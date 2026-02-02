"""
Instrument Registry
===================

Central store for all active instruments across portfolios.

Responsibilities:
    - Track unique instruments (no duplicates)
    - Manage RiskFactor resolution
    - Cleanup expired instruments
    - Provide subscription list for DXLink
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, List, Dict, Set

from .domain_models import (
    Instrument, RiskFactor, RiskFactorType, RiskFactorResolver
)


@dataclass
class InstrumentRegistry:
    """
    Central store for all active instruments.
    
    Usage:
        registry = InstrumentRegistry()
        registry.register(instrument)
        
        # Get all symbols to subscribe via DXLink
        symbols = registry.get_subscription_symbols()
        
        # Cleanup expired
        expired = registry.cleanup_expired()
    """
    instruments: Dict[str, Instrument] = field(default_factory=dict)
    
    # Track which risk factor symbols we're subscribed to
    _subscribed_symbols: Set[str] = field(default_factory=set)
    
    def register(self, instrument: Instrument) -> Instrument:
        """
        Register an instrument. If already registered, return existing.
        Also resolves and attaches RiskFactors.
        
        Returns the registered instrument (may be existing one if duplicate).
        """
        if instrument.instrument_id in self.instruments:
            return self.instruments[instrument.instrument_id]
        
        # Resolve risk factors if not already done
        if not instrument.risk_factors:
            instrument.risk_factors = RiskFactorResolver.resolve(instrument)
        
        self.instruments[instrument.instrument_id] = instrument
        
        # Track new symbols for subscription
        for rf in instrument.risk_factors:
            self._subscribed_symbols.add(rf.symbol)
        
        return instrument
    
    def register_many(self, instruments: List[Instrument]) -> List[Instrument]:
        """Register multiple instruments at once."""
        return [self.register(inst) for inst in instruments]
    
    def unregister(self, instrument_id: str) -> Optional[Instrument]:
        """
        Remove an instrument from the registry.
        
        Note: Does not remove symbols from subscription set (other instruments may use them).
        Call rebuild_subscriptions() after bulk unregister if needed.
        """
        return self.instruments.pop(instrument_id, None)
    
    def get_by_id(self, instrument_id: str) -> Optional[Instrument]:
        """Look up instrument by ID."""
        return self.instruments.get(instrument_id)
    
    def get_all(self) -> List[Instrument]:
        """Get all registered instruments."""
        return list(self.instruments.values())
    
    def get_subscription_symbols(self) -> List[str]:
        """
        Get all unique symbols that need DXLink subscription.
        
        This is the list you pass to DXLink to subscribe for market data.
        """
        return list(self._subscribed_symbols)
    
    def get_all_risk_factors(self) -> List[RiskFactor]:
        """
        Get all unique risk factors across all instruments.
        
        Useful for iterating through to update market data.
        """
        seen_symbols: Set[str] = set()
        factors: List[RiskFactor] = []
        
        for inst in self.instruments.values():
            for rf in inst.risk_factors:
                if rf.symbol not in seen_symbols:
                    seen_symbols.add(rf.symbol)
                    factors.append(rf)
        
        return factors
    
    def rebuild_subscriptions(self):
        """
        Rebuild the subscription symbol set from current instruments.
        
        Call this after bulk unregister operations.
        """
        self._subscribed_symbols.clear()
        for inst in self.instruments.values():
            for rf in inst.risk_factors:
                self._subscribed_symbols.add(rf.symbol)
    
    def cleanup_expired(self, as_of: Optional[date] = None) -> List[Instrument]:
        """
        Remove expired instruments.
        
        Returns list of removed instruments (useful for logging).
        """
        check_date = as_of or date.today()
        expired = [
            inst for inst in self.instruments.values() 
            if inst.is_expired(check_date)
        ]
        
        for inst in expired:
            del self.instruments[inst.instrument_id]
        
        # Rebuild subscriptions since we removed instruments
        if expired:
            self.rebuild_subscriptions()
        
        return expired
    
    def get_instruments_by_underlying(self, underlying_symbol: str) -> List[Instrument]:
        """
        Get all instruments for a given underlying.
        
        Useful for:
            - Hedging: find all positions exposed to SPY
            - Risk aggregation: sum Greeks by underlying
        """
        return [
            inst for inst in self.instruments.values()
            if inst.underlying_symbol == underlying_symbol or inst.ticker == underlying_symbol
        ]
    
    def get_instruments_by_type(self, asset_type) -> List[Instrument]:
        """Get all instruments of a specific asset type."""
        return [
            inst for inst in self.instruments.values()
            if inst.asset_type == asset_type
        ]
    
    def get_expiring_soon(self, days: int = 7, as_of: Optional[date] = None) -> List[Instrument]:
        """Get instruments expiring within N days."""
        check_date = as_of or date.today()
        return [
            inst for inst in self.instruments.values()
            if inst.expiry and 0 <= (inst.expiry - check_date).days <= days
        ]
    
    def find_risk_factor(self, symbol: str) -> Optional[RiskFactor]:
        """
        Find a RiskFactor by its symbol across all instruments.
        
        Useful for updating market data: when DXLink sends quote for "MSFT",
        find the RiskFactor to update.
        """
        for inst in self.instruments.values():
            for rf in inst.risk_factors:
                if rf.symbol == symbol:
                    return rf
        return None
    
    def update_market_data(self, symbol: str, bid, ask, mark, iv=None, greeks=None):
        """
        Update market data for a symbol across all instruments that use it.
        
        This is called when DXLink sends a quote update.
        """
        updated_count = 0
        for inst in self.instruments.values():
            for rf in inst.risk_factors:
                if rf.symbol == symbol:
                    rf.update_market_data(bid, ask, mark, iv, greeks)
                    updated_count += 1
        return updated_count
    
    @property
    def count(self) -> int:
        """Number of registered instruments."""
        return len(self.instruments)
    
    @property
    def subscription_count(self) -> int:
        """Number of unique symbols to subscribe."""
        return len(self._subscribed_symbols)
    
    def summary(self) -> dict:
        """Get summary statistics."""
        from collections import Counter
        type_counts = Counter(inst.asset_type.value for inst in self.instruments.values())
        
        return {
            "total_instruments": self.count,
            "subscription_symbols": self.subscription_count,
            "by_type": dict(type_counts),
            "expiring_7d": len(self.get_expiring_soon(7))
        }


# Singleton instance for the application
_registry: Optional[InstrumentRegistry] = None


def get_registry() -> InstrumentRegistry:
    """Get the global instrument registry instance."""
    global _registry
    if _registry is None:
        _registry = InstrumentRegistry()
    return _registry


def reset_registry():
    """Reset the global registry (useful for testing)."""
    global _registry
    _registry = InstrumentRegistry()
