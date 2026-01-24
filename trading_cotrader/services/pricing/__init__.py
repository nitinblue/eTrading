"""
Options Pricing Module

Provides:
- Black-Scholes model implementation
- Greeks calculations
- Implied volatility solver
- Probability calculations (POP, expected move)
- Scenario analysis (what-if)

Usage:
    from services.pricing import BlackScholesModel, ProbabilityCalculator
    
    bs = BlackScholesModel()
    price = bs.price(spot=100, strike=105, tte=0.25, rate=0.05, vol=0.2, opt_type='call')
    greeks = bs.greeks(spot=100, strike=105, tte=0.25, rate=0.05, vol=0.2, opt_type='call')
    
    prob = ProbabilityCalculator()
    pop = prob.probability_of_profit(trade, current_price=100, iv=0.25)
"""

from services.pricing.black_scholes import BlackScholesModel, OptionPrice, BSGreeks
from services.pricing.greeks import GreeksCalculator, PositionGreeks
from services.pricing.implied_vol import ImpliedVolCalculator, IVSurface
from services.pricing.probability import ProbabilityCalculator, ProbabilityResult
from services.pricing.scenarios import ScenarioEngine, WhatIfResult, Scenario

__all__ = [
    'BlackScholesModel',
    'OptionPrice',
    'BSGreeks',
    'GreeksCalculator',
    'PositionGreeks',
    'ImpliedVolCalculator',
    'IVSurface',
    'ProbabilityCalculator',
    'ProbabilityResult',
    'ScenarioEngine',
    'WhatIfResult',
    'Scenario',
]
