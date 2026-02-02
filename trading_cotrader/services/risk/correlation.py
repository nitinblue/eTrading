"""
Correlation Analysis

Analyze correlation between positions to:
- Avoid concentrated correlated risk
- Identify diversification opportunities
- Understand portfolio behavior under stress
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging

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
    
    def get_correlation(self, sym1: str, sym2: str) -> Optional[float]:
        """Get correlation between two symbols."""
        if sym1 == sym2:
            return 1.0
        key = (min(sym1, sym2), max(sym1, sym2))
        return self.matrix.get(key)
    
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


class CorrelationAnalyzer:
    """
    Analyze correlations between portfolio positions.
    
    Usage:
        analyzer = CorrelationAnalyzer(market_data)
        
        # Get correlation matrix
        matrix = analyzer.calculate_correlation_matrix(['AAPL', 'MSFT', 'GOOGL'])
        
        # Find correlated positions
        pairs = analyzer.find_correlated_positions(positions, threshold=0.7)
        
        # Get diversification score
        score = analyzer.diversification_score(positions)
    """
    
    def __init__(self, market_data_provider=None):
        """
        Initialize analyzer.
        
        Args:
            market_data_provider: Provider for historical price data
        """
        self.market_data = market_data_provider
        self._correlation_cache: Dict[str, CorrelationMatrix] = {}
    
    def calculate_correlation_matrix(
        self,
        symbols: List[str],
        lookback_days: int = 60
    ) -> CorrelationMatrix:
        """
        Calculate correlation matrix for a set of symbols.
        
        Args:
            symbols: List of ticker symbols
            lookback_days: Number of days of history to use
            
        Returns:
            CorrelationMatrix object
        """
        logger.info(f"Calculating correlation matrix for {len(symbols)} symbols")
        
        # Check cache
        cache_key = f"{','.join(sorted(symbols))}_{lookback_days}"
        if cache_key in self._correlation_cache:
            cached = self._correlation_cache[cache_key]
            # Check if still fresh (within 1 day)
            age = (datetime.utcnow() - cached.calculation_date).days
            if age < 1:
                return cached
        
        # TODO: Full implementation
        # 1. Get historical returns for each symbol
        # 2. Calculate pairwise correlations
        # 3. Build matrix
        
        matrix = {}
        for i, sym1 in enumerate(symbols):
            for sym2 in symbols[i+1:]:
                # Placeholder - would calculate from returns
                corr = self._estimate_correlation(sym1, sym2)
                key = (min(sym1, sym2), max(sym1, sym2))
                matrix[key] = corr
        
        result = CorrelationMatrix(
            symbols=symbols,
            matrix=matrix,
            lookback_days=lookback_days
        )
        
        self._correlation_cache[cache_key] = result
        return result
    
    def find_correlated_positions(
        self,
        positions: List,  # List[Position]
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
        # Get unique underlyings
        underlyings = list(set(
            getattr(getattr(p, 'symbol', None), 'ticker', 'UNKNOWN')
            for p in positions
        ))
        
        if len(underlyings) < 2:
            return []
        
        # Get correlation matrix
        matrix = self.calculate_correlation_matrix(underlyings)
        
        # Find correlated pairs
        pairs = []
        position_values = {}
        for pos in positions:
            ticker = getattr(getattr(pos, 'symbol', None), 'ticker', 'UNKNOWN')
            value = abs(getattr(pos, 'market_value', Decimal('0')))
            position_values[ticker] = position_values.get(ticker, Decimal('0')) + value
        
        for i, sym1 in enumerate(underlyings):
            for sym2 in underlyings[i+1:]:
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
        
        # Sort by combined exposure
        pairs.sort(key=lambda x: abs(x.correlation) * float(x.combined_exposure), reverse=True)
        return pairs
    
    def diversification_score(
        self,
        positions: List,  # List[Position]
        portfolio_value: Decimal = Decimal('0')
    ) -> float:
        """
        Calculate portfolio diversification score.
        
        Score is 0-1 where:
        - 0 = Highly concentrated/correlated
        - 1 = Perfectly diversified
        
        Args:
            positions: List of Position objects
            portfolio_value: Total portfolio value
            
        Returns:
            Diversification score (0-1)
        """
        if len(positions) < 2:
            return 0.0
        
        # Get underlyings and weights
        underlyings = {}
        for pos in positions:
            ticker = getattr(getattr(pos, 'symbol', None), 'ticker', 'UNKNOWN')
            value = abs(getattr(pos, 'market_value', Decimal('0')))
            underlyings[ticker] = underlyings.get(ticker, Decimal('0')) + value
        
        if len(underlyings) < 2:
            return 0.0
        
        # Calculate weights
        total = sum(underlyings.values())
        if total == 0:
            return 0.0
        
        weights = {k: float(v / total) for k, v in underlyings.items()}
        
        # Get correlation matrix
        symbols = list(underlyings.keys())
        matrix = self.calculate_correlation_matrix(symbols)
        
        # Calculate weighted average correlation
        total_weighted_corr = 0.0
        total_weight = 0.0
        
        for i, sym1 in enumerate(symbols):
            for sym2 in symbols[i+1:]:
                corr = matrix.get_correlation(sym1, sym2)
                if corr is not None:
                    weight = weights[sym1] * weights[sym2]
                    total_weighted_corr += abs(corr) * weight
                    total_weight += weight
        
        if total_weight == 0:
            return 1.0
        
        avg_correlation = total_weighted_corr / total_weight
        
        # Diversification score is inverse of correlation
        score = 1.0 - avg_correlation
        
        # Adjust for number of positions (more is better, to a point)
        position_bonus = min(len(underlyings) / 10, 0.2)  # Max 0.2 bonus
        
        return min(score + position_bonus, 1.0)
    
    def correlation_with_portfolio(
        self,
        new_symbol: str,
        positions: List,
        portfolio_value: Decimal
    ) -> float:
        """
        Calculate how a new symbol correlates with existing portfolio.
        
        Useful for pre-trade analysis.
        
        Args:
            new_symbol: Symbol being considered
            positions: Existing positions
            portfolio_value: Total portfolio value
            
        Returns:
            Weighted average correlation with portfolio (-1 to 1)
        """
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
        
        # Get correlations
        symbols = list(underlyings.keys()) + [new_symbol]
        matrix = self.calculate_correlation_matrix(symbols)
        
        # Weighted average correlation
        weighted_corr = 0.0
        for sym, weight in weights.items():
            corr = matrix.get_correlation(new_symbol, sym)
            if corr is not None:
                weighted_corr += corr * weight
        
        return weighted_corr
    
    def _estimate_correlation(self, sym1: str, sym2: str) -> float:
        """
        Estimate correlation between two symbols.
        
        Placeholder - would use actual historical data.
        """
        # Known correlations (rough estimates)
        known_correlations = {
            ('AAPL', 'MSFT'): 0.8,
            ('AAPL', 'GOOGL'): 0.7,
            ('MSFT', 'GOOGL'): 0.75,
            ('SPY', 'QQQ'): 0.9,
            ('SPY', 'IWM'): 0.85,
            ('QQQ', 'IWM'): 0.75,
            ('GLD', 'SPY'): -0.1,
            ('TLT', 'SPY'): -0.3,
        }
        
        key = (min(sym1, sym2), max(sym1, sym2))
        if key in known_correlations:
            return known_correlations[key]
        
        # Default: moderate correlation for equities
        return 0.5


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    analyzer = CorrelationAnalyzer()
    
    # Calculate correlation matrix
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'SPY']
    matrix = analyzer.calculate_correlation_matrix(symbols)
    
    print("Correlation Matrix:")
    for (s1, s2), corr in matrix.matrix.items():
        print(f"  {s1} - {s2}: {corr:.2f}")
