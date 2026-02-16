# CLAUDE.md
# Project: Trading CoTrader
# Last Updated: February 16, 2026 (session 11)
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
The gap: institutional discipline has never been applied to personal wealth. 250K sits idle (50K personal, 200K self-directed IRA).
This tool deploys capital systematically, safely, with full risk visibility at every level: trade, strategy, portfolio.
Mental model: Macro Context → My Exposure → Action Required. Never "I have an iron condor." Always "I have -150 SPY delta, +$450 theta/day. Am I within limits?"

---

## [NITIN OWNS] BUSINESS OBJECTIVES — CURRENT
<!-- Add new entries at TOP with date. Move completed sessions to CLAUDE_ARCHIVE.md. -->

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

*(No mandate set for current session — waiting for Nitin's direction.)*

---

## [NITIN OWNS] TODAY'S SURGICAL TASK
<!-- OVERWRITE each session. 5 lines max. -->

*(No task set for current session.)*

---

## [CLAUDE OWNS] WHAT USER CAN DO TODAY

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
- 4 risk-tiered portfolios from YAML, strategy permissions matrix
- Performance metrics per portfolio (win rate, Sharpe, drawdown, expectancy)
- Source tracking on every trade (screener, manual, astrology, etc.)

**Testing:**
- Harness: `python -m trading_cotrader.harness.runner --skip-sync` — 14/16 pass (2 skip without broker), 17 steps
- Unit tests: `pytest trading_cotrader/tests/ -v` — 55 tests, all pass

**Broker & Server:**
- Authenticate TastyTrade, sync portfolio, pull live Greeks
- Grid server: `python -m trading_cotrader.runners.run_grid_server`

**Blocked / Not Yet Working:**
- Liquidity check on entry screeners not yet wired (exit-side only)
- OI + daily volume from broker not integrated (mock placeholders) — needs `/market-metrics`
- Auto-accept for exit recommendations not implemented
- IV rank uses realized vol proxy — needs broker IV
- Macro doesn't check FOMC/earnings dates
- UI is prototypes only (`ui/`)
- Performance metrics return zeros (no closed trades)
- 6 strategies not testable in harness (equity legs, two expirations, custom)

---

## [CLAUDE OWNS] CURRENT BLOCKER

**No active blockers.**

---

## [CLAUDE OWNS] CODE MAP
<!-- Maps objectives to code. Update when new features are built. -->

| Area | Key files |
|------|-----------|
| **Portfolios** | `config/risk_config.yaml`, `config/risk_config_loader.py`, `services/portfolio_manager.py` |
| **Trade Booking** | `services/trade_booking_service.py`, `cli/book_trade.py`, `core/models/domain.py` (TradeStatus, TradeSource) |
| **Screeners** | `services/screeners/` (vix, iv_rank, leaps), `services/recommendation_service.py`, `services/technical_analysis_service.py` |
| **Macro Gate** | `services/macro_context_service.py`, `config/daily_macro.yaml` |
| **Portfolio Eval** | `services/portfolio_evaluation_service.py`, `services/position_mgmt/rules_engine.py`, `services/liquidity_service.py` |
| **Recommendations** | `core/models/recommendation.py` (RecommendationType), `repositories/recommendation.py`, `cli/accept_recommendation.py`, `cli/evaluate_portfolio.py` |
| **Risk** | `services/risk/` (VaR, correlation, concentration, margin, limits), `services/risk_manager.py`, `services/hedging/hedge_calculator.py` |
| **Performance** | `services/performance_metrics_service.py` (win rate, CAGR, Sharpe, drawdown, source breakdown) |
| **Events/ML** | `services/event_logger.py`, `core/models/events.py`, `ai_cotrader/` (feature extraction, RL — needs data) |
| **Pricing** | `analytics/pricing/` (BS, P&L), `analytics/greeks/engine.py`, `services/pricing/` |
| **DB/ORM** | `core/database/schema.py` (11 tables), `core/database/session.py`, `repositories/` |
| **Broker** | `adapters/tastytrade_adapter.py`, `services/position_sync.py`, `services/portfolio_sync.py` |
| **Server** | `server/api_v2.py` (FastAPI), `server/websocket_server.py`, `runners/run_grid_server.py` |
| **Tests** | `tests/` (55 pytest), `harness/` (17 integration steps) |

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
pytest trading_cotrader/tests/ -v                        # 55 unit tests

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

# Server
python -m trading_cotrader.runners.run_grid_server
```

### Critical runtime notes
- Greeks come from DXLink streaming, NOT REST API
- Always test with `IS_PAPER_TRADING=true` before live
- Never store credentials in code — use `.env`
