# CLAUDE.md
# Project: Trading CoTrader
# Last Updated: February 23, 2026 (session 35b)
# Historical reference: CLAUDE_ARCHIVE.md (architecture decisions, session log s1-s26)

## STANDING INSTRUCTIONS
- **ALWAYS update CLAUDE.md** after major changes — update: code map, agent flow, UI pages, open items.
- **ALWAYS update MEMORY.md** (`~/.claude/projects/.../memory/MEMORY.md`) with session summary.
- **Append new architecture decisions to CLAUDE_ARCHIVE.md**, not here.
- **Force reinstall market_analyzer** at start of each session: `pip install --force-reinstall --no-deps -e ../market_analyzer`
- If context is running low, prioritize writing updates BEFORE doing more work.

---

## [NITIN OWNS] WHY THIS EXISTS

20 years pricing and risk analytics on institutional trading floors — IR, commodities, FX, mortgages.
The gap: 1. Time flies by, opportunity cost enormous. 2. Believes in systems and automation — now possible with Agentic AI. 3. Failing in managing own money is a behaviour problem, not knowledge. 4. Institutional discipline never applied to personal wealth. 250K sits idle (50K personal, 200K self-directed IRA).
Agent-based approach deploys capital systematically, safely, with full risk visibility at every level: trade, strategy, portfolio.
Mental model: Macro Context -> My Exposure -> Action Required. Never "I have an iron condor." Always "I have -150 SPY delta, +$450 theta/day. Am I within limits?"

---

## [NITIN OWNS] UI PAGE ARCHITECTURE

### Primary Pages (always in sidebar)

| # | Page | Route | What It Shows | Data Source |
|---|------|-------|---------------|-------------|
| 1 | **Market Analysis** | `/` (landing) | Watchlist grid with column groups: Core, Regime, Technicals, Momentum, Fundamentals, Opportunities, Smart Money, Levels. Macro strip. Signals badges. | **Scout** (Quant) -> ResearchContainer -> `api_research.py` |
| 2 | **Ticker Detail** | `/market/:ticker` | Deep-dive single ticker: regime, phase, technicals, levels, opportunities, chart | Scout -> ResearchContainer + MarketAnalyzer endpoints |
| 3 | **Portfolio** | `/portfolio` | Live broker positions, Greeks, P&L, risk factors, agent-booked trades | **Steward** (PortfolioManager) -> PortfolioBundle containers -> `api_v2.py` |
| 4 | **Agents** | `/agents` | Agent cards: status, last run, grade, responsibilities, run history | `api_agents.py` -> AgentRunORM + BaseAgent metadata |

### Archived Pages (under "Other" menu item, keep APIs)

| Page | Route | Status |
|------|-------|--------|
| Trading / WhatIf | `/trading` | Keep API (`api_trading_sheet.py`), archive UI |
| Capital | `/capital` | Move under Other |
| Recommendations | `/recommendations` | Move under Other |
| Reports | `/reports` | Move under Other |
| Data Explorer | `/data` | Move under Other |
| Funds | `/funds` | Move under Other |

### Removed from Sidebar (hide, keep code for later)

| Page | Route | Why |
|------|-------|-----|
| Workflow | `/workflow` | Not useful as standalone page yet |
| Risk | `/risk` | Risk data should live on Portfolio page |
| Performance | `/performance` | Performance data should live on Portfolio page |

### Config (expandable submenu)
- `/settings/portfolios`, `/settings/risk`, `/settings/workflow`, `/settings/capital`

### UI Data Flow Pattern (QuantAgent exemplar — ALL pages must follow this)
```
MarketAnalyzer (external lib)
  |
  v
Agent.populate()          <-- agent owns the data pipeline
  |
  v
Container (in-memory)     <-- agent writes to its container
  |
  v
Container.save_to_db()    <-- persist for cold start
  |
  v
API endpoint              <-- reads from container (instant), never calls library directly
  |
  v
React Frontend            <-- renders from API response
```
**Every page renders from its respective agent's container. No page calls services directly.**

---

## [CLAUDE OWNS] AGENT ARCHITECTURE — THE 5 DOMAIN AGENTS

### Naming Conventions
- **Agent files = NOUNS** (what it IS): `steward.py`, `sentinel.py`, `scout.py`, `maverick.py`, `atlas.py`
- **Service files = VERBS** (what it DOES): `portfolio_sync.py`, `condition_evaluator.py`
- **Agent = decision authority.** If it doesn't make autonomous decisions, it's a service, not an agent.

### The 5 Domain Agents

| ID | Fun Name | Role | File | Container | Status |
|----|----------|------|------|-----------|--------|
| `steward` | **Steward** | PortfolioManager — portfolio state, positions, P&L, capital utilization | `agents/domain/steward.py` | PortfolioBundle (via ContainerManager) | DONE (populate + run) |
| `sentinel` | **Sentinel** | RiskManager — VaR, circuit breakers, fitness checks, execution gatekeeper | `agents/domain/sentinel.py` | (future) | Done (merged Guardian+Risk) |
| `scout` | **Scout** | Quant — research, screening, templates, market analysis | `agents/domain/scout.py` | **ResearchContainer** | EXEMPLAR (done) |
| `maverick` | **Maverick** | Trader — domain orchestrator, cross-references Scout+Steward, trading signals | `agents/domain/maverick.py` | Reads from PortfolioBundle + ResearchContainer | WIRED (run: boot+monitoring) |
| `atlas` | **Atlas** | TechArchitect — infrastructure, reporting, QA, system health | `agents/domain/atlas.py` | (future) | Skeleton |

### Non-Agent Services (tools agents can use, not autonomous)
- **AgentBrain** (`services/agent_brain.py`) — LLM chat/analysis via Claude API. Infrastructure service, not an agent.
- **CalendarAgent** — will become a simple service call in engine (is trading day? yes/no)

### Agent Pattern (Scout = exemplar, ALL agents must follow)

```python
class Scout(BaseAgent):  # QuantResearchAgent — THE EXEMPLAR
    """
    1. Owns a Container (ResearchContainer)
    2. populate() fills container from external data (MarketAnalyzer)
    3. run() evaluates templates against container data
    4. analyze() does deep single-symbol analysis
    5. Container persists to DB for cold start
    6. API reads from container, NEVER from external lib directly
    7. get_metadata() classmethod returns agent card info
    """

    def populate(self, context: dict) -> AgentResult:
        # Called during boot + every 30min monitoring
        # Fills ResearchContainer from MarketAnalyzer facade
        # Persists to research_snapshots DB table

    def run(self, context: dict) -> AgentResult:
        # Evaluates research templates via ConditionEvaluator
        # Auto-books triggered trades into research portfolios

    def analyze(self, symbol: str) -> dict:
        # Deep analysis of single symbol
```

**ALL agents must follow this exact pattern:**
1. Own a container
2. `populate()` fills container from data sources
3. `run()` makes decisions based on container data
4. Container persists to DB for instant cold start
5. API reads from container (never the external data source)

### Legacy Agents (8 remaining in engine.py, to be absorbed into the 5 domain agents)

3 legacy agents **removed in s35**: CalendarAgent (inlined in engine), MarketDataAgent (Scout handles it), MacroAgent (replaced by direct MacroContextService call).

| Legacy File | Absorb Into | Role |
|-------------|-------------|------|
| ~~`perception/portfolio_state.py`~~ | ~~**Steward** (populate)~~ | DONE (s35b) — deleted |
| `analysis/screener.py` | **Scout** (run) | Run screeners |
| `analysis/evaluator.py` | **Sentinel** | Evaluate positions for exits |
| ~~`analysis/capital.py`~~ | ~~**Steward** (run)~~ | DONE (s35b) — deleted |
| `execution/executor.py` | **Maverick** | Place orders |
| `execution/notifier.py` | **Maverick** | Send alerts |
| `execution/reporter.py` | **Atlas** | Generate reports |
| `learning/accountability.py` | **Maverick** | Trading discipline |
| `learning/session_objectives.py` | **Maverick** | Daily objectives |
| `learning/qa_agent.py` | **Atlas** | QA assessment |

---

## [CLAUDE OWNS] CONTAINER ARCHITECTURE

### What a Container Is
A container is an **in-memory data store** that an agent owns. It:
- Gets populated by the agent's `populate()` method
- Persists to DB for instant cold start (`save_to_db()` / `load_from_db()`)
- Is read by API endpoints (never the external data source directly)
- Lives in `containers/` directory

### Current Containers

| Container | Owner Agent | DB Table | Fields | API |
|-----------|------------|----------|--------|-----|
| **ResearchContainer** | Scout (Quant) | `research_snapshots` (~155 cols) + `macro_snapshots` | Per-symbol: technicals, regime, phase, opportunities, smart money, levels, fundamentals | `api_research.py` (3 endpoints) |
| **PortfolioBundle** | Steward (PortfolioManager, future) | PositionORM, TradeORM, PortfolioORM | Per-portfolio: positions, trades, risk factors, Greeks, P&L | `api_v2.py` + `api_trading_sheet.py` |
| **ContainerManager** | Engine | — | Orchestrates all bundles + research container | Internal |

### ResearchContainer Detail (Scout's container — the exemplar)

```
ResearchEntry (per symbol):
  # Core
  symbol, last_updated, data_source

  # Technicals (from MarketAnalyzer.technicals)
  price, rsi, atr, iv_rank, sma_20/50/200, bollinger_*, vwap, volume, macd_*

  # Regime (from MarketAnalyzer.regime)
  regime_id (R1-R4), regime_label, confidence, trend, volatility_state

  # Phase (from MarketAnalyzer.phase)
  phase_name (Wyckoff), phase_confidence, phase_age_days, phase_strategy

  # Opportunities (from MarketAnalyzer.opportunity)
  opp_zero_dte_verdict/confidence/strategy/summary
  opp_leap_verdict/confidence/strategy/summary
  opp_breakout_verdict/confidence/strategy/summary
  opp_momentum_verdict/confidence/strategy/summary

  # Smart Money (from MarketAnalyzer.technicals)
  smart_money_score, unfilled_fvg_count, active_ob_count

  # Levels (from MarketAnalyzer.levels) — added s34
  levels_direction, levels_stop_price, levels_best_target_price/rr
  levels_s1/s2/s3 (price, strength, sources, confluence)
  levels_r1/r2/r3 (price, strength, sources, confluence)
  levels_summary

  # Fundamentals (from MarketAnalyzer.fundamentals)
  market_cap, pe_ratio, dividend_yield, sector, earnings_date

MacroContext (global):
  vix, vix_regime, macro_events (30d calendar)
```

### Data Pipeline: How Scout Populates ResearchContainer

```
Scout.populate(context):
  1. Load watchlist from config/market_watchlist.yaml
  2. ma = MarketAnalyzer()
  3. Batch regime detection: ma.regime.detect_batch(tickers)
  4. Per-ticker:
     a. ma.technicals.snapshot(ticker) -> container.update_technicals()
     b. ma.phase.detect(ticker) -> container.update_phase()
     c. ma.opportunity.assess_*(ticker) -> container.update_opportunities()
     d. ma.levels.analyze(ticker) -> container.update_levels()
     e. ma.fundamentals.fetch(ticker) -> container.update_fundamentals()
  5. ma.macro.calendar() -> container.update_macro()
  6. container.save_to_db(session) -> research_snapshots table
```

---

## [CLAUDE OWNS] WORKFLOW ENGINE — State Machine

### 12 States, 17 Transitions

```
IDLE -> BOOTING -> MACRO_CHECK -> SCREENING -> RECOMMENDATION_REVIEW (human pause)
                                      |                    |
                                      v                    v
                                 MONITORING <---------- EXECUTION
                                   |    |
                                   |    v
                                   |  TRADE_MANAGEMENT -> TRADE_REVIEW (human pause)
                                   |                           |
                                   v                           v
                              EOD_EVALUATION              EXECUTION
                                   |
                                   v
                               REPORTING -> IDLE

From anywhere: -> HALTED (circuit breaker) -> resume -> MONITORING
```

### Agent Call Matrix (which agent runs in which state)

| State | Agent Called | Method | Type |
|-------|-------------|--------|------|
| **BOOTING** | CalendarAgent | _check_trading_day() | Inlined (s35) |
| | PortfolioSyncService | sync | Service |
| | **Steward** | populate() | BaseAgent (DONE s35b) |
| | **Sentinel** | run() | BaseAgent |
| | **Steward** | run() | BaseAgent (capital util, DONE s35b) |
| | SessionObjectivesAgent | set_objectives() | Legacy -> Maverick |
| | **Scout** (Quant) | populate() | BaseAgent (DONE) |
| | **Maverick** | run() | BaseAgent (DONE s35c) |
| **MACRO_CHECK** | MacroAgent | run() | Legacy -> Scout |
| **SCREENING** | ScreenerAgent | run() | Legacy -> Scout |
| | RiskAgent (Sentinel) | run() | BaseAgent |
| **REC_REVIEW** | (human pause — approve/reject) | | |
| **EXECUTION** | Guardian.check_constraints() | per-action | BaseAgent |
| | ExecutorAgent | run() | Legacy -> Maverick |
| **MONITORING** | PortfolioSyncService | sync | Service |
| (30min cycle) | **Steward** | populate() + run() | BaseAgent (DONE s35b) |
| | **Sentinel** | run() | BaseAgent |
| | **Scout** | run() + populate() | BaseAgent (DONE) |
| | **Maverick** | run() | BaseAgent (DONE s35c) |
| **TRADE_MGMT** | PortfolioState, EvaluatorAgent | run() | Legacy |
| **EOD_EVAL** | PortfolioState, EvaluatorAgent | run() | Legacy |
| **REPORTING** | Accountability, Capital, SessionObj, QA, Reporter | run() | Legacy |

### Boot Sequence (what happens on engine start)
1. `_init_container_manager()` — create ContainerManager, initialize bundles per portfolio
2. `_load_research_from_db()` — instant cold start: ResearchContainer loads from `research_snapshots`
3. `_refresh_containers()` — load portfolio bundles from DB
4. Create all agents (5 core BaseAgent + 11 legacy)
5. Authenticate broker adapters
6. Start APScheduler (30min monitoring cycle)
7. Transition: IDLE -> BOOTING -> state handlers take over

### Monitoring Cycle (every 30 minutes)
1. Refresh market data (MarketDataAgent)
2. Sync broker positions (PortfolioSyncService)
3. Refresh portfolio state (PortfolioStateAgent)
4. Refresh containers from DB
5. Capital check, safety check (Sentinel)
6. Scout.run() — evaluate research templates
7. Scout.populate() — refresh ResearchContainer + persist to DB
8. Transition to TRADE_MANAGEMENT

---

## [CLAUDE OWNS] MARKET ANALYZER — External Library

**Location**: `C:\Users\nitin\PythonProjects\market_analyzer` (editable install in eTrading venv)
**Force reinstall each session**: `pip install --force-reinstall --no-deps -e ../market_analyzer`

### MarketAnalyzer Facade
```python
ma = MarketAnalyzer()
ma.regime.detect(ticker)           # R1-R4 regime classification
ma.regime.detect_batch(tickers)    # batch detection
ma.regime.research(ticker)         # full research with transitions
ma.technicals.snapshot(ticker)     # TechnicalSnapshot (price, RSI, ATR, etc.)
ma.phase.detect(ticker)            # Wyckoff phase detection
ma.opportunity.assess_zero_dte(t)  # 0DTE assessment (GO/CAUTION/NO_GO)
ma.opportunity.assess_leap(t)      # LEAP assessment
ma.opportunity.assess_breakout(t)  # Breakout assessment
ma.opportunity.assess_momentum(t)  # Momentum assessment
ma.levels.analyze(ticker)          # Support/resistance, stop loss, targets, R:R
ma.fundamentals.fetch(ticker)      # Market cap, P/E, dividend, sector
ma.macro.calendar()                # 30-day macro event calendar
```

### API Endpoints (in api_v2.py)
| Method | Path | Source |
|--------|------|--------|
| GET | `/api/v2/regime/{ticker}` | ma.regime.detect() |
| POST | `/api/v2/regime/batch` | ma.regime.detect_batch() |
| GET | `/api/v2/regime/{ticker}/research` | ma.regime.research() |
| POST | `/api/v2/regime/research` | batch research |
| GET | `/api/v2/phase/{ticker}` | ma.phase.detect() |
| GET | `/api/v2/opportunity/zero-dte/{ticker}` | ma.opportunity.assess_zero_dte() |
| GET | `/api/v2/opportunity/leap/{ticker}` | ma.opportunity.assess_leap() |
| GET | `/api/v2/opportunity/breakout/{ticker}` | ma.opportunity.assess_breakout() |
| GET | `/api/v2/opportunity/momentum/{ticker}` | ma.opportunity.assess_momentum() |
| GET | `/api/v2/levels/{ticker}` | ma.levels.analyze() |
| GET | `/api/v2/technicals/{ticker}` | ma.technicals.snapshot() |
| GET | `/api/v2/fundamentals/{ticker}` | ma.fundamentals.fetch() |
| GET | `/api/v2/macro/calendar` | ma.macro.calendar() |

---

## [CLAUDE OWNS] CODE MAP

| Area | Key Files |
|------|-----------|
| **Scout (Quant)** | `agents/domain/scout.py`, `containers/research_container.py`, `web/api_research.py`, `repositories/research_snapshot.py` |
| **Steward (PortfolioManager)** | `agents/domain/steward.py`, `containers/portfolio_bundle.py` |
| **Sentinel (RiskManager)** | `agents/domain/sentinel.py` (merged Guardian+Risk), `services/portfolio_fitness.py`, `services/risk/var_calculator.py`, `config/workflow_rules.yaml` |
| **Maverick (Trader)** | `agents/domain/maverick.py` (orchestrator — reads PortfolioBundle + ResearchContainer) |
| **Atlas (TechArchitect)** | `agents/domain/atlas.py` (skeleton) |
| **Agent Framework** | `agents/base.py` (BaseAgent ABC), `agents/protocol.py` (AgentResult/AgentStatus) |
| **Agent API** | `web/api_agents.py` (9 endpoints, dynamic registry from BaseAgent metadata) |
| **Containers** | `containers/container_manager.py`, `containers/portfolio_bundle.py`, `containers/research_container.py` |
| **Workflow Engine** | `workflow/engine.py` (orchestrator), `workflow/states.py` (12 states), `workflow/scheduler.py` |
| **Trading Sheet** | `web/api_trading_sheet.py` (4 endpoints: dashboard, evaluate, add-whatif, book) |
| **Market Analyzer** | External lib `market_analyzer` (editable from `../market_analyzer`). Endpoints in `web/api_v2.py` |
| **Research Templates** | `config/research_templates.yaml` (7 templates), `services/research/template_loader.py`, `services/research/condition_evaluator.py` |
| **Broker Adapters** | `adapters/base.py` (ABC), `adapters/factory.py`, `adapters/tastytrade_adapter.py` |
| **Pricing** | `services/pricing/probability.py` (POP/EV), `services/pricing/black_scholes.py` |
| **DB/ORM** | `core/database/schema.py` (23 tables), `core/database/session.py`, `repositories/` |
| **Web Server** | `web/approval_api.py` (FastAPI factory), `web/api_v2.py`, `web/api_research.py`, `web/api_agents.py`, `web/api_trading_sheet.py` |
| **Config** | `config/risk_config.yaml` (15 portfolios), `config/brokers.yaml`, `config/workflow_rules.yaml`, `config/market_watchlist.yaml` |
| **Frontend** | `frontend/` (Vite + React 18 + TS + Tailwind + AG Grid + Recharts) |
| **Tests** | `tests/` (270 pytest), `harness/` (integration) |

### Frontend Files
| Page | File | Route |
|------|------|-------|
| Market Analysis (landing) | `pages/ResearchDashboardPage.tsx` | `/` |
| Ticker Detail | `pages/ResearchPage.tsx` | `/market/:ticker` |
| Portfolio | `pages/PortfolioPage.tsx` | `/portfolio` |
| Agents | `pages/AgentsPage.tsx` | `/agents` |
| Agent Detail | `pages/AgentDetailPage.tsx` | `/agents/:name` |
| Trading | `pages/TradingDashboardPage.tsx` | `/trading` |
| All others | see `App.tsx` | various |
| Sidebar | `layout/Sidebar.tsx` | — |

---

## [CLAUDE OWNS] CODING STANDARDS

### General
- `Decimal` for ALL money/price values. Never float.
- `UUID` strings for all entity IDs
- Type hints on every function signature
- `dataclass` for domain models, prefer `frozen=True` for value objects
- Specific exceptions only, never bare `Exception`
- Always use `session_scope()` for DB — never raw sessions
- Import order: stdlib -> third-party -> local (`trading_cotrader.`)
- Schema change: ORM in `schema.py` -> domain in `domain.py` -> `setup_database.py`

### Naming Conventions
- **Agent files = NOUNS** (what it is): `guardian.py`, `scout.py`, `warden.py`
- **Service files = VERBS** (what it does): `portfolio_sync.py`, `condition_evaluator.py`, `trade_booking_service.py`
- Agent classes: `SentinelAgent`, `ScoutAgent`, etc.
- Service classes: `PortfolioFitnessChecker`, `ConditionEvaluator`, etc.

### ZERO DEAD CODE POLICY (Nitin mandate)
- **NEVER create code that is not immediately used end-to-end.** Every file, class, function must be imported and called.
- **NEVER create placeholder/stub agents, services, or files** "for future use."
- **Before creating a new file:** Verify it will be imported and used. If not, don't create it.
- **Before deleting functionality from UI:** Delete the corresponding backend code too.
- **Metadata lives WITH the code.** Agent descriptions, icons, boundaries belong in the agent class (`get_metadata()`).
- **After every change:** Run `pytest` + `pnpm build`. Fix broken imports immediately.

---

## [CLAUDE OWNS] DEV COMMANDS

```bash
# Force reinstall market_analyzer (EVERY SESSION)
pip install --force-reinstall --no-deps -e ../market_analyzer

# Core
python -m trading_cotrader.scripts.setup_database
pytest trading_cotrader/tests/ -v

# Workflow engine + web (THE MAIN WAY TO RUN)
python -m trading_cotrader.runners.run_workflow --paper --web                 # with broker
python -m trading_cotrader.runners.run_workflow --paper --no-broker --web     # without broker
python -m trading_cotrader.runners.run_workflow --once --no-broker --mock     # single cycle test

# React frontend
cd frontend && pnpm dev                                  # dev server at localhost:5173
cd frontend && pnpm build                                # production build

# Screeners (CLI)
python -m trading_cotrader.cli.run_screener --screener all --symbols SPY,QQQ --no-broker

# Harness
python -m trading_cotrader.harness.runner --skip-sync
```

### Critical Runtime Notes
- Greeks come from DXLink streaming, NOT REST API
- Always test with `IS_PAPER_TRADING=true` before live
- Never store credentials in code — use `.env`
- **Harness vs Engine rule:** Every feature working in harness MUST be verified in workflow engine + API

---

## [CLAUDE OWNS] EXISTING INFRASTRUCTURE (Not Yet Wired to Agents)

| Service | File | What It Does | Wire Into |
|---------|------|-------------|-----------|
| VaR Calculator | `services/risk/var_calculator.py` | Parametric + historical VaR | Sentinel |
| P&L Attribution | `analytics/pricing/pnl_calculator.py` | Greek decomposition of P&L | Steward |
| Portfolio Evaluation | `services/portfolio_evaluation_service.py` | Exit rules (TP, SL, DTE, delta) | Sentinel |
| Black-Scholes | `services/pricing/black_scholes.py` | Greeks computation | Sentinel |
| Macro Context | `services/macro_context_service.py` | VIX regime, macro gates | Scout or Sentinel |
| Performance Metrics | `services/performance_metrics_service.py` | Win rate, Sharpe, drawdown | Maverick |
| Liquidity | `services/liquidity_service.py` | OI, spread, volume thresholds | Scout |
| Order Execution | `adapters/tastytrade_adapter.py` (place_order) | 2-step LIMIT orders | Maverick |
| Trade Booking | `services/trade_booking_service.py` | Book trades with legs, Greeks | Maverick |
| Snapshots | `services/snapshot_service.py` | Daily portfolio snapshots | Atlas |
| Earnings Calendar | `services/earnings_calendar_service.py` | yfinance earnings dates | Scout |
| Agent Intelligence | `services/agent_brain.py` | LLM via Claude API | Service (any agent) |

---

## [CLAUDE OWNS] OPEN ITEMS

### Agent Definition & Implementation — IN PROGRESS (open-ended)
Agent definitions are evolving. Scout (Quant) is the exemplar. Other 4 agents (Steward, Sentinel, Maverick, Atlas) have roles defined but implementation is open. Next session continues building Scout.

**Current state (s35c):**
- **Scout** (Quant) — DONE: BaseAgent + populate() + ResearchContainer + DB persistence + API. File: `agents/domain/scout.py`
- **Sentinel** (RiskManager) — DONE: Merged Guardian+Risk. Circuit breakers + VaR + constraints + container-based risk reads. File: `agents/domain/sentinel.py`
- **Steward** (PortfolioManager) — DONE: populate() fills PortfolioBundle from DB, run() does capital utilization analysis. Absorbed portfolio_state + capital agents. File: `agents/domain/steward.py`
- **Maverick** (Trader) — WIRED (s35c): Domain orchestrator. run() cross-references Steward's PortfolioBundle with Scout's ResearchContainer to produce trading signals. Runs during boot + monitoring. `api_trading_sheet.py` GET reads entirely from containers. Next: absorb executor + notifier + accountability + objectives.
- **Atlas** (TechArchitect) — Skeleton. Needs: absorb reporter + QA, own container for system health

### AgentBrain Service — Unfinished
- 3 methods have no API endpoints
- Chat is stateless
- Uses raw broker data, not container data
- Requires `ANTHROPIC_API_KEY`
- Decision: service (not an agent) — any agent can use it as a tool

### UI Enhancements Pending
- Market Analysis page: click-through to ticker detail needs polish
- Portfolio page: all data should come from Steward's container
- Agents page: needs enhancements (TBD by Nitin)
- Sidebar: restructure per UI Architecture section (primary/archived/removed)
- Agent file renames to nouns — DONE (s35): all 5 domain agents in `agents/domain/`

---

## [CLAUDE OWNS] SESSION LOG (recent)

| Session | Date | What |
|---------|------|------|
| s35c | Feb 23 | Wired Maverick as domain orchestrator. MaverickAgent.run() cross-references Steward's PortfolioBundle with Scout's ResearchContainer to produce trading signals. Rewired `api_trading_sheet.py` GET endpoint: ALL reads from containers (no DB queries). Added `market_context` (Scout's research) to trading dashboard response. Rewired `evaluate` endpoint to use ResearchContainer instead of TechnicalAnalysisService. Engine passes container_manager to Maverick, calls in boot + monitoring. Updated api_agents.py registry. 11 new tests. 296 tests pass. |
| s35b | Feb 23 | Built out Steward (PortfolioManager). populate() absorbs PortfolioStateAgent (fills PortfolioBundle from DB), run() absorbs CapitalUtilizationAgent (capital analysis + alerts). Enhanced Sentinel with container_manager (reads risk from containers, falls back to DB). Added PortfolioRiskLimits + concentration_pct + to_summary() to RiskFactorContainer. Deleted 2 legacy files (portfolio_state.py, capital.py). 13 new tests. 285 tests pass. |
| s35 | Feb 23 | Agent architecture reorganization. Created `agents/domain/` with 5 renamed agents (scout, sentinel, steward, maverick, atlas). Merged Guardian+Risk into Sentinel. Converted 3 legacy agents to services (calendar inlined, market_data removed, macro uses service). Deleted 8 old files. Updated engine, APIs, 3 test files, 12 frontend files. 272 tests pass. |
| s34 | Feb 22 | LevelsService integration (ResearchContainer + schema + Scout + API + UI). CLAUDE.md rewrite. |
| s33 | Feb 22 | MarketAnalyzer full integration — phase + opportunities + smart money. 9 API endpoints. |
| s32 | Feb 22 | Agent framework refactor — BaseAgent ABC + QuantResearchAgent exemplar. |
| s31 | Feb 22 | DB-backed ResearchContainer — instant cold start from research_snapshots. |
| s30 | Feb 22 | ResearchContainer + API + UI. ResearchDashboardPage as landing. |
| s29 | Feb 21 | Market regime integration. 4 regime endpoints. |
| s28 | Feb 21 | P&L + duplication postmortem. 5 critical bug fixes. |
| s27 | Feb 19 | THE PIVOT — Trading Sheet as product. 1 feature at a time. |
| s26 | Feb 19 | Trading Sheet v1. Probability, fitness checker. |
| s25 | Feb 18 | Full frontend. Critical broker/container fix in engine.py. |
