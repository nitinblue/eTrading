# domain/models.py
from dataclasses import dataclass
from typing import Literal

StrategyType = Literal[
    "IRON_CONDOR",
    "VERTICAL",
    "CSP",
    "COVERED_CALL",
    "STRANGLE"
]

RiskType = Literal["DEFINED", "UNDEFINED"]

@dataclass(frozen=True)
class Trade:
    trade_id: str
    symbol: str
    strategy: StrategyType
    risk_type: RiskType

    credit: float
    max_loss: float           # defined OR modeled
    delta: float
    dte: int

    sector: str
