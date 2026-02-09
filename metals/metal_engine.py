# ===============================
# FILE: metal_engine.py
# ===============================
from dataclasses import dataclass
from typing import List, Optional
from metals.idea_engine import generate_all_ideas


@dataclass
class MarketState:
    price: float
    rsi: float
    macd: float
    macd_signal: float
    iv_rank: Optional[float]
    dxy_trend: str  # up | down | flat

@dataclass
class Decision:
    action: str
    strategy: Optional[str]
    size: float
    rationale: List[str]

class MetalDecisionEngine:
    def __init__(self, config, strategy_defs):
        self.config = config
        self.strategy_defs = strategy_defs

    def decide(self, metal: str, state: MarketState, available_cash: float) -> Decision:
        reasons = []
        bullish = state.macd > state.macd_signal

        # --- DXY gate ---
        if state.dxy_trend == "up":
            reasons.append("DXY trending up – macro headwind")

        # --- Action ---
        if state.rsi < 45 and bullish and state.dxy_trend != "up":
            action = "ACCUMULATE"
        elif state.rsi > 65:
            action = "HARVEST"
            reasons.append("RSI overbought")
        else:
            action = "HOLD"

        # --- Strategy ---
        strategy = None
        if action == "ACCUMULATE":
            if state.iv_rank and state.iv_rank < 50:
                strategy = "LEAPS"
            else:
                strategy = "DIAGONAL"
        elif action == "HARVEST":
            strategy = "COVERED_CALL"

        # --- Size ---
        size = 0
        if action == "ACCUMULATE":
            size = available_cash * self.config["max_trade_fraction"]

        return Decision(action, strategy, size, reasons)