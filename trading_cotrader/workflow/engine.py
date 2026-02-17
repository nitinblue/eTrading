"""
Workflow Engine — Core orchestrator for the continuous trading workflow.

Uses `transitions` state machine to coordinate all agents through
the trading day: boot → macro → screen → review → execute →
monitor → trade management → trade review → report → idle.

Trade management (rolls, adjustments, exits) runs in the
TRADE_MANAGEMENT state and produces signals in TRADE_REVIEW
for user approval.

Usage:
    engine = WorkflowEngine(paper_mode=True, use_mock=True)
    engine.boot()  # single cycle
    # or
    engine.handle_user_intent(UserIntent(action='status'))
"""

from datetime import datetime
from typing import Optional
import json
import uuid
import logging

from transitions import Machine

from trading_cotrader.workflow.states import WorkflowStates, TRANSITIONS
from trading_cotrader.agents.protocol import AgentStatus
from trading_cotrader.agents.messages import UserIntent, SystemResponse
from trading_cotrader.config.workflow_config_loader import load_workflow_config, WorkflowConfig

# Agents
from trading_cotrader.agents.safety.guardian import GuardianAgent
from trading_cotrader.agents.perception.market_data import MarketDataAgent
from trading_cotrader.agents.perception.portfolio_state import PortfolioStateAgent
from trading_cotrader.agents.perception.calendar import CalendarAgent
from trading_cotrader.agents.analysis.macro import MacroAgent
from trading_cotrader.agents.analysis.screener import ScreenerAgent
from trading_cotrader.agents.analysis.evaluator import EvaluatorAgent
from trading_cotrader.agents.analysis.risk import RiskAgent
from trading_cotrader.agents.execution.executor import ExecutorAgent
from trading_cotrader.agents.execution.broker_router import BrokerRouter
from trading_cotrader.agents.execution.notifier import NotifierAgent
from trading_cotrader.agents.execution.reporter import ReporterAgent
from trading_cotrader.agents.learning.accountability import AccountabilityAgent
from trading_cotrader.agents.learning.session_objectives import SessionObjectivesAgent
from trading_cotrader.agents.learning.qa_agent import QAAgent
from trading_cotrader.agents.analysis.capital import CapitalUtilizationAgent
from trading_cotrader.agents.decision.interaction import InteractionManager

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """
    Core orchestrator. Uses transitions.Machine for state management
    and coordinates all agents in sequence.

    Human pause points:
        - RECOMMENDATION_REVIEW: entry recommendations await user decision
        - TRADE_REVIEW: roll/adjust/exit signals await user decision

    Portfolio evaluation covers:
        - Profit targets (take profit)
        - Stop losses (book loss)
        - DTE-based exits
        - Delta breach exits
        - Roll opportunities
        - Adjustment signals
        - Liquidity checks (illiquid → close instead of adjust)
    """

    def __init__(
        self,
        broker=None,
        use_mock: bool = False,
        paper_mode: bool = True,
        config_path: str = None,
    ):
        self.broker = broker
        self.use_mock = use_mock
        self.paper_mode = paper_mode

        # Load configuration
        self.config: WorkflowConfig = load_workflow_config(config_path)

        # Initialize broker registry and adapter factory
        from trading_cotrader.config.broker_config_loader import load_broker_registry, BrokerRegistry
        from trading_cotrader.adapters.factory import BrokerAdapterFactory

        try:
            self.broker_registry = load_broker_registry()
        except FileNotFoundError:
            self.broker_registry = BrokerRegistry()

        # Create adapters via factory (or use pre-provided broker)
        adapters = {}
        if broker:
            adapters['tastytrade'] = broker
        else:
            # Create API adapters from registry
            api_adapters = BrokerAdapterFactory.create_all_api(self.broker_registry)
            adapters.update(api_adapters)

        self.broker_router = BrokerRouter(self.broker_registry, adapters)

        # Shared context between all agents
        self.context: dict = {
            'cycle_count': 0,
            'engine_start_time': datetime.utcnow().isoformat(),
        }

        # Initialize all agents
        self.guardian = GuardianAgent(self.config)
        self.market_data = MarketDataAgent(broker, use_mock)
        self.portfolio_state = PortfolioStateAgent()
        self.calendar_agent = CalendarAgent(self.config)
        self.macro = MacroAgent(broker)
        self.screener = ScreenerAgent(broker)
        self.evaluator = EvaluatorAgent(broker)
        self.risk = RiskAgent()
        self.executor = ExecutorAgent(broker, paper_mode, broker_router=self.broker_router)
        self.notifier = NotifierAgent(self.config)
        self.reporter = ReporterAgent()
        self.accountability = AccountabilityAgent()
        self.capital_utilization = CapitalUtilizationAgent(self.config)
        self.session_objectives = SessionObjectivesAgent()
        self.qa_agent = QAAgent(self.config)
        self.interaction = InteractionManager(self)

        # State machine — states are string values from WorkflowStates
        self.machine = Machine(
            model=self,
            states=[s.value for s in WorkflowStates],
            transitions=self._prepare_transitions(),
            initial=WorkflowStates.IDLE.value,
            send_event=True,
            auto_transitions=False,
        )

        # Try to restore persisted state
        self._restore_state()

    def _prepare_transitions(self) -> list:
        """Convert WorkflowStates enum values in transitions to strings."""
        prepared = []
        for t in TRANSITIONS:
            entry = dict(t)
            # Convert source
            src = entry['source']
            if isinstance(src, WorkflowStates):
                entry['source'] = src.value
            elif isinstance(src, list):
                entry['source'] = [s.value if isinstance(s, WorkflowStates) else s for s in src]
            # Convert dest
            dst = entry['dest']
            if isinstance(dst, WorkflowStates):
                entry['dest'] = dst.value
            prepared.append(entry)
        return prepared

    # -----------------------------------------------------------------
    # State callbacks (called by transitions library on state entry)
    # -----------------------------------------------------------------

    def on_enter_booting(self, event):
        """Boot sequence: calendar → market data → portfolio state → safety."""
        logger.info("=== WORKFLOW BOOT ===")
        self.context['cycle_count'] = self.context.get('cycle_count', 0) + 1

        # Calendar check
        cal_result = self.calendar_agent.run(self.context)
        self._log_agent(cal_result)

        if not self.context.get('is_trading_day', True):
            logger.info("Not a trading day. Going idle.")
            self.go_idle()
            return

        # Market data
        md_result = self.market_data.run(self.context)
        self._log_agent(md_result)

        # Portfolio state
        ps_result = self.portfolio_state.run(self.context)
        self._log_agent(ps_result)

        # Safety check
        safety = self.guardian.run(self.context)
        self._log_agent(safety)

        if safety.status == AgentStatus.BLOCKED:
            logger.warning(f"Guardian blocked boot: {safety.messages}")
            self.halt()
            return

        # Capital utilization check at boot
        cap_result = self.capital_utilization.run(self.context)
        self._log_agent(cap_result)

        # Set session objectives for the day
        obj_result = self.session_objectives.set_objectives(self.context)
        self._log_agent(obj_result)

        # Notify if capital alerts exist
        alerts = self.context.get('capital_alerts', [])
        if alerts:
            self.notifier.notify_idle_capital(alerts)

        self.check_macro()

    def on_enter_macro_check(self, event):
        """Evaluate macro conditions."""
        result = self.macro.run(self.context)
        self._log_agent(result)

        should_screen = self.context.get('macro_assessment', {}).get('should_screen', True)
        if not should_screen:
            logger.info("Macro: risk_off — skipping screeners, going to monitoring")
            self.skip_to_monitor()
        else:
            self.screen()

    def on_enter_screening(self, event):
        """Run screeners and calculate risk."""
        result = self.screener.run(self.context)
        self._log_agent(result)

        risk_result = self.risk.run(self.context)
        self._log_agent(risk_result)

        recs = self.context.get('pending_recommendations', [])
        if recs:
            logger.info(f"Screening produced {len(recs)} recommendations")
            self.review_recs()
        else:
            logger.info("No recommendations from screeners")
            self.skip_to_monitor()

    def on_enter_recommendation_review(self, event):
        """HUMAN PAUSE — present recommendations and wait for user input."""
        recs = self.context.get('pending_recommendations', [])
        self.notifier.notify_recommendations(recs)
        self._persist_state()
        logger.info(
            f"WAITING FOR USER: {len(recs)} recommendation(s) pending. "
            f"Use 'approve <id>' / 'reject <id>' / 'list' / 'status'"
        )

    def on_enter_monitoring(self, event):
        """Home state during market hours. Persists state."""
        logger.info("=== MONITORING ===")
        self._persist_state()

    def on_enter_trade_management(self, event):
        """
        Trade management — evaluate ALL open positions for:
            - Roll opportunities (approaching expiration)
            - Adjustments (rebalancing legs, delta correction)
            - Profit targets (take profit)
            - Stop losses (book loss)
            - DTE-based exits (time decay)
            - Delta breach (hedging failure)
            - Liquidity check (illiquid → force close)

        Uses PortfolioEvaluationService which wires RulesEngine
        to live trade data.
        """
        logger.info("=== TRADE MANAGEMENT ===")

        # Refresh portfolio state before evaluation
        ps_result = self.portfolio_state.run(self.context)
        self._log_agent(ps_result)

        # Run evaluation across all portfolios
        result = self.evaluator.run(self.context)
        self._log_agent(result)

        signals = self.context.get('exit_signals', [])
        if signals:
            logger.info(f"Trade management found {len(signals)} signal(s) (roll/adjust/exit)")
            self.review_trades()
        else:
            logger.info("No trade management signals — back to monitoring")
            self.skip_to_monitor()

    def on_enter_trade_review(self, event):
        """HUMAN PAUSE — present roll/adjust/exit signals and wait for user input."""
        signals = self.context.get('exit_signals', [])
        self.notifier.notify_exits(signals)
        self._persist_state()
        logger.info(
            f"WAITING FOR USER: {len(signals)} trade management signal(s) pending review. "
            f"Use 'approve <id>' / 'reject <id>' / 'list'"
        )

    def on_enter_execution(self, event):
        """Execute all approved actions."""
        approved = self.context.get('approved_actions', [])
        executed = 0

        for action in approved:
            # Guardian constraint check per action
            ok, reason = self.guardian.check_trading_constraints(action, self.context)
            if ok:
                self.context['action'] = action
                result = self.executor.run(self.context)
                self._log_agent(result)
                if result.status == AgentStatus.COMPLETED:
                    executed += 1
            else:
                logger.warning(f"Guardian blocked action: {reason}")

        # Clear approved actions
        self.context['approved_actions'] = []
        logger.info(f"Executed {executed}/{len(approved)} approved actions")

        # Refresh portfolio state after execution
        self.portfolio_state.run(self.context)
        self.monitor()

    def on_enter_eod_evaluation(self, event):
        """End-of-day evaluation — run one final exit check."""
        logger.info("=== EOD EVALUATION ===")

        # Final portfolio state refresh
        self.portfolio_state.run(self.context)

        # Run evaluator one more time
        self.evaluator.run(self.context)

        # Generate report
        self.report()

    def on_enter_reporting(self, event):
        """Generate reports, run accountability, capture snapshots, send notifications."""
        logger.info("=== REPORTING ===")

        # Accountability metrics first (reporter needs them)
        self.accountability.run(self.context)

        # Final capital utilization snapshot
        self.capital_utilization.run(self.context)

        # Capture daily snapshots for all portfolios (feeds analytics + ML)
        snapshot_results = self._capture_snapshots()
        self.context['snapshot_results'] = snapshot_results

        # Accumulate ML training data
        self._accumulate_ml_data()

        # Session performance evaluation (objectives vs actuals)
        perf_result = self.session_objectives.evaluate_performance(self.context)
        self._log_agent(perf_result)

        # QA assessment
        qa_result = self.qa_agent.run(self.context)
        self._log_agent(qa_result)

        # Generate report (now includes capital + session + QA sections)
        self.reporter.run(self.context)
        self.notifier.send_daily_summary(self.context)
        self.go_idle()

    def on_enter_halted(self, event):
        """Trading halted — notify and persist."""
        reason = self.context.get('halt_reason', 'Unknown')
        logger.warning(f"=== HALTED: {reason} ===")
        self.notifier.notify_halt(reason)
        self._persist_state()

    # -----------------------------------------------------------------
    # Condition methods (used by transitions library)
    # -----------------------------------------------------------------

    def is_not_risk_off(self, event) -> bool:
        """Condition: macro is not risk_off."""
        return self.context.get('macro_assessment', {}).get('should_screen', True)

    def has_recommendations(self, event) -> bool:
        """Condition: there are pending entry recommendations."""
        return bool(self.context.get('pending_recommendations'))

    def has_exit_signals(self, event) -> bool:
        """Condition: there are exit/roll/adjust signals."""
        return bool(self.context.get('exit_signals'))

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def handle_user_intent(self, intent: UserIntent) -> SystemResponse:
        """Handle a user command via the InteractionManager."""
        response = self.interaction.handle(intent)

        # If user approved something and we're in a review state, try to execute
        if intent.action == 'approve' and self.context.get('approved_actions'):
            current = self.state
            if current == WorkflowStates.RECOMMENDATION_REVIEW.value:
                self.execute()
            elif current == WorkflowStates.TRADE_REVIEW.value:
                self.execute_trade_action()

        return response

    def run_monitoring_cycle(self):
        """
        Called periodically (every 30 min) by APScheduler during market hours.

        Refreshes market data, portfolio state, checks safety,
        and evaluates positions for exit signals.
        """
        logger.info("--- Monitoring cycle ---")

        # Only run if in monitoring state
        current = self.state
        if current != WorkflowStates.MONITORING.value:
            logger.debug(f"Skip monitoring cycle: state is {current}")
            return

        # Refresh
        self.market_data.run(self.context)
        self.portfolio_state.run(self.context)

        # Capital utilization check
        cap_result = self.capital_utilization.run(self.context)
        self._log_agent(cap_result)

        # Notify if capital alerts (respects nag frequency via severity escalation)
        alerts = self.context.get('capital_alerts', [])
        if alerts:
            self.notifier.notify_idle_capital(alerts)

        # Safety check
        safety = self.guardian.run(self.context)
        if safety.status == AgentStatus.BLOCKED:
            self.halt()
            return

        # Trade management (rolls, adjustments, exits)
        self.manage_trades()

    def run_once(self):
        """Run a single complete cycle for testing."""
        logger.info("=== RUNNING SINGLE CYCLE ===")
        self.boot()

    # -----------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------

    def _persist_state(self):
        """Save current state and context to WorkflowStateORM."""
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.core.database.schema import WorkflowStateORM

            # Serialize context (remove non-serializable items)
            ctx_copy = {}
            for k, v in self.context.items():
                try:
                    json.dumps(v)
                    ctx_copy[k] = v
                except (TypeError, ValueError):
                    ctx_copy[k] = str(v)

            with session_scope() as session:
                # Get or create single workflow state row
                state_row = session.query(WorkflowStateORM).first()
                if state_row is None:
                    state_row = WorkflowStateORM(
                        id=str(uuid.uuid4()),
                        current_state=self.state,
                    )
                    session.add(state_row)

                state_row.previous_state = state_row.current_state
                state_row.current_state = self.state
                state_row.last_transition_at = datetime.utcnow()
                state_row.cycle_count = self.context.get('cycle_count', 0)
                state_row.halted = (self.state == WorkflowStates.HALTED.value)
                state_row.halt_reason = self.context.get('halt_reason')
                state_row.halt_override_rationale = self.context.get('halt_override_rationale')
                state_row.context_json = ctx_copy
                state_row.updated_at = datetime.utcnow()

        except Exception as e:
            logger.error(f"Failed to persist state: {e}")

    def _restore_state(self):
        """Restore state from DB if available."""
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.core.database.schema import WorkflowStateORM

            with session_scope() as session:
                state_row = session.query(WorkflowStateORM).first()
                if state_row and state_row.current_state:
                    # Validate state is known
                    valid_states = {s.value for s in WorkflowStates}
                    if state_row.current_state in valid_states:
                        # Only restore non-halted states to idle
                        restored = state_row.current_state
                        if restored == WorkflowStates.HALTED.value:
                            self.machine.set_state(WorkflowStates.HALTED.value)
                            logger.info(f"Restored halted state. Reason: {state_row.halt_reason}")
                        else:
                            # Start fresh from idle — don't resume mid-flow
                            logger.info(f"Previous state was {restored}, starting from idle")

                    # Restore context
                    if state_row.context_json:
                        self.context.update(state_row.context_json)
                        logger.info(f"Restored context (cycle {self.context.get('cycle_count', 0)})")

        except Exception as e:
            logger.debug(f"Could not restore state (first run?): {e}")

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _capture_snapshots(self) -> dict:
        """Capture daily snapshots for all active portfolios."""
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.services.snapshot_service import SnapshotService

            with session_scope() as session:
                svc = SnapshotService(session)
                results = svc.capture_all_portfolio_snapshots()
                total = len(results)
                ok = sum(results.values())
                logger.info(f"Snapshots: {ok}/{total} portfolios captured")
                return results
        except Exception as e:
            logger.error(f"Snapshot capture failed: {e}")
            return {}

    def _accumulate_ml_data(self) -> None:
        """Feed ML pipeline with latest snapshot data."""
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.ai_cotrader.data_pipeline import MLDataPipeline
            from trading_cotrader.core.database.schema import PortfolioORM

            with session_scope() as session:
                pipeline = MLDataPipeline(session)

                # Get first real portfolio for ML accumulation
                portfolio = session.query(PortfolioORM).filter(
                    PortfolioORM.portfolio_type == 'real'
                ).first()

                if portfolio:
                    pipeline.accumulate_training_data(
                        portfolio=portfolio,
                        positions=portfolio.positions or [],
                    )

                status = pipeline.get_ml_status()
                self.context['ml_status'] = status
                logger.info(
                    f"ML pipeline: {status.get('snapshots', 0)} snapshots, "
                    f"{status.get('events_with_outcomes', 0)} labeled events"
                )
        except Exception as e:
            logger.warning(f"ML pipeline update failed (non-blocking): {e}")

    def _log_agent(self, result):
        """Log agent result."""
        for msg in result.messages:
            level = logging.WARNING if result.status == AgentStatus.ERROR else logging.INFO
            logger.log(level, f"[{result.agent_name}] {msg}")
