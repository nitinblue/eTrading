from dataclasses import dataclass
from typing import List, Optional

@dataclass
class TradeIdea:
    underlying: str
    strategy: str
    legs: List["OptionSnapshot"]
    verdict: str                  # APPROVED | WAIT | AVOID
    why: List[str]
    notes: Optional[List[str]] = None


@dataclass
class OptionSnapshot:
    symbol: str
    expiry: str
    strike: float
    option_type: str
    price: float | None
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None
    iv: float | None

@dataclass
class TradeIdea:
    underlying: str
    strategy: str
    legs: List[OptionSnapshot]
    verdict: str              # APPROVED | WAIT | AVOID
    why: List[str]
