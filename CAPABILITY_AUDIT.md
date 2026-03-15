# Capability Audit — What's in UI vs CLI-Only vs Not Wired
# Date: 2026-03-15 (Session 41 overnight)
# MA: 62+ functions, 88 instruments, 48 CLI commands, 10 presets
# eTrading: 25+ CLI commands, 40+ API endpoints, 12 frontend pages
# Reference: market_analyzer/USER_MANUAL.md (trader's perspective)

## Summary (Updated)

Per MA USER_MANUAL.md, MA provides 62+ functions across 10 categories.

| Category | MA Functions | In UI | CLI Only | API Only | Not Wired |
|----------|-------------|-------|----------|----------|-----------|
| Market Analysis (8 services) | context, regime, technicals, levels, phase, fundamentals, macro, vol_surface | 5 | 2 | 1 | 0 |
| Technical Analysis (13 indicators) | RSI, MACD, BB, Stoch, ADX, Fib, Donchian, Keltner, Pivots, VWAP, VCP, SmartMoney, ORB | 6 | 0 | 0 | 7 |
| Trade Assessment (12 assessors) | IC, IFly, calendar, diagonal, ratio, 0DTE, LEAP, earnings, breakout, momentum, MR, ORB | 0 | 0 | 0 | 12 (internal) |
| Trade Analytics (10 functions) | POP+quality, yield, breakevens, income_entry, exec_quality, sizing, Greeks, strike_align, account_filter, entry_window | 5 | 3 | 2 | 0 |
| Position Management (5 functions) | exit_monitor, health_check, adjustment, overnight_risk, intraday | 3 | 5 | 2 | 0 |
| ML/Learning (7 functions) | drift, bandits, thresholds, POP_calibrate, weight_calibrate, Q-learning, performance_report | 1 | 2 | 0 | 4 |
| Performance (4 functions) | sharpe, drawdown, regime_perf, profit_factor | 1 | 1 | 1 | 1 |
| Multi-Market (6) | registry, universe, cross_market, instrument_info, margin, strategy_available | 1 | 2 | 1 | 2 |
| Hedging (4 functions) | assess_hedge, currency_pnl, portfolio_exposure, currency_exposure | 0 | 0 | 1 | 3 |
| Macro (5 functions) | dashboard, bond, credit, dollar, inflation | 1 | 1 | 1 | 2 |
| Currency (4 functions) | convert, exposure, pnl, hedge_assessment | 0 | 0 | 0 | 4 |
| **Total** | **~78** | **23** | **16** | **9** | **35** |

**30% in UI (up from 20%). 45% not wired (down from 60%). Significant improvement.**

### What Improved Since Last Audit
- Macro dashboard → now in UI (Research + Agents page)
- Cross-market → now in UI (Research + Agents page)
- Trade quality score (TQ1) → in proposals + explain modal
- Health detail → clickable badge with exit plan, breakevens, adjustments
- Sharpe/drawdown → Performance Analytics panel on Desks page
- Daily report → panel on Desks page
- System alerts → panel on Desks page
- Explain trade → modal with gates, commentary, data gaps
- Income yield ROC → grid column

### Biggest Remaining Gaps (from USER_MANUAL.md)
1. **7 advanced technicals** not shown (Fibonacci, ADX, Donchian, Keltner, Pivots, VWAP, ORB)
2. **12 assessor details** never visible (user can't see WHY iron condor scored 0.82)
3. **4 currency functions** not wired (currency P&L, exposure, conversion)
4. **4 ML functions** not surfaced in UI (drift alerts, bandit rankings, thresholds — CLI only)
5. **Hedging recommendations** wired in backend but not shown anywhere
6. **Vol surface** computed but never displayed

---

## DETAILED AUDIT

### Legend
- **UI** = Visible in web dashboard (data rendered, action available)
- **CLI** = Available via terminal command only
- **API** = Backend endpoint exists but frontend doesn't call it
- **WIRED** = eTrading calls MA but result not surfaced
- **NOT WIRED** = eTrading doesn't call this MA function

---

### 1. MARKET ANALYSIS

| # | MA Capability | Function | UI | CLI | API | Status | Gap |
|---|--------------|----------|-----|-----|-----|--------|-----|
| 1 | Regime detection (R1-R4) | `ma.regime.detect()` | Research page (regime badge per ticker) | — | `/api/v2/research` | **IN UI** | — |
| 2 | Market context | `ma.context.assess()` | Research page (MarketContextStrip) | — | `/api/v2/context` | **IN UI** | — |
| 3 | Black swan alert | `ma.black_swan.alert()` | Research page (BlackSwanBar) | — | `/api/v2/black-swan` | **IN UI** | — |
| 4 | Daily trading plan | `ma.plan.generate()` | Research page (PlanPanel) | `plan` | `/api/v2/plan` | **IN UI** | — |
| 5 | Macro calendar | `ma.macro.calendar()` | Research page (upcoming events) | — | via plan | **IN UI** | Only shows next event, not full calendar |
| 6 | Regime explanation (HMM deep dive) | `ma.regime.explain()` | — | — | `/api/v2/regime/{ticker}/explain` | **API only** | Has chart endpoint but no UI page to display it |
| 7 | Intermarket dashboard | `ctx.intermarket` | — | — | via context | **NOT SURFACED** | Context has intermarket data but UI doesn't render cross-asset regime comparison |
| 8 | Volatility surface | `ma.vol_surface.surface()` | — | — | — | **NOT WIRED** | Term structure + skew available but nowhere in UI |

### 2. TECHNICAL ANALYSIS

| # | MA Capability | Function | UI | CLI | API | Status | Gap |
|---|--------------|----------|-----|-----|-----|--------|-----|
| 9 | Technical snapshot (RSI, MACD, BB, etc.) | `ma.technicals.snapshot()` | Research page (TickerDetailPanel) | — | `/api/v2/research` | **IN UI** | Shows RSI, MACD, Bollinger. Missing: Fibonacci, ADX, Donchian, Keltner, Pivots, VWAP |
| 10 | Advanced technicals | `tech.fibonacci`, `tech.adx`, `tech.donchian`, `tech.keltner`, `tech.pivot_points`, `tech.daily_vwap` | — | — | Data exists in snapshot but not serialized | **NOT SURFACED** | 6 indicators computed but never reach UI. ResearchSnapshotORM doesn't store them. |

### 3. TRADE ASSESSMENT (11 Strategy Assessors)

| # | MA Capability | Function | UI | CLI | API | Status | Gap |
|---|--------------|----------|-----|-----|-----|--------|-----|
| 11 | Iron condor assessment | `assess_iron_condor()` | — | — | Via ranking (internal) | **INTERNAL** | Assessor runs inside ranking. Result is a score + TradeSpec. User never sees WHY iron condor was chosen. |
| 12 | Iron butterfly | `assess_iron_butterfly()` | — | — | Via ranking | **INTERNAL** | Same |
| 13 | Credit/debit spread | `assess_*_spread()` | — | — | Via ranking | **INTERNAL** | Same |
| 14 | Calendar spread | `assess_calendar()` | — | — | Via ranking | **INTERNAL** | Same |
| 15 | Diagonal spread | `assess_diagonal()` | — | — | Via ranking | **INTERNAL** | Same |
| 16 | Ratio spread | `assess_ratio_spread()` | — | — | Via ranking | **INTERNAL** | Same |
| 17 | 0DTE assessment | `assess_zero_dte()` | — | — | Via ranking | **INTERNAL** | Same |
| 18 | LEAP assessment | `assess_leap()` | — | — | Via ranking | **INTERNAL** | Same |
| 19 | Breakout assessment | `assess_breakout()` | — | — | Via ranking | **INTERNAL** | Same |
| 20 | Momentum assessment | `assess_momentum()` | — | — | Via ranking | **INTERNAL** | Same |
| 21 | Mean reversion | `assess_mean_reversion()` | — | — | Via ranking | **INTERNAL** | Same |
| 22 | Earnings play | `assess_earnings_play()` | — | — | Via ranking | **INTERNAL** | Same |
| 23 | ORB assessment | `assess_orb()` | — | — | Via ranking | **INTERNAL** | Same |

**KEY GAP:** Users can't see individual assessor results. They see the final score but not "Iron condor scored 0.82 because: regime alignment 95%, risk/reward strong, IV rank 45 in sweet spot." This is the commentary (debug=True) that exists but doesn't reach UI.

### 4. TRADE ANALYTICS

| # | MA Capability | Function | UI | CLI | API | Status | Gap |
|---|--------------|----------|-----|-----|-----|--------|-----|
| 24 | Probability of Profit (POP) | `estimate_pop()` | Desks page (POP column), propose output | `propose` | In trade serialization | **IN UI** | Shown as percentage. Missing: regime factor used, confidence interval |
| 25 | Expected Value | `estimate_pop().ev` | Desks page (via POP), propose output | `propose` | In trade serialization | **IN UI** | Shown as dollar amount |
| 26 | Breakevens | `compute_breakevens()` | Trading terminal (BE column) | — | In trade serialization | **IN UI** | Shows low-high range. Missing: visual on price chart |
| 27 | Income yield (ROC) | `compute_income_yield()` | — | — | Stored in TradeORM but not serialized | **NOT SURFACED** | Computed at entry, stored in income_yield_roc. Not in API response or UI. |
| 28 | Income entry check | `check_income_entry()` | — | `propose` (shows confirmed/not) | — | **CLI ONLY** | Gate 9 result shown in propose output but not in UI |
| 29 | Execution quality | `validate_execution_quality()` | — | `propose` (shows GO/WIDE) | — | **CLI ONLY** | Gate 11 result. Not visible in UI. |
| 30 | Position sizing | `spec.position_size()` | — | `propose` (shows contracts) | — | **CLI ONLY** | Contracts shown in propose but not in desk cards |
| 31 | Greeks aggregation | `aggregate_greeks()` | Trading terminal (Greeks columns) | — | In trade serialization | **IN UI** (via broker) | Uses broker Greeks directly, not MA aggregation |
| 32 | Strike alignment to S/R | `align_strikes_to_levels()` | — | — | — | **NOT WIRED** | Available but never called. Could improve strike selection. |
| 33 | Account filtering | `filter_trades_by_account()` | — | — | — | **NOT USED** | We do per-trade BP check (gate 3b) instead. This batch-filters. |

### 5. POSITION MANAGEMENT

| # | MA Capability | Function | UI | CLI | API | Status | Gap |
|---|--------------|----------|-----|-----|-----|--------|-----|
| 34 | Exit monitoring | `monitor_exit_conditions()` | — (health badge visible) | `exits` | — | **CLI + BADGE** | Exit signals shown in CLI. UI only shows health badge (OK/TST/BRK/EXIT). Missing: which rule triggered, P&L%, urgency. |
| 35 | Trade health check | `check_trade_health()` | Health badge in Trading terminal | `health` | — | **CLI + BADGE** | Health status visible. Full details (adjustment options, commentary) only in CLI. |
| 36 | Adjustment recommendation | `recommend_action()` | — | `health` | — | **CLI ONLY** | System recommends HOLD/ROLL/CLOSE but user can't see WHY in UI. Only in CLI health command. |
| 37 | Overnight risk | `assess_overnight_risk()` | — | `health` | — | **CLI ONLY** | Runs in engine EOD. Results in CLI. UI has no overnight risk indicator. |
| 38 | Intraday signals (0DTE) | `ma.intraday.monitor()` | — | — | — | **ENGINE ONLY** | Runs every 2 min for 0DTE. Auto-closes. User never sees signals unless they check CLI. No UI panel. |

### 6. MACHINE LEARNING

| # | MA Capability | Function | UI | CLI | API | Status | Gap |
|---|--------------|----------|-----|-----|-----|--------|-----|
| 39 | Drift detection | `detect_drift()` | — | `ml` | — | **CLI ONLY** | Drift alerts stored in MLStateORM. Not shown in UI. |
| 40 | Thompson Sampling | `build_bandits()`, `select_strategies()` | — | `ml` | — | **CLI ONLY** | Bandit rankings shown in `ml` command. Not in UI. |
| 41 | Threshold optimization | `optimize_thresholds()` | — | `ml` | — | **CLI ONLY** | Optimized thresholds in `ml` command. Not in UI. |
| 42 | POP calibration | `calibrate_pop_factors()` | — | `ml` | — | **CLI ONLY** | Calibrated factors in `ml` command. Not in UI. |
| 43 | Weight calibration | `calibrate_weights()` | — | — | — | **NOT SURFACED** | Runs in ML cycle but results not shown anywhere. |
| 44 | Q-learning patterns | TradeLearner | — | `learn` | — | **CLI ONLY** | Patterns updated. Not shown in UI. |
| 45 | Commentary (debug mode) | `debug=True` on MA calls | — | `explain` | `/api/v2/trades/{id}/explain` | **API EXISTS** | Explain endpoint exists. Frontend has no "explain" button or panel. |
| 46 | Data gaps | `result.data_gaps` | — | `explain` | In lineage | **NOT SURFACED** | Stored in decision_lineage but not shown in trade grid or cards. |

### 7. PERFORMANCE ANALYTICS

| # | MA Capability | Function | UI | CLI | API | Status | Gap |
|---|--------------|----------|-----|-----|-----|--------|-----|
| 47 | Sharpe ratio | `compute_sharpe()` | — | `deskperf` | `/api/v2/desks/performance` | **API EXISTS** | Endpoint exists. DeskPerformance page doesn't call it. |
| 48 | Drawdown analysis | `compute_drawdown()` | — | `deskperf` | `/api/v2/desks/performance` | **API EXISTS** | Same. |
| 49 | Regime performance | `compute_regime_performance()` | — | `deskperf` | `/api/v2/desks/performance` | **API EXISTS** | Same. |
| 50 | Performance report | `compute_performance_report()` | — | — | — | **NOT WIRED** | Full report with per-strategy breakdown, POP accuracy. Not called. |
| 51 | Strategy performance | `compute_strategy_performance()` | — | — | — | **NOT WIRED** | Per-strategy breakdown. Not called. |
| 52 | Profit factor | `compute_profit_factor()` | — | — | — | **NOT WIRED** | Gross wins / gross losses. Not called. |

### 8. MULTI-MARKET

| # | MA Capability | Function | UI | CLI | API | Status | Gap |
|---|--------------|----------|-----|-----|-----|--------|-----|
| 53 | MarketRegistry | `MarketRegistry()` | — | `markets` | `/api/v2/brokers` | **CLI + partial API** | `brokers` endpoint shows broker metadata. `markets` CLI shows instruments. No dedicated UI page. |
| 54 | Instrument info (lot sizes) | `registry.get_instrument()` | — | `markets` | — | **CLI ONLY** | Shows in `markets` command. Not in UI. |
| 55 | Strategy availability | `registry.strategy_available()` | — | — | — | **NOT SURFACED** | Used internally by Maverick. User can't see which strategies are blocked for India. |
| 56 | Margin estimation | `registry.estimate_margin()` | — | — | — | **NOT WIRED** | Available but never called. Could show estimated margin per trade. |
| 57 | Symbol mapping | `registry.to_yfinance()` | — | — | — | **INTERNAL** | Used by DataService. User doesn't need to see this. |

### 9. HEDGING (New — H1-H5)

| # | MA Capability | Function | UI | CLI | API | Status | Gap |
|---|--------------|----------|-----|-----|-----|--------|-----|
| 58 | Currency conversion | `convert_amount()` | — | — | — | **NOT WIRED** | Available but no cross-currency display yet. |
| 59 | Hedge assessment | `assess_hedge()` | — | — | — | **WIRED** (trade_health_service) | Computes hedges. Results not surfaced in CLI or UI. |
| 60 | Currency exposure | `compute_portfolio_exposure()` | — | — | — | **NOT WIRED** | Portfolio-level FX exposure. Not called. |
| 61 | Currency P&L decomposition | `compute_currency_pnl()` | — | — | — | **NOT WIRED** | Trading P&L vs FX P&L. Not called. |

---

## TOP PRIORITY GAPS (What Users Can't See But Should)

### Tier 1: Should Be in UI Now (Data Exists, Just Not Rendered)

| # | What's Missing | Where It Should Go | Data Source | Effort |
|---|---------------|-------------------|-------------|--------|
| A | **Sharpe / drawdown / regime perf per desk** | Desks page — desk cards | `/api/v2/desks/performance` (exists) | Small |
| B | **Explain trade** button | Trading terminal — per-trade action | `/api/v2/trades/{id}/explain` (exists) | Small |
| C | **Exit signals detail** (which rule, P&L%, urgency) | Trading terminal — expandable row or tooltip | Data in health check, not serialized | Medium |
| D | **Adjustment recommendation** (HOLD/ROLL/CLOSE + why) | Trading terminal or Desks page | `health` CLI shows it. Need API. | Medium |
| E | **Daily P&L report** | Reports page | `/api/v2/report/daily` (exists) | Small |
| F | **System events / alerts** | Agents page | `/api/v2/system/events` (exists) | Small |
| G | **Income yield (ROC)** per trade | Trading terminal column | Stored in TradeORM.income_yield_roc. Not in serialization. | Tiny |
| H | **Overnight risk indicator** | Desks page or Trading terminal | Engine runs it. Not surfaced. | Small |

### Tier 2: Should Build API + UI (MA Capability Not Exposed)

| # | What's Missing | Value | Effort |
|---|---------------|-------|--------|
| I | **Assessment breakdown** per trade (why this strategy was chosen) | Users understand the system's reasoning | Medium |
| J | **Advanced technicals** (Fibonacci, ADX, Donchian, Keltner, Pivots, VWAP) | Research page has RSI/MACD but missing 6 new indicators | Medium |
| K | **ML dashboard** (drift alerts, bandit rankings, threshold values, POP calibration) | Show that the system is learning | Medium |
| L | **Volatility surface** (term structure + skew) | Visual for options traders | Medium |
| M | **Intraday signals panel** for 0DTE | Real-time signals during day trades | Medium |
| N | **Margin estimation** per trade | Show estimated buying power impact | Small |
| O | **Strategy availability matrix** | Which strategies work in which market | Small |

### Tier 3: Future (Needs India Broker + Multi-Market)

| # | What's Missing | Needs |
|---|---------------|-------|
| P | **Currency exposure dashboard** | Cross-market positions |
| Q | **FX P&L decomposition** | Trading + FX P&L split |
| R | **Hedge recommendations** in UI | Hedge assessment wired, need panel |
| S | **India-specific instrument info** (lot sizes, expiry conventions) | India broker connection |
