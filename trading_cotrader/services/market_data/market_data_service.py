"""
Market Data Service
===================

Builds and maintains the Market Data Container.

Flow:
    1. Extract unique instruments from all portfolio positions
    2. Register instruments in the registry
    3. Subscribe to DXLink for market data
    4. Update RiskFactors when data arrives
    5. Provide current market snapshot

This is the bridge between:
    - Portfolio positions (from TastyTrade)
    - Instrument registry (our internal model)
    - DXLink streaming (market data source)
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any, Callable

from .instrument_registry import InstrumentRegistry, get_registry
from .domain_models import (
    Instrument, RiskFactor, Greeks, AssetType, OptionType,
    create_stock_instrument, create_equity_option_instrument,
    create_futures_instrument, create_futures_option_instrument
)


@dataclass
class MarketDataContainer:
    """
    The complete market data state.
    
    Contains all instruments with their current market data.
    This is what the UI consumes.
    """
    timestamp: datetime
    instruments: List[Instrument]
    
    # Quick lookups
    by_id: Dict[str, Instrument] = field(default_factory=dict)
    by_underlying: Dict[str, List[Instrument]] = field(default_factory=dict)
    
    # Symbols that need market data from DXLink
    dxlink_symbols: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Build lookup dictionaries."""
        self.by_id = {inst.instrument_id: inst for inst in self.instruments}
        
        self.by_underlying = {}
        for inst in self.instruments:
            underlying = inst.underlying_symbol or inst.ticker
            if underlying not in self.by_underlying:
                self.by_underlying[underlying] = []
            self.by_underlying[underlying].append(inst)
    
    def get_instrument(self, instrument_id: str) -> Optional[Instrument]:
        """Get instrument by ID."""
        return self.by_id.get(instrument_id)
    
    def get_underlyings(self) -> List[str]:
        """Get list of all underlyings."""
        return list(self.by_underlying.keys())
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "instrument_count": len(self.instruments),
            "dxlink_symbol_count": len(self.dxlink_symbols),
            "underlyings": self.get_underlyings(),
            "instruments": [
                {
                    "id": inst.instrument_id,
                    "ticker": inst.ticker,
                    "type": inst.asset_type.value,
                    "strike": float(inst.strike) if inst.strike else None,
                    "expiry": inst.expiry.isoformat() if inst.expiry else None,
                    "dte": inst.days_to_expiry(),
                    "price": float(inst.current_price) if inst.current_price else None,
                    "greeks": {
                        "delta": float(inst.greeks.delta) if inst.greeks else None,
                        "gamma": float(inst.greeks.gamma) if inst.greeks else None,
                        "theta": float(inst.greeks.theta) if inst.greeks else None,
                        "vega": float(inst.greeks.vega) if inst.greeks else None,
                    } if inst.greeks else None
                }
                for inst in self.instruments
            ]
        }


class MarketDataService:
    """
    Service that manages the market data container.
    
    Usage:
        service = MarketDataService()
        
        # Sync from broker positions
        service.sync_from_positions(broker_positions)
        
        # Get current container
        container = service.get_container()
        
        # Update when DXLink sends data
        service.on_quote_update(symbol, bid, ask, mark, iv, greeks)
    """
    
    def __init__(self, registry: Optional[InstrumentRegistry] = None):
        self.registry = registry or get_registry()
        self._last_sync: Optional[datetime] = None
    
    def sync_from_positions(self, positions: List[Dict[str, Any]]) -> int:
        """
        Extract unique instruments from broker positions and register them.
        
        Args:
            positions: List of position dicts from broker adapter.
                       Expected format matches TastyTrade position response.
        
        Returns:
            Number of new instruments registered.
        """
        new_count = 0
        
        for pos in positions:
            instrument = self._position_to_instrument(pos)
            if instrument:
                existing = self.registry.get_by_id(instrument.instrument_id)
                if not existing:
                    self.registry.register(instrument)
                    new_count += 1
        
        # Cleanup expired
        expired = self.registry.cleanup_expired()
        if expired:
            print(f"Cleaned up {len(expired)} expired instruments")
        
        self._last_sync = datetime.now()
        return new_count
    
    def _position_to_instrument(self, position: Dict[str, Any]) -> Optional[Instrument]:
        """
        Convert a broker position to an Instrument.
        
        Handles the mapping from TastyTrade position format to our domain model.
        """
        try:
            symbol = position.get("symbol", "")
            instrument_type = position.get("instrument_type", "").upper()
            
            # Stock
            if instrument_type == "EQUITY":
                return create_stock_instrument(ticker=symbol)
            
            # Equity Option
            elif instrument_type == "EQUITY_OPTION":
                return self._parse_equity_option(position)
            
            # Futures
            elif instrument_type == "FUTURE":
                return self._parse_futures(position)
            
            # Futures Option
            elif instrument_type in ("FUTURE_OPTION", "FUTURES_OPTION"):
                return self._parse_futures_option(position)
            
            # FX - deferred
            elif instrument_type in ("FOREX", "FX"):
                print(f"FX instrument deferred: {symbol}")
                return None
            
            else:
                print(f"Unknown instrument type: {instrument_type} for {symbol}")
                return None
                
        except Exception as e:
            print(f"Error parsing position: {e}")
            return None
    
    def _parse_equity_option(self, position: Dict[str, Any]) -> Instrument:
        """Parse equity option from broker position."""
        symbol = position.get("symbol", "")
        underlying = position.get("underlying_symbol", position.get("root_symbol", ""))
        
        # Parse option details
        strike = Decimal(str(position.get("strike_price", 0)))
        
        # Handle expiry - could be string or date
        expiry_raw = position.get("expiration_date") or position.get("expiry")
        if isinstance(expiry_raw, str):
            expiry = date.fromisoformat(expiry_raw.split("T")[0])
        elif isinstance(expiry_raw, date):
            expiry = expiry_raw
        else:
            raise ValueError(f"Cannot parse expiry: {expiry_raw}")
        
        option_type_str = position.get("option_type", "").upper()
        option_type = OptionType.CALL if option_type_str in ("C", "CALL") else OptionType.PUT
        
        multiplier = int(position.get("multiplier", 100))
        
        return create_equity_option_instrument(
            occ_symbol=symbol,
            ticker=underlying,
            option_type=option_type,
            strike=strike,
            expiry=expiry,
            multiplier=multiplier
        )
    
    def _parse_futures(self, position: Dict[str, Any]) -> Instrument:
        """Parse futures contract from broker position."""
        symbol = position.get("symbol", "")
        root = position.get("root_symbol", symbol.split("/")[0] if "/" in symbol else symbol)
        
        # Futures expiry
        expiry_raw = position.get("expiration_date")
        expiry = None
        if expiry_raw:
            if isinstance(expiry_raw, str):
                expiry = date.fromisoformat(expiry_raw.split("T")[0])
            elif isinstance(expiry_raw, date):
                expiry = expiry_raw
        
        multiplier = int(position.get("multiplier", 1))
        
        return create_futures_instrument(
            symbol=symbol,
            ticker=root,
            multiplier=multiplier,
            expiry=expiry
        )
    
    def _parse_futures_option(self, position: Dict[str, Any]) -> Instrument:
        """Parse futures option from broker position."""
        symbol = position.get("symbol", "")
        underlying_future = position.get("underlying_symbol", "")
        root = position.get("root_symbol", "")
        
        strike = Decimal(str(position.get("strike_price", 0)))
        
        expiry_raw = position.get("expiration_date")
        if isinstance(expiry_raw, str):
            expiry = date.fromisoformat(expiry_raw.split("T")[0])
        elif isinstance(expiry_raw, date):
            expiry = expiry_raw
        else:
            raise ValueError(f"Cannot parse expiry: {expiry_raw}")
        
        option_type_str = position.get("option_type", "").upper()
        option_type = OptionType.CALL if option_type_str in ("C", "CALL") else OptionType.PUT
        
        multiplier = int(position.get("multiplier", 1))
        
        return create_futures_option_instrument(
            occ_symbol=symbol,
            ticker=root,
            futures_symbol=underlying_future,
            option_type=option_type,
            strike=strike,
            expiry=expiry,
            multiplier=multiplier
        )
    
    def get_dxlink_symbols(self) -> List[str]:
        """
        Get list of symbols that need market data from DXLink.
        
        These are the symbols you pass to DXLinkStreamer.get_greeks() or similar.
        Note: We don't manage subscriptions - DXLinkStreamer handles that.
        """
        return self.registry.get_subscription_symbols()
    
    def on_quote_update(
        self,
        symbol: str,
        bid: Decimal,
        ask: Decimal,
        mark: Decimal,
        iv: Optional[Decimal] = None,
        greeks: Optional[Greeks] = None
    ) -> int:
        """
        Handle quote update from DXLink.
        
        Args:
            symbol: The symbol that was updated
            bid, ask, mark: Price data
            iv: Implied volatility (for options)
            greeks: Greeks (for options)
        
        Returns:
            Number of risk factors updated.
        """
        return self.registry.update_market_data(symbol, bid, ask, mark, iv, greeks)
    
    def get_container(self) -> MarketDataContainer:
        """
        Get current market data container.
        
        This is the main output - everything the UI needs.
        """
        return MarketDataContainer(
            timestamp=datetime.now(),
            instruments=self.registry.get_all(),
            dxlink_symbols=self.registry.get_subscription_symbols()
        )
    
    def get_instruments_for_underlying(self, underlying: str) -> List[Instrument]:
        """Get all instruments for a specific underlying."""
        return self.registry.get_instruments_by_underlying(underlying)
    
    def get_summary(self) -> dict:
        """Get summary of current state."""
        summary = self.registry.summary()
        summary["last_sync"] = self._last_sync.isoformat() if self._last_sync else None
        return summary


# =============================================================================
# Convenience function for integration with existing adapter
# =============================================================================

def build_market_data_container(
    positions: List[Dict[str, Any]],
    registry: Optional[InstrumentRegistry] = None
) -> MarketDataContainer:
    """
    One-shot function to build market data container from positions.
    
    Usage:
        positions = await tastytrade_adapter.get_positions()
        container = build_market_data_container(positions)
    """
    service = MarketDataService(registry)
    service.sync_from_positions(positions)
    return service.get_container()
