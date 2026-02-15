# CLAUDE.md
# Project: Trading CoTrader
# Last Updated: February 15, 2026 (session 5)

---

## [NITIN OWNS] WHY THIS EXISTS
<!--
  RULE: Add new entries at TOP with date. Never delete anything below.
  History of how your thinking evolved lives here permanently.
-->

### Feb 14, 2026
20 years pricing and risk analytics on institutional trading floors — IR, commodities, FX, mortgages.
Nitin understands how top-end platforms work and that trading is fundamentally about risk management
first, staying invested through cycles second.

The gap: that institutional discipline has never been applied to personal wealth. 250K sits idle
(50K personal, 200K self-directed IRA) while college tuition for two daughters and other obligations
approach.

This tool exists to close that gap — not by chasing returns, but by deploying capital systematically,
safely, and with full risk visibility at every level: trade, strategy, portfolio.

The secondary objective: build this right and it becomes a product for a small group of people who
think the same way. Not mass market. High conviction, high discipline users only.

The mental model is always: Macro Context → My Exposure → Action Required.
Never: "I have an iron condor." Always: "I have -150 SPY delta, +$450 theta/day. Am I within limits?"

---

## [NITIN OWNS] BUSINESS OBJECTIVES
<!--
  RULE: Add new entries at TOP with date. Never delete or overwrite prior entries.
  Change a status by adding a new dated row at top, not by editing old rows.
-->

### Feb 15, 2026

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

Status options: NOT STARTED → IN PROGRESS → USER CAN NOW DO THIS

---

## [NITIN OWNS] SESSION MANDATE
<!--
  RULE: Add new entries at TOP with date. Never delete prior entries.
  History of what you were focused on each day lives here permanently.
-->

### Feb 15, 2026
Objective:
1. my 250K is in 2 accounts but here we will have, but we will have concept of dividing this into multiple portfolios with different timehorizon and risk profile. Please create portfolio for a. high risk (choose a better name, generally short term options) - allocate 10K (this will be real allocation), b. medium risk, allocate 20K medium term trades... c. Core holdings, wehre long term stocks but sometimes i wheel the stocks, or do covered calls... d. will be completely hypothetical model portfolio, where i will do trades that i know will win, will capture the comments, i will also do trades i know will lose, will capture comments, and this should serve as training data for AI/ML
2. Develop Portfolio performance metrics , slice and dice by strategy type, by week, metrics to produce: equity curve, avg win, avg loss, win rate, expected value per trade, are we going to use the event log data to define the scope and values comes from sql lite table where we have snapshot ?? I am just wandering, see how do we define this.. lets stick with writting APIs and showing result in terminal, print using tabulate...You have already build what if trade, for 18 strategies, book bunch of what if trade and prepare a Model portfolio... 
Done looks like: User can _______________ Strong feedback loop for AI/ML database to write models on how to keep optimizing daily profit based on the portfolio results...
Not touching today: UI

---

## [NITIN OWNS] TODAY'S SURGICAL TASK
<!--
  RULE: OVERWRITE COMPLETELY every session. No dates. No history.
  This is a directive, not a record. 5 lines max.
  Write this in claude.ai BEFORE opening Claude Code.
-->

FILE: 
OBJECTIVE: 
COMMAND TO RUN: 
---

## [CLAUDE OWNS] WHAT USER CAN DO TODAY
<!-- Claude updates this at end of every session. Written as user actions only. -->

- User can authenticate with TastyTrade broker and maintain a live session
- User can sync portfolio and pull live positions with current market prices and Greeks
- User can create a WhatIf trade (identical object to a real trade, just flagged as WHAT_IF)
- User can book a WhatIf trade end-to-end via `TradeBookingService` with live DXLink Greeks/quotes → DB → containers → snapshot → ML
- User can book any of 12 strategy types as WhatIf trades (single, vertical, iron condor, iron butterfly, straddle, strangle, butterfly, condor, jade lizard, big lizard, ratio spread, calendar spread)
- User can look up strategy templates (risk category, bias, theta/vega profile, exit rules) via `strategy_templates.py`
- User can run the test harness (`python -m harness.runner`) — steps 1-14 defined (12 books a single trade, 13 books all 12 testable strategies, 14 initializes multi-tier portfolios + performance metrics)
- User can initialize 4 risk-tiered portfolios from YAML config (Core Holdings $200K, Medium Risk $20K, High Risk $10K, Model Portfolio $25K) via `PortfolioManager`
- User can view performance metrics per portfolio (win rate, P&L, profit factor, expectancy, max drawdown, Sharpe, CAGR) via `PerformanceMetricsService`
- User can see strategy permissions matrix — which strategies are allowed in which portfolio tier
- User can route WhatIf trades to specific portfolios via `portfolio_name` parameter in `TradeBookingService`
- User can log events against trades via CLI
- User can start the grid server (`python -m trading_cotrader.runners.run_grid_server`) and view positions in browser

**Blocked / Not Yet Working:**
- `is_open` property vs field mismatch in `repositories/trade.py` — breaks trade persistence round-trips
- WhatIf end-to-end lifecycle (intent → evaluate → execute → close) not yet validated
- 6 strategies not yet testable via harness: covered call, protective put, collar (need equity legs), diagonal, calendar double (need two expirations), custom (no fixed structure)
- UI exists as HTML/JSX prototypes (`ui/`) but is not a production React app yet

---

## [CLAUDE OWNS] ARCHITECTURE DECISIONS
<!-- Append only. Never delete. Add new decisions at the bottom with a date. -->

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
- DECISION: `harness/` provides a step-based integration test framework (steps 01-14) with rich terminal output. The harness tests the full vertical slice: imports → broker → portfolio → market data → risk → hedging → trades → events → ML status → containers → trade booking → strategy templates → portfolio tiers + performance metrics. pytest reserved for unit tests (not yet written).
- CONSTRAINT THAT FORCED IT: Integration testing across broker + DB + domain requires ordered steps with shared state. pytest fixtures don't naturally model this.
- OBJECTIVE IT SERVES: All objectives (validates the entire stack works end-to-end)

### Decision 12: Multi-Tier Portfolios from YAML Config (Feb 15, 2026)
- DECISION: Portfolios are defined in `config/risk_config.yaml` with capital allocations, allowed strategies, risk limits, and exit rule profiles. `PortfolioManager` creates them in DB using `broker='cotrader'` + `account_id=<config_name>` to reuse the existing unique constraint. No schema changes needed.
- CONSTRAINT THAT FORCED IT: User needs 4 risk tiers (Core/Med/High/Model) with different strategy permissions and capital allocations. Config must be easily adjustable without code changes.
- REJECTED APPROACH: Hardcoded portfolio definitions in code — rejected because allocation amounts and strategy permissions change as user's portfolio evolves.
- OBJECTIVE IT SERVES: #1, #3, #7, #8

---

## [CLAUDE OWNS] CODE MAP
<!-- Maps code to business objectives. What exists in code that serves each objective. -->

| Objective # | What exists in code today |
|-------------|--------------------------|
| 1 (Deploy 250K) | `config/risk_config.yaml` — 4 portfolio tiers defined (Core $200K, Medium $20K, High $10K, Model $25K). `config/risk_config_loader.py` — risk + portfolio config loading with `PortfolioConfig`, `PortfoliosConfig` dataclasses. `services/portfolio_manager.py` — initializes portfolios from YAML, validates allocations, routes trades. `core/database/schema.py` — portfolio_type, per-portfolio risk limits in ORM. |
| 2 (Income generation) | `analytics/pricing/option_pricer.py` — Black-Scholes. `analytics/greeks/engine.py` — Greeks. `analytics/pricing/pnl_calculator.py` — P&L. `services/pricing/` — additional BS, greeks, implied vol, probability, scenarios. |
| 3 (80/20 risk book) | `services/risk/limits.py` — risk limits manager. `services/risk/portfolio_risk.py` — portfolio risk analyzer. `core/models/domain.py` — `PortfolioType` enum, `RiskCategory` on trades. `services/risk_manager.py` — top-level risk orchestration. `config/risk_config.yaml` — per-portfolio strategy permissions (Core=5, Med=10, High=10, Model=17 allowed strategies). `services/portfolio_manager.py` — validates strategy-to-portfolio routing. |
| 4 (Wheel strategy / CSP) | Domain objects support all trade types. `core/models/strategy_templates.py` — 18 strategy templates with risk/bias/Greeks profiles. `services/trade_booking_service.py` — end-to-end WhatIf booking with live Greeks. No strategy-specific automation yet — this is a gap. |
| 5 (Every decision logged) | `services/event_logger.py` — event logging service. `core/models/events.py` — event sourcing models. `repositories/event.py` — event repository. `cli/log_event.py` — CLI interface. `services/trade_booking_service.py` — auto-logs TradeEvent on every WhatIf booking. |
| 6 (System surfaces insights) | `ai_cotrader/` — structure exists. Feature extraction and RL agents stubbed. NOT YET WIRED TO LIVE DATA. |
| 7 (Risk limits enforced) | `services/risk/var_calculator.py` — VaR. `services/risk/correlation.py`. `services/risk/concentration.py`. `services/risk/margin.py`. `services/risk/limits.py`. `services/position_mgmt/rules_engine.py` — exit rules. `services/risk_factors/` — risk factor resolution. `services/hedging/hedge_calculator.py` — hedge recommendations. |
| 8 (AI/ML / RL) | `ai_cotrader/feature_engineering/feature_extractor.py` — 55-dimension state vectors. `ai_cotrader/learning/supervised.py` — pattern recognition (Decision Tree). `ai_cotrader/learning/reinforcement.py` — Q-Learning + DQN. `RewardFunction` defined. `services/performance_metrics_service.py` — OptionsKit-style metrics (win rate, CAGR, Sharpe, drawdown, expectancy, strategy breakdown, weekly P&L). Model Portfolio in `risk_config.yaml` requires rationale on every trade for training data. NEEDS DATA — usable after 500+ logged trades. |

---

## [CLAUDE OWNS] CURRENT BLOCKER
<!-- What is actively broken right now. Claude updates this every session. -->

**Blocker:** `is_open` property vs field mismatch in `repositories/trade.py`
**Impact:** Trade persistence round-trips break — the repo tries to read/write `is_open` as a stored DB field, but the domain model defines it as a computed property from `trade_status`.
**Fix:** `is_open` must be computed from `trade_status`, never read from DB as a stored field. Remove all `is_open` field access in `repositories/trade.py`.
**File to fix:** `repositories/trade.py` (lines ~58-65, ~273-275, ~451-453)
**Test command after fix:** `python -m harness.runner --skip-sync`

---

## [CLAUDE OWNS] SESSION LOG
<!--
  RULE: Claude appends one entry at TOP after every session. Never deletes.
  This is the permanent record of what got done.
-->

### Feb 15, 2026 (session 5)
- BUILT: `config/risk_config.yaml` — 4 portfolio tiers (Core Holdings $200K, Medium Risk $20K, High Risk $10K, Model Portfolio $25K) with allowed strategies, risk limits, exit rule profiles, preferred underlyings
- BUILT: `services/portfolio_manager.py` — initializes portfolios from YAML, validates allocations <=100%, routes trades, enforces strategy permissions
- BUILT: `services/performance_metrics_service.py` — OptionsKit-style metrics: win rate, P&L, profit factor, expectancy, avg/biggest win/loss, max drawdown, CAGR, Sharpe, MAR ratio, strategy breakdown, weekly P&L
- BUILT: `harness/steps/step14_portfolio_performance.py` — prints 4 tables: YAML config, DB portfolios, performance metrics, strategy permissions matrix
- EXTENDED: `config/risk_config_loader.py` — added `PortfolioConfig`, `PortfoliosConfig`, `ExitRuleProfile`, `PortfolioRiskLimits` dataclasses + parsing
- EXTENDED: `repositories/portfolio.py` — added `get_by_type()`, `get_by_account_id()`; fixed `to_domain()` and `create_from_domain()` to round-trip `initial_capital`, `portfolio_type`, `description`, `tags`, `max_portfolio_delta`, risk limits
- EXTENDED: `services/trade_booking_service.py` — added `portfolio_name` parameter to `book_whatif_trade()` for portfolio-specific routing + strategy validation
- EXTENDED: `harness/runner.py` — registered step 14
- VERIFIED: All 4 portfolios create correctly, step 14 passes in 86ms
- NEXT: Book WhatIf trades into specific portfolios, populate performance metrics with real trade data

### Feb 14, 2026 (session 4)
- BUILT: `harness/steps/step13_strategy_templates.py` — books WhatIf trades for all 12 testable pure-option strategies with live DXLink Greeks
- UPDATED: `harness/runner.py` — added StrategyTemplateStep as step 13
- STRATEGIES TESTED: single, vertical_spread, iron_condor, iron_butterfly, straddle, strangle, butterfly, condor, jade_lizard, big_lizard, ratio_spread, calendar_spread
- SKIPPED: covered_call, protective_put, collar (equity legs), diagonal, calendar_double (two expirations), custom (no structure)
- NEXT: Fix is_open bug in repositories/trade.py, run full harness with broker to validate all 13 steps

### Feb 14, 2026 (session 2)
- AUDITED: CLAUDE.md against actual codebase — found major discrepancies
- FIXED: File structure, dev commands, code map, blocker section — all now match real code
- KEY FINDINGS: runners/ only has run_grid_server.py; harness/ is the real test framework; frontend/ doesn't exist (it's ui/); config/risk_config.yaml is missing; containers/ and server/ were undocumented
- NEXT: Fix is_open bug in repositories/trade.py, get harness steps passing

### Feb 14, 2026
- SYNTHESIZED: All prior docs (ARCHITECTURE_28Jan26, PROJECT_MASTER, PROJECT_STATUS_SESSION_JAN26) into CLAUDE.md
- ESTABLISHED: Ownership rules, session pattern, surgical task pattern
- NEXT: Fix is_open bug in repositories/trade.py, get debug_autotrader steps 1-13 passing

---

## [CLAUDE OWNS] OPEN QUESTIONS
<!-- Things that need Nitin's decision before code proceeds. -->

| # | Question | Context | Decision |
|---|----------|---------|----------|
| 1 | What VaR confidence level matters to you? | Risk limits module is built, defaults to 95%. Needs your threshold | TBD |
| 2 | Max portfolio VaR tolerance as % of equity? | Same — needs your number to enforce | TBD |
| 3 | Concentration limit per underlying? | Defaulted to 10% (Core), 30% (Med), 40% (High) in YAML — correct? | TBD |
| 4 | Preferred exit rules? | Defaults set in YAML: conservative (50% profit, 21 DTE roll), balanced (65%, 14 DTE), aggressive (80%, 7 DTE) — adjust? | TBD |
| 5 | Is paper trading in scope before live trading? | Affects whether to add a paper portfolio type first | TBD |
| 6 | Should playground/ scripts be promoted to runners/? | Currently sync_portfolio, portfolio_analyzer etc. live in playground/, not runners/ | TBD |

---

## [CLAUDE OWNS] CODING STANDARDS
<!-- Claude reads this before writing any code. Never asks about these. -->

### Non-negotiables
- `Decimal` for ALL money/price values. Never float.
- `UUID` strings for all entity IDs
- Type hints on every function signature
- `dataclass` for domain models, prefer `frozen=True` for value objects
- Specific exceptions only, never bare `Exception`
- Always use `session_scope()` context manager for DB — never raw sessions

### Imports order
```python
# 1. Standard library
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List

# 2. Third-party
from sqlalchemy import Column, String
from pydantic import Field

# 3. Local
from trading_cotrader.core.models.domain import Position, Trade
from trading_cotrader.config.settings import get_settings
```

### DB session pattern (always this, never anything else)
```python
from trading_cotrader.core.database.session import session_scope

with session_scope() as session:
    repo = SomeRepository(session)
    # auto-commits on success, auto-rollbacks on error
```

### Adding a new strategy type
1. Add enum to `StrategyType` in `core/models/domain.py`
2. Add config in `config.yaml` under `strategies.defined` or `strategies.undefined`

### Adding a new risk check
1. Add method to `RiskManager` in `services/risk_manager.py`
2. Call from `validate_trade()`
3. Add test in `tests/`

### Modifying DB schema
1. Update ORM in `core/database/schema.py`
2. Update domain model in `core/models/domain.py`
3. Run `setup_database.py` to recreate (never manual migrations in dev)

---

## [CLAUDE OWNS] DEV COMMANDS
<!-- Claude uses these exact commands. Never invents alternatives. -->

```bash
# Database setup
python -m trading_cotrader.scripts.setup_database

# Test harness (primary test/validation tool — 14 steps)
python -m trading_cotrader.harness.runner --skip-sync   # use existing DB data, no broker needed
python -m trading_cotrader.harness.runner --mock        # mock data, no broker
python -m trading_cotrader.harness.runner               # full test with broker connection

# Grid server (WebSocket + REST API for UI)
python -m trading_cotrader.runners.run_grid_server
# Then open trading_cotrader/ui/trading-grid.html in browser

# Daily operations (in playground/ — experimental scripts)
python -m trading_cotrader.playground.sync_portfolio
python -m trading_cotrader.playground.sync_with_greeks
python -m trading_cotrader.playground.portfolio_analyzer
python -m trading_cotrader.playground.validate_data

# Log a trading decision
python -m trading_cotrader.cli.log_event --underlying SPY --strategy iron_condor --rationale "High IV rank"

# Tests (note: tests/ dir is currently empty — harness is the primary test tool)
pytest
pytest -v
```

### Testing today's work (Feb 15 — multi-tier portfolios + performance metrics)
```bash
# 1. Verify YAML config loads correctly (4 portfolios, 100% allocation)
python -c "from trading_cotrader.config.risk_config_loader import RiskConfigLoader; c = RiskConfigLoader().load(); print(f'{len(c.portfolios.get_all())} portfolios, {c.portfolios.total_allocation_pct()}% allocated')"

# 2. Run full harness — step 14 validates portfolios + metrics
python -m trading_cotrader.harness.runner --skip-sync

# 3. Verify portfolios exist in DB
python -c "
from trading_cotrader.core.database.session import session_scope
from trading_cotrader.services.portfolio_manager import PortfolioManager
with session_scope() as s:
    pm = PortfolioManager(s)
    for p in pm.get_all_managed_portfolios():
        print(f'{p.name}: equity={p.total_equity}, delta_limit={p.max_portfolio_delta}')
"

# 4. Verify strategy validation works
python -c "
from trading_cotrader.core.database.session import session_scope
from trading_cotrader.services.portfolio_manager import PortfolioManager
with session_scope() as s:
    pm = PortfolioManager(s)
    print(pm.validate_trade_for_portfolio('core_holdings', 'covered_call'))
    print(pm.validate_trade_for_portfolio('core_holdings', 'iron_condor'))
    print(pm.validate_trade_for_portfolio('high_risk', 'iron_condor'))
"
```

### Critical runtime notes
- Greeks come from DXLink streaming, NOT REST API — adapter handles this
- Always test with `IS_PAPER_TRADING=true` before live
- Never store credentials in code — use `.env` or YAML with `${VAR}` syntax

---

## TECH STACK (REFERENCE)

| Layer | Choice | Status |
|-------|--------|--------|
| Backend | Python + FastAPI (`server/api_v2.py`) | ✅ Working |
| WebSocket | Custom (`server/websocket_server.py`) | ✅ Built |
| Database | SQLite (→ PostgreSQL later) | ✅ Working |
| Broker | TastyTrade via SDK (`adapters/tastytrade_adapter.py`) | ✅ Connected |
| Greeks/Pricing | Black-Scholes (custom, in both `analytics/` and `services/pricing/`) | ✅ Built |
| Frontend | HTML + JSX prototypes (`ui/`), NOT a React app yet | ⚠️ Prototypes only |
| Event Sourcing | Custom (`core/models/events.py`) | ✅ Built |
| AI/ML | Q-Learning + DQN (numpy) | ⚠️ Built, needs data |
| Containers | Domain object state management (`containers/`) | ✅ Built |
| Portfolio Mgmt | Multi-tier from YAML (`services/portfolio_manager.py`) | ✅ Built |
| Performance | OptionsKit metrics (`services/performance_metrics_service.py`) | ✅ Built, needs trade data |

---

## FILE STRUCTURE (WHAT EXISTS TODAY)

```
trading_cotrader/
├── adapters/
│   └── tastytrade_adapter.py        ✅ Auth, positions, balance (+ _working.py, _working_v1.py backups)
├── analytics/
│   ├── pricing/option_pricer.py     ✅ Black-Scholes
│   ├── pricing/pnl_calculator.py    ✅ P&L
│   ├── greeks/engine.py             ✅ Greeks calculations
│   ├── volatility_surface.py        ✅ IV surface
│   └── functional_portfolio.py      ✅ Functional portfolio analysis
├── cli/
│   └── log_event.py                 ✅ CLI for logging trade decisions
├── config/
│   ├── settings.py                  ✅
│   ├── risk_config_loader.py        ✅ (extended with PortfolioConfig, PortfoliosConfig, ExitRuleProfile)
│   └── risk_config.yaml             ✅ 4 portfolio tiers, exit rules, underlyings, strategy rules
├── containers/
│   ├── container_manager.py         ✅ Orchestrates all containers
│   ├── portfolio_container.py       ✅ Portfolio state
│   ├── position_container.py        ✅ Position state
│   ├── trade_container.py           ✅ Trade state
│   └── risk_factor_container.py     ✅ Risk factor state
├── core/
│   ├── database/schema.py           ✅ ORM (11 tables, WhatIf support)
│   ├── database/session.py          ✅ session_scope() context manager
│   ├── models/domain.py             ✅ PortfolioType, TradeStatus lifecycle, PnLAttribution
│   ├── models/events.py             ✅ Event sourcing models
│   ├── models/calculations.py       ✅
│   ├── models/strategy_templates.py  ✅ 18 strategy templates (risk, bias, Greeks, exits)
│   └── validation/validators.py     ✅
├── harness/                          ✅ TEST FRAMEWORK (replaces old debug_autotrader)
│   ├── runner.py                    ✅ Main orchestrator (python -m trading_cotrader.harness.runner)
│   ├── base.py                      ✅ Step base classes, rich output
│   ├── run_containers.py            ✅ Container-based test variant
│   └── steps/
│       ├── step01_imports.py        ✅ Import validation
│       ├── step02_broker.py         ✅ Broker connection
│       ├── step03_portfolio.py      ✅ Portfolio sync
│       ├── step04_market_data.py    ✅ Market data containers
│       ├── step05_risk_aggregation.py ✅ Risk aggregation
│       ├── step05_risk_factors.py   ✅ Risk factor resolution
│       ├── step06_hedging.py        ✅ Hedge calculations
│       ├── step07_risk_limits.py    ✅ Risk limit checks
│       ├── step08_trades.py         ✅ Trade history
│       ├── step09_events.py         ✅ Event logging
│       ├── step10_ml_status.py      ✅ ML readiness check
│       ├── step11_containers.py     ✅ Container integration
│       ├── step12_trade_booking.py  ✅ Single WhatIf trade booking
│       ├── step13_strategy_templates.py ✅ All 12 strategy template bookings
│       └── step14_portfolio_performance.py ✅ Multi-tier portfolios + performance metrics
├── repositories/
│   ├── base.py                      ✅
│   ├── portfolio.py                 ✅
│   ├── trade.py                     ⚠️ is_open bug — fix first
│   ├── position.py                  ✅
│   └── event.py                     ✅
├── runners/
│   └── run_grid_server.py           ✅ WebSocket + REST server for UI
├── scripts/
│   ├── setup_database.py            ✅ DB creation
│   └── test_whatif_flow.py          ✅ WhatIf test script
├── server/
│   ├── api_v2.py                    ✅ FastAPI REST endpoints
│   ├── contracts.py                 ✅ API request/response contracts
│   ├── data_provider.py             ✅ Data abstraction layer (33KB)
│   └── websocket_server.py          ✅ WebSocket server (26KB)
├── services/
│   ├── position_sync.py             ✅ Broker position sync
│   ├── portfolio_sync.py            ✅ Portfolio-level sync
│   ├── greeks_service.py            ✅ Greeks calculation service
│   ├── event_logger.py              ✅ Event logging
│   ├── event_analytics.py           ✅ Event analysis
│   ├── data_service.py              ✅ General data service
│   ├── snapshot_service.py          ✅ Portfolio snapshot service
│   ├── option_grid_service.py       ✅ Option chain grid
│   ├── trade_booking_service.py     ✅ End-to-end WhatIf booking (DXLink → DB → containers → ML) + portfolio routing
│   ├── portfolio_manager.py         ✅ Multi-tier portfolio init from YAML, strategy routing, validation
│   ├── performance_metrics_service.py ✅ Win rate, CAGR, Sharpe, drawdown, strategy breakdown, weekly P&L
│   ├── risk_manager.py              ✅ Top-level risk orchestration
│   ├── real_risk_check.py           ✅ Live risk validation
│   ├── hedging/hedge_calculator.py  ✅ Hedge recommendations
│   ├── market_data/                 ✅ Market data domain (3 files)
│   ├── pricing/                     ✅ BS, greeks, implied vol, probability, scenarios (5 files)
│   ├── risk/                        ✅ VaR, correlation, concentration, margin, limits, portfolio_risk
│   ├── risk_factors/                ✅ Risk factor models + resolver
│   └── position_mgmt/rules_engine.py ✅ Exit rules
├── ai_cotrader/
│   ├── data_pipeline.py             ⚠️ Built, needs live data
│   ├── feature_engineering/         ⚠️ Built, needs live event data
│   ├── learning/                    ⚠️ Built, needs 500+ events to train
│   └── models/                      ⚠️ Agents defined, not trained
├── playground/                       ⚠️ Experimental scripts (not production)
│   ├── auto_trader.py               Prototype auto-trader
│   ├── sync_portfolio.py            Daily sync script
│   ├── sync_with_greeks.py          Greeks sync
│   ├── portfolio_analyzer.py        Analysis script
│   ├── validate_data.py             Data validation
│   ├── instituitional_trading_v4.py Large prototype (61KB)
│   ├── instituitional_trading_v5.py Large prototype (64KB)
│   ├── beta_hedging_v1/v2.py        Beta hedging experiments
│   ├── regime_markovchain_v1/v2.py  Regime detection experiments
│   ├── passive_strategies.py        Passive strategy experiments
│   └── test_flow.py                 Test flow script
├── tests/
│   └── __init__.py                  ❌ EMPTY — no pytest tests written yet
└── ui/                               ⚠️ Prototypes, not a React app
    ├── grid/TradingDashboard.jsx    JSX component (single file)
    ├── trading-grid.html            Main UI entry point
    ├── institutional-dashboard.html  Dashboard prototype
    ├── trading-terminal.html         Terminal prototype
    ├── trading-terminal_v0.html      Terminal v0
    └── payoff_graph.py              Python payoff graph utility
```
