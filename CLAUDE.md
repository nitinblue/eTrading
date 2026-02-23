# CLAUDE.md
# Project: Trading CoTrader
# Last Updated: February 22, 2026 (session 33)
# Historical reference: CLAUDE_ARCHIVE.md (architecture decisions, session log s1-s26, file structure, tech stack)

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
A stateful, constrained decision-maker that chooses actions under uncertainty using a formal objective function.
🔹 Model Class 1: Regime Detection (Structural, not predictive)

### Feb 19, 2026 (Session 27) — THE PIVOT: One View, Real World
We have built a gazillion things over 26 sessions — 16 agents, 7 research templates, screeners, VaR, fitness checker, probability calculator, broker sync, 11 frontend pages, containers, workflow engine. **But none of it works end-to-end as a real trading tool.**

**New approach:**
- **Fresh start with `api_trading_sheet.py`** as the SINGLE entry point for all trading functionality
- Go through **1 feature at a time** — read existing code, plug it in properly
- 90% of what we need already exists. This is a **re-visualization**, not a rebuild
- The Trading Sheet IS the product. Everything else serves it
- Stop building new features. Make existing features WORK for real trading

**What "works" means:**
- I can see my real TastyTrade positions with accurate Greeks and P&L
- I can evaluate a research template and see which symbols trigger with full condition breakdown
- I can see the payoff (POP, EV, max profit/loss) for any proposed trade
- I can check if a trade fits my portfolio (delta, margin, VaR, concentration)
- I can add trades to WhatIf, toggle them, see impact, then book or execute
- Every piece of data is accurate, not zeros or placeholders

### Previous objectives (archived in CLAUDE_ARCHIVE.md)
- Sessions 1-26: Built full infrastructure — see CLAUDE_ARCHIVE.md for complete history
- Deploy 250K across multi-broker portfolios — IN PROGRESS
- Income generation primary, not alpha chasing
- Real capital deployment postponed until agent readiness demonstrated

---

## [NITIN OWNS] SESSION MANDATE

### Feb 19, 2026 (Session 27) — Fresh Start: Trading Sheet as Single Trading Hub
- `api_trading_sheet.py` is the starting point — rewrite/evolve it one feature at a time
- Each feature: READ existing backend service → PLUG into trading sheet API → VERIFY with real data
- Nitin will specify what to work on. Claude reads the existing code, wires it in
- Frontend (`TradingSheetPage.tsx`) evolves alongside the API

**Session history (s1-s26) moved to CLAUDE_ARCHIVE.md** — sessions 22-26 are most relevant:
- s22: Scenario templates, MarketDataContainer, TechnicalSnapshot, screeners
- s23: QuantResearchAgent, research portfolios, parameter variants
- s24: ConditionEvaluator, research_templates.yaml, template_loader
- s25: Full frontend, ContainerManager+broker sync fix in engine.py
- s26: Trading Sheet v1 (api_trading_sheet.py, probability wired, fitness checker)

---

## [NITIN OWNS] TODAY'S SURGICAL TASK

Session 27: Fresh start. Trading Sheet is the product. 1 feature at a time.
- Nitin directs which feature to plug in next
- Claude reads existing service code, wires into api_trading_sheet.py + TradingSheetPage.tsx
- Real data verification against TastyTrade positions in DB

---

## [CLAUDE OWNS] EXISTING INFRASTRUCTURE — Ready to Plug In

Everything below EXISTS in the codebase. The job now is to wire each into the Trading Sheet properly.

### Data Sources (what feeds the Trading Sheet)
| Source | Service/File | What It Provides | Wired? |
|--------|-------------|-----------------|--------|
| **Broker Positions** | `services/portfolio_sync.py`, `adapters/tastytrade_adapter.py` | Real positions from TastyTrade with live Greeks via DXLink | YES (engine.py boot+monitoring) |
| **Technical Indicators** | `services/technical_analysis_service.py` | TechnicalSnapshot: price, RSI, Bollinger, VWAP, ATR, IV rank, regimes, MAs, volume | YES (template eval) |
| **Research Container** | `containers/research_container.py`, `web/api_research.py` | Unified per-symbol research: technicals + HMM regime + fundamentals + macro + **phase + opportunities + smart money** (s33). Owns `config/market_watchlist.yaml`. DB-backed: instant cold start from `research_snapshots` table (111 cols), engine refreshes + persists during boot/monitoring | YES (API + UI + DB) |
| **Market Data Container** | `containers/market_data_container.py` | Cross-portfolio cached indicators, change tracking (legacy, superseded by ResearchContainer) | PARTIAL |
| **Research Templates** | `config/research_templates.yaml`, `services/research/template_loader.py` | 7 templates with entry/exit conditions, strategy config, parameter variants | YES (evaluate endpoint) |
| **Condition Evaluator** | `services/research/condition_evaluator.py` | 7 operators, reference comparisons, multipliers, AND/OR logic | YES (evaluate endpoint) |
| **Probability Calculator** | `services/pricing/probability.py` | POP, EV, max profit/loss, breakevens for multi-leg trades | YES (compute_trade_payoff) |
| **Portfolio Fitness** | `services/portfolio_fitness.py` | Delta/margin/VaR/concentration/position limit checks | YES (fitness check) |
| **VaR Calculator** | `services/risk/var_calculator.py`, `services/risk/correlation.py` | Parametric + historical VaR, incremental VaR, CVaR, per-underlying breakdown | NOT YET |
| **Black-Scholes** | `services/pricing/black_scholes.py`, `analytics/pricing/` | Greeks computation, theoretical pricing | NOT YET |
| **P&L Attribution** | `analytics/pricing/pnl_calculator.py` | Delta/gamma/theta/vega/unexplained P&L decomposition | NOT YET |
| **Portfolio Evaluation** | `services/portfolio_evaluation_service.py` | Exit rules: take profit, stop loss, DTE, delta breach, roll, adjust | NOT YET |
| **Screeners** | `services/screeners/` (7 screeners) | VIX regime, IV rank, LEAPS, correction, earnings, black swan, arbitrage | VIA TEMPLATES |
| **QuantResearchAgent** | `agents/analysis/quant_research.py` | Auto-evaluates templates, books into research portfolios | NOT YET |
| **Market Analyzer** | `market_analyzer` library (external, renamed from `market_regime`), 9 endpoints in `web/api_v2.py` | MarketAnalyzer facade: regime (R1-R4), technicals, phase (Wyckoff), opportunities (0DTE/LEAP/breakout/momentum), fundamentals, macro | YES (api_v2.py + ResearchDashboard UI) |
| **Macro Context** | `services/macro_context_service.py`, `config/daily_macro.yaml` | VIX regime, macro outlook, expected vol — gates all recommendations | NOT YET |
| **Earnings Calendar** | `services/earnings_calendar_service.py` | yfinance earnings dates, 24h cache | NOT YET |
| **Performance Metrics** | `services/performance_metrics_service.py` | Win rate, Sharpe, drawdown, expectancy, profit factor, CAGR | NOT YET |
| **Liquidity** | `services/liquidity_service.py` | OI, spread, volume thresholds — blocks illiquid trades | NOT YET |
| **Order Execution** | `adapters/tastytrade_adapter.py` (place_order, get_live_orders) | 2-step: preview → LIMIT order on TastyTrade | NOT YET |
| **Trade Booking** | `services/trade_booking_service.py` | Book WhatIf/paper/live trades with legs, Greeks, source tracking | PARTIAL |
| **Guardian Agent** | `agents/safety/guardian.py` | Circuit breakers (daily/weekly loss, VIX), trading constraints (max trades, time windows) | NOT YET |
| **Snapshots** | `services/snapshot_service.py` | Daily portfolio snapshots for historical analysis | NOT YET |
| **Containers** | `containers/container_manager.py`, `containers/portfolio_bundle.py` | Per-portfolio bundled position/trade/risk containers | YES (engine.py) |

### Supporting Infrastructure (already working)
| Area | Status |
|------|--------|
| **Workflow Engine** | 12-state machine, APScheduler, state persistence, decision logging — WORKING |
| **FastAPI Web Server** | Embedded in workflow engine via `--web` flag — WORKING |
| **React Frontend** | Vite + React 18 + TS + Tailwind + AG Grid + Recharts — WORKING |
| **SQLite DB** | 23 tables, ORM models, session_scope pattern — WORKING |
| **Broker Adapters** | TastyTrade (API), Fidelity (manual), Zerodha (API stub), Stallion (read-only) — WORKING |
| **270 unit tests** | All pass — WORKING |

---

## [CLAUDE OWNS] TRADING SHEET — Current State

**Central file: `trading_cotrader/web/api_trading_sheet.py`**

### Endpoints
| Method | Path | What It Does | Status |
|--------|------|-------------|--------|
| GET | `/api/v2/trading-sheet/{portfolio}` | Full trading view: portfolio summary, positions, WhatIf trades, risk factors | v1 DONE |
| POST | `/api/v2/trading-sheet/{portfolio}/evaluate` | Evaluate research template — per-symbol condition breakdown | v1 DONE |
| POST | `/api/v2/trading-sheet/{portfolio}/add-whatif` | Add proposed trade to WhatIf | v1 DONE |
| POST | `/api/v2/trading-sheet/{portfolio}/book` | Convert WhatIf to paper trade | v1 DONE |

### Market Analyzer Endpoints (in api_v2.py)
| Method | Path | What It Does | Status |
|--------|------|-------------|--------|
| GET | `/api/v2/regime/{ticker}` | Tier 1: regime label (R1-R4), confidence, trend, probabilities | DONE |
| POST | `/api/v2/regime/batch` | Tier 1 batch: multiple tickers `{"tickers": [...]}` | DONE |
| GET | `/api/v2/regime/{ticker}/research` | Tier 2: full research — transition matrix, features, history, strategy | DONE |
| POST | `/api/v2/regime/research` | Tier 2 batch: multi-ticker research + cross-comparison | DONE |
| GET | `/api/v2/phase/{ticker}` | Wyckoff phase detection (PhaseService) | DONE (s33) |
| GET | `/api/v2/opportunity/zero-dte/{ticker}` | 0DTE opportunity assessment (GO/CAUTION/NO_GO) | DONE (s33) |
| GET | `/api/v2/opportunity/leap/{ticker}` | LEAP opportunity assessment | DONE (s33) |
| GET | `/api/v2/opportunity/breakout/{ticker}` | Breakout opportunity assessment | DONE (s33) |
| GET | `/api/v2/opportunity/momentum/{ticker}` | Momentum opportunity assessment | DONE (s33) |

### What GET /trading-sheet returns today
```
portfolio:     name, equity, cash, buying_power, margin, Greeks (net + with WhatIf),
               VaR, theta/VaR ratio, delta utilization
positions:     per-position: symbol, type, strike, DTE, qty, entry/current Greeks,
               P&L total + attribution, delta drift, IV change
whatif_trades: per-trade: legs, payoff (POP, EV, max P/L, breakevens),
               Greeks, fitness check (passes/warnings)
risk_factors:  per-underlying: net Greeks, delta dollars, concentration %, P&L
```

### Known Issues in Current v1
- Entry Greeks on broker positions are zeros (not captured at open time)
- P&L attribution all zeros (needs P&L calculator wired)
- VaR is just reading portfolio ORM field (not computed fresh)
- VaR impact for WhatIf is crude linear approximation (needs real incremental VaR)
- `current_underlying_price` zeros on some positions (broker sync gap)
- Max profit/loss calculation from ProbabilityResult is hacky (reverse-engineering from EV)
- No position-level health metrics (% of max profit realized, breakeven distance)

### Frontend: `frontend/src/pages/TradingSheetPage.tsx`
5 sections: PortfolioSummary (KPI strip), PositionsSection (table), WhatIfSection (cards),
RiskFactorsSection (table), TemplateEvalSection (dropdown + condition breakdown)

---

## [CLAUDE OWNS] CURRENT BLOCKER

**No active blockers.** Nitin directs feature-by-feature.

---

## [CLAUDE OWNS] CODE MAP
<!-- Maps functionality to files. -->

| Area | Key files |
|------|-----------|
| **Research Container** | `containers/research_container.py` (ResearchEntry + MacroContext + DB bridge), `web/api_research.py` (3 endpoints), `repositories/research_snapshot.py` (DB persistence) |
| **Research Frontend** | `frontend/src/pages/ResearchDashboardPage.tsx` (default "/" page), `frontend/src/hooks/useResearch.ts` |
| **Trading Sheet API** | `web/api_trading_sheet.py` (4 endpoints — THE CENTRAL FILE) |
| **Trading Sheet Frontend** | `frontend/src/pages/TradingSheetPage.tsx`, `frontend/src/hooks/useTradingSheet.ts` |
| **Portfolio Fitness** | `services/portfolio_fitness.py` (PortfolioFitnessChecker) |
| **Workflow Engine** | `workflow/engine.py` (orchestrator + ContainerManager + broker sync), `workflow/states.py`, `workflow/scheduler.py`, `runners/run_workflow.py` |
| **Agents (5 active)** | `agents/base.py` (BaseAgent ABC), `agents/protocol.py` (AgentResult). Active: `safety/guardian.py` (GuardianAgent/circuit_breaker), `analysis/risk.py` (RiskAgent), `analysis/quant_research.py` (QuantResearchAgent — exemplar, owns ResearchContainer), `infrastructure/tech_architect.py` (TechArchitectAgent skeleton), `learning/trade_discipline.py` (TradeDisciplineAgent skeleton). **11 legacy agent files still imported by engine.py — see CLEANUP below** |
| **Safety** | `agents/safety/guardian.py`, `config/workflow_rules.yaml` |
| **Broker Adapters** | `adapters/base.py` (ABC), `adapters/factory.py`, `adapters/tastytrade_adapter.py` |
| **Containers** | `containers/container_manager.py`, `containers/portfolio_bundle.py`, `containers/market_data_container.py` |
| **Pricing** | `services/pricing/probability.py` (POP/EV), `services/pricing/black_scholes.py`, `analytics/pricing/pnl_calculator.py` |
| **Risk** | `services/risk/var_calculator.py`, `services/risk/correlation.py` |
| **Research** | `config/research_templates.yaml` (7 templates), `services/research/template_loader.py`, `services/research/condition_evaluator.py` |
| **Screeners** | `services/screeners/` (7 screeners), `services/recommendation_service.py` |
| **Technical Analysis** | `services/technical_analysis_service.py` (TechnicalSnapshot) |
| **Portfolio Eval** | `services/portfolio_evaluation_service.py`, `services/position_mgmt/rules_engine.py` |
| **Performance** | `services/performance_metrics_service.py` |
| **Trade Booking** | `services/trade_booking_service.py` |
| **Broker Sync** | `services/portfolio_sync.py`, `services/position_sync.py` |
| **DB/ORM** | `core/database/schema.py` (23 tables), `core/database/session.py`, `repositories/` |
| **Market Analyzer** | External lib `market_analyzer` (editable install from `../market_analyzer`, renamed from `market_regime` s33). MarketAnalyzer facade in `web/api_v2.py` (9 endpoints: regime, phase, opportunities). QuantResearchAgent uses facade for populate(). Frontend endpoints in `frontend/src/api/endpoints.ts` |
| **Agent Intelligence** | `services/agent_brain.py` (AgentBrain — LLM via Claude API), 4 endpoints in `web/api_v2.py` (agent section), `frontend/src/hooks/useAgentBrain.ts` |
| **Web Server** | `web/approval_api.py` (FastAPI factory), `web/api_v2.py`, `web/api_admin.py`, `web/api_reports.py`, `web/api_explorer.py`, `web/api_agents.py` |
| **Config** | `config/risk_config.yaml` (15 portfolios), `config/brokers.yaml` (4 brokers), `config/workflow_rules.yaml`, `config/research_templates.yaml` |
| **Frontend** | `frontend/` (Vite + React 18 + TS + Tailwind + AG Grid + Recharts), 11 pages + 4 settings |
| **Tests** | `tests/` (270 pytest), `harness/` (17 integration steps) |

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
- Schema change: ORM in `schema.py` → domain in `domain.py` → `setup_database.py`

### ZERO DEAD CODE POLICY (Nitin mandate, s31)
- **NEVER create code that is not immediately used end-to-end.** Every file, class, function must be imported and called by something that runs.
- **NEVER create placeholder/stub agents, services, or files** "for future use." Build it when it's needed, not before.
- **Before creating a new file:** Verify it will be imported and used. If not, don't create it.
- **Before deleting functionality from UI:** Delete the corresponding backend code too. UI-only consolidation is cosmetic debt.
- **Agent = decision authority.** If it doesn't make autonomous decisions, it's a service, not an agent. Services live in `services/`, agents live in `agents/`.
- **Metadata lives WITH the code.** Agent descriptions, icons, boundaries belong in the agent class, not in a separate web file.
- **After every change:** Run `pytest` + `pnpm build`. If imports break, fix them immediately — don't leave orphans.

---

## [CLAUDE OWNS] DEV COMMANDS

```bash
# Core
python -m trading_cotrader.scripts.setup_database
pytest trading_cotrader/tests/ -v                        # 270 unit tests

# Workflow engine + web (THE MAIN WAY TO RUN)
python -m trading_cotrader.runners.run_workflow --paper --web                 # with broker
python -m trading_cotrader.runners.run_workflow --paper --no-broker --web     # without broker
python -m trading_cotrader.runners.run_workflow --once --no-broker --mock     # single cycle test

# React frontend
cd frontend && pnpm dev                                  # dev server at localhost:5173
cd frontend && pnpm build                                # production build

# Screeners (CLI — still work independently)
python -m trading_cotrader.cli.run_screener --screener all --symbols SPY,QQQ --no-broker

# Harness
python -m trading_cotrader.harness.runner --skip-sync
```

### Critical runtime notes
- Greeks come from DXLink streaming, NOT REST API
- Always test with `IS_PAPER_TRADING=true` before live
- Never store credentials in code — use `.env`
- **Harness vs Engine rule (learned s25):** Every feature working in harness MUST be verified in workflow engine + API

---

## [CLAUDE OWNS] AGENT FRAMEWORK REFACTOR — Status (s32-33)

**Done (s32):**
- `agents/base.py` — BaseAgent ABC with `populate()`, `run()`, `analyze()`, `safety_check()`, `get_metadata()` classmethod
- QuantResearchAgent — exemplar: extends BaseAgent, owns ResearchContainer, has `populate()` that replaces `_populate_research_container()` from api_research.py, `_ResearchEntryAdapter` for ConditionEvaluator compatibility
- GuardianAgent, RiskAgent — extend BaseAgent with class-level metadata
- TechArchitectAgent (skeleton), TradeDisciplineAgent (skeleton) — extend BaseAgent
- `api_agents.py` — `_build_registry(engine)` reads metadata dynamically from agent classes, fallback to static AGENT_REGISTRY
- `api_research.py` — delegates populate calls to `engine.quant_research.populate()` instead of old utility function
- `engine.py` — passes ResearchContainer to QuantResearchAgent, calls `agent.populate()` instead of `_refresh_research_container()`, deletes `_refresh_research_container()` method

**Still TODO (legacy agents in engine.py):**
Engine still imports and calls 11 legacy agents that aren't BaseAgent subclasses yet. They're called in state handlers (booting, screening, execution, reporting). To fully delete them, their logic must be absorbed into the 5 core agents or converted to standalone services called by those agents.

### Files still to absorb into core agents:
| Legacy File | Used By | Absorb Into |
|-------------|---------|-------------|
| `perception/market_data.py` | booting, monitoring | quant_research.populate() or service |
| `perception/portfolio_state.py` | booting, monitoring, execution | risk agent |
| `perception/calendar.py` | booting | service call in engine |
| `analysis/macro.py` | macro_check | service call in engine |
| `analysis/screener.py` | screening | quant_research |
| `analysis/evaluator.py` | trade_management, eod | risk agent |
| `analysis/capital.py` | booting, monitoring | risk agent |
| `execution/executor.py` | execution | tech_architect |
| `execution/notifier.py` | various | tech_architect |
| `execution/reporter.py` | reporting | tech_architect |
| `learning/accountability.py` | reporting | trade_discipline |
| `learning/session_objectives.py` | booting, reporting | trade_discipline |
| `learning/qa_agent.py` | reporting | tech_architect |

### Final 5 agents:
| ID | Class | File | Category | Status |
|----|-------|------|----------|--------|
| circuit_breaker | GuardianAgent | `agents/safety/guardian.py` | safety | BaseAgent (s32) |
| risk | RiskAgent | `agents/analysis/risk.py` | domain | BaseAgent (s32) |
| quant_research | QuantResearchAgent | `agents/analysis/quant_research.py` | domain | BaseAgent + populate() (s32) |
| tech_architect | TechArchitectAgent | `agents/infrastructure/tech_architect.py` | infrastructure | Skeleton (s32) |
| trade_discipline | TradeDisciplineAgent | `agents/learning/trade_discipline.py` | learning | Skeleton (s32) |

---

## [CLAUDE OWNS] OPEN ITEMS

### Agent Intelligence (Dashboard) — Unfinished
1. 3 AgentBrain methods have no API endpoints: `explain_recommendation()`, `generate_accountability_message()`, `generate_self_assessment()`
2. Position analysis endpoint (`/agent/analyze/{symbol}`) exists but no UI trigger
3. Chat is stateless — no conversation history across messages
4. Data source gap — brief uses raw broker adapter data, not processed container data with corrected P&L/risk
5. Requires `ANTHROPIC_API_KEY` in `.env` to function

### Market Analyzer — Full Integration Done (s33)
- `market_regime` renamed to `market_analyzer` with MarketAnalyzer facade
- 9 endpoints in `api_v2.py` (regime + phase + 4 opportunities)
- ResearchContainer stores ~30 new fields (phase, smart money, opportunities)
- ResearchDashboard UI: Opportunities + Smart Money column groups with verdict badges
- QuantResearchAgent uses MarketAnalyzer facade for populate()

## [CLAUDE OWNS] OPEN QUESTIONS

(None currently)
