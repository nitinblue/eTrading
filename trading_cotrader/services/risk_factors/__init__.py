"""
Risk Factors Module - 2D Matrix Structure
=========================================

Core concept from institutional_trading_v4.py:
- Y-axis: Unique instruments (keyed by streamer_symbol)
- X-axis: Greeks per underlying (Delta_MSFT, Gamma_MSFT, etc.)

Usage:
    from services.risk_factors import RiskFactorMatrix, InstrumentRiskRow
    
    # Build the matrix
    matrix = RiskFactorMatrix()
    
    matrix.add_instrument(
        streamer_symbol="MSFT  260321C00400000",
        position_quantity=100,
        multiplier=100,
        underlying="MSFT",
        delta=Decimal("0.65"),
        gamma=Decimal("0.015"),
        theta=Decimal("-0.45"),
        vega=Decimal("0.25"),
    )
    
    # Get aggregated risk factors
    aggregated = matrix.get_aggregated_risk_factors()
    # {'MSFT': AggregatedRiskFactor(total_delta=6500, ...), ...}
    
    # Get portfolio totals
    totals = matrix.get_portfolio_totals()
    # {'delta': 6500, 'gamma': 150, 'theta': -4500, ...}
    
    # Get factors needing hedge
    needs_hedge = matrix.get_factors_needing_hedge(delta_threshold=Decimal('100'))
"""

from trading_cotrader.services.risk_factors.models import (
    # Core classes
    RiskFactorMatrix,
    InstrumentRiskRow,
    AggregatedRiskFactor,
    RiskFactorType,
    
    # Factory functions
    create_risk_matrix_from_positions,
    create_underlying_price_factor,
    
    # Backward compatibility aliases
    RiskFactorContainer,  # Alias for RiskFactorMatrix
    InstrumentSensitivity,  # Alias for InstrumentRiskRow
    RiskFactor,  # Alias for AggregatedRiskFactor
)

__all__ = [
    # Primary classes
    'RiskFactorMatrix',
    'InstrumentRiskRow', 
    'AggregatedRiskFactor',
    'RiskFactorType',
    
    # Factory functions
    'create_risk_matrix_from_positions',
    'create_underlying_price_factor',
    
    # Backward compatibility
    'RiskFactorContainer',
    'InstrumentSensitivity',
    'RiskFactor',
]
