"""
Macro Context Service — Gate screener execution based on macro conditions.

Delegates market assessment to MarketAnalyzer (ma.context.assess()):
    - environment_label: risk-on / cautious / defensive / crisis
    - trading_allowed: bool (False when black swan CRITICAL)
    - position_size_factor: 0.0-1.0

Keeps user override logic locally (daily_macro.yaml or CLI).

Usage:
    from trading_cotrader.services.macro_context_service import MacroContextService

    macro = MacroContextService()
    assessment = macro.evaluate()
    if not assessment.should_screen:
        print(f"Skipping all screeners: {assessment.rationale}")
"""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional
import logging

# MarketAnalyzer imported lazily in _assess_from_market_analyzer() to avoid
# hmmlearn dependency at test collection time.

logger = logging.getLogger(__name__)


# Map MarketAnalyzer environment_label → our regime/modifier
_ENVIRONMENT_MAP = {
    'risk-on':   {'regime': 'risk_on',  'modifier': 1.0, 'should_screen': True},
    'cautious':  {'regime': 'cautious', 'modifier': 0.7, 'should_screen': True},
    'defensive': {'regime': 'cautious', 'modifier': 0.5, 'should_screen': True},
    'crisis':    {'regime': 'risk_off', 'modifier': 0.0, 'should_screen': False},
}


@dataclass
class MacroOverride:
    """Optional user-provided macro context (from CLI or daily_macro.yaml)."""
    market_probability: Optional[str] = None  # bullish / neutral / bearish / uncertain
    expected_volatility: Optional[str] = None  # low / normal / high / extreme
    notes: str = ""


@dataclass
class MacroAssessment:
    """Result of macro evaluation."""
    regime: str = "neutral"              # risk_on / neutral / cautious / risk_off
    confidence_modifier: float = 1.0     # 1.0 = no change, 0.6 = reduce, 0.0 = skip
    should_screen: bool = True           # False = skip all screeners
    rationale: str = ""
    vix_level: Optional[Decimal] = None
    override_applied: bool = False


class MacroContextService:
    """
    Evaluates macro conditions to gate screener execution.

    Delegates to MarketAnalyzer's context.assess() for market data.
    User override (daily_macro.yaml or CLI) trumps auto-assessment.
    """

    MACRO_FILE_PATHS = [
        Path('config/daily_macro.yaml'),
        Path('trading_cotrader/config/daily_macro.yaml'),
    ]

    def __init__(self, market_data=None, market_metrics=None):
        self._market_data = market_data
        self._market_metrics = market_metrics

    def evaluate(
        self, override: Optional[MacroOverride] = None
    ) -> MacroAssessment:
        """
        Evaluate macro conditions.

        Args:
            override: Optional user override. If None, tries daily_macro.yaml.

        Returns:
            MacroAssessment with regime, confidence modifier, and should_screen.
        """
        # User override trumps everything
        if override is None:
            override = self._load_override_from_file()

        if override and (override.market_probability or override.expected_volatility):
            return self._evaluate_from_override(override)

        # Delegate to MarketAnalyzer
        return self._assess_from_market_analyzer()

    def _assess_from_market_analyzer(self) -> MacroAssessment:
        """Auto-assess macro via MarketAnalyzer context service."""
        try:
            from market_analyzer import MarketAnalyzer
            ma = MarketAnalyzer(
                market_data=self._market_data,
                market_metrics=self._market_metrics,
            )
            ctx = ma.context.assess()

            env = ctx.environment_label or 'cautious'
            mapping = _ENVIRONMENT_MAP.get(env, _ENVIRONMENT_MAP['cautious'])

            # Extract VIX from black swan indicators if available
            vix_level = None
            if ctx.black_swan and ctx.black_swan.indicators:
                for ind in ctx.black_swan.indicators:
                    if 'vix' in ind.name.lower() and 'level' in ind.name.lower():
                        if ind.value is not None:
                            vix_level = Decimal(str(round(ind.value, 1)))
                        break

            return MacroAssessment(
                regime=mapping['regime'],
                confidence_modifier=ctx.position_size_factor if ctx.position_size_factor is not None else mapping['modifier'],
                should_screen=ctx.trading_allowed if ctx.trading_allowed is not None else mapping['should_screen'],
                rationale=ctx.summary or f"MarketAnalyzer: {env}",
                vix_level=vix_level,
            )

        except Exception as e:
            logger.warning(f"MarketAnalyzer context assessment failed: {e}")
            return MacroAssessment(
                regime="neutral",
                confidence_modifier=1.0,
                should_screen=True,
                rationale=f"MarketAnalyzer unavailable ({e}) — proceeding neutral",
            )

    def _evaluate_from_override(self, override: MacroOverride) -> MacroAssessment:
        """Evaluate based on user override."""
        prob = (override.market_probability or "").lower()
        vol = (override.expected_volatility or "").lower()

        if prob == "uncertain" or vol == "extreme":
            return MacroAssessment(
                regime="risk_off",
                confidence_modifier=0.0,
                should_screen=False,
                rationale=(
                    f"User override: probability={prob}, volatility={vol}"
                    + (f" — {override.notes}" if override.notes else "")
                ),
                override_applied=True,
            )

        if vol == "high" or prob == "bearish":
            return MacroAssessment(
                regime="cautious",
                confidence_modifier=0.6,
                should_screen=True,
                rationale=(
                    f"User override: probability={prob}, volatility={vol} — cautious mode"
                    + (f" — {override.notes}" if override.notes else "")
                ),
                override_applied=True,
            )

        if prob == "bullish" and vol in ("low", "normal", ""):
            return MacroAssessment(
                regime="risk_on",
                confidence_modifier=1.0,
                should_screen=True,
                rationale=(
                    f"User override: probability={prob}, volatility={vol} — risk-on"
                    + (f" — {override.notes}" if override.notes else "")
                ),
                override_applied=True,
            )

        return MacroAssessment(
            regime="neutral",
            confidence_modifier=1.0,
            should_screen=True,
            rationale=(
                f"User override: probability={prob}, volatility={vol} — neutral"
                + (f" — {override.notes}" if override.notes else "")
            ),
            override_applied=True,
        )

    def _load_override_from_file(self) -> Optional[MacroOverride]:
        """Try to load daily macro override from YAML file."""
        for path in self.MACRO_FILE_PATHS:
            if path.exists():
                try:
                    import yaml
                    with open(path, 'r') as f:
                        data = yaml.safe_load(f)
                    if data and isinstance(data, dict):
                        return MacroOverride(
                            market_probability=data.get('market_probability'),
                            expected_volatility=data.get('expected_volatility'),
                            notes=data.get('notes', ''),
                        )
                except Exception as e:
                    logger.warning(f"Failed to load macro override from {path}: {e}")
        return None
