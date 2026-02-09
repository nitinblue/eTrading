# Metals Options Portfolio System

This document is the **single source of truth** for how your metals options portfolio is built, managed, and executed day‑to‑day. It combines **investment philosophy, systematic rules, and the refactored Python engine logic** so you can deploy immediately and evolve safely.

---

## 1. Objective

- Express **long‑term bullish view on metals** without owning physical metals
- Use **options as the primary vehicle** (capital‑efficient, defined risk)
- Separate **slow, convex capital (IRA)** from **faster, opportunistic capital (Personal)**
- Make decisions that are:
  - Repeatable
  - Rule‑driven
  - Explainable (including *why not to trade*)

Universe:
- **GLD (Gold)**
- **SLV (Silver)**
- **CPER (Copper)**
- **DXY (Dollar Index – regime filter)**

---

## 2. Account Architecture

### 2.1 IRA Account – $200k

**Mandate:** Long‑term exposure with controlled drawdowns and low turnover

| Metal | Target Allocation |
|-----|------------------|
| GLD | 40% |
| SLV | 35% |
| CPER | 25% |

**Strategy Mix**
- 50% LEAPS Calls (core exposure)
- 30% Diagonals / Calendars (theta + cost reduction)
- 20% Covered Calls (income when extended)

Constraints:
- No naked short options
- Position size capped per metal

---

### 2.2 Personal Account – $30k

**Mandate:** Higher velocity, higher risk tolerance

**Strategy Mix**
- 35% Calendars / Diagonals
- 25% Smaller LEAPS
- 20% Wheel (GLD, SLV only)
- 20% Tactical call spreads

Rules:
- CPER: no wheel, spreads only
- Always defined risk

---

## 3. Daily / Weekly Decision Framework

Each cycle the system evaluates **five layers** per metal.

### 3.1 Regime Detection

Inputs:
- RSI (14)
- MACD (12/26/9)
- 50 / 200 DMA slope
- IV Rank
- DXY trend

Outputs:
- Trend: Bull / Pullback / Range / Breakdown
- Volatility: Low / Normal / High

---

### 3.2 Action Decision

One of:
- **ACCUMULATE** (add exposure)
- **HOLD** (manage existing positions)
- **HARVEST** (sell premium / reduce risk)
- **AVOID** (no new trades)

The engine must explicitly choose one.

---

### 3.3 Strategy Selection Logic

| Market State | Preferred Strategy |
|------------|------------------|
| Pullback + Bullish | LEAPS |
| Range + High IV | Calendar / Diagonal |
| Extended + Bullish | Covered Call / Call Spread |
| High IV + Unclear Trend | Avoid |

---

### 3.4 Sizing Rules

Global caps (from config):
- Max trade fraction
- Max metal exposure
- Max strategy exposure

Sizing formula:
```
trade_size = min(
  available_cash * max_trade_fraction,
  remaining_metal_cap,
  remaining_strategy_cap
)
```

---

### 3.5 Exit Rules (Defined at Entry)

- **Profit target:** 50–80% on premium
- **Time stop:** 40–50% of DTE used
- **Trend stop:** Break of 200 DMA
- **Volatility stop:** IV crush after event

---

## 4. Dollar Index (DXY) – Global Gate

DXY is not a trade signal, it is a **permission filter**.

Rules:
- DXY trending UP → reduce long premium, favor spreads
- DXY trending DOWN → allow LEAPS and aggressive calendars

If DXY contradicts metals signal → downgrade action by one level
(e.g. ACCUMULATE → HOLD)

---

## 5. Engine Outputs (Every Cycle)

For each metal:

- Market snapshot
- Action decision
- Eligible strategies
- **Examples of valid trades**
- **Explicit reasons trades are NOT taken**

Example output:
> "GLD: RSI 62, IV Rank 58, price extended above 50 DMA → Avoid LEAPS. Prefer waiting for pullback or using call spreads only."

---

## 6. Refactored Python Engine (Core Logic)

Below is the refactored **decision engine skeleton** that replaces ad‑hoc suggestions with a rule‑driven system. This plugs into your existing data fetch and broker adapter.

```python
# metal_engine.py

from dataclasses import dataclass
from typing import Dict, List

@dataclass
class MarketState:
    price: float
    rsi: float
    macd: float
    macd_signal: float
    iv_rank: float | None
    dxy_trend: str  # up / down / flat

@dataclass
class Decision:
    action: str
    strategy: str | None
    size: float
    rationale: List[str]

class MetalDecisionEngine:
    def __init__(self, config, strategy_defs):
        self.config = config
        self.strategy_defs = strategy_defs

    def decide(self, metal: str, state: MarketState, available_cash: float) -> Decision:
        reasons = []

        # 1. Regime
        bullish = state.macd > state.macd_signal

        # 2. DXY gate
        if state.dxy_trend == "up":
            reasons.append("DXY trending up – headwind for metals")

        # 3. Action logic
        if state.rsi < 45 and bullish and state.dxy_trend != "up":
            action = "ACCUMULATE"
        elif state.rsi > 65:
            action = "HARVEST"
            reasons.append("RSI overbought")
        else:
            action = "HOLD"

        # 4. Strategy selection
        strategy = None
        if action == "ACCUMULATE":
            strategy = "LEAPS" if state.iv_rank and state.iv_rank < 50 else "DIAGONAL"
        elif action == "HARVEST":
            strategy = "COVERED_CALL"

        # 5. Position sizing
        max_trade = available_cash * self.config["max_trade_fraction"]

        return Decision(
            action=action,
            strategy=strategy,
            size=max_trade if action == "ACCUMULATE" else 0,
            rationale=reasons
        )
```

This engine:
- Separates **signal → decision → execution**
- Makes "no trade" a first‑class output
- Is safe to deploy incrementally

---

## 7. Day‑to‑Day Operating Guide

**Daily (5–10 min):**
- Run engine
- Read rationale output
- Do nothing unless ACCUMULATE or HARVEST

**Weekly (30 min):**
- Review exposure vs targets
- Roll short legs
- Trim winners

**Monthly (1 hr):**
- Rebalance metal allocations
- Roll LEAPS if < 12 months remaining

---

## 8. Guiding Principles (Non‑Negotiable)

- Cash is a position
- Defined risk always
- Let trends pay, not opinions
- Most money is made by **not trading**

---

This document evolves, but it should **never lose its structure**. Any future change must clearly answer:
> Does this improve decision quality or just add activity?


2️⃣ Trade Families You Will Always Generate

Every cycle, for each metal, generate at least one example of:

## 8. Possible trade Strategies
Strategy	    Purpose
LEAPS Call	    Core long exposure
Diagonal Call	Income + upside
Calendar Call	Volatility / timing
Bull Call Spread	Cheap directional
Wheel Entry (CSP)	Asset acquisition