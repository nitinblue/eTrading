"""
Interaction Manager — Routes user intents to workflow engine actions.

Handles: approve, reject, defer, status, list, halt, resume, override.
"""

from datetime import datetime
from typing import TYPE_CHECKING
import logging

from trading_cotrader.agents.messages import UserIntent, SystemResponse

if TYPE_CHECKING:
    from trading_cotrader.workflow.engine import WorkflowEngine

logger = logging.getLogger(__name__)


class InteractionManager:
    """Routes user commands to the appropriate workflow engine actions."""

    def __init__(self, engine: 'WorkflowEngine'):
        self.engine = engine

    def handle(self, intent: UserIntent) -> SystemResponse:
        """
        Route a UserIntent to the correct handler.

        Returns SystemResponse with results and available actions.
        """
        handlers = {
            'approve': self._approve,
            'reject': self._reject,
            'defer': self._defer,
            'status': self._status,
            'list': self._list_pending,
            'halt': self._halt,
            'resume': self._resume,
            'override': self._override,
            'help': self._help,
        }

        handler = handlers.get(intent.action)
        if not handler:
            return SystemResponse(
                message=f"Unknown action: {intent.action}. "
                        f"Available: {', '.join(handlers.keys())}",
                available_actions=list(handlers.keys()),
            )

        try:
            return handler(intent)
        except Exception as e:
            logger.error(f"Error handling intent '{intent.action}': {e}")
            return SystemResponse(
                message=f"Error: {e}",
                requires_action=False,
            )

    def _approve(self, intent: UserIntent) -> SystemResponse:
        """Approve a recommendation."""
        if not intent.target:
            return SystemResponse(
                message="Usage: approve <recommendation_id> [--portfolio <name>]",
                requires_action=True,
            )

        # Log decision
        self.engine.accountability.log_decision(
            rec_id=intent.target,
            response='approved',
            rationale=intent.rationale or 'Approved via workflow',
            presented_at=datetime.utcnow(),  # approximation
            responded_at=datetime.utcnow(),
            decision_type=intent.parameters.get('type', 'entry'),
        )

        # Add to approved actions
        action = {
            'recommendation_id': intent.target,
            'portfolio': intent.parameters.get('portfolio'),
            'notes': intent.rationale or 'Approved via workflow',
        }
        approved = self.engine.context.get('approved_actions', [])
        approved.append(action)
        self.engine.context['approved_actions'] = approved

        return SystemResponse(
            message=f"Approved recommendation {intent.target[:8]}... "
                    f"({len(approved)} action(s) queued)",
            data={'approved_count': len(approved)},
        )

    def _reject(self, intent: UserIntent) -> SystemResponse:
        """Reject a recommendation."""
        if not intent.target:
            return SystemResponse(message="Usage: reject <recommendation_id>")

        self.engine.accountability.log_decision(
            rec_id=intent.target,
            response='rejected',
            rationale=intent.rationale or 'Rejected via workflow',
            presented_at=datetime.utcnow(),
            responded_at=datetime.utcnow(),
        )

        # Try to reject in DB
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.services.recommendation_service import RecommendationService

            with session_scope() as session:
                svc = RecommendationService(session, broker=self.engine.broker)
                svc.reject_recommendation(
                    intent.target,
                    reason=intent.rationale or 'Rejected via workflow',
                )
        except Exception as e:
            logger.warning(f"Could not reject rec in DB: {e}")

        return SystemResponse(
            message=f"Rejected recommendation {intent.target[:8]}...",
        )

    def _defer(self, intent: UserIntent) -> SystemResponse:
        """Defer a decision for later."""
        if not intent.target:
            return SystemResponse(message="Usage: defer <recommendation_id>")

        self.engine.accountability.log_decision(
            rec_id=intent.target,
            response='deferred',
            rationale=intent.rationale or 'Deferred via workflow',
            presented_at=datetime.utcnow(),
            responded_at=datetime.utcnow(),
        )

        return SystemResponse(
            message=f"Deferred recommendation {intent.target[:8]}... "
                    f"(will be reminded in {self.engine.config.decision_timeouts.reminder_minutes} min)",
        )

    def _status(self, intent: UserIntent = None) -> SystemResponse:
        """Show current workflow status."""
        ctx = self.engine.context
        state = self.engine.state if hasattr(self.engine, 'state') else 'unknown'

        lines = [
            f"State: {state}",
            f"Cycle: {ctx.get('cycle_count', 0)}",
            f"Trading day: {ctx.get('is_trading_day', '?')}",
            f"Cadences: {ctx.get('cadences', [])}",
            f"VIX: {ctx.get('vix', '?')}",
            f"Open trades: {len(ctx.get('open_trades', []))}",
            f"Pending entry recs: {len(ctx.get('pending_recommendations', []))}",
            f"Exit signals: {len(ctx.get('exit_signals', []))}",
            f"Trades today: {ctx.get('trades_today_count', 0)}",
        ]

        risk = ctx.get('risk_snapshot', {})
        if risk:
            lines.append(f"VaR 95%: ${risk.get('var_95', 0):,.0f}")

        macro = ctx.get('macro_assessment', {})
        if macro:
            lines.append(f"Macro: {macro.get('regime', '?')} — {macro.get('rationale', '')[:60]}")

        return SystemResponse(
            message="\n".join(lines),
            data={
                'state': str(state),
                'vix': ctx.get('vix'),
                'open_trades': len(ctx.get('open_trades', [])),
            },
            available_actions=['approve', 'reject', 'defer', 'list', 'halt', 'resume'],
        )

    def _list_pending(self, intent: UserIntent = None) -> SystemResponse:
        """List all pending recommendations."""
        ctx = self.engine.context
        recs = ctx.get('pending_recommendations', [])
        exits = ctx.get('exit_signals', [])

        if not recs and not exits:
            return SystemResponse(message="No pending decisions.")

        lines = []
        if recs:
            lines.append("ENTRY RECOMMENDATIONS:")
            for r in recs:
                lines.append(
                    f"  [{r.get('id', '?')[:8]}] {r.get('underlying', '?')} "
                    f"{r.get('strategy_type', '?')} conf={r.get('confidence', '?')}"
                )

        if exits:
            lines.append("EXIT SIGNALS:")
            for s in exits:
                lines.append(
                    f"  [{s.get('id', '?')[:8]}] {s.get('underlying', '?')} "
                    f"{s.get('type', '?')} urgency={s.get('exit_urgency', '?')}"
                )

        return SystemResponse(
            message="\n".join(lines),
            pending_decisions=[*recs, *exits],
            requires_action=True,
            available_actions=['approve', 'reject', 'defer'],
        )

    def _halt(self, intent: UserIntent) -> SystemResponse:
        """Manually halt trading."""
        reason = intent.rationale or "Manual halt via user command"
        self.engine.context['halt_reason'] = reason
        try:
            self.engine.halt()
        except Exception:
            pass  # may already be halted
        return SystemResponse(message=f"Trading HALTED: {reason}")

    def _resume(self, intent: UserIntent) -> SystemResponse:
        """Resume from halted state."""
        if not intent.rationale:
            return SystemResponse(
                message="Resume requires rationale. Usage: resume --rationale 'why it's safe to resume'",
                requires_action=True,
            )
        try:
            self.engine.context['halt_override_rationale'] = intent.rationale
            self.engine.resume()
            return SystemResponse(message=f"Resumed trading. Rationale: {intent.rationale}")
        except Exception as e:
            return SystemResponse(message=f"Cannot resume: {e}")

    def _override(self, intent: UserIntent) -> SystemResponse:
        """Override a circuit breaker (requires rationale)."""
        if not intent.rationale:
            return SystemResponse(
                message="Override requires written rationale. "
                        "Usage: override --target <breaker> --rationale 'why'",
                requires_action=True,
            )

        breaker = intent.target or "unknown"
        granted = self.engine.guardian.request_override(breaker, intent.rationale)
        if granted:
            return SystemResponse(message=f"Override granted for '{breaker}'")
        return SystemResponse(message=f"Override DENIED for '{breaker}' — no rationale")

    def _help(self, intent: UserIntent = None) -> SystemResponse:
        """Show available commands."""
        return SystemResponse(
            message=(
                "Available commands:\n"
                "  status             — Show current workflow state\n"
                "  list               — List pending recommendations\n"
                "  approve <id>       — Approve a recommendation\n"
                "  reject <id>        — Reject a recommendation\n"
                "  defer <id>         — Defer a decision\n"
                "  halt               — Halt all trading\n"
                "  resume             — Resume trading (requires rationale)\n"
                "  override <breaker> — Override circuit breaker (requires rationale)\n"
                "  help               — Show this help\n"
                "  quit               — Stop the workflow engine"
            ),
            available_actions=['approve', 'reject', 'defer', 'status', 'list',
                             'halt', 'resume', 'override', 'help', 'quit'],
        )
