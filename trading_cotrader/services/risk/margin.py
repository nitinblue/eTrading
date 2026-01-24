"""
Margin Requirement Estimator

Estimate margin requirements for:
- Current portfolio
- Proposed trades
- What-if scenarios

Note: These are estimates. Actual margin is determined by broker.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MarginType(Enum):
    """Types of margin requirements"""
    REG_T = "reg_t"          # Standard Reg T margin
    PORTFOLIO = "portfolio"   # Portfolio margin (if available)


@dataclass
class MarginRequirement:
    """Margin requirement for a position or trade"""
    initial_margin: Decimal = Decimal('0')      # Required to open
    maintenance_margin: Decimal = Decimal('0')  # Required to maintain
    buying_power_effect: Decimal = Decimal('0') # Impact on buying power
    
    margin_type: MarginType = MarginType.REG_T
    
    # Breakdown
    by_position: Dict[str, Decimal] = field(default_factory=dict)
    
    notes: List[str] = field(default_factory=list)


@dataclass
class MarginAnalysis:
    """Complete margin analysis for portfolio"""
    current_margin_used: Decimal = Decimal('0')
    maintenance_requirement: Decimal = Decimal('0')
    available_margin: Decimal = Decimal('0')
    margin_utilization: float = 0.0
    
    excess_equity: Decimal = Decimal('0')
    sma: Decimal = Decimal('0')  # Special Memorandum Account
    
    # Status
    margin_call_risk: bool = False
    warning_level: bool = False  # > 80% utilization


class MarginEstimator:
    """
    Estimate margin requirements.
    
    Usage:
        estimator = MarginEstimator()
        
        # Get current margin usage
        analysis = estimator.analyze_portfolio(portfolio, positions)
        
        # Estimate margin for new trade
        requirement = estimator.estimate_trade_margin(trade)
        
        # Check if trade is affordable
        can_afford = estimator.can_afford_trade(analysis, requirement)
    """
    
    def __init__(self, margin_type: MarginType = MarginType.REG_T):
        self.margin_type = margin_type
    
    def analyze_portfolio(
        self,
        portfolio,  # Portfolio
        positions: List  # List[Position]
    ) -> MarginAnalysis:
        """Analyze current portfolio margin usage."""
        analysis = MarginAnalysis()
        
        buying_power = getattr(portfolio, 'buying_power', Decimal('0'))
        total_equity = getattr(portfolio, 'total_equity', Decimal('0'))
        
        # Calculate margin used
        for pos in positions:
            margin = self._estimate_position_margin(pos)
            analysis.current_margin_used += margin
        
        # Calculate metrics
        analysis.available_margin = buying_power
        if total_equity > 0:
            analysis.margin_utilization = float(analysis.current_margin_used / total_equity)
        
        analysis.maintenance_requirement = analysis.current_margin_used * Decimal('0.75')
        analysis.excess_equity = total_equity - analysis.maintenance_requirement
        
        # Warnings
        analysis.warning_level = analysis.margin_utilization > 0.8
        analysis.margin_call_risk = analysis.margin_utilization > 0.9
        
        return analysis
    
    def estimate_trade_margin(self, trade) -> MarginRequirement:
        """Estimate margin requirement for a proposed trade."""
        requirement = MarginRequirement(margin_type=self.margin_type)
        
        # TODO: Implement based on trade legs
        # For options:
        # - Short naked puts: 20% of underlying + premium - OTM amount
        # - Short naked calls: Higher of above or underlying price + premium
        # - Spreads: Width of spread - premium received
        # - Covered calls: No additional margin
        
        return requirement
    
    def can_afford_trade(
        self,
        current_analysis: MarginAnalysis,
        trade_margin: MarginRequirement
    ) -> tuple[bool, str]:
        """Check if portfolio can afford a trade."""
        if trade_margin.buying_power_effect > current_analysis.available_margin:
            return False, f"Insufficient buying power: need ${trade_margin.buying_power_effect:,.2f}, have ${current_analysis.available_margin:,.2f}"
        
        new_utilization = float(
            (current_analysis.current_margin_used + trade_margin.initial_margin) /
            (current_analysis.current_margin_used + current_analysis.available_margin)
        )
        
        if new_utilization > 0.9:
            return False, f"Would exceed safe margin utilization: {new_utilization*100:.1f}%"
        
        return True, "Trade is affordable"
    
    def _estimate_position_margin(self, position) -> Decimal:
        """Estimate margin for a single position."""
        symbol = getattr(position, 'symbol', None)
        if not symbol:
            return Decimal('0')
        
        asset_type = getattr(symbol, 'asset_type', None)
        quantity = getattr(position, 'quantity', 0)
        market_value = abs(getattr(position, 'market_value', Decimal('0')))
        
        # Equity positions
        if not asset_type or getattr(asset_type, 'value', '') == 'equity':
            # 50% initial margin for long equity
            return market_value * Decimal('0.5')
        
        # Option positions
        if getattr(asset_type, 'value', '') == 'option':
            if quantity > 0:  # Long options
                return market_value  # Premium is the "margin"
            else:  # Short options
                # Simplified: 20% of underlying equivalent
                underlying_value = market_value * 100  # rough estimate
                return underlying_value * Decimal('0.2')
        
        return market_value * Decimal('0.5')
