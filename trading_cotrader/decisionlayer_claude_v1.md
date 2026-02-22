## 2. High-Level Architecture

```

┌──────────────────────┐ ← Trading platform (cotrader) (C:\Users\nitin\PythonProjects\eTrading\CLAUDE.md)
│  (HMM-based)               │
│     cotrader         │
│ (execution, broker,  │
│  market data feeds)  │
└─────────┬────────────┘
│
│  In-memory containers
│  (Portfolio, Position, RiskFactor)
▼
┌────────────────────────────┐
│  Market Regime Service     │  ← Independent library (C:\Users\nitin\PythonProjects\eTrading\trading_cotrader\hmm_regime_claude.md)
│  (HMM-based)               │
└─────────┬──────────────────┘
│
▼
┌────────────────────────────┐
│  Decision Agent            │  ← Independent library (This md file is for decision agent)
│  (rule + objective based)  │
└─────────┬──────────────────┘
│
▼
┌────────────────────────────┐← Part of trading platform  (cotrader) (C:\Users\nitin\PythonProjects\eTrading\trading_cotrader\services\trade_booking_service.py)
│  What-if Evaluator         │
│  (PnL, Greeks, Margin)     │
└────────────────────────────┘

````

**Key Design Choice**  
- `cotrader` remains execution-focused  
- **Regime detection and decision intelligence live outside** and are *called* by cotrader

---

## 6. Decision Agent (Not Just a Layer)

### 6.1 Why an Agent?

**Yes — there is real value here**

The agent:
- Maintains internal state
- Evaluates trade-offs
- Explains *why* something was chosen or rejected
- Can evolve without breaking execution logic

This is **agentic design**, not LLM-driven AI.

---

## 7. Decision Agent Responsibilities

### Inputs
- Portfolio container
- Position container
- RiskFactor container
- Regime label (+ confidence)
- Config (YAML limits)

### Outputs
- Ranked list of **candidate actions**
- Each with:
  - Expected PnL
  - Greek impact
  - Margin impact
  - Risk metrics
  - Regime consistency score

---

## 8. Decision Objectives (What Are We Maximizing?)

This is **multi-objective**, not a single scalar.

### Core Objectives

| Objective | Direction |
|--------|-----------|
| Theta / day | Maximize |
| Tail risk | Minimize |
| Margin usage | Minimize |
| Delta drift | Minimize (unless directional regime) |
| Vega exposure | Regime-dependent |
| Portfolio concentration | Minimize |

---

## 9. Candidate Actions (Atomic)

The agent does **not** invent strategies.  
It selects from **atomic actions**.

Examples:
- Open new position (strategy template)
- Hedge delta (same ticker only)
- Roll strike
- Roll duration
- Reduce size
- Close position

Each action is evaluated via **what-if simulation**.

---

## 10. Hedging Rules (Small Account Constraints)

- **Same ticker only**
- No beta-weighted SPX / NDX hedges
- Prefer options over stock for IRA efficiency
- Defined risk preferred over naked

---

## 11. What-If Evaluation Engine

For each candidate action:
- Clone portfolio state
- Apply action
- Recompute:
  - Greeks
  - Margin
  - Max loss
  - PnL distribution (scenario-based)

No Monte Carlo initially — deterministic scenarios only.

---

## 12. External Integration Contracts

### 12.1 Market Regime Service

```python
get_regime(
    ticker: str,
    timestamp: datetime
) -> {
    "regime": "R1 | R2 | R3 | R4",
    "confidence": float,
    "features": dict
}
````

---

### 12.2 Decision Agent

```python
propose_actions(
    portfolio,
    positions,
    risk_factors,
    regime_info
) -> List[ActionProposal]
```

---

## 13. Project Structure (Independent Libraries)

### decision_agent/

```
decision_agent/
├── objectives/
│   └── objective_spec.md
├── actions/
│   └── action_catalog.md
├── evaluator/
│   └── what_if_contract.md
├── agent/
│   └── agent_spec.md
└── README.md
```

---

## 14. Why No Reinforcement Learning (For Now)

RL is *not rejected*, just deferred.

Reasons:

* Sparse rewards
* Regime-conditioned action space
* Hard risk constraints
* Limited data for tail events

This design keeps RL **pluggable later** at the ranking stage.

---

## 15. Final Design Rule

> **If a decision cannot be explained in plain English, it is not allowed in production**

This system is meant to:

* Teach you *how decisions are made*
* Prevent overtrading
* Scale complexity only when justified

---

---

## Example how decision layer will call what if trade function thats in cotrader
Decision Agent
   └── proposes "what-if action"
         └── cotrader simulates it
               └── returns metrics
                     └── Decision Agent ranks & explains


Future-proof

3. Trade = First-Class Object (Your Big Advantage)


The Correct Contract Between Layers
Decision Layer → cotrader

The decision layer sends intent, not implementation.

ActionProposal(
    action_type="OPEN",
    strategy="SHORT_STRANGLE",
    ticker="AAPL",
    params={
        "dte": 30,
        "delta": 0.15,
        "width": None,
        "size": 1
    },
    rationale={
        "regime": "R1",
        "objective": "theta_income"
    }
)
cotrader → Decision Layer

cotrader evaluates the what-if trade using real portfolio logic.

WhatIfResult(
    pnl={
        "expected": 85,
        "stress_down": -420,
        "stress_up": -380
    },
    greeks={
        "delta": +3,
        "theta": +18,
        "vega": -12
    },
    margin={
        "used": 4200,
        "available_after": 15800
    },
    risk_flags=[]
)
Decision Layer Final Output
RankedProposal(
    action=ActionProposal,
    what_if=WhatIfResult,
    score=0.81,
    explanation=[
        "Regime R1 favors theta strategies",
        "Improves portfolio theta by 12%",
        "Margin usage remains below 30%",
        "Downside stress within risk limits"
    ]
)

```
