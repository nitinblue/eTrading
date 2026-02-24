"""
COMPLETE FUNCTIONAL PORTFOLIO ENGINE
=====================================

Architecture:
1. Volatility Surface (term structure, not single number)
2. Functional transformations (composable, pure)
3. DAG computation graph (flexible scenarios)
4. Foundation for hedge recommendations & arbitrage detection

This is production-grade infrastructure.
"""

from typing import Callable, Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, replace
from decimal import Decimal
from datetime import datetime, date
from functools import reduce
import logging

import trading_cotrader.core.models.domain as dm
from trading_cotrader.analytics.greeks.engine import GreeksEngine, GreeksCalculation
from trading_cotrader.analytics.volatility_surface import VolatilitySurface, VolatilitySurfaceBuilder

logger = logging.getLogger(__name__)


# ============================================================================
# PART 1: Computation Context (Immutable Configuration)
# ============================================================================

@dataclass(frozen=True)
class GreeksSource:
    """Configuration for Greeks calculation"""
    source: str  # 'broker', 'calculated', 'surface'
    
    # For 'surface' source
    volatility_surface: Optional[VolatilitySurface] = None
    
    # For sensitivity analysis
    delta_adjustment: Decimal = Decimal('1.0')
    theta_adjustment: Decimal = Decimal('1.0')
    vega_adjustment: Decimal = Decimal('1.0')


@dataclass(frozen=True)
class MarketScenario:
    """Market scenario for what-if analysis"""
    # Price changes
    underlying_price_change_pct: Decimal = Decimal('0')  # Percentage
    
    # Volatility changes
    iv_change_absolute: Decimal = Decimal('0')  # Add/subtract from IV
    iv_change_percent: Decimal = Decimal('0')  # Multiply IV
    
    # Time changes
    time_decay_days: int = 0
    
    # Rate changes
    interest_rate_change: Decimal = Decimal('0')
    
    @property
    def description(self) -> str:
        """Human-readable description"""
        parts = []
        if self.underlying_price_change_pct != 0:
            parts.append(f"Price {self.underlying_price_change_pct:+.1f}%")
        if self.iv_change_absolute != 0:
            parts.append(f"IV {self.iv_change_absolute:+.1%}")
        if self.time_decay_days > 0:
            parts.append(f"{self.time_decay_days}d decay")
        return ", ".join(parts) if parts else "Current"


@dataclass(frozen=True)
class ComputationContext:
    """Complete context for portfolio computation"""
    greeks_source: GreeksSource
    market_scenario: MarketScenario
    as_of_date: datetime
    
    # Risk parameters
    risk_free_rate: Decimal = Decimal('0.053')
    dividend_yields: Dict[str, Decimal] = None
    
    def __post_init__(self):
        if self.dividend_yields is None:
            object.__setattr__(self, 'dividend_yields', {
                'SPY': Decimal('0.015'),
                'QQQ': Decimal('0.006'),
                'IWM': Decimal('0.015'),
                'default': Decimal('0.010')
            })
    
    @classmethod
    def default(cls):
        return cls(
            greeks_source=GreeksSource('broker'),
            market_scenario=MarketScenario(),
            as_of_date=datetime.utcnow()
        )


# ============================================================================
# PART 2: Enhanced Position (With Calculated Fields)
# ============================================================================

@dataclass(frozen=True)
class EnhancedPosition:
    """
    Position with calculated fields (immutable)
    
    This is the OUTPUT of transformations
    """
    # Original position
    base_position: dm.Position
    
    # Greeks (can be from different sources)
    greeks: Optional[dm.Greeks]
    greeks_source: str  # 'broker', 'calculated', 'surface'
    
    # Scenario results
    scenario_pnl: Decimal = Decimal('0')
    scenario_price: Optional[Decimal] = None
    
    # P&L attribution
    pnl_from_delta: Decimal = Decimal('0')
    pnl_from_gamma: Decimal = Decimal('0')
    pnl_from_theta: Decimal = Decimal('0')
    pnl_from_vega: Decimal = Decimal('0')
    pnl_from_rho: Decimal = Decimal('0')
    
    # Calculated IV (if using surface)
    calculated_iv: Optional[Decimal] = None
    
    # Metadata
    calculation_context: Optional[ComputationContext] = None
    
    @property
    def total_pnl(self) -> Decimal:
        """Total P&L (original + scenario)"""
        return self.base_position.unrealized_pnl() + self.scenario_pnl


# ============================================================================
# PART 3: Transformation Functions (Pure)
# ============================================================================

def transform_greeks_from_broker(
    position: dm.Position,
    context: ComputationContext
) -> EnhancedPosition:
    """Use broker-provided Greeks (ground truth for operations)"""
    
    if not position.greeks:
        logger.warning(f"No broker Greeks for {position.symbol.ticker}")
        return EnhancedPosition(
            base_position=position,
            greeks=None,
            greeks_source='broker',
            calculation_context=context
        )
    
    # Apply adjustments if specified
    greeks = position.greeks
    if context.greeks_source.delta_adjustment != 1.0:
        greeks = dm.Greeks(
            delta=greeks.delta * context.greeks_source.delta_adjustment,
            gamma=greeks.gamma,
            theta=greeks.theta * context.greeks_source.theta_adjustment,
            vega=greeks.vega * context.greeks_source.vega_adjustment,
            rho=greeks.rho,
            timestamp=greeks.timestamp
        )
    
    return EnhancedPosition(
        base_position=position,
        greeks=greeks,
        greeks_source='broker',
        calculation_context=context
    )


def transform_greeks_from_surface(
    position: dm.Position,
    context: ComputationContext,
    greeks_engine: GreeksEngine
) -> EnhancedPosition:
    """Calculate Greeks using volatility surface (most accurate)"""
    
    if position.symbol.asset_type != dm.AssetType.OPTION:
        # Equity: delta = quantity
        greeks = dm.Greeks(
            delta=Decimal(str(position.quantity)),
            gamma=Decimal('0'),
            theta=Decimal('0'),
            vega=Decimal('0'),
            rho=Decimal('0'),
            timestamp=datetime.utcnow()
        )
        return EnhancedPosition(
            base_position=position,
            greeks=greeks,
            greeks_source='equity',
            calculation_context=context
        )
    
    surface = context.greeks_source.volatility_surface
    if not surface:
        logger.warning(f"No volatility surface available for {position.symbol.ticker}")
        return transform_greeks_from_broker(position, context)
    
    try:
        # Get IV from surface
        iv = surface.get_iv(
            strike=position.symbol.strike,
            expiration=position.symbol.expiration.date()
        )
        
        if not iv:
            logger.warning(f"Could not get IV from surface for {position.symbol.ticker}")
            return transform_greeks_from_broker(position, context)
        
        # Apply scenario IV changes
        if context.market_scenario.iv_change_absolute != 0:
            iv += context.market_scenario.iv_change_absolute
        if context.market_scenario.iv_change_percent != 0:
            iv *= (1 + context.market_scenario.iv_change_percent)
        
        # Calculate time to expiry
        time_to_expiry = (position.symbol.expiration - context.as_of_date).total_seconds() / (365.25 * 24 * 3600)
        
        # Apply time decay
        if context.market_scenario.time_decay_days > 0:
            time_to_expiry -= context.market_scenario.time_decay_days / 365.25
        
        if time_to_expiry <= 0:
            # Expired
            greeks = dm.Greeks(
                delta=Decimal('0'), gamma=Decimal('0'), theta=Decimal('0'),
                vega=Decimal('0'), rho=Decimal('0'), timestamp=datetime.utcnow()
            )
        else:
            # Calculate spot price (with scenario)
            spot_price = float(surface.spot_price)
            if context.market_scenario.underlying_price_change_pct != 0:
                spot_price *= (1 + float(context.market_scenario.underlying_price_change_pct) / 100)
            
            # Get dividend yield
            div_yield = context.dividend_yields.get(
                position.symbol.ticker,
                context.dividend_yields['default']
            )
            
            # Calculate Greeks
            greeks_calc = greeks_engine.calculate_greeks(
                option_type=position.symbol.option_type.value,
                spot_price=spot_price,
                strike=float(position.symbol.strike),
                time_to_expiry=time_to_expiry,
                volatility=float(iv),
                dividend_yield=float(div_yield)
            )
            
            # Position-level Greeks (multiply by quantity)
            greeks = dm.Greeks(
                delta=greeks_calc.delta * abs(position.quantity),
                gamma=greeks_calc.gamma * abs(position.quantity),
                theta=greeks_calc.theta * abs(position.quantity),
                vega=greeks_calc.vega * abs(position.quantity),
                rho=greeks_calc.rho * abs(position.quantity),
                timestamp=datetime.utcnow()
            )
        
        return EnhancedPosition(
            base_position=position,
            greeks=greeks,
            greeks_source='surface',
            calculated_iv=iv,
            calculation_context=context
        )
    
    except Exception as e:
        logger.error(f"Error calculating Greeks from surface for {position.symbol.ticker}: {e}")
        return transform_greeks_from_broker(position, context)


def transform_apply_scenario(
    enhanced_pos: EnhancedPosition,
    context: ComputationContext
) -> EnhancedPosition:
    """Apply market scenario to calculate P&L impact"""
    
    if not enhanced_pos.greeks:
        return enhanced_pos
    
    greeks = enhanced_pos.greeks
    position = enhanced_pos.base_position
    scenario = context.market_scenario
    
    # Calculate P&L components
    pnl_delta = Decimal('0')
    pnl_gamma = Decimal('0')
    pnl_theta = Decimal('0')
    pnl_vega = Decimal('0')
    
    # Price change impact
    if scenario.underlying_price_change_pct != 0:
        if position.current_price:
            price_move = position.current_price * scenario.underlying_price_change_pct / 100
            
            # Delta P&L (first order)
            pnl_delta = greeks.delta * price_move * position.symbol.multiplier
            
            # Gamma P&L (second order)
            pnl_gamma = Decimal('0.5') * greeks.gamma * (price_move ** 2) * position.symbol.multiplier
    
    # Time decay
    if scenario.time_decay_days > 0:
        pnl_theta = greeks.theta * scenario.time_decay_days * position.symbol.multiplier
    
    # Volatility change
    if scenario.iv_change_absolute != 0:
        # Vega is per 1% IV change
        pnl_vega = greeks.vega * scenario.iv_change_absolute * 100 * position.symbol.multiplier
    
    total_scenario_pnl = pnl_delta + pnl_gamma + pnl_theta + pnl_vega
    
    return replace(
        enhanced_pos,
        scenario_pnl=total_scenario_pnl,
        pnl_from_delta=pnl_delta,
        pnl_from_gamma=pnl_gamma,
        pnl_from_theta=pnl_theta,
        pnl_from_vega=pnl_vega
    )


# ============================================================================
# PART 4: Portfolio Computation Engine (DAG)
# ============================================================================

@dataclass(frozen=True)
class PortfolioResult:
    """Immutable computation result"""
    # Positions
    positions: List[EnhancedPosition]
    
    # Aggregated metrics
    total_pnl: Decimal
    total_delta: Decimal
    total_gamma: Decimal
    total_theta: Decimal
    total_vega: Decimal
    total_rho: Decimal
    
    # P&L attribution
    pnl_from_delta: Decimal
    pnl_from_gamma: Decimal
    pnl_from_theta: Decimal
    pnl_from_vega: Decimal
    
    # Metadata
    context: ComputationContext
    timestamp: datetime
    
    def to_dict(self) -> Dict:
        """Serialize for storage/API"""
        return {
            'total_pnl': float(self.total_pnl),
            'total_delta': float(self.total_delta),
            'total_theta': float(self.total_theta),
            'total_vega': float(self.total_vega),
            'pnl_attribution': {
                'delta': float(self.pnl_from_delta),
                'gamma': float(self.pnl_from_gamma),
                'theta': float(self.pnl_from_theta),
                'vega': float(self.pnl_from_vega)
            },
            'scenario': self.context.market_scenario.description,
            'greeks_source': self.context.greeks_source.source,
            'timestamp': self.timestamp.isoformat()
        }


class PortfolioComputationEngine:
    """
    DAG-based portfolio computation engine
    
    This is the core of your system.
    """
    
    def __init__(self, greeks_engine: GreeksEngine):
        self.greeks_engine = greeks_engine
    
    def compute(
        self,
        positions: List[dm.Position],
        context: ComputationContext
    ) -> PortfolioResult:
        """
        Execute computation graph
        
        DAG Flow:
        positions → transform_greeks → apply_scenario → aggregate
        """
        
        # Step 1: Transform positions (apply Greeks source)
        enhanced_positions = []
        for pos in positions:
            if context.greeks_source.source == 'broker':
                enhanced = transform_greeks_from_broker(pos, context)
            elif context.greeks_source.source == 'surface':
                enhanced = transform_greeks_from_surface(pos, context, self.greeks_engine)
            else:
                enhanced = transform_greeks_from_broker(pos, context)
            
            enhanced_positions.append(enhanced)
        
        # Step 2: Apply scenario
        scenario_positions = [
            transform_apply_scenario(epos, context)
            for epos in enhanced_positions
        ]
        
        # Step 3: Aggregate
        total_pnl = sum(p.total_pnl for p in scenario_positions)
        total_delta = sum(p.greeks.delta if p.greeks else 0 for p in scenario_positions)
        total_gamma = sum(p.greeks.gamma if p.greeks else 0 for p in scenario_positions)
        total_theta = sum(p.greeks.theta if p.greeks else 0 for p in scenario_positions)
        total_vega = sum(p.greeks.vega if p.greeks else 0 for p in scenario_positions)
        total_rho = sum(p.greeks.rho if p.greeks else 0 for p in scenario_positions)
        
        pnl_delta = sum(p.pnl_from_delta for p in scenario_positions)
        pnl_gamma = sum(p.pnl_from_gamma for p in scenario_positions)
        pnl_theta = sum(p.pnl_from_theta for p in scenario_positions)
        pnl_vega = sum(p.pnl_from_vega for p in scenario_positions)
        
        return PortfolioResult(
            positions=scenario_positions,
            total_pnl=total_pnl,
            total_delta=total_delta,
            total_gamma=total_gamma,
            total_theta=total_theta,
            total_vega=total_vega,
            total_rho=total_rho,
            pnl_from_delta=pnl_delta,
            pnl_from_gamma=pnl_gamma,
            pnl_from_theta=pnl_theta,
            pnl_from_vega=pnl_vega,
            context=context,
            timestamp=datetime.utcnow()
        )


# ============================================================================
# PART 5: High-Level API (Builder Pattern)
# ============================================================================

class PortfolioAnalyzer:
    """
    High-level API for portfolio analysis
    
    Usage:
        analyzer = PortfolioAnalyzer(positions)
        
        # Current state
        current = analyzer.current()
        
        # What-if scenarios
        crash = analyzer.scenario(spy_drop=5).compute()
        rally = analyzer.scenario(spy_rise=3).compute()
        
        # Compare Greeks sources
        broker_view = analyzer.with_broker_greeks().compute()
        surface_view = analyzer.with_surface_greeks(surface).compute()
    """
    
    def __init__(self, positions: List[dm.Position], greeks_engine: GreeksEngine = None):
        self.positions = positions
        self.greeks_engine = greeks_engine or GreeksEngine()
        self.engine = PortfolioComputationEngine(self.greeks_engine)
        self._context = ComputationContext.default()
    
    def with_broker_greeks(self):
        """Use broker Greeks"""
        self._context = replace(
            self._context,
            greeks_source=GreeksSource('broker')
        )
        return self
    
    def with_surface_greeks(self, surface: VolatilitySurface):
        """Use volatility surface for Greeks"""
        self._context = replace(
            self._context,
            greeks_source=GreeksSource('surface', volatility_surface=surface)
        )
        return self
    
    def scenario(
        self,
        spy_move: float = 0,
        iv_change: float = 0,
        days_forward: int = 0
    ):
        """Apply market scenario"""
        self._context = replace(
            self._context,
            market_scenario=MarketScenario(
                underlying_price_change_pct=Decimal(str(spy_move)),
                iv_change_absolute=Decimal(str(iv_change)),
                time_decay_days=days_forward
            )
        )
        return self
    
    def compute(self) -> PortfolioResult:
        """Execute computation"""
        return self.engine.compute(self.positions, self._context)
    
    def current(self) -> PortfolioResult:
        """Current state (no scenario)"""
        self._context = replace(
            self._context,
            market_scenario=MarketScenario()
        )
        return self.compute()


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

"""
Example 1: Current Portfolio State
-----------------------------------
analyzer = PortfolioAnalyzer(positions)
current = analyzer.current()

print(f"Total P&L: ${current.total_pnl:,.2f}")
print(f"Delta: {current.total_delta:.2f}")
print(f"Theta: {current.total_theta:.2f}/day")


Example 2: What-If Scenario
----------------------------
crash = analyzer.scenario(spy_move=-5, iv_change=0.10).compute()

print(f"After 5% crash:")
print(f"  P&L: ${crash.total_pnl:,.2f}")
print(f"  P&L from delta: ${crash.pnl_from_delta:,.2f}")
print(f"  P&L from vega: ${crash.pnl_from_vega:,.2f}")


Example 3: Compare Greeks Sources
----------------------------------
# Build volatility surface
surface = builder.build_from_positions(positions, spot_price)

# Broker view
broker_result = (PortfolioAnalyzer(positions)
    .with_broker_greeks()
    .compute())

# Surface view
surface_result = (PortfolioAnalyzer(positions)
    .with_surface_greeks(surface)
    .compute())

# Compare
delta_diff = abs(broker_result.total_delta - surface_result.total_delta)
print(f"Delta mismatch: {delta_diff:.2f}")


Example 4: Stress Test Matrix
------------------------------
analyzer = PortfolioAnalyzer(positions)

for spy_move in range(-10, 11, 2):
    for iv_change in [-0.10, -0.05, 0, 0.05, 0.10]:
        result = analyzer.scenario(
            spy_move=spy_move,
            iv_change=iv_change
        ).compute()
        
        print(f"SPY {spy_move:+3d}%, IV {iv_change:+.2f}: ${result.total_pnl:,.2f}")
"""

if __name__ == "__main__":
    print(__doc__)
