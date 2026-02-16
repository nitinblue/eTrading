# Trading Playbook
> Systematic options portfolio management. Macro → Exposure → Action.
> Every decision codified. Every trade logged. No trade from memory.

---

## 1. Portfolio Architecture

| Portfolio | Capital | Target | Cadence | What It Does |
|-----------|---------|--------|---------|-------------|
| **Core Holdings** | $200K (80%) | 12.5% | Monthly+ | Long-term stock accumulation. CSP → assignment → covered call → wheel. Buy-and-hold backbone. |
| **Medium Risk** | $20K (8%) | 20% | Weekly/Monthly | LEAPS, PMCC, calendars, double calendars, iron condors. Leveraged income. |
| **High Risk** | $10K (4%) | 75% | 0DTE/Weekly | 0DTE iron butterflies, weekly credit spreads, short-term theta plays. Never exceed 5% of total capital. |
| **Model Portfolio** | $25K (8%) | N/A | Any | Training data for AI/ML. Intentional wins AND losses. Every trade requires rationale + exit commentary. |

**Rule:** Total allocation = 100%. Cash reserve enforced per portfolio (Core 15%, Med 10%, High 5%).

---

## 2. Daily Routine

### Pre-Market (6:30 - 9:30 AM ET) — 15 minutes

**Step 1: Macro Check**
What is the market telling me today?

```bash
# Check VIX, assess macro regime
python -m trading_cotrader.cli.run_screener --screener vix --symbols SPY --no-broker
```

- [ ] VIX level: ___  (below 16 = low, 16-25 = normal, 25-35 = elevated, 35+ = crisis)
- [ ] Overnight moves: SPY ___ QQQ ___ (check futures)
- [ ] Economic calendar: Any FOMC, CPI, PPI, jobs report today?
- [ ] Earnings: Any holdings reporting today?

**If macro is risk_off (VIX 35+, major event uncertainty): STOP. No new trades. Evaluate exits only.**

```bash
# Override macro if needed
python -m trading_cotrader.cli.run_screener --screener vix --symbols SPY --macro-outlook risk_off --no-broker
```

**Step 2: Position Review**
What do I own and does anything need attention?

```bash
# Evaluate all open positions against exit rules
python -m trading_cotrader.cli.evaluate_portfolio --all --no-broker --dry-run
```

Check each open position:
- [ ] Any position at 50%+ profit? → Close or take profit
- [ ] Any position at 1x-2x loss of credit received? → Cut or adjust
- [ ] Any position within 21 DTE? → Evaluate for roll
- [ ] Any position within 7 DTE? → Close or roll NOW
- [ ] Any short strike delta > 0.30? → Manage

**Step 3: Today's Trading Plan**
What cadence am I trading today?

| Day | What to Prepare | Template |
|-----|----------------|----------|
| **Monday** | Weekly review. No new entries unless screener fires. | — |
| **Tuesday** | Prep Wednesday calendar templates. Check SPX levels. | `weekly_call_calendar_spx_*.json` |
| **Wednesday** | SPX weekly calendars at 2-3 PM. 0DTE if conditions met. | `weekly_call_calendar_spx_7_9.json` or `_9_12.json` |
| **Thursday** | Prep Friday diagonal template. Check QQQ levels. | `weekly_put_diagonal_qqq.json` |
| **Friday** | QQQ weekly diagonal at 1:30 PM. 0DTE if conditions met. | `weekly_put_diagonal_qqq.json` |

Pick the right template, update strikes/expiry to current market:

```bash
# List all available templates
ls trading_cotrader/config/templates/

# Dry-run to verify before committing
python -m trading_cotrader.cli.book_trade --file trading_cotrader/config/templates/<template>.json --no-broker --dry-run
```

### Market Hours — Execution Windows

| Time (ET) | Action |
|-----------|--------|
| 9:30-9:45 | **Do nothing.** Let opening volatility settle. |
| 9:45-11:00 | 0DTE entry window (if trading 0DTE) |
| 11:00-1:00 | Monitor positions. No impulse trades. |
| 1:30 PM | Friday: QQQ diagonal entry |
| 2:00 PM | Wednesday: SPX 9/12 calendar entry (conservative) |
| 2:30 PM | 0DTE time stop — close all 0DTE positions regardless of P&L |
| 3:00 PM | Wednesday: SPX 7/9 calendar entry (aggressive) |
| 3:30-4:00 | Final position check. Log any decisions. |

### Post-Market (after 4 PM) — 10 minutes

```bash
# Log today's decisions
python -m trading_cotrader.cli.log_event --underlying SPY --strategy iron_condor --rationale "Took 50% profit at 2 PM"

# Prep tomorrow's templates
# Edit the template file with tomorrow's strikes/expiry
```

- [ ] Log every trade decision (entry, exit, adjustment, hold) with rationale
- [ ] Update template for tomorrow if applicable
- [ ] Note anything unusual in market behavior

---

## 3. Weekly Schedule

### Monday: Review & Assess
- Review all open positions across all 4 portfolios
- Check performance metrics from last week
- Identify positions approaching exits (DTE, profit target, stop loss)
- Run screener for new monthly opportunities

```bash
python -m trading_cotrader.cli.run_screener --screener all --symbols SPY,QQQ,IWM,AAPL,MSFT,NVDA --no-broker
python -m trading_cotrader.cli.accept_recommendation --list
```

### Wednesday: Weekly Calendar Entry
**SPX Call Calendar** — the highest-CAGR weekly strategy (64% CAGR backtested)

Pre-trade checklist:
- [ ] Not a quarterly futures expiry week (Mar/Jun/Sep/Dec 3rd Friday)
- [ ] No FOMC announcement today
- [ ] SPX not in a strong directional trend (check RSI 40-60 range)
- [ ] Template prepared with current ATM strike and correct DTE

```bash
# Conservative variant (recommended to start)
python -m trading_cotrader.cli.book_trade --file trading_cotrader/config/templates/weekly_call_calendar_spx_9_12.json --no-broker

# Aggressive variant (after proving the conservative works)
python -m trading_cotrader.cli.book_trade --file trading_cotrader/config/templates/weekly_call_calendar_spx_7_9.json --no-broker
```

### Friday: Weekly Diagonal Entry
**QQQ Put Diagonal** — 88% win rate backtested

Pre-trade checklist:
- [ ] VIX is 16 or above
- [ ] QQQ not in freefall (check support levels)
- [ ] Template prepared with current 50-delta put and 10-delta-lower long put

```bash
python -m trading_cotrader.cli.book_trade --file trading_cotrader/config/templates/weekly_put_diagonal_qqq.json --no-broker
```

### Friday Evening: Week-End Ritual (20 minutes)

```bash
# Check what recommendations are pending
python -m trading_cotrader.cli.accept_recommendation --list

# Expire old recommendations
python -m trading_cotrader.cli.accept_recommendation --expire
```

Journal entry (in event log or personal notes):
- [ ] Trades opened this week: ___
- [ ] Trades closed this week: ___ (P&L: ___)
- [ ] Rules followed? Any impulse trades?
- [ ] What did the market teach me this week?
- [ ] Next week's focus: ___

---

## 4. Monthly Review (1st weekend of each month)

### Performance Check

```bash
# Run full harness to verify system health
python -m trading_cotrader.harness.runner --skip-sync

# Unit tests
pytest trading_cotrader/tests/ -v
```

Review metrics per portfolio:
- Win rate (target: 70%+ for defined risk, 80%+ for weekly income)
- Average win vs average loss (need positive expectancy)
- Max drawdown (Core <15%, Med <20%, High <30%)
- CAGR vs target (Core 12.5%, Med 20%, High 75%)
- Sharpe ratio (target >1.0)

Review metrics by strategy:
- Which strategies are profitable?
- Which strategies are losing?
- Are you following the screener or overriding it?

Review metrics by trade source:
- Screener recommendations: win rate ___
- Manual trades: win rate ___
- Are screener trades outperforming manual?

### Monthly Adjustments
- [ ] Update `active_strategies` in `risk_config.yaml` if a strategy is consistently losing
- [ ] Adjust position sizing if drawdown exceeded targets
- [ ] Update `daily_macro.yaml` with current market assessment
- [ ] Roll any positions approaching monthly expiry

---

## 5. Entry Rules (The Gate)

**Every trade must pass ALL of these before entry. No exceptions.**

### Universal Rules
1. **Macro gate passed** — System is not in risk_off mode
2. **Screener recommended OR explicit rationale documented** — No "I feel like it" trades
3. **Within portfolio risk limits** — Position count, concentration, delta limits
4. **Liquidity check passed** — Bid-ask spread <5%, open interest >100, daily volume >500
5. **Template populated** — Every field filled, strikes verified against current market

### Strategy-Specific Entry Conditions
These are in each template's `entry_conditions` field. Quick reference:

| Strategy | IV Rank Min | Market Outlook | Key Filter |
|----------|-------------|----------------|------------|
| Iron Condor | 30 (pref 50) | Neutral/range | RSI 30-70, flat regime, ATR >0.8% |
| Iron Butterfly | 30 | Neutral | RSI 35-65, flat regime |
| Iron Butterfly 0DTE | 20 | Neutral | RSI 40-60, flat regime, 9:45-11 AM entry |
| Vertical Spread | 20 | Directional | RSI 20-80 |
| Calendar Spread | 15 | Neutral | IV LOW (benefits from rising IV) |
| Double Calendar | 20 | Neutral/range | Wednesday entry, avoid quarterly expiry |
| Diagonal/PMCC | 15 | Directional | IV LOW, buy 50-70Δ 3-4mo, sell 30-50Δ 1mo before |
| Strangle | 40 (pref 60) | Neutral | RSI 30-70, flat, IV pctile 40+, undefined risk approval |
| Straddle | 40 | Neutral | RSI 35-65, flat, undefined risk approval |
| Covered Call | 20 | Neutral/slightly bullish | Must own shares |
| LEAPS | 40+ | Bullish | >10% correction, near support, elevated IV |

### Position Sizing Rules
| Portfolio | Max Single Position | Max Single Trade Risk | Max Positions |
|-----------|--------------------|-----------------------|---------------|
| Core Holdings | 10% of portfolio | 5% of portfolio | 16 |
| Medium Risk | 25% of portfolio | 10% of portfolio | 5 |
| High Risk | 30% of portfolio | 15% of portfolio | 5 |
| Model Portfolio | 20% of portfolio | 15% of portfolio | 20 |

---

## 6. Exit Rules (The Discipline)

**Exits are not negotiable. The system tells you when to act. You execute.**

### Profit Targets
| Profile | Target | Applies To |
|---------|--------|-----------|
| Conservative (Core) | 50% of max profit | All strategies |
| Balanced (Medium) | 65% of max profit | All strategies |
| Aggressive (High) | 80% of max profit | All strategies |
| 0DTE | 50% of credit | Iron butterflies |
| Weekly calendars | 30-50% of debit | SPX calendars |
| Weekly diagonal | $1.50 per contract | QQQ diagonal |

### Stop Losses
| Risk Type | Stop Loss | Strategies |
|-----------|-----------|-----------|
| Defined risk | 100% of max loss (let it play out or close early) | Verticals, iron condors, butterflies |
| Undefined risk | 2x credit received | Strangles, straddles, naked options |
| 0DTE | 1x credit received | 0DTE iron butterflies |
| Weekly calendar | -20 delta test (conservative) | SPX 9/12 calendar |

### Time-Based Exits
| Trigger | Action |
|---------|--------|
| 21 DTE | Evaluate for roll. Is there still edge? |
| 7 DTE | Close or roll. No exceptions for monthly trades. |
| 0 DTE (2:30 PM) | Close all 0DTE positions. No holding to settlement. |
| Front-month expiry (weekly) | Roll front leg day BEFORE expiry (Thursday for Friday expiry) |

### Delta-Based Exits
- Short strike delta exceeds 0.30 → Manage (roll untested side closer, or close)
- Portfolio delta exceeds limit → Hedge or reduce

---

## 7. Risk Rules (The Hard Limits)

**These are circuit breakers. If hit, STOP trading and reassess.**

### Portfolio-Level Limits
| Limit | Core | Medium | High |
|-------|------|--------|------|
| Max portfolio delta | 1000 | 300 | 100 |
| Max total risk % | 25% | 40% | 100% |
| Min cash reserve | 15% | 10% | 5% |
| Max concentration per underlying | 10% | 30% | 40% |

### Global Limits
- **Max daily loss:** 3% of total capital ($7,500) → Stop trading for the day
- **Max drawdown:** 15% of total capital ($37,500) → Reduce all positions by 50%, reassess strategy
- **VaR limit:** 3% at 95% confidence, 1-day horizon
- **Undefined risk cap:** 20% of total portfolio (80% must be defined risk)

### Circuit Breakers
- VIX > 35: No new positions. Evaluate existing for exit.
- Account down 3% in a day: No new positions until next day.
- 3 consecutive losing trades in same strategy: Pause that strategy for 1 week. Review.
- Any single trade loses more than 2x expected max loss: Full portfolio review.

---

## 8. Journaling (The Learning Engine)

Every trade is a data point. The journal turns data points into wisdom.

### What to Log (Every Trade)

```bash
# On entry
python -m trading_cotrader.cli.log_event --underlying SPY --strategy iron_condor \
  --rationale "IV rank 52, RSI 48, flat regime. Selling premium. 30-45 DTE. Template: monthly_iron_condor_spy"

# On exit
python -m trading_cotrader.cli.log_event --underlying SPY --strategy iron_condor \
  --rationale "Closed at 55% profit. 18 DTE remaining. Followed exit rule."

# On adjustment
python -m trading_cotrader.cli.log_event --underlying SPY --strategy iron_condor \
  --rationale "Rolled untested call side down $5. Put side was tested at 0.28 delta."
```

### Weekly Journal Prompts
Write these in a notebook, not just the system:

1. **What trades did I take this week?** (List them)
2. **Did I follow my rules?** (Be honest. Which rules did I break?)
3. **What did I learn?** (One insight per week is enough)
4. **What surprised me?** (Market behavior I didn't expect)
5. **What will I do differently?** (One specific change)
6. **Emotional state during trades?** (Calm/anxious/greedy/fearful — this matters)

### Monthly Journal Prompts
1. **Am I profitable this month?** (By portfolio, by strategy)
2. **Am I following the system?** (% of trades that came from screener vs impulse)
3. **Is the system improving?** (Are screener recommendations getting better?)
4. **Capital deployment:** Am I using my capital or is it sitting idle?
5. **Biggest lesson this month:**

---

## 9. Templates Quick Reference

### Night-Before Prep

Pick the template for tomorrow's cadence. Open the file, update:
- `legs[].streamer_symbol` — current strikes and expiry date
- `notes` — describe the specific trade
- `rationale` — why NOW, why THIS strike
- `confidence` — 1-10, be honest

```
trading_cotrader/config/templates/
├── 0dte_iron_butterfly_spy.json          ← Any day, 9:45-11 AM entry
├── weekly_call_calendar_spx_7_9.json     ← Wednesday 3 PM (aggressive)
├── weekly_call_calendar_spx_9_12.json    ← Wednesday 2 PM (conservative)
├── weekly_put_diagonal_qqq.json          ← Friday 1:30 PM
├── weekly_double_calendar_spy.json       ← Wednesday 2-3 PM
├── monthly_iron_condor_spy.json          ← When IV rank 30+, neutral
├── monthly_iron_butterfly_spy.json       ← When IV rank 30+, pinning
├── monthly_diagonal_pmcc_spy.json        ← When IV is LOW, directional
├── monthly_calendar_spread_spy.json      ← When IV is LOW, neutral
├── monthly_vertical_spread_spy.json      ← Directional, defined risk
├── monthly_covered_call_spy.json         ← On existing stock holdings
├── monthly_collar_spy.json              ← Protect holdings, zero cost
├── monthly_protective_put_spy.json       ← Insurance, buy when IV is low
├── monthly_straddle_spy.json             ← High IV, pinning, UNDEFINED RISK
├── monthly_strangle_spy.json             ← Highest IV, wide range, UNDEFINED RISK
├── monthly_butterfly_spy.json            ← Low cost pin bet
├── monthly_condor_spy.json              ← Wide range, low cost
├── monthly_single_spy.json              ← CSP or directional
├── monthly_ratio_spread_spy.json        ← Advanced, partial undefined risk
├── monthly_jade_lizard_spy.json         ← Bullish, no upside risk if credit > width
├── monthly_big_lizard_spy.json          ← Straddle + upside hedge, UNDEFINED
├── custom_combo_spy.json                ← Experimental
```

---

## 10. Guiding Principles

These are not rules to memorize. They are beliefs to internalize.

1. **The market doesn't care about your opinion.** Trade what IS, not what you think SHOULD be. The screener doesn't have opinions. Follow it.

2. **Risk management is the only edge that compounds.** A 50% drawdown requires 100% gain to recover. Protect capital first, always.

3. **Small, consistent income beats big, occasional wins.** The weekly calendars make $48-94/lot. Boring. But 80%+ win rate over 150+ trades. That's the game.

4. **Every trade needs a reason to exist AND a reason to die.** Entry rationale AND exit plan, defined BEFORE entry. If you can't articulate both, don't trade.

5. **The journal is more valuable than the P&L.** P&L tells you what happened. The journal tells you WHY. Only "why" makes you better.

6. **Impulse is the enemy.** If a trade isn't in a template, it doesn't exist. If the screener didn't recommend it, you need a written rationale that's better than the screener.

7. **Losses are tuition.** But only if you log them. An unlogged loss teaches nothing. A logged loss with commentary is training data for both you AND the AI.

8. **The system is smarter than you in the moment.** You built the rules when you were calm. Trust them when you're not. That's the whole point.

---

## 11. Tool Runbook — Step by Step

This is the complete walkthrough of the system. Each step shows what the tool does, what data it produces, and how to interpret the output.

### Step 1: System Health Check

Before anything else, verify the system is working.

```bash
# Run full integration harness (16 steps)
python -m trading_cotrader.harness.runner --skip-sync

# Run unit tests (55 tests)
pytest trading_cotrader/tests/ -v
```

**What you see:** 16 numbered steps with PASS/FAIL/SKIP status.
**What it validates:**
| Step | What It Tests | Diagnostic Data |
|------|--------------|-----------------|
| 1 - Imports | All modules load correctly | Import errors if any |
| 2 - Broker | TastyTrade authentication (skips with --skip-sync) | Session token, account info |
| 3 - Portfolio | Virtual portfolios exist in DB | All 4 portfolios side-by-side: name, equity, trade count, P&L |
| 4 - Market Data | Market data containers initialized | Position count, market data status |
| 5 - Risk Aggregation | Greeks aggregated by underlying | Net delta, gamma, theta, vega per underlying |
| 5b - Risk Factors | Risk factor resolution | Risk factor model output |
| 6 - Hedging | Hedge calculator recommendations | Suggested hedges with delta offset |
| 7 - Risk Limits | Portfolio risk limits checked | Limit breaches, warnings, pass/fail per limit |
| 8 - Trades | Trade history loaded | Open/closed trade counts, last 5 trades |
| 9 - Events | Event log statistics | Events by type, by underlying, ML readiness |
| 10 - ML Status | AI/ML data readiness | Trade count vs threshold (500), model import status |
| 11 - Containers | Container manager integration | Container counts, state consistency |
| 12 - Trade Booking | Single WhatIf trade booking | Full booking output: legs, Greeks, DB IDs |
| 13 - Strategy Templates | All 12 strategy bookings | Each strategy type booked and verified |
| 14 - Portfolio Performance | Metrics per portfolio | Win rate, P&L, Sharpe, CAGR per portfolio |
| 15 - Recommendations | Full screener pipeline | Watchlist → screener → recommendation → accept |
| 16 - Enhanced Screeners | Macro gate, technicals, filters | Technical snapshots, entry filter results, macro assessment |

### Step 2: Macro Context Assessment

The system's first decision: is it safe to trade today?

```bash
# Auto-assess from current VIX
python -m trading_cotrader.cli.run_screener --screener vix --symbols SPY --no-broker

# Override with your own view
python -m trading_cotrader.cli.run_screener --screener vix --symbols SPY \
  --macro-outlook cautious --expected-vol elevated --macro-notes "FOMC tomorrow" --no-broker

# Force risk-off (blocks all screening)
python -m trading_cotrader.cli.run_screener --screener vix --symbols SPY --macro-outlook risk_off --no-broker
```

**Diagnostic data produced:**
- **Macro Assessment:** `risk_on` / `neutral` / `cautious` / `risk_off`
- **VIX Level:** Current VIX value and what regime it maps to
- **Auto-Assessment Logic:**
  - VIX < 16 → `risk_on` (low vol, good for selling premium)
  - VIX 16-25 → `neutral` (normal conditions)
  - VIX 25-35 → `cautious` (elevated vol, reduce position size, lower confidence)
  - VIX > 35 → `risk_off` (crisis, no new trades, evaluate exits)
- **Confidence Modifier:** If cautious, recommendation confidence is reduced by ~20%
- **Override Source:** Whether assessment came from VIX auto-assess, CLI args, or `config/daily_macro.yaml`

**How to interpret:** If the output says "Macro gate: RISK_OFF — skipping all screening", the system is protecting you. Don't override unless you have a very specific reason with a written rationale.

### Step 3: Technical Analysis Snapshot

For every symbol the screener evaluates, it generates a TechnicalSnapshot.

```bash
# Run any screener to see technical data on the recommendations
python -m trading_cotrader.cli.run_screener --screener all --symbols SPY,QQQ,NVDA --no-broker
```

**Diagnostic data per symbol:**
| Indicator | What It Tells You | Decision Impact |
|-----------|------------------|-----------------|
| **EMA 20** | Short-term trend direction | Price above EMA 20 = bullish short-term |
| **EMA 50** | Medium-term trend | EMA 20 > EMA 50 = bullish crossover |
| **SMA 200** | Long-term trend | Price below SMA 200 = bear market territory |
| **RSI 14** | Overbought/oversold (0-100) | <30 = oversold (bullish setup), >70 = overbought (bearish setup) |
| **ATR (14-day)** | Average daily range as % of price | Used for stop placement and strike selection |
| **IV Rank** | Current IV vs 1-year range (0-100) | >30 = elevated (good for selling), <20 = low (good for buying) |
| **IV Percentile** | % of days IV was lower in past year | >50 = IV is higher than usual |
| **Directional Regime** | T (trending) or F (flat/range-bound) | Neutral strategies need F, directional need T |
| **Volatility Regime** | LOW / NORMAL / HIGH | Calendar spreads need HIGH, iron condors work in NORMAL |
| **% from 52-week High** | How far price has fallen from peak | LEAPS only recommended after >10% correction |

**How to interpret:** Each recommendation includes this data. If the screener recommends an iron condor but the directional regime is "T" (trending), it means conditions changed since the filter was checked. Be cautious.

### Step 4: Entry Filter Verification

Every strategy has specific entry filters defined in `risk_config.yaml`. The screener checks these BEFORE recommending.

**Diagnostic data (visible in screener output and harness step 16):**

```
Entry filter check for iron_condor on SPY:
  RSI check: 48.2 in range [30, 70] → PASS
  Directional regime: F (required: [F]) → PASS
  ATR percent: 1.2% >= 0.8% → PASS
  Result: ALL FILTERS PASSED
```

When a filter fails:
```
Entry filter check for iron_condor on TSLA:
  RSI check: 78.5 NOT in range [30, 70] → FAIL (overbought)
  Result: FILTERS FAILED — no recommendation generated
```

**What each filter means:**
| Filter | What It Checks | Why It Matters |
|--------|---------------|----------------|
| `rsi_range` | RSI must be within specified range | Prevents selling premium when momentum is extreme |
| `directional_regime` | Must match required regime (F=flat, T=trending) | Iron condors need flat markets, verticals need trends |
| `min_atr_percent` | ATR as % of price must exceed minimum | Ensures enough movement for premium but not too much |
| `volatility_regime` | Must match (LOW/NORMAL/HIGH) | Calendars need HIGH vol, some strategies need LOW |
| `min_iv_percentile` | IV percentile floor | Strangles only when IV is genuinely elevated |

### Step 5: Recommendation Pipeline (The Full Thought Process)

This is the complete chain of reasoning from "should I trade?" to "here's what to do":

```
1. MACRO GATE
   └── VIX = 22, Auto-assess = neutral → PROCEED
   └── User override: none → PROCEED

2. SYMBOLS (from watchlist or CLI)
   └── SPY, QQQ, NVDA, AAPL

3. FOR EACH SYMBOL → EACH ACTIVE SCREENER:
   └── VIX Regime Screener:
       ├── VIX = 22 → "normal" regime → suggests iron_condor
       ├── Technical Snapshot: RSI=52, EMA20>EMA50, regime=F
       ├── Entry Filters for iron_condor: RSI [30,70]=PASS, regime [F]=PASS, ATR=PASS
       └── Raw recommendation: iron_condor on SPY, confidence=7

   └── IV Rank Screener:
       ├── IV Rank = 45 → "elevated" → suggests sell premium
       ├── Entry Filters: PASS
       └── Raw recommendation: iron_condor on SPY, confidence=6

   └── LEAPS Screener:
       ├── SPY correction check: -3% from 52w high → FAIL (need >10%)
       └── No recommendation (too picky — by design)

4. ACTIVE STRATEGY FILTER
   └── iron_condor is in medium_risk.active_strategies? YES → KEEP
   └── iron_condor is in core_holdings.active_strategies? NO → REMOVE for core
   └── Suggests portfolio: medium_risk

5. CONFIDENCE MODIFIER
   └── Macro = neutral → no adjustment → confidence stays 7

6. LIQUIDITY CHECK (if enabled)
   └── SPY bid-ask spread: 0.1% → PASS (threshold: 5%)
   └── SPY open interest: 50,000 → PASS (threshold: 100)
   └── SPY daily volume: 2M → PASS (threshold: 500)

7. FINAL RECOMMENDATION
   └── Strategy: iron_condor
   └── Underlying: SPY
   └── Portfolio: medium_risk
   └── Confidence: 7/10
   └── Status: PENDING (awaiting user accept/reject)
```

**How to see this:** Run any screener and observe the output. Each recommendation includes the reasoning chain.

### Step 6: Trade Booking Verification

When you book a trade (or dry-run it), the system produces diagnostic output.

```bash
python -m trading_cotrader.cli.book_trade --file trading_cotrader/config/templates/monthly_iron_condor_spy.json --no-broker --dry-run
```

**Diagnostic data:**
```
TRADE BOOKING
  File: monthly_iron_condor_spy.json
  Underlying: SPY
  Strategy: iron_condor
  Legs: 4
  Portfolio: medium_risk

  DRY RUN — validated but not booked
    Leg 0: .SPY260417P570 x 1    (buy put protection)
    Leg 1: .SPY260417P580 x -1   (sell put — short strike)
    Leg 2: .SPY260417C620 x -1   (sell call — short strike)
    Leg 3: .SPY260417C630 x 1    (buy call protection)

  Manual Greeks applied:
    Net delta: -0.20     (slightly bearish — check if acceptable)
    Net theta: +0.05     (positive — earning $5/day per contract)
    Net vega:  -0.06     (short vol — profits from IV decrease)

  Portfolio validation: PASS
    iron_condor is allowed in medium_risk: YES
    iron_condor is active in medium_risk: YES
    Position count: 2/5 (within limit)
    Concentration: SPY at 18% (within 30% limit)
```

**What to verify before removing `--dry-run`:**
- [ ] Legs are correct (right strikes, right expiry, right direction)
- [ ] Greeks make sense (theta positive for credit strategies, delta matches your bias)
- [ ] Portfolio validation passed
- [ ] You have a documented rationale

### Step 7: Position Evaluation Diagnostic

When the system evaluates existing positions, it shows which exit rules triggered.

```bash
python -m trading_cotrader.cli.evaluate_portfolio --portfolio medium_risk --no-broker --dry-run
```

**Diagnostic data per position:**
```
Position: SPY iron_condor (opened 2026-01-15)
  Current P&L: +$340 (68% of max profit)
  DTE remaining: 12
  Short put delta: 0.18
  Short call delta: 0.22

  Exit Rules Evaluated:
    ✓ Profit Target (65%): P&L at 68% → TRIGGERED → Recommend CLOSE
    · Stop Loss (1.5x): Not triggered (in profit)
    · DTE Roll (14 DTE): 12 DTE → TRIGGERED → Recommend ROLL or CLOSE
    · Delta Breach (0.30): Both deltas below 0.30 → OK

  Liquidity Check:
    Bid-ask spread: 0.3% → PASS (adjustment threshold: 3%)
    → Can adjust/roll if desired (liquid enough)

  RECOMMENDATION: CLOSE (take profit — 68% > 65% target AND within DTE window)
```

**Possible actions:**
| Action | When | What Happens |
|--------|------|--------------|
| HOLD | No rules triggered | Do nothing |
| CLOSE | Profit target hit OR DTE window OR stop loss | Book opposite trade to close |
| ROLL | DTE approaching but still has edge | Close current, open new at later expiry |
| ADJUST | One side tested but overall still profitable | Roll untested side closer |
| HEDGE | Portfolio delta limit approaching | Add hedge position |

### Step 8: Performance Diagnostics

After accumulating trades, the system produces performance analytics.

```bash
# Full harness shows metrics in step 14
python -m trading_cotrader.harness.runner --skip-sync
```

**Diagnostic data per portfolio:**
```
Portfolio: Medium Risk ($20,000)
  ─────────────────────────────────
  Total P&L:      +$2,340
  Win Rate:        78% (14/18 trades)
  Avg Winner:      $230
  Avg Loser:      -$420
  Profit Factor:   2.1  (gross profit / gross loss — want >1.5)
  Expectancy:      $130/trade (avg P&L per trade — want >$0)
  Max Drawdown:   -8.2% (want <20% for medium risk)
  CAGR:            24% (target: 20%)
  Sharpe Ratio:    1.8 (want >1.0)

  By Strategy:
    iron_condor:  82% WR, +$1,200 P&L, 1.9 profit factor
    calendar:     71% WR, +$640 P&L, 1.6 profit factor
    diagonal:     75% WR, +$500 P&L, 2.3 profit factor

  By Source:
    screener_vix: 85% WR (12 trades)
    manual:       60% WR (5 trades)  ← Are your manual trades worse? Pay attention.
    screener_iv:  100% WR (1 trade)  ← Too few trades to judge

  Weekly P&L:
    Week 1: +$340
    Week 2: -$180
    Week 3: +$520
    Week 4: +$280
```

**Key questions the diagnostics answer:**
1. **Am I making money?** → Total P&L, CAGR
2. **Am I making money the right way?** → Win rate, profit factor, expectancy
3. **Am I risking too much?** → Max drawdown, Sharpe
4. **Which strategies work?** → Strategy breakdown
5. **Is the system better than my instincts?** → Source breakdown (screener vs manual)
6. **Am I improving?** → Weekly P&L trend, event log growth

### Step 9: Event Log Audit Trail

Every decision is logged as an immutable event. This is your audit trail AND your ML training data.

```bash
# Log a decision
python -m trading_cotrader.cli.log_event --underlying SPY --strategy iron_condor \
  --rationale "IV rank 45, RSI 52, flat regime. Screener recommended. Following system."
```

**What gets stored per event:**
| Field | Purpose |
|-------|---------|
| Timestamp | When the decision was made |
| Underlying | Which stock/ETF |
| Strategy | Which strategy type |
| Event Type | ENTRY / EXIT / ADJUSTMENT / ROLL / OBSERVATION |
| Rationale | Your written reasoning (ML training data) |
| Trade ID | Links to the trade object |
| Market Context | VIX, price, IV rank at time of decision |

**Harness step 9 shows:**
- Total events by type (how many entries, exits, adjustments)
- Events by underlying (where are you most active?)
- ML readiness (do you have enough events for supervised learning? Need 500+)

### Step 10: Full Diagnostic Summary

Run this to see the entire system state at a glance:

```bash
# Everything in one run
python -m trading_cotrader.harness.runner --skip-sync 2>&1 | less

# Or targeted checks:
python -c "
from trading_cotrader.core.database.session import session_scope
from trading_cotrader.services.portfolio_manager import PortfolioManager
with session_scope() as s:
    pm = PortfolioManager(s)
    for p in pm.get_all_managed_portfolios():
        print(f'{p.name}: equity={p.total_equity}, delta_limit={p.max_portfolio_delta}')
"
```

---

## 12. Diagnostic Quick Reference

Every piece of data the system produces, where it comes from, and what it means:

| Data Point | Where to See It | What It Tells You |
|------------|----------------|-------------------|
| Macro assessment | Screener output | Is it safe to trade today? |
| VIX regime | Screener output | Low/normal/elevated/crisis |
| Technical snapshot | Screener output, harness step 16 | RSI, EMA, IV rank, regime per symbol |
| Entry filter results | Harness step 16 | Which filters passed/failed for each rec |
| Active strategy filter | Screener output | Was the rec removed because strategy isn't active? |
| Confidence score | Recommendation list | 1-10, adjusted by macro context |
| Liquidity check | Portfolio evaluation output | Bid-ask spread, OI, volume vs thresholds |
| Exit rule evaluation | `evaluate_portfolio` output | Which exit rules triggered (profit/loss/DTE/delta) |
| Portfolio Greeks | Harness step 5 | Net delta/gamma/theta/vega by underlying |
| Risk limit status | Harness step 7 | Which limits are approaching/breached |
| Trade booking validation | `book_trade --dry-run` | Legs, Greeks, portfolio routing check |
| Performance metrics | Harness step 14 | Win rate, P&L, Sharpe, CAGR per portfolio |
| Strategy breakdown | Harness step 14 | Which strategies are profitable/losing |
| Source breakdown | Harness step 14 | Screener vs manual trade performance |
| Event log stats | Harness step 9 | Event counts, ML readiness |
| ML data readiness | Harness step 10 | Trade count vs 500 threshold, model status |
| Container state | Harness step 11 | In-memory state consistency |

---

## Appendix: CLI Command Reference

```bash
# === DAILY ===
# Macro check + screener
python -m trading_cotrader.cli.run_screener --screener all --symbols SPY,QQQ --no-broker
python -m trading_cotrader.cli.run_screener --screener vix --symbols SPY --macro-outlook cautious --no-broker

# Position evaluation
python -m trading_cotrader.cli.evaluate_portfolio --all --no-broker --dry-run

# Book a trade from template
python -m trading_cotrader.cli.book_trade --file trading_cotrader/config/templates/<file>.json --no-broker
python -m trading_cotrader.cli.book_trade --file trading_cotrader/config/templates/<file>.json --no-broker --dry-run

# Log a decision
python -m trading_cotrader.cli.log_event --underlying SPY --strategy iron_condor --rationale "reason"

# === WEEKLY ===
# Review recommendations
python -m trading_cotrader.cli.accept_recommendation --list
python -m trading_cotrader.cli.accept_recommendation --accept <ID> --notes "reason" --portfolio medium_risk
python -m trading_cotrader.cli.accept_recommendation --reject <ID> --reason "too risky"
python -m trading_cotrader.cli.accept_recommendation --expire

# === SYSTEM ===
# Test harness (verify everything works)
python -m trading_cotrader.harness.runner --skip-sync
pytest trading_cotrader/tests/ -v

# Database setup (first time only)
python -m trading_cotrader.scripts.setup_database
```
