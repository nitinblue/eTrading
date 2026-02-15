"""
Strategy Templates - Authoritative source for all strategy definitions.

Every strategy type has one canonical template that defines:
- Risk classification (defined/undefined/mixed)
- Directional bias
- Leg structure
- Max profit/loss formulas
- Default exit rules
- Greeks profile (theta/vega sign)
- Margin type

This replaces all hardcoded strategy maps and risk classification logic
scattered across the codebase.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Dict, Optional, Tuple

from trading_cotrader.core.models.domain import (
    OptionType,
    RiskCategory,
    StrategyType,
)


# ============================================================================
# Enums
# ============================================================================

class DirectionalBias(Enum):
    """Expected directional exposure of the strategy."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    VARIABLE = "variable"   # Depends on strikes chosen


# ============================================================================
# Template dataclasses
# ============================================================================

@dataclass(frozen=True)
class LegTemplate:
    """Canonical leg in a strategy template."""
    option_type: Optional[OptionType]   # None for equity leg
    side: str                           # "buy" or "sell"
    strike_position: str                # "atm", "otm_low", "otm_high", "itm", etc.
    quantity_multiplier: int            # 1 = same as base qty, -1 = opposite


@dataclass(frozen=True)
class StrategyTemplate:
    """Everything the system needs to know about a strategy type."""
    strategy_type: StrategyType
    name: str
    description: str

    # Risk classification
    risk_category: RiskCategory

    # Directional bias
    directional_bias: DirectionalBias

    # Leg structure
    leg_count: int
    leg_definitions: Tuple[LegTemplate, ...]

    # Max profit/loss formula keys (resolved by calculate functions)
    max_profit_formula: str
    max_loss_formula: str

    # Default exit rules
    default_profit_target_pct: Decimal
    default_stop_loss_pct: Decimal
    default_dte_exit: int

    # Greeks profile
    typical_delta_sign: int     # -1, 0, +1
    is_theta_positive: bool
    is_vega_negative: bool

    # Margin
    margin_type: str            # "max_loss", "naked_put", "naked_call", "portfolio_margin"


# ============================================================================
# Exhaustive strategy catalog
# ============================================================================

_TEMPLATES: Dict[StrategyType, StrategyTemplate] = {}


def _register(t: StrategyTemplate) -> None:
    _TEMPLATES[t.strategy_type] = t


# ---------------------------------------------------------------------------
# SINGLE (long option)
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.SINGLE,
    name="Single Option",
    description="Single long or short option; risk depends on direction",
    risk_category=RiskCategory.UNDEFINED,       # short naked is undefined
    directional_bias=DirectionalBias.VARIABLE,
    leg_count=1,
    leg_definitions=(
        LegTemplate(option_type=None, side="variable", strike_position="variable", quantity_multiplier=1),
    ),
    max_profit_formula="unlimited_or_premium",
    max_loss_formula="unlimited_or_premium",
    default_profit_target_pct=Decimal('50'),
    default_stop_loss_pct=Decimal('200'),
    default_dte_exit=7,
    typical_delta_sign=0,       # depends on call/put and buy/sell
    is_theta_positive=False,    # depends on direction
    is_vega_negative=False,
    margin_type="naked_put",
))

# ---------------------------------------------------------------------------
# VERTICAL SPREAD
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.VERTICAL_SPREAD,
    name="Vertical Spread",
    description="Two options same expiration, different strikes; defined risk",
    risk_category=RiskCategory.DEFINED,
    directional_bias=DirectionalBias.VARIABLE,  # bull put, bear call, etc.
    leg_count=2,
    leg_definitions=(
        LegTemplate(option_type=None, side="sell", strike_position="closer_to_atm", quantity_multiplier=1),
        LegTemplate(option_type=None, side="buy", strike_position="further_from_atm", quantity_multiplier=1),
    ),
    max_profit_formula="credit",
    max_loss_formula="width_minus_credit",
    default_profit_target_pct=Decimal('50'),
    default_stop_loss_pct=Decimal('200'),
    default_dte_exit=7,
    typical_delta_sign=0,
    is_theta_positive=True,
    is_vega_negative=True,
    margin_type="max_loss",
))

# ---------------------------------------------------------------------------
# IRON CONDOR
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.IRON_CONDOR,
    name="Iron Condor",
    description="Short strangle + long wings; neutral, defined risk",
    risk_category=RiskCategory.DEFINED,
    directional_bias=DirectionalBias.NEUTRAL,
    leg_count=4,
    leg_definitions=(
        LegTemplate(option_type=OptionType.PUT, side="buy", strike_position="otm_low", quantity_multiplier=1),
        LegTemplate(option_type=OptionType.PUT, side="sell", strike_position="otm_mid_low", quantity_multiplier=1),
        LegTemplate(option_type=OptionType.CALL, side="sell", strike_position="otm_mid_high", quantity_multiplier=1),
        LegTemplate(option_type=OptionType.CALL, side="buy", strike_position="otm_high", quantity_multiplier=1),
    ),
    max_profit_formula="credit",
    max_loss_formula="widest_wing_minus_credit",
    default_profit_target_pct=Decimal('50'),
    default_stop_loss_pct=Decimal('200'),
    default_dte_exit=21,
    typical_delta_sign=0,
    is_theta_positive=True,
    is_vega_negative=True,
    margin_type="max_loss",
))

# ---------------------------------------------------------------------------
# IRON BUTTERFLY
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.IRON_BUTTERFLY,
    name="Iron Butterfly",
    description="Short straddle + long wings; neutral, defined risk, high credit",
    risk_category=RiskCategory.DEFINED,
    directional_bias=DirectionalBias.NEUTRAL,
    leg_count=4,
    leg_definitions=(
        LegTemplate(option_type=OptionType.PUT, side="buy", strike_position="otm_low", quantity_multiplier=1),
        LegTemplate(option_type=OptionType.PUT, side="sell", strike_position="atm", quantity_multiplier=1),
        LegTemplate(option_type=OptionType.CALL, side="sell", strike_position="atm", quantity_multiplier=1),
        LegTemplate(option_type=OptionType.CALL, side="buy", strike_position="otm_high", quantity_multiplier=1),
    ),
    max_profit_formula="credit",
    max_loss_formula="wing_width_minus_credit",
    default_profit_target_pct=Decimal('25'),
    default_stop_loss_pct=Decimal('200'),
    default_dte_exit=21,
    typical_delta_sign=0,
    is_theta_positive=True,
    is_vega_negative=True,
    margin_type="max_loss",
))

# ---------------------------------------------------------------------------
# STRADDLE
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.STRADDLE,
    name="Straddle",
    description="ATM call + ATM put; same strike, same expiration",
    risk_category=RiskCategory.UNDEFINED,       # short straddle is undefined
    directional_bias=DirectionalBias.NEUTRAL,
    leg_count=2,
    leg_definitions=(
        LegTemplate(option_type=OptionType.PUT, side="variable", strike_position="atm", quantity_multiplier=1),
        LegTemplate(option_type=OptionType.CALL, side="variable", strike_position="atm", quantity_multiplier=1),
    ),
    max_profit_formula="unlimited_or_credit",
    max_loss_formula="unlimited_or_debit",
    default_profit_target_pct=Decimal('25'),
    default_stop_loss_pct=Decimal('200'),
    default_dte_exit=21,
    typical_delta_sign=0,
    is_theta_positive=True,     # short straddle default
    is_vega_negative=True,
    margin_type="naked_put",
))

# ---------------------------------------------------------------------------
# STRANGLE
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.STRANGLE,
    name="Strangle",
    description="OTM call + OTM put; different strikes, same expiration",
    risk_category=RiskCategory.UNDEFINED,       # short strangle is undefined
    directional_bias=DirectionalBias.NEUTRAL,
    leg_count=2,
    leg_definitions=(
        LegTemplate(option_type=OptionType.PUT, side="variable", strike_position="otm_low", quantity_multiplier=1),
        LegTemplate(option_type=OptionType.CALL, side="variable", strike_position="otm_high", quantity_multiplier=1),
    ),
    max_profit_formula="unlimited_or_credit",
    max_loss_formula="unlimited_or_debit",
    default_profit_target_pct=Decimal('50'),
    default_stop_loss_pct=Decimal('200'),
    default_dte_exit=21,
    typical_delta_sign=0,
    is_theta_positive=True,     # short strangle default
    is_vega_negative=True,
    margin_type="naked_put",
))

# ---------------------------------------------------------------------------
# CALENDAR SPREAD
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.CALENDAR_SPREAD,
    name="Calendar Spread",
    description="Same strike, different expirations; debit spread, benefits from time and IV",
    risk_category=RiskCategory.DEFINED,
    directional_bias=DirectionalBias.NEUTRAL,
    leg_count=2,
    leg_definitions=(
        LegTemplate(option_type=None, side="sell", strike_position="atm", quantity_multiplier=1),
        LegTemplate(option_type=None, side="buy", strike_position="atm", quantity_multiplier=1),
    ),
    max_profit_formula="varies_iv_dependent",
    max_loss_formula="debit_paid",
    default_profit_target_pct=Decimal('50'),
    default_stop_loss_pct=Decimal('100'),
    default_dte_exit=7,
    typical_delta_sign=0,
    is_theta_positive=True,
    is_vega_negative=False,     # long vega (benefits from rising IV)
    margin_type="max_loss",
))

# ---------------------------------------------------------------------------
# CALENDAR DOUBLE SPREAD
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.CALENDAR_DOUBLE_SPREAD,
    name="Calendar Double Spread",
    description="Two calendar spreads at different strikes; neutral, defined risk",
    risk_category=RiskCategory.DEFINED,
    directional_bias=DirectionalBias.NEUTRAL,
    leg_count=4,
    leg_definitions=(
        LegTemplate(option_type=OptionType.PUT, side="sell", strike_position="otm_low", quantity_multiplier=1),
        LegTemplate(option_type=OptionType.PUT, side="buy", strike_position="otm_low", quantity_multiplier=1),
        LegTemplate(option_type=OptionType.CALL, side="sell", strike_position="otm_high", quantity_multiplier=1),
        LegTemplate(option_type=OptionType.CALL, side="buy", strike_position="otm_high", quantity_multiplier=1),
    ),
    max_profit_formula="varies_iv_dependent",
    max_loss_formula="debit_paid",
    default_profit_target_pct=Decimal('50'),
    default_stop_loss_pct=Decimal('100'),
    default_dte_exit=7,
    typical_delta_sign=0,
    is_theta_positive=True,
    is_vega_negative=False,
    margin_type="max_loss",
))

# ---------------------------------------------------------------------------
# DIAGONAL SPREAD
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.DIAGONAL_SPREAD,
    name="Diagonal Spread",
    description="Different strikes and expirations; directional calendar",
    risk_category=RiskCategory.DEFINED,
    directional_bias=DirectionalBias.VARIABLE,
    leg_count=2,
    leg_definitions=(
        LegTemplate(option_type=None, side="sell", strike_position="otm_near", quantity_multiplier=1),
        LegTemplate(option_type=None, side="buy", strike_position="itm_far", quantity_multiplier=1),
    ),
    max_profit_formula="varies",
    max_loss_formula="debit_plus_width_risk",
    default_profit_target_pct=Decimal('50'),
    default_stop_loss_pct=Decimal('100'),
    default_dte_exit=7,
    typical_delta_sign=0,
    is_theta_positive=True,
    is_vega_negative=False,
    margin_type="max_loss",
))

# ---------------------------------------------------------------------------
# BUTTERFLY
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.BUTTERFLY,
    name="Butterfly",
    description="Three strikes: buy 1 low, sell 2 middle, buy 1 high; defined risk",
    risk_category=RiskCategory.DEFINED,
    directional_bias=DirectionalBias.NEUTRAL,
    leg_count=3,
    leg_definitions=(
        LegTemplate(option_type=None, side="buy", strike_position="otm_low", quantity_multiplier=1),
        LegTemplate(option_type=None, side="sell", strike_position="atm", quantity_multiplier=2),
        LegTemplate(option_type=None, side="buy", strike_position="otm_high", quantity_multiplier=1),
    ),
    max_profit_formula="wing_width_minus_debit",
    max_loss_formula="debit_paid",
    default_profit_target_pct=Decimal('50'),
    default_stop_loss_pct=Decimal('100'),
    default_dte_exit=7,
    typical_delta_sign=0,
    is_theta_positive=True,
    is_vega_negative=True,
    margin_type="max_loss",
))

# ---------------------------------------------------------------------------
# CONDOR (all same type — calls or puts)
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.CONDOR,
    name="Condor",
    description="Four strikes: buy low, sell two middle, buy high; defined risk",
    risk_category=RiskCategory.DEFINED,
    directional_bias=DirectionalBias.NEUTRAL,
    leg_count=4,
    leg_definitions=(
        LegTemplate(option_type=None, side="buy", strike_position="otm_low", quantity_multiplier=1),
        LegTemplate(option_type=None, side="sell", strike_position="otm_mid_low", quantity_multiplier=1),
        LegTemplate(option_type=None, side="sell", strike_position="otm_mid_high", quantity_multiplier=1),
        LegTemplate(option_type=None, side="buy", strike_position="otm_high", quantity_multiplier=1),
    ),
    max_profit_formula="wing_minus_debit",
    max_loss_formula="debit_paid",
    default_profit_target_pct=Decimal('50'),
    default_stop_loss_pct=Decimal('100'),
    default_dte_exit=7,
    typical_delta_sign=0,
    is_theta_positive=True,
    is_vega_negative=True,
    margin_type="max_loss",
))

# ---------------------------------------------------------------------------
# COVERED CALL
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.COVERED_CALL,
    name="Covered Call",
    description="Long stock + short OTM call; income on existing position",
    risk_category=RiskCategory.DEFINED,
    directional_bias=DirectionalBias.BULLISH,
    leg_count=2,
    leg_definitions=(
        LegTemplate(option_type=None, side="buy", strike_position="equity", quantity_multiplier=100),
        LegTemplate(option_type=OptionType.CALL, side="sell", strike_position="otm_high", quantity_multiplier=1),
    ),
    max_profit_formula="premium_plus_stock_gain",
    max_loss_formula="stock_cost_minus_premium",
    default_profit_target_pct=Decimal('75'),
    default_stop_loss_pct=Decimal('100'),
    default_dte_exit=7,
    typical_delta_sign=1,
    is_theta_positive=True,
    is_vega_negative=True,
    margin_type="max_loss",
))

# ---------------------------------------------------------------------------
# PROTECTIVE PUT
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.PROTECTIVE_PUT,
    name="Protective Put",
    description="Long stock + long OTM put; insurance on existing position",
    risk_category=RiskCategory.DEFINED,
    directional_bias=DirectionalBias.BULLISH,
    leg_count=2,
    leg_definitions=(
        LegTemplate(option_type=None, side="buy", strike_position="equity", quantity_multiplier=100),
        LegTemplate(option_type=OptionType.PUT, side="buy", strike_position="otm_low", quantity_multiplier=1),
    ),
    max_profit_formula="unlimited_above_cost_plus_debit",
    max_loss_formula="stock_cost_minus_strike_plus_debit",
    default_profit_target_pct=Decimal('100'),
    default_stop_loss_pct=Decimal('100'),
    default_dte_exit=7,
    typical_delta_sign=1,
    is_theta_positive=False,
    is_vega_negative=False,
    margin_type="max_loss",
))

# ---------------------------------------------------------------------------
# JADE LIZARD
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.JADE_LIZARD,
    name="Jade Lizard",
    description="Short put + short call spread; no upside risk if credit > call spread width",
    risk_category=RiskCategory.MIXED,
    directional_bias=DirectionalBias.BULLISH,
    leg_count=3,
    leg_definitions=(
        LegTemplate(option_type=OptionType.PUT, side="sell", strike_position="otm_low", quantity_multiplier=1),
        LegTemplate(option_type=OptionType.CALL, side="sell", strike_position="otm_mid_high", quantity_multiplier=1),
        LegTemplate(option_type=OptionType.CALL, side="buy", strike_position="otm_high", quantity_multiplier=1),
    ),
    max_profit_formula="credit",
    max_loss_formula="put_strike_times_multiplier",
    default_profit_target_pct=Decimal('50'),
    default_stop_loss_pct=Decimal('200'),
    default_dte_exit=21,
    typical_delta_sign=1,
    is_theta_positive=True,
    is_vega_negative=True,
    margin_type="naked_put",
))

# ---------------------------------------------------------------------------
# BIG LIZARD
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.BIG_LIZARD,
    name="Big Lizard",
    description="Short straddle + long OTM call; unlimited upside risk",
    risk_category=RiskCategory.UNDEFINED,
    directional_bias=DirectionalBias.NEUTRAL,
    leg_count=3,
    leg_definitions=(
        LegTemplate(option_type=OptionType.PUT, side="sell", strike_position="atm", quantity_multiplier=1),
        LegTemplate(option_type=OptionType.CALL, side="sell", strike_position="atm", quantity_multiplier=1),
        LegTemplate(option_type=OptionType.CALL, side="buy", strike_position="otm_high", quantity_multiplier=1),
    ),
    max_profit_formula="credit",
    max_loss_formula="unlimited_upside",
    default_profit_target_pct=Decimal('25'),
    default_stop_loss_pct=Decimal('200'),
    default_dte_exit=21,
    typical_delta_sign=0,
    is_theta_positive=True,
    is_vega_negative=True,
    margin_type="naked_put",
))

# ---------------------------------------------------------------------------
# RATIO SPREAD
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.RATIO_SPREAD,
    name="Ratio Spread",
    description="Unequal number of long and short options; naked leg creates unlimited risk",
    risk_category=RiskCategory.UNDEFINED,
    directional_bias=DirectionalBias.VARIABLE,
    leg_count=3,
    leg_definitions=(
        LegTemplate(option_type=None, side="buy", strike_position="closer_to_atm", quantity_multiplier=1),
        LegTemplate(option_type=None, side="sell", strike_position="further_from_atm", quantity_multiplier=2),
    ),
    max_profit_formula="varies",
    max_loss_formula="unlimited_on_naked_leg",
    default_profit_target_pct=Decimal('50'),
    default_stop_loss_pct=Decimal('200'),
    default_dte_exit=21,
    typical_delta_sign=0,
    is_theta_positive=True,
    is_vega_negative=True,
    margin_type="naked_call",
))

# ---------------------------------------------------------------------------
# COLLAR
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.COLLOR,      # matches enum spelling
    name="Collar",
    description="Long stock + long put + short call; capped upside and downside",
    risk_category=RiskCategory.DEFINED,
    directional_bias=DirectionalBias.NEUTRAL,
    leg_count=3,
    leg_definitions=(
        LegTemplate(option_type=None, side="buy", strike_position="equity", quantity_multiplier=100),
        LegTemplate(option_type=OptionType.PUT, side="buy", strike_position="otm_low", quantity_multiplier=1),
        LegTemplate(option_type=OptionType.CALL, side="sell", strike_position="otm_high", quantity_multiplier=1),
    ),
    max_profit_formula="call_strike_minus_stock_cost",
    max_loss_formula="stock_cost_minus_put_strike",
    default_profit_target_pct=Decimal('100'),
    default_stop_loss_pct=Decimal('100'),
    default_dte_exit=7,
    typical_delta_sign=1,
    is_theta_positive=False,    # roughly theta-neutral
    is_vega_negative=False,     # roughly vega-neutral
    margin_type="max_loss",
))

# ---------------------------------------------------------------------------
# CUSTOM
# ---------------------------------------------------------------------------
_register(StrategyTemplate(
    strategy_type=StrategyType.CUSTOM,
    name="Custom",
    description="User-defined strategy; risk profile determined at trade time",
    risk_category=RiskCategory.UNDEFINED,       # assume worst case
    directional_bias=DirectionalBias.VARIABLE,
    leg_count=0,
    leg_definitions=(),
    max_profit_formula="varies",
    max_loss_formula="varies",
    default_profit_target_pct=Decimal('50'),
    default_stop_loss_pct=Decimal('200'),
    default_dte_exit=21,
    typical_delta_sign=0,
    is_theta_positive=False,
    is_vega_negative=False,
    margin_type="portfolio_margin",
))


# ============================================================================
# Lookup functions
# ============================================================================

def get_template(strategy_type: StrategyType) -> StrategyTemplate:
    """Get the template for a strategy type. Raises KeyError if not found."""
    return _TEMPLATES[strategy_type]


def get_all_templates() -> Dict[StrategyType, StrategyTemplate]:
    """Return all registered strategy templates."""
    return dict(_TEMPLATES)


def is_defined_risk(strategy_type: StrategyType) -> bool:
    """Check if a strategy type is defined-risk."""
    template = _TEMPLATES.get(strategy_type)
    if template is None:
        return False
    return template.risk_category == RiskCategory.DEFINED


def get_strategy_type_from_string(name: str) -> StrategyType:
    """
    Map a strategy name string to StrategyType enum.

    Replaces all _STRATEGY_MAP dicts across the codebase.
    Handles case-insensitive lookup, spaces, hyphens, etc.
    Falls back to CUSTOM if not matched.
    """
    if not name:
        return StrategyType.CUSTOM

    normalized = name.strip().lower().replace('-', '_').replace(' ', '_')

    # Direct enum value match
    for st in StrategyType:
        if st.value == normalized:
            return st

    # Common aliases
    _ALIASES: Dict[str, StrategyType] = {
        'collar': StrategyType.COLLOR,          # handle correct spelling
        'credit_spread': StrategyType.VERTICAL_SPREAD,
        'debit_spread': StrategyType.VERTICAL_SPREAD,
        'put_spread': StrategyType.VERTICAL_SPREAD,
        'call_spread': StrategyType.VERTICAL_SPREAD,
        'bull_put': StrategyType.VERTICAL_SPREAD,
        'bear_call': StrategyType.VERTICAL_SPREAD,
        'bull_call': StrategyType.VERTICAL_SPREAD,
        'bear_put': StrategyType.VERTICAL_SPREAD,
        'double_calendar': StrategyType.CALENDAR_DOUBLE_SPREAD,
        'poor_mans_covered_call': StrategyType.DIAGONAL_SPREAD,
        'pmcc': StrategyType.DIAGONAL_SPREAD,
    }

    return _ALIASES.get(normalized, StrategyType.CUSTOM)


# ============================================================================
# Max profit / loss calculation
# ============================================================================

def calculate_max_profit(
    strategy_type: StrategyType,
    net_credit_debit: Decimal,
    width: Decimal = Decimal('0'),
    multiplier: int = 100,
    strike: Optional[Decimal] = None,
) -> Optional[Decimal]:
    """
    Calculate max profit for a strategy.

    Args:
        net_credit_debit: Positive = credit received, negative = debit paid
        width: Distance between strikes (for spreads)
        multiplier: Contract multiplier (100 for equity options)
        strike: Relevant strike price (for naked/covered strategies)

    Returns:
        Max profit in dollars, or None if unlimited.
    """
    template = _TEMPLATES.get(strategy_type)
    if template is None:
        return None

    formula = template.max_profit_formula
    m = Decimal(str(multiplier))

    if formula == "credit":
        return abs(net_credit_debit) * m if net_credit_debit > 0 else Decimal('0')

    if formula == "width_minus_debit":
        return (width - abs(net_credit_debit)) * m

    if formula == "wing_width_minus_debit":
        return (width - abs(net_credit_debit)) * m

    if formula == "wing_minus_debit":
        return (width - abs(net_credit_debit)) * m

    if formula == "debit_paid":
        return abs(net_credit_debit) * m

    if formula in ("unlimited_or_premium", "unlimited_or_credit",
                    "unlimited_above_cost_plus_debit"):
        return None     # unlimited profit potential

    if formula == "premium_plus_stock_gain":
        # Covered call: premium + (strike - stock_cost)
        if strike is not None:
            return abs(net_credit_debit) * m
        return None

    if formula == "call_strike_minus_stock_cost":
        return None     # depends on stock cost vs call strike

    if formula in ("varies", "varies_iv_dependent"):
        return None

    return None


def calculate_max_loss(
    strategy_type: StrategyType,
    net_credit_debit: Decimal,
    width: Decimal = Decimal('0'),
    multiplier: int = 100,
    strike: Optional[Decimal] = None,
) -> Optional[Decimal]:
    """
    Calculate max loss for a strategy.

    Args:
        net_credit_debit: Positive = credit received, negative = debit paid
        width: Distance between strikes (for spreads)
        multiplier: Contract multiplier (100 for equity options)
        strike: Relevant strike price (for naked strategies)

    Returns:
        Max loss in dollars (always positive), or None if unlimited.
    """
    template = _TEMPLATES.get(strategy_type)
    if template is None:
        return None

    formula = template.max_loss_formula
    m = Decimal(str(multiplier))

    if formula == "width_minus_credit":
        return (width - abs(net_credit_debit)) * m

    if formula == "widest_wing_minus_credit":
        return (width - abs(net_credit_debit)) * m

    if formula == "wing_width_minus_credit":
        return (width - abs(net_credit_debit)) * m

    if formula == "debit_paid":
        return abs(net_credit_debit) * m

    if formula == "debit_plus_width_risk":
        return (abs(net_credit_debit) + width) * m

    if formula in ("unlimited_or_premium", "unlimited_or_debit"):
        return None     # can be unlimited (short straddle/strangle)

    if formula in ("unlimited_upside", "unlimited_on_naked_leg"):
        return None

    if formula == "put_strike_times_multiplier":
        if strike is not None:
            return strike * m
        return None

    if formula == "stock_cost_minus_premium":
        # Covered call: stock can go to 0
        if strike is not None:
            return (strike - abs(net_credit_debit)) * m
        return None

    if formula == "stock_cost_minus_strike_plus_debit":
        # Protective put
        return None     # depends on stock cost

    if formula == "stock_cost_minus_put_strike":
        # Collar
        return None     # depends on stock cost

    if formula == "varies":
        return None

    return None
