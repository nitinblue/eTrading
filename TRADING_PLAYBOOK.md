# Trading Playbook — Agent Operations Manual
> How the CoTrader agents operate your portfolios. What happens at each step. When you get notified. What you need to decide.
>
> Last updated: February 16, 2026 (session 16)

---

## 1. System Overview

CoTrader is a **continuous workflow engine** that manages 10 portfolios across 4 brokers. It runs a state machine loop during market hours, pausing only when it needs your decision. You don't run CLI commands. You respond to the agent.

```
Start:  python -m trading_cotrader.runners.run_workflow --web --port 8080
Single: python -m trading_cotrader.runners.run_workflow --once --no-broker --mock
```

### The Loop

```
IDLE → BOOT → MACRO_CHECK → SCREENING → RECOMMENDATION_REVIEW (⏸ YOU) → EXECUTION
                                                                              ↓
                   REPORTING ← EOD_EVALUATION ← MONITORING ← ←←←←←←←←←←←←←←←
                       ↓              ↓
                     IDLE      TRADE_MANAGEMENT → TRADE_REVIEW (⏸ YOU) → EXECUTION → MONITORING
```

**Two pause points.** Everything else is autonomous.

| State | What Happens | Duration | Your Action |
|-------|-------------|----------|-------------|
| BOOT | Calendar, market data, portfolio state, circuit breakers, capital check, session objectives | ~10 sec | None |
| MACRO_CHECK | VIX regime assessment, risk_on/off gate | ~2 sec | None (auto-skip if risk_off) |
| SCREENING | Run screeners for today's cadences, risk analysis | ~5 sec | None |
| **RECOMMENDATION_REVIEW** | **Workflow pauses. Presents recommendations.** | **Until you act** | **approve / reject / defer** |
| EXECUTION | Books approved trades (paper mode), Guardian safety check | ~3 sec | None |
| MONITORING | Home state. Refreshes every 30 min. Checks exits. | 30 min cycles | Status check anytime |
| TRADE_MANAGEMENT | Evaluates all open positions against exit rules | ~5 sec | None |
| **TRADE_REVIEW** | **Workflow pauses. Presents exit signals.** | **Until you act** | **approve / reject / defer** |
| EOD_EVALUATION | Final position check at 3:30 PM ET | ~5 sec | None |
| REPORTING | Daily summary, accountability, capital efficiency, QA, agent grades | ~15 sec | Read report |
| HALTED | Circuit breaker tripped or manual halt | Until you resume | **resume --rationale "..."** |

---

## 2. Boot Sequence (9:25 AM ET)

15 agents initialize. Here's what each does and what you see:

### Step 1: Calendar Check
```
┌─────────────────────────────────────────────────┐
│ CALENDAR                                         │
│ Trading day:  YES                                │
│ Cadences:     [0dte, weekly]                     │
│ FOMC today:   NO                                 │
│ Minutes to close: 390                            │
└─────────────────────────────────────────────────┘
```
- Non-trading day (NYSE holiday) → skips to IDLE immediately
- FOMC day → blocks 0DTE trades (`skip_0dte_on_fomc: true` in YAML)

### Step 2: Market Data
```
┌─────────────────────────────────────────────────┐
│ MARKET DATA                                      │
│ Fetched 3/3 snapshots (SPY, QQQ, IWM)           │
│ VIX: 22.4                                        │
└─────────────────────────────────────────────────┘
```
- Technical snapshots: EMA 20/50, SMA 200, RSI 14, ATR, IV rank, directional/vol regime
- VIX fetched via broker adapter or yfinance fallback

### Step 3: Portfolio State
```
┌─────────────────────────────────────────────────────────────────────┐
│ PORTFOLIO STATE                                                      │
│ Portfolio            Equity     Daily P&L   Open Trades   Status     │
│ tastytrade           $50,000    -0.2%       4             active     │
│ fidelity_ira         $200,000   +0.1%       2             active     │
│ fidelity_personal    $50,000    +0.3%       1             active     │
│ zerodha              ₹500,000   +0.0%       0             active     │
│ stallion             ₹2,000,000 +0.5%       29            read-only  │
└─────────────────────────────────────────────────────────────────────┘
```
- Each portfolio loads into its own `PortfolioBundle` (positions, trades, risk factors)
- WhatIf portfolios share parent's bundle (e.g., `tastytrade_whatif` sees same positions as `tastytrade`)
- USD and INR portfolios never cross-contaminate

### Step 4: Guardian — Circuit Breaker Check

| Breaker | Threshold | Status |
|---------|-----------|--------|
| Daily loss | 3.0% | OK (-0.2%) |
| Weekly loss | 5.0% | OK (-1.1%) |
| VIX halt | 35.0 | OK (22.4) |
| Tastytrade drawdown | 25.0% | OK (3.2%) |
| Fidelity IRA drawdown | 15.0% | OK (1.1%) |
| Consecutive losses | 3 pause / 5 halt | OK (1) |

**If ANY breaker trips → HALTED state. You are notified immediately:**
```
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
TRADING HALTED
Reason: Daily loss -3.2% exceeds 3.0% limit
Override requires written rationale.
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
```

### Step 5: Capital Utilization

```
┌───────────────────────────────────────────────────────────────────────────┐
│ CAPITAL UTILIZATION                                                        │
│ Portfolio            Target   Actual   Gap     Idle $      Cost/Day  Sev   │
│ tastytrade           90%      62%      -28%    $14,000     $15.34    WARN  │
│ fidelity_ira         85%      80%      -5%     $10,000     $3.42     ok    │
│ fidelity_personal    90%      45%      -45%    $27,500     $18.84    CRIT  │
│ zerodha              90%      0%       -90%    ₹450,000    ₹0.00     ok    │
│ stallion             100%     98%      -2%     ₹40,000     ₹0.00     ok    │
└───────────────────────────────────────────────────────────────────────────┘
```

**You are notified when severity > ok:**
```
[WARNING] tastytrade: $14,000 idle (62% deployed, target 90%). 5 days since last trade.
[CRITICAL] fidelity_personal: $27,500 idle (45% deployed, target 90%). 12 days since last trade. Costing $18.84/day.
  → You have $27,500 idle AND 1 pending recommendation — approve it?
```

- Staggered deployment ramp: system doesn't nag to deploy $200K on day 1 (8-week ramp, per-portfolio weekly caps)
- Severity escalation: `ok` → `info` (gap > threshold) → `warning` (5+ days idle) → `critical` (10+ days idle)
- Nag frequency: max once every 4 hours per portfolio

### Step 6: Session Objectives

Each agent declares today's goals (graded at EOD):
```
┌────────────────────────────────────────────────────────────┐
│ SESSION OBJECTIVES                                          │
│ Agent          Objective                        Target      │
│ guardian       Enforce circuit breakers          0 breaches  │
│ capital        Monitor idle capital              all < 15%   │
│ screener       Screen today's cadences           ≥1 rec      │
│ evaluator      Evaluate all open positions       100%        │
│ accountability Track decision quality            TTD < 60min │
└────────────────────────────────────────────────────────────┘
```

---

## 3. Macro Check

The first gate: is it safe to trade today?

```
┌─────────────────────────────────────────────────┐
│ MACRO ASSESSMENT                                 │
│ VIX:          22.4                               │
│ Regime:       normal (16-25)                     │
│ Assessment:   neutral                            │
│ Should screen: YES                               │
│ Confidence modifier: 1.0 (no adjustment)         │
└─────────────────────────────────────────────────┘
```

| VIX Range | Regime | What Happens |
|-----------|--------|-------------|
| < 16 | low_vol | `risk_on` — full screening, good for selling premium |
| 16-25 | normal | `neutral` — normal screening, no confidence adjustment |
| 25-35 | elevated | `cautious` — screens run but confidence reduced ~20% |
| > 35 | crisis | `risk_off` — **skips screening entirely**, goes to MONITORING |

**If risk_off, you see:**
```
Macro: risk_off — VIX 38.2 exceeds crisis threshold. Skipping all screeners. Monitoring positions only.
```

Override via CLI args or `config/daily_macro.yaml`:
```bash
python -m trading_cotrader.runners.run_workflow --once --macro-outlook cautious --expected-vol elevated
```

---

## 4. Screening

Runs screeners matched to today's cadences. Entry filters gate every recommendation.

### Cadence → Screener Mapping

| Day | Cadence | Screeners Run |
|-----|---------|--------------|
| Any | 0dte | VIX Regime |
| Wednesday | 0dte, weekly | VIX Regime, IV Rank |
| Friday | 0dte, weekly | VIX Regime, IV Rank |
| Monthly DTE window (35-55) | monthly | VIX Regime, IV Rank |
| LEAPS (monthly) | leaps | LEAPS Entry (picky AND logic) |

### Screening Pipeline

```
1. MACRO GATE          → risk_off? STOP. Otherwise proceed.
2. WATCHLIST           → SPY, QQQ, IWM (default) or custom
3. FOR EACH SYMBOL × SCREENER:
   ├── Technical Snapshot  (RSI, EMA, ATR, IV rank, regime)
   ├── Screener Logic      (VIX regime → strategy suggestion)
   ├── Entry Filters       (RSI range, regime, ATR%, IV pctile from risk_config.yaml)
   └── Strategy Filter     (is strategy active in target portfolio?)
4. CONFIDENCE MODIFIER → cautious macro reduces score ~20%
5. OUTPUT              → List of recommendations
```

### Entry Filter Example

```
Entry filter check for iron_condor on SPY:
  RSI check:        48.2 in range [30, 70]     → PASS
  Directional regime: F (required: [F])         → PASS
  ATR percent:      1.2% >= 0.8%               → PASS
  Result: ALL FILTERS PASSED
```

### Risk Snapshot (runs alongside screening)

```
┌──────────────────────────────────┐
│ RISK SNAPSHOT                     │
│ VaR 95% (1-day):  $2,340         │
│ VaR 99% (1-day):  $3,890         │
│ Expected Shortfall: $4,120        │
│ Open positions:    7              │
│ Top concentration: SPY at 35%     │
└──────────────────────────────────┘
```

---

## 5. Recommendation Review — YOU DECIDE

**Workflow pauses here. You are notified.**

```
============================================================
NEW RECOMMENDATIONS PENDING REVIEW
============================================================
  [a1b2c3d4] SPY iron_condor — confidence=7
    VIX 22.4 normal regime. RSI 48, flat. Selling premium 30-45 DTE.
    Suggested portfolio: tastytrade

  [e5f6g7h8] QQQ vertical_spread — confidence=6
    IV rank 45th percentile. Directional bias bullish.
    Suggested portfolio: fidelity_personal
============================================================
2 recommendation(s). Use 'approve <id>' or 'reject <id>'.
```

### Your Commands

| Command | What It Does |
|---------|-------------|
| `approve a1b2c3d4` | Accept recommendation → queued for EXECUTION |
| `reject a1b2c3d4` | Reject → logged to decision_log with reason |
| `defer a1b2c3d4` | Defer → will be re-presented next monitoring cycle |
| `list` | Show all pending recommendations + exit signals |
| `status` | Show workflow state, cycle count, VIX, trade counts |
| `halt` | Manually halt trading (enters HALTED state) |
| `help` | Show all commands |

### Decision Tracking

Every decision is logged to `decision_log` table with timestamp. The system tracks:
- **Time-to-decision (TTD)** — how long you took to respond
- **Recs ignored** — if you don't act by market close, logged as "no action"
- **Reminder** at 60 minutes if still pending
- **Nag** at 4 hours if still pending

---

## 6. Execution

For each approved action, the Guardian runs a **per-action safety check** before execution:

### Trading Constraints (checked per action)

| Constraint | Threshold | What Happens If Violated |
|-----------|-----------|-------------------------|
| Max trades/day | 3 | Blocked: "3 trades already today" |
| Max trades/week/portfolio | 5 | Blocked: "5 trades this week in tastytrade" |
| No entry first 15 min | 9:30-9:45 ET | Blocked: "Opening volatility window" |
| No entry last 30 min | 3:30-4:00 ET | Blocked: "Closing window" (closes allowed) |
| Undefined risk approval | Required | Blocked: "Undefined risk requires explicit approval" |
| No adding to losers | Without rationale | Blocked: "Position is losing, provide rationale" |
| Cross-broker routing | Enforced | Blocked: "Cannot route Fidelity trade to Tastytrade API" |
| Currency mismatch | Enforced | Blocked: "Cannot book USD trade in INR portfolio" |

### Broker Routing

| Broker | Routing | What You See |
|--------|---------|-------------|
| Tastytrade | API (future) | `[PAPER] Executed rec a1b2c3d4 → trade t9y8z7w6` |
| Fidelity | Manual | `MANUAL EXECUTION REQUIRED at Fidelity. Account: Z12345678. Book the following trade manually.` |
| Zerodha | API (future) | Same as Tastytrade |
| Stallion | Read-only | `BLOCKED: Stallion is a managed fund. No trade execution.` |

**All trades are paper/WhatIf mode by default.** Live execution requires `--live` flag + double-confirmation (not yet built).

---

## 7. Monitoring (Home State)

The engine stays in MONITORING between cycles. Every 30 minutes:

```
┌────────────────────────────────────────────┐
│ MONITORING CYCLE #4                         │
│ Time: 11:30 AM ET                           │
│ VIX: 21.8 (↓0.6)                            │
│ Open trades: 7                              │
│ Pending recs: 0                             │
│ Capital alerts: 1 warning                   │
│ Circuit breakers: all clear                 │
│ Next action: evaluate exits                 │
└────────────────────────────────────────────┘
```

**What runs each cycle:**
1. MarketDataAgent — refresh VIX + snapshots
2. PortfolioStateAgent — refresh positions + P&L
3. CapitalUtilizationAgent — check idle capital (respects 4-hour nag frequency)
4. GuardianAgent — circuit breaker check (halt if tripped)
5. Trigger TRADE_MANAGEMENT

---

## 8. Exit Evaluation

Evaluates every open position against exit rules. Rules come from the portfolio's `exit_rule_profile` in `risk_config.yaml`.

### Exit Rules Evaluated Per Position

| Rule | Conservative (Core) | Balanced (Medium) | Aggressive (High) |
|------|-------------------|-------------------|-------------------|
| Profit target | 50% of max | 65% of max | 80% of max |
| Stop loss (defined) | 100% of max loss | 100% | 100% |
| Stop loss (undefined) | 2x credit | 2x credit | 2x credit |
| DTE roll trigger | 21 DTE | 14 DTE | 7 DTE |
| DTE close trigger | 7 DTE | 5 DTE | 3 DTE |
| Short delta breach | 0.30 | 0.35 | 0.40 |

### Exit Signal Example

```
┌────────────────────────────────────────────────────────────────────┐
│ EXIT SIGNALS                                                        │
│                                                                      │
│ Trade: SPY iron_condor (opened 2026-01-15, DTE=12)                  │
│ Current P&L: +$340 (68% of max profit)                              │
│                                                                      │
│ Rules evaluated:                                                     │
│   ✓ Profit target (65%): 68% → TRIGGERED                           │
│   · Stop loss: not triggered (in profit)                             │
│   ✓ DTE window (14 DTE): 12 DTE → TRIGGERED                       │
│   · Delta breach (0.35): put=0.18, call=0.22 → OK                  │
│                                                                      │
│ Liquidity:                                                           │
│   Bid-ask spread: 0.3% (threshold 3%) → LIQUID                     │
│   Can adjust/roll: YES                                               │
│                                                                      │
│ RECOMMENDATION: CLOSE (take profit)                                  │
│ Urgency: HIGH (multiple rules triggered)                            │
│ Type: EXIT                                                           │
└────────────────────────────────────────────────────────────────────┘
```

### Signal Types

| Type | When | What It Means |
|------|------|--------------|
| EXIT | Profit target hit, stop loss, DTE critical | Close the position |
| ROLL | DTE approaching but still has edge, liquid | Close current + open new at later expiry |
| ADJUST | One side tested, overall still profitable, liquid | Roll untested side closer |

**Illiquidity downgrade:** if ROLL/ADJUST is recommended but the option is illiquid (OI < 500, spread > 3%), it gets downgraded to EXIT (close it, don't try to finesse illiquid options).

---

## 9. Exit Review — YOU DECIDE

**Workflow pauses again. You are notified.**

```
============================================================
EXIT SIGNALS DETECTED
============================================================
  [x1y2z3w4] SPY iron_condor EXIT — urgency=HIGH
    Take profit: 68% > 65% target. DTE=12 < 14.
    Portfolio: tastytrade

  [a9b8c7d6] QQQ vertical_spread ROLL — urgency=NORMAL
    DTE=18, still within range. Roll to next monthly.
    Portfolio: fidelity_personal
============================================================
2 signal(s). Use 'approve <id>' or 'reject <id>'.
```

Same commands as Recommendation Review. Approved exits go to EXECUTION:
- **EXIT** → books opposite trade to close
- **ROLL** → closes current + books new at later expiry (`rolled_from_id` / `rolled_to_id` linkage)
- **ADJUST** → modifies legs (rolls untested side)

---

## 10. End-of-Day Reporting (4:15 PM ET)

Six agents produce the daily report:

### 10a. Accountability Metrics
```
┌──────────────────────────────────────┐
│ ACCOUNTABILITY                        │
│ Trades today:            2            │
│ Recs ignored:            1            │
│ Recs deferred:           0            │
│ Avg time-to-decision:    23 min       │
│ Decisions today:         4            │
└──────────────────────────────────────┘
```

### 10b. Capital Efficiency
```
┌───────────────────────────────────────────────────────────────────────────┐
│ CAPITAL EFFICIENCY                                                         │
│ Portfolio            Target   Actual   Gap     Idle $      Cost/Day  Days  │
│ tastytrade           90%      68%      -22%    $16,000     $17.53    3     │
│ fidelity_ira         85%      80%      -5%     $10,000     $3.42     1     │
│ fidelity_personal    90%      50%      -40%    $25,000     $17.12    8 !!  │
└───────────────────────────────────────────────────────────────────────────┘
```

### 10c. Session Performance (Agent Grades)
```
┌────────────────────────────────────────────────────────────────────────┐
│ SESSION PERFORMANCE                                                     │
│ Agent          Objective                     Target  Actual  Grade      │
│ guardian       Enforce circuit breakers       0       0       A         │
│ capital        Monitor idle capital           <15%    22%     C         │
│ screener       Screen today's cadences        ≥1      2       A         │
│ evaluator      Evaluate all positions          100%   100%    A         │
│ accountability Decision quality               <60min  23min   A         │
└────────────────────────────────────────────────────────────────────────┘
```

### 10d. Corrective Plan
```
┌────────────────────────────────────────────────────────────────────────┐
│ CORRECTIVE PLAN                                                         │
│ 1. Capital idle: fidelity_personal (8 days). Escalate to critical.     │
│ 2. Rejected rec SPY iron_condor — review rationale tomorrow.           │
│ 3. No LEAPS screening today — add LEAPS cadence when DTE window open. │
└────────────────────────────────────────────────────────────────────────┘
```

### 10e. QA Report
```
┌──────────────────────────────────────┐
│ QA ASSESSMENT                         │
│ Tests:     137/137 passed             │
│ Coverage:  42.3%                      │
│ Low coverage: 18 files below 70%      │
│ Suggestions: 10 new test cases        │
└──────────────────────────────────────┘
```

### 10f. Full Daily Summary

All of the above is assembled by ReporterAgent and sent via NotifierAgent (console always, email if configured).

---

## 11. HALTED State

Entered when a circuit breaker trips or you manually halt.

**How you get here:**
- Daily loss exceeds 3% → auto-halt
- Weekly loss exceeds 5% → auto-halt
- VIX > 35 → auto-halt
- Per-portfolio drawdown exceeded → auto-halt
- 5 consecutive losses in a portfolio → auto-halt
- You typed `halt` → manual halt

**How you get out:**
```
> resume --rationale "VIX dropped back to 28. Reviewed positions. No new entries, monitoring only."
```

The rationale is required and persisted. No empty rationale accepted.

---

## 12. Portfolio Architecture

### 10 Portfolios Across 4 Brokers

| Portfolio | Broker | Currency | Type | Capital | Execution |
|-----------|--------|----------|------|---------|-----------|
| tastytrade | Tastytrade | USD | Real | $50K | API (future) |
| tastytrade_whatif | Tastytrade | USD | WhatIf | mirrors real | Paper |
| fidelity_ira | Fidelity | USD | Real | $200K | Manual (CSV sync) |
| fidelity_ira_whatif | Fidelity | USD | WhatIf | mirrors real | Paper |
| fidelity_personal | Fidelity | USD | Real | $50K | Manual (CSV sync) |
| fidelity_personal_whatif | Fidelity | USD | WhatIf | mirrors real | Paper |
| zerodha | Zerodha | INR | Real | ₹500K | API (future) |
| zerodha_whatif | Zerodha | INR | WhatIf | mirrors real | Paper |
| stallion | Stallion | INR | Real | ₹2M | Read-only (managed fund) |
| stallion_whatif | Stallion | INR | WhatIf | mirrors real | Paper |

### Broker Adapter Architecture

All broker-specific code is isolated in `adapters/`:

```
adapters/
├── base.py                    # BrokerAdapterBase (ABC)
│   ├── ManualBrokerAdapter    # Fidelity — manual execution, CSV import
│   └── ReadOnlyAdapter        # Stallion — managed fund, no trading
├── factory.py                 # BrokerAdapterFactory.create(broker_config)
└── tastytrade_adapter.py      # TastyTrade SDK — ALL tastytrade imports here only
```

Zero `tastytrade` imports outside `adapters/`. Services use the generic `BrokerAdapterBase` interface.

### Per-Portfolio Container Bundles

Each real portfolio gets its own isolated container:

```
ContainerManager
├── tastytrade bundle        (PortfolioContainer + PositionContainer + TradeContainer + RiskFactorContainer)
│   └── shared by tastytrade_whatif
├── fidelity_ira bundle
│   └── shared by fidelity_ira_whatif
├── fidelity_personal bundle
│   └── shared by fidelity_personal_whatif
├── zerodha bundle
│   └── shared by zerodha_whatif
└── stallion bundle
    └── shared by stallion_whatif
```

USD positions never mix with INR positions. Each bundle loads from DB filtered by `portfolio_id`.

---

## 13. Entry Rules

Every trade must pass ALL gates. No exceptions.

### Gate Chain

```
MACRO GATE → SCREENER → ENTRY FILTERS → STRATEGY FILTER → CONFIDENCE → LIQUIDITY → RECOMMENDATION
```

### Strategy-Specific Entry Conditions

| Strategy | IV Rank Min | Market Outlook | Key Filter |
|----------|-------------|----------------|------------|
| Iron Condor | 30 (pref 50) | Neutral/range | RSI 30-70, flat regime, ATR > 0.8% |
| Iron Butterfly | 30 | Neutral | RSI 35-65, flat regime |
| Iron Butterfly 0DTE | 20 | Neutral | RSI 40-60, flat regime, 9:45-11 AM |
| Vertical Spread | 20 | Directional | RSI 20-80 |
| Calendar Spread | 15 | Neutral | IV LOW (benefits from rising IV) |
| Double Calendar | 20 | Neutral/range | Wednesday entry, avoid quarterly expiry |
| Diagonal/PMCC | 15 | Directional | IV LOW, buy 50-70D 3-4mo, sell 30-50D 1mo |
| Strangle | 40 (pref 60) | Neutral | RSI 30-70, flat, IV pctile 40+, undefined risk |
| Straddle | 40 | Neutral | RSI 35-65, flat, undefined risk |
| Covered Call | 20 | Neutral/bullish | Must own shares |
| LEAPS | 40+ | Bullish | > 10% correction, near support, elevated IV |

### Trading Schedule

| Day | Cadences | Notes |
|-----|----------|-------|
| Monday | 0DTE | Review week. No new weekly/monthly unless screener fires. |
| Tuesday | 0DTE | Prep Wednesday templates. |
| Wednesday | 0DTE, weekly | SPX calendars at 2-3 PM ET. |
| Thursday | 0DTE | Prep Friday templates. |
| Friday | 0DTE, weekly | QQQ diagonal at 1:30 PM ET. |
| Monthly window | monthly | When DTE 35-55 for next monthly expiry. |

### Position Sizing

| Portfolio | Max Single Position | Max Trade Risk | Max Positions |
|-----------|--------------------|-----------------------|---------------|
| Core (Fidelity IRA) | 10% | 5% | 16 |
| Medium (Fidelity Personal) | 25% | 10% | 5 |
| High (Tastytrade) | 30% | 15% | 5 |

---

## 14. Exit Rules

Exits are not negotiable. The evaluator tells you when to act. You execute.

### Profit Targets

| Profile | Target | Applies To |
|---------|--------|-----------|
| Conservative (Core) | 50% of max profit | All strategies |
| Balanced (Medium) | 65% of max profit | All strategies |
| Aggressive (High) | 80% of max profit | All strategies |
| 0DTE | 50% of credit | Iron butterflies |
| Weekly calendars | 30-50% of debit | SPX calendars |

### Stop Losses

| Risk Type | Stop Loss |
|-----------|-----------|
| Defined risk | 100% of max loss (let it play out or cut early) |
| Undefined risk | 2x credit received |
| 0DTE | 1x credit received |

### Time-Based Exits

| Trigger | Action |
|---------|--------|
| 21 DTE | Evaluate for roll |
| 7 DTE | Close or roll. No exceptions. |
| 0 DTE (2:30 PM) | Close all 0DTE positions |
| Front-month expiry (weekly) | Roll day BEFORE expiry |

---

## 15. Circuit Breakers & Hard Limits

All thresholds in `config/workflow_rules.yaml`. No hardcoded values.

### Circuit Breakers

| Breaker | Threshold | Effect |
|---------|-----------|--------|
| Daily loss | 3.0% | HALT — no new trades today |
| Weekly loss | 5.0% | HALT — requires written review to resume |
| VIX | 35 | HALT — evaluate exits only |
| Portfolio drawdown | 15-25% (per portfolio) | HALT that portfolio |
| Consecutive losses (strategy) | 3 | PAUSE that strategy 1 week |
| Consecutive losses (portfolio) | 5 | HALT that portfolio |

### Trading Constraints

| Constraint | Value |
|-----------|-------|
| Max trades per day | 3 |
| Max trades per week per portfolio | 5 |
| No entry first minutes | 15 (9:30-9:45) |
| No entry last minutes | 30 (3:30-4:00) |
| Undefined risk | Requires explicit approval |
| Adding to losers | Requires written rationale |

---

## 16. Notification Summary

When and how the system reaches you:

| Event | When | Channel | Your Action |
|-------|------|---------|-------------|
| Circuit breaker tripped | Immediately | Console + email | `resume --rationale "..."` |
| New recommendations | After screening | Console + email | `approve` / `reject` / `defer` |
| Exit signals | After evaluation | Console + email | `approve` / `reject` / `defer` |
| Idle capital alert (warning) | Boot + every 4h | Console + email | Review pending recs |
| Idle capital alert (critical) | Boot + every 4h | Console + email | Deploy capital or provide rationale |
| Manual execution needed | After approval | Console + email | Execute trade at Fidelity/Zerodha |
| Decision reminder | 60 min pending | Console | Act on recommendation |
| Decision nag | 4 hours pending | Console | Act NOW or logged as "ignored" |
| Daily summary report | 4:15 PM ET | Console + email | Read, review corrective plan |
| Trading halt (manual) | When you type `halt` | Console | `resume` when ready |

Email is off by default. Enable in `workflow_rules.yaml` → `notifications.email.enabled: true`.

---

## 17. Guiding Principles

1. **The market doesn't care about your opinion.** Trade what IS, not what you think SHOULD be. The screener has no opinions. Follow it.

2. **Risk management is the only edge that compounds.** A 50% drawdown requires 100% gain to recover. Protect capital first.

3. **Small, consistent income beats big, occasional wins.** Weekly calendars make $48-94/lot. Boring. But 80%+ win rate over 150+ trades.

4. **Every trade needs a reason to exist AND a reason to die.** Entry rationale AND exit plan, defined BEFORE entry.

5. **Impulse is the enemy.** If the screener didn't recommend it, you need a written rationale that's better than the screener.

6. **Losses are tuition.** But only if you log them. An unlogged loss teaches nothing. A logged loss is training data.

7. **The system is smarter than you in the moment.** You built the rules when you were calm. Trust them when you're not.

8. **Capital sitting idle is capital losing money.** The system will nag you. Let it. That's the point.

---

## 18. Quick Reference — Commands

### Workflow Commands (during workflow run)

| Command | Description |
|---------|------------|
| `approve <id>` | Approve a recommendation or exit signal |
| `reject <id>` | Reject with logged reason |
| `defer <id>` | Defer to next monitoring cycle |
| `list` | Show all pending recommendations + exit signals |
| `status` | Show workflow state, VIX, trade counts, pending decisions |
| `halt` | Manually halt trading |
| `resume --rationale "..."` | Resume from HALTED state (rationale required) |
| `override --target <breaker> --rationale "..."` | Override a specific circuit breaker |
| `help` | Show all commands |

### CLI Commands (standalone, outside workflow)

```bash
# Workflow
python -m trading_cotrader.runners.run_workflow --once --no-broker --mock    # single cycle
python -m trading_cotrader.runners.run_workflow --web --port 8080            # web dashboard + continuous

# Trade booking
python -m trading_cotrader.cli.book_trade --file trading_cotrader/config/templates/<file>.json --no-broker
python -m trading_cotrader.cli.book_trade --file <file>.json --no-broker --dry-run

# Screeners
python -m trading_cotrader.cli.run_screener --screener all --symbols SPY,QQQ --no-broker
python -m trading_cotrader.cli.run_screener --screener vix --symbols SPY --macro-outlook cautious --no-broker

# Recommendations
python -m trading_cotrader.cli.accept_recommendation --list
python -m trading_cotrader.cli.accept_recommendation --accept <ID> --notes "reason" --portfolio tastytrade
python -m trading_cotrader.cli.accept_recommendation --reject <ID> --reason "too risky"

# Portfolio evaluation
python -m trading_cotrader.cli.evaluate_portfolio --all --no-broker --dry-run

# Multi-broker
python -m trading_cotrader.cli.init_portfolios
python -m trading_cotrader.cli.sync_fidelity --file Portfolio_Positions.csv
python -m trading_cotrader.cli.load_stallion

# System health
pytest trading_cotrader/tests/ -v                        # 137 tests
python -m trading_cotrader.harness.runner --skip-sync    # 17-step harness
python -m trading_cotrader.scripts.setup_database        # DB setup
```

---

## 19. Templates

27 templates in `config/templates/`:

| Cadence | Count | Examples |
|---------|-------|---------|
| 0DTE | 1 | `0dte_iron_butterfly_spy.json` |
| Weekly | 4 | `weekly_call_calendar_spx_7_9.json`, `weekly_put_diagonal_qqq.json` |
| Monthly | 16 | `monthly_iron_condor_spy.json`, `monthly_calendar_spread_spy.json` |
| LEAPS | 5 | `leaps_deep_itm_call.json`, `leaps_pmcc.json` |
| Custom | 1 | `custom_combo_spy.json` |

Each template includes `entry_conditions` and `pnl_drivers` — the screener checks these before recommending.

---

## 20. Configuration Files

| File | What It Controls |
|------|-----------------|
| `config/workflow_rules.yaml` | Circuit breakers, trading constraints, scheduling, capital deployment, notifications, QA thresholds |
| `config/risk_config.yaml` | 10 portfolios, strategy permissions, entry filters, exit rule profiles, position sizing, liquidity thresholds |
| `config/brokers.yaml` | 4 broker definitions (Tastytrade, Fidelity, Zerodha, Stallion) |
| `config/daily_macro.yaml` | Manual macro assessment override |
| `config/templates/*.json` | 27 trade templates with entry conditions |

**Every rule is in YAML. No hardcoded thresholds anywhere.**
