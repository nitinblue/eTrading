"""
Value at Risk (VaR) Calculator

Provides multiple methods for calculating portfolio VaR:
- Parametric (variance-covariance)
- Historical simulation
- Monte Carlo simulation

VaR answers: "What's the maximum loss at X% confidence over Y days?"
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Tuple
import logging

# These will be imported from actual domain when integrated
# from core.models.domain import Position, Portfolio

logger = logging.getLogger(__name__)


class VaRMethod(Enum):
    """VaR calculation methods"""
    PARAMETRIC = "parametric"          # Assumes normal distribution
    HISTORICAL = "historical"          # Uses actual historical returns
    MONTE_CARLO = "monte_carlo"        # Simulates many scenarios


@dataclass
class VaRContribution:
    """How much each position contributes to portfolio VaR"""
    position_id: str
    symbol: str
    var_contribution: Decimal
    percent_of_total: float
    marginal_var: Decimal  # VaR if we removed this position


@dataclass
class VaRResult:
    """
    Result of VaR calculation
    
    VaR of $10,000 at 95% confidence means:
    "We are 95% confident the portfolio won't lose more than $10,000 in the given period"
    """
    # Core result
    var_amount: Decimal              # Absolute VaR in dollars
    var_percent: Decimal             # VaR as % of portfolio value
    
    # Parameters used
    confidence_level: float          # e.g., 0.95 for 95%
    horizon_days: int                # e.g., 1 for 1-day VaR
    method: VaRMethod
    
    # Breakdown
    contributions: List[VaRContribution] = field(default_factory=list)
    
    # Context
    portfolio_value: Decimal = Decimal('0')
    calculation_time: datetime = field(default_factory=datetime.utcnow)
    
    # Additional metrics
    expected_shortfall: Optional[Decimal] = None  # CVaR - average loss beyond VaR
    
    def __str__(self) -> str:
        return (
            f"VaR({self.method.value}): ${self.var_amount:,.2f} "
            f"({self.var_percent:.2f}%) at {self.confidence_level*100:.0f}% confidence, "
            f"{self.horizon_days}-day horizon"
        )


class VaRCalculator:
    """
    Calculate Value at Risk for a portfolio
    
    Usage:
        calculator = VaRCalculator(market_data_provider)
        
        # Parametric VaR (fastest, assumes normal distribution)
        result = calculator.calculate_parametric_var(positions, confidence=0.95)
        
        # Historical VaR (uses actual past returns)
        result = calculator.calculate_historical_var(positions, lookback_days=252)
        
        # Monte Carlo VaR (most flexible, slowest)
        result = calculator.calculate_monte_carlo_var(positions, simulations=10000)
    """
    
    def __init__(self, market_data_provider=None):
        """
        Initialize VaR calculator
        
        Args:
            market_data_provider: Provider for historical prices and volatility
        """
        self.market_data = market_data_provider
        self._volatility_cache: Dict[str, float] = {}
        self._correlation_cache: Optional[Dict] = None
    
    def calculate_parametric_var(
        self,
        positions: List,  # List[Position]
        portfolio_value: Decimal,
        confidence: float = 0.95,
        horizon_days: int = 1
    ) -> VaRResult:
        """
        Calculate VaR using parametric (variance-covariance) method.
        
        Assumes returns are normally distributed.
        Fast but may underestimate tail risk.
        
        Args:
            positions: List of Position objects
            portfolio_value: Total portfolio value
            confidence: Confidence level (0.95 = 95%)
            horizon_days: Time horizon in days
            
        Returns:
            VaRResult with VaR amount and breakdown
        """
        # TODO: Full implementation
        # Steps:
        # 1. Get volatility for each position's underlying
        # 2. Get correlation matrix
        # 3. Calculate portfolio variance using weights and correlation
        # 4. Apply confidence level z-score
        # 5. Scale by sqrt(horizon_days)
        
        logger.info(f"Calculating parametric VaR for {len(positions)} positions")
        
        # Placeholder - will implement with actual calculation
        contributions = []
        total_var = Decimal('0')
        
        for pos in positions:
            # Get position details
            # position_value = pos.market_value
            # volatility = self._get_volatility(pos.symbol.ticker)
            # weight = position_value / portfolio_value
            
            # For now, placeholder
            contribution = VaRContribution(
                position_id=getattr(pos, 'id', 'unknown'),
                symbol=getattr(getattr(pos, 'symbol', None), 'ticker', 'UNKNOWN'),
                var_contribution=Decimal('0'),
                percent_of_total=0.0,
                marginal_var=Decimal('0')
            )
            contributions.append(contribution)
        
        return VaRResult(
            var_amount=total_var,
            var_percent=Decimal('0') if portfolio_value == 0 else (total_var / portfolio_value) * 100,
            confidence_level=confidence,
            horizon_days=horizon_days,
            method=VaRMethod.PARAMETRIC,
            contributions=contributions,
            portfolio_value=portfolio_value
        )
    
    def calculate_historical_var(
        self,
        positions: List,  # List[Position]
        portfolio_value: Decimal,
        lookback_days: int = 252,
        confidence: float = 0.95,
        horizon_days: int = 1
    ) -> VaRResult:
        """
        Calculate VaR using historical simulation.
        
        Uses actual historical returns - no distribution assumption.
        More accurate for fat tails but needs good historical data.
        
        Args:
            positions: List of Position objects
            portfolio_value: Total portfolio value
            lookback_days: Days of history to use
            confidence: Confidence level
            horizon_days: Time horizon
            
        Returns:
            VaRResult with VaR amount
        """
        # TODO: Full implementation
        # Steps:
        # 1. Get historical returns for each underlying
        # 2. Calculate historical portfolio returns
        # 3. Find the percentile corresponding to confidence level
        
        logger.info(f"Calculating historical VaR using {lookback_days} days of history")
        
        return VaRResult(
            var_amount=Decimal('0'),
            var_percent=Decimal('0'),
            confidence_level=confidence,
            horizon_days=horizon_days,
            method=VaRMethod.HISTORICAL,
            portfolio_value=portfolio_value
        )
    
    def calculate_monte_carlo_var(
        self,
        positions: List,  # List[Position]
        portfolio_value: Decimal,
        simulations: int = 10000,
        confidence: float = 0.95,
        horizon_days: int = 1
    ) -> VaRResult:
        """
        Calculate VaR using Monte Carlo simulation.
        
        Most flexible - can model any return distribution.
        Slowest but most accurate for complex portfolios.
        
        Args:
            positions: List of Position objects
            portfolio_value: Total portfolio value
            simulations: Number of Monte Carlo simulations
            confidence: Confidence level
            horizon_days: Time horizon
            
        Returns:
            VaRResult with VaR amount
        """
        # TODO: Full implementation
        # Steps:
        # 1. Model return distribution for each underlying
        # 2. Generate correlated random returns
        # 3. Calculate portfolio P&L for each simulation
        # 4. Find percentile for VaR
        
        logger.info(f"Calculating Monte Carlo VaR with {simulations} simulations")
        
        return VaRResult(
            var_amount=Decimal('0'),
            var_percent=Decimal('0'),
            confidence_level=confidence,
            horizon_days=horizon_days,
            method=VaRMethod.MONTE_CARLO,
            portfolio_value=portfolio_value
        )
    
    def calculate_expected_shortfall(
        self,
        var_result: VaRResult,
        positions: List
    ) -> Decimal:
        """
        Calculate Expected Shortfall (CVaR) - average loss beyond VaR.
        
        ES/CVaR is more informative than VaR for tail risk.
        If VaR is $10k at 95%, ES might be $15k (average loss in worst 5% of cases).
        
        Args:
            var_result: Previously calculated VaR
            positions: Positions used in VaR calculation
            
        Returns:
            Expected Shortfall amount
        """
        # TODO: Implement based on method used for VaR
        return Decimal('0')
    
    def calculate_incremental_var(
        self,
        current_positions: List,
        proposed_trade,  # Trade
        portfolio_value: Decimal,
        confidence: float = 0.95
    ) -> Tuple[VaRResult, VaRResult, Decimal]:
        """
        Calculate how a proposed trade affects portfolio VaR.
        
        Critical for pre-trade risk assessment.
        
        Args:
            current_positions: Existing positions
            proposed_trade: Trade being considered
            portfolio_value: Current portfolio value
            confidence: Confidence level
            
        Returns:
            Tuple of (VaR before, VaR after, change in VaR)
        """
        # Calculate current VaR
        var_before = self.calculate_parametric_var(
            current_positions, portfolio_value, confidence
        )
        
        # Add proposed trade to positions
        # new_positions = current_positions + trade_to_positions(proposed_trade)
        # var_after = self.calculate_parametric_var(new_positions, new_value, confidence)
        
        # For now, placeholder
        var_after = var_before
        change = Decimal('0')
        
        return var_before, var_after, change
    
    def _get_volatility(self, symbol: str, lookback_days: int = 30) -> float:
        """
        Get annualized volatility for a symbol.
        
        Caches results for efficiency.
        """
        cache_key = f"{symbol}_{lookback_days}"
        
        if cache_key in self._volatility_cache:
            return self._volatility_cache[cache_key]
        
        # TODO: Calculate from market data
        # daily_returns = self.market_data.get_returns(symbol, lookback_days)
        # volatility = daily_returns.std() * sqrt(252)  # Annualize
        
        volatility = 0.25  # Placeholder 25% annualized vol
        self._volatility_cache[cache_key] = volatility
        
        return volatility
    
    def _get_z_score(self, confidence: float) -> float:
        """Get z-score for given confidence level."""
        # Common values
        z_scores = {
            0.90: 1.282,
            0.95: 1.645,
            0.99: 2.326,
        }
        return z_scores.get(confidence, 1.645)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example usage (will work when integrated with actual domain models)
    calculator = VaRCalculator()
    
    # Mock positions for testing
    mock_positions = []
    
    result = calculator.calculate_parametric_var(
        positions=mock_positions,
        portfolio_value=Decimal('100000'),
        confidence=0.95,
        horizon_days=1
    )
    
    print(result)
