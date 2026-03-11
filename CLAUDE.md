# CLAUDE.md — Trading CoTrader
# Last Updated: March 11, 2026 (session 39)

## PRIME DIRECTIVE

**We are building a money-making machine, not a tech project.**

$250K capital ($50K personal, $200K self-directed IRA). Goal: deploy systematically to fund Nitin's daughter's college education through options trading.

### Non-Negotiable Rules

1. **Never book a bogus trade.** Every trade must come from the full pipeline with real market data. No mock data, no fabricated positions, no "just to test" entries.
2. **Never take action for the sake of taking action.** Every action requires 90%+ confidence based on data lineage. If confidence is below threshold, call out the gap — don't work around it.
3. **No mocked data in production flow.** Everything must be tradeable. If data isn't available, say so.
4. **Every event is data.** Log everything as events. No data gets wasted — it feeds ML/RL. The system must become intelligent over time.
5. **Measure progress by: can Maverick execute a real trade today?** Not lines of code. Not test count.

### Accountability Model

**Agents own their WhatIf desk P&L — fully, no excuses.**
- Each agent's desk has a WhatIf portfolio. The agent is 100% accountable for its performance: win rate, P&L, Sharpe, drawdown.
- Agents scan, propose, book, monitor, and close trades in their WhatIf portfolios autonomously.
- On cloud (SaaS), agent desk performance is the product's track record. There will be no excuses — the numbers speak.

**Agents never touch real portfolio P&L.**
- Humans decide what to promote from WhatIf → real execution.
- The human bears full responsibility for actual capital deployment.
- The system's job is to make the WhatIf track record so compelling that promotion is obvious.

### Before Every Session
- Ask: **"Does this move us closer to real trades with real money?"**
- If asked for UI/cleanup/refactoring — do it, but state what's blocking the first trade.
- Review `GAPS.md` — the standing gap analysis.
- Force reinstall: `pip install --force-reinstall --no-deps -e ../market_analyzer`
- Update CLAUDE.md and MEMORY.md after major changes.

---

## ARCHITECTURE — How Money Gets Made

```
Market Data (TastyTrade DXLink) → Scout (screen + rank) → Maverick (6 gates + sizing)
  → WhatIf Portfolio (paper) → Human Review → Real Order (TastyTrade API)
  → Exit Monitor → Close Order → P&L → ML/RL Learning Loop
```

### The Pipeline (scan → propose → deploy → execute)

| Step | What | Status |
|------|------|--------|
| `scan` | Scout screens watchlist, ranks candidates, Maverick applies 6 gates | DONE |
| `propose` | Show scored proposals with trade specs | DONE |
| `deploy` | Book approved trades to WhatIf portfolio | DONE |
| `execute <id>` | Dry-run preflight (buying power, fees, risk) | DONE |
| `execute <id> --confirm` | Place real order on TastyTrade | DONE |
| `orders` | Check fill status, auto-update trade on fill | DONE |
| `exits` | Monitor profit targets, stop losses, DTE | DONE |
| `close <id>` | Close specific trade (DB + event + outcome) | DONE |
| `close auto` | Auto-close all URGENT + profit target signals | DONE |
| `learn` | Feed outcomes to ML/RL pattern recognition | DONE |

### Maverick's 6 Gates (every trade must pass ALL)
1. **Verdict** — MarketAnalyzer says GO or CAUTION (not NO_GO)
2. **Score** — Composite score ≥ 0.35
3. **Trade spec** — Valid legs, strikes, expiration exist
4. **Duplicate** — Not already in portfolio (underlying:strategy key)
5. **Position limit** — Under desk max positions
6. **ML score** — Pattern recognition doesn't flag negative (when data exists)

### Trading Desks (capital allocation)
| Desk | Capital | DTE | Underlyings | Exit Rules |
|------|---------|-----|-------------|------------|
| desk_0dte | $10K | 0 DTE | SPY, QQQ, IWM | No stop (defined risk), 90% TP |
| desk_medium | $10K | ~45 DTE | Top 10 | 50% TP, 2× credit SL, close ≤21 DTE |
| desk_leaps | $20K | 180+ DTE | Blue chips | 100% TP, 50% SL |

### Credential Flow (SaaS Pattern)
eTrading authenticates with TastyTrade → passes pre-authenticated sessions to MarketAnalyzer.
MarketAnalyzer never touches credentials. Single connection reused everywhere.
```
TastytradeAdapter.authenticate() → session + data_session
  → adapter.get_market_providers() → (MarketDataProvider, MarketMetricsProvider)
  → injected into Scout → MarketAnalyzer(market_data=..., market_metrics=...)
  → also available to API endpoints via engine._market_data/_market_metrics
```

---

## AGENTS

| Agent | Role | Status |
|-------|------|--------|
| **Scout** (Quant) | Screen, rank, regime, technicals, opportunities | DONE |
| **Steward** (Portfolio Mgr) | Portfolio state, positions, P&L, capital | DONE |
| **Sentinel** (Risk Mgr) | Circuit breakers, constraints, risk limits | DONE |
| **Maverick** (Trader) | THE workflow agent — orchestrates everything | WIRED (no order execution yet) |
| **Atlas** (Tech Architect) | Infrastructure | Skeleton — not prioritized |

**Pattern:** Agent owns Container → populate() fills from data → save_to_db() → API reads → UI renders

**Engine pipeline** (BOOTING + MONITORING states):
Steward.populate → Sentinel.run → Steward.run → Scout.populate → Scout.run → Maverick.run

---

## EVENT & LEARNING SYSTEM

Every action creates a `TradeEvent` with full context:
- **MarketContext**: VIX, IV rank, regime, technicals, macro
- **DecisionContext**: rationale, confidence (1-10), outlook, alternatives considered
- **TradeOutcomeData**: WIN/LOSS, P&L, close reason, Greeks attribution

**Learning loop:** TradeLearner (Q-learning) reads closed trade events → builds patterns (regime:iv:strategy:dte:side) → scores future trades → feeds back into Maverick gate 6.

**Confidence framework** (to build): Every event gets a confidence level based on data lineage. Over time, reports identify habitual vs merit-based actions.

---

## KEY FILES

```
runners/run_workflow.py          # THE entry point
agents/workflow/engine.py        # 12-state orchestrator
agents/domain/maverick.py        # Trader (6 gates, proposals, booking, sizing)
agents/domain/scout.py           # Quant (screening, ranking)
agents/domain/steward.py         # Portfolio manager
agents/domain/sentinel.py        # Risk manager
adapters/tastytrade_adapter.py   # Broker (40+ methods, SaaS credential pattern)
services/trade_booking_service.py # Book trades with legs + Greeks
services/trade_lifecycle.py      # Close trades, record outcomes
services/exit_monitor.py         # Profit target, stop loss, DTE exit
services/mark_to_market.py       # Update P&L from live quotes
services/trade_learner.py        # ML/RL pattern recognition
core/models/events.py            # TradeEvent, DecisionContext, MarketContext
repositories/event.py            # Event persistence + queries
config/risk_config.yaml          # 15 portfolios, 3 desks
config/workflow_rules.yaml       # Circuit breakers, limits
```

---

## CODING STANDARDS

- `Decimal` for ALL money/price values. Never float.
- Type hints on every function. `dataclass` for domain models.
- `session_scope()` for DB. No raw sessions.
- ALL imports at file top (unless circular avoidance).
- Agent files = NOUNS. Service files = VERBS.
- **ZERO dead code.** Every file/class/function must be called. No stubs.
- **ZERO local math.** Greeks/prices from broker only. No Black-Scholes, POP/EV, VaR.
- **ZERO bogus data.** No mock trades in production flow. No fabricated positions.

---

## DEV COMMANDS

```bash
pip install --force-reinstall --no-deps -e ../market_analyzer
pytest trading_cotrader/tests/ -v
python -m trading_cotrader.runners.run_workflow --paper --web          # with broker
python -m trading_cotrader.runners.run_workflow --once --no-broker --mock  # single cycle
cd frontend && pnpm dev                                                # React :5173
cd frontend && pnpm build                                              # production build
```

---

## UI (8 pages)

| Route | Page | Tabs |
|-------|------|------|
| `/` | Research Dashboard | Landing — Scout data, daily plan, screener |
| `/trading` | Trading Dashboard | Positions, WhatIf, risk |
| `/portfolio` | Portfolio | Positions, Performance, Capital |
| `/risk` | Risk | Risk dashboard |
| `/agents` | Agents | Workflow, Active Agents, Quant, Knowledge, ML/RL |
| `/reports` | Reports | Portfolio reports |
| `/data` | Data Explorer | Query builder |
| `/settings` | Config | Portfolios, Risk, Workflow, Capital (tabbed) |

---

## SAAS VISION

This system will become a cloud-hosted SaaS product. Design every feature with multi-tenancy in mind.

**Architecture direction:**
- **User authentication** — OAuth/SSO. Multiple users per account (family, advisor+client).
- **Desk setup** — First-time user onboarding: create desks, allocate capital, select underlyings. Desks are the core organizational unit regardless of portfolio/broker.
- **Broker integration** — SaaS pattern already implemented: credentials stay with eTrading, MarketAnalyzer gets pre-authenticated sessions. Each user connects their own broker account.
- **Cloud hosting** — Deploy to cloud (AWS/GCP). DB → PostgreSQL. Async task queue for agent pipeline. WebSocket for real-time updates.
- **Multi-tenancy** — Tenant isolation at DB level. Each user's agents, desks, portfolios, events, ML models are scoped to their account.

**What's already SaaS-ready:**
- Credential separation (SaaS pattern for MarketAnalyzer)
- Desk abstraction (capital buckets independent of broker)
- Event system (per-trade audit trail)
- ML/RL learning loop (per-user pattern recognition)

**What needs work for SaaS:**
- User model + auth (currently single-user)
- Tenant-scoped DB queries
- API rate limiting + quotas
- Cloud deployment (Docker, K8s)
- Admin dashboard for user management

---

## OPEN GAPS (see GAPS.md for full detail)

**The full pipeline is BUILT:** scan → propose → deploy → execute → mark → exits → close auto → learn.
No gaps in the trading flow itself. What remains:

1. **End-to-end validation with live broker** — run the full pipeline with real market data, real broker connection. Prove it works.
2. **Confidence framework** — Assign confidence levels to events, track data lineage, report habitual vs merit-based actions.
3. **SaaS: user model + auth + multi-tenancy** — no user table, no login, no tenant scoping.
4. **SaaS: desk onboarding UI** — `setup-desks` is CLI only, needs wizard for new users.
5. **SPX ticker handling** — SPX fails on yfinance (it's an index). Use SPY or handle gracefully.

---

## SESSION LOG

| Session | Date | Key Outcome |
|---------|------|-------------|
| s39 | Mar 11 | Fixed ranking bug (.ranked→.top_trades). CLAUDE.md rewritten ("money-making machine"). Corrected stale GAPS (pipeline fully built, no blockers). MarketAnalyzer REQ-1→5: dxlink_symbols, position_size(), exit_plan field, IntradayService for 0DTE. 168+940 tests. |
| s38 | Mar 10 | UI consolidation (6 pages→3 via tabs). Desk-aware daily plan. SaaS credential refactoring. Stallion deletion. |
| s37b | Mar 9 | Trading desks + full lifecycle. 3 desks, CLI: close/perf/learn. Auto-booking. 170 tests. |
| s37 | Mar 9 | Full trading workflow. Maverick 5 gates + proposals + booking + sizing. 163 tests. |
| s36 | Feb 26 | Tech debt mega-cleanup. Deleted legacy agents, dead services. 149 tests. |
