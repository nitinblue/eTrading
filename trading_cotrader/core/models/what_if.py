"""
What-If Scenario Object

A What-If is a FIRST-CLASS OBJECT that:
- Can be created with parameters
- Stored in UI grid cells
- Re-evaluates when parameters change (reactive)
- Can be compared with other What-Ifs
- Answers "Should I take this trade?"

This is the core concept for pre-trade risk management.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Optional, Callable, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class WhatIfStatus(Enum):
    """Status of what-if evaluation"""
    PENDING = "pending"           # Not yet evaluated
    PASSED = "passed"             # Passes all checks
    WARNING = "warning"           # Passes but has warnings
    BLOCKED = "blocked"           # Fails risk checks
    ERROR = "error"               # Evaluation error


@dataclass
class RiskCheckResult:
    """Result of a single risk check"""
    check_name: str
    passed: bool
    current_value: Any
    limit_value: Any
    message: str
    severity: str = "info"  # info, warning, error


@dataclass
class WhatIfInputs:
    """
    Inputs to a What-If scenario.
    
    These are the parameters that can be changed.
    When changed, the What-If re-evaluates.
    """
    # The proposed trade
    underlying: str = ""
    strategy_type: str = ""
    
    # Legs (simplified representation)
    legs: List[Dict] = field(default_factory=list)
    # Each leg: {type: 'put'/'call', strike: 100, expiration: date, quantity: -1, action: 'sell'}
    
    # Premium
    net_credit: Decimal = Decimal('0')  # Positive = credit, negative = debit
    
    # Market assumptions (can be overridden)
    underlying_price: Optional[Decimal] = None
    implied_volatility: Optional[float] = None
    days_to_expiry: Optional[int] = None
    
    # What price are we assuming for the trade?
    assumed_fill_price: Optional[Decimal] = None


@dataclass
class WhatIfOutputs:
    """
    Computed outputs of a What-If scenario.
    
    These are calculated from inputs + current portfolio state.
    They update reactively when inputs change.
    """
    # Trade metrics
    max_profit: Decimal = Decimal('0')
    max_loss: Decimal = Decimal('0')
    breakeven_prices: List[Decimal] = field(default_factory=list)
    
    # Probability metrics
    probability_of_profit: float = 0.0
    probability_max_profit: float = 0.0
    probability_max_loss: float = 0.0
    expected_value: Decimal = Decimal('0')
    
    # Greeks of the trade
    trade_delta: Decimal = Decimal('0')
    trade_gamma: Decimal = Decimal('0')
    trade_theta: Decimal = Decimal('0')
    trade_vega: Decimal = Decimal('0')
    
    # Portfolio impact
    portfolio_delta_before: Decimal = Decimal('0')
    portfolio_delta_after: Decimal = Decimal('0')
    portfolio_var_before: Decimal = Decimal('0')
    portfolio_var_after: Decimal = Decimal('0')
    var_impact: Decimal = Decimal('0')
    var_impact_percent: float = 0.0
    
    # Concentration impact
    underlying_exposure_before: float = 0.0
    underlying_exposure_after: float = 0.0
    strategy_exposure_before: float = 0.0
    strategy_exposure_after: float = 0.0
    
    # Correlation with existing positions
    correlation_with_portfolio: float = 0.0
    correlated_positions: List[str] = field(default_factory=list)
    
    # Margin impact
    margin_required: Decimal = Decimal('0')
    buying_power_before: Decimal = Decimal('0')
    buying_power_after: Decimal = Decimal('0')
    margin_utilization_after: float = 0.0
    
    # Risk checks
    risk_checks: List[RiskCheckResult] = field(default_factory=list)
    
    # Overall status
    status: WhatIfStatus = WhatIfStatus.PENDING
    warnings: List[str] = field(default_factory=list)
    blockers: List[str] = field(default_factory=list)
    
    # Timestamps
    evaluated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WhatIfScenario:
    """
    A What-If Scenario object.
    
    This is the core object that traders interact with.
    It combines inputs (changeable) with outputs (computed).
    
    Usage:
        # Create a what-if
        what_if = WhatIfScenario.create_put_credit_spread(
            underlying='SPY',
            short_strike=490,
            long_strike=485,
            expiration=date(2024, 2, 16),
            credit=1.50
        )
        
        # Evaluate against portfolio
        engine.evaluate(what_if, portfolio, positions)
        
        # Check if we should proceed
        if what_if.should_proceed():
            print("Trade is acceptable")
        
        # Change assumption and re-evaluate
        what_if.inputs.underlying_price = Decimal('495')
        engine.evaluate(what_if, portfolio, positions)
        
        # Store in UI grid
        grid['A1'] = what_if
        
        # Compare with another scenario
        if what_if.outputs.expected_value > other_what_if.outputs.expected_value:
            print("This scenario is better")
    """
    
    # Identity
    id: str = ""
    name: str = ""
    description: str = ""
    
    # Inputs and outputs
    inputs: WhatIfInputs = field(default_factory=WhatIfInputs)
    outputs: WhatIfOutputs = field(default_factory=WhatIfOutputs)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    tags: List[str] = field(default_factory=list)
    
    # State
    is_evaluated: bool = False
    is_stale: bool = False  # True if inputs changed since last evaluation
    
    def should_proceed(self) -> tuple[bool, str]:
        """
        Should we proceed with this trade?
        
        Returns:
            Tuple of (should_proceed, reason)
        """
        if not self.is_evaluated:
            return False, "Not yet evaluated"
        
        if self.outputs.status == WhatIfStatus.BLOCKED:
            return False, f"Blocked: {', '.join(self.outputs.blockers)}"
        
        if self.outputs.status == WhatIfStatus.ERROR:
            return False, "Evaluation error"
        
        if self.outputs.status == WhatIfStatus.WARNING:
            return True, f"Proceed with caution: {', '.join(self.outputs.warnings)}"
        
        return True, "All checks passed"
    
    def passes_risk_checks(self) -> bool:
        """Quick check if all risk checks pass."""
        return all(check.passed for check in self.outputs.risk_checks)
    
    def get_failed_checks(self) -> List[RiskCheckResult]:
        """Get list of failed risk checks."""
        return [check for check in self.outputs.risk_checks if not check.passed]
    
    def get_summary(self) -> Dict:
        """Get summary for display."""
        return {
            'name': self.name,
            'underlying': self.inputs.underlying,
            'strategy': self.inputs.strategy_type,
            'credit': float(self.inputs.net_credit),
            'max_profit': float(self.outputs.max_profit),
            'max_loss': float(self.outputs.max_loss),
            'pop': self.outputs.probability_of_profit * 100,
            'ev': float(self.outputs.expected_value),
            'var_impact': float(self.outputs.var_impact),
            'status': self.outputs.status.value,
            'can_proceed': self.should_proceed()[0]
        }
    
    def mark_stale(self):
        """Mark as needing re-evaluation."""
        self.is_stale = True
    
    def to_dict(self) -> Dict:
        """Serialize for storage."""
        return {
            'id': self.id,
            'name': self.name,
            'inputs': {
                'underlying': self.inputs.underlying,
                'strategy_type': self.inputs.strategy_type,
                'legs': self.inputs.legs,
                'net_credit': float(self.inputs.net_credit),
            },
            'outputs': self.get_summary(),
            'created_at': self.created_at.isoformat(),
            'is_evaluated': self.is_evaluated
        }
    
    # =========================================================================
    # Factory Methods for Common Strategies
    # =========================================================================
    
    @classmethod
    def create_put_credit_spread(
        cls,
        underlying: str,
        short_strike: float,
        long_strike: float,
        expiration: datetime,
        credit: float,
        quantity: int = 1,
        name: str = None
    ) -> 'WhatIfScenario':
        """Create a bull put spread what-if."""
        import uuid
        
        if name is None:
            name = f"{underlying} {int(short_strike)}/{int(long_strike)} Put Spread"
        
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            inputs=WhatIfInputs(
                underlying=underlying,
                strategy_type='put_credit_spread',
                legs=[
                    {'type': 'put', 'strike': short_strike, 'expiration': expiration, 'quantity': -quantity, 'action': 'sell'},
                    {'type': 'put', 'strike': long_strike, 'expiration': expiration, 'quantity': quantity, 'action': 'buy'}
                ],
                net_credit=Decimal(str(credit))
            )
        )
    
    @classmethod
    def create_iron_condor(
        cls,
        underlying: str,
        put_long_strike: float,
        put_short_strike: float,
        call_short_strike: float,
        call_long_strike: float,
        expiration: datetime,
        credit: float,
        quantity: int = 1,
        name: str = None
    ) -> 'WhatIfScenario':
        """Create an iron condor what-if."""
        import uuid
        
        if name is None:
            name = f"{underlying} {int(put_short_strike)}/{int(call_short_strike)} IC"
        
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            inputs=WhatIfInputs(
                underlying=underlying,
                strategy_type='iron_condor',
                legs=[
                    {'type': 'put', 'strike': put_long_strike, 'expiration': expiration, 'quantity': quantity, 'action': 'buy'},
                    {'type': 'put', 'strike': put_short_strike, 'expiration': expiration, 'quantity': -quantity, 'action': 'sell'},
                    {'type': 'call', 'strike': call_short_strike, 'expiration': expiration, 'quantity': -quantity, 'action': 'sell'},
                    {'type': 'call', 'strike': call_long_strike, 'expiration': expiration, 'quantity': quantity, 'action': 'buy'}
                ],
                net_credit=Decimal(str(credit))
            )
        )
    
    @classmethod
    def create_short_put(
        cls,
        underlying: str,
        strike: float,
        expiration: datetime,
        credit: float,
        quantity: int = 1,
        name: str = None
    ) -> 'WhatIfScenario':
        """Create a short put what-if."""
        import uuid
        
        if name is None:
            name = f"{underlying} {int(strike)} Short Put"
        
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            inputs=WhatIfInputs(
                underlying=underlying,
                strategy_type='short_put',
                legs=[
                    {'type': 'put', 'strike': strike, 'expiration': expiration, 'quantity': -quantity, 'action': 'sell'}
                ],
                net_credit=Decimal(str(credit))
            )
        )


# =============================================================================
# What-If Evaluation Engine
# =============================================================================

class WhatIfEngine:
    """
    Engine for evaluating What-If scenarios.
    
    Usage:
        engine = WhatIfEngine(risk_config, pricing_service, risk_service)
        
        # Create and evaluate
        what_if = WhatIfScenario.create_put_credit_spread(...)
        engine.evaluate(what_if, portfolio, positions)
        
        # Check results
        if what_if.should_proceed()[0]:
            print("Trade is acceptable")
    """
    
    def __init__(
        self,
        risk_config=None,
        pricing_service=None,
        risk_service=None,
        market_data=None
    ):
        self.risk_config = risk_config
        self.pricing = pricing_service
        self.risk = risk_service
        self.market_data = market_data
    
    def evaluate(
        self,
        what_if: WhatIfScenario,
        portfolio,  # Portfolio
        positions: List,  # List[Position]
        market_data: Dict = None
    ) -> WhatIfScenario:
        """
        Evaluate a what-if scenario against portfolio.
        
        This is the main evaluation method that:
        1. Calculates trade metrics (max profit, POP, etc.)
        2. Calculates portfolio impact (VaR, Greeks, concentration)
        3. Runs all risk checks
        4. Sets status and warnings
        
        Args:
            what_if: WhatIfScenario to evaluate
            portfolio: Current portfolio
            positions: Current positions
            market_data: Optional market data override
            
        Returns:
            The same WhatIfScenario with outputs populated
        """
        logger.info(f"Evaluating what-if: {what_if.name}")
        
        try:
            outputs = what_if.outputs
            inputs = what_if.inputs
            
            # Get market data
            spot = float(inputs.underlying_price or self._get_price(inputs.underlying))
            vol = inputs.implied_volatility or self._get_iv(inputs.underlying)
            dte = inputs.days_to_expiry or self._get_dte(inputs.legs)
            
            # 1. Calculate trade metrics
            self._calculate_trade_metrics(what_if, spot, vol, dte)
            
            # 2. Calculate Greeks
            self._calculate_trade_greeks(what_if, spot, vol, dte)
            
            # 3. Calculate portfolio impact
            self._calculate_portfolio_impact(what_if, portfolio, positions)
            
            # 4. Calculate margin
            self._calculate_margin_impact(what_if, portfolio)
            
            # 5. Run risk checks
            self._run_risk_checks(what_if, portfolio)
            
            # 6. Determine status
            self._determine_status(what_if)
            
            what_if.is_evaluated = True
            what_if.is_stale = False
            outputs.evaluated_at = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error evaluating what-if: {e}")
            what_if.outputs.status = WhatIfStatus.ERROR
            what_if.outputs.blockers.append(f"Evaluation error: {str(e)}")
        
        return what_if
    
    def _calculate_trade_metrics(self, what_if: WhatIfScenario, spot: float, vol: float, dte: int):
        """Calculate max profit, max loss, POP, EV."""
        outputs = what_if.outputs
        inputs = what_if.inputs
        
        strategy = inputs.strategy_type
        credit = float(inputs.net_credit)
        
        # Calculate based on strategy type
        if strategy == 'put_credit_spread':
            short_strike = next(l['strike'] for l in inputs.legs if l['quantity'] < 0)
            long_strike = next(l['strike'] for l in inputs.legs if l['quantity'] > 0)
            width = short_strike - long_strike
            
            outputs.max_profit = Decimal(str(credit * 100))  # Per contract
            outputs.max_loss = Decimal(str((width - credit) * 100))
            outputs.breakeven_prices = [Decimal(str(short_strike - credit))]
            
        elif strategy == 'iron_condor':
            put_legs = [l for l in inputs.legs if l['type'] == 'put']
            call_legs = [l for l in inputs.legs if l['type'] == 'call']
            
            put_short = next(l['strike'] for l in put_legs if l['quantity'] < 0)
            put_long = next(l['strike'] for l in put_legs if l['quantity'] > 0)
            call_short = next(l['strike'] for l in call_legs if l['quantity'] < 0)
            call_long = next(l['strike'] for l in call_legs if l['quantity'] > 0)
            
            width = max(put_short - put_long, call_long - call_short)
            
            outputs.max_profit = Decimal(str(credit * 100))
            outputs.max_loss = Decimal(str((width - credit) * 100))
            outputs.breakeven_prices = [
                Decimal(str(put_short - credit)),
                Decimal(str(call_short + credit))
            ]
            
        elif strategy == 'short_put':
            strike = inputs.legs[0]['strike']
            outputs.max_profit = Decimal(str(credit * 100))
            outputs.max_loss = Decimal(str((strike - credit) * 100))  # Undefined risk
            outputs.breakeven_prices = [Decimal(str(strike - credit))]
        
        # Calculate probabilities (placeholder - would use pricing service)
        if self.pricing:
            # Use pricing service
            pass
        else:
            # Rough estimates
            outputs.probability_of_profit = 0.70  # Placeholder
            outputs.probability_max_profit = 0.50
            outputs.probability_max_loss = 0.10
        
        # Expected value
        pop = outputs.probability_of_profit
        outputs.expected_value = Decimal(str(
            pop * float(outputs.max_profit) - (1 - pop) * float(outputs.max_loss)
        ))
    
    def _calculate_trade_greeks(self, what_if: WhatIfScenario, spot: float, vol: float, dte: int):
        """Calculate trade Greeks."""
        # Placeholder - would use pricing service
        outputs = what_if.outputs
        outputs.trade_delta = Decimal('5')  # Example: 5 delta for a put spread
        outputs.trade_theta = Decimal('10')  # $10/day theta
        outputs.trade_vega = Decimal('-5')  # Short vega
    
    def _calculate_portfolio_impact(self, what_if: WhatIfScenario, portfolio, positions):
        """Calculate impact on portfolio metrics."""
        outputs = what_if.outputs
        
        # Current portfolio Greeks
        current_delta = sum(
            getattr(getattr(p, 'greeks', None), 'delta', 0) or 0
            for p in positions
        )
        
        outputs.portfolio_delta_before = Decimal(str(current_delta))
        outputs.portfolio_delta_after = outputs.portfolio_delta_before + outputs.trade_delta
        
        # VaR impact (placeholder)
        outputs.portfolio_var_before = Decimal('3000')
        outputs.portfolio_var_after = Decimal('3200')
        outputs.var_impact = outputs.portfolio_var_after - outputs.portfolio_var_before
        
        total_equity = float(getattr(portfolio, 'total_equity', 100000))
        outputs.var_impact_percent = float(outputs.var_impact / Decimal(str(total_equity)) * 100)
        
        # Concentration (placeholder)
        outputs.underlying_exposure_before = 5.0  # 5% in this underlying
        outputs.underlying_exposure_after = 8.0   # Would be 8% after trade
    
    def _calculate_margin_impact(self, what_if: WhatIfScenario, portfolio):
        """Calculate margin requirements."""
        outputs = what_if.outputs
        inputs = what_if.inputs
        
        outputs.buying_power_before = getattr(portfolio, 'buying_power', Decimal('50000'))
        
        # Estimate margin based on strategy
        if inputs.strategy_type in ['put_credit_spread', 'call_credit_spread', 'iron_condor']:
            # Defined risk - margin = max loss
            outputs.margin_required = outputs.max_loss
        else:
            # Undefined risk - estimate
            outputs.margin_required = Decimal('5000')  # Placeholder
        
        outputs.buying_power_after = outputs.buying_power_before - outputs.margin_required
        
        total = float(outputs.buying_power_before)
        if total > 0:
            outputs.margin_utilization_after = float(outputs.margin_required / Decimal(str(total)) * 100)
    
    def _run_risk_checks(self, what_if: WhatIfScenario, portfolio):
        """Run all risk checks from config."""
        outputs = what_if.outputs
        outputs.risk_checks = []
        
        # Load config
        config = self.risk_config
        if not config:
            return
        
        # Check VaR
        max_var = config.var.max_var_percent if hasattr(config, 'var') else 3.0
        total_equity = float(getattr(portfolio, 'total_equity', 100000))
        var_limit = total_equity * max_var / 100
        
        outputs.risk_checks.append(RiskCheckResult(
            check_name="VaR Limit",
            passed=float(outputs.portfolio_var_after) <= var_limit,
            current_value=float(outputs.portfolio_var_after),
            limit_value=var_limit,
            message=f"VaR ${outputs.portfolio_var_after:,.0f} vs limit ${var_limit:,.0f}",
            severity="error" if float(outputs.portfolio_var_after) > var_limit else "info"
        ))
        
        # Check concentration
        max_conc = 20.0  # Default
        if hasattr(config, 'concentration'):
            max_conc = config.concentration.single_underlying.max_percent
        
        outputs.risk_checks.append(RiskCheckResult(
            check_name="Concentration Limit",
            passed=outputs.underlying_exposure_after <= max_conc,
            current_value=outputs.underlying_exposure_after,
            limit_value=max_conc,
            message=f"{outputs.underlying_exposure_after:.1f}% vs limit {max_conc:.0f}%",
            severity="error" if outputs.underlying_exposure_after > max_conc else "info"
        ))
        
        # Check buying power
        min_reserve = 20.0  # 20% reserve
        if hasattr(config, 'margin'):
            min_reserve = config.margin.min_buying_power_reserve
        
        bp_remaining_pct = float(outputs.buying_power_after / outputs.buying_power_before * 100)
        outputs.risk_checks.append(RiskCheckResult(
            check_name="Buying Power Reserve",
            passed=bp_remaining_pct >= min_reserve,
            current_value=bp_remaining_pct,
            limit_value=min_reserve,
            message=f"{bp_remaining_pct:.0f}% remaining vs {min_reserve:.0f}% minimum",
            severity="warning" if bp_remaining_pct < min_reserve else "info"
        ))
    
    def _determine_status(self, what_if: WhatIfScenario):
        """Determine overall status from risk checks."""
        outputs = what_if.outputs
        
        failed = [c for c in outputs.risk_checks if not c.passed]
        errors = [c for c in failed if c.severity == 'error']
        warnings = [c for c in failed if c.severity == 'warning']
        
        if errors:
            outputs.status = WhatIfStatus.BLOCKED
            outputs.blockers = [c.message for c in errors]
        elif warnings:
            outputs.status = WhatIfStatus.WARNING
            outputs.warnings = [c.message for c in warnings]
        else:
            outputs.status = WhatIfStatus.PASSED
    
    def _get_price(self, symbol: str) -> float:
        """Get current price for symbol."""
        if self.market_data:
            return self.market_data.get_price(symbol)
        return 100.0  # Placeholder
    
    def _get_iv(self, symbol: str) -> float:
        """Get current IV for symbol."""
        if self.market_data:
            return self.market_data.get_iv(symbol)
        return 0.25  # Placeholder 25%
    
    def _get_dte(self, legs: List[Dict]) -> int:
        """Get days to expiration from legs."""
        if legs and 'expiration' in legs[0]:
            exp = legs[0]['expiration']
            if isinstance(exp, datetime):
                return (exp - datetime.now()).days
        return 30  # Default


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    from datetime import date
    
    # Create a what-if scenario
    what_if = WhatIfScenario.create_put_credit_spread(
        underlying='SPY',
        short_strike=490,
        long_strike=485,
        expiration=datetime(2024, 2, 16),
        credit=1.50
    )
    
    print(f"Created: {what_if.name}")
    print(f"Credit: ${what_if.inputs.net_credit}")
    
    # Create engine and evaluate
    engine = WhatIfEngine()
    
    # Mock portfolio
    class MockPortfolio:
        total_equity = Decimal('100000')
        buying_power = Decimal('50000')
    
    engine.evaluate(what_if, MockPortfolio(), [])
    
    print(f"\nResults:")
    print(f"  Max Profit: ${what_if.outputs.max_profit}")
    print(f"  Max Loss: ${what_if.outputs.max_loss}")
    print(f"  POP: {what_if.outputs.probability_of_profit*100:.0f}%")
    print(f"  EV: ${what_if.outputs.expected_value:.0f}")
    print(f"  Status: {what_if.outputs.status.value}")
    print(f"  Should Proceed: {what_if.should_proceed()}")
