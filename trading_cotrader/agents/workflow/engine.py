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

from trading_cotrader.agents.workflow.states import WorkflowStates, TRANSITIONS
from trading_cotrader.agents.protocol import AgentStatus
from trading_cotrader.agents.messages import UserIntent, SystemResponse
from trading_cotrader.config.workflow_config_loader import load_workflow_config, WorkflowConfig

# The 5 domain agents
from trading_cotrader.agents.domain.sentinel import SentinelAgent
from trading_cotrader.agents.domain.scout import ScoutAgent
from trading_cotrader.agents.domain.steward import StewardAgent
from trading_cotrader.agents.domain.maverick import MaverickAgent
from trading_cotrader.agents.domain.atlas import AtlasAgent

# Non-agent utilities used by engine
from trading_cotrader.adapters.broker_router import BrokerRouter
from trading_cotrader.agents.workflow.interaction import InteractionManager

# Services replacing former agents (calendar, market_data, macro)
from trading_cotrader.services.macro_context_service import MacroContextService, MacroOverride


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
            # Pre-provided broker (e.g., from harness) — assumed already authenticated
            adapters['tastytrade'] = broker
        else:
            # Create API adapters from registry and authenticate each one
            api_adapters = BrokerAdapterFactory.create_all_api(self.broker_registry)
            for name, adapter in api_adapters.items():
                if hasattr(adapter, 'authenticate'):
                    try:
                        if adapter.authenticate():
                            logger.info(f"Broker [{name}] authenticated successfully")
                            adapters[name] = adapter
                        else:
                            logger.warning(f"Broker [{name}] authentication failed — skipping")
                    except Exception as e:
                        logger.warning(f"Broker [{name}] auth error: {e} — skipping")
                else:
                    adapters[name] = adapter

        self.broker_router = BrokerRouter(self.broker_registry, adapters)
        self._adapters = adapters  # Expose for API endpoints (agent brain, transactions, etc.)

        # Shared context between all agents
        self.context: dict = {
            'cycle_count': 0,
            'engine_start_time': datetime.utcnow().isoformat(),
        }

        # Initialize ContainerManager so API endpoints have live data
        self._init_container_manager()

        # Initialize the 5 domain agents (BaseAgent subclasses)
        research_container = self.container_manager.research if self.container_manager else None
        self.sentinel = SentinelAgent(config=self.config, container_manager=self.container_manager)
        self.scout = ScoutAgent(container=research_container, config=self.config)
        self.steward = StewardAgent(container_manager=self.container_manager, config=self.config)
        self.maverick = MaverickAgent(container_manager=self.container_manager, config=self.config)
        self.atlas = AtlasAgent(config=self.config)

        # Service replacing MacroAgent
        self._macro_service = MacroContextService(broker=broker)

        # Interaction manager (command router, not an agent)
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
    # Container access (for API endpoints)
    # -----------------------------------------------------------------

    @property
    def container_manager(self):
        """Expose container_manager from context for API endpoints."""
        return self.context.get('container_manager')

    # -----------------------------------------------------------------
    # State callbacks (called by transitions library on state entry)
    # -----------------------------------------------------------------

    def on_enter_booting(self, event):
        """Boot sequence: infrastructure only — all agents disabled."""
        logger.info("=== WORKFLOW BOOT (agents disabled) ===")
        self.context['cycle_count'] = self.context.get('cycle_count', 0) + 1

        # Calendar check (inlined — was CalendarAgent)
        self._check_trading_day()

        if not self.context.get('is_trading_day', True):
            logger.info("Not a trading day. Going idle.")
            self.go_idle()
            return

        # Sync positions from broker(s) into DB
        self._sync_broker_positions()

        # Refresh containers from DB so API has data
        self._refresh_containers()

        # Skip all agents — go straight to monitoring
        self.check_macro()

    def on_enter_macro_check(self, event):
        """Macro check — agents disabled, skip straight to monitoring."""
        logger.info("Macro check skipped (agents disabled) — going to monitoring")
        self.skip_to_monitor()

    def on_enter_screening(self, event):
        """Screening — agents disabled, skip to monitoring."""
        logger.info("Screening skipped (agents disabled)")
        self.skip_to_monitor()

    def on_enter_recommendation_review(self, event):
        """HUMAN PAUSE — present recommendations and wait for user input."""
        recs = self.context.get('pending_recommendations', [])
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
        """Trade management — agents disabled, skip to monitoring."""
        logger.info("Trade management skipped (agents disabled)")
        self.skip_to_monitor()

    def on_enter_trade_review(self, event):
        """HUMAN PAUSE — present roll/adjust/exit signals and wait for user input."""
        signals = self.context.get('exit_signals', [])
        self._persist_state()
        logger.info(
            f"WAITING FOR USER: {len(signals)} trade management signal(s) pending review. "
            f"Use 'approve <id>' / 'reject <id>' / 'list'"
        )

    def on_enter_execution(self, event):
        """Execution — agents disabled, go to monitoring."""
        logger.info("Execution skipped (agents disabled)")
        self.context['approved_actions'] = []
        self.monitor()

    def on_enter_eod_evaluation(self, event):
        """EOD evaluation — agents disabled, skip to reporting."""
        logger.info("=== EOD EVALUATION (agents disabled) ===")
        self.report()

    def on_enter_reporting(self, event):
        """Reporting — agents disabled, go idle."""
        logger.info("=== REPORTING (agents disabled) ===")
        self.go_idle()

    def on_enter_halted(self, event):
        """Trading halted — persist state."""
        reason = self.context.get('halt_reason', 'Unknown')
        logger.warning(f"=== HALTED: {reason} ===")
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

        All agents disabled — only sync broker positions and refresh containers.
        """
        logger.info("--- Monitoring cycle (agents disabled) ---")

        # Only run if in monitoring state
        current = self.state
        if current != WorkflowStates.MONITORING.value:
            logger.debug(f"Skip monitoring cycle: state is {current}")
            return

        # Infrastructure only: sync broker + refresh containers
        self._sync_broker_positions()
        self._refresh_containers()

    def run_once(self):
        """Run a single complete cycle for testing."""
        logger.info("=== RUNNING SINGLE CYCLE ===")
        self.boot()

        # In --once mode, auto-advance past human pause states
        # so monitoring cycle (incl. QuantResearchAgent) fires.
        if self.state == WorkflowStates.RECOMMENDATION_REVIEW.value:
            logger.info("Auto-advancing past recommendation_review for single cycle")
            self.execute()  # transitions to execution → monitoring

        if self.state == WorkflowStates.MONITORING.value:
            self.run_monitoring_cycle()

    # -----------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------

    def _persist_state(self):
        """Save current state and context to WorkflowStateORM."""
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.core.database.schema import WorkflowStateORM

            # Serialize context (skip non-serializable runtime objects)
            _SKIP_KEYS = {'container_manager'}  # runtime objects, not state
            ctx_copy = {}
            for k, v in self.context.items():
                if k in _SKIP_KEYS:
                    continue
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

                    # Restore context (skip runtime-only keys that may be stale)
                    if state_row.context_json:
                        restored_ctx = state_row.context_json
                        # Never restore runtime objects from DB — they're re-created at startup
                        restored_ctx.pop('container_manager', None)
                        self.context.update(restored_ctx)
                        logger.info(f"Restored context (cycle {self.context.get('cycle_count', 0)})")

        except Exception as e:
            logger.debug(f"Could not restore state (first run?): {e}")

    # -----------------------------------------------------------------
    # Container initialization & refresh
    # -----------------------------------------------------------------

    def _init_container_manager(self):
        """Create ContainerManager with bundles from risk_config.yaml."""
        try:
            from trading_cotrader.containers.container_manager import ContainerManager
            from trading_cotrader.config.risk_config_loader import get_risk_config

            cm = ContainerManager()
            risk_config = get_risk_config()
            cm.initialize_bundles(risk_config.portfolios)
            self.context['container_manager'] = cm
            logger.info("ContainerManager initialized with portfolio bundles")

            # Load research from DB (instant cold start)
            self._load_research_from_db()

            # Load existing data from DB
            self._refresh_containers()
        except Exception as e:
            logger.warning(f"ContainerManager init failed (non-blocking): {e}")

    def _refresh_containers(self):
        """Refresh ContainerManager from DB — populates positions, risk factors, trades."""
        cm = self.container_manager
        if cm is None:
            return
        try:
            from trading_cotrader.core.database.session import session_scope
            with session_scope() as session:
                cm.load_all_bundles(session)
            logger.info("Containers refreshed from DB")
        except Exception as e:
            logger.warning(f"Container refresh failed (non-blocking): {e}")

    def _sync_broker_positions(self):
        """
        Sync positions from all API-capable brokers into DB.

        Uses PortfolioSyncService for each broker adapter that has real
        connectivity (not Manual/ReadOnly). Skips gracefully when no
        broker is available (--no-broker mode).
        """
        from trading_cotrader.adapters.base import ManualBrokerAdapter, ReadOnlyAdapter

        adapters = self.broker_router.adapters if self.broker_router else {}
        if not adapters:
            logger.debug("No broker adapters — skipping position sync")
            return

        synced_any = False
        for broker_name, adapter in adapters.items():
            # Skip non-API adapters
            if isinstance(adapter, (ManualBrokerAdapter, ReadOnlyAdapter)):
                continue

            try:
                from trading_cotrader.core.database.session import session_scope
                from trading_cotrader.services.portfolio_sync import PortfolioSyncService

                with session_scope() as session:
                    sync_svc = PortfolioSyncService(session, adapter)
                    result = sync_svc.sync_portfolio()

                if result.success:
                    logger.info(
                        f"Broker sync [{broker_name}]: "
                        f"{result.positions_synced} positions synced"
                    )
                    synced_any = True
                else:
                    logger.warning(
                        f"Broker sync [{broker_name}] failed: {result.error}"
                    )
            except Exception as e:
                logger.warning(
                    f"Broker sync [{broker_name}] error (non-blocking): {e}"
                )

    # -----------------------------------------------------------------
    # Research container DB bridge
    # -----------------------------------------------------------------

    def _load_research_from_db(self):
        """Load research container from DB for instant cold start."""
        cm = self.container_manager
        if cm is None:
            return
        try:
            # Load watchlist config first
            from pathlib import Path
            import yaml
            config_path = Path(__file__).parent.parent / 'config' / 'market_watchlist.yaml'
            if config_path.exists():
                with open(config_path, 'r') as f:
                    cfg = yaml.safe_load(f)
                items = cfg.get('watchlist', [])
                cm.research.load_watchlist_config(items)

            from trading_cotrader.core.database.session import session_scope
            with session_scope() as session:
                count = cm.research.load_from_db(session)
            if count:
                logger.info(f"Research container loaded {count} entries from DB (cold start)")
        except Exception as e:
            logger.warning(f"Research DB load failed (non-blocking): {e}")

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _check_trading_day(self):
        """
        Inline calendar check (was CalendarAgent).

        Sets context keys: is_trading_day, cadences, fomc_today,
        minutes_since_open, minutes_to_close, market_open_time, market_close_time.
        """
        from datetime import date
        try:
            import exchange_calendars
            import pandas as pd
            import pytz

            today = date.today()
            cal = exchange_calendars.get_calendar('XNYS')
            tz = pytz.timezone(self.config.market_hours.timezone)
            now = datetime.now(tz)

            ts = pd.Timestamp(today)
            is_trading_day = cal.is_session(ts)

            if not is_trading_day:
                self.context['is_trading_day'] = False
                self.context['cadences'] = []
                logger.info(f"{today} is not a trading day")
                return

            session_open = cal.session_open(ts)
            session_close = cal.session_close(ts)
            open_et = session_open.astimezone(tz)
            close_et = session_close.astimezone(tz)

            if now < open_et:
                minutes_since_open = 0
                minutes_to_close = int((close_et - open_et).total_seconds() / 60)
            elif now > close_et:
                minutes_since_open = int((close_et - open_et).total_seconds() / 60)
                minutes_to_close = 0
            else:
                minutes_since_open = int((now - open_et).total_seconds() / 60)
                minutes_to_close = int((close_et - now).total_seconds() / 60)

            fomc_today = str(today) in self.config.schedule.fomc_dates

            # Determine cadences
            sched = self.config.schedule
            day_name = today.strftime('%A').lower()
            cadences = list(sched.daily)
            if day_name == 'wednesday':
                for c in sched.wednesday:
                    if c not in cadences:
                        cadences.append(c)
            elif day_name == 'friday':
                for c in sched.friday:
                    if c not in cadences:
                        cadences.append(c)
            if fomc_today and sched.skip_0dte_on_fomc:
                cadences = [c for c in cadences if c != '0dte']
            if sched.monthly_dte_window and len(sched.monthly_dte_window) == 2:
                if 'monthly' not in cadences:
                    cadences.append('monthly')

            self.context['is_trading_day'] = True
            self.context['cadences'] = cadences
            self.context['fomc_today'] = fomc_today
            self.context['minutes_since_open'] = minutes_since_open
            self.context['minutes_to_close'] = minutes_to_close
            self.context['market_open_time'] = open_et.strftime('%H:%M')
            self.context['market_close_time'] = close_et.strftime('%H:%M')

            logger.info(
                f"Trading day: cadences={cadences}, "
                f"FOMC={'YES' if fomc_today else 'no'}, "
                f"{minutes_to_close} min to close"
            )

        except Exception as e:
            logger.error(f"Calendar check failed: {e}")
            # Fail safe: assume trading day
            self.context['is_trading_day'] = True
            self.context['cadences'] = ['0dte']
            self.context['minutes_to_close'] = 999
            self.context['minutes_since_open'] = 999

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

    def _run_agent(self, agent, context: dict, method: str = 'run') -> 'AgentResult':
        """
        Run an agent method with timing, persist result to AgentRunORM.

        Returns the AgentResult. DB persistence is fire-and-forget —
        failures never block the workflow.
        """
        started_at = datetime.utcnow()
        try:
            fn = getattr(agent, method)
            result = fn(context)
        except Exception as e:
            from trading_cotrader.agents.protocol import AgentResult, AgentStatus as AS
            result = AgentResult(
                agent_name=getattr(agent, 'name', str(agent)),
                status=AS.ERROR,
                messages=[f"Agent crashed: {e}"],
            )

        finished_at = datetime.utcnow()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        # Log to console
        for msg in result.messages:
            level = logging.WARNING if result.status == AgentStatus.ERROR else logging.INFO
            logger.log(level, f"[{result.agent_name}] {msg}")

        # Persist to DB (fire-and-forget)
        try:
            from trading_cotrader.core.database.session import session_scope
            from trading_cotrader.core.database.schema import AgentRunORM

            with session_scope() as session:
                run = AgentRunORM(
                    id=str(uuid.uuid4()),
                    agent_name=result.agent_name,
                    cycle_id=self.context.get('cycle_count', 0),
                    workflow_state=self.state,
                    status=result.status.value if hasattr(result.status, 'value') else str(result.status),
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=duration_ms,
                    data_json=result.data or {},
                    messages=result.messages or [],
                    metrics_json=result.metrics or {},
                    objectives=result.objectives or [],
                    requires_human=result.requires_human,
                    human_prompt=result.human_prompt,
                    error_message=result.messages[0] if result.status == AgentStatus.ERROR and result.messages else None,
                )
                session.add(run)
        except Exception as e:
            logger.debug(f"Failed to persist agent run for {result.agent_name}: {e}")

        return result

    def _log_agent(self, result):
        """Log agent result (legacy — used for results already obtained)."""
        for msg in result.messages:
            level = logging.WARNING if result.status == AgentStatus.ERROR else logging.INFO
            logger.log(level, f"[{result.agent_name}] {msg}")
