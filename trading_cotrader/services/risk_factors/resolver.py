"""
Risk Factor Resolver

Maps dm.Position objects to their constituent risk factors.
Uses existing analytics/greeks/engine.py for calculations when needed.
"""

from decimal import Decimal
from typing import List, Optional
import logging

from trading_cotrader.services.risk_factors.models import (
    RiskFactor, RiskFactorType, InstrumentSensitivity,
    create_underlying_price_factor
)

import trading_cotrader.core.models.domain as dm

logger = logging.getLogger(__name__)


class RiskFactorResolver:
    """
    Resolves Position objects to risk factor sensitivities.
    
    Usage:
        resolver = RiskFactorResolver()
        for position in positions:
            sensitivities = resolver.resolve_position(position)
            for sens in sensitivities:
                container.add_sensitivity(sens)
    """
    
    def resolve_position(self, position: 'dm.Position') -> List[InstrumentSensitivity]:
        """
        Resolve a Position to its risk factor sensitivities.
        
        Args:
            position: dm.Position object with symbol and greeks
            
        Returns:
            List of InstrumentSensitivity objects
        """
        if dm is None:
            logger.error("Domain models not available")
            return []
        
        symbol = position.symbol
        greeks = position.greeks
        quantity = position.quantity
        
        # Get instrument ID
        if symbol.asset_type == dm.AssetType.OPTION:
            instrument_id = symbol.get_option_symbol()
        else:
            instrument_id = symbol.ticker
        
        # Get multiplier
        multiplier = symbol.multiplier or 100
        
        # Resolve based on asset type
        if symbol.asset_type == dm.AssetType.EQUITY:
            return self._resolve_equity(instrument_id, symbol.ticker, quantity, multiplier)
        
        elif symbol.asset_type == dm.AssetType.OPTION:
            return self._resolve_option(
                instrument_id, 
                symbol.ticker,
                quantity, 
                multiplier,
                greeks
            )
        
        elif symbol.asset_type == dm.AssetType.FUTURE:
            return self._resolve_future(instrument_id, symbol.ticker, quantity, multiplier)
        
        elif hasattr(dm.AssetType, 'FUTURE_OPTION') and symbol.asset_type == dm.AssetType.FUTURE_OPTION:
            return self._resolve_option(instrument_id, symbol.ticker, quantity, multiplier, greeks)
        
        else:
            logger.warning(f"Unknown asset type: {symbol.asset_type}")
            return []
    
    def _resolve_equity(
        self, 
        instrument_id: str, 
        ticker: str, 
        quantity: int,
        multiplier: int = 1
    ) -> List[InstrumentSensitivity]:
        """Equity → single UNDERLYING_PRICE factor with delta = 1"""
        factor = create_underlying_price_factor(ticker)
        
        sensitivity = InstrumentSensitivity(
            instrument_id=instrument_id,
            instrument_description=f"{ticker} stock",
            risk_factor=factor,
            delta=Decimal('1'),
            gamma=Decimal('0'),
            theta=Decimal('0'),
            vega=Decimal('0'),
            rho=Decimal('0'),
            position_quantity=quantity,
            multiplier=multiplier,
        )
        
        return [sensitivity]
    
    def _resolve_option(
        self,
        instrument_id: str,
        underlying: str,
        quantity: int,
        multiplier: int,
        greeks: Optional['dm.Greeks']
    ) -> List[InstrumentSensitivity]:
        """Option → UNDERLYING_PRICE factor with Greeks from position"""
        
        # Extract Greeks (handle None)
        delta = Decimal(str(greeks.delta)) if greeks and greeks.delta else Decimal('0')
        gamma = Decimal(str(greeks.gamma)) if greeks and greeks.gamma else Decimal('0')
        theta = Decimal(str(greeks.theta)) if greeks and greeks.theta else Decimal('0')
        vega = Decimal(str(greeks.vega)) if greeks and greeks.vega else Decimal('0')
        rho = Decimal(str(greeks.rho)) if greeks and greeks.rho else Decimal('0')
        
        factor = create_underlying_price_factor(underlying)
        
        sensitivity = InstrumentSensitivity(
            instrument_id=instrument_id,
            instrument_description=f"{underlying} option",
            risk_factor=factor,
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho,
            position_quantity=quantity,
            multiplier=multiplier,
        )
        
        return [sensitivity]
    
    def _resolve_future(
        self,
        instrument_id: str,
        underlying: str,
        quantity: int,
        multiplier: int
    ) -> List[InstrumentSensitivity]:
        """Future → single UNDERLYING_PRICE factor with delta = 1"""
        factor = create_underlying_price_factor(underlying)
        
        sensitivity = InstrumentSensitivity(
            instrument_id=instrument_id,
            instrument_description=f"{underlying} future",
            risk_factor=factor,
            delta=Decimal('1'),
            gamma=Decimal('0'),
            theta=Decimal('0'),
            vega=Decimal('0'),
            rho=Decimal('0'),
            position_quantity=quantity,
            multiplier=multiplier,
        )
        
        return [sensitivity]


def resolve_positions_to_container(positions: List['dm.Position']) -> 'RiskFactorContainer':
    """
    Convenience function: resolve positions and return populated container.
    
    Usage:
        container = resolve_positions_to_container(positions)
        print(container.get_total_delta_by_underlying())
    """
    from services.risk_factors.models import RiskFactorContainer
    
    resolver = RiskFactorResolver()
    container = RiskFactorContainer()
    
    for position in positions:
        sensitivities = resolver.resolve_position(position)
        for sens in sensitivities:
            container.add_sensitivity(sens)
    
    return container
