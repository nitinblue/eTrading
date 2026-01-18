from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


class RiskType(str, Enum):
    DEFINED = "defined"
    UNDEFINED = "undefined"


class TradeStatus(str, Enum):
    IDEA = "idea"
    VALIDATED = "validated"
    REJECTED = "rejected"
    EXECUTED = "executed"


@dataclass
class TradeIdea:
    symbol: str
    strategy: str
    risk_type: RiskType
    max_loss: float
    prob_profit: float
    metadata: dict
    status: TradeStatus = TradeStatus.IDEA


@dataclass
class Order:
    symbol: str
    quantity: int
    order_type: str   # MARKET / LIMIT
    price: Optional[float]
    broker_payload: dict


@dataclass
class Position:
    symbol: str
    quantity: int
    avg_price: float
    unrealized_pnl: float
    broker_position_id: str
