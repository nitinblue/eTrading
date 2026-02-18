"""
Market Data Container — Per-underlying technical indicator storage with change tracking.

Cross-portfolio container (market data is shared across all portfolios).
Populated by MarketDataAgent from TechnicalAnalysisService snapshots.
Consumed by screeners, risk agents, and the frontend API.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class MarketDataEntry:
    """Technical indicators for a single underlying."""
    symbol: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Price
    current_price: Decimal = Decimal('0')

    # Moving averages
    ema_20: Optional[Decimal] = None
    ema_50: Optional[Decimal] = None
    sma_200: Optional[Decimal] = None

    # Oscillators
    rsi_14: Optional[float] = None

    # Volatility
    atr_14: Optional[Decimal] = None
    atr_percent: Optional[float] = None
    iv_rank: Optional[float] = None
    iv_percentile: Optional[float] = None

    # Bollinger Bands
    bollinger_upper: Optional[Decimal] = None
    bollinger_middle: Optional[Decimal] = None
    bollinger_lower: Optional[Decimal] = None
    bollinger_width: Optional[float] = None

    # VWAP
    vwap: Optional[Decimal] = None

    # Regimes
    directional_regime: Optional[str] = None  # U/F/D
    volatility_regime: Optional[str] = None   # LOW/NORMAL/HIGH

    # Key levels
    high_52w: Optional[Decimal] = None
    low_52w: Optional[Decimal] = None
    pct_from_52w_high: Optional[float] = None
    nearest_support: Optional[Decimal] = None
    nearest_resistance: Optional[Decimal] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'current_price': float(self.current_price),
            'ema_20': float(self.ema_20) if self.ema_20 else None,
            'ema_50': float(self.ema_50) if self.ema_50 else None,
            'sma_200': float(self.sma_200) if self.sma_200 else None,
            'rsi_14': self.rsi_14,
            'atr_14': float(self.atr_14) if self.atr_14 else None,
            'atr_percent': self.atr_percent,
            'iv_rank': self.iv_rank,
            'iv_percentile': self.iv_percentile,
            'bollinger_upper': float(self.bollinger_upper) if self.bollinger_upper else None,
            'bollinger_middle': float(self.bollinger_middle) if self.bollinger_middle else None,
            'bollinger_lower': float(self.bollinger_lower) if self.bollinger_lower else None,
            'bollinger_width': self.bollinger_width,
            'vwap': float(self.vwap) if self.vwap else None,
            'directional_regime': self.directional_regime,
            'volatility_regime': self.volatility_regime,
            'high_52w': float(self.high_52w) if self.high_52w else None,
            'low_52w': float(self.low_52w) if self.low_52w else None,
            'pct_from_52w_high': self.pct_from_52w_high,
            'nearest_support': float(self.nearest_support) if self.nearest_support else None,
            'nearest_resistance': float(self.nearest_resistance) if self.nearest_resistance else None,
        }


class MarketDataContainer:
    """
    Per-underlying technical indicator storage with change tracking.

    Cross-portfolio: market data is the same regardless of which portfolio
    you're looking at. One instance in ContainerManager.
    """

    def __init__(self):
        self._data: Dict[str, MarketDataEntry] = {}

    def update_from_snapshot(self, snap) -> Dict[str, Any]:
        """
        Update entry from a TechnicalSnapshot object.

        Args:
            snap: TechnicalSnapshot from TechnicalAnalysisService.

        Returns:
            Dict of changed field names → {'old': ..., 'new': ...}.
        """
        symbol = snap.symbol
        changes: Dict[str, Any] = {}

        entry = self._data.get(symbol)
        if entry is None:
            entry = MarketDataEntry(symbol=symbol)
            self._data[symbol] = entry

        # Map snapshot fields to entry fields
        field_map = {
            'current_price': 'current_price',
            'ema_20': 'ema_20',
            'ema_50': 'ema_50',
            'sma_200': 'sma_200',
            'rsi_14': 'rsi_14',
            'atr_14': 'atr_14',
            'atr_percent': 'atr_percent',
            'iv_rank': 'iv_rank',
            'iv_percentile': 'iv_percentile',
            'bollinger_upper': 'bollinger_upper',
            'bollinger_middle': 'bollinger_middle',
            'bollinger_lower': 'bollinger_lower',
            'bollinger_width': 'bollinger_width',
            'vwap': 'vwap',
            'directional_regime': 'directional_regime',
            'volatility_regime': 'volatility_regime',
            'high_52w': 'high_52w',
            'low_52w': 'low_52w',
            'pct_from_52w_high': 'pct_from_52w_high',
            'nearest_support': 'nearest_support',
            'nearest_resistance': 'nearest_resistance',
        }

        for snap_field, entry_field in field_map.items():
            new_val = getattr(snap, snap_field, None)
            old_val = getattr(entry, entry_field, None)
            if new_val != old_val:
                changes[entry_field] = {'old': old_val, 'new': new_val}
                setattr(entry, entry_field, new_val)

        entry.timestamp = datetime.utcnow()
        return changes

    def update_from_dict(self, symbol: str, data: dict) -> Dict[str, Any]:
        """
        Update from raw dict (for API/manual override).

        Returns:
            Dict of changed field names.
        """
        changes: Dict[str, Any] = {}
        entry = self._data.get(symbol)
        if entry is None:
            entry = MarketDataEntry(symbol=symbol)
            self._data[symbol] = entry

        for key, val in data.items():
            if hasattr(entry, key) and key != 'symbol':
                old_val = getattr(entry, key)
                if old_val != val:
                    changes[key] = {'old': old_val, 'new': val}
                    setattr(entry, key, val)

        entry.timestamp = datetime.utcnow()
        return changes

    def get(self, symbol: str) -> Optional[MarketDataEntry]:
        """Get entry for a symbol."""
        return self._data.get(symbol)

    def get_all(self) -> Dict[str, MarketDataEntry]:
        """Get all entries."""
        return dict(self._data)

    def to_grid_rows(self) -> List[Dict]:
        """Serialize all entries for AG Grid."""
        return [entry.to_dict() for entry in self._data.values()]

    @property
    def symbols(self) -> List[str]:
        """All tracked symbols."""
        return list(self._data.keys())

    @property
    def count(self) -> int:
        return len(self._data)
