from dataclasses import dataclass
from typing import Optional

from trading_bot.domain.instruments import Instrument


@dataclass
class Position:
    """
    Position = Instrument + quantity + PnL + Greeks
    """

    instrument: Instrument
    quantity: int

    avg_price: Optional[float] = None
    market_price: Optional[float] = None

    unrealized_pnl: Optional[float] = None
    realized_pnl: Optional[float] = None

    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
