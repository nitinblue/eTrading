# trading_bot/abstract_broker.py
"""Abstract base class for brokers (agnostic interface)."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict

from trading_bot.order_model import UniversalOrder  # Absolute import (from package root)

class Broker(ABC):
    """Abstract base for broker implementations."""
    @abstractmethod
    def connect(self) -> None:
        """Connect to the broker API."""
        pass

    @abstractmethod
    def get_positions(self) -> List[Dict]:
        """Get current positions."""
        pass

    def response_mapper(self, raw_response: Dict) -> Dict:
        """Map broker-specific response to standardized format (override in implementations)."""
        return raw_response
    
    
    '''
     @abstractmethod
    def get_positions(self, account_id: Optional[str] = None) -> List[Dict]:
        """Get current positions."""
        pass

    @abstractmethod
    def get_account_balance(self, account_id: Optional[str] = None) -> Dict:
        """Get account balance."""
        pass

    @abstractmethod
    def execute_order(self, order: UniversalOrder, account_id: Optional[str] = None) -> Dict:
        """Execute an order."""
        pass

    def response_mapper(self, raw_response: Dict) -> Dict:
        """Map broker-specific response to standardized format (override in implementations)."""
        return raw_response
    '''