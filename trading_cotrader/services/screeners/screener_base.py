"""
Screener Base Class — Abstract interface for all screeners.

Each screener:
    1. Takes a list of symbols (from a watchlist)
    2. Evaluates market conditions per symbol
    3. Returns a list of Recommendation objects

Screeners do NOT book trades. They only generate recommendations.
The RecommendationService handles the accept/reject lifecycle.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional, Dict, Any
import logging

from trading_cotrader.core.models.recommendation import (
    Recommendation, RecommendedLeg, MarketSnapshot
)

logger = logging.getLogger(__name__)


class ScreenerBase(ABC):
    """Abstract base class for all screeners."""

    # Subclass must set these
    name: str = "base_screener"
    source: str = "manual"  # TradeSource enum value

    def __init__(self, broker=None, technical_service=None):
        """
        Args:
            broker: TastytradeAdapter (authenticated). None = mock mode.
            technical_service: TechnicalAnalysisService instance (optional).
        """
        self.broker = broker
        self.technical_service = technical_service

    @abstractmethod
    def screen(self, symbols: List[str]) -> List[Recommendation]:
        """
        Screen a list of symbols and generate recommendations.

        Args:
            symbols: List of underlying ticker symbols.

        Returns:
            List of Recommendation objects.
        """
        pass

    def get_market_context(self, symbol: str) -> MarketSnapshot:
        """
        Get current market context for a symbol.
        Override in subclass for live data.

        Returns:
            MarketSnapshot with current conditions.
        """
        return MarketSnapshot(underlying_price=Decimal('0'))

    def _get_technical_snapshot(self, symbol: str):
        """Get technical snapshot if service is available."""
        if self.technical_service:
            return self.technical_service.get_snapshot(symbol)
        return None

    def _enrich_market_context(
        self, ctx: MarketSnapshot, tech_snap
    ) -> MarketSnapshot:
        """Enrich a MarketSnapshot with technical indicators."""
        if tech_snap is None:
            return ctx

        ctx.rsi = Decimal(str(tech_snap.rsi_14)) if tech_snap.rsi_14 is not None else None
        ctx.iv_rank = Decimal(str(tech_snap.iv_rank)) if tech_snap.iv_rank is not None else None
        ctx.iv_percentile = Decimal(str(tech_snap.iv_percentile)) if tech_snap.iv_percentile is not None else None
        ctx.ema_20 = tech_snap.ema_20
        ctx.ema_50 = tech_snap.ema_50
        ctx.sma_200 = tech_snap.sma_200
        ctx.atr_percent = tech_snap.atr_percent
        ctx.directional_regime = tech_snap.directional_regime
        ctx.volatility_regime = tech_snap.volatility_regime
        ctx.pct_from_52w_high = tech_snap.pct_from_52w_high
        return ctx

    def _check_entry_filters(
        self, strategy_type: str, tech_snap, risk_config=None
    ) -> tuple:
        """
        Check entry filters from risk_config for a strategy type.

        Args:
            strategy_type: e.g. "iron_condor"
            tech_snap: TechnicalSnapshot (or None)
            risk_config: RiskConfig (loaded if None)

        Returns:
            (passed: bool, reason: str)
        """
        if tech_snap is None:
            return True, "no technical data — skipping filters"

        if risk_config is None:
            try:
                from trading_cotrader.config.risk_config_loader import get_risk_config
                risk_config = get_risk_config()
            except Exception:
                return True, "could not load risk config"

        rule = risk_config.strategy_rules.get(strategy_type)
        if rule is None or rule.entry_filters is None:
            return True, "no entry filters defined"

        ef = rule.entry_filters

        # RSI range check
        if ef.rsi_range and tech_snap.rsi_14 is not None:
            if not (ef.rsi_range[0] <= tech_snap.rsi_14 <= ef.rsi_range[1]):
                return False, f"RSI {tech_snap.rsi_14:.1f} outside [{ef.rsi_range[0]}, {ef.rsi_range[1]}]"

        # Directional regime check
        if ef.directional_regime and tech_snap.directional_regime:
            if tech_snap.directional_regime not in ef.directional_regime:
                return False, (
                    f"Directional regime '{tech_snap.directional_regime}' "
                    f"not in {ef.directional_regime}"
                )

        # Volatility regime check
        if ef.volatility_regime and tech_snap.volatility_regime:
            if tech_snap.volatility_regime not in ef.volatility_regime:
                return False, (
                    f"Volatility regime '{tech_snap.volatility_regime}' "
                    f"not in {ef.volatility_regime}"
                )

        # ATR percent checks
        if ef.min_atr_percent is not None and tech_snap.atr_percent is not None:
            if tech_snap.atr_percent < ef.min_atr_percent:
                return False, f"ATR% {tech_snap.atr_percent:.4f} < min {ef.min_atr_percent}"

        if ef.max_atr_percent is not None and tech_snap.atr_percent is not None:
            if tech_snap.atr_percent > ef.max_atr_percent:
                return False, f"ATR% {tech_snap.atr_percent:.4f} > max {ef.max_atr_percent}"

        # IV percentile checks
        if ef.min_iv_percentile is not None and tech_snap.iv_percentile is not None:
            if tech_snap.iv_percentile < ef.min_iv_percentile:
                return False, f"IV pctile {tech_snap.iv_percentile:.1f} < min {ef.min_iv_percentile}"

        if ef.max_iv_percentile is not None and tech_snap.iv_percentile is not None:
            if tech_snap.iv_percentile > ef.max_iv_percentile:
                return False, f"IV pctile {tech_snap.iv_percentile:.1f} > max {ef.max_iv_percentile}"

        # Pct from high checks
        if ef.min_pct_from_high is not None and tech_snap.pct_from_52w_high is not None:
            if tech_snap.pct_from_52w_high > ef.min_pct_from_high:
                return False, (
                    f"Pct from high {tech_snap.pct_from_52w_high:.1f}% "
                    f"> min {ef.min_pct_from_high}%"
                )

        return True, "all entry filters passed"

    def _build_option_streamer_symbol(
        self,
        ticker: str,
        expiration_str: str,
        option_type: str,
        strike: Decimal,
    ) -> str:
        """
        Build DXLink streamer symbol for an option.

        Args:
            ticker: Underlying ticker (e.g. "SPY")
            expiration_str: YYMMDD format (e.g. "260320")
            option_type: "C" or "P"
            strike: Strike price

        Returns:
            Streamer symbol (e.g. ".SPY260320P550")
        """
        strike_str = str(int(strike))
        return f".{ticker}{expiration_str}{option_type}{strike_str}"

    def _get_nearest_monthly_expiration(self, dte_target: int = 45) -> str:
        """
        Get the nearest monthly options expiration as YYMMDD string.
        Targets approximately `dte_target` days out.

        Returns:
            YYMMDD formatted expiration string.
        """
        from datetime import datetime, timedelta
        import calendar

        target_date = datetime.utcnow() + timedelta(days=dte_target)

        # Find 3rd Friday of the target month
        year = target_date.year
        month = target_date.month
        cal = calendar.Calendar()
        fridays = [
            d for d in cal.itermonthdates(year, month)
            if d.weekday() == 4 and d.month == month
        ]
        if len(fridays) >= 3:
            third_friday = fridays[2]
        else:
            third_friday = fridays[-1]

        # If third friday is in the past, go to next month
        if third_friday < target_date.date():
            month += 1
            if month > 12:
                month = 1
                year += 1
            fridays = [
                d for d in cal.Calendar().itermonthdates(year, month)
                if d.weekday() == 4 and d.month == month
            ]
            third_friday = fridays[2] if len(fridays) >= 3 else fridays[-1]

        return third_friday.strftime('%y%m%d')
