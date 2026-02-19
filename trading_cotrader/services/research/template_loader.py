"""
Research Template Loader — Reads and validates research_templates.yaml.

Provides:
  - ResearchTemplate dataclass (the full template)
  - TradeStrategyConfig dataclass (how to trade)
  - StrategyVariant dataclass (strategy within a template)
  - load_research_templates() -> Dict[str, ResearchTemplate]
  - get_enabled_templates() -> Dict[str, ResearchTemplate]
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from trading_cotrader.services.research.condition_evaluator import (
    Condition, parse_conditions,
)

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent.parent / 'config' / 'research_templates.yaml'


@dataclass
class StrategyVariant:
    """A single strategy within a trade_strategy block."""
    strategy_type: str = ""
    option_type: Optional[str] = None      # "put" or "call"
    direction: Optional[str] = None        # "buy" or "sell"
    dte_target: Optional[int] = None
    short_delta: Optional[float] = None
    delta_target: Optional[float] = None
    wing_width_pct: Optional[float] = None
    near_dte_target: Optional[int] = None
    far_dte_target: Optional[int] = None
    put_delta: Optional[float] = None
    call_delta: Optional[float] = None
    confidence: int = 5
    risk_category: str = "defined"

    @classmethod
    def from_dict(cls, d: Dict) -> 'StrategyVariant':
        return cls(
            strategy_type=d.get('strategy_type', ''),
            option_type=d.get('option_type'),
            direction=d.get('direction'),
            dte_target=d.get('dte_target'),
            short_delta=d.get('short_delta'),
            delta_target=d.get('delta_target'),
            wing_width_pct=d.get('wing_width_pct'),
            near_dte_target=d.get('near_dte_target'),
            far_dte_target=d.get('far_dte_target'),
            put_delta=d.get('put_delta'),
            call_delta=d.get('call_delta'),
            confidence=d.get('confidence', 5),
            risk_category=d.get('risk_category', 'defined'),
        )


@dataclass
class TradeStrategyConfig:
    """How to trade: equity or option, with strategy details."""
    instrument: str = "option"             # "equity" or "option"
    position_type: Optional[str] = None    # "long" or "short" (equity)
    trade_template: Optional[str] = None   # Ref to TradeTemplate JSON (option)
    strategies: List[StrategyVariant] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict) -> 'TradeStrategyConfig':
        strategies = [
            StrategyVariant.from_dict(s)
            for s in d.get('strategies', [])
        ]
        return cls(
            instrument=d.get('instrument', 'option'),
            position_type=d.get('position_type'),
            trade_template=d.get('trade_template'),
            strategies=strategies,
        )


@dataclass
class ParameterVariant:
    """A parameter variant for A/B testing."""
    variant_id: str = "base"
    overrides: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict) -> 'ParameterVariant':
        return cls(
            variant_id=d.get('variant_id', 'base'),
            overrides=d.get('overrides', {}),
        )


@dataclass
class ResearchTemplate:
    """
    A research hypothesis template: WHERE to look, WHEN to enter/exit, HOW to trade.
    """
    name: str = ""
    enabled: bool = True
    display_name: str = ""
    description: str = ""
    author: str = "system"

    # Universe
    universe: List[str] = field(default_factory=list)
    universe_from: Optional[str] = None    # "earnings_calendar", future: "watchlist:name"

    # Routing
    target_portfolio: str = ""
    cadence: str = "opportunistic"         # "opportunistic", "event_driven"
    auto_approve: bool = True

    # Strategy
    trade_strategy: TradeStrategyConfig = field(default_factory=TradeStrategyConfig)

    # Conditions
    entry_conditions: List[Condition] = field(default_factory=list)
    exit_conditions: List[Condition] = field(default_factory=list)

    # Variants
    variants: List[ParameterVariant] = field(default_factory=list)

    @classmethod
    def from_dict(cls, name: str, d: Dict) -> 'ResearchTemplate':
        trade_strategy = TradeStrategyConfig.from_dict(d.get('trade_strategy', {}))
        entry_conditions = parse_conditions(d.get('entry_conditions', []))
        exit_conditions = parse_conditions(d.get('exit_conditions', []))
        variants = [
            ParameterVariant.from_dict(v)
            for v in d.get('variants', [{'variant_id': 'base'}])
        ]

        return cls(
            name=name,
            enabled=d.get('enabled', True),
            display_name=d.get('display_name', name),
            description=d.get('description', ''),
            author=d.get('author', 'system'),
            universe=d.get('universe', []),
            universe_from=d.get('universe_from'),
            target_portfolio=d.get('target_portfolio', ''),
            cadence=d.get('cadence', 'opportunistic'),
            auto_approve=d.get('auto_approve', True),
            trade_strategy=trade_strategy,
            entry_conditions=entry_conditions,
            exit_conditions=exit_conditions,
            variants=variants,
        )


def load_research_templates(
    config_path: Optional[Path] = None,
) -> Dict[str, ResearchTemplate]:
    """
    Load all research templates from YAML config.

    Returns:
        Dict mapping template name to ResearchTemplate.
    """
    path = config_path or _CONFIG_PATH

    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning(f"Research templates config not found: {path}")
        return {}
    except Exception as e:
        logger.error(f"Failed to load research templates: {e}")
        return {}

    templates_raw = raw.get('research_templates', {})
    if not templates_raw:
        logger.warning("No research_templates found in config")
        return {}

    templates = {}
    for name, data in templates_raw.items():
        try:
            template = ResearchTemplate.from_dict(name, data)
            templates[name] = template
            logger.debug(f"Loaded research template: {name} (enabled={template.enabled})")
        except Exception as e:
            logger.error(f"Failed to parse research template '{name}': {e}")

    logger.info(f"Loaded {len(templates)} research templates ({sum(1 for t in templates.values() if t.enabled)} enabled)")
    return templates


def get_enabled_templates(
    config_path: Optional[Path] = None,
) -> Dict[str, ResearchTemplate]:
    """Load only enabled research templates."""
    all_templates = load_research_templates(config_path)
    return {
        name: t for name, t in all_templates.items() if t.enabled
    }
