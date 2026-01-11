from dataclasses import dataclass
from enum import Enum


class RiskType(str, Enum):
    DEFINED = "DEFINED"
    UNDEFINED = "UNDEFINED"


@dataclass(frozen=True)
class RiskProfile:
    risk_type: RiskType
    max_loss: float
    buying_power: float
    probability_of_profit: float | None = None
    delta: float | None = None
    theta: float | None = None
    vega: float | None = None
