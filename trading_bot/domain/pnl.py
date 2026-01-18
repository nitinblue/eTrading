from dataclasses import dataclass


@dataclass(frozen=True)
class PnL:
    unrealized: float
    realized: float
    theta: float | None = None
    delta: float | None = None
    vega: float | None = None
