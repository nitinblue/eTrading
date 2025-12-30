# trading_bot/order_model.py
"""Broker-agnostic order model (universal across brokers)."""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any
from tastytrade.order import PriceEffect  # Used if Tastytrade is active; can be replaced with custom enum

class OrderAction(Enum):
    BUY_TO_OPEN = "BUY_TO_OPEN"
    BUY_TO_CLOSE = "BUY_TO_CLOSE"
    SELL_TO_OPEN = "SELL_TO_OPEN"
    SELL_TO_CLOSE = "SELL_TO_CLOSE"

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

@dataclass
class OrderLeg:
    """Single leg of an order."""
    symbol: str
    quantity: int
    action: OrderAction

@dataclass
class UniversalOrder:
    """Universal order model (broker-agnostic)."""
    legs: List[OrderLeg]
    price_effect: PriceEffect
    order_type: OrderType = OrderType.LIMIT
    limit_price: Optional[float] = None
    time_in_force: str = "DAY"
    dry_run: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "legs": [{"symbol": leg.symbol, "quantity": leg.quantity, "action": leg.action.value} for leg in self.legs],
            "price_effect": self.price_effect.value,
            "order_type": self.order_type.value,
            "limit_price": self.limit_price,
            "time_in_force": self.time_in_force,
            "dry_run": self.dry_run
        }