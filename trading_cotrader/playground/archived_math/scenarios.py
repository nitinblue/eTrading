"""
Scenario Analysis Engine

What-if analysis for trades and portfolios:
- Price scenarios
- Volatility scenarios
- Time decay scenarios
- Combined scenarios
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging

from services.pricing.black_scholes import BlackScholesModel, OptionType

logger = logging.getLogger(__name__)


@dataclass
class Scenario:
    """Definition of a what-if scenario"""
    name: str
    
    # Price changes
    price_change_percent: float = 0.0
    price_change_absolute: float = 0.0
    
    # Volatility changes
    iv_change_percent: float = 0.0
    iv_change_absolute: float = 0.0
    
    # Time changes
    days_forward: int = 0
    
    # Combined
    description: str = ""


@dataclass
class WhatIfResult:
    """Result of a scenario analysis"""
    scenario: Scenario
    
    # P&L
    position_pnl: Decimal = Decimal('0')
    pnl_percent: Decimal = Decimal('0')
    
    # Greeks after scenario
    delta_after: Decimal = Decimal('0')
    theta_after: Decimal = Decimal('0')
    
    # Position values
    value_before: Decimal = Decimal('0')
    value_after: Decimal = Decimal('0')
    
    # Breakdown by leg (for multi-leg trades)
    leg_results: List[Dict] = field(default_factory=list)


# Standard scenarios
STANDARD_SCENARIOS = [
    Scenario("Price +1%", price_change_percent=1.0),
    Scenario("Price -1%", price_change_percent=-1.0),
    Scenario("Price +5%", price_change_percent=5.0),
    Scenario("Price -5%", price_change_percent=-5.0),
    Scenario("Price +10%", price_change_percent=10.0),
    Scenario("Price -10%", price_change_percent=-10.0),
    Scenario("IV +5%", iv_change_absolute=5.0),  # 5 vol points
    Scenario("IV -5%", iv_change_absolute=-5.0),
    Scenario("1 Week Forward", days_forward=7),
    Scenario("2 Weeks Forward", days_forward=14),
    Scenario("At Expiration", days_forward=999),  # Special case
    Scenario("Crash: -20%, +40vol", price_change_percent=-20, iv_change_absolute=40),
    Scenario("Rally: +10%, -10vol", price_change_percent=10, iv_change_absolute=-10),
]


class ScenarioEngine:
    """
    Run what-if scenarios on positions and trades.
    
    Usage:
        engine = ScenarioEngine()
        
        # Run single scenario
        result = engine.run_scenario(position, spot=100, vol=0.25, scenario=Scenario("Price +5%", price_change_percent=5))
        
        # Run all standard scenarios
        results = engine.run_all_scenarios(position, spot=100, vol=0.25)
        
        # Build P&L matrix (price x vol)
        matrix = engine.build_pnl_matrix(position, spot=100, vol=0.25)
    """
    
    def __init__(self):
        self.bs_model = BlackScholesModel()
    
    def run_scenario(
        self,
        position,  # Position or Trade
        spot: float,
        volatility: float,
        scenario: Scenario,
        days_to_expiry: int = 30,
        rate: float = 0.05
    ) -> WhatIfResult:
        """
        Run a single scenario on a position.
        
        Args:
            position: Position or Trade object
            spot: Current underlying price
            volatility: Current IV
            scenario: Scenario to run
            days_to_expiry: Days until expiration
            rate: Risk-free rate
            
        Returns:
            WhatIfResult with P&L and Greeks
        """
        # Calculate new values under scenario
        new_spot = spot * (1 + scenario.price_change_percent / 100) + scenario.price_change_absolute
        new_vol = volatility + scenario.iv_change_absolute / 100
        new_vol = max(0.01, new_vol)  # Floor at 1%
        
        new_dte = max(0, days_to_expiry - scenario.days_forward)
        if scenario.days_forward == 999:  # At expiration
            new_dte = 0
        
        # Get current value
        current_value = self._calculate_position_value(position, spot, volatility, days_to_expiry, rate)
        
        # Get scenario value
        scenario_value = self._calculate_position_value(position, new_spot, new_vol, new_dte, rate)
        
        pnl = scenario_value - current_value
        pnl_pct = (pnl / abs(current_value) * 100) if current_value != 0 else 0
        
        return WhatIfResult(
            scenario=scenario,
            position_pnl=Decimal(str(pnl)),
            pnl_percent=Decimal(str(pnl_pct)),
            value_before=Decimal(str(current_value)),
            value_after=Decimal(str(scenario_value))
        )
    
    def run_all_scenarios(
        self,
        position,
        spot: float,
        volatility: float,
        days_to_expiry: int = 30,
        scenarios: List[Scenario] = None
    ) -> List[WhatIfResult]:
        """Run all standard scenarios."""
        if scenarios is None:
            scenarios = STANDARD_SCENARIOS
        
        results = []
        for scenario in scenarios:
            result = self.run_scenario(position, spot, volatility, scenario, days_to_expiry)
            results.append(result)
        
        return results
    
    def build_pnl_matrix(
        self,
        position,
        spot: float,
        volatility: float,
        days_to_expiry: int = 30,
        price_range: Tuple[float, float] = (-20, 20),  # % range
        vol_range: Tuple[float, float] = (-10, 10),    # vol points
        price_steps: int = 9,
        vol_steps: int = 5,
        rate: float = 0.05
    ) -> Dict:
        """
        Build a P&L matrix across price and volatility changes.
        
        Returns dict with 'prices', 'vols', 'pnl_matrix'
        """
        # Generate price points
        price_changes = []
        step = (price_range[1] - price_range[0]) / (price_steps - 1)
        for i in range(price_steps):
            price_changes.append(price_range[0] + i * step)
        
        # Generate vol points
        vol_changes = []
        step = (vol_range[1] - vol_range[0]) / (vol_steps - 1)
        for i in range(vol_steps):
            vol_changes.append(vol_range[0] + i * step)
        
        # Calculate current value
        current_value = self._calculate_position_value(position, spot, volatility, days_to_expiry, rate)
        
        # Build matrix
        pnl_matrix = []
        for vol_change in vol_changes:
            row = []
            for price_change in price_changes:
                new_spot = spot * (1 + price_change / 100)
                new_vol = max(0.01, volatility + vol_change / 100)
                
                new_value = self._calculate_position_value(position, new_spot, new_vol, days_to_expiry, rate)
                pnl = new_value - current_value
                row.append(pnl)
            pnl_matrix.append(row)
        
        return {
            'price_changes': price_changes,
            'vol_changes': vol_changes,
            'pnl_matrix': pnl_matrix,
            'current_value': current_value
        }
    
    def time_decay_projection(
        self,
        position,
        spot: float,
        volatility: float,
        days_to_expiry: int,
        days_to_project: int = None,
        rate: float = 0.05
    ) -> List[Dict]:
        """
        Project position value over time (theta decay).
        
        Returns list of {day, value, pnl, theta} dictionaries
        """
        if days_to_project is None:
            days_to_project = days_to_expiry
        
        current_value = self._calculate_position_value(position, spot, volatility, days_to_expiry, rate)
        
        projections = []
        for day in range(days_to_project + 1):
            remaining_dte = max(0, days_to_expiry - day)
            value = self._calculate_position_value(position, spot, volatility, remaining_dte, rate)
            pnl = value - current_value
            
            projections.append({
                'day': day,
                'dte': remaining_dte,
                'value': value,
                'pnl': pnl,
                'pnl_percent': (pnl / abs(current_value) * 100) if current_value != 0 else 0
            })
        
        return projections
    
    def _calculate_position_value(
        self,
        position,
        spot: float,
        volatility: float,
        days_to_expiry: int,
        rate: float
    ) -> float:
        """Calculate position value."""
        # For now, simple implementation
        # TODO: Handle multi-leg positions properly
        
        symbol = getattr(position, 'symbol', None)
        if not symbol:
            return 0.0
        
        asset_type = getattr(symbol, 'asset_type', None)
        if not asset_type or getattr(asset_type, 'value', '') == 'equity':
            # Equity position
            quantity = getattr(position, 'quantity', 0)
            return spot * quantity
        
        # Option position
        strike = float(getattr(symbol, 'strike', 0) or 0)
        option_type = getattr(symbol, 'option_type', None)
        quantity = getattr(position, 'quantity', 0)
        multiplier = getattr(symbol, 'multiplier', 100)
        
        if not strike or not option_type:
            return 0.0
        
        opt_type = OptionType.CALL if getattr(option_type, 'value', '') == 'call' else OptionType.PUT
        time_to_expiry = max(0.001, days_to_expiry / 365)
        
        price = self.bs_model.price(spot, strike, time_to_expiry, rate, volatility, opt_type)
        return price * quantity * multiplier


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    engine = ScenarioEngine()
    
    print("Standard Scenarios Available:")
    for scenario in STANDARD_SCENARIOS:
        print(f"  - {scenario.name}")
    
    # Would use actual position
    # results = engine.run_all_scenarios(position, spot=100, vol=0.25)
