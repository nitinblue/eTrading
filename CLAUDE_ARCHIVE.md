# CLAUDE_ARCHIVE.md
# Project: Trading CoTrader — Historical Reference
# Archived: February 16, 2026
#
# This file contains stable/historical content moved from CLAUDE.md to keep
# the active file lean. Claude can reference this when needed.
# CLAUDE.md remains the active working document loaded every session.

---

## BUSINESS OBJECTIVES — COMPLETED / PRIOR SESSIONS

### Feb 15, 2026 (Session 3)

| # | Objective | Signal (observable behavior) | Status |
|---|-----------|-------------------------------|--------|
| 1 | Register strategies per portfolio that Nitin actively trades (not all strategies at once). Underlyings come from watchlist. System knows which portfolio trades which strategies and screens only those. | Portfolio config has `active_strategies` (subset of `allowed_strategies`), screener filters by them | USER CAN NOW DO THIS |
| 2 | Enhanced entry criteria beyond VIX regime: relative VIX between 2 dates (for calendars/double calendars), basic technicals (MA crossover, RSI overbought/oversold), IV rank/percentile. Recommendations should be robust — acceptable to say "no recommendation right now". | Screener checks multiple criteria before recommending; many runs produce 0 recs because conditions aren't met | USER CAN NOW DO THIS |
| 3 | Macro short-circuit: before screening individual underlyings, check macro regime (market uncertainty, VIX spike, correlation spike, etc.). If macro says "stay away", skip all individual screening and return no recs. Provision to accept optional daily inputs: probability of market trend (bullish/bearish/neutral with confidence), expected volatility. If not provided, system proceeds BAU. | System can short-circuit entire screening run based on macro; user can optionally provide daily market view | USER CAN NOW DO THIS |
| 4 | Long-term investment entry criteria: for LEAPS and core holdings, be very picky about entry — only recommend after meaningful correction, at support levels, high IV rank for selling premium. Do not recommend LEAPS in a flat/overextended market. | LEAPS recommendations only appear after 10%+ correction AND near support AND IV rank > 40 | USER CAN NOW DO THIS |

### Feb 15, 2026 (Session 2)

| # | Objective | Signal (observable behavior) | Status |
|---|-----------|-------------------------------|--------|
| 1 | Now that we have what if trade booking feature, lets plug in screeners, based on which at the start of session or on demand, trade recommendation can be made (as a first class trade object), this is not based on portfolio or performance or risk. this is purely based on market regime, volatility, market conditions etc. Selection of Index, ETF and Stocks can be based on technicals, VIX, IV. I understand i need to define the universe of stocks. Thats the 2nd objective below | USER CAN NOW DO THIS |
| 2 | Create the universe of Stock on which screeners can be run. Lets try fetching watchlist from TastyTrade.. /public-watchlists/{watchlist_name} Returns a requested tastyworks watchlist (start with Tom's Watchlist) if required i will create my watchlist | USER CAN NOW DO THIS |
| 3 | recommendation of watchlist should not be added to whatif portfolio, because i want to make a conscious decision and add rational before accepting the recommendation at which point trade should be booked in what if portfolio, there is a likelihood i will send a real order for that. | USER CAN NOW DO THIS |
| 4 | To track performance every trade should be associated with where it originated from. I am also working on recommendation coming from astrology. So i may want to check performance of trades based on their sources.. please integrate a robust logic for this. | USER CAN NOW DO THIS |

### Feb 15, 2026 (Session 1)

| # | Objective | Signal (observable behavior) | Status |
|---|-----------|-------------------------------|--------|
| 1 | Deploy 250K in structured, risk-managed portfolio (50K personal + 200K IRA) | Capital allocated across defined risk buckets, not in cash | IN PROGRESS |
| 2 | Income generation is primary, not alpha chasing | Portfolio generates consistent premium income via options + dividends | NOT STARTED |
| 3 | Option book structured: 20% undefined risk / 80% defined risk | Every open position tagged to risk profile, limits enforced by system, not memory | IN PROGRESS |

### Feb 14, 2026

| # | Objective | Signal (observable behavior) | Status |
|---|-----------|-------------------------------|--------|
| 1 | Deploy 250K in structured, risk-managed portfolio (50K personal + 200K IRA) | Capital allocated across defined risk buckets, not in cash | NOT STARTED |
| 2 | Income generation is primary, not alpha chasing | Portfolio generates consistent premium income via options + dividends | NOT STARTED |
| 3 | Option book structured: 20% undefined risk / 80% defined risk | Every open position tagged to risk profile, limits enforced by system, not memory | NOT STARTED |
| 4 | Core long-term holdings accumulated via options (CSP → wheel strategy) | User never buys stock outright when options route is available | NOT STARTED |
| 5 | Every trade decision codified and logged before execution | No trade exists without recorded rationale linked to a strategy and objective | IN PROGRESS |
| 6 | System surfaces insights and recommendations — user approves, does not originate | User chooses from system-generated options, not thinking from scratch | NOT STARTED |
| 7 | Risk limits enforced at every level: trade, strategy, portfolio | System blocks or warns before limit breach, not after | IN PROGRESS |
| 8 | Event data feeds AI/ML layer for reinforcement learning | System measurably improves recommendations over time as trades accumulate | NOT STARTED |

---

## SESSION MANDATES — PRIOR

### Feb 15, 2026 (Session 4)
Objective:
1. Recommendation service should continuously evaluate portfolio and recommend trade roll, adjustments, book loss, take profit. User accepts or rejects (until we turn on auto-accept).
2. Close trades by booking opposite trade, book new adjusted trade. Roll linkage via rolled_from_id/rolled_to_id.
3. Check liquidity (bid-ask spread, open interest, volume) before adjustment/close decisions. Illiquid → close instead of adjust.
4. Going forward, check liquidity and volume before entering a trade. Configure thresholds in YAML.
Done looks like: User can run `python -m trading_cotrader.cli.evaluate_portfolio --portfolio high_risk --no-broker --dry-run` and see exit/roll/adjust recommendations for open trades.
Not touching today: UI

### Feb 15, 2026 (Session 1)
Objective:
1. my 250K is in 2 accounts but here we will have, but we will have concept of dividing this into multiple portfolios with different timehorizon and risk profile. Please create portfolio for a. high risk (choose a better name, generally short term options) - allocate 10K (this will be real allocation), b. medium risk, allocate 20K medium term trades... c. Core holdings, where long term stocks but sometimes i wheel the stocks, or do covered calls... d. will be completely hypothetical model portfolio, where i will do trades that i know will win, will capture the comments, i will also do trades i know will lose, will capture comments, and this should serve as training data for AI/ML
2. Develop Portfolio performance metrics, slice and dice by strategy type, by week, metrics to produce: equity curve, avg win, avg loss, win rate, expected value per trade
Done looks like: User can _______________ Strong feedback loop for AI/ML database to write models on how to keep optimizing daily profit based on the portfolio results...
Not touching today: UI

---

## ARCHITECTURE DECISIONS (1-13)

### Decision 1: Objects That Behave, Not Values That Display
- DECISION: Every entity (Portfolio, Trade, Position, WhatIf) is a domain object with state, behavior, and lifecycle. UI holds references (IDs), backend owns state and exposes methods.
- CONSTRAINT THAT FORCED IT: Need P&L attribution by Greek, not just a final number. Values can't carry that.
- REJECTED APPROACH: Value-only grid (TastyTrade/ThinkorSwim style) — rejected because it cannot support "why did I make/lose money" decomposition.
- OBJECTIVE IT SERVES: #5, #6, #7

### Decision 2: WhatIf = Trade (Same Object Model)
- DECISION: A WhatIf scenario is structurally identical to a real trade. Same domain object, same Greeks path, same P&L attribution. Differentiated only by `trade_type=WHAT_IF` and `portfolio_type=WHAT_IF`.
- CONSTRAINT THAT FORCED IT: If WhatIf is a separate object, it can never be promoted to a real trade without translation. Translation = bugs + drift.
- REJECTED APPROACH: Separate WhatIf object/table — rejected. One code path for both hypothetical and real.
- OBJECTIVE IT SERVES: #4, #5

### Decision 3: Refresh-First, Streaming-Ready Architecture
- DECISION: UI calls `GET /snapshot` on demand. Backend fetches fresh data from broker. Contract is identical whether data came from cache or live API. `RefreshBasedProvider` and `StreamingProvider` are swappable behind the same interface.
- CONSTRAINT THAT FORCED IT: TastyTrade DXLink streaming is complex to implement reliably in MVP. Refresh is practical; streaming is architectural.
- REJECTED APPROACH: Build streaming first — rejected, adds complexity before core object model is stable.
- OBJECTIVE IT SERVES: #7

### Decision 4: Trade Lifecycle is Explicit State Machine
- DECISION: `TradeStatus` follows: INTENT → EVALUATED → PENDING → EXECUTED → CLOSED/ROLLED. `is_open` is a computed property from status, not a stored field.
- CONSTRAINT THAT FORCED IT: Need to represent a trade that exists as a plan before it exists as a real position. INTENT and EVALUATED states are pre-execution.
- REJECTED APPROACH: Boolean `is_open` stored field — rejected because it goes stale and requires manual sync.
- OBJECTIVE IT SERVES: #5, #8

### Decision 5: Event Sourcing as the Foundation for AI/ML
- DECISION: Every trade action, decision, and market context snapshot is logged as an immutable event. Events are the training data for future RL. System is unusable for ML without this layer.
- CONSTRAINT THAT FORCED IT: RL needs (state, action, reward) triples. Without event sourcing, there is no way to reconstruct what the trader knew at the moment of decision.
- REJECTED APPROACH: Log only outcomes — rejected, loses the context that makes ML useful.
- OBJECTIVE IT SERVES: #8

### Decision 6: Single-Screen Institutional Cockpit (not a dashboard)
- DECISION: One screen. Top to bottom: Market Context → Risk Monitor (by underlying) → Scenario Matrix → Positions Grid (AG Grid, editable) → Hedging Blotter. No tabs for normal workflow.
- CONSTRAINT THAT FORCED IT: Trader mental model is top-down: macro → exposure → action. Tab-based UIs break that flow.
- REJECTED APPROACH: Dashboard with cards and widgets — rejected because it puts layout decisions on the user and fragments context.
- OBJECTIVE IT SERVES: #6, #7

### Decision 7: Risk Aggregated by Underlying, Not by Strategy
- DECISION: Primary risk view always aggregates Greeks by underlying (SPY delta: -150, QQQ delta: +80). Strategy grouping is secondary/optional.
- CONSTRAINT THAT FORCED IT: Hedging decisions are made at the underlying level. Knowing "my iron condor is -50 delta" is useless if you have 3 other SPY strategies running.
- REJECTED APPROACH: Strategy-centric view as primary — rejected. This is the core distinction between retail and institutional thinking.
- OBJECTIVE IT SERVES: #3, #7

### Decision 8: Broker = TastyTrade (Primary), Architecture = Multi-Broker Ready
- DECISION: TastyTrade as first broker. All broker interaction goes through `broker_adapter.py` abstract base class. No direct TastyTrade calls outside the adapter.
- CONSTRAINT THAT FORCED IT: Options-focused, good API, retail-friendly pricing. But lock-in is unacceptable for a product sold to others.
- REJECTED APPROACH: TastyTrade calls scattered throughout codebase — rejected.
- OBJECTIVE IT SERVES: Future monetization (Milestone 9)

### Decision 9: SQLite Now, PostgreSQL When Needed
- DECISION: Start with SQLite. No migration until either (a) multi-user or (b) performance is measurably a problem.
- CONSTRAINT THAT FORCED IT: Operational simplicity matters more than scale at this stage.
- REJECTED APPROACH: PostgreSQL from day one — rejected, adds DevOps overhead before the schema is stable.
- OBJECTIVE IT SERVES: All objectives (reduces friction in early development)

### Decision 10: Container Pattern for Runtime State (Feb 14, 2026)
- DECISION: `containers/` holds runtime state objects (PortfolioContainer, PositionContainer, TradeContainer, RiskFactorContainer) orchestrated by ContainerManager. These are in-memory state holders that sit between the DB/broker layer and the services layer.
- CONSTRAINT THAT FORCED IT: Services need rich, interconnected runtime state (positions + greeks + risk factors together). Passing raw DB rows around creates coupling and repeated hydration logic.
- OBJECTIVE IT SERVES: #7 (risk aggregation needs all state in one place)

### Decision 11: Test Harness Over pytest for Integration Testing (Feb 14, 2026)
- DECISION: `harness/` provides a step-based integration test framework (steps 01-17) with rich terminal output. pytest covers unit tests (55 tests in `tests/`).
- CONSTRAINT THAT FORCED IT: Integration testing across broker + DB + domain requires ordered steps with shared state. pytest fixtures don't naturally model this.
- OBJECTIVE IT SERVES: All objectives (validates the entire stack works end-to-end)

### Decision 12: Multi-Tier Portfolios from YAML Config (Feb 15, 2026)
- DECISION: Portfolios are defined in `config/risk_config.yaml` with capital allocations, allowed strategies, risk limits, and exit rule profiles. `PortfolioManager` creates them in DB using `broker='cotrader'` + `account_id=<config_name>` to reuse the existing unique constraint.
- CONSTRAINT THAT FORCED IT: User needs 4 risk tiers (Core/Med/High/Model) with different strategy permissions and capital allocations. Config must be easily adjustable without code changes.
- REJECTED APPROACH: Hardcoded portfolio definitions in code — rejected because allocation amounts and strategy permissions change.
- OBJECTIVE IT SERVES: #1, #3, #7, #8

### Decision 13: Exit Recommendations Mirror Entry Recommendations (Feb 15, 2026)
- DECISION: Exit/roll/adjust recommendations are the same `Recommendation` domain object as entry recommendations, differentiated by `recommendation_type` field (ENTRY, EXIT, ROLL, ADJUST). Accept/reject workflow is identical. Close = book opposite trade. Roll = close + open atomically with `rolled_from_id`/`rolled_to_id` linkage. Liquidity is checked before generating adjustment recommendations; if illiquid, downgrade ADJUST/ROLL → CLOSE.
- CONSTRAINT THAT FORCED IT: Existing recommendation lifecycle and CLI already work. Building a separate exit system would duplicate infrastructure.
- REJECTED APPROACH: Separate "exit signal" objects with auto-execution — rejected because user wants accept/reject control.
- OBJECTIVE IT SERVES: Session4-1 (continuous evaluation), Session4-2 (roll linkage), Session4-3 (liquidity gating)

---

## SESSION LOG (Sessions 1-10)

### Feb 15, 2026 (session 10)
- BUILT: `services/portfolio_evaluation_service.py` — evaluates open trades via RulesEngine, generates EXIT/ROLL/ADJUST recommendations with liquidity gating
- BUILT: `services/liquidity_service.py` — LiquiditySnapshot, threshold checks, mock mode
- BUILT: `cli/evaluate_portfolio.py` — CLI for portfolio evaluation
- BUILT: `harness/steps/step17_portfolio_evaluation.py` — 8 tests
- EXTENDED: recommendation model with RecommendationType enum + exit fields
- EXTENDED: recommendation_service with _accept_exit/_accept_roll
- EXTENDED: risk_config.yaml + loader with liquidity thresholds
- FIXED: position_mgmt/__init__.py import path
- VERIFIED: 55/55 pytest, 14/16 harness

### Feb 15, 2026 (session 9)
- FIXED: `is_open` bug in `repositories/trade.py` — 3 edits
- BUILT: 55-test pytest suite (7 files): pricing, Greeks, trade booking, is_open, filters, macro, portfolios
- VERIFIED: 55/55 pytest, 13/15 harness

### Feb 15, 2026 (session 8)
- BUILT: TechnicalAnalysisService, MacroContextService, LEAPS screener
- BUILT: Enhanced screener pipeline: macro gate → entry filters → active strategy filter → confidence modifier
- BUILT: harness step 16 (9 tests)
- EXTENDED: risk_config.yaml (active_strategies, entry_filters), screener framework
- VERIFIED: 13/15 harness

### Feb 15, 2026 (session 7)
- FIXED: SymbolORM IntegrityError cascade (savepoint pattern)
- FIXED: date vs datetime mismatch in symbol lookup
- CONVERTED: Trade templates YAML → JSON
- TESTED: Full recommendation pipeline
- VERIFIED: 12/14 harness

### Feb 15, 2026 (session 6)
- BUILT: Recommendation domain model, screener framework, VIX/IV rank screeners
- BUILT: WatchlistService, RecommendationService, CLI (run_screener, accept_recommendation)
- BUILT: TradeSource enum, source tracking, harness step 15
- VERIFIED: 11/14 harness

### Feb 15, 2026 (session 5)
- BUILT: 4-tier portfolio config in YAML, PortfolioManager, PerformanceMetricsService
- BUILT: harness step 14
- VERIFIED: step 14 passes

### Feb 14, 2026 (session 4)
- BUILT: harness step 13 — books 12 strategy templates as WhatIf trades

### Feb 14, 2026 (session 2)
- AUDITED: CLAUDE.md against actual codebase, fixed all discrepancies

### Feb 14, 2026 (session 1)
- SYNTHESIZED: All prior docs into CLAUDE.md, established ownership rules

---

## TECH STACK

| Layer | Choice | Status |
|-------|--------|--------|
| Backend | Python + FastAPI (`server/api_v2.py`) | Working |
| WebSocket | Custom (`server/websocket_server.py`) | Built |
| Database | SQLite (→ PostgreSQL later) | Working |
| Broker | TastyTrade via SDK (`adapters/tastytrade_adapter.py`) | Connected |
| Greeks/Pricing | Black-Scholes (custom, `analytics/` + `services/pricing/`) | Built |
| Frontend | HTML + JSX prototypes (`ui/`), NOT React | Prototypes |
| Event Sourcing | Custom (`core/models/events.py`) | Built |
| AI/ML | Q-Learning + DQN (numpy) | Needs data |
| Containers | Domain state management (`containers/`) | Built |
| Portfolio Mgmt | Multi-tier from YAML (`services/portfolio_manager.py`) | Built |
| Performance | OptionsKit metrics (`services/performance_metrics_service.py`) | Needs trade data |
| Screeners | VIX + IV rank + LEAPS (`services/screeners/`) | All 3 working |
| Technicals | EMA/RSI/ATR/regime/IV rank (`services/technical_analysis_service.py`) | Built |
| Macro Gate | VIX auto-assess + override (`services/macro_context_service.py`) | Built |
| Recommendations | First-class objects (`services/recommendation_service.py`) | Built |
| Source Tracking | TradeSource enum + breakdown metrics | Built |
| Portfolio Eval | Exit/roll/adjust + liquidity (`services/portfolio_evaluation_service.py`) | Built |
| Liquidity | Threshold checks (`services/liquidity_service.py`) | Built (mock OI/vol) |
| Unit Tests | pytest, 55 tests (`tests/`) | All pass |

---

## FILE STRUCTURE (snapshot as of session 10)

```
trading_cotrader/
├── adapters/
│   └── tastytrade_adapter.py        Auth, positions, balance
├── analytics/
│   ├── pricing/option_pricer.py     Black-Scholes
│   ├── pricing/pnl_calculator.py    P&L
│   ├── greeks/engine.py             Greeks calculations
│   ├── volatility_surface.py        IV surface
│   └── functional_portfolio.py      Functional portfolio analysis
├── cli/
│   ├── log_event.py                 CLI for logging trade decisions
│   ├── book_trade.py                CLI for booking WhatIf trades from JSON
│   ├── run_screener.py              CLI for running screeners against watchlists
│   ├── accept_recommendation.py     CLI for listing/accepting/rejecting recommendations
│   └── evaluate_portfolio.py        CLI for portfolio evaluation (exit/roll/adjust recs)
├── config/
│   ├── settings.py
│   ├── risk_config_loader.py        PortfolioConfig, LiquidityThresholds, EntryFilters
│   ├── risk_config.yaml             4 portfolio tiers, exit rules, liquidity thresholds
│   ├── trade_template.json          Trade booking template
│   ├── sample_past_trade.json       Past-dated trade with manual Greeks
│   └── daily_macro.yaml             Optional daily macro override
├── containers/                       Runtime state management
│   ├── container_manager.py
│   ├── portfolio_container.py
│   ├── position_container.py
│   ├── trade_container.py
│   └── risk_factor_container.py
├── core/
│   ├── database/schema.py           ORM (11 tables)
│   ├── database/session.py          session_scope()
│   ├── models/domain.py             PortfolioType, TradeStatus, TradeSource, Greeks, Symbol
│   ├── models/events.py             Event sourcing
│   ├── models/calculations.py
│   ├── models/strategy_templates.py  18 strategy templates
│   ├── models/recommendation.py     Recommendation + RecommendationType + Watchlist
│   └── validation/validators.py
├── harness/                          Integration test framework (17 steps)
│   ├── runner.py                    Main orchestrator
│   ├── base.py                      Step base classes
│   ├── run_containers.py
│   └── steps/                       step01 through step17
├── repositories/                     Data access layer
│   ├── base.py, portfolio.py, trade.py, position.py
│   ├── event.py, recommendation.py, watchlist.py
├── runners/
│   └── run_grid_server.py           WebSocket + REST server
├── scripts/
│   ├── setup_database.py
│   └── test_whatif_flow.py
├── server/
│   ├── api_v2.py                    FastAPI REST
│   ├── contracts.py                 API contracts
│   ├── data_provider.py             Data abstraction
│   └── websocket_server.py          WebSocket server
├── services/
│   ├── position_sync.py, portfolio_sync.py, greeks_service.py
│   ├── event_logger.py, event_analytics.py, data_service.py
│   ├── snapshot_service.py, option_grid_service.py
│   ├── trade_booking_service.py     WhatIf booking + portfolio routing
│   ├── portfolio_manager.py         Multi-tier init, strategy routing
│   ├── performance_metrics_service.py  Win rate, CAGR, Sharpe, drawdown
│   ├── watchlist_service.py         TastyTrade + custom watchlists
│   ├── recommendation_service.py    Screener orchestrator + accept exit/roll
│   ├── technical_analysis_service.py  EMA, RSI, ATR, IV rank, regime
│   ├── macro_context_service.py     Macro short-circuit
│   ├── portfolio_evaluation_service.py  Exit/roll/adjust + liquidity gating
│   ├── liquidity_service.py         Bid-ask, OI, volume checks
│   ├── screeners/                   VIX, IV rank, LEAPS screeners
│   ├── risk_manager.py, real_risk_check.py
│   ├── hedging/hedge_calculator.py
│   ├── market_data/, pricing/, risk/, risk_factors/
│   └── position_mgmt/rules_engine.py  Exit rules engine
├── ai_cotrader/                      ML/RL (needs data)
├── playground/                       Experimental scripts
├── tests/                            55 unit tests (pytest)
└── ui/                               HTML/JSX prototypes
```
