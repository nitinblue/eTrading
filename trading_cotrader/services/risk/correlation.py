"""
Correlation Analysis

Analyze correlation between positions to:
- Avoid concentrated correlated risk
- Identify diversification opportunities
- Understand portfolio behavior under stress

Uses yfinance for real historical return data with 1-day caching.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CorrelatedPair:
    """A pair of correlated positions/underlyings"""
    symbol_a: str
    symbol_b: str
    correlation: float  # -1 to 1
    combined_exposure: Decimal  # Combined $ exposure
    combined_percent: float  # Combined % of portfolio

    def is_highly_correlated(self, threshold: float = 0.7) -> bool:
        return abs(self.correlation) >= threshold

    def is_diversifying(self) -> bool:
        return self.correlation < -0.3


@dataclass
class CorrelationMatrix:
    """Correlation matrix for a set of underlyings"""
    symbols: List[str]
    matrix: Dict[Tuple[str, str], float]  # (sym1, sym2) -> correlation
    calculation_date: datetime = field(default_factory=datetime.utcnow)
    lookback_days: int = 60

    # The underlying numpy arrays (for VaR calculations)
    returns_data: Optional[np.ndarray] = field(default=None, repr=False)
    covariance_matrix: Optional[np.ndarray] = field(default=None, repr=False)
    volatilities: Optional[Dict[str, float]] = field(default=None, repr=False)

    def get_correlation(self, sym1: str, sym2: str) -> Optional[float]:
        """Get correlation between two symbols."""
        if sym1 == sym2:
            return 1.0
        key = (min(sym1, sym2), max(sym1, sym2))
        return self.matrix.get(key)

    def get_covariance(self, sym1: str, sym2: str) -> Optional[float]:
        """Get covariance between two symbols from the covariance matrix."""
        if self.covariance_matrix is None or not self.symbols:
            return None
        try:
            i = self.symbols.index(sym1)
            j = self.symbols.index(sym2)
            return float(self.covariance_matrix[i, j])
        except (ValueError, IndexError):
            return None

    def get_volatility(self, symbol: str) -> Optional[float]:
        """Get annualized volatility for a symbol."""
        if self.volatilities:
            return self.volatilities.get(symbol)
        return None

    def get_most_correlated(self, symbol: str, n: int = 5) -> List[Tuple[str, float]]:
        """Get n most correlated symbols to the given symbol."""
        correlations = []
        for other in self.symbols:
            if other != symbol:
                corr = self.get_correlation(symbol, other)
                if corr is not None:
                    correlations.append((other, corr))

        correlations.sort(key=lambda x: abs(x[1]), reverse=True)
        return correlations[:n]

    def get_least_correlated(self, symbol: str, n: int = 5) -> List[Tuple[str, float]]:
        """Get n least correlated (most diversifying) symbols."""
        correlations = []
        for other in self.symbols:
            if other != symbol:
                corr = self.get_correlation(symbol, other)
                if corr is not None:
                    correlations.append((other, corr))

        correlations.sort(key=lambda x: x[1])
        return correlations[:n]


def _fetch_returns(symbols: List[str], lookback_days: int = 252) -> Optional[Dict[str, np.ndarray]]:
    """
    Fetch daily log returns from yfinance.

    Returns dict of {symbol: np.array of daily log returns} or None on failure.
    """
    try:
        import yfinance as yf
    except ImportError:
        logger.warning("yfinance not installed — cannot fetch historical returns")
        return None

    if not symbols:
        return None

    try:
        end = datetime.utcnow()
        # Fetch extra days to account for weekends/holidays
        start = end - timedelta(days=int(lookback_days * 1.5))

        # Download all at once for efficiency
        data = yf.download(
            symbols,
            start=start.strftime('%Y-%m-%d'),
            end=end.strftime('%Y-%m-%d'),
            progress=False,
            auto_adjust=True
        )

        if data.empty:
            logger.warning(f"No data returned from yfinance for {symbols}")
            return None

        # yfinance always returns multi-level columns: (Price, Ticker)
        close = data['Close']

        # close may be a Series (single symbol, old yfinance) or DataFrame
        import pandas as pd
        returns = {}

        if isinstance(close, pd.Series):
            # Old yfinance format: single symbol returns a Series
            prices = close.dropna().values.flatten()
            if len(prices) < 20:
                logger.warning(f"Insufficient data for {symbols[0]}: {len(prices)} days")
                return None
            log_ret = np.diff(np.log(prices))
            log_ret = log_ret[-lookback_days:] if len(log_ret) > lookback_days else log_ret
            returns[symbols[0]] = log_ret
        else:
            # DataFrame — iterate columns (works for single or multiple symbols)
            for sym in symbols:
                if sym in close.columns:
                    prices = close[sym].dropna().values.flatten()
                    if len(prices) < 20:
                        logger.warning(f"Insufficient data for {sym}: {len(prices)} days")
                        continue
                    log_ret = np.diff(np.log(prices))
                    log_ret = log_ret[-lookback_days:] if len(log_ret) > lookback_days else log_ret
                    returns[sym] = log_ret
                else:
                    logger.warning(f"No data for {sym}")

        return returns if returns else None
    except Exception as e:
        logger.error(f"Error fetching returns from yfinance: {e}")
        return None


class CorrelationAnalyzer:
    """
    Analyze correlations between portfolio positions.

    Uses real yfinance historical data with 1-day caching.
    Falls back to hardcoded estimates if yfinance unavailable.

    Usage:
        analyzer = CorrelationAnalyzer()

        # Get correlation matrix
        matrix = analyzer.calculate_correlation_matrix(['AAPL', 'MSFT', 'GOOGL'])

        # Find correlated positions
        pairs = analyzer.find_correlated_positions(positions, threshold=0.7)

        # Get diversification score
        score = analyzer.diversification_score(positions)
    """

    def __init__(self, market_data_provider=None):
        self.market_data = market_data_provider
        self._correlation_cache: Dict[str, CorrelationMatrix] = {}

    def calculate_correlation_matrix(
        self,
        symbols: List[str],
        lookback_days: int = 252
    ) -> CorrelationMatrix:
        """
        Calculate correlation matrix for a set of symbols using real historical data.

        Args:
            symbols: List of ticker symbols
            lookback_days: Number of trading days of history to use (default 252 = 1 year)

        Returns:
            CorrelationMatrix with correlation pairs, covariance matrix, and volatilities
        """
        logger.info(f"Calculating correlation matrix for {len(symbols)} symbols")

        # Check cache (valid for 1 day)
        cache_key = f"{','.join(sorted(symbols))}_{lookback_days}"
        if cache_key in self._correlation_cache:
            cached = self._correlation_cache[cache_key]
            age = (datetime.utcnow() - cached.calculation_date).total_seconds()
            if age < 86400:  # 24 hours
                return cached

        # Fetch real returns from yfinance
        returns_data = _fetch_returns(symbols, lookback_days)

        if returns_data and len(returns_data) >= 1:
            result = self._build_matrix_from_returns(symbols, returns_data, lookback_days)
        else:
            # Fallback to hardcoded estimates
            logger.warning("Using hardcoded correlation estimates (yfinance unavailable)")
            result = self._build_matrix_from_estimates(symbols, lookback_days)

        self._correlation_cache[cache_key] = result
        return result

    def _build_matrix_from_returns(
        self,
        symbols: List[str],
        returns_data: Dict[str, np.ndarray],
        lookback_days: int
    ) -> CorrelationMatrix:
        """Build correlation matrix from actual return data."""
        # Filter to symbols we have data for
        valid_symbols = [s for s in symbols if s in returns_data]

        if len(valid_symbols) == 0:
            return self._build_matrix_from_estimates(symbols, lookback_days)

        # Align return arrays to same length
        min_len = min(len(returns_data[s]) for s in valid_symbols)
        if min_len < 5:
            logger.warning(f"Insufficient aligned data ({min_len} days), using estimates")
            return self._build_matrix_from_estimates(symbols, lookback_days)
        aligned = np.column_stack([returns_data[s][-min_len:] for s in valid_symbols])

        # Compute covariance and correlation matrices
        # Daily covariance matrix
        cov_matrix = np.cov(aligned, rowvar=False)

        # Handle single symbol case
        if len(valid_symbols) == 1:
            cov_matrix = np.array([[cov_matrix]]) if cov_matrix.ndim == 0 else cov_matrix.reshape(1, 1)

        # Compute correlation from covariance
        std_devs = np.sqrt(np.diag(cov_matrix))
        # Avoid division by zero
        std_devs[std_devs == 0] = 1e-10
        corr_matrix = cov_matrix / np.outer(std_devs, std_devs)

        # Build pairwise correlation dict
        matrix = {}
        for i, sym1 in enumerate(valid_symbols):
            for j in range(i + 1, len(valid_symbols)):
                sym2 = valid_symbols[j]
                key = (min(sym1, sym2), max(sym1, sym2))
                matrix[key] = float(corr_matrix[i, j])

        # For symbols we don't have data for, use estimates
        for sym in symbols:
            if sym not in valid_symbols:
                for other in valid_symbols:
                    key = (min(sym, other), max(sym, other))
                    if key not in matrix:
                        matrix[key] = self._estimate_correlation(sym, other)

        # Annualized volatilities (daily std * sqrt(252))
        volatilities = {}
        for i, sym in enumerate(valid_symbols):
            volatilities[sym] = float(std_devs[i] * np.sqrt(252))

        return CorrelationMatrix(
            symbols=symbols,
            matrix=matrix,
            lookback_days=lookback_days,
            returns_data=aligned,
            covariance_matrix=cov_matrix,
            volatilities=volatilities
        )

    def _build_matrix_from_estimates(
        self,
        symbols: List[str],
        lookback_days: int
    ) -> CorrelationMatrix:
        """Build matrix from hardcoded estimates (fallback)."""
        matrix = {}
        for i, sym1 in enumerate(symbols):
            for sym2 in symbols[i + 1:]:
                corr = self._estimate_correlation(sym1, sym2)
                key = (min(sym1, sym2), max(sym1, sym2))
                matrix[key] = corr

        # Default 25% annualized vol for all
        volatilities = {sym: 0.25 for sym in symbols}

        return CorrelationMatrix(
            symbols=symbols,
            matrix=matrix,
            lookback_days=lookback_days,
            volatilities=volatilities
        )

    def find_correlated_positions(
        self,
        positions: List,
        threshold: float = 0.7,
        portfolio_value: Decimal = Decimal('0')
    ) -> List[CorrelatedPair]:
        """
        Find highly correlated position pairs.

        Args:
            positions: List of Position objects
            threshold: Correlation threshold (0-1)
            portfolio_value: Total portfolio value for % calculation

        Returns:
            List of CorrelatedPair objects
        """
        underlyings = list(set(
            getattr(getattr(p, 'symbol', None), 'ticker', 'UNKNOWN')
            for p in positions
        ))

        if len(underlyings) < 2:
            return []

        matrix = self.calculate_correlation_matrix(underlyings)

        pairs = []
        position_values = {}
        for pos in positions:
            ticker = getattr(getattr(pos, 'symbol', None), 'ticker', 'UNKNOWN')
            value = abs(getattr(pos, 'market_value', Decimal('0')))
            position_values[ticker] = position_values.get(ticker, Decimal('0')) + value

        for i, sym1 in enumerate(underlyings):
            for sym2 in underlyings[i + 1:]:
                corr = matrix.get_correlation(sym1, sym2)
                if corr and abs(corr) >= threshold:
                    combined = position_values.get(sym1, Decimal('0')) + position_values.get(sym2, Decimal('0'))
                    pct = float(combined / portfolio_value) if portfolio_value > 0 else 0

                    pairs.append(CorrelatedPair(
                        symbol_a=sym1,
                        symbol_b=sym2,
                        correlation=corr,
                        combined_exposure=combined,
                        combined_percent=pct
                    ))

        pairs.sort(key=lambda x: abs(x.correlation) * float(x.combined_exposure), reverse=True)
        return pairs

    def diversification_score(
        self,
        positions: List,
        portfolio_value: Decimal = Decimal('0')
    ) -> float:
        """
        Calculate portfolio diversification score (0-1, higher is better).
        """
        if len(positions) < 2:
            return 0.0

        underlyings = {}
        for pos in positions:
            ticker = getattr(getattr(pos, 'symbol', None), 'ticker', 'UNKNOWN')
            value = abs(getattr(pos, 'market_value', Decimal('0')))
            underlyings[ticker] = underlyings.get(ticker, Decimal('0')) + value

        if len(underlyings) < 2:
            return 0.0

        total = sum(underlyings.values())
        if total == 0:
            return 0.0

        weights = {k: float(v / total) for k, v in underlyings.items()}

        symbols = list(underlyings.keys())
        matrix = self.calculate_correlation_matrix(symbols)

        total_weighted_corr = 0.0
        total_weight = 0.0

        for i, sym1 in enumerate(symbols):
            for sym2 in symbols[i + 1:]:
                corr = matrix.get_correlation(sym1, sym2)
                if corr is not None:
                    weight = weights[sym1] * weights[sym2]
                    total_weighted_corr += abs(corr) * weight
                    total_weight += weight

        if total_weight == 0:
            return 1.0

        avg_correlation = total_weighted_corr / total_weight
        score = 1.0 - avg_correlation
        position_bonus = min(len(underlyings) / 10, 0.2)

        return min(score + position_bonus, 1.0)

    def correlation_with_portfolio(
        self,
        new_symbol: str,
        positions: List,
        portfolio_value: Decimal
    ) -> float:
        """Calculate how a new symbol correlates with existing portfolio."""
        underlyings = {}
        for pos in positions:
            ticker = getattr(getattr(pos, 'symbol', None), 'ticker', 'UNKNOWN')
            if ticker != new_symbol:
                value = abs(getattr(pos, 'market_value', Decimal('0')))
                underlyings[ticker] = underlyings.get(ticker, Decimal('0')) + value

        if not underlyings:
            return 0.0

        total = sum(underlyings.values())
        if total == 0:
            return 0.0

        weights = {k: float(v / total) for k, v in underlyings.items()}

        symbols = list(underlyings.keys()) + [new_symbol]
        matrix = self.calculate_correlation_matrix(symbols)

        weighted_corr = 0.0
        for sym, weight in weights.items():
            corr = matrix.get_correlation(new_symbol, sym)
            if corr is not None:
                weighted_corr += corr * weight

        return weighted_corr

    def _estimate_correlation(self, sym1: str, sym2: str) -> float:
        """
        Fallback correlation estimates when yfinance data unavailable.
        """
        known_correlations = {
            ('AAPL', 'MSFT'): 0.8,
            ('AAPL', 'GOOGL'): 0.7,
            ('MSFT', 'GOOGL'): 0.75,
            ('SPY', 'QQQ'): 0.9,
            ('SPY', 'IWM'): 0.85,
            ('QQQ', 'IWM'): 0.75,
            ('GLD', 'SPY'): -0.1,
            ('TLT', 'SPY'): -0.3,
            ('NVDA', 'QQQ'): 0.8,
            ('NVDA', 'SPY'): 0.7,
            ('NVDA', 'AAPL'): 0.65,
            ('NVDA', 'MSFT'): 0.7,
        }

        key = (min(sym1, sym2), max(sym1, sym2))
        if key in known_correlations:
            return known_correlations[key]

        return 0.5
