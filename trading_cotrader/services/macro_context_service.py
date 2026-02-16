"""
Macro Context Service — Short-circuit screeners when macro conditions are dangerous.

Before any screener runs, evaluate macro conditions:
    1. Auto-assessment from VIX level/trend
    2. Optional user override from daily_macro.yaml or CLI args

If macro says "risk_off" → no screeners run, no recommendations generated.
If macro says "cautious" → run screeners but reduce confidence on all recs.

Usage:
    from trading_cotrader.services.macro_context_service import MacroContextService

    macro = MacroContextService()
    assessment = macro.evaluate()
    if not assessment.should_screen:
        print(f"Skipping all screeners: {assessment.rationale}")
"""

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


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

    Auto-assessment from VIX:
        VIX < 15         → risk_on   (modifier 1.0)
        VIX 15-25        → neutral   (modifier 1.0)
        VIX 25-35        → cautious  (modifier 0.6)
        VIX > 35         → risk_off  (should_screen=False)

    User override trumps auto-assessment.
    """

    # Default path for daily macro file
    MACRO_FILE_PATHS = [
        Path('config/daily_macro.yaml'),
        Path('trading_cotrader/config/daily_macro.yaml'),
    ]

    def __init__(self, broker=None):
        self.broker = broker

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
        # Try loading override from file if not provided
        if override is None:
            override = self._load_override_from_file()

        # If user override provided, use it
        if override and (override.market_probability or override.expected_volatility):
            return self._evaluate_from_override(override)

        # Otherwise auto-assess from VIX
        return self._auto_assess()

    def _auto_assess(self) -> MacroAssessment:
        """Auto-assess macro from VIX level."""
        vix = self._get_vix()
        if vix is None:
            return MacroAssessment(
                regime="neutral",
                confidence_modifier=1.0,
                should_screen=True,
                rationale="Could not determine VIX — proceeding with neutral assessment",
            )

        if vix < 15:
            return MacroAssessment(
                regime="risk_on",
                confidence_modifier=1.0,
                should_screen=True,
                rationale=f"VIX={vix:.1f} — low volatility, risk-on environment",
                vix_level=vix,
            )
        elif vix <= 25:
            return MacroAssessment(
                regime="neutral",
                confidence_modifier=1.0,
                should_screen=True,
                rationale=f"VIX={vix:.1f} — normal range, proceed as usual",
                vix_level=vix,
            )
        elif vix <= 35:
            return MacroAssessment(
                regime="cautious",
                confidence_modifier=0.6,
                should_screen=True,
                rationale=f"VIX={vix:.1f} — elevated volatility, reduced confidence",
                vix_level=vix,
            )
        else:
            return MacroAssessment(
                regime="risk_off",
                confidence_modifier=0.0,
                should_screen=False,
                rationale=f"VIX={vix:.1f} — extreme volatility, skip all screening",
                vix_level=vix,
            )

    def _evaluate_from_override(self, override: MacroOverride) -> MacroAssessment:
        """Evaluate based on user override."""
        # Determine regime from user inputs
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

        # Default: neutral
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

    def _get_vix(self) -> Optional[Decimal]:
        """Get current VIX level."""
        if not self.broker:
            # Default mock for no-broker mode
            return Decimal('18')

        try:
            quote = self.broker.get_quote('VIX')
            if quote:
                bid = quote.get('bid', 0) or 0
                ask = quote.get('ask', 0) or 0
                mid = (bid + ask) / 2
                if mid > 0:
                    return Decimal(str(mid))
        except NotImplementedError:
            pass
        except Exception as e:
            logger.error(f"Failed to fetch VIX via broker: {e}")

        # Fallback: try yfinance
        try:
            import yfinance as yf
            vix_data = yf.Ticker('^VIX').history(period='1d')
            if not vix_data.empty:
                return Decimal(str(vix_data['Close'].iloc[-1]))
        except Exception as e:
            logger.warning(f"yfinance VIX fallback failed: {e}")

        return None
