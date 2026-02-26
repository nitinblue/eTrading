# CLAUDE.md
# Project: Trading CoTrader
# Last Updated: February 26, 2026 (session 36)
# Historical reference: CLAUDE_ARCHIVE.md (architecture decisions, session log s1-s26)

## STANDING INSTRUCTIONS
- **ALWAYS update CLAUDE.md** after major changes — update: code map, open items, session log.
- **ALWAYS update MEMORY.md** (`~/.claude/projects/.../memory/MEMORY.md`) with session summary.
- **Force reinstall market_analyzer** at start of each session: `pip install --force-reinstall --no-deps -e ../market_analyzer`
- If context is running low, prioritize writing updates BEFORE doing more work.

---

## WHY THIS EXISTS

20 years pricing and risk analytics on institutional trading floors — IR, commodities, FX, mortgages.
The gap: 1. Time flies by, opportunity cost enormous. 2. Believes in systems and automation — now possible with Agentic AI. 3. Failing in managing own money is a behaviour problem, not knowledge. 4. Institutional discipline never applied to personal wealth. 250K sits idle (50K personal, 200K self-directed IRA).
Agent-based approach deploys capital systematically, safely, with full risk visibility at every level: trade, strategy, portfolio.
Mental model: Macro Context -> My Exposure -> Action Required. Never "I have an iron condor." Always "I have -150 SPY delta, +$450 theta/day. Am I within limits?"

---

## APPROACH — BUILD AGENTS ONE AT A TIME

We are building core agents **one at a time, in a controlled way**. There is only ONE workflow agent: **Maverick (Trader)**. No plans to prioritize beyond what's described here.

**Maverick is the only agent that runs in the workflow state machine.** Scout, Steward, and Sentinel are data/analysis agents that Maverick orchestrates. Atlas is infrastructure — no autonomous decisions.

### The 5 Domain Agents

| Agent | Role | Status | What's Done |
|-------|------|--------|-------------|
| **Scout** (Quant) | Market analysis, screening, ranking | DONE | populate() fills ResearchContainer from MarketAnalyzer. run() does screening + ranking + black swan + context. |
| **Steward** (PortfolioManager) | Portfolio state, positions, P&L, capital | DONE | populate() fills PortfolioBundle from DB. run() does capital utilization analysis. |
| **Sentinel** (RiskManager) | Circuit breakers, constraints, risk reads | DONE | Merged Guardian+Risk. Reads risk from containers, falls back to DB. |
| **Maverick** (Trader) | **THE workflow agent** — orchestrates everything | WIRED | run() cross-references Steward+Scout containers, produces trading signals. Next: build out execution, notifications, discipline. |
| **Atlas** (TechArchitect) | Infrastructure, system health | Skeleton | Not prioritized. |

### Agent Pattern (Scout = exemplar)
```
Agent owns Container -> populate() fills from data source -> save_to_db() -> API reads from container -> UI renders
```
Every agent follows this. No exceptions. No page calls services directly.

---

## DIRECTORY STRUCTURE

```
trading_cotrader/
  agents/                    # THE agent system
    base.py                  #   BaseAgent ABC
    protocol.py              #   AgentResult/AgentStatus
    messages.py              #   Message types
    domain/                  #   5 domain agents
      scout.py               #     Quant (EXEMPLAR)
      steward.py             #     PortfolioManager
      sentinel.py            #     RiskManager
      maverick.py            #     Trader (THE workflow agent)
      atlas.py               #     TechArchitect (skeleton)
    workflow/                #   State machine + scheduling
      engine.py              #     12-state orchestrator
      states.py              #     State definitions
      scheduler.py           #     APScheduler (30min cycle)
      interaction.py         #     CLI command router
  adapters/                  # Broker abstraction
    base.py                  #   ABC + Manual + ReadOnly
    factory.py               #   Create adapters by broker
    broker_router.py         #   Route to correct adapter
    tastytrade_adapter.py    #   TastyTrade (primary, 40+ methods)
  containers/                # In-memory data stores
    container_manager.py     #   Orchestrates all bundles + research
    research_container.py    #   Scout's container (~155 fields)
    portfolio_bundle.py      #   Steward's container (per-portfolio)
    position_container.py    #   Individual positions
    portfolio_container.py   #   Portfolio state
    risk_factor_container.py #   Risk aggregation + limits
    trade_container.py       #   Trade tracking
    market_data_container.py #   Technicals cross-portfolio
  services/                  # Tools agents use (not autonomous)
    agent_brain.py           #   LLM via Claude API
    macro_context_service.py #   VIX regime, macro gates
    performance_metrics_service.py  # Win rate, Sharpe, drawdown
    portfolio_manager.py     #   Portfolio state management
    portfolio_sync.py        #   Broker -> DB sync
    snapshot_service.py      #   Daily portfolio snapshots
    trade_booking_service.py #   Book trades with legs + Greeks
    risk/                    #   Risk calculations
    risk_factors/            #   Risk factor models + resolver
  web/                       # FastAPI endpoints
    approval_api.py          #   Server factory + CORS
    api_v2.py                #   MarketAnalyzer facade (25+ endpoints)
    api_research.py          #   Research container endpoints
    api_agents.py            #   Agent registry + status
    api_trading_sheet.py     #   Trading hub (positions, WhatIf, risk)
    api_reports.py           #   Portfolio reports
    api_terminal.py          #   Terminal/CLI endpoints
    api_explorer.py          #   Data query builder
    api_admin.py             #   Admin/config endpoints
  core/                      # Database + domain models
    database/schema.py       #   21 SQLAlchemy ORM tables
    database/session.py      #   DB session factory
    models/domain.py         #   Frozen dataclasses
    models/events.py         #   Event domain models
    models/strategy_templates.py  # Trade templates
  config/                    # Configuration
    risk_config.yaml         #   15 portfolios (5 real + 5 WhatIf + 5 research)
    brokers.yaml             #   4 brokers
    workflow_rules.yaml      #   Circuit breakers, limits
    market_watchlist.yaml    #   Watchlist tickers for Scout
  repositories/              # DB repository layer (7 files)
  cli/                       # CLI commands (4 commands)
  runners/run_workflow.py    # THE main entry point
  harness/                   # Integration test harness (9 steps)
  tests/                     # 149 pytest (9 files)
  frontend/                  # Vite + React 18 + TS + Tailwind + AG Grid
  playground/                # Archived code (math + screeners)
```

---

## MARKET ANALYZER — External Library

**Location**: `../market_analyzer` (editable install in eTrading venv)

```python
ma = MarketAnalyzer()
ma.regime.detect(ticker)           # R1-R4 regime classification
ma.technicals.snapshot(ticker)     # TechnicalSnapshot (price, RSI, ATR, etc.)
ma.phase.detect(ticker)            # Wyckoff phase detection
ma.opportunity.assess_*(ticker)    # 10 strategy assessments (GO/CAUTION/NO_GO)
ma.levels.analyze(ticker)          # Support/resistance, stop loss, targets
ma.fundamentals.fetch(ticker)      # Market cap, P/E, dividend, sector
ma.macro.calendar()                # 30-day macro event calendar
ma.screening.scan(tickers)         # Screen watchlist
ma.ranking.rank(tickers)           # Rank candidates
ma.black_swan.alert(tickers)       # Black swan detection
ma.context.assess(tickers)         # Market context assessment
```

---

## WORKFLOW ENGINE

Maverick is the only workflow agent. Engine runs in `agents/workflow/engine.py`.

**Active states:** BOOTING and MONITORING call agents. All other states are stubs (legacy agents deleted).

| State | What Happens |
|-------|-------------|
| **BOOTING** | Calendar check -> PortfolioSync -> Steward.populate() -> Sentinel.run() -> Steward.run() -> Scout.populate() -> Maverick.run() |
| **MONITORING** (30min) | PortfolioSync -> Steward.populate()+run() -> Sentinel.run() -> Scout.run()+populate() -> Maverick.run() |
| **Others** | Stubs — no agents wired yet |

---

## UI PAGES

### Primary (always in sidebar)
| Page | Route | Data Source |
|------|-------|-------------|
| Market Analysis | `/` (landing) | Scout -> ResearchContainer -> `api_research.py` |
| Ticker Detail | `/market/:ticker` | Scout + MarketAnalyzer endpoints |
| Portfolio | `/portfolio` | Steward -> PortfolioBundle -> `api_v2.py` |
| Agents | `/agents` | `api_agents.py` -> BaseAgent metadata |

### Archived (under "Other" menu)
Trading/WhatIf, Capital, Reports, Data Explorer, Funds

### Config
`/settings/portfolios`, `/settings/risk`, `/settings/workflow`, `/settings/capital`

---

## CODING STANDARDS

- `Decimal` for ALL money/price values. Never float.
- Type hints on every function signature. `dataclass` for domain models.
- Always use `session_scope()` for DB — never raw sessions.
- **ALL imports at top of file.** No inline/deferred imports unless circular import avoidance.
- **Agent files = NOUNS** (what it is). **Service files = VERBS** (what it does).
- **ZERO DEAD CODE POLICY**: Every file, class, function must be imported and called. Never create stubs "for future use." After every change: `pytest` + `pnpm build`.
- **ZERO local math**: Greeks and prices ALWAYS come from the broker (TastyTrade DXLink streaming). No Black-Scholes, no POP/EV, no VaR calculations.

---

## DEV COMMANDS

```bash
pip install --force-reinstall --no-deps -e ../market_analyzer  # EVERY SESSION
pytest trading_cotrader/tests/ -v                               # 149 tests
python -m trading_cotrader.scripts.setup_database               # create DB tables
python -m trading_cotrader.runners.run_workflow --paper --web    # with broker
python -m trading_cotrader.runners.run_workflow --paper --no-broker --web  # without broker
python -m trading_cotrader.runners.run_workflow --once --no-broker --mock  # single cycle
python -m trading_cotrader.harness.runner --skip-sync            # integration harness
cd frontend && pnpm dev                                          # React dev at :5173
cd frontend && pnpm build                                        # production build
```

---

## OPEN ITEMS

### Maverick (Trader) — THE priority
Only workflow agent. Currently wired: run() produces trading signals from Steward+Scout containers. Next: build out execution (place orders via broker adapter), notifications, trading discipline. Build one capability at a time.

### AgentBrain Service
LLM chat via Claude API (`services/agent_brain.py`). 3 methods without endpoints, stateless chat, uses raw broker data not containers. Requires `ANTHROPIC_API_KEY`.

### UI
- Sidebar: restructure per primary/archived/config layout
- Portfolio page: should read from Steward's container
- Market Analysis: click-through to ticker detail needs polish

---

## SESSION LOG (recent)

| Session | Date | What |
|---------|------|------|
| s36 | Feb 26 | Tech debt mega-cleanup. 3 phases: (1) Deleted 8 legacy agents + 7 empty dirs, moved BrokerRouter→adapters/, InteractionManager→agents/workflow/. (2) Deleted ai_cotrader ML pipeline. (3) Killed recommendation service + screeners. Then: deleted analytics/ (empty), services/pricing/ (empty), 11 dead services, 3 harness-only service dirs, 4 harness steps, dead CLI/scripts. Moved workflow/→agents/workflow/. Fixed bare imports in risk_factors/resolver.py. services/ went from 35→16 files. 149 tests pass. |
| s35e | Feb 25 | MarketAnalyzer upgrade + research template retirement. New services: BlackSwan, Context, Screening, Ranking + 5 opportunity assessments. 8 new API endpoints. Frontend: BlackSwanBar + MarketContextStrip. Retired research templates. Rewrote Scout.run(). 166 tests. |
| s35d | Feb 23 | Math purge: moved 14 files to playground/archived_math/. Zero local math policy. 257 tests. |
| s35c | Feb 23 | Wired Maverick as domain orchestrator. Container-first trading dashboard. 296 tests. |
| s35b | Feb 23 | Built Steward + enhanced Sentinel with containers. 285 tests. |
| s35 | Feb 23 | Agent architecture reorganization. 5 domain agents in agents/domain/. 272 tests. |
