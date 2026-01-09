# domain/portfolio.py
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class PortfolioState:
    trades: List
    realized_pnl: float
    unrealized_pnl: float
