"""
Hedging Module
==============

Provides hedge calculation at the instrument level.

Usage:
    from hedging import HedgeCalculator, RiskBucket, HedgeRecommendation
    
    calc = HedgeCalculator(registry)
    hedge = calc.calculate_delta_hedge("SPY", current_delta=-1.5, underlying_price=588.25)
"""

from trading_cotrader.services.hedging.hedge_calculator import (
    HedgeType,
    HedgeRecommendation,
    HedgeCalculator,
)

__all__ = [
    "HedgeType",
    "HedgeRecommendation",
    "HedgeCalculator",
]
    
    
    #"RiskBucket",