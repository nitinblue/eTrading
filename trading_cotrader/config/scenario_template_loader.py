"""
Scenario Template Loader — Parses scenario_templates.yaml into typed dataclasses.

Each scenario template defines:
- Trigger conditions (market state that activates the scenario)
- Strategies to recommend when triggered
- Target underlyings and cadence
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging
import yaml

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).parent


@dataclass
class ScenarioTrigger:
    """Conditions that must be met to activate a scenario."""
    pct_from_52w_high: Optional[Tuple[float, float]] = None  # [min, max] range
    vix: Optional[Tuple[float, float]] = None
    vix_min: Optional[float] = None
    rsi_max: Optional[float] = None
    rsi_range: Optional[Tuple[float, float]] = None
    iv_rank_min: Optional[float] = None
    directional_regime: Optional[List[str]] = None
    volatility_regime: Optional[List[str]] = None
    days_to_earnings: Optional[Tuple[int, int]] = None
    pct_from_52w_high_max: Optional[float] = None
    bollinger_width_min: Optional[float] = None


@dataclass
class ScenarioStrategy:
    """A strategy to recommend when a scenario triggers."""
    strategy_type: str = ""
    option_type: Optional[str] = None
    direction: str = "sell"
    dte_target: int = 45
    short_delta: Optional[float] = None
    delta_target: Optional[float] = None
    wing_width_pct: Optional[float] = None
    near_dte_target: Optional[int] = None
    far_dte_target: Optional[int] = None
    put_delta: Optional[float] = None
    call_delta: Optional[float] = None
    confidence: int = 5
    risk_category: str = "defined"
    route_to_portfolios: List[str] = field(default_factory=list)


@dataclass
class ScenarioTemplate:
    """A complete scenario definition."""
    name: str = ""
    display_name: str = ""
    description: str = ""
    scenario_type: str = ""
    enabled: bool = True
    trigger: ScenarioTrigger = field(default_factory=ScenarioTrigger)
    strategies: List[ScenarioStrategy] = field(default_factory=list)
    underlyings: List[str] = field(default_factory=list)
    cadence: str = "opportunistic"
    rationale_template: str = ""
    auto_approve: bool = False


def _parse_trigger(raw: dict) -> ScenarioTrigger:
    """Parse trigger_conditions dict into ScenarioTrigger."""
    t = ScenarioTrigger()
    if 'pct_from_52w_high' in raw:
        v = raw['pct_from_52w_high']
        t.pct_from_52w_high = (float(v[0]), float(v[1]))
    if 'vix' in raw:
        v = raw['vix']
        t.vix = (float(v[0]), float(v[1]))
    if 'vix_min' in raw:
        t.vix_min = float(raw['vix_min'])
    if 'rsi_max' in raw:
        t.rsi_max = float(raw['rsi_max'])
    if 'rsi_range' in raw:
        v = raw['rsi_range']
        t.rsi_range = (float(v[0]), float(v[1]))
    if 'iv_rank_min' in raw:
        t.iv_rank_min = float(raw['iv_rank_min'])
    if 'directional_regime' in raw:
        t.directional_regime = list(raw['directional_regime'])
    if 'volatility_regime' in raw:
        t.volatility_regime = list(raw['volatility_regime'])
    if 'days_to_earnings' in raw:
        v = raw['days_to_earnings']
        t.days_to_earnings = (int(v[0]), int(v[1]))
    if 'pct_from_52w_high_max' in raw:
        t.pct_from_52w_high_max = float(raw['pct_from_52w_high_max'])
    if 'bollinger_width_min' in raw:
        t.bollinger_width_min = float(raw['bollinger_width_min'])
    return t


def _parse_strategy(raw: dict) -> ScenarioStrategy:
    """Parse a single strategy dict into ScenarioStrategy."""
    return ScenarioStrategy(
        strategy_type=raw.get('strategy_type', ''),
        option_type=raw.get('option_type'),
        direction=raw.get('direction', 'sell'),
        dte_target=raw.get('dte_target', 45),
        short_delta=raw.get('short_delta'),
        delta_target=raw.get('delta_target'),
        wing_width_pct=raw.get('wing_width_pct'),
        near_dte_target=raw.get('near_dte_target'),
        far_dte_target=raw.get('far_dte_target'),
        put_delta=raw.get('put_delta'),
        call_delta=raw.get('call_delta'),
        confidence=raw.get('confidence', 5),
        risk_category=raw.get('risk_category', 'defined'),
        route_to_portfolios=raw.get('route_to_portfolios', []),
    )


def load_scenario_templates(
    path: Optional[Path] = None,
) -> Dict[str, ScenarioTemplate]:
    """
    Load scenario templates from YAML.

    Args:
        path: Override path. Default: config/scenario_templates.yaml

    Returns:
        Dict of template_name → ScenarioTemplate.
    """
    if path is None:
        path = _CONFIG_DIR / 'scenario_templates.yaml'

    if not path.exists():
        logger.warning(f"Scenario templates not found at {path}")
        return {}

    with open(path, 'r') as f:
        raw = yaml.safe_load(f) or {}

    templates: Dict[str, ScenarioTemplate] = {}
    for name, data in raw.get('scenario_templates', {}).items():
        trigger = _parse_trigger(data.get('trigger_conditions', {}))
        strategies = [
            _parse_strategy(s)
            for s in data.get('strategies', [])
        ]
        template = ScenarioTemplate(
            name=name,
            display_name=data.get('display_name', name),
            description=data.get('description', ''),
            scenario_type=data.get('scenario_type', ''),
            enabled=data.get('enabled', True),
            trigger=trigger,
            strategies=strategies,
            underlyings=data.get('underlyings', []),
            cadence=data.get('cadence', 'opportunistic'),
            rationale_template=data.get('rationale_template', ''),
            auto_approve=data.get('auto_approve', False),
        )
        templates[name] = template

    logger.info(f"Loaded {len(templates)} scenario templates")
    return templates
