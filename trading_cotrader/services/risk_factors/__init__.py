"""
Risk Factors Module

Provides risk-factor-based portfolio analysis.

Usage:
    from services.risk_factors import RiskFactorResolver, RiskFactorContainer
    
    # Resolve positions to risk factors
    resolver = RiskFactorResolver()
    container = RiskFactorContainer()
    
    for position in positions:
        sensitivities = resolver.resolve_position(position)
        for sens in sensitivities:
            container.add_sensitivity(sens)
    
    # Get aggregated risk by underlying
    greeks_by_underlying = container.get_total_greeks_by_underlying()
    # {'MSFT': {'delta': 150, 'gamma': 2.5, ...}, ...}
    
    # Get portfolio totals
    totals = container.get_portfolio_totals()
    # {'delta': 150, 'gamma': 2.5, 'theta': -45, ...}
    
    # Quick helper
    from services.risk_factors import resolve_positions_to_container
    container = resolve_positions_to_container(positions)
"""

from services.risk_factors.models import (
    RiskFactorType,
    RiskFactor,
    InstrumentSensitivity,
    AggregatedRiskFactor,
    RiskFactorContainer,
    create_underlying_price_factor,
)

from services.risk_factors.resolver import (
    RiskFactorResolver,
    resolve_positions_to_container,
)

__all__ = [
    'RiskFactorType',
    'RiskFactor',
    'InstrumentSensitivity',
    'AggregatedRiskFactor',
    'RiskFactorContainer',
    'RiskFactorResolver',
    'resolve_positions_to_container',
    'create_underlying_price_factor',
]
