"""
Options Pricing Module

Provides:
- Black-Scholes model implementation
- Greeks calculations
- Implied volatility solver
- Probability calculations (POP, expected move)
- Scenario analysis (what-if)

Usage:
    from trading_cotrader.services.pricing.probability import ProbabilityCalculator
    from trading_cotrader.services.pricing.black_scholes import BlackScholesModel
"""

# Lazy imports — some sub-modules use old-style paths (services.pricing.*)
# that only resolve when running from the project root. Wrap in try/except
# so direct module imports (e.g. from ...probability import X) still work.
try:
    from trading_cotrader.services.pricing.black_scholes import BlackScholesModel, OptionPrice, BSGreeks
    from trading_cotrader.services.pricing.greeks import GreeksCalculator, PositionGreeks
    from trading_cotrader.services.pricing.implied_vol import ImpliedVolCalculator, IVSurface
    from trading_cotrader.services.pricing.probability import ProbabilityCalculator, ProbabilityResult
    from trading_cotrader.services.pricing.scenarios import ScenarioEngine, WhatIfResult, Scenario
except ImportError:
    try:
        from services.pricing.black_scholes import BlackScholesModel, OptionPrice, BSGreeks
        from services.pricing.greeks import GreeksCalculator, PositionGreeks
        from services.pricing.implied_vol import ImpliedVolCalculator, IVSurface
        from services.pricing.probability import ProbabilityCalculator, ProbabilityResult
        from services.pricing.scenarios import ScenarioEngine, WhatIfResult, Scenario
    except ImportError:
        pass  # Individual module imports will still work

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
