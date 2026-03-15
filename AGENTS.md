# The Five Agents — Identity, Purpose, Intelligence
# Date: 2026-03-14 (Session 41)

## Agent Names

| Current | Role | Indian | Constellation | Greek | Zodiac / Sun Sign | Tarot | Short |
|---------|------|--------|---------------|-------|-------------------|-------|-------|
| **Scout** | Market Intelligence | **Chanakya** — strategist behind empires | **Orion** — the hunter, scanning | **Hermes** — messenger of gods | **Gemini** — the twins, information gatherer, curious, analytical | The Magician | **Seeker** |
| **Steward** | Treasury & Performance | **Kubera** — god of wealth, treasurer | **Libra** — the scales, balance | **Plutus** — god of wealth | **Taurus** — the bull, wealth builder, patient, values stability | The Emperor | **Vault** |
| **Sentinel** | Risk Enforcement | **Bhishma** — unbreakable vow | **Draco** — the dragon, guardian | **Cerberus** — three-headed guardian | **Capricorn** — the sea-goat, disciplined, rule-enforcer, conservative | Justice | **Shield** |
| **Maverick** | Trader | **Arjuna** — "only the eye of the fish" | **Sagittarius** — the archer | **Artemis** — never misses | **Scorpio** — precise, strategic, calculated, intense focus | The Chariot | **Archer** |
| **Atlas** | Infra & Analytics | **Vishwakarma** — divine architect | **Polaris** — the north star | **Hephaestus** — god of the forge | **Virgo** — the analyst, detail-oriented, systems thinker, improver | The Hermit | **Forge** |

---

## Philosophy

Every agent exists because it owns a distinct **payoff function** — a measure of success that it maximizes. Agents are not wrappers around services. They are autonomous decision-makers that get smarter over time through AI/ML. If an agent can't articulate its payoff function or path to intelligence, it doesn't belong.

**"Trade Small, Trade Frequent. Capital Preservation First. Every Event Is Data."**

---

## The Five Agents

```
  Chanakya (Scout)        — Sees the battlefield
  Kubera (Steward)        — Guards the treasury
  Bhishma (Sentinel)      — Enforces the vows
  Arjuna (Maverick)       — Takes the shot
  Vishwakarma (Atlas)     — Builds the machine
```

---

## CHANAKYA — The Strategist (Scout)

> *Kautilya, author of Arthashastra. The mind behind the Maurya empire. Saw what others couldn't.*

### Identity
Chanakya is the **market intelligence engine**. He reads the world — regimes, technicals, fundamentals, macro — and identifies where opportunity lives. He doesn't trade. He advises.

### What He Owns
- **Sole interface to MarketAnalyzer** (20+ services, nobody else calls MA)
- ResearchContainer — the complete market picture for every ticker
- Watchlist resolution (broker watchlists → ticker universe)
- Two-phase screening (fast screen → deep rank)
- Strategy selection via Thompson Sampling bandits

### Payoff Function
```
Maximize: Information quality × Signal accuracy

Measures:
  - Candidate → proposal conversion rate (how many survive Arjuna's gates)
  - Score ↔ P&L correlation (do high-scored trades actually win?)
  - Regime detection accuracy (does R1 really mean calm market?)
  - Screening efficiency (candidates / tickers scanned ratio)
  - Data freshness (how old is the research? stale = penalty)
```

### Intelligence — Gets Smarter Over Time

| Capability | How It Learns | ML System |
|-----------|--------------|-----------|
| Strategy selection | Thompson Sampling: Beta(wins, losses) per regime×strategy cell. Explores undersampled, exploits proven. | ML-E2 Bandits |
| IV rank integration | Passes IV rank to each assessor. Assessors have learned hard stops (IC < 15, IFly < 20). | SQ1, SQ9 |
| Regime staleness | Detects when HMM model is outdated (>60 days). Triggers retrain. | SQ2 |
| POP calibration | Corrects probability estimates from actual win rates per regime. | ML-E4, SQ3 |
| Commentary | Captures step-by-step reasoning from every MA service (debug=True). | G08 |
| Data gaps | Flags where analysis is weak — missing IV, stale regime, no fundamentals. | G09 |

### Key Decisions Chanakya Makes
1. Which tickers to analyze (watchlist resolution)
2. Which candidates pass screening (min_score threshold)
3. Which strategies to prioritize per regime (bandit selection)
4. Whether market context allows trading (black swan, macro calendar)
5. Quality assessment of every recommendation (data gaps, commentary)

---

## KUBERA — The Treasurer (Steward)

> *God of wealth in Hindu mythology. Treasurer of the gods. Guardian of the north. Manages the riches of the entire cosmos.*

### Identity
Kubera is the **portfolio architect and performance accountant**. He decides how capital is allocated across desks, tracks performance at every level (portfolio, desk, strategy, ticker), and determines whether the system is making money efficiently.

### What He Owns
- **Capital allocation across desks** — how much goes to 0DTE vs Medium vs LEAPs
- **Portfolio-level performance** — P&L attribution, Sharpe, drawdown, win rate by desk
- **Desk rebalancing** — when a desk is underperforming, shift capital
- **Black swan response** — when Bhishma triggers a halt, Kubera decides how to unwind
- **Position-level P&L attribution** — delta, theta, gamma, vega contribution

### Payoff Function
```
Maximize: Risk-adjusted return across all desks
         (Total portfolio Sharpe ratio)

Measures:
  - Sharpe ratio per desk and aggregate
  - Capital efficiency: P&L / capital deployed
  - Drawdown control: max drawdown per desk
  - Desk allocation optimality: did the right desk get more capital?
  - Theta earned per day per dollar deployed
  - Win rate by desk (accountability per virtual book)
  - Recovery speed: how fast does P&L recover after drawdown?
```

### Intelligence — Gets Smarter Over Time

| Capability | How It Learns | ML System |
|-----------|--------------|-----------|
| Desk capital allocation | Analyze performance per desk. Shift capital toward high-Sharpe desks. Reduce allocation to underperforming desks. | **NEW: Capital optimization from outcomes** |
| Strategy weighting | `calibrate_weights(outcomes)` adjusts how strategies are scored based on actual performance. | ML-E3 via MA |
| Performance attribution | Track which Greek (delta, theta, vega) drives P&L. Optimize desk composition toward theta-dominant strategies in calm markets. | **NEW: Greek attribution analysis** |
| Desk creation | Given account size and risk tolerance, suggest optimal desk configuration. For SaaS: onboarding wizard. | **NEW: Desk configuration engine** |
| Benchmark tracking | Compare desk performance against passive strategies (buy-and-hold SPY, sell-put on SPY). Is the system adding alpha? | **NEW: Alpha measurement** |

### Key Decisions Kubera Makes
1. How to split account capital across desks (currently YAML, should learn)
2. When to rebalance (shift capital from underperforming desk)
3. Performance grading per desk (is desk_0dte earning its allocation?)
4. Unwinding strategy when Bhishma halts trading
5. Daily P&L report — theta earned, realized/unrealized, attribution

### Current State vs Vision

| Capability | Current | Vision |
|-----------|---------|--------|
| populate() | DB → context flattening | Same (necessary plumbing) |
| Capital utilization | Deterministic rules from YAML | **ML-driven**: learn optimal deployment % from performance |
| Desk allocation | Fixed YAML ($10K/$15K/$20K) | **ML-driven**: shift capital based on Sharpe per desk |
| Performance reporting | Basic P&L aggregation | **Full attribution**: by Greek, by strategy, by regime |
| Desk creation | Manual CLI | **AI-suggested**: given account size → recommend desks |
| Black swan response | Not owned | **Should own**: Bhishma halts, Kubera decides unwinding order |

---

## BHISHMA — The Guardian (Sentinel)

> *The grandsire of the Kuru dynasty. Took an unbreakable vow of celibacy to protect his father's kingdom. Stood guard for generations. Could only fall by his own choice.*

### Identity
Bhishma is the **risk enforcer**. His vows (circuit breakers) are unbreakable. When the market turns hostile, Bhishma halts everything. No agent overrides him without explicit human rationale.

### What He Owns
- **5 circuit breakers** — daily loss, weekly loss, VIX spike, portfolio drawdown, consecutive losses
- **8 trading constraints** — max trades/day, time-of-day, undefined risk, adding to losers
- **Override mechanism** — rationale-based override (human must explain why)
- **The HALT decision** — when Bhishma says stop, everything stops

### Payoff Function
```
Maximize: Capital preserved during adverse conditions
         (zero catastrophic losses)

Measures:
  - Max drawdown during live trading (should never exceed configured limit)
  - Circuit breaker trigger accuracy (true positives vs false positives)
  - Time-to-halt: how fast does the system react to a VIX spike?
  - Override justification quality: were overrides good decisions?
  - Recovery after halt: did halting actually prevent further losses?
```

### Intelligence — Rule-Based (By Design)

**Bhishma does NOT use ML.** This is intentional.

Risk enforcement should be **deterministic and predictable**. A risk system that "learns" to allow bigger losses is broken. Hard rules are the correct architecture for safety systems.

However, Bhishma CAN evolve through:

| Capability | How It Evolves | ML? |
|-----------|---------------|-----|
| Threshold calibration | Analyze historical halts. Were thresholds too tight (false positives) or too loose (missed a crash)? | **Semi-ML**: statistical analysis, not gradient descent |
| Constraint validation | After N trades, check if constraints (max trades/day) were optimal. Were more profitable trades missed? | **Retrospective analysis** |
| Black swan detection | Currently reads MA's black_swan.alert(). Could add: correlation breakdown, credit spread blow-out, liquidity freeze detection. | **Rule enrichment**, not ML |
| Override audit | Track all overrides. Were they justified? Did overriding lead to better or worse outcomes? | **Retrospective scoring** |

### Why Bhishma Stays Rule-Based
"I would rather take no action than compulsions." — Nitin

Bhishma embodies this. He doesn't learn to take action. He learns to NOT take action (halt) more precisely. His vows get **tighter**, never looser.

---

## ARJUNA — The Archer (Maverick)

> *The greatest archer in the Mahabharata. When asked what he sees, Arjuna says: "I see only the eye of the fish." Focused, precise, disciplined. Never takes a shot he doesn't believe in.*

### Identity
Arjuna is the **trader**. He receives Chanakya's intelligence, checks with Bhishma's rules, and takes precise shots through 11 gates. Every trade has a reason. Every rejection has a reason. Nothing is impulsive.

### What He Owns
- **11-gate quality filter** — the most rigorous trade selection in the system
- **3 trading desks** — 0DTE ($10K), Medium ($15K), LEAPs ($20K)
- **Position sizing** — 2% risk per trade, MA-computed contracts
- **Trade booking** — TradeSpec → legs → DB, with full lineage
- **Exit monitoring** — delegates to MA's monitor_exit_conditions()
- **Adjustment pipeline** — delegates to MA's recommend_action()
- **Decision lineage** — full audit trail for every proposal (accepted or rejected)

### Payoff Function
```
Maximize: P&L per unit of risk deployed (desk-level Sharpe)

Measures:
  - Win rate per desk (target: > 60%)
  - Average P&L per trade
  - Sharpe ratio per desk (target: > 1.0)
  - Gate selectivity: rejection rate (higher = more disciplined)
  - Profit factor: gross wins / gross losses (target: > 1.5)
  - Theta earned per day (income metric for credit strategies)
  - Time-in-trade efficiency: are we holding too long?
```

### Intelligence — Gets Smarter Over Time

| Capability | How It Learns | ML System |
|-----------|--------------|-----------|
| Gate 6: ML pattern score | Q-learning from regime:iv:strategy:dte:side patterns | TradeLearner |
| Gate 6b: Drift detection | Flags degrading strategies. CRITICAL → suspend. WARNING → reduce size. | ML-E1 |
| Gate 7: POP calibration | Probability corrected from actual win rates per regime | ML-E4 |
| Gate thresholds | POP min, score min, IV rank limits self-tune from outcomes | ML-E3 |
| Bandit-informed ranking | Strategies ranked by learned win rates (via Chanakya) | ML-E2 |
| Decision lineage | Full audit trail feeds all learning systems | G14 |

### 11 Gates — "I See Only the Eye of the Fish"

| # | Gate | What Arjuna Checks | Intelligence |
|---|------|-------------------|-------------|
| 1 | Verdict | MA says GO or CAUTION (not NO_GO) | MA's assessment |
| 2 | Score | Composite ranking >= 0.35 | MA's 10-factor score |
| 3 | Trade spec | Valid legs with strikes and expirations exist | Structure validation |
| 3b | Buying power | Wing width × 100 fits available capital | Capital check |
| 4 | No duplicates | Not already holding this ticker:strategy | Portfolio awareness |
| 5 | Position limit | Under max positions for desk | Risk constraint |
| 6 | ML pattern | Historical pattern doesn't say AVOID | **Q-learning** |
| 6b | Drift check | Strategy not CRITICAL degradation | **Drift detection** |
| 7 | POP | Probability of profit >= 45% | **Calibrated from outcomes** |
| 8 | EV | Expected value > $0 | **Feeds from POP** |
| 9 | Income entry | IV rank, RSI, regime all in sweet spot | MA's entry check |
| 10 | Time window | Within allowed entry hours | Time constraint |
| 11 | Liquidity | Bid-ask spread, OI, volume acceptable | MA's execution quality |

---

## VISHWAKARMA — The Architect (Atlas)

> *The divine architect in Hindu mythology. Built Lanka for Kubera, Indraprastha for the Pandavas, weapons for the gods. The creator who ensures everything works.*

### Identity
Vishwakarma is the **infrastructure and intelligence architect**. He ensures the AI/ML systems are healthy, identifies gaps in the platform, manages communication infrastructure (chat, MCP, notifications), and continuously improves the machine itself.

### What He Owns
- **Trading floor health** — is every component operational? Broker connected? Data flowing?
- **System failure detection** — agent crashes, DB errors, broker timeouts, stale prices
- **AI/ML infrastructure** — are models trained? Bandits current? Thresholds optimized?
- **Data analytics** — cross-agent insights, performance attribution, correlation analysis
- **Communication infrastructure** — MCP servers, chat interfaces, notifications
- **Gap identification** — what capabilities are missing? What's degraded?
- **Self-improvement** — propose new ML features, identify automation opportunities

### Payoff Function
```
Maximize: System reliability × intelligence depth × uptime
         (zero silent failures, every ML model current, full data coverage)

Measures:
  Trading Floor Health:
  - Broker connection uptime (target: 99.5% during market hours)
  - Agent success rate per cycle (target: 100%)
  - Data pipeline completeness: TradeOutcome for every close, lineage for every booking
  - Price freshness: max staleness across all open positions (target: < 30 min)
  - API response time: p95 < 500ms

  AI/ML Health:
  - ML model freshness: days since last bandit update, threshold optimization, POP calibration
  - Drift alert coverage: % of (regime, strategy) cells monitored
  - Learning velocity: outcomes per week feeding into ML systems
  - Model accuracy: predicted POP vs actual win rate per regime

  Data Analytics:
  - Cross-desk correlation: are desks diversified or correlated?
  - Greek attribution accuracy: model P&L vs actual P&L (attribution error)
  - Regime transition analysis: what happens to P&L when regime changes?
  - Strategy performance decay: which strategies are aging out?
  - Fill quality: slippage analysis (planned entry vs actual fill)
```

### Intelligence — Gets Smarter Over Time

| Capability | How It Learns | ML System |
|-----------|--------------|-----------|
| Failure prediction | Track error patterns per agent/service. Predict failures before they happen. | **Anomaly detection on system metrics** |
| ML model monitoring | Track accuracy of POP, regime, bandits against actual outcomes. Flag degradation. | **Meta-ML: analyzing the analyzers** |
| Data quality scoring | Score each data field by freshness, completeness, accuracy. Surface gaps. | **Statistical monitoring** |
| Analytics insights | Correlate: regime transitions × P&L, strategy × time-of-day, desk × market condition. | **Cross-dimensional analysis** |
| Notification intelligence | Learn which events need immediate alert vs daily digest vs ignore. | **Priority learning from user response** |
| Gap-to-impact analysis | When a capability is missing, estimate P&L impact of adding it. | **Counterfactual analysis** |

### Trading Floor Health Checks

| Check | Frequency | What It Monitors | Action on Failure |
|-------|-----------|-----------------|-------------------|
| Broker connection | Every cycle | Can we reach TastyTrade? DXLink streaming? | Alert + switch to offline mode |
| Price freshness | Every cycle | Any position with price > 30 min old? | Alert + force mark-to-market |
| Agent run health | Every cycle | Did each agent complete without error? | Log + alert if 3 consecutive failures |
| DB integrity | Daily | Orphan trades? Missing legs? Inconsistent state? | Alert + auto-repair if possible |
| ML model age | Daily | Bandits > 7 days old? Thresholds > 30 days? POP > 14 days? | Trigger learning cycle |
| Decision lineage | Every booking | Was lineage stored? Are all gate results present? | Alert if missing |
| Position reconciliation | Daily | Do DB positions match broker positions? | Alert + flag discrepancies |
| Capital consistency | Daily | Do desk allocations sum correctly? Any negative BP? | Alert |

### Data Analytics Layer

| Analysis | What It Reveals | Frequency |
|----------|----------------|-----------|
| **Regime × P&L heatmap** | Which regimes are profitable? Where are we losing? | Weekly |
| **Strategy lifecycle** | How long does each strategy stay profitable? When does it decay? | Monthly |
| **Greek attribution** | Is P&L from theta (intended) or delta (unintended direction bet)? | Daily |
| **Desk correlation** | Are 0DTE and Medium correlated? (Bad: concentrated risk) | Weekly |
| **Fill quality** | Slippage: planned entry vs actual. Are we getting fair fills? | Per trade |
| **Gate efficiency** | Which gate rejects most? Is any gate never triggered (redundant)? | Monthly |
| **Time-of-day analysis** | Best entry times? Does P&L vary by hour? | Monthly |
| **Win rate by regime transition** | Trades entered in R1 that hit R3 during hold — what happens? | Monthly |
| **Bandit convergence** | Are bandit distributions narrowing? (More data = more confident) | Weekly |
| **Confidence calibration** | Trades with POP 70% — did 70% actually win? | Monthly |

### Current State vs Vision

| Capability | Current | Vision |
|-----------|---------|--------|
| Trading floor health | Not monitored | **Full dashboard**: broker, agents, DB, prices, pipelines |
| System failures | Logged but not monitored | **Active monitoring**: error rate tracking, failure prediction |
| ML model health | Not checked | **Freshness dashboard**: when was each model last trained? |
| Data analytics | Basic P&L only | **Full analytics**: regime heatmap, Greek attribution, gate efficiency |
| MCP | Not implemented | Broker MCP, notification MCP, chat interface |
| Notifications | Not implemented | Slack/email: halt, drift, close, P&L threshold, system failure |
| Position reconciliation | Not implemented | DB vs broker position matching |
| Self-improvement | Not implemented | "50 closed trades, threshold optimization is 30 days stale" |

### Why Vishwakarma Matters
Without Vishwakarma, the system becomes a **black box that silently degrades**. Models go stale. Data pipelines break. Broker disconnects go unnoticed. Gaps accumulate. Nobody notices until P&L drops.

Vishwakarma is the agent that **watches the watchers**. He ensures the machine keeps getting smarter — and sounds the alarm when it stops.

---

## THE LEARNING ECOSYSTEM

```
                    Chanakya (Scout)
                    ┌─ Market intelligence
                    ├─ Thompson Sampling selection ←────── closed trades
                    ├─ IV rank threading ←──────────────── broker metrics
                    └─ Commentary + data gaps ←─────────── MA debug mode
                         │
                         ▼ ranked candidates
                    Arjuna (Maverick)
                    ┌─ 11-gate filter
                    ├─ Gate 6: Q-learning score ←────────── pattern database
                    ├─ Gate 6b: drift detection ←────────── recent win rates
                    ├─ Gate 7: calibrated POP ←──────────── regime factors
                    ├─ Gate thresholds ←─────────────────── optimized cutoffs
                    └─ Decision lineage → stored
                         │
                         ▼ trade booked / closed
                    Kubera (Steward)
                    ┌─ Performance tracking
                    ├─ Desk P&L attribution ←────────────── Greek decomposition
                    ├─ Capital reallocation ←────────────── desk Sharpe comparison
                    └─ Daily report → user
                         │
                         ▼ trade outcomes
                    ML Learning Loop
                    ┌─ ML-E1: Drift detection → Arjuna
                    ├─ ML-E2: Bandit update → Chanakya
                    ├─ ML-E3: Threshold tune → Arjuna
                    ├─ ML-E4: POP calibration → Chanakya
                    └─ ML-E6: Q-learning → Arjuna
                         │
                         ▼ system health
                    Vishwakarma (Atlas)
                    ┌─ ML model freshness monitoring
                    ├─ Data pipeline validation
                    ├─ Gap identification
                    └─ Self-improvement proposals

    Throughout: Bhishma (Sentinel) enforces vows. Cannot be overridden.
```

---

## AGENT PIPELINE — Who Runs When

```
Every 30 minutes (market hours):

  1. Kubera.populate()        Load portfolio state from DB
  2. Bhishma.run()            Circuit breakers (may HALT)
  3. Kubera.run()             Capital utilization + performance
  4. Chanakya.populate()      Fetch market intelligence (15+ MA services)
  5. Chanakya.run()           Screen → Rank → Select strategies
  6. Mark-to-market           Update prices + health checks
  7. Arjuna.run()             11 gates → proposals → exits
  7b. Auto-book               Proposals → WhatIf desks
  8. Auto-close               URGENT exit signals → close trades
  8b. Adjustments             TESTED/BREACHED → roll/close
  9. ML learning              Every 10th cycle: drift, bandits, thresholds
  10. Vishwakarma.run()       System health + gap check (future)

Every 2 minutes (0DTE desk):
  - Intraday fast cycle: IntradayService signals → auto-close

3:30 PM:
  - Overnight risk assessment → close dangerous holds

End of day:
  - P&L report
  - ML learning cycle
  - System health check
```

---

## NAMING OPTIONS

### Option A: Indian Mythology

| Agent | Name | Character | Why |
|-------|------|-----------|-----|
| Scout | **Chanakya** (चाणक्य) | Strategist behind Maurya empire | Sees the battlefield. Reads markets. Advises with intelligence. |
| Steward | **Kubera** (कुबेर) | God of wealth, treasurer of the gods | Guards the treasury. Allocates capital. Measures performance. |
| Sentinel | **Bhishma** (भीष्म) | Grandsire with unbreakable vow | Enforces inviolable rules. Cannot be overridden. |
| Maverick | **Arjuna** (अर्जुन) | Greatest archer — "I see only the eye of the fish" | Precise execution. 11 gates. Never takes a shot he doesn't believe in. |
| Atlas | **Vishwakarma** (विश्वकर्मा) | Divine architect who built cities for the gods | Builds the machine. Watches the watchers. |

### Option B: Constellations

| Agent | Name | Constellation | Why |
|-------|------|--------------|-----|
| Scout | **Orion** | The Hunter — always scanning the sky | Scans markets, hunts for opportunities |
| Steward | **Libra** | The Scales — balance and measurement | Weighs capital allocation, measures performance |
| Sentinel | **Draco** | The Dragon — guardian of the celestial pole | Guards the treasury, never sleeps |
| Maverick | **Sagittarius** | The Archer — precise, aimed, fires with purpose | 11 gates, every shot deliberate |
| Atlas | **Polaris** | The North Star — always present, guides navigation | System health, guides infrastructure |

### Option C: Greek/Western Mythology

| Agent | Name | Character | Why |
|-------|------|-----------|-----|
| Scout | **Hermes** | Messenger of the gods, bringer of intelligence | Market intelligence, carries information |
| Steward | **Plutus** | God of wealth | Treasury, capital allocation, performance |
| Sentinel | **Cerberus** | Three-headed guardian of the underworld | 5 circuit breakers, nothing passes unchecked |
| Maverick | **Artemis** | Goddess of the hunt, never misses | Precision, 11 gates, disciplined execution |
| Atlas | **Hephaestus** | God of the forge, built tools for the gods | Builds and maintains the machine |

---

---

## CAPABILITIES, GAPS & PLAN OF ACTION

### CHANAKYA (Scout) — Capabilities & Gaps

| # | Capability | Status | Intelligence | Gap / Next Step | Priority |
|---|-----------|--------|-------------|-----------------|----------|
| C1 | Regime detection (R1-R4 via HMM) | **BUILT** | ML (HMM) | Regime staleness check wired | — |
| C2 | Technical analysis (RSI, MACD, BB, Stochastic, S/R) | **BUILT** | No | — | — |
| C3 | Advanced technicals (Fibonacci, ADX, Donchian, Keltner, Pivots, VWAP) | **BUILT** | No | — | — |
| C4 | Smart money (Order Blocks, FVGs) | **BUILT** | No | — | — |
| C5 | Fundamentals (PE, growth, margins, earnings) | **BUILT** | No | — | — |
| C6 | Macro calendar (FOMC, CPI, NFP) | **BUILT** | No | — | — |
| C7 | Black swan / tail risk monitor | **BUILT** | No | — | — |
| C8 | Two-phase scan (screen → rank) | **BUILT** | No | — | — |
| C9 | Thompson Sampling strategy selection | **BUILT** | **ML-E2** | Bandit update on close wired | — |
| C10 | IV rank threading to ranking | **BUILT** | SQ9 | Wired in Scout.run() | — |
| C11 | Commentary / debug mode | **BUILT** | G08 | `debug=True` passed to context.assess() | — |
| C12 | Data gap identification | **BUILT** | G09 | Stored in context for lineage | — |
| C13 | Watchlist from broker (MA-Income) | **BUILT** | No | — | — |
| C14 | Volatility surface / term structure | **BUILT** | No | Not used in screening yet | LOW |
| C15 | Sector rotation signals | GAP | No | Cross-sector regime comparison. Which sectors leading/lagging? | MEDIUM |
| C16 | Earnings calendar integration | PARTIAL | No | MA has earnings dates. Scout doesn't filter by "earnings this week." | LOW |
| C17 | Correlation-aware screening | **BUILT** | SQ7 | Dedup correlated candidates | — |
| C18 | Multi-timeframe analysis | GAP | No | Daily + weekly regime confluence. Weekly bullish + daily R1 = stronger signal. | MEDIUM |
| C19 | Sentiment / options flow | GAP | No | Put/call ratio, unusual options activity, dark pool prints | LOW |

### KUBERA (Steward) — Capabilities & Gaps

| # | Capability | Status | Intelligence | Gap / Next Step | Priority |
|---|-----------|--------|-------------|-----------------|----------|
| K1 | Portfolio state loading (DB → context) | **BUILT** | No | — | — |
| K2 | Capital utilization analysis | **BUILT** | No | Deterministic rules. Should learn optimal deployment %. | MEDIUM |
| K3 | Staggered capital ramp | **BUILT** | No | — | — |
| K4 | Performance reporting (P&L, win rate) | **BUILT** | No | Basic. Needs Greek attribution, by-desk breakdown. | HIGH |
| K5 | Desk capital allocation | CONFIG | No | Fixed YAML. Should learn: shift capital toward high-Sharpe desks. | **HIGH** |
| K6 | Desk performance comparison | GAP | **ML needed** | Compare desks by Sharpe, profit factor. Recommend reallocation. | **HIGH** |
| K7 | Greek P&L attribution | GAP | Analytics | How much P&L from theta vs delta vs vega? Per desk. | **HIGH** |
| K8 | Black swan response / unwinding | GAP | No | When Bhishma halts, Kubera should decide unwinding order (most liquid first, least risk last). | MEDIUM |
| K9 | Daily P&L report generation | GAP | No | Morning: overnight P&L, theta earned, positions at risk, cash flow. | **HIGH** |
| K10 | Desk creation wizard (SaaS) | GAP | **ML** | Given account size + risk tolerance → recommend desk count, capital split, strategies. | LOW (SaaS) |
| K11 | Benchmark comparison | GAP | Analytics | Is each desk beating SPY buy-and-hold? Sell-put on SPY? Quantify alpha. | MEDIUM |
| K12 | Trade outcome pipeline | **BUILT** | ML-E1-E5 | TradeOutcome construction from closed trades | — |
| K13 | Weight calibration | **BUILT** | ML via MA | calibrate_weights() from outcomes | — |
| K14 | Performance report (full) | **BUILT** | ML via MA | compute_performance_report() | — |

### BHISHMA (Sentinel) — Capabilities & Gaps

| # | Capability | Status | Intelligence | Gap / Next Step | Priority |
|---|-----------|--------|-------------|-----------------|----------|
| B1 | Daily loss circuit breaker | **BUILT** | Rules | — | — |
| B2 | Weekly loss circuit breaker | **BUILT** | Rules | — | — |
| B3 | VIX spike circuit breaker | **BUILT** | Rules | — | — |
| B4 | Portfolio drawdown breaker | **BUILT** | Rules | — | — |
| B5 | Consecutive losses breaker | **BUILT** | Rules | — | — |
| B6 | Max trades per day | **BUILT** | Rules | — | — |
| B7 | Time-of-day constraints | **BUILT** | Rules | — | — |
| B8 | Undefined risk blocking | **BUILT** | Rules | — | — |
| B9 | Override with rationale | **BUILT** | No | — | — |
| B10 | Threshold retrospective | GAP | **Semi-ML** | After N halts, were thresholds too tight or too loose? Suggest adjustment. | MEDIUM |
| B11 | Correlation breakdown detection | GAP | Rules | When SPY-TLT correlation flips → structural risk. Alert even if VIX is calm. | MEDIUM |
| B12 | Liquidity freeze detection | GAP | Rules | When bid-ask spreads blow out across multiple tickers → market stress. | LOW |
| B13 | Override audit trail | GAP | Analytics | Were overrides good decisions? Track outcome of every override. | LOW |
| B14 | Cross-desk risk aggregation | GAP | No | Net delta across ALL desks. Total portfolio exposure, not per-desk. | **HIGH** |

### ARJUNA (Maverick) — Capabilities & Gaps

| # | Capability | Status | Intelligence | Gap / Next Step | Priority |
|---|-----------|--------|-------------|-----------------|----------|
| A1 | Gate 1-5: Basic filters | **BUILT** | No | — | — |
| A2 | Gate 6: ML pattern score | **BUILT** | **Q-learning** | — | — |
| A3 | Gate 6b: Drift detection | **BUILT** | **ML-E1** | — | — |
| A4 | Gate 7-8: POP + EV | **BUILT** | **ML-E4** (calibrated) | — | — |
| A5 | Gate 9: Income entry check | **BUILT** | No (MA decides) | — | — |
| A6 | Gate 10: Entry time window | **BUILT** | No | — | — |
| A7 | Gate 11: Execution quality | **BUILT** | No (MA checks) | — | — |
| A8 | Position sizing (MA) | **BUILT** | No | — | — |
| A9 | Desk routing by DTE | **BUILT** | No | — | — |
| A10 | Trade booking + lineage | **BUILT** | G14 | — | — |
| A11 | Exit monitoring (MA) | **BUILT** | No (MA decides) | — | — |
| A12 | Health checks (MA) | **BUILT** | No (MA decides) | — | — |
| A13 | Adjustment pipeline | **BUILT** | No (MA decides) | — | — |
| A14 | Overnight risk | **BUILT** | No (MA decides) | — | — |
| A15 | ExitPlan serialization | **BUILT** | No | — | — |
| A16 | Breakeven storage | **BUILT** | No | — | — |
| A17 | Multi-leg order generation | GAP | No | For adjustments: generate the actual closing + opening legs. Currently flags for human. | **HIGH** |
| A18 | Partial close (scale out) | GAP | No | Close 50% at TP1, hold rest for TP2. ExitPlan supports this but not wired. | MEDIUM |
| A19 | Roll execution | GAP | No | When MA says ROLL_AWAY → generate roll order (close old, open new strikes). | **HIGH** |
| A20 | Trailing stop | GAP | No | ExitPlan has trailing_stop field. Not wired in exit monitor. | MEDIUM |

### VISHWAKARMA (Atlas) — Capabilities & Gaps

| # | Capability | Status | Intelligence | Gap / Next Step | Priority |
|---|-----------|--------|-------------|-----------------|----------|
| V1 | Agent run health tracking | GAP | Anomaly detection | Track run times, success/failure per agent per cycle. Alert on degradation. | **HIGH** |
| V2 | Broker connection monitoring | GAP | Rules | Is DXLink connected? Are quotes flowing? Timeout detection. | **HIGH** |
| V3 | Price freshness monitoring | GAP | Rules | Any position with stale price > 30 min? Force mark-to-market. | **HIGH** |
| V4 | ML model freshness | GAP | **Meta-ML** | Dashboard: when was each ML model last trained/updated? Auto-trigger if stale. | **HIGH** |
| V5 | Data pipeline validation | GAP | Rules | TradeOutcome for every close? Lineage for every booking? Alert if missing. | MEDIUM |
| V6 | Position reconciliation | GAP | Rules | DB positions vs broker positions. Flag discrepancies. | **HIGH** |
| V7 | Regime × P&L heatmap | GAP | Analytics | Which regime:strategy cells are profitable? Visual. | MEDIUM |
| V8 | Greek P&L attribution | GAP | Analytics | Theta earned vs delta movement vs vega change. Per desk. | MEDIUM |
| V9 | Gate efficiency analysis | GAP | Analytics | Which gates reject most? Any gate never triggered (redundant)? | LOW |
| V10 | Confidence calibration | GAP | **ML** | Trades with POP 70% — did 70% actually win? Calibration chart. | MEDIUM |
| V11 | Desk correlation analysis | GAP | Analytics | Are desks diversified or correlated? Risk concentration flag. | MEDIUM |
| V12 | Fill quality / slippage | GAP | Analytics | Planned entry vs actual fill. Spread cost tracking. | LOW |
| V13 | MCP server management | GAP | No | Broker MCP, notification MCP, external tool connections. | LOW (future) |
| V14 | Notification routing | GAP | **ML** | Which events → Slack? Email? Push? Learn from user response. | MEDIUM |
| V15 | Self-improvement proposals | GAP | **Meta-ML** | "You have 50 trades but haven't run threshold optimization in 30 days." | LOW |
| V16 | System performance benchmarks | GAP | Analytics | Scan latency, rank latency, booking latency. Track over time. | LOW |

---

## PRIORITY PLAN OF ACTION

### Immediate (Next 1-2 sessions)

| # | What | Agent | Why | Effort |
|---|------|-------|-----|--------|
| 1 | Daily P&L report | Kubera | Users need morning briefing. Theta earned, overnight changes, positions at risk. | Medium |
| 2 | Cross-desk risk aggregation | Bhishma | Net delta/vega across ALL desks. Can't manage risk per-desk only. | Medium |
| 3 | Broker connection monitoring | Vishwakarma | Silent disconnects = stale prices = bad decisions. Must detect. | Small |
| 4 | Agent run health tracking | Vishwakarma | Know when agents fail. Currently silent. | Small |
| 5 | Greek P&L attribution | Kubera | Is P&L from theta (intended) or delta (accidental)? Critical insight. | Medium |

### Short-term (Next 3-5 sessions)

| # | What | Agent | Why | Effort |
|---|------|-------|-----|--------|
| 6 | Desk performance comparison | Kubera | Which desk earns its capital? Data-driven reallocation. | Medium |
| 7 | Multi-leg order generation | Arjuna | Adjustments currently flag for human. Should generate exact legs. | Medium |
| 8 | ML model freshness dashboard | Vishwakarma | Know when bandits/thresholds/POP are stale. Auto-trigger retraining. | Small |
| 9 | Position reconciliation | Vishwakarma | DB vs broker match. Foundation for real trading. | Medium |
| 10 | Regime × P&L heatmap | Vishwakarma | Visual: which cells make money? Which lose? | Small |

### Medium-term (5-10 sessions)

| # | What | Agent | Why | Effort |
|---|------|-------|-----|--------|
| 11 | Dynamic desk capital allocation | Kubera | ML: shift capital toward high-Sharpe desks. | Large |
| 12 | Trailing stop wiring | Arjuna | ExitPlan supports it. Exit monitor doesn't use it yet. | Medium |
| 13 | Roll execution (full legs) | Arjuna | ROLL_AWAY → generate close + open legs automatically. | Medium |
| 14 | Confidence calibration chart | Vishwakarma | POP 70% trades: did 70% win? Visual calibration. | Small |
| 15 | Notification system (Slack) | Vishwakarma | Halt, drift, trade booked, P&L threshold → Slack channel. | Medium |

---

## MEASURES OF SUCCESS — SCOREBOARD

| Agent | Primary Metric | Target | Secondary Metrics |
|-------|---------------|--------|-------------------|
| **Chanakya** | Score ↔ P&L correlation | > 0.5 | Candidate conversion rate, data freshness |
| **Kubera** | Portfolio Sharpe ratio | > 1.0 | Capital efficiency, drawdown control, theta/day |
| **Bhishma** | Max drawdown vs limit | Never exceeds | Circuit breaker accuracy, time-to-halt |
| **Arjuna** | Win rate × average P&L | > 60% WR, > $0 avg | Profit factor > 1.5, gate rejection rate |
| **Vishwakarma** | System uptime × ML freshness | 99%+ | Gap count trending to zero, notification coverage |
