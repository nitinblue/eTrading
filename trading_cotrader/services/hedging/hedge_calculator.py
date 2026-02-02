"""
Hedge Calculator

Computes hedge recommendations at the RISK FACTOR level.
Uses existing analytics/greeks/engine.py for Greek calculations.

Based on institutional_trading_v3.py logic:
- Delta: Futures/Stock (lowest cost, no time decay)
- Gamma: ATM options (highest gamma per contract)
- Vega: Longer-dated options (higher vega per unit)
- Theta: Short options/iron condor (collect premium)
- Rho: Long-dated options (higher rho sensitivity)
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Dict, Optional, Literal
from enum import Enum
import logging

try:
    from scipy.stats import norm
    import numpy as np
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

from trading_cotrader.services.risk_factors.models import (
    RiskFactor, RiskFactorType, AggregatedRiskFactor, RiskFactorContainer
)

logger = logging.getLogger(__name__)


class HedgeType(Enum):
    STOCK = "stock"
    FUTURE = "future"
    ATM_CALL = "atm_call"
    ATM_PUT = "atm_put"
    LONG_DATED_CALL = "long_dated_call"
    LONG_DATED_PUT = "long_dated_put"
    IRON_CONDOR = "iron_condor"
    STRADDLE = "straddle"


@dataclass
class HedgeOption:
    """Single hedge option with analysis"""
    hedge_type: HedgeType
    instrument: str
    position: Decimal
    greek_per_unit: Decimal
    
    delta_impact: Decimal = Decimal('0')
    gamma_impact: Decimal = Decimal('0')
    theta_impact: Decimal = Decimal('0')
    vega_impact: Decimal = Decimal('0')
    rho_impact: Decimal = Decimal('0')
    
    estimated_price: Optional[Decimal] = None
    estimated_cost: Optional[Decimal] = None
    
    is_recommended: bool = False
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    why_not: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'hedge_type': self.hedge_type.value,
            'instrument': self.instrument,
            'position': float(self.position),
            'delta_impact': float(self.delta_impact),
            'is_recommended': self.is_recommended,
            'pros': self.pros,
        }


@dataclass
class HedgeRecommendation:
    """Complete hedge recommendation for one risk factor"""
    risk_factor: RiskFactor
    greek_type: Literal["delta", "gamma", "theta", "vega", "rho"]
    exposure: Decimal
    target: Decimal
    optimizing_for: str
    options: List[HedgeOption] = field(default_factory=list)
    
    @property
    def recommended(self) -> Optional[HedgeOption]:
        for opt in self.options:
            if opt.is_recommended:
                return opt
        return self.options[0] if self.options else None
    
    def to_dict(self) -> Dict:
        return {
            'underlying': self.risk_factor.underlying,
            'greek_type': self.greek_type,
            'exposure': float(self.exposure),
            'target': float(self.target),
            'recommended': self.recommended.to_dict() if self.recommended else None,
        }


def _bs_greeks(S: float, K: float, T: float, r: float, sigma: float, opt_type: str = 'call') -> Dict:
    """Black-Scholes Greeks for hedge sizing"""
    if not HAS_SCIPY:
        # Fallback approximation
        return {'delta': 0.5, 'gamma': 0.01, 'theta': -0.05, 'vega': 0.2, 'rho': 0.1}
    
    if T <= 0:
        T = 1/365
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if opt_type == 'call':
        delta = norm.cdf(d1)
        theta = - (S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)
        rho = K * T * np.exp(-r * T) * norm.cdf(d2)
    else:
        delta = -norm.cdf(-d1)
        theta = - (S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)
        rho = -K * T * np.exp(-r * T) * norm.cdf(-d2)
    
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    vega = S * np.sqrt(T) * norm.pdf(d1)
    
    return {'delta': delta, 'gamma': gamma, 'theta': theta, 'vega': vega, 'rho': rho}


class HedgeCalculator:
    """
    Calculate hedge recommendations for risk factors.
    
    Usage:
        calculator = HedgeCalculator()
        
        # Single hedge
        reco = calculator.calculate_delta_hedge('MSFT', Decimal('150'), Decimal('410'))
        
        # All hedges for container
        recommendations = calculator.calculate_all_hedges(container, market_data)
    """
    
    def __init__(self, risk_free_rate: float = 0.05, default_vol: float = 0.25, default_expiry: float = 30/365):
        self.risk_free_rate = risk_free_rate
        self.default_vol = default_vol
        self.default_expiry = default_expiry
    
    def calculate_delta_hedge(
        self,
        underlying: str,
        total_delta: Decimal,
        spot_price: Decimal,
        target_delta: Decimal = Decimal('0'),
    ) -> HedgeRecommendation:
        """Delta hedge - recommend stock/futures"""
        S = float(spot_price)
        delta_to_hedge = float(total_delta - target_delta)
        
        risk_factor = RiskFactor(RiskFactorType.UNDERLYING_PRICE, underlying)
        options = []
        
        # Option 1: Stock/Future (RECOMMENDED)
        stock_option = HedgeOption(
            hedge_type=HedgeType.STOCK,
            instrument=f"{underlying}_Stock",
            position=Decimal(str(-delta_to_hedge)),
            greek_per_unit=Decimal('1'),
            delta_impact=Decimal(str(-delta_to_hedge)),
            estimated_price=spot_price,
            estimated_cost=abs(Decimal(str(delta_to_hedge)) * spot_price),
            is_recommended=True,
            pros=["Low cost", "No time decay", "Precise offset"],
        )
        options.append(stock_option)
        
        # Option 2: ATM Call
        atm = _bs_greeks(S, S, self.default_expiry, self.risk_free_rate, self.default_vol, 'call')
        call_pos = -delta_to_hedge / atm['delta'] if atm['delta'] != 0 else 0
        call_option = HedgeOption(
            hedge_type=HedgeType.ATM_CALL,
            instrument=f"{underlying}_ATM_Call",
            position=Decimal(str(round(call_pos, 2))),
            greek_per_unit=Decimal(str(atm['delta'])),
            delta_impact=Decimal(str(-delta_to_hedge)),
            gamma_impact=Decimal(str(call_pos * atm['gamma'])),
            is_recommended=False,
            pros=["Adds gamma protection"],
            why_not="Higher cost and time decay vs stock",
        )
        options.append(call_option)
        
        return HedgeRecommendation(
            risk_factor=risk_factor,
            greek_type="delta",
            exposure=total_delta,
            target=target_delta,
            optimizing_for="minimize cost, no time decay",
            options=options,
        )
    
    def calculate_gamma_hedge(
        self,
        underlying: str,
        total_gamma: Decimal,
        spot_price: Decimal,
        target_gamma: Decimal = Decimal('0'),
    ) -> HedgeRecommendation:
        """Gamma hedge - recommend ATM options"""
        S = float(spot_price)
        gamma_to_hedge = float(total_gamma - target_gamma)
        
        risk_factor = RiskFactor(RiskFactorType.UNDERLYING_PRICE, underlying)
        
        atm = _bs_greeks(S, S, self.default_expiry, self.risk_free_rate, self.default_vol, 'call')
        call_pos = -gamma_to_hedge / atm['gamma'] if atm['gamma'] != 0 else 0
        
        call_option = HedgeOption(
            hedge_type=HedgeType.ATM_CALL,
            instrument=f"{underlying}_ATM_Call",
            position=Decimal(str(round(call_pos, 2))),
            greek_per_unit=Decimal(str(atm['gamma'])),
            delta_impact=Decimal(str(call_pos * atm['delta'])),
            gamma_impact=Decimal(str(-gamma_to_hedge)),
            is_recommended=True,
            pros=["Highest gamma per contract", "Convexity protection"],
        )
        
        return HedgeRecommendation(
            risk_factor=risk_factor,
            greek_type="gamma",
            exposure=total_gamma,
            target=target_gamma,
            optimizing_for="convexity protection, cost efficiency",
            options=[call_option],
        )
    
    def calculate_vega_hedge(
        self,
        underlying: str,
        total_vega: Decimal,
        spot_price: Decimal,
        target_vega: Decimal = Decimal('0'),
    ) -> HedgeRecommendation:
        """Vega hedge - recommend longer-dated options"""
        S = float(spot_price)
        vega_to_hedge = float(total_vega - target_vega)
        
        risk_factor = RiskFactor(RiskFactorType.IMPLIED_VOL, underlying)
        
        long_greeks = _bs_greeks(S, S, 0.5, self.risk_free_rate, self.default_vol, 'put')
        pos = -vega_to_hedge / long_greeks['vega'] if long_greeks['vega'] != 0 else 0
        
        put_option = HedgeOption(
            hedge_type=HedgeType.LONG_DATED_PUT,
            instrument=f"{underlying}_Long_Dated_Put",
            position=Decimal(str(round(pos, 2))),
            greek_per_unit=Decimal(str(long_greeks['vega'])),
            vega_impact=Decimal(str(-vega_to_hedge)),
            is_recommended=True,
            pros=["Higher vega per unit", "Lower theta bleed"],
        )
        
        return HedgeRecommendation(
            risk_factor=risk_factor,
            greek_type="vega",
            exposure=total_vega,
            target=target_vega,
            optimizing_for="vol protection with minimal cost",
            options=[put_option],
        )
    
    def calculate_theta_hedge(
        self,
        underlying: str,
        total_theta: Decimal,
        spot_price: Decimal,
        target_theta: Decimal = Decimal('0'),
    ) -> HedgeRecommendation:
        """Theta hedge - recommend iron condor"""
        S = float(spot_price)
        theta_to_hedge = float(total_theta - target_theta)
        
        risk_factor = RiskFactor(RiskFactorType.TIME_DECAY, underlying)
        
        atm = _bs_greeks(S, S, self.default_expiry, self.risk_free_rate, self.default_vol, 'call')
        pos = -theta_to_hedge / (atm['theta'] * 4) if atm['theta'] != 0 else 0
        
        condor_option = HedgeOption(
            hedge_type=HedgeType.IRON_CONDOR,
            instrument=f"{underlying}_Iron_Condor",
            position=Decimal(str(round(pos, 2))),
            greek_per_unit=Decimal(str(atm['theta'] * 4)),
            theta_impact=Decimal(str(-theta_to_hedge)),
            is_recommended=True,
            pros=["Defined risk", "Collects premium"],
        )
        
        return HedgeRecommendation(
            risk_factor=risk_factor,
            greek_type="theta",
            exposure=total_theta,
            target=target_theta,
            optimizing_for="offset decay with premium collection",
            options=[condor_option],
        )
    
    def calculate_all_hedges(
        self,
        container: RiskFactorContainer,
        market_data: Dict[str, Decimal],
        delta_threshold: Decimal = Decimal('50'),
        gamma_threshold: Decimal = Decimal('5'),
        vega_threshold: Decimal = Decimal('200'),
        theta_threshold: Decimal = Decimal('100'),
    ) -> List[HedgeRecommendation]:
        """Calculate hedges for all risk factors exceeding thresholds"""
        recommendations = []
        
        for factor_id, agg in container.aggregated.items():
            if agg.risk_factor.factor_type != RiskFactorType.UNDERLYING_PRICE:
                continue
            
            underlying = agg.risk_factor.underlying
            spot = market_data.get(underlying, Decimal('100'))
            
            if abs(agg.total_delta) > delta_threshold:
                recommendations.append(self.calculate_delta_hedge(underlying, agg.total_delta, spot))
            
            if abs(agg.total_gamma) > gamma_threshold:
                recommendations.append(self.calculate_gamma_hedge(underlying, agg.total_gamma, spot))
            
            if abs(agg.total_vega) > vega_threshold:
                recommendations.append(self.calculate_vega_hedge(underlying, agg.total_vega, spot))
            
            if abs(agg.total_theta) > theta_threshold:
                recommendations.append(self.calculate_theta_hedge(underlying, agg.total_theta, spot))
        
        return recommendations
