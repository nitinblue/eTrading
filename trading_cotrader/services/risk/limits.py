"""
Risk Limits Management

Define, check, and enforce risk limits:
- VaR limits
- Greeks limits
- Concentration limits
- Drawdown limits
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Dict, Optional, Callable, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class LimitType(Enum):
    """Types of risk limits"""
    VAR = "var"
    DELTA = "delta"
    THETA = "theta"
    VEGA = "vega"
    GAMMA = "gamma"
    CONCENTRATION = "concentration"
    DRAWDOWN = "drawdown"
    MAX_LOSS = "max_loss"


class LimitAction(Enum):
    """What to do when limit is breached"""
    ALERT = "alert"           # Just alert
    BLOCK_NEW = "block_new"   # Block new trades
    REDUCE = "reduce"         # Suggest reduction
    LIQUIDATE = "liquidate"   # Force liquidation


@dataclass
class RiskLimit:
    """Definition of a risk limit"""
    name: str
    limit_type: LimitType
    value: Decimal
    
    # Thresholds
    warning_threshold: float = 0.8  # Warn at 80%
    
    # Response
    breach_action: LimitAction = LimitAction.BLOCK_NEW
    
    # Metadata
    description: str = ""
    unit: str = ""  # "$", "%", etc.
    
    def format_value(self) -> str:
        """Format limit value for display."""
        if self.unit == "$":
            return f"${self.value:,.2f}"
        elif self.unit == "%":
            return f"{self.value:.1f}%"
        else:
            return f"{self.value:.2f} {self.unit}".strip()


@dataclass
class LimitBreach:
    """A limit breach or warning"""
    limit: RiskLimit
    current_value: Decimal
    limit_value: Decimal
    utilization: float  # current/limit
    is_breach: bool  # True = breach, False = warning
    action_required: LimitAction
    message: str = ""


@dataclass
class LimitCheckResult:
    """Result of checking all limits"""
    all_clear: bool = True
    breaches: List[LimitBreach] = field(default_factory=list)
    warnings: List[LimitBreach] = field(default_factory=list)
    
    def has_breaches(self) -> bool:
        return len(self.breaches) > 0
    
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0
    
    def summary(self) -> str:
        if self.all_clear:
            return "All limits OK"
        parts = []
        if self.breaches:
            parts.append(f"{len(self.breaches)} breach(es)")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")
        return ", ".join(parts)


# Default risk limits
def get_default_limits(portfolio_value: Decimal) -> List[RiskLimit]:
    """Get default risk limits scaled to portfolio size."""
    return [
        RiskLimit(
            name="Daily VaR (95%)",
            limit_type=LimitType.VAR,
            value=portfolio_value * Decimal('0.03'),  # 3% of portfolio
            description="Maximum 1-day Value at Risk at 95% confidence",
            unit="$",
            breach_action=LimitAction.BLOCK_NEW
        ),
        RiskLimit(
            name="Portfolio Delta",
            limit_type=LimitType.DELTA,
            value=Decimal('100'),  # 100 delta
            description="Maximum net delta exposure",
            unit="delta",
            breach_action=LimitAction.ALERT
        ),
        RiskLimit(
            name="Daily Theta",
            limit_type=LimitType.THETA,
            value=portfolio_value * Decimal('0.001'),  # 0.1% of portfolio
            description="Maximum daily theta (time decay)",
            unit="$",
            breach_action=LimitAction.ALERT
        ),
        RiskLimit(
            name="Vega Exposure",
            limit_type=LimitType.VEGA,
            value=portfolio_value * Decimal('0.01'),  # 1% of portfolio
            description="Maximum vega exposure",
            unit="$",
            breach_action=LimitAction.ALERT
        ),
        RiskLimit(
            name="Max Loss",
            limit_type=LimitType.MAX_LOSS,
            value=portfolio_value * Decimal('0.2'),  # 20% max loss
            description="Maximum theoretical loss",
            unit="$",
            breach_action=LimitAction.REDUCE
        ),
        RiskLimit(
            name="Drawdown",
            limit_type=LimitType.DRAWDOWN,
            value=Decimal('15'),  # 15%
            description="Maximum drawdown from peak",
            unit="%",
            breach_action=LimitAction.REDUCE
        ),
    ]


class RiskLimits:
    """
    Manage and check risk limits.
    
    Usage:
        limits = RiskLimits(portfolio_value=Decimal('100000'))
        
        # Add custom limit
        limits.add_limit(RiskLimit(
            name="Custom Limit",
            limit_type=LimitType.DELTA,
            value=Decimal('50')
        ))
        
        # Check limits against portfolio risk
        result = limits.check_all(portfolio_risk)
        
        if not result.all_clear:
            for breach in result.breaches:
                print(f"BREACH: {breach.message}")
    """
    
    def __init__(
        self,
        portfolio_value: Decimal = Decimal('100000'),
        limits: List[RiskLimit] = None
    ):
        """
        Initialize risk limits.
        
        Args:
            portfolio_value: Portfolio value for scaling limits
            limits: Custom limits (defaults to standard limits)
        """
        self.portfolio_value = portfolio_value
        self.limits = limits or get_default_limits(portfolio_value)
    
    def add_limit(self, limit: RiskLimit):
        """Add a risk limit."""
        self.limits.append(limit)
    
    def remove_limit(self, name: str):
        """Remove a risk limit by name."""
        self.limits = [l for l in self.limits if l.name != name]
    
    def update_limit(self, name: str, new_value: Decimal):
        """Update a limit value."""
        for limit in self.limits:
            if limit.name == name:
                limit.value = new_value
                return
    
    def check_all(self, portfolio_risk) -> LimitCheckResult:
        """
        Check all limits against portfolio risk.
        
        Args:
            portfolio_risk: PortfolioRisk object
            
        Returns:
            LimitCheckResult with any breaches/warnings
        """
        result = LimitCheckResult()
        
        for limit in self.limits:
            breach = self._check_limit(limit, portfolio_risk)
            if breach:
                if breach.is_breach:
                    result.breaches.append(breach)
                else:
                    result.warnings.append(breach)
        
        result.all_clear = len(result.breaches) == 0
        return result
    
    def check_with_trade(
        self,
        portfolio_risk,
        trade_impact  # RiskImpact
    ) -> LimitCheckResult:
        """
        Check if limits would be breached after a trade.
        
        Args:
            portfolio_risk: Current portfolio risk
            trade_impact: Impact of proposed trade
            
        Returns:
            LimitCheckResult for post-trade state
        """
        # TODO: Apply trade impact and recheck
        return self.check_all(portfolio_risk)
    
    def _check_limit(self, limit: RiskLimit, portfolio_risk) -> Optional[LimitBreach]:
        """Check a single limit."""
        current_value = self._get_metric_value(limit.limit_type, portfolio_risk)
        
        if current_value is None:
            return None
        
        utilization = float(abs(current_value) / limit.value) if limit.value != 0 else 0
        
        if utilization >= 1.0:
            # Breach
            return LimitBreach(
                limit=limit,
                current_value=current_value,
                limit_value=limit.value,
                utilization=utilization,
                is_breach=True,
                action_required=limit.breach_action,
                message=f"{limit.name} BREACHED: {self._format_value(current_value, limit.unit)} vs limit {limit.format_value()}"
            )
        elif utilization >= limit.warning_threshold:
            # Warning
            return LimitBreach(
                limit=limit,
                current_value=current_value,
                limit_value=limit.value,
                utilization=utilization,
                is_breach=False,
                action_required=LimitAction.ALERT,
                message=f"{limit.name} WARNING: {utilization*100:.0f}% of limit"
            )
        
        return None
    
    def _get_metric_value(self, limit_type: LimitType, portfolio_risk) -> Optional[Decimal]:
        """Get the current value for a limit type."""
        if limit_type == LimitType.VAR:
            var = getattr(portfolio_risk, 'var_1d_95', None)
            return var.var_amount if var else None
        
        greeks = getattr(portfolio_risk, 'greeks', None)
        if greeks:
            if limit_type == LimitType.DELTA:
                return abs(getattr(greeks, 'delta_dollars', Decimal('0')))
            elif limit_type == LimitType.THETA:
                return abs(getattr(greeks, 'theta_daily', Decimal('0')))
            elif limit_type == LimitType.VEGA:
                return abs(getattr(greeks, 'vega_dollars', Decimal('0')))
        
        if limit_type == LimitType.MAX_LOSS:
            return getattr(portfolio_risk, 'max_loss_all_positions', Decimal('0'))
        
        return None
    
    def _format_value(self, value: Decimal, unit: str) -> str:
        """Format a value for display."""
        if unit == "$":
            return f"${value:,.2f}"
        elif unit == "%":
            return f"{value:.1f}%"
        return f"{value:.2f}"
    
    def get_limit_status(self) -> List[Dict]:
        """Get status of all limits (for display)."""
        # Would need portfolio_risk to calculate current values
        return [
            {
                'name': limit.name,
                'type': limit.limit_type.value,
                'limit': limit.format_value(),
                'description': limit.description
            }
            for limit in self.limits
        ]


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Create limits for $100k portfolio
    limits = RiskLimits(portfolio_value=Decimal('100000'))
    
    print("Configured Risk Limits:")
    for status in limits.get_limit_status():
        print(f"  {status['name']}: {status['limit']}")
