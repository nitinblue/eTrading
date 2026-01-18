from dataclasses import dataclass
from enum import Enum
from typing import List
from .legs import TradeLeg


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass
class Order:
    order_id: str
    account_id: str
    legs: List[TradeLeg]
    order_type: OrderType
    limit_price: float | None = None
