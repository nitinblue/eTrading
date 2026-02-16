"""
Workflow Configuration Loader — Loads workflow_rules.yaml into typed dataclasses.

Follows the same pattern as risk_config_loader.py.

Usage:
    from trading_cotrader.config.workflow_config_loader import load_workflow_config
    config = load_workflow_config()
    print(config.circuit_breakers.daily_loss_pct)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path
import yaml
import logging

logger = logging.getLogger(__name__)


@dataclass
class MarketHoursConfig:
    """Market hours configuration."""
    open: str = "09:30"
    close: str = "16:00"
    timezone: str = "US/Eastern"


@dataclass
class EmailConfig:
    """Email notification configuration."""
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    from_address: str = ""
    to_addresses: List[str] = field(default_factory=list)
    # Backward compat: single address also supported
    to_address: str = ""
    daily_summary_time: str = "16:15"
    weekly_digest_day: str = "friday"

    def get_recipients(self) -> List[str]:
        """Get all recipient addresses."""
        recipients = list(self.to_addresses)
        if self.to_address and self.to_address not in recipients:
            recipients.append(self.to_address)
        return recipients


@dataclass
class NotificationsConfig:
    """Notifications configuration."""
    email: EmailConfig = field(default_factory=EmailConfig)


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker thresholds."""
    daily_loss_pct: float = 3.0
    weekly_loss_pct: float = 5.0
    vix_halt_threshold: float = 35.0
    consecutive_loss_pause: int = 3
    consecutive_loss_halt: int = 5
    max_portfolio_drawdown: Dict[str, float] = field(default_factory=lambda: {
        "core_income": 15.0, "medium_risk": 20.0,
        "high_risk": 30.0, "model_portfolio": 25.0,
    })


@dataclass
class TradingConstraintsConfig:
    """Trading constraint rules."""
    max_trades_per_day: int = 3
    max_trades_per_week_per_portfolio: int = 5
    no_entry_first_minutes: int = 15
    no_entry_last_minutes: int = 30
    require_approval_undefined_risk: bool = True
    no_adding_to_losers_without_rationale: bool = True


@dataclass
class TradingScheduleConfig:
    """Which cadences run on which days."""
    daily: List[str] = field(default_factory=lambda: ["0dte"])
    wednesday: List[str] = field(default_factory=lambda: ["0dte", "weekly"])
    friday: List[str] = field(default_factory=lambda: ["0dte", "weekly"])
    monthly_dte_window: List[int] = field(default_factory=lambda: [35, 55])
    skip_0dte_on_fomc: bool = True
    fomc_dates: List[str] = field(default_factory=list)


@dataclass
class DecisionTimeoutsConfig:
    """Timeouts for user decisions."""
    reminder_minutes: int = 60
    nag_minutes: int = 240
    log_missed_at_eod: bool = True


@dataclass
class StaggeredDeploymentConfig:
    """Ramp-up schedule so capital isn't deployed all at once."""
    ramp_weeks: int = 8
    max_deploy_per_week_pct: Dict[str, float] = field(default_factory=lambda: {
        "core_income": 15.0, "medium_risk": 25.0,
        "high_risk": 30.0, "model_portfolio": 50.0,
    })


@dataclass
class CapitalDeploymentConfig:
    """Idle capital alert thresholds per portfolio."""
    idle_alert_pct: Dict[str, float] = field(default_factory=lambda: {
        "core_income": 15.0, "medium_risk": 10.0,
        "high_risk": 5.0, "model_portfolio": 10.0,
    })
    escalation: Dict[str, int] = field(default_factory=lambda: {
        "warning_days_idle": 5,
        "critical_days_idle": 10,
        "nag_frequency_hours": 4,
    })
    target_annual_return_pct: Dict[str, float] = field(default_factory=lambda: {
        "core_income": 12.5, "medium_risk": 20.0,
        "high_risk": 75.0, "model_portfolio": 0.0,
    })
    staggered: StaggeredDeploymentConfig = field(default_factory=StaggeredDeploymentConfig)


@dataclass
class WorkflowConfig:
    """Complete workflow configuration."""
    cycle_frequency_minutes: int = 30
    market_hours: MarketHoursConfig = field(default_factory=MarketHoursConfig)
    boot_time_minutes_before_open: int = 5
    eod_eval_time: str = "15:30"
    report_time: str = "16:15"
    circuit_breakers: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    constraints: TradingConstraintsConfig = field(default_factory=TradingConstraintsConfig)
    schedule: TradingScheduleConfig = field(default_factory=TradingScheduleConfig)
    decision_timeouts: DecisionTimeoutsConfig = field(default_factory=DecisionTimeoutsConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    capital_deployment: CapitalDeploymentConfig = field(default_factory=CapitalDeploymentConfig)


# Default search paths for the config file
_DEFAULT_PATHS = [
    Path('config/workflow_rules.yaml'),
    Path(__file__).parent / 'workflow_rules.yaml',
    Path(__file__).parent.parent / 'config' / 'workflow_rules.yaml',
]


def load_workflow_config(config_path: str = None) -> WorkflowConfig:
    """
    Load workflow configuration from YAML.

    Args:
        config_path: Explicit path. If None, searches default locations.

    Returns:
        WorkflowConfig with all rules loaded.
    """
    if config_path:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow config not found: {config_path}")
    else:
        path = _find_config_file()

    logger.info(f"Loading workflow config from: {path}")
    with open(path, 'r') as f:
        raw = yaml.safe_load(f)

    return _parse_config(raw)


def _find_config_file() -> Path:
    """Find config file in default locations."""
    for p in _DEFAULT_PATHS:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"Workflow config not found. Tried: {[str(p) for p in _DEFAULT_PATHS]}"
    )


def _parse_config(raw: dict) -> WorkflowConfig:
    """Parse raw YAML dict into typed WorkflowConfig."""
    wf = raw.get('workflow', {})
    config = WorkflowConfig(
        cycle_frequency_minutes=wf.get('cycle_frequency_minutes', 30),
        boot_time_minutes_before_open=wf.get('boot_time_minutes_before_open', 5),
        eod_eval_time=wf.get('eod_eval_time', '15:30'),
        report_time=wf.get('report_time', '16:15'),
    )

    # Market hours
    mh = wf.get('market_hours', {})
    if mh:
        config.market_hours = MarketHoursConfig(
            open=mh.get('open', '09:30'),
            close=mh.get('close', '16:00'),
            timezone=mh.get('timezone', 'US/Eastern'),
        )

    # Circuit breakers
    cb = raw.get('circuit_breakers', {})
    if cb:
        config.circuit_breakers = CircuitBreakerConfig(
            daily_loss_pct=cb.get('daily_loss_pct', 3.0),
            weekly_loss_pct=cb.get('weekly_loss_pct', 5.0),
            vix_halt_threshold=cb.get('vix_halt_threshold', 35.0),
            consecutive_loss_pause=cb.get('consecutive_loss_pause', 3),
            consecutive_loss_halt=cb.get('consecutive_loss_halt', 5),
            max_portfolio_drawdown=cb.get('max_portfolio_drawdown', {}),
        )

    # Trading constraints
    tc = raw.get('trading_constraints', {})
    if tc:
        config.constraints = TradingConstraintsConfig(
            max_trades_per_day=tc.get('max_trades_per_day', 3),
            max_trades_per_week_per_portfolio=tc.get('max_trades_per_week_per_portfolio', 5),
            no_entry_first_minutes=tc.get('no_entry_first_minutes', 15),
            no_entry_last_minutes=tc.get('no_entry_last_minutes', 30),
            require_approval_undefined_risk=tc.get('require_approval_undefined_risk', True),
            no_adding_to_losers_without_rationale=tc.get('no_adding_to_losers_without_rationale', True),
        )

    # Trading schedule
    ts = raw.get('trading_schedule', {})
    if ts:
        config.schedule = TradingScheduleConfig(
            daily=ts.get('daily', ['0dte']),
            wednesday=ts.get('wednesday', ['0dte', 'weekly']),
            friday=ts.get('friday', ['0dte', 'weekly']),
            monthly_dte_window=ts.get('monthly_dte_window', [35, 55]),
            skip_0dte_on_fomc=ts.get('skip_0dte_on_fomc', True),
            fomc_dates=ts.get('fomc_dates', []),
        )

    # Decision timeouts
    dt = raw.get('decision_timeouts', {})
    if dt:
        config.decision_timeouts = DecisionTimeoutsConfig(
            reminder_minutes=dt.get('reminder_minutes', 60),
            nag_minutes=dt.get('nag_minutes', 240),
            log_missed_at_eod=dt.get('log_missed_at_eod', True),
        )

    # Notifications
    notif = raw.get('notifications', {})
    if notif:
        email_data = notif.get('email', {})
        config.notifications = NotificationsConfig(
            email=EmailConfig(**email_data) if email_data else EmailConfig(),
        )

    # Capital deployment
    cd = raw.get('capital_deployment', {})
    if cd:
        stag = cd.get('staggered_deployment', {})
        staggered_cfg = StaggeredDeploymentConfig(
            ramp_weeks=stag.get('ramp_weeks', 8),
            max_deploy_per_week_pct=stag.get('max_deploy_per_week_pct', {}),
        ) if stag else StaggeredDeploymentConfig()

        config.capital_deployment = CapitalDeploymentConfig(
            idle_alert_pct=cd.get('idle_alert_pct', {}),
            escalation=cd.get('escalation', {}),
            target_annual_return_pct=cd.get('target_annual_return_pct', {}),
            staggered=staggered_cfg,
        )

    logger.info("Workflow configuration loaded")
    return config
