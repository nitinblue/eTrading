"""
Risk Factor Models

Integrates with existing core/models/domain.py objects.
Uses existing analytics/greeks/engine.py for calculations.

Core Concept: 
- RiskFactor = what you're exposed to (MSFT price, Gold price)
- Sensitivity = how much (delta, gamma, theta, vega, rho)
- Aggregation = sum across all instruments per risk factor
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional, Set
from enum import Enum
import logging

# Import existing domain models
try:
    import trading_cotrader.core.models.domain as dm
except ImportError:
    dm = None

logger = logging.getLogger(__name__)


class RiskFactorType(Enum):
    """Types of risk factors"""
    UNDERLYING_PRICE = "underlying_price"
    IMPLIED_VOL = "implied_vol"
    TIME_DECAY = "time_decay"
    INTEREST_RATE = "interest_rate"


@dataclass(frozen=True)
class RiskFactor:
    """
    A single risk factor that affects P&L.
    
    Examples:
        RiskFactor(UNDERLYING_PRICE, "MSFT") - MSFT spot price
        RiskFactor(UNDERLYING_PRICE, "GC") - Gold futures price
    """
    factor_type: RiskFactorType
    underlying: Optional[str]
    description: str = ""
    
    @property
    def factor_id(self) -> str:
        if self.underlying:
            return f"{self.underlying}_{self.factor_type.value}"
        return self.factor_type.value


@dataclass
class InstrumentSensitivity:
    """
    One instrument's sensitivity to one risk factor.
    
    Links a Position to a RiskFactor with Greeks.
    """
    instrument_id: str
    instrument_description: str
    risk_factor: RiskFactor
    
    # Raw sensitivities (per unit)
    delta: Decimal = Decimal('0')
    gamma: Decimal = Decimal('0')
    theta: Decimal = Decimal('0')
    vega: Decimal = Decimal('0')
    rho: Decimal = Decimal('0')
    
    # Position context
    position_quantity: int = 0
    multiplier: int = 100
    
    @property
    def total_delta(self) -> Decimal:
        return self.delta * self.position_quantity * self.multiplier
    
    @property
    def total_gamma(self) -> Decimal:
        return self.gamma * self.position_quantity * self.multiplier
    
    @property
    def total_theta(self) -> Decimal:
        return self.theta * self.position_quantity * self.multiplier
    
    @property
    def total_vega(self) -> Decimal:
        return self.vega * self.position_quantity * self.multiplier
    
    @property
    def total_rho(self) -> Decimal:
        return self.rho * self.position_quantity * self.multiplier


@dataclass
class AggregatedRiskFactor:
    """
    Aggregated sensitivities across ALL instruments for ONE risk factor.
    
    This is THE key output for hedging decisions.
    """
    risk_factor: RiskFactor
    
    total_delta: Decimal = Decimal('0')
    total_gamma: Decimal = Decimal('0')
    total_theta: Decimal = Decimal('0')
    total_vega: Decimal = Decimal('0')
    total_rho: Decimal = Decimal('0')
    
    # Dollar metrics
    delta_dollars: Decimal = Decimal('0')
    gamma_dollars: Decimal = Decimal('0')
    
    contributing_instruments: List[str] = field(default_factory=list)
    sensitivities: List[InstrumentSensitivity] = field(default_factory=list)
    
    def add_sensitivity(self, sens: InstrumentSensitivity):
        self.total_delta += sens.total_delta
        self.total_gamma += sens.total_gamma
        self.total_theta += sens.total_theta
        self.total_vega += sens.total_vega
        self.total_rho += sens.total_rho
        
        if sens.instrument_id not in self.contributing_instruments:
            self.contributing_instruments.append(sens.instrument_id)
        self.sensitivities.append(sens)
    
    def compute_dollar_values(self, spot_price: Decimal):
        self.delta_dollars = self.total_delta * spot_price
        one_pct = spot_price * Decimal('0.01')
        self.gamma_dollars = Decimal('0.5') * self.total_gamma * (one_pct ** 2)
    
    def to_dict(self) -> Dict:
        return {
            'underlying': self.risk_factor.underlying,
            'delta': float(self.total_delta),
            'gamma': float(self.total_gamma),
            'theta': float(self.total_theta),
            'vega': float(self.total_vega),
            'rho': float(self.total_rho),
            'delta_dollars': float(self.delta_dollars),
            'instruments': len(self.contributing_instruments),
        }


@dataclass
class RiskFactorContainer:
    """
    Container for all risk factors and aggregated sensitivities.
    
    Main data structure for risk-factor-based portfolio management.
    """
    timestamp: datetime = field(default_factory=datetime.utcnow)
    risk_factors: Dict[str, RiskFactor] = field(default_factory=dict)
    aggregated: Dict[str, AggregatedRiskFactor] = field(default_factory=dict)
    all_sensitivities: List[InstrumentSensitivity] = field(default_factory=list)
    
    def add_risk_factor(self, factor: RiskFactor):
        if factor.factor_id not in self.risk_factors:
            self.risk_factors[factor.factor_id] = factor
            self.aggregated[factor.factor_id] = AggregatedRiskFactor(risk_factor=factor)
    
    def add_sensitivity(self, sens: InstrumentSensitivity):
        factor = sens.risk_factor
        if factor.factor_id not in self.risk_factors:
            self.add_risk_factor(factor)
        self.aggregated[factor.factor_id].add_sensitivity(sens)
        self.all_sensitivities.append(sens)
    
    def get_aggregated(self, factor_id: str) -> Optional[AggregatedRiskFactor]:
        return self.aggregated.get(factor_id)
    
    def get_total_delta_by_underlying(self) -> Dict[str, Decimal]:
        """Get total delta grouped by underlying"""
        deltas = {}
        for agg in self.aggregated.values():
            if agg.risk_factor.factor_type == RiskFactorType.UNDERLYING_PRICE:
                deltas[agg.risk_factor.underlying] = agg.total_delta
        return deltas
    
    def get_total_greeks_by_underlying(self) -> Dict[str, Dict[str, Decimal]]:
        """Get all Greeks grouped by underlying (for UI display)"""
        result = {}
        for agg in self.aggregated.values():
            if agg.risk_factor.factor_type == RiskFactorType.UNDERLYING_PRICE:
                underlying = agg.risk_factor.underlying
                result[underlying] = {
                    'delta': agg.total_delta,
                    'gamma': agg.total_gamma,
                    'theta': agg.total_theta,
                    'vega': agg.total_vega,
                    'rho': agg.total_rho,
                    'instruments': len(agg.contributing_instruments),
                }
        return result
    
    def get_portfolio_totals(self) -> Dict[str, Decimal]:
        """Get total portfolio Greeks"""
        totals = {'delta': Decimal('0'), 'gamma': Decimal('0'), 
                  'theta': Decimal('0'), 'vega': Decimal('0'), 'rho': Decimal('0')}
        for agg in self.aggregated.values():
            if agg.risk_factor.factor_type == RiskFactorType.UNDERLYING_PRICE:
                totals['delta'] += agg.total_delta
                totals['gamma'] += agg.total_gamma
                totals['theta'] += agg.total_theta
                totals['vega'] += agg.total_vega
                totals['rho'] += agg.total_rho
        return totals
    
    def get_factors_needing_hedge(
        self,
        delta_threshold: Decimal = Decimal('100'),
        gamma_threshold: Decimal = Decimal('10'),
        vega_threshold: Decimal = Decimal('500'),
    ) -> List[AggregatedRiskFactor]:
        """Get risk factors exceeding thresholds"""
        needs_hedge = []
        for agg in self.aggregated.values():
            if agg.risk_factor.factor_type == RiskFactorType.UNDERLYING_PRICE:
                if (abs(agg.total_delta) > delta_threshold or
                    abs(agg.total_gamma) > gamma_threshold or
                    abs(agg.total_vega) > vega_threshold):
                    needs_hedge.append(agg)
        return needs_hedge
    
    def to_summary_table(self) -> List[Dict]:
        """For display in harness/UI"""
        rows = []
        for factor_id, agg in sorted(self.aggregated.items()):
            if agg.risk_factor.factor_type == RiskFactorType.UNDERLYING_PRICE:
                rows.append({
                    'Underlying': agg.risk_factor.underlying,
                    'Delta': float(agg.total_delta),
                    'Gamma': float(agg.total_gamma),
                    'Theta': float(agg.total_theta),
                    'Vega': float(agg.total_vega),
                    'Rho': float(agg.total_rho),
                    'Instruments': len(agg.contributing_instruments),
                })
        return rows


def create_underlying_price_factor(underlying: str) -> RiskFactor:
    """Factory for underlying price risk factor"""
    return RiskFactor(
        factor_type=RiskFactorType.UNDERLYING_PRICE,
        underlying=underlying,
        description=f"{underlying} spot price"
    )
