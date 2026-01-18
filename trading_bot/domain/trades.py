from dataclasses import dataclass, field
from enum import Enum
from typing import List
from uuid import uuid4

from .legs import TradeLeg
from .risk import RiskProfile


class StrategyType(str, Enum):
    STOCK = "STOCK"
    COVERED_CALL = "COVERED_CALL"
    CSP = "CSP"
    VERTICAL = "VERTICAL"
    IRON_CONDOR = "IRON_CONDOR"
    STRANGLE = "STRANGLE"


class TradeStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"


@dataclass
class Trade:
    trade_id: str = field(default_factory=lambda: str(uuid4()))
    strategy: StrategyType = StrategyType.STOCK
    legs: List[TradeLeg] = field(default_factory=list)
    risk: RiskProfile | None = None
    status: TradeStatus = TradeStatus.PROPOSED
    notes: str = ""
