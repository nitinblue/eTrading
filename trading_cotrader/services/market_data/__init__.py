"""
Market Data Module
==================

Provides the Market Data Container functionality:
    - Instrument and RiskFactor domain models
    - InstrumentRegistry for tracking unique instruments
    - MarketDataService for building the container

Usage:
    from market_data import (
        MarketDataService,
        InstrumentRegistry,
        Instrument,
        RiskFactor,
        build_market_data_container
    )
    
    # Option 1: Use the service
    service = MarketDataService()
    service.sync_from_positions(broker_positions)
    container = service.get_container()
    
    # Option 2: One-shot function
    container = build_market_data_container(broker_positions)
"""

# Domain models
from .domain_models import (
    # Enums
    AssetType,
    OptionType,
    RiskFactorType,
    
    # Core classes
    Greeks,
    RiskFactor,
    Instrument,
    RiskFactorResolver,
    
    # Factory functions
    create_stock_instrument,
    create_equity_option_instrument,
    create_futures_instrument,
    create_futures_option_instrument,
)

# Registry
from .instrument_registry import (
    InstrumentRegistry,
    get_registry,
    reset_registry,
)

# Service
from .market_data_service import (
    MarketDataContainer,
    MarketDataService,
    build_market_data_container,
)

__all__ = [
    # Enums
    "AssetType",
    "OptionType", 
    "RiskFactorType",
    
    # Core classes
    "Greeks",
    "RiskFactor",
    "Instrument",
    "RiskFactorResolver",
    "InstrumentRegistry",
    "MarketDataContainer",
    "MarketDataService",
    
    # Factory functions
    "create_stock_instrument",
    "create_equity_option_instrument",
    "create_futures_instrument",
    "create_futures_option_instrument",
    
    # Convenience
    "get_registry",
    "reset_registry",
    "build_market_data_container",
]
