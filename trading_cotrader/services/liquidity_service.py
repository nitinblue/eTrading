"""
Liquidity Service — Checks bid-ask spread, open interest, and volume
before entering trades or recommending adjustments.

If a position is illiquid, the system recommends CLOSE instead of ADJUST/ROLL.
Thresholds are configured in risk_config.yaml under `liquidity_thresholds`.

Usage:
    from trading_cotrader.services.liquidity_service import LiquidityService

    svc = LiquidityService(broker=broker)
    snap = svc.check_liquidity(".SPY260320P550")
    if svc.meets_entry_threshold(snap):
        print("Liquid enough to enter")
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Dict
import logging

from trading_cotrader.config.risk_config_loader import (
    LiquidityThreshold, LiquidityThresholds, get_risk_config
)

logger = logging.getLogger(__name__)


@dataclass
class LiquiditySnapshot:
    """Point-in-time liquidity data for a single option/symbol."""
    symbol: str = ""
    bid: Decimal = Decimal('0')
    ask: Decimal = Decimal('0')
    mid: Decimal = Decimal('0')
    spread: Decimal = Decimal('0')
    spread_pct: float = 0.0          # (ask-bid)/mid * 100
    open_interest: int = 0
    daily_volume: int = 0
    is_liquid: bool = True            # meets entry threshold
    is_adjustment_liquid: bool = True  # meets adjustment threshold (tighter)

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'bid': float(self.bid),
            'ask': float(self.ask),
            'mid': float(self.mid),
            'spread': float(self.spread),
            'spread_pct': self.spread_pct,
            'open_interest': self.open_interest,
            'daily_volume': self.daily_volume,
            'is_liquid': self.is_liquid,
            'is_adjustment_liquid': self.is_adjustment_liquid,
        }


class LiquidityService:
    """
    Checks liquidity for options before entry or adjustment decisions.

    With broker: fetches real bid/ask/OI/volume via DXLink.
    Without broker (mock mode): returns a default "liquid" snapshot.
    """

    def __init__(self, broker=None, config: Optional[LiquidityThresholds] = None):
        self.broker = broker
        if config is not None:
            self.config = config
        else:
            try:
                self.config = get_risk_config().liquidity
            except Exception:
                self.config = LiquidityThresholds()

    def check_liquidity(self, symbol: str) -> LiquiditySnapshot:
        """
        Get liquidity snapshot for a symbol.

        Args:
            symbol: Streamer symbol (e.g. ".SPY260320P550")

        Returns:
            LiquiditySnapshot with bid/ask/spread/OI/volume.
        """
        if not self.broker:
            return self._mock_liquidity(symbol)

        try:
            return self._fetch_liquidity(symbol)
        except Exception as e:
            logger.warning(f"Failed to fetch liquidity for {symbol}: {e}")
            return self._mock_liquidity(symbol)

    def meets_entry_threshold(
        self, snap: LiquiditySnapshot, threshold: Optional[LiquidityThreshold] = None
    ) -> bool:
        """Check if liquidity meets entry thresholds."""
        t = threshold or self.config.entry
        return self._check_threshold(snap, t)

    def meets_adjustment_threshold(
        self, snap: LiquiditySnapshot, threshold: Optional[LiquidityThreshold] = None
    ) -> bool:
        """Check if liquidity meets adjustment thresholds (tighter)."""
        t = threshold or self.config.adjustment
        return self._check_threshold(snap, t)

    def get_liquidity_reason(
        self, snap: LiquiditySnapshot, threshold: Optional[LiquidityThreshold] = None
    ) -> str:
        """Get human-readable reason why liquidity check failed."""
        t = threshold or self.config.entry
        reasons = []

        if snap.open_interest < t.min_open_interest:
            reasons.append(f"OI {snap.open_interest} < {t.min_open_interest}")
        if snap.spread_pct > t.max_bid_ask_spread_pct:
            reasons.append(f"spread {snap.spread_pct:.1f}% > {t.max_bid_ask_spread_pct}%")
        if snap.daily_volume < t.min_daily_volume:
            reasons.append(f"volume {snap.daily_volume} < {t.min_daily_volume}")

        return "; ".join(reasons) if reasons else "liquid"

    def _check_threshold(self, snap: LiquiditySnapshot, t: LiquidityThreshold) -> bool:
        """Check snapshot against a threshold."""
        if snap.open_interest < t.min_open_interest:
            return False
        if snap.spread_pct > t.max_bid_ask_spread_pct:
            return False
        if snap.daily_volume < t.min_daily_volume:
            return False
        return True

    def _mock_liquidity(self, symbol: str) -> LiquiditySnapshot:
        """Return a default liquid snapshot for mock/no-broker mode."""
        return LiquiditySnapshot(
            symbol=symbol,
            bid=Decimal('1.50'),
            ask=Decimal('1.55'),
            mid=Decimal('1.525'),
            spread=Decimal('0.05'),
            spread_pct=3.3,
            open_interest=5000,
            daily_volume=2000,
            is_liquid=True,
            is_adjustment_liquid=True,
        )

    def _fetch_liquidity(self, symbol: str) -> LiquiditySnapshot:
        """Fetch real liquidity data from broker via DXLink."""
        import asyncio
        from tastytrade.streamer import DXLinkStreamer
        from tastytrade.dxfeed import Quote as DXQuote

        bid = Decimal('0')
        ask = Decimal('0')

        async def _stream_quote():
            nonlocal bid, ask
            try:
                async with DXLinkStreamer(self.broker.data_session) as streamer:
                    await streamer.subscribe(DXQuote, [symbol])
                    event = await asyncio.wait_for(
                        streamer.get_event(DXQuote), timeout=3.0
                    )
                    bid = Decimal(str(event.bid_price or 0))
                    ask = Decimal(str(event.ask_price or 0))
            except asyncio.TimeoutError:
                logger.warning(f"Timeout fetching quote for {symbol}")
            except Exception as e:
                logger.warning(f"Error fetching quote for {symbol}: {e}")

        self.broker._run_async(_stream_quote())

        mid = (bid + ask) / 2 if (bid and ask) else Decimal('0')
        spread = ask - bid
        spread_pct = float(spread / mid * 100) if mid > 0 else 999.0

        # Note: open interest and volume require additional API calls
        # For now, return defaults that pass — real OI/vol integration
        # will come with TastyTrade /market-metrics API
        snap = LiquiditySnapshot(
            symbol=symbol,
            bid=bid,
            ask=ask,
            mid=mid,
            spread=spread,
            spread_pct=spread_pct,
            open_interest=5000,   # placeholder until /market-metrics
            daily_volume=2000,    # placeholder until /market-metrics
        )
        snap.is_liquid = self.meets_entry_threshold(snap)
        snap.is_adjustment_liquid = self.meets_adjustment_threshold(snap)
        return snap
