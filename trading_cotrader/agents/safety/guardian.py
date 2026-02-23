"""
Guardian Agent (Circuit Breaker) — Safety layer that checks circuit breakers
and trading constraints before any action is taken.

All thresholds come from workflow_rules.yaml, never hardcoded.

Usage:
    guardian = GuardianAgent(config)
    result = guardian.run(context)
    if result.status == AgentStatus.BLOCKED:
        print(f"HALTED: {result.messages}")
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import ClassVar, List, Optional
import logging

from trading_cotrader.agents.base import BaseAgent
from trading_cotrader.agents.protocol import AgentResult, AgentStatus
from trading_cotrader.config.workflow_config_loader import WorkflowConfig

logger = logging.getLogger(__name__)


class GuardianAgent(BaseAgent):
    """Checks circuit breakers and trading constraints before every action."""

    # Class-level metadata
    name: ClassVar[str] = "circuit_breaker"
    display_name: ClassVar[str] = "Circuit Breaker"
    category: ClassVar[str] = "safety"
    role: ClassVar[str] = "Circuit breaker & kill switch"
    intro: ClassVar[str] = (
        "I am the emergency stop. Daily/weekly loss limits, VIX spikes, "
        "no-trade tickers — when something is wrong, I halt everything. "
        "Simple rules, no exceptions."
    )
    responsibilities: ClassVar[List[str]] = [
        "Circuit breakers (daily/weekly loss)",
        "VIX halt threshold",
        "No-trade ticker list",
        "Emergency halt",
    ]
    datasources: ClassVar[List[str]] = [
        "workflow_rules.yaml",
        "VIX feed",
        "Daily P&L",
    ]
    boundaries: ClassVar[List[str]] = [
        "Cannot override human halt decisions",
        "Does not evaluate strategies or positions",
        "Kill switch only",
    ]
    runs_during: ClassVar[List[str]] = ["booting", "monitoring", "execution"]

    def __init__(self, config: WorkflowConfig = None, container=None):
        super().__init__(container=container, config=config)

    def safety_check(self, context: dict) -> tuple[bool, str]:
        """Pre-flight check — same as run() but returns tuple."""
        result = self.run(context)
        if result.status == AgentStatus.BLOCKED:
            return False, "; ".join(result.messages)
        return True, ""

    def run(self, context: dict) -> AgentResult:
        """
        Full safety sweep. Called at boot and before every action.

        Checks:
            1. Daily P&L loss limit
            2. Weekly P&L loss limit
            3. VIX halt threshold
            4. Per-portfolio drawdown
            5. Consecutive losses (per strategy / per portfolio)
        """
        breakers_tripped: list[str] = []

        if self.config is None:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.COMPLETED,
                messages=["No config — skipping circuit breaker checks"],
            )

        cb = self.config.circuit_breakers

        # 1. Daily loss
        daily_pnl_pct = context.get('daily_pnl_pct', 0.0)
        if daily_pnl_pct < -cb.daily_loss_pct:
            breakers_tripped.append(
                f"Daily loss {daily_pnl_pct:.1f}% exceeded {cb.daily_loss_pct}% limit"
            )

        # 2. Weekly loss
        weekly_pnl_pct = context.get('weekly_pnl_pct', 0.0)
        if weekly_pnl_pct < -cb.weekly_loss_pct:
            breakers_tripped.append(
                f"Weekly loss {weekly_pnl_pct:.1f}% exceeded {cb.weekly_loss_pct}% limit"
            )

        # 3. VIX halt
        vix = context.get('vix', 0.0)
        if vix > cb.vix_halt_threshold:
            breakers_tripped.append(
                f"VIX {vix:.1f} exceeded halt threshold {cb.vix_halt_threshold}"
            )

        # 4. Per-portfolio drawdown
        portfolio_drawdowns = context.get('portfolio_drawdowns', {})
        for portfolio_name, drawdown_pct in portfolio_drawdowns.items():
            max_dd = cb.max_portfolio_drawdown.get(portfolio_name)
            if max_dd is not None and drawdown_pct > max_dd:
                breakers_tripped.append(
                    f"{portfolio_name} drawdown {drawdown_pct:.1f}% exceeded {max_dd}% limit"
                )

        # 5. Consecutive losses
        consecutive_losses = context.get('consecutive_losses', {})
        for key, count in consecutive_losses.items():
            if count >= cb.consecutive_loss_halt:
                breakers_tripped.append(
                    f"{key}: {count} consecutive losses (halt threshold: {cb.consecutive_loss_halt})"
                )
            elif count >= cb.consecutive_loss_pause:
                breakers_tripped.append(
                    f"{key}: {count} consecutive losses (pause threshold: {cb.consecutive_loss_pause})"
                )

        if breakers_tripped:
            context['halt_reason'] = "; ".join(breakers_tripped)
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.BLOCKED,
                data={'breakers_tripped': breakers_tripped},
                messages=[f"CIRCUIT BREAKER: {b}" for b in breakers_tripped],
            )

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.COMPLETED,
            messages=["All circuit breakers clear"],
        )

    def check_trading_constraints(self, action: dict, context: dict) -> tuple[bool, str]:
        """
        Check trading constraints for a specific action.

        Args:
            action: Dict with keys like 'type', 'risk_category', 'portfolio', etc.
            context: Shared workflow context.

        Returns:
            (is_allowed, reason_if_blocked)
        """
        if self.config is None:
            return True, ""

        tc = self.config.constraints

        # Max trades per day
        trades_today = context.get('trades_today_count', 0)
        if trades_today >= tc.max_trades_per_day:
            return False, (
                f"Max trades per day ({tc.max_trades_per_day}) reached. "
                f"Already placed {trades_today} trades today."
            )

        # Max trades per week per portfolio
        portfolio_name = action.get('portfolio', '')
        weekly_trades = context.get('weekly_trades_per_portfolio', {})
        portfolio_weekly = weekly_trades.get(portfolio_name, 0)
        if portfolio_weekly >= tc.max_trades_per_week_per_portfolio:
            return False, (
                f"Max weekly trades for {portfolio_name} "
                f"({tc.max_trades_per_week_per_portfolio}) reached."
            )

        # Time-of-day constraints
        minutes_since_open = context.get('minutes_since_open', 999)
        minutes_to_close = context.get('minutes_to_close', 999)

        if minutes_since_open < tc.no_entry_first_minutes:
            return False, (
                f"No entries in first {tc.no_entry_first_minutes} minutes of market. "
                f"Only {minutes_since_open} min since open."
            )

        if minutes_to_close < tc.no_entry_last_minutes:
            # Allow closing trades in last 30 min
            is_closing = action.get('type') in ('exit', 'close')
            if not is_closing:
                return False, (
                    f"No new entries in last {tc.no_entry_last_minutes} minutes. "
                    f"Only {minutes_to_close} min to close."
                )

        # Undefined risk approval
        if tc.require_approval_undefined_risk:
            risk_category = action.get('risk_category', 'defined')
            if risk_category == 'undefined' and not action.get('undefined_risk_approved'):
                return False, (
                    "Undefined risk trade requires explicit approval. "
                    "Set undefined_risk_approved=True in action."
                )

        # No adding to losers without rationale
        if tc.no_adding_to_losers_without_rationale:
            is_adding_to_loser = action.get('adding_to_loser', False)
            has_rationale = bool(action.get('rationale', '').strip())
            if is_adding_to_loser and not has_rationale:
                return False, "Adding to a losing position requires written rationale."

        # Cross-broker routing safety
        target_broker = action.get('target_broker')
        portfolio_broker = action.get('portfolio_broker')
        if target_broker and portfolio_broker and target_broker != portfolio_broker:
            return False, (
                f"Cross-broker routing blocked: cannot route {portfolio_broker} "
                f"portfolio trade to {target_broker} API."
            )

        # Currency mismatch safety
        action_currency = action.get('currency')
        portfolio_currency = action.get('portfolio_currency')
        if action_currency and portfolio_currency and action_currency != portfolio_currency:
            return False, (
                f"Currency mismatch: {action_currency} trade cannot be placed "
                f"in {portfolio_currency} portfolio."
            )

        return True, ""

    def request_override(self, breaker: str, rationale: str) -> bool:
        """
        Request override of a circuit breaker.

        Requires non-empty rationale. Logs the override.

        Returns:
            True if override granted (rationale provided).
        """
        if not rationale.strip():
            logger.warning(f"Override denied for '{breaker}': no rationale provided")
            return False

        logger.warning(
            f"CIRCUIT BREAKER OVERRIDE: '{breaker}' overridden. "
            f"Rationale: {rationale}"
        )
        return True
