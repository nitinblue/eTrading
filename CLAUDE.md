# CLAUDE.md
# Project: Trading CoTrader
# Last Updated: February 16, 2026 (session 16, continued)
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
### Feb 16, 2026 (Session 6) — Continuous Trading Workflow Engine
Updating the objective set in Session 5 on Feb 16. I want to get started with building Agents who will be taking full responsiblility of prortfolo management, trading, growing the money. Nitin will be there to help take decisions. System is not expected to be big time on LLM,
but most definitely System needs to be smart enough to continously improve the payoff, and capable of reinforcement learning. Nitin is very new to creating Agents, Claude is responsible to propose the most simple, elegant solution to writting agents which is not suppose to have general intelligenece, but knows in and out of the system and understands the execution on a daily basis. I am happy with the AI/ML learning capabilities at this point. However in future Agents should be able to adapt to latest and greatest. Main objective is to develop a product, that acts as a cotrader, and does not expect end user to do repeat mundane work. I have always believed in codifying rules and decision anyway, so why should any one be required to get up every morning and look at charts and markets.

### Feb 16, 2026 (Session 5) — Continuous Trading Workflow Engine

**Context:** The system today is a collection of CLI tools you run on-demand. Each piece works (screeners, booking, evaluation, metrics) but nothing connects them into a continuous operating loop. You run a screener, copy a recommendation ID, run accept, copy a template, edit it, run book_trade. This is fragile, manual, and easy to skip. The harness validates integration but doesn't drive real trading decisions.

**What this is:** A continuously running workflow engine that operates your entire trading day — from macro check to trade execution to position management — with decision points where YOU approve/reject, and accountability tracking that ensures you stay invested and follow the system.

**How it differs from harness:** Harness runs once, tests, exits. Workflow runs continuously, maintains state, pauses for user decisions, sends notifications, tracks accountability, and drives real capital deployment.

| # | Objective | Signal (observable behavior) | Status |
|---|-----------|-------------------------------|--------|
| 1 | **Workflow state machine** — Continuous loop: BOOT → MACRO_CHECK → SCREENING → RECOMMENDATION_REVIEW → EXECUTION → MONITORING → EXIT_EVALUATION → EXIT_REVIEW → REPORTING. State persisted in DB. Can resume after restart. | `python -m trading_cotrader.runners.run_workflow --once --no-broker --mock` runs single cycle. State in DB/CLI. | DONE (s13) |
| 2 | **User decision points** — Workflow pauses at RECOMMENDATION_REVIEW and EXIT_REVIEW. Presents options (approve/reject/defer). Tracks time-to-decision via DecisionLogORM. | Workflow stops, notifies user, waits. Interactive CLI: approve/reject/defer/status/list/halt/resume/override. | DONE (s13) |
| 3 | **Notifications & approvals** — Console notifications always on. Email framework built (off by default). Recommendations, exits, halts, daily summaries. | NotifierAgent: console + email (SMTP/TLS). Enable in workflow_rules.yaml when ready. | DONE (s13) |
| 4 | **Capital deployment accountability** — Track deployed vs idle capital per portfolio. Days since last trade. Recs ignored. Time-to-decision. | AccountabilityAgent queries DecisionLogORM + TradeORM. Writes accountability_metrics to context. | DONE (s13) |
| 5 | **Trade plan compliance** — Every execution compared to template. Deviations flagged: wrong strikes, wrong DTE, wrong timing, wrong portfolio, skipped entry conditions. "Did you follow the playbook?" metric. Source comparison: system recs vs manual overrides, with performance tracking on both. | Monthly compliance report: "87% of trades followed template. Manual overrides underperformed system recs by 12%." | NOT STARTED |
| 6 | **Workflow scheduling** — Calendar-aware via exchange_calendars (NYSE holidays). FOMC dates in YAML. Cadences: 0DTE daily, weekly Wed/Fri, monthly by DTE window. APScheduler for continuous mode. | CalendarAgent + WorkflowScheduler. Morning boot 9:25, monitoring every 30 min, EOD 3:30, report 4:15 ET. | DONE (s13) |
| 7 | **WhatIf → Order conversion** — Paper mode default. ExecutorAgent books via RecommendationService.accept_recommendation(). | `--paper` mode (default). `--live` flag exists but double-confirmation not yet implemented. | PARTIAL (s13) |
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
- Event data feeds AI/ML for RL — **NOT STARTED** (needs 500+ trades)

---

## [NITIN OWNS] SESSION MANDATE
<!-- Current session only. Move prior to CLAUDE_ARCHIVE.md. -->

### Feb 16, 2026 (Session 5)
Objective:
1. Build a continuous trading workflow engine that replaces the manual CLI-driven approach
2. Workflow = state machine: macro → screener → recommendations → user decision → trade staging → monitoring → exit evaluation
3. Different from harness: workflow maintains state, pauses for user, sends notifications, runs continuously
4. Accountability: track capital deployment, trade plan compliance, time-to-decision, missed opportunities
5. Start with WhatIf/paper mode, future: convert to real broker orders
Done looks like: `python -m trading_cotrader.workflow.engine --start` runs a continuous loop, presents recommendations, waits for user, tracks everything.
Not touching today: UI, real broker orders (paper mode only)

---

## [NITIN OWNS] TODAY'S SURGICAL TASK
<!-- OVERWRITE each session. 5 lines max. -->

Document the workflow engine architecture. Create TRADING_PLAYBOOK.md (done).
Create trade templates with entry conditions and P&L drivers (done).
Next: implement the workflow engine core (state machine, scheduler, notification framework).

---

## [CLAUDE OWNS] WHAT USER CAN DO TODAY

**Web Approval Dashboard (NEW — Session 17):**
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
- Full state machine: IDLE → BOOT → MACRO_CHECK → SCREENING → RECOMMENDATION_REVIEW → EXECUTION → MONITORING → EXIT_EVALUATION → EXIT_REVIEW → REPORTING
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
- Unit tests: `pytest trading_cotrader/tests/ -v` — 157 tests, all pass

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
- AI/ML model training not wired (need data first — 100+ closed trades)
- AI/ML recommendations not integrated into workflow (need trained models)
- Live broker order execution (paper mode only — `--live` needs double-confirmation UI)
- Trade plan compliance tracking (template comparison, deviation flagging)
- Email notifications (framework built, SMTP not configured)
- Liquidity check on entry screeners not yet wired (exit-side only)
- OI + daily volume from broker not integrated (mock placeholders)
- IV rank uses realized vol proxy — needs broker IV
- UI is prototypes only (`ui/`)
- Performance metrics return zeros (no closed trades)

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
| **Analysis** | `agents/analysis/macro.py`, `agents/analysis/screener.py`, `agents/analysis/evaluator.py`, `agents/analysis/risk.py`, `agents/analysis/capital.py` (idle capital monitoring) |
| **Execution** | `agents/execution/executor.py`, `agents/execution/broker_router.py` (per-broker routing), `agents/execution/notifier.py`, `agents/execution/reporter.py` |
| **Decision** | `agents/decision/interaction.py` (InteractionManager — routes user commands) |
| **Learning** | `agents/learning/accountability.py` (decision tracking), `agents/learning/session_objectives.py` (agent self-assessment), `agents/learning/qa_agent.py` (daily QA assessment) |
| **Workflow Config** | `config/workflow_rules.yaml`, `config/workflow_config_loader.py` |
| **Broker Adapters** | `adapters/base.py` (BrokerAdapterBase ABC, ManualBrokerAdapter, ReadOnlyAdapter), `adapters/factory.py` (BrokerAdapterFactory), `adapters/tastytrade_adapter.py` (TastyTrade SDK — all `tastytrade` imports confined here) |
| **Broker Config** | `config/brokers.yaml` (4 brokers), `config/broker_config_loader.py` (BrokerRegistry) |
| **Containers** | `containers/portfolio_bundle.py` (per-portfolio bundle), `containers/container_manager.py` (Dict[str, PortfolioBundle]), `containers/portfolio_container.py`, `containers/position_container.py` |
| **Portfolios** | `config/risk_config.yaml` (10 portfolios), `config/risk_config_loader.py`, `services/portfolio_manager.py` |
| **Trade Booking** | `services/trade_booking_service.py`, `cli/book_trade.py`, `core/models/domain.py` (TradeStatus, TradeSource) |
| **Screeners** | `services/screeners/` (vix, iv_rank, leaps), `services/recommendation_service.py`, `services/technical_analysis_service.py` |
| **Macro Gate** | `services/macro_context_service.py`, `config/daily_macro.yaml` |
| **Portfolio Eval** | `services/portfolio_evaluation_service.py`, `services/position_mgmt/rules_engine.py`, `services/liquidity_service.py` |
| **Recommendations** | `core/models/recommendation.py` (RecommendationType), `repositories/recommendation.py`, `cli/accept_recommendation.py`, `cli/evaluate_portfolio.py` |
| **Risk/VaR** | `services/risk/var_calculator.py`, `services/risk/correlation.py`, `services/risk/` (concentration, margin, limits) |
| **Performance** | `services/performance_metrics_service.py` (win rate, CAGR, Sharpe, drawdown, source breakdown) |
| **Events/ML** | `services/event_logger.py`, `core/models/events.py`, `ai_cotrader/` (feature extraction, RL — needs data) |
| **Pricing** | `analytics/pricing/` (BS, P&L), `analytics/greeks/engine.py`, `services/pricing/` |
| **DB/ORM** | `core/database/schema.py` (19 tables incl. workflow_state, decision_log), `core/database/session.py`, `repositories/` |
| **Broker** | `adapters/tastytrade_adapter.py`, `services/position_sync.py`, `services/portfolio_sync.py`, `cli/init_portfolios.py`, `cli/sync_fidelity.py`, `cli/load_stallion.py` |
| **Web Dashboard** | `web/approval_api.py` (FastAPI app factory, embedded in workflow engine), `ui/approval-dashboard.html` (self-contained dark theme) |
| **Tests** | `tests/` (116 pytest), `harness/` (17 integration steps) |
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
pytest trading_cotrader/tests/ -v                        # 116 unit tests

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
```

### Critical runtime notes
- Greeks come from DXLink streaming, NOT REST API
- Always test with `IS_PAPER_TRADING=true` before live
- Never store credentials in code — use `.env`
