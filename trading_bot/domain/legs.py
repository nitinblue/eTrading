from dataclasses import dataclass
from enum import Enum
from .instruments import Instrument


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True)
class TradeLeg:
    instrument: Instrument
    side: Side
    quantity: int
    price: float | None = None   # filled at execution
