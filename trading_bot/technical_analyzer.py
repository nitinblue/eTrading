# trading_bot/technical_analyzer.py
"""
Technical Analyzer framework with OO indicator design.
- Uses Strategy Pattern for indicators (no if/else).
- Register new indicators in the factory.
- Uses yfinance for historical data.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import logging
from abc import ABC, abstractmethod
from datetime import datetime

logger = logging.getLogger(__name__)

class Indicator(ABC):
    """Abstract base for technical indicators."""
    @abstractmethod
    def calculate(self, data: pd.DataFrame) -> dict:
        """Calculate the indicator and return results."""
        pass

# Concrete Indicators (add more as needed)
class RSIIndicator(Indicator):
    def __init__(self, period: int = 14):
        self.period = period

    def calculate(self, data: pd.DataFrame) -> dict:
        if data.empty:
            return {'rsi': np.nan}
        close = data['Close']
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=self.period, min_periods=1).mean()
        avg_loss = loss.rolling(window=self.period, min_periods=1).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return {'rsi': rsi.iloc[-1] if len(rsi) > 0 else np.nan}

class SMAIndicator(Indicator):
    def __init__(self, short_period: int = 50, long_period: int = 200):
        self.short_period = short_period
        self.long_period = long_period

    def calculate(self, data: pd.DataFrame) -> dict:
        if data.empty:
            return {'sma50': np.nan, 'sma200': np.nan}
        close = data['Close']
        sma50 = close.rolling(window=self.short_period).mean().iloc[-1] if len(close) >= self.short_period else np.nan
        sma200 = close.rolling(window=self.long_period).mean().iloc[-1] if len(close) >= self.long_period else np.nan
        return {'sma50': sma50, 'sma200': sma200}

class MACDIndicator(Indicator):
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def calculate(self, data: pd.DataFrame) -> dict:
        if data.empty:
            return {'macd': np.nan, 'macd_signal': np.nan}
        close = data['Close']
        ema_fast = close.ewm(span=self.fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=self.signal, adjust=False).mean()
        return {'macd': macd.iloc[-1], 'macd_signal': macd_signal.iloc[-1]}

# Factory to register and create indicators
class IndicatorFactory:
    _indicators = {}

    @classmethod
    def register(cls, name: str, indicator_class: type):
        cls._indicators[name] = indicator_class

    @classmethod
    def create(cls, name: str, params: dict) -> Indicator:
        indicator_class = cls._indicators.get(name)
        if not indicator_class:
            raise ValueError(f"Indicator {name} not registered")
        return indicator_class(**params)

# Register indicators (add more here)
IndicatorFactory.register('rsi', RSIIndicator)
IndicatorFactory.register('sma', SMAIndicator)
IndicatorFactory.register('macd', MACDIndicator)

class TechnicalAnalyzer:
    def __init__(self, config):
        # Handle Pydantic or dict config
        self.config = getattr(config, 'technical', {}) if hasattr(config, 'technical') else config.get('technical', {})
        self.indicator_params = self.config.get('indicators', {})
        self.phase_thresholds = self.config.get('phase_thresholds', {'consolidation_rsi': (40, 60)})

    def fetch_historical_data(self, underlying: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
        try:
            ticker = yf.Ticker(underlying)
            data = ticker.history(period=period, interval=interval)
            if data.empty:
                logger.warning(f"No data for {underlying}")
            return data
        except Exception as e:
            logger.error(f"Fetch failed for {underlying}: {e}")
            return pd.DataFrame()

    def calculate_indicators(self, data: pd.DataFrame) -> dict:
        """Calculate all configured indicators using OO factory (no if/else)."""
        results = {}
        for name in self.indicator_params:
            try:
                indicator = IndicatorFactory.create(name, self.indicator_params[name])
                results.update(indicator.calculate(data))
            except ValueError as e:
                logger.warning(f"Failed to create indicator {name}: {e}")

        return results

    def detect_phases(self, data: pd.DataFrame, indicators: dict) -> str:
        rsi = indicators.get('rsi', 50)
        low, high = self.phase_thresholds['consolidation_rsi']
        if rsi < 30:
            return "accumulation"
        elif rsi > 70:
            return "distribution"
        elif low <= rsi <= high:
            return "consolidation"
        return "unknown"

    def find_order_blocks_support_resistance(self, data: pd.DataFrame) -> dict:
        if data.empty:
            return {'support': np.nan, 'resistance': np.nan, 'order_block': np.nan}
        support = data['Low'].rolling(window=20).min().iloc[-1]
        resistance = data['High'].rolling(window=20).max().iloc[-1]
        order_block = data['Close'].mode()[0] if not data['Close'].mode().empty else data['Close'].iloc[-1]
        return {'support': support, 'resistance': resistance, 'order_block': order_block}

    def get_positive_signal(self, underlying: str, strategy_type: str = 'bullish') -> bool:
        data = self.fetch_historical_data(underlying)
        indicators = self.calculate_indicators(data)
        phase = self.detect_phases(data, indicators)

        if strategy_type == 'bullish':
            return indicators.get('rsi', 50) < 30 and indicators.get('sma_short', 0) > indicators.get('sma_long', 0)
        elif strategy_type == 'bearish':
            return indicators.get('rsi', 50) > 70 and indicators.get('sma_short', 0) < indicators.get('sma_long', 0)
        elif strategy_type == 'neutral':
            return phase == "consolidation"
        return False