# CLAUDE.md
# Project: Trading CoTrader
# Last Updated: February 18, 2026 (session 24)
# Historical reference: CLAUDE_ARCHIVE.md (architecture decisions, session log, file structure, tech stack)

## STANDING INSTRUCTIONS
- **ALWAYS update CLAUDE.md** after major changes — update: code map, "what user can do", blockers, open questions.
- **ALWAYS update MEMORY.md** (`~/.claude/projects/.../memory/MEMORY.md`) with session summary.
- **Append new architecture decisions to CLAUDE_ARCHIVE.md**, not here.
- **Append session log entries to CLAUDE_ARCHIVE.md**, not here.
- If context is running low, prioritize writing updates BEFORE doing more work.

---

## [NITIN OWNS] WHY THIS EXISTS

20 years pricing and risk analytics on institutional trading floors — IR, commodities, FX, mortgages.
The gap: 1. Time flies by, Nitin did not even realized how much opportunity cost this has been. 2. Nitin does not believe in doing the same things over and over again, believes in building systems and automation. Level of automation Nitin expected was not possible till recently when  Agentic AI has arrived.. 3. Failing in managing own money has not been because of lack of knowledge but is more of a behaviour change that is required, and just because we build a robust trading platform with great UI will not change the behaviour. 4. institutional discipline has never been applied to personal wealth. 250K sits idle (50K personal, 200K self-directed IRA).
Agent based approach deploys capital systematically, safely, with full risk visibility at every level: trade, strategy, portfolio. Work that can be delegated to Agents should be done so. Nitin is a technologist enjoys building models, applications but cannot sit around and use it all day long.
Mental model: Macro Context → My Exposure → Action Required. Never "I have an iron condor." Always "I have -150 SPY delta, +$450 theta/day. Am I within limits?"

---

## [NITIN OWNS] BUSINESS OBJECTIVES — CURRENT
<!-- Add new entries at TOP with date. Move completed sessions to CLAUDE_ARCHIVE.md. -->
### Feb 17, 2026 
I am glad we have a agentic workflow that can keep running in loop. Now i strongly feel a need for a UI. Here are the objectives whey i need UI
1. To manage and configure all my portfolios, and configure virtual construct of portfolios, capital allocation 
2. To manage and all the configuration settings for risk limits etc. 
3. Manage my agent buddy, and get full, insights into my Agentic workflow
4. Behaviour aspects of my trading, as i said just because I have a UI does not mean i can get disciplined about trading. So how do i change my focus from forcing myself to look into doing trading myself, to managing and updating agent so that Agent actually keeps me invested, and discilplined and generates consistent returns. I want to be very ruthless about this. This is the only reason why i need tool, otherwise i can place orders with Broker directly and dont need to build this tool. I am not able to explain the depth of this aspect, hence you think hard, you reflect and tell me how do we make this agent a monster where it just does not lets up.. 
5. Agent has to keep becoming smarter and smarter, how do we ensure this
6. Every single screen functionality around trading actions, data has to be very well thought through, every single piece of data that can be dumped should be done, and thre should not be any need for me to go around debugging something. Think interms of Portfolio, positions, riskfactors, risk, pnl, strategies, portfolio performance, returns, captial usage, efficiency, margins, value at risk, black swan events, arbitrage opportunities, screeners, entry points, exit points, technical analysis, fundamental analysis, hedging, rolling, adjustments, profit taking, loss booking.. So may be start with Portfolio peformance as the top view then we drill down.
7. After tracking all these also if Agent is not making money, then honest investigation what is going wrong, what needs to change, how do we give result. Accountability matrix, go to green plan, retrospection, define how we will measure performance of the agent, and rate my agent every day.. 
8. Demonstration that we have rock solid reinforcement learning loop built in, full capablity to inspect AI/ML performance. 
9. Full access to raw data from various databases, event logs etc.. 
10. Thorough analysis of solid foundation for a great UI which is comprehensive, composable, has proper tech stack and not just javascript. Remember lot of rendering of trading data is actually objects which gets refreshed from containers. Every single trade should be an object, including recommendation trades. So create a portfolio for recomendation. Every trade has to be tacked with proper source, AI/ML should have full visiblity into performance of trades coming from any source. I dont want to see trades being represented in strings..

### Feb 16, 2026 (Session 6) — Continuous Trading Workflow Engine
Updating the objective set in Session 5 on Feb 16. I want to get started with building Agents who will be taking full responsiblility of prortfolo management, trading, growing the money. Nitin will be there to help take decisions. System is not expected to be big time on LLM,
but most definitely System needs to be smart enough to continously improve the payoff, and capable of reinforcement learning. Nitin is very new to creating Agents, Claude is responsible to propose the most simple, elegant solution to writting agents which is not suppose to have general intelligenece, but knows in and out of the system and understands the execution on a daily basis. I am happy with the AI/ML learning capabilities at this point. However in future Agents should be able to adapt to latest and greatest. Main objective is to develop a product, that acts as a cotrader, and does not expect end user to do repeat mundane work. I have always believed in codifying rules and decision anyway, so why should any one be required to get up every morning and look at charts and markets.

### Feb 16, 2026 (Session 5) — Continuous Trading Workflow Engine

**Context:** The system today is a collection of CLI tools you run on-demand. Each piece works (screeners, booking, evaluation, metrics) but nothing connects them into a continuous operating loop. You run a screener, copy a recommendation ID, run accept, copy a template, edit it, run book_trade. This is fragile, manual, and easy to skip. The harness validates integration but doesn't drive real trading decisions.

**What this is:** A continuously running workflow engine that operates your entire trading day — from macro check to trade execution to position management — with decision points where YOU approve/reject, and accountability tracking that ensures you stay invested and follow the system.

**How it differs from harness:** Harness runs once, tests, exits. Workflow runs continuously, maintains state, pauses for user decisions, sends notifications, tracks accountability, and drives real capital deployment.

| # | Objective | Signal (observable behavior) | Status |
|---|-----------|-------------------------------|--------|
| 1 | **Workflow state machine** — Continuous loop: BOOT → MACRO_CHECK → SCREENING → RECOMMENDATION_REVIEW → EXECUTION → MONITORING → TRADE_MANAGEMENT → TRADE_REVIEW → REPORTING. State persisted in DB. Can resume after restart. | `python -m trading_cotrader.runners.run_workflow --once --no-broker --mock` runs single cycle. State in DB/CLI. | DONE (s13) |
| 2 | **User decision points** — Workflow pauses at RECOMMENDATION_REVIEW and TRADE_REVIEW. Presents options (approve/reject/defer). Tracks time-to-decision via DecisionLogORM. | Workflow stops, notifies user, waits. Interactive CLI: approve/reject/defer/status/list/halt/resume/override. | DONE (s13) |
| 3 | **Notifications & approvals** — Console notifications always on. Email framework built (off by default). Recommendations, exits, halts, daily summaries. | NotifierAgent: console + email (SMTP/TLS). Enable in workflow_rules.yaml when ready. | DONE (s13) |
| 4 | **Capital deployment accountability** — Track deployed vs idle capital per portfolio. Days since last trade. Recs ignored. Time-to-decision. | AccountabilityAgent queries DecisionLogORM + TradeORM. Writes accountability_metrics to context. | DONE (s13) |
| 5 | **Trade plan compliance** — Every execution compared to template. Deviations flagged: wrong strikes, wrong DTE, wrong timing, wrong portfolio, skipped entry conditions. "Did you follow the playbook?" metric. Source comparison: system recs vs manual overrides, with performance tracking on both. | Monthly compliance report: "87% of trades followed template. Manual overrides underperformed system recs by 12%." | NOT STARTED |
| 6 | **Workflow scheduling** — Calendar-aware via exchange_calendars (NYSE holidays). FOMC dates in YAML. Cadences: 0DTE daily, weekly Wed/Fri, monthly by DTE window. APScheduler for continuous mode. | CalendarAgent + WorkflowScheduler. Morning boot 9:25, monitoring every 30 min, EOD 3:30, report 4:15 ET. | DONE (s13) |
| 7 | **WhatIf → Order conversion** — Pick WhatIf trade, dry-run preview with margin/fees, confirm to place LIMIT order on TastyTrade. Auto-fill detection. | CLI: `execute <trade_id>` (preview) → `execute <trade_id> --confirm` (place). Web: `POST /api/execute/{id}`. `orders` polls fill status. | DONE (s18) |
| 8 | **Daily/weekly reporting** — ReporterAgent generates structured reports: trades, P&L, portfolio snapshot, pending decisions, risk, calendar. | ReporterAgent → daily_report in context → NotifierAgent sends. Weekly digest framework built. | DONE (s13) |
| 9 | **Circuit breakers & trading halts** — GuardianAgent checks: daily loss (3%), weekly loss (5%), VIX>35, per-portfolio drawdown, consecutive losses. Override requires written rationale. All thresholds from YAML. | GuardianAgent tested: breakers trip correctly, override denied without rationale, granted with it. | DONE (s13) |
| 10 | **Rule-based trading constraints** — Max trades/day (3), max/week/portfolio (5), no first 15 min, no last 30 min, undefined risk approval, no adding to losers without rationale. All in workflow_rules.yaml. | GuardianAgent.check_trading_constraints() enforced before every execution. | DONE (s13) |

### Feb 15, 2026 (Session 4) — Portfolio Evaluation + Liquidity

| # | Objective | Status |
|---|-----------|--------|
| 1 | Recommendation service continuously evaluates portfolio → roll, adjust, book loss, take profit. User accepts/rejects. | USER CAN NOW DO THIS |
| 2 | Close trades by booking opposite trade. Roll linkage via `rolled_from_id`/`rolled_to_id`. | USER CAN NOW DO THIS |
| 3 | Check liquidity before adjustment/close. Illiquid → close instead of adjust. | USER CAN NOW DO THIS |
| 4 | Check liquidity before entering trades. Block entry if thresholds not met. | NOT STARTED (exit-side only) |
| 5 | Liquidity thresholds configured in YAML. | USER CAN NOW DO THIS |

### Standing objectives (from Feb 14-15)
- Deploy 250K across 4 risk-tiered portfolios (Core $200K, Medium $20K, High $10K, Model $25K) — **IN PROGRESS**
- Income generation primary, not alpha chasing — **NOT STARTED**
- 20% undefined / 80% defined risk book — **IN PROGRESS**
- Event data feeds AI/ML for RL — **IN PROGRESS** (research auto-book pipeline will generate 1000+ simulated trades/month, eliminating the wait for real data)

---

## [NITIN OWNS] SESSION MANDATE
<!-- Current session only. Move prior to CLAUDE_ARCHIVE.md. -->

### Feb 18, 2026 (Session 24)
Generic Research Template System — replace hardcoded screeners with config-driven templates.
- Created `config/research_templates.yaml`: 7 templates (4 migrated from scenario_templates + 3 new user-defined) (DONE)
- Created `services/research/condition_evaluator.py`: generic condition engine with 7 operators, reference comparisons, multipliers, AND/OR logic (DONE)
- Created `services/research/template_loader.py`: typed dataclass loader for research templates (DONE)
- Rewrote `agents/analysis/quant_research.py`: template-driven evaluation replacing screener-based flow (DONE)
- Added equity trade support: `instrument: equity` generates single-leg equity recommendations (DONE)
- Added `research_custom` portfolio for user-defined templates (DONE)
- Added `TradeSource.RESEARCH_TEMPLATE` enum value (DONE)
- Deprecated `config/scenario_templates.yaml` (migrated to research_templates.yaml) (DONE)
- Simplified `workflow_rules.yaml`: `research.templates_enabled: true` replaces per-screener config (DONE)
- Extended TechnicalSnapshot: `sma_50`, `volume`, `avg_volume_20` (DONE)
- 270/270 tests pass (89 new: 44 condition_evaluator + 46 research_templates + rewritten quant_research)

### Feb 18, 2026 (Session 23)
Auto-Book Research Pipeline + Parameter Variants (Phase 1 of Quant Agent Evolution).
- QuantResearchAgent built: runs all enabled scenario screeners, auto-accepts into research portfolios (DONE)
- 4 research portfolios in risk_config.yaml: research_correction, research_earnings, research_black_swan, research_arbitrage (DONE)
- Research config in workflow_rules.yaml: per-screener symbols, target_portfolio, parameter variants (DONE)
- Parameter variants: A/B testing (e.g. correction with short_delta=0.25/0.30/0.35) tagged with variant_id (DONE)
- Wired into workflow engine: runs every MONITORING cycle after regular screeners (DONE)
- New domain model additions: PortfolioType.RESEARCH, TradeSource.QUANT_RESEARCH + 4 scenario sources (DONE)
- Portfolio.create_research() factory method for virtual research portfolios (DONE)
- DB migration: setup_database.py migrate_schema() for incremental column/table additions (DONE)
- Agent registry updated: quant_research in AGENT_REGISTRY (DONE)
- 181/181 tests pass (24 new quant_research tests)

### Feb 18, 2026 (Session 22)
Scenario-Based Recommendation Templates + Market Data Container.
- 9 scenario templates in YAML (4 active, 5 future: orderblock, vol contraction, breakout, breakdown, consolidation) (DONE)
- ScenarioScreener base + 4 concrete screeners (correction, earnings, black_swan, arbitrage) (DONE)
- MarketDataContainer with change tracking, wired into ContainerManager (DONE)
- Bollinger Bands + VWAP + nearest resistance added to TechnicalAnalysisService (DONE)
- EarningsCalendarService via yfinance (DONE)
- Market data API endpoints at /api/v2/market-data (DONE)
- Scenario fields on Recommendation model + ORM (DONE)

### Feb 18, 2026 (Session 21)
Agent Dashboard & Visibility (Phase 1 of 4-phase Agent Management plan).
- Make all 16 agents visible: status, objectives, grades, run history (DONE)
- Persist every agent.run() call to DB with timing (DONE)
- Frontend agent dashboard with cards, timeline, detail pages (DONE)
- ML/RL status panel (DONE)
- Placeholder tabs for Quant Research + Knowledge Base (DONE)

---

## [NITIN OWNS] TODAY'S SURGICAL TASK
<!-- OVERWRITE each session. 5 lines max. -->

Session 24: Generic Research Template System (DONE).
- Replaced hardcoded screener classes with config-driven research_templates.yaml (7 templates)
- ConditionEvaluator: generic engine with 7 operators, reference comparisons, multipliers
- QuantResearchAgent rewritten: evaluates templates via ConditionEvaluator, not screener classes
- Equity trade support: single-leg equity recommendations alongside options
- 5 research portfolios (added research_custom for user-defined templates)
- scenario_templates.yaml deprecated → research_templates.yaml
- 270/270 tests pass (89 new).

---

## [CLAUDE OWNS] WHAT USER CAN DO TODAY

**Generic Research Template System (NEW — Session 24):**
- `config/research_templates.yaml`: 7 research templates — 4 migrated (correction, earnings, black_swan, arbitrage) + 3 user-defined (ma_crossover_rsi, bollinger_bounce, high_iv_iron_condor)
- **ConditionEvaluator** (`services/research/condition_evaluator.py`): generic engine with 7 operators (gt, gte, lt, lte, eq, between, in), reference comparisons (price > sma_20), multipliers (volume >= 1.5x avg_volume_20), AND/OR logic
- **ResearchTemplate loader** (`services/research/template_loader.py`): typed dataclass loading from YAML, parameter variants, trade strategy config
- **QuantResearchAgent rewritten**: evaluates templates via ConditionEvaluator instead of hardcoded screener classes
- **Equity trade support**: `instrument: equity` produces single-leg equity recommendations (long/short)
- **Option leg construction**: 7 strategy types — vertical_spread, strangle, iron_condor, iron_butterfly, single, calendar_spread, double_calendar
- 5 research portfolios: `research_correction`, `research_earnings`, `research_black_swan`, `research_arbitrage`, `research_custom` (for user-defined templates)
- Templates define: universe, entry_conditions (AND), exit_conditions (OR), trade_strategy, parameter variants, target_portfolio, cadence, auto_approve
- Indicators resolved from 3 sources: TechnicalSnapshot (price, RSI, Bollinger, etc.), global context (VIX, days_to_earnings), trade context (pnl_pct, days_held)
- `scenario_templates.yaml` deprecated — active templates migrated to `research_templates.yaml`
- `workflow_rules.yaml` simplified: `research.templates_enabled: true` replaces per-screener config
- TechnicalSnapshot extended: `sma_50`, `volume`, `avg_volume_20`
- 270 tests (89 new: 44 condition_evaluator + 46 research_templates)

**Auto-Book Research Pipeline (Session 23):**
- `QuantResearchAgent` runs every MONITORING cycle: evaluates all enabled research templates with parameter variants
- Auto-accepts ALL recommendations into research portfolios (no human gate) — generates ML training data
- New enum values: `PortfolioType.RESEARCH`, `TradeSource.QUANT_RESEARCH`, `TradeSource.RESEARCH_TEMPLATE`, `TradeSource.SCENARIO_CORRECTION/EARNINGS/BLACK_SWAN/ARBITRAGE`
- `Portfolio.create_research()` factory: virtual portfolios with zero capital
- DB migration: `setup_database.py` now runs `migrate_schema()` to detect and add missing tables/columns automatically
- Agent registry: `quant_research` visible in `/api/v2/agents` with category=analysis, runs_during=monitoring

**Scenario-Based Screeners + Market Data (Session 22):**
- 9 scenario templates in `config/scenario_templates.yaml` — 4 active (correction, earnings, black_swan, arbitrage), 5 future (orderblock, vol_contraction, breakout, breakdown, consolidation)
- `python -m trading_cotrader.cli.run_screener --screener correction --symbols SPY,QQQ --no-broker` — correction screener (triggers on 8-15% drop + VIX 22-45)
- `python -m trading_cotrader.cli.run_screener --screener earnings --symbols AAPL,NVDA --no-broker` — earnings IV crush screener (yfinance calendar)
- `python -m trading_cotrader.cli.run_screener --screener black_swan --symbols SPY --no-broker` — black swan hedge (VIX>30 + 12%+ drop)
- `python -m trading_cotrader.cli.run_screener --screener arbitrage --symbols SPY,QQQ --no-broker` — vol arbitrage calendar spreads (IV rank + Bollinger)
- Workflow engine runs `opportunistic` screeners (correction, arbitrage) and `event_driven` screeners (earnings, black_swan) every MONITORING cycle
- Each scenario recommendation carries `scenario_template_name`, `scenario_type`, `trigger_conditions_met` — full audit trail
- Dynamic leg construction from YAML-defined delta targets and wing widths
- `GET /api/v2/market-data` — all tracked underlyings with Bollinger/VWAP/MAs/RSI/regimes
- `GET /api/v2/market-data/{symbol}` — single underlying technical indicators
- `MarketDataContainer` persists indicators across workflow cycles (populated by MarketDataAgent)
- `TechnicalSnapshot` now includes: `bollinger_upper/middle/lower/width`, `vwap`, `nearest_resistance`
- `EarningsCalendarService` fetches earnings dates via yfinance with 24h cache
- Future templates (enabled=false) ready for implementation: orderblock, vol contraction, breakout, breakdown, consolidation

**Agent Dashboard & Visibility (NEW — Session 21):**
- Agent API: `GET /api/v2/agents` (16 agents with status, grade, run count, capabilities)
- Agent detail: `GET /api/v2/agents/{name}` (recent runs, objectives, stats)
- Paginated run history: `GET /api/v2/agents/{name}/runs?limit=50`
- Historical objectives: `GET /api/v2/agents/{name}/objectives?days=30`
- Dashboard stats: `GET /api/v2/agents/summary` (error count, avg duration, grade distribution)
- Cycle timeline: `GET /api/v2/agents/timeline?cycles=3` (Gantt-like view)
- ML status: `GET /api/v2/agents/ml-status` (snapshots, events, readiness)
- Engine context: `GET /api/v2/agents/context` (current state, truncated)
- Every `agent.run()` call persisted to `agent_runs` table with timing (fire-and-forget)
- Session objectives persisted per-agent per-day in `agent_objectives` table
- Static registry for all 16 agents: category, role, responsibilities, capabilities (implemented + planned)
- Frontend: `/agents` → 16 agent cards with status dots, grades, capability badges
- Frontend: `/agents/{name}` → detail page with grade history chart (Recharts), expandable run history, JSON viewer
- Frontend: 4 tabs — Active Agents (functional), Quant Research (placeholder), Knowledge Base (placeholder), ML/RL Status (functional)
- 2 new DB tables: `agent_runs`, `agent_objectives` (21 tables total)

**Live Order Execution (NEW — Session 18):**
- `execute <trade_id>` — dry-run preview of a WhatIf trade: legs, mid-price, margin impact, fees, Greeks
- `execute <trade_id> --confirm` — place the real LIMIT order on TastyTrade
- `orders` — poll live/recent order status, auto-update filled trades to EXECUTED
- Web API: `POST /api/execute/{id}` (with `{"confirm": false}` or `{"confirm": true}`), `GET /api/orders`
- Config: `execution_defaults` in `workflow_rules.yaml` — order_type, time_in_force, price_strategy, allowed_brokers
- Price calculated as bid-ask midpoint from live quotes via DXLink
- 2-step confirmation: preview stores state in `engine.context['pending_execution']`, confirm reads it
- All TastyTrade SDK order imports confined to `adapters/tastytrade_adapter.py`
- Adapter ABC: `place_order()`, `get_order()`, `get_live_orders()` — ManualBrokerAdapter/ReadOnlyAdapter raise NotImplementedError

**Web Approval Dashboard (Session 17):**
- `python -m trading_cotrader.runners.run_workflow --web --port 8080` — starts dashboard embedded in workflow engine
- Dashboard at `http://localhost:8080` — dark theme, auto-refresh every 15s, approve/reject/defer from browser
- Both CLI and web work simultaneously (same process, same `handle_user_intent()` code path)
- Endpoints: `/api/pending`, `/api/status`, `/api/approve/{id}`, `/api/reject/{id}`, `/api/defer/{id}`, `/api/history`, `/api/halt`, `/api/resume`, `/api/portfolios`
- Approve modal: portfolio dropdown + notes field. Reject modal: reason field.
- Remote access: expose port via ngrok, Tailscale, or Cloudflare Tunnel (Chicago + Hyderabad)
- `server/` folder deleted — was decoupled from workflow engine and unused
- `run_grid_server.py` shows deprecation notice pointing to `--web` flag

**Broker Adapter Abstraction + Per-Portfolio Containers (Session 16):**
- All `tastytrade` SDK imports confined to `adapters/tastytrade_adapter.py` — zero leakage to services/screeners/server
- `BrokerAdapterBase` ABC in `adapters/base.py`: `authenticate()`, `get_positions()`, `get_quote()`, `get_quotes()`, `get_greeks()`, `get_option_chain()`, `get_public_watchlists()`
- `ManualBrokerAdapter` (Fidelity) and `ReadOnlyAdapter` (Stallion) stub adapters
- `BrokerAdapterFactory.create(broker_config)` — creates correct adapter from YAML config
- `BrokerAdapterFactory.create_all_api(registry)` — batch-creates API-capable adapters
- Per-portfolio `PortfolioBundle` containers: each real portfolio gets its own `PositionContainer`, `TradeContainer`, `RiskFactorContainer`
- WhatIf portfolios share parent's bundle (positions visible from both)
- `ContainerManager` rewritten: `Dict[str, PortfolioBundle]`, currency-filtered access, backward-compat properties
- `QAAgent` runs daily in REPORTING state: pytest + coverage analysis, gap identification, test suggestions, persists to decision_log
- Services cleaned up: `data_service.py`, `option_grid_service.py`, `macro_context_service.py`, `liquidity_service.py`, `trade_booking_service.py`, `vix_regime_screener.py`, `watchlist_service.py` — all use adapter interface

**Multi-Broker Portfolios (Session 15):**
- 10 portfolios: 5 real (Tastytrade, Fidelity IRA, Fidelity Personal, Zerodha, Stallion) + 5 WhatIf mirrors
- 3-layer broker design: Broker Registry (`config/brokers.yaml`) → Portfolio Config (`risk_config.yaml`) → Execution Routing (`agents/execution/broker_router.py`)
- Multi-currency: USD (Tastytrade, Fidelity) and INR (Zerodha, Stallion)
- Execution routing: API brokers (Tastytrade, Zerodha), manual execution (Fidelity), read-only managed fund (Stallion)
- Cross-broker safety: Fidelity trade NEVER routes to Tastytrade API; currency isolation enforced
- Stallion: fully managed fund — 29 holdings loaded from PDF, read-only (no trade execution)
- Fidelity CSV sync: `python -m trading_cotrader.cli.sync_fidelity --file Portfolio_Positions.csv`
- Portfolio init: `python -m trading_cotrader.cli.init_portfolios` (creates 10, tags old `cotrader/*` as deprecated)
- Stallion load: `python -m trading_cotrader.cli.load_stallion` (29 equity holdings + cash)
- WhatIf portfolios inherit strategies from real parent automatically

**Capital Utilization & Agent Self-Assessment (Session 14):**
- CapitalUtilizationAgent runs every boot + monitoring cycle: per-portfolio idle capital, gap %, opportunity cost/day
- Staggered deployment ramp: doesn't nag to deploy $200K on day 1 (8-week ramp, per-portfolio weekly caps in YAML)
- Severity escalation: ok → info → warning → critical (based on gap vs threshold and days idle)
- Correlates with pending recommendations: "You have $3K idle AND 1 pending rec — approve it?"
- SessionObjectivesAgent: agents declare objectives at morning boot, graded at EOD (A/B/C/F)
- EOD corrective plan: gaps identified with concrete actions for tomorrow
- Reporter now includes CAPITAL EFFICIENCY + SESSION PERFORMANCE + CORRECTIVE PLAN sections
- Notifier: idle capital alerts with severity formatting
- All thresholds in `config/workflow_rules.yaml` (escalation, target returns, staggered deployment)

**Workflow Engine (Session 13):**
- Single cycle: `python -m trading_cotrader.runners.run_workflow --once --no-broker --mock`
- Continuous mode: `python -m trading_cotrader.runners.run_workflow --paper --no-broker`
- Interactive CLI: `status`, `list`, `approve <id>`, `reject <id>`, `defer <id>`, `halt`, `resume --rationale "..."`, `override`, `help`
- Full state machine: IDLE → BOOT → MACRO_CHECK → SCREENING → RECOMMENDATION_REVIEW → EXECUTION → MONITORING → TRADE_MANAGEMENT → TRADE_REVIEW → REPORTING
- Exit evaluation covers: take profit, stop loss, DTE exits, delta breach, roll opportunities, adjustments, liquidity downgrade
- Guardian agent: circuit breakers (daily loss 3%, weekly 5%, VIX>35, drawdown, consecutive losses) + trading constraints (max trades/day, time-of-day, undefined risk approval)
- All rules in `config/workflow_rules.yaml` — no hardcoded thresholds
- Calendar-aware: NYSE holidays via exchange_calendars, FOMC dates in YAML
- APScheduler: morning boot, monitoring every 30 min, EOD 3:30 PM, report 4:15 PM ET
- State persisted in DB (`workflow_state` table), resumes after restart
- Decision logging (`decision_log` table): tracks time-to-decision, ignored recs, deferrals
- Accountability: capital deployment %, days since last trade, recs ignored
- Notifications: console always, email framework (off by default)
- Paper mode default — all trades booked as WhatIf

**Trade Booking:**
- Book WhatIf trades from JSON: `python -m trading_cotrader.cli.book_trade --file trade.json [--no-broker]`
- Book past-dated trades, trades with manual Greeks, any of 12 strategy types
- Route trades to specific portfolios with strategy validation

**Screeners & Recommendations:**
- Run screeners: `python -m trading_cotrader.cli.run_screener --screener vix|iv_rank|leaps|all --symbols SPY,QQQ --no-broker`
- Macro short-circuit: `--macro-outlook uncertain --expected-vol extreme` (blocks all recs)
- List/accept/reject recommendations: `python -m trading_cotrader.cli.accept_recommendation --list|--accept <ID>|--reject <ID>`
- Active strategies per portfolio filter screener output
- Entry filters per strategy (RSI, regime, ATR%, IV percentile) in `risk_config.yaml`

**Portfolio Evaluation (exit/roll/adjust):**
- Evaluate open trades: `python -m trading_cotrader.cli.evaluate_portfolio --portfolio high_risk --no-broker --dry-run`
- Evaluate all: `python -m trading_cotrader.cli.evaluate_portfolio --all --no-broker`
- Accept EXIT rec (closes trade), ROLL rec (closes + books new with linkage)
- Illiquidity downgrade: ADJUST/ROLL → CLOSE when options illiquid
- Liquidity thresholds configurable in `risk_config.yaml`

**Portfolio & Risk:**
- 10 multi-broker portfolios (5 real + 5 whatif) from YAML, strategy permissions matrix
- Performance metrics per portfolio (win rate, Sharpe, drawdown, expectancy)
- Source tracking on every trade (screener, manual, astrology, etc.)

**Risk Analysis (VaR):**
- Real parametric VaR (delta-normal) using yfinance historical returns + covariance
- Historical VaR using actual past return distributions (captures fat tails)
- Incremental VaR: calculate portfolio VaR → add WhatIf trade → compare incremental impact
- Expected Shortfall (CVaR) at all confidence levels
- Per-underlying VaR contribution breakdown (standalone, component, marginal VaR)
- Correlation matrix from real yfinance data (1-day cache, fallback to estimates if offline)

**Testing:**
- Harness: `python -m trading_cotrader.harness.runner --skip-sync` — 14/16 pass (2 skip without broker), 17 steps
- Unit tests: `pytest trading_cotrader/tests/ -v` — 181 tests, all pass

**React Frontend (Session 19 — Phase 1):**
- `frontend/` — Vite + React 18 + TypeScript + Tailwind CSS + AG Grid + TanStack Query
- Portfolio page: all 10 portfolios in AG Grid, Greeks bars, P&L coloring, deployed %, VaR
- Position drill-down: click portfolio → see open trades with legs, Greeks, DTE, source
- Trade detail modal: legs table, P&L attribution (delta/gamma/theta/vega/unexplained), Greeks entry→current, timeline
- WhatIf trades visually distinct (blue tint, WHATIF badge)
- Status bar: market hours, workflow state, WS connection, pending recs count
- Top bar: workflow state badge, VIX with color coding, macro regime
- Dev: `cd frontend && pnpm dev` (Vite at :5173, proxies to :8080)
- Prod: `cd frontend && pnpm build` → backend serves `frontend/dist/` at `/`
- v2 API: `GET /api/v2/portfolios`, `/positions`, `/trades`, `/workflow/status`, `/recommendations`, `/risk`, `/capital`, `/decisions`, `/performance`

**Admin & Config Screens (Session 20):**
- Admin API: `GET/PUT /api/admin/portfolios`, `/risk`, `/strategies`, `/workflow`, `/capital-plan`, `POST /reload`
- YAML remains source of truth — API reads/writes YAML + reloads singletons
- 4 settings pages: Portfolios (left-right master-detail), Risk (VaR/Greeks/concentration/margin/exit profiles/liquidity), Workflow (circuit breakers/constraints/schedule/execution/strategy rules), Capital (live status/idle alerts/escalation/target returns/staggered ramp)
- Sidebar: Config nav with expandable sub-items (Portfolios, Risk, Workflow, Capital)
- Common components: SaveBar (sticky save/cancel), FormSection (collapsible), Toast (success/error)
- Portfolio edit: strategies checkboxes (allowed + active), risk limits, preferred underlyings (tag input), exit profile dropdown
- Strategy rules: expandable inline edit in table rows with entry filters
- `curl http://localhost:8080/api/admin/portfolios` returns YAML config as JSON

**Reports & Data Explorer (Session 20 continued):**
- Reports API: `GET /api/reports/trade-journal`, `/performance`, `/strategy-breakdown`, `/source-attribution`, `/weekly-pnl`, `/decisions`, `/recommendations`, `/trade-events`, `/daily-snapshots`, `/greeks-history`
- Reports use `PerformanceMetricsService` for portfolio/strategy/source metrics (win rate, Sharpe, drawdown, expectancy, profit factor, CAGR)
- All report endpoints support filters (portfolio, status, date range, source, strategy) + pagination (limit/offset)
- Explorer API: `GET /api/explorer/tables` (19 tables with metadata + row counts), `GET /api/explorer/tables/{name}` (metadata + 5 samples), `POST /api/explorer/query` (structured queries), `POST /api/explorer/query/csv` (CSV export)
- Explorer uses table/column whitelist from ORM introspection — NO raw SQL, max 1000 rows per query
- 10 operators: eq, neq, gt, gte, lt, lte, contains, starts_with, in, between — validated against column type
- Reports page: 8 tabbed views (Trade Journal, Performance, Strategy, Source, Decisions, Weekly P&L, Recommendations, Events) with AG Grid + CSV export
- Data Explorer page: left panel table list + right panel query builder (filter rows, sort, limit) + AG Grid results with dynamic columns

**Broker & Server:**
- Authenticate TastyTrade, sync portfolio, pull live Greeks
- Web approval dashboard: `python -m trading_cotrader.runners.run_workflow --web --port 8080`
- Old grid server removed (`server/` folder deleted, `run_grid_server.py` shows deprecation notice)

**Snapshot & AI/ML Pipeline (Session 16 continued):**
- SnapshotService wired into workflow engine — captures daily snapshots for ALL active portfolios
- ML pipeline wired: `MLDataPipeline.accumulate_training_data()` runs after every snapshot capture
- 20 new snapshot + ML tests (157 total)
- AI/ML assessment: `AI_ML_ASSESSMENT.md` — comprehensive evaluation of current ML capability
- Data is now flowing; need 100+ closed trades for supervised learning, 500+ for RL

**Blocked / Not Yet Working:**
- **RESEARCH PIPELINE (Layers 1-1.5 DONE, Layers 2-3 pending)** — QuantResearchAgent auto-books via generic research templates (s23-24). Still needed: QuantLifecycleAgent for daily MTM + auto-exit (s25), ML feature pipeline + first models (s26).
- AI/ML model training not wired (need data first — being addressed by auto-book pipeline)
- AI/ML recommendations not integrated into workflow (need trained models)
- Live order execution for non-TastyTrade brokers (Fidelity/Zerodha/Stallion)
- Trade plan compliance tracking (template comparison, deviation flagging)
- Email notifications (framework built, SMTP not configured)
- Liquidity check on entry screeners not yet wired (exit-side only)
- OI + daily volume from broker not integrated (mock placeholders)
- IV rank uses realized vol proxy — needs broker IV
- Performance metrics return zeros (no closed trades yet — research portfolios will fix this)
- Volatility curve / term structure analysis for calendar/double calendar strike selection
- Equity curve, drawdown chart, benchmark vs SPY/QQQ
- Enable future scenario templates: orderblock, vol_contraction, breakout, breakdown, consolidation (need additional trigger conditions: support/resistance detection, volume ratio, Bollinger width max)
- **Quant Agent at Level 0** — generates data but doesn't learn. Needs: parameter optimization (s25), hypothesis generation (s27), template health monitoring (s26), knowledge base (s27). See 5-level evolution plan below.
- Agent Learning Framework (Phase 2) — structured learnings, knowledge base (planned s27)
- Trade Reasoning + RL Feedback (Phase 4) — structured reasoning chains, RL loop (planned s28+)
- Frontend screens not yet built: Dashboard, Recommendations, Workflow, Risk, Performance, Capital, Trading
- **Real capital deployment on hold** — Nitin postponing investment until research portfolios demonstrate agent readiness

---

## [CLAUDE OWNS] NEXT MAJOR INITIATIVE: Autonomous Research → ML Training Data

### The Problem
ML pipeline needs 100+ closed trades for supervised learning, 500+ for RL. Real trading generates maybe 2-5 trades/week. At that rate, useful ML is 6-12 months away. Meanwhile the Quant agent sits idle.

### The Insight (Nitin, Session 22)
**Don't wait for real data. Generate it.** Every scenario template defines a complete trade hypothesis. The system should:
1. Run ALL scenario screeners every cycle (not just on user's cadence)
2. AUTO-ACCEPT every recommendation into dedicated research WhatIf portfolios
3. Track these trades daily — mark-to-market, evaluate exits, close at rules
4. Feed every lifecycle event to ML pipeline
5. In weeks, not months, have thousands of simulated trade outcomes

### Architecture: 3-Layer Research Engine

**Layer 1: Aggressive Auto-Book (QuantResearchAgent)**
```
Every MONITORING cycle:
  → Run ALL 9 scenario screeners against expanded watchlist (50+ symbols)
  → Auto-accept ALL recommendations into research portfolios (no human gate)
  → One research portfolio PER scenario type (correction_research, earnings_research, etc.)
  → Tag every trade: source=quant_research, scenario_type, trigger_conditions
  → No capital limits on research portfolios (virtual — tracking P&L only)
```

**Layer 2: Daily Lifecycle Management (QuantLifecycleAgent)**
```
Every MONITORING cycle:
  → Run PortfolioEvaluationService on ALL research portfolios
  → Auto-accept EXIT/ROLL recommendations (no human gate)
  → Mark-to-market via TechnicalAnalysisService (price from yfinance)
  → Track: entry price, current price, max favorable, max adverse, days held
  → Compute theoretical Greeks from Black-Scholes (already have analytics/pricing/)
  → Close trades at template-defined exit rules (profit target, stop loss, DTE)
```

**Layer 3: ML Feature Extraction + Model Training**
```
After every trade close:
  → Extract features: scenario_type, trigger_conditions, entry_iv_rank, entry_rsi,
    days_held, max_favorable_pct, max_adverse_pct, pnl_pct, vix_at_entry, vix_at_exit,
    regime_at_entry, regime_at_exit, bollinger_position, earnings_proximity
  → Write to ml_training_data table (already have ai_cotrader/data_pipeline.py)
  → Weekly: retrain simple models (logistic regression on win/loss, random forest on P&L)
  → Monthly: evaluate model predictions vs actual outcomes
  → Continuously: adjust scenario trigger thresholds based on what works

Model outputs feed back into:
  → Confidence scoring: ML-adjusted confidence on new recommendations
  → Template tuning: "correction screener with RSI<35 wins 72% vs 54% for RSI<40"
  → Portfolio allocation: "earnings scenarios have 0.8 Sharpe, allocate more capital"
```

### Research Portfolios (new, virtual, no capital)
| Portfolio | Scenario | Watchlist |
|-----------|----------|-----------|
| `research_correction` | correction_premium_sell | SPY,QQQ,AAPL,NVDA,MSFT,AMZN,GOOGL,META,TSLA,AMD |
| `research_earnings` | earnings_iv_crush | Dynamic (earnings calendar) |
| `research_black_swan` | black_swan_hedge | SPY,QQQ,IWM |
| `research_arbitrage` | vol_arbitrage_calendar | SPY,QQQ,SPX,IWM |
| `research_orderblock` | orderblock (future) | Top 20 liquid names |
| `research_breakout` | breakout (future) | Top 20 liquid names |
| `research_consolidation` | consolidation (future) | SPY,QQQ,IWM |

### Quant Agent Evolution — 5 Levels (Honest Assessment)

**Current state: Level 0 — Data Generator.** The system generates data but doesn't truly learn. Six specific weaknesses identified:

| # | Weakness | What's Missing |
|---|----------|---------------|
| 1 | No hypothesis generation | Templates are human-authored. System never asks "what if RSI<30 works better than RSI<40?" |
| 2 | No parameter optimization | Fixed YAML params. Never tests delta=0.25 vs 0.30, never adjusts thresholds based on outcomes |
| 3 | No backtesting framework | Can't test "would this template have worked in 2022 bear market?" |
| 4 | No structured knowledge accumulation | Insights from session objectives vanish. No persistent "what we learned" repository |
| 5 | No causal reasoning | Correlates outcomes with features but can't explain WHY a trade worked |
| 6 | Open feedback loop | ML scores don't flow back to template selection or parameter adjustment |

**Target evolution:**

| Level | Name | What It Does | Session |
|-------|------|-------------|---------|
| 0 | Data Generator | Books WhatIf trades, tracks outcomes | s23-24 |
| 1 | Template Executor | Runs templates as-is, measures win rate per template | s23-24 |
| 2 | Parameter Optimizer | Tests parameter variants (delta, DTE, wing width), identifies best combos | s25 |
| 3 | Hypothesis Generator | Proposes new trigger conditions, creates experimental templates | s27 |
| 4 | Adaptive Strategy Manager | Adjusts portfolio allocation based on regime-conditional performance | s28 |
| 5 | LLM-Augmented Reasoning | Uses language model to explain trade outcomes, synthesize insights | Future |

**Nitin's strategic decision (Session 22):** Real capital deployment postponed until agents demonstrate consistent research portfolio performance. "I will not get into market fully — postponing investment plan before my agents are ready."

### Implementation Plan (Sessions 23-27+)

**Session 23: Auto-Book Pipeline + Parameter Variants**
- Create research portfolio configs in risk_config.yaml (portfolio_type=research, no capital limits)
- Build `QuantResearchAgent` — runs all enabled scenario screeners, auto-accepts into research portfolios
- Wire into workflow engine: runs every MONITORING cycle after regular screeners
- **Parameter variants**: For each template, book 2-3 variants (e.g. correction with short_delta=0.25/0.30/0.35) — tagged with `variant_id` for A/B comparison
- CLI: `python -m trading_cotrader.cli.run_research --once --no-broker` for manual trigger
- Verify: 1 cycle generates 10-50 WhatIf trades across research portfolios

**Session 24: Research Lifecycle + MTM**
- Build `QuantLifecycleAgent` — evaluates research portfolios, auto-closes at exit rules
- Daily MTM: use yfinance close prices to mark research positions
- Track: entry_price, current_price, max_favorable, max_adverse, theoretical_greeks
- Compute P&L attribution (delta, theta, vega, gamma, unexplained) using existing analytics
- Verify: trades open, get marked daily, close at profit/stop/DTE rules

**Session 25: ML Feature Pipeline + First Models + Feature Importance**
- Extend `MLDataPipeline` to extract features from closed research trades
- Feature set: 20+ features per trade (scenario, trigger conditions, market state, outcome)
- Train first models: logistic regression (win/loss), random forest (P&L prediction)
- **Feature importance analysis**: Which trigger conditions matter most? Which are noise?
- Model evaluation: accuracy, precision, recall, Sharpe of model-filtered trades
- Persist model artifacts + evaluation metrics to DB
- API: `GET /api/v2/agents/ml-models` (model list, performance, feature importance)

**Session 26: Feedback Loop + Template Health Monitor + Quant Dashboard**
- ML-adjusted confidence: new recommendations get model prediction overlay
- **Template health monitor**: Per-template scorecard — win rate, avg P&L, max drawdown, Sharpe, sample size. Auto-disable templates that underperform after N trades (configurable threshold)
- Template tuning: QuantAgent suggests parameter changes based on research outcomes
- Frontend: Research tab showing all research portfolios, trade outcomes, model performance
- Equity curves per scenario type, win rates, average P&L, Sharpe ratios
- A/B comparison: "correction with RSI<35 vs RSI<40" side-by-side

**Session 27: Hypothesis Engine (Level 3)**
- **Clustering analysis**: Group closed trades by outcome, find what separates winners from losers
- **Autonomous template proposal**: "Trades with RSI<30 AND VIX>25 AND bollinger_width>0.05 won 78% — create new template?"
- **Experiment framework**: QuantAgent creates experimental templates, runs them in dedicated research portfolio, evaluates after N trades
- **Knowledge Base agent**: Persists structured learnings — "SPY correction trades work best with 45 DTE, not 30" — queryable by other agents
- Human-in-loop: experimental templates require approval before graduating to active

**Session 28+: Adaptive Strategy + LLM Integration (Future)**
- Regime-conditional allocation: "In HIGH vol, weight corrections 3x, reduce calendars"
- Cross-scenario correlation: "Don't run both correction and black_swan — they overlap"
- LLM integration: Use Claude API to explain trade outcomes in natural language
- Autonomous TRADING_PLAYBOOK.md updates based on accumulated evidence

### Key Design Decisions
1. Research portfolios are **virtual** — no real capital, no broker interaction, yfinance-only pricing
2. Research trades use **same domain model** as real trades (Trade, Leg, etc.) — ML features identical
3. Auto-accept bypasses InteractionManager — QuantAgent writes directly to DB
4. Exit rules come from **exit_rule_profiles** in risk_config.yaml (same as real portfolios)
5. Research data feeds the SAME MLDataPipeline that real trades will eventually feed
6. When ML models prove reliable on research data, they graduate to scoring real recommendations

---

## [CLAUDE OWNS] CURRENT BLOCKER

**No active blockers.**

---

## [CLAUDE OWNS] CODE MAP
<!-- Maps objectives to code. Update when new features are built. -->

| Area | Key files |
|------|-----------|
| **Workflow Engine** | `workflow/engine.py` (orchestrator), `workflow/states.py` (state machine), `workflow/scheduler.py` (APScheduler), `runners/run_workflow.py` (CLI) |
| **Agents** | `agents/protocol.py` (Agent/AgentResult), `agents/messages.py` (UserIntent/SystemResponse) |
| **Safety** | `agents/safety/guardian.py` (circuit breakers + trading constraints), `config/workflow_rules.yaml` (all thresholds) |
| **Perception** | `agents/perception/market_data.py`, `agents/perception/portfolio_state.py`, `agents/perception/calendar.py` |
| **Analysis** | `agents/analysis/macro.py`, `agents/analysis/screener.py`, `agents/analysis/evaluator.py`, `agents/analysis/risk.py`, `agents/analysis/capital.py` (idle capital monitoring), `agents/analysis/quant_research.py` (auto-book research pipeline) |
| **Execution** | `agents/execution/executor.py`, `agents/execution/broker_router.py` (per-broker routing), `agents/execution/notifier.py`, `agents/execution/reporter.py` |
| **Decision** | `agents/decision/interaction.py` (InteractionManager — routes user commands) |
| **Learning** | `agents/learning/accountability.py` (decision tracking), `agents/learning/session_objectives.py` (agent self-assessment), `agents/learning/qa_agent.py` (daily QA assessment) |
| **Workflow Config** | `config/workflow_rules.yaml` (incl. `execution_defaults`), `config/workflow_config_loader.py` (`ExecutionConfig`) |
| **Broker Adapters** | `adapters/base.py` (BrokerAdapterBase ABC, ManualBrokerAdapter, ReadOnlyAdapter), `adapters/factory.py` (BrokerAdapterFactory), `adapters/tastytrade_adapter.py` (TastyTrade SDK — all `tastytrade` imports confined here) |
| **Broker Config** | `config/brokers.yaml` (4 brokers), `config/broker_config_loader.py` (BrokerRegistry) |
| **Containers** | `containers/portfolio_bundle.py` (per-portfolio bundle), `containers/container_manager.py` (Dict[str, PortfolioBundle]), `containers/market_data_container.py` (cross-portfolio technical indicators), `containers/portfolio_container.py`, `containers/position_container.py` |
| **Portfolios** | `config/risk_config.yaml` (10 portfolios), `config/risk_config_loader.py`, `services/portfolio_manager.py` |
| **Trade Booking** | `services/trade_booking_service.py`, `cli/book_trade.py`, `core/models/domain.py` (TradeStatus, TradeSource) |
| **Screeners** | `services/screeners/` (vix, iv_rank, leaps, correction, earnings, black_swan, arbitrage), `services/screeners/scenario_screener.py` (base), `services/recommendation_service.py`, `services/technical_analysis_service.py` |
| **Research Templates** | `config/research_templates.yaml` (7 templates), `services/research/template_loader.py` (ResearchTemplate/ParameterVariant), `services/research/condition_evaluator.py` (Condition/ConditionEvaluator) |
| **Scenario Templates** | `config/scenario_templates.yaml` (DEPRECATED — migrated to research_templates.yaml) |
| **Earnings Calendar** | `services/earnings_calendar_service.py` (yfinance, 24h cache) |
| **Macro Gate** | `services/macro_context_service.py`, `config/daily_macro.yaml` |
| **Portfolio Eval** | `services/portfolio_evaluation_service.py`, `services/position_mgmt/rules_engine.py`, `services/liquidity_service.py` |
| **Recommendations** | `core/models/recommendation.py` (RecommendationType), `repositories/recommendation.py`, `cli/accept_recommendation.py`, `cli/evaluate_portfolio.py` |
| **Risk/VaR** | `services/risk/var_calculator.py`, `services/risk/correlation.py`, `services/risk/` (concentration, margin, limits) |
| **Performance** | `services/performance_metrics_service.py` (win rate, CAGR, Sharpe, drawdown, source breakdown) |
| **Events/ML** | `services/event_logger.py`, `core/models/events.py`, `ai_cotrader/` (feature extraction, RL — needs data) |
| **Pricing** | `analytics/pricing/` (BS, P&L), `analytics/greeks/engine.py`, `services/pricing/` |
| **DB/ORM** | `core/database/schema.py` (21 tables incl. workflow_state, decision_log, agent_runs, agent_objectives), `core/database/session.py`, `repositories/` |
| **Broker** | `adapters/tastytrade_adapter.py`, `services/position_sync.py`, `services/portfolio_sync.py`, `cli/init_portfolios.py`, `cli/sync_fidelity.py`, `cli/load_stallion.py` |
| **Web Dashboard** | `web/approval_api.py` (FastAPI app factory, embedded in workflow engine), `ui/approval-dashboard.html` (legacy dark theme) |
| **v2 API** | `web/api_v2.py` (comprehensive REST API for React frontend, mounted at `/api/v2`) |
| **Admin API** | `web/api_admin.py` (YAML config CRUD, mounted at `/api/admin`) |
| **Reports API** | `web/api_reports.py` (10 pre-built report endpoints at `/api/reports`, uses PerformanceMetricsService) |
| **Explorer API** | `web/api_explorer.py` (structured query builder at `/api/explorer`, table/column whitelist, 21 tables) |
| **Agents API** | `web/api_agents.py` (10 endpoints at `/api/v2/agents`, 16-agent registry with capabilities) |
| **React Frontend** | `frontend/` (Vite + React 18 + TS + Tailwind + AG Grid), `frontend/src/pages/PortfolioPage.tsx`, `frontend/src/pages/ReportsPage.tsx` (8 tabs), `frontend/src/pages/DataExplorerPage.tsx` (query builder), `frontend/src/pages/AgentsPage.tsx` (4 tabs: agents, research, knowledge, ML), `frontend/src/pages/AgentDetailPage.tsx` (drill-down), `frontend/src/pages/settings/` (4 config screens), `frontend/src/components/agents/` (AgentCard, AgentRunTimeline, ObjectiveGradeChart), `frontend/src/hooks/useAgents.ts` |
| **Tests** | `tests/` (270 pytest), `harness/` (17 integration steps) |
| **Templates** | `config/templates/` (27 templates: 1 0DTE, 4 weekly, 16 monthly, 5 LEAPS, 1 custom) |

---

## [CLAUDE OWNS] OPEN QUESTIONS

| # | Question | Context | Decision |
|---|----------|---------|----------|
| 1 | VaR confidence level? | Defaults to 95% | TBD |
| 2 | Max portfolio VaR as % of equity? | Needs threshold to enforce | TBD |
| 3 | Concentration limits correct? | 10% (Core), 30% (Med), 40% (High) | TBD |
| 4 | Exit rule profiles correct? | Conservative 50%/21DTE, balanced 65%/14DTE, aggressive 80%/7DTE | TBD |
| 5 | Paper trading before live? | Affects portfolio type | TBD |
| 6 | Promote playground/ to runners/? | sync_portfolio etc. are experimental | TBD |
| 7 | Liquidity defaults reasonable? | Entry: OI≥100, spread≤5%, vol≥500. Adjustment: OI≥500, spread≤3%, vol≥1000 | TBD |
| 8 | Auto-accept criteria for exits? | Stop loss hit? Profit target? DTE<3? | TBD |
| 9 | Workflow notification channel? | Email first? Slack? SMS? Multiple? | TBD |
| 10 | Daily loss halt %? | Suggested 3% of total capital. Per-portfolio or global? | TBD |
| 11 | Weekly loss halt %? | Suggested 5% of total capital. Requires review to resume? | TBD |
| 12 | Max trades per day? | Suggested 3 (across all portfolios). 0DTE count separately? | TBD |
| 13 | Consecutive loss pause threshold? | 3 losses in same strategy = pause 1 week? 5 = pause portfolio? | TBD |
| 14 | Workflow cycle frequency? | Every 30 min during market hours? Event-driven? Configurable? | TBD |
| 15 | Paper mode duration? | How long to run paper before going live? 1 month? 3 months? Performance threshold? | TBD |

---

## [CLAUDE OWNS] CODING STANDARDS

- `Decimal` for ALL money/price values. Never float.
- `UUID` strings for all entity IDs
- Type hints on every function signature
- `dataclass` for domain models, prefer `frozen=True` for value objects
- Specific exceptions only, never bare `Exception`
- Always use `session_scope()` for DB — never raw sessions
- Import order: stdlib → third-party → local (`trading_cotrader.`)
- DB pattern: `with session_scope() as session: repo = SomeRepository(session)`
- Adding strategy: enum in `domain.py` → config in `risk_config.yaml`
- Schema change: ORM in `schema.py` → domain in `domain.py` → `setup_database.py`

---

## [CLAUDE OWNS] DEV COMMANDS

```bash
# Core
python -m trading_cotrader.scripts.setup_database
python -m trading_cotrader.harness.runner --skip-sync    # 17 steps, no broker
python -m trading_cotrader.harness.runner --mock
pytest trading_cotrader/tests/ -v                        # 270 unit tests

# Workflow engine (NEW)
python -m trading_cotrader.runners.run_workflow --once --no-broker --mock    # single cycle test
python -m trading_cotrader.runners.run_workflow --paper --no-broker          # continuous, no broker
python -m trading_cotrader.runners.run_workflow --paper --no-broker --web    # continuous + web dashboard
python -m trading_cotrader.runners.run_workflow --paper                       # continuous, with broker

# Trade booking
python -m trading_cotrader.cli.book_trade --file trading_cotrader/config/trade_template.json --no-broker

# Screeners
python -m trading_cotrader.cli.run_screener --screener vix --symbols SPY,QQQ --no-broker
python -m trading_cotrader.cli.run_screener --screener all --symbols SPY,QQQ --no-broker
python -m trading_cotrader.cli.run_screener --screener correction --symbols SPY,QQQ --no-broker
python -m trading_cotrader.cli.run_screener --screener earnings --symbols AAPL,NVDA --no-broker
python -m trading_cotrader.cli.run_screener --screener black_swan --symbols SPY --no-broker
python -m trading_cotrader.cli.run_screener --screener arbitrage --symbols SPY,QQQ --no-broker
python -m trading_cotrader.cli.run_screener --screener vix --symbols SPY --macro-outlook uncertain --expected-vol extreme --no-broker

# Recommendations
python -m trading_cotrader.cli.accept_recommendation --list
python -m trading_cotrader.cli.accept_recommendation --accept <ID> --notes "reason" --portfolio high_risk

# Portfolio evaluation
python -m trading_cotrader.cli.evaluate_portfolio --portfolio high_risk --no-broker --dry-run
python -m trading_cotrader.cli.evaluate_portfolio --all --no-broker

# Multi-broker (NEW)
python -m trading_cotrader.cli.init_portfolios                                # create 10 portfolios
python -m trading_cotrader.cli.init_portfolios --dry-run                       # preview only
python -m trading_cotrader.cli.sync_fidelity --file Portfolio_Positions.csv     # load Fidelity CSV
python -m trading_cotrader.cli.load_stallion                                   # load 29 Stallion holdings
python -m trading_cotrader.cli.load_stallion --dry-run                         # preview only

# Web dashboard (embedded in workflow)
# python -m trading_cotrader.runners.run_workflow --web --port 8080 --no-broker --mock

# React frontend (NEW — Session 19)
cd frontend && pnpm install                              # install frontend deps (first time)
cd frontend && pnpm dev                                  # dev server at localhost:5173
cd frontend && pnpm build                                # production build → frontend/dist/

# Live order execution (within workflow CLI):
#   execute <trade_id>           # dry-run preview
#   execute <trade_id> --confirm # place real order
#   orders                       # check fill status
```

### Critical runtime notes
- Greeks come from DXLink streaming, NOT REST API
- Always test with `IS_PAPER_TRADING=true` before live
- Never store credentials in code — use `.env`
