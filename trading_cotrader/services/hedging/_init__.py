"""
Hedging Services
================

Provides hedge calculation and recommendation functionality.

Main classes:
- HedgeCalculator: Calculates hedge recommendations for risk factors
- HedgeRecommendation: A single hedge recommendation
- HedgeOption: A hedge option with analysis
- HedgeType: Types of hedges (STOCK, ATM_CALL, etc.)

Usage:
    from services.hedging import HedgeCalculator
    
    calc = HedgeCalculator()
    reco = calc.calculate_delta_hedge("SPY", Decimal("150"), Decimal("588"))
"""

from trading_cotrader.services.hedging.hedge_calculator import (
    HedgeCalculator,
    HedgeRecommendation,
    HedgeOption,
    HedgeType,
)

__all__ = [
    'HedgeCalculator',
    'HedgeRecommendation', 
    'HedgeOption',
    'HedgeType',
]
