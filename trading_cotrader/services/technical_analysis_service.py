"""
Technical Analysis Service — Computes indicators and regime classification.

Provides TechnicalSnapshot for each symbol with:
    - Moving averages (EMA 20/50, SMA 200)
    - RSI 14
    - ATR 14 + ATR percent
    - IV rank/percentile (realized vol proxy)
    - Directional regime (U/F/D)
    - Volatility regime (LOW/NORMAL/HIGH)
    - Distance from 52-week high + nearest support

Uses yfinance for OHLCV data. Falls back to pandas-based indicators
if talib is not available. Mock path for testing.

Usage:
    from trading_cotrader.services.technical_analysis_service import TechnicalAnalysisService

    ta = TechnicalAnalysisService()
    snap = ta.get_snapshot('SPY')
    print(f"RSI={snap.rsi_14}, regime={snap.directional_regime}")
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional
import logging
import math

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Cache duration for OHLCV data (seconds)
_CACHE_TTL = 3600  # 1 hour


@dataclass
class TechnicalSnapshot:
    """Technical indicators snapshot for a single symbol."""
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
    atr_percent: Optional[float] = None   # ATR / price

    # IV proxies (from realized vol)
    iv_rank: Optional[float] = None       # 0-100
    iv_percentile: Optional[float] = None # 0-100

    # Regime classification
    directional_regime: Optional[str] = None  # "U" / "F" / "D"
    volatility_regime: Optional[str] = None   # "LOW" / "NORMAL" / "HIGH"

    # Position relative to history
    pct_from_52w_high: Optional[float] = None  # negative = below high
    high_52w: Optional[Decimal] = None
    low_52w: Optional[Decimal] = None
    nearest_support: Optional[Decimal] = None  # SMA 200 or recent swing low

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'current_price': float(self.current_price),
            'ema_20': float(self.ema_20) if self.ema_20 else None,
            'ema_50': float(self.ema_50) if self.ema_50 else None,
            'sma_200': float(self.sma_200) if self.sma_200 else None,
            'rsi_14': self.rsi_14,
            'atr_14': float(self.atr_14) if self.atr_14 else None,
            'atr_percent': self.atr_percent,
            'iv_rank': self.iv_rank,
            'iv_percentile': self.iv_percentile,
            'directional_regime': self.directional_regime,
            'volatility_regime': self.volatility_regime,
            'pct_from_52w_high': self.pct_from_52w_high,
            'nearest_support': float(self.nearest_support) if self.nearest_support else None,
        }


class TechnicalAnalysisService:
    """
    Computes technical indicators for symbols.

    Uses yfinance for data + talib (or pandas fallback) for indicators.
    Caches OHLCV data for 1 hour.
    """

    def __init__(self, use_mock: bool = False):
        """
        Args:
            use_mock: If True, return mock snapshots without fetching data.
        """
        self.use_mock = use_mock
        self._cache: Dict[str, tuple] = {}  # symbol → (timestamp, DataFrame)
        self._talib_available = self._check_talib()

    def get_snapshot(self, symbol: str) -> TechnicalSnapshot:
        """Get technical snapshot for a single symbol."""
        if self.use_mock:
            return self._mock_snapshot(symbol)

        try:
            df = self._fetch_ohlcv(symbol)
            if df is None or len(df) < 60:
                logger.warning(f"Insufficient data for {symbol}, using mock")
                return self._mock_snapshot(symbol)
            return self._compute_snapshot(symbol, df)
        except Exception as e:
            logger.warning(f"Failed to compute snapshot for {symbol}: {e}")
            return self._mock_snapshot(symbol)

    def get_snapshots(self, symbols: List[str]) -> Dict[str, TechnicalSnapshot]:
        """Get technical snapshots for multiple symbols."""
        results = {}
        for symbol in symbols:
            results[symbol] = self.get_snapshot(symbol)
        return results

    def _check_talib(self) -> bool:
        """Check if talib is available."""
        try:
            import talib  # noqa: F401
            return True
        except ImportError:
            logger.info("talib not available, using pandas fallback for indicators")
            return False

    def _fetch_ohlcv(self, symbol: str) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data from yfinance with caching."""
        now = datetime.utcnow()

        # Check cache
        if symbol in self._cache:
            cached_time, cached_df = self._cache[symbol]
            if (now - cached_time).total_seconds() < _CACHE_TTL:
                return cached_df

        try:
            import yfinance as yf
            df = yf.download(
                symbol, period="2y", interval="1d",
                auto_adjust=True, progress=False
            )
            if df is None or df.empty:
                return None

            # Handle MultiIndex columns from yfinance
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
            self._cache[symbol] = (now, df)
            return df
        except Exception as e:
            logger.warning(f"yfinance fetch failed for {symbol}: {e}")
            return None

    def _compute_snapshot(self, symbol: str, df: pd.DataFrame) -> TechnicalSnapshot:
        """Compute all indicators from OHLCV data."""
        close = df["Close"].to_numpy(dtype=np.float64).reshape(-1)
        high = df["High"].to_numpy(dtype=np.float64).reshape(-1)
        low = df["Low"].to_numpy(dtype=np.float64).reshape(-1)

        snap = TechnicalSnapshot(symbol=symbol)
        snap.current_price = Decimal(str(round(close[-1], 2)))

        # Moving averages
        if self._talib_available:
            import talib
            ema_20 = talib.EMA(close, timeperiod=20)
            ema_50 = talib.EMA(close, timeperiod=50)
            sma_200 = talib.SMA(close, timeperiod=200)
            rsi = talib.RSI(close, timeperiod=14)
            atr = talib.ATR(high, low, close, timeperiod=14)
            macd_hist = talib.MACD(close)[2]
            adx = talib.ADX(high, low, close, timeperiod=14)
        else:
            ema_20 = self._ema_pd(close, 20)
            ema_50 = self._ema_pd(close, 50)
            sma_200 = self._sma_pd(close, 200)
            rsi = self._rsi_pd(close, 14)
            atr = self._atr_pd(high, low, close, 14)
            macd_hist = self._macd_pd(close)
            adx = np.full_like(close, 25.0)  # default neutral ADX

        # Set MA values
        if not np.isnan(ema_20[-1]):
            snap.ema_20 = Decimal(str(round(ema_20[-1], 2)))
        if not np.isnan(ema_50[-1]):
            snap.ema_50 = Decimal(str(round(ema_50[-1], 2)))
        if len(sma_200) > 0 and not np.isnan(sma_200[-1]):
            snap.sma_200 = Decimal(str(round(sma_200[-1], 2)))

        # RSI
        if not np.isnan(rsi[-1]):
            snap.rsi_14 = round(float(rsi[-1]), 2)

        # ATR
        if not np.isnan(atr[-1]):
            snap.atr_14 = Decimal(str(round(atr[-1], 2)))
            snap.atr_percent = round(float(atr[-1] / close[-1]), 6)

        # Directional regime (from playground pattern)
        snap.directional_regime = self._classify_directional(
            ema_20, ema_50, rsi, macd_hist, adx, len(close) - 1
        )

        # Volatility regime
        snap.volatility_regime = self._classify_volatility(atr, close, len(close) - 1)

        # 52-week high/low
        lookback_252 = min(252, len(close))
        recent = close[-lookback_252:]
        high_52w = float(np.max(recent))
        low_52w = float(np.min(recent))
        snap.high_52w = Decimal(str(round(high_52w, 2)))
        snap.low_52w = Decimal(str(round(low_52w, 2)))
        snap.pct_from_52w_high = round(
            (float(close[-1]) - high_52w) / high_52w * 100, 2
        )

        # Nearest support: SMA 200 or 52-week low, whichever is closer above the low
        if snap.sma_200 and float(snap.sma_200) < float(snap.current_price):
            snap.nearest_support = snap.sma_200
        else:
            snap.nearest_support = snap.low_52w

        # IV rank/percentile via realized vol proxy
        snap.iv_rank, snap.iv_percentile = self._compute_iv_proxy(close)

        return snap

    def _classify_directional(
        self, ema_fast, ema_slow, rsi, macd_hist, adx, idx: int
    ) -> str:
        """Classify directional regime: U(p), F(lat), D(own)."""
        if any(np.isnan(x[idx]) for x in [ema_fast, ema_slow, rsi, adx]):
            return "F"

        ema_diff = ema_fast[idx] - ema_slow[idx]
        trend = np.tanh((ema_diff / ema_slow[idx]) * 20)
        momentum = (rsi[idx] - 50) / 50

        macd_val = macd_hist[idx] if not np.isnan(macd_hist[idx]) else 0.0
        accel = np.tanh(macd_val * 5)
        strength = min(adx[idx] / 40, 1)

        up = max(trend, 0) + max(momentum, 0) + max(accel, 0)
        down = max(-trend, 0) + max(-momentum, 0) + max(-accel, 0)
        flat = (1 - strength) * 2

        scores = {"U": up, "F": flat, "D": down}
        return max(scores, key=scores.get)

    def _classify_volatility(self, atr, close, idx: int) -> str:
        """Classify volatility regime: LOW, NORMAL, HIGH."""
        if np.isnan(atr[idx]):
            return "NORMAL"
        atr_pct = atr[idx] / close[idx]
        if atr_pct < 0.012:
            return "LOW"
        elif atr_pct < 0.025:
            return "NORMAL"
        else:
            return "HIGH"

    def _compute_iv_proxy(self, close: np.ndarray) -> tuple:
        """
        Compute IV rank and percentile using realized vol as proxy.

        Uses 20-day realized vol compared against 252-day range.
        """
        if len(close) < 60:
            return None, None

        returns = np.diff(np.log(close))

        # Current 20-day realized vol (annualized)
        current_vol = float(np.std(returns[-20:]) * math.sqrt(252) * 100)

        # Rolling 20-day vol over past year
        lookback = min(252, len(returns))
        rolling_vols = []
        for i in range(20, lookback):
            rv = float(np.std(returns[-(i+1):-(i-19)]) * math.sqrt(252) * 100)
            rolling_vols.append(rv)

        if not rolling_vols:
            return None, None

        # IV rank: where is current vol relative to 52w range
        vol_min = min(rolling_vols)
        vol_max = max(rolling_vols)
        if vol_max - vol_min < 0.001:
            iv_rank = 50.0
        else:
            iv_rank = round((current_vol - vol_min) / (vol_max - vol_min) * 100, 1)
            iv_rank = max(0.0, min(100.0, iv_rank))

        # IV percentile: % of observations below current
        below = sum(1 for v in rolling_vols if v <= current_vol)
        iv_pct = round(below / len(rolling_vols) * 100, 1)

        return iv_rank, iv_pct

    # =========================================================================
    # Pandas fallback indicators (when talib not available)
    # =========================================================================

    @staticmethod
    def _ema_pd(data: np.ndarray, period: int) -> np.ndarray:
        s = pd.Series(data)
        return s.ewm(span=period, adjust=False).mean().to_numpy()

    @staticmethod
    def _sma_pd(data: np.ndarray, period: int) -> np.ndarray:
        s = pd.Series(data)
        return s.rolling(window=period).mean().to_numpy()

    @staticmethod
    def _rsi_pd(data: np.ndarray, period: int = 14) -> np.ndarray:
        s = pd.Series(data)
        delta = s.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.to_numpy()

    @staticmethod
    def _atr_pd(
        high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
    ) -> np.ndarray:
        h = pd.Series(high)
        l = pd.Series(low)
        c = pd.Series(close)
        prev_c = c.shift(1)
        tr = pd.concat([
            h - l,
            (h - prev_c).abs(),
            (l - prev_c).abs(),
        ], axis=1).max(axis=1)
        return tr.rolling(window=period).mean().to_numpy()

    @staticmethod
    def _macd_pd(data: np.ndarray) -> np.ndarray:
        s = pd.Series(data)
        ema12 = s.ewm(span=12, adjust=False).mean()
        ema26 = s.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal = macd_line.ewm(span=9, adjust=False).mean()
        return (macd_line - signal).to_numpy()

    # =========================================================================
    # Mock snapshots for testing
    # =========================================================================

    def _mock_snapshot(self, symbol: str) -> TechnicalSnapshot:
        """Return a reasonable mock snapshot for testing."""
        mock_prices = {
            'SPY': 590, 'QQQ': 510, 'IWM': 220, 'AAPL': 240,
            'MSFT': 430, 'AMZN': 210, 'GOOGL': 175, 'TSLA': 340,
            'NVDA': 135, 'META': 590, 'AMD': 160, 'JPM': 230,
            'V': 300,
        }
        price = mock_prices.get(symbol, 100)

        return TechnicalSnapshot(
            symbol=symbol,
            current_price=Decimal(str(price)),
            ema_20=Decimal(str(round(price * 0.99, 2))),
            ema_50=Decimal(str(round(price * 0.97, 2))),
            sma_200=Decimal(str(round(price * 0.92, 2))),
            rsi_14=52.0,
            atr_14=Decimal(str(round(price * 0.015, 2))),
            atr_percent=0.015,
            iv_rank=45.0,
            iv_percentile=50.0,
            directional_regime="F",
            volatility_regime="NORMAL",
            pct_from_52w_high=-3.5,
            high_52w=Decimal(str(round(price * 1.035, 2))),
            low_52w=Decimal(str(round(price * 0.82, 2))),
            nearest_support=Decimal(str(round(price * 0.92, 2))),
        )
