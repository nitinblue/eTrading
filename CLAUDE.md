# CLAUDE.md
# Project: Trading CoTrader
# Last Updated: February 16, 2026 (session 12)
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

### Feb 16, 2026 (Session 5) — Continuous Trading Workflow Engine

**Context:** The system today is a collection of CLI tools you run on-demand. Each piece works (screeners, booking, evaluation, metrics) but nothing connects them into a continuous operating loop. You run a screener, copy a recommendation ID, run accept, copy a template, edit it, run book_trade. This is fragile, manual, and easy to skip. The harness validates integration but doesn't drive real trading decisions.

**What this is:** A continuously running workflow engine that operates your entire trading day — from macro check to trade execution to position management — with decision points where YOU approve/reject, and accountability tracking that ensures you stay invested and follow the system.

**How it differs from harness:** Harness runs once, tests, exits. Workflow runs continuously, maintains state, pauses for user decisions, sends notifications, tracks accountability, and drives real capital deployment.

| # | Objective | Signal (observable behavior) | Status |
|---|-----------|-------------------------------|--------|
| 1 | **Workflow state machine** — Continuous loop: MACRO_CHECK → WATCHLIST_REFRESH → SCREENING → RECOMMENDATION_REVIEW → TRADE_PLANNING → ORDER_STAGING → POSITION_MONITORING → EXIT_EVALUATION → EXIT_REVIEW → REPORTING. State persisted in DB. Can resume after restart. | `python -m trading_cotrader.workflow.engine --start` runs continuously. State visible in DB/CLI. | NOT STARTED |
| 2 | **User decision points** — Workflow pauses at RECOMMENDATION_REVIEW and EXIT_REVIEW. Presents options (accept/reject/modify/defer). Tracks time-to-decision. Escalates if ignored (reminder after 1hr, nag after 4hr, missed-opportunity log after expiry). | Workflow stops, notifies user, waits for decision. If no decision by market close, logs as "no action" with accountability note. | NOT STARTED |
| 3 | **Notifications & approvals** — Email alerts on: new recommendations, exit triggers, risk limit approaching, idle capital warning, daily summary. Future: Slack, SMS, mobile push. Approval can come via email reply, CLI, or (future) mobile app. | User receives email: "3 new recommendations pending. $8K idle in medium_risk. SPY iron condor at 52% profit — close?" | NOT STARTED |
| 4 | **Capital deployment accountability** — Track deployed vs idle capital per portfolio. Alert when cash exceeds target reserve (Core: >15% idle = alert, Med: >10%, High: >5%). Weekly "capital efficiency" report. Track "days since last trade" per portfolio. Log conscious dry-powder decisions vs laziness/inaction. | Weekly report: "Core: 62% deployed (target 85%). 6 days since last trade. 2 screener recs were ignored." | NOT STARTED |
| 5 | **Trade plan compliance** — Every execution compared to template. Deviations flagged: wrong strikes, wrong DTE, wrong timing, wrong portfolio, skipped entry conditions. "Did you follow the playbook?" metric. Source comparison: system recs vs manual overrides, with performance tracking on both. | Monthly compliance report: "87% of trades followed template. Manual overrides underperformed system recs by 12%." | NOT STARTED |
| 6 | **Workflow scheduling** — Calendar-aware: knows which cadence runs on which day (0DTE daily, weekly Wed/Fri, monthly when DTE aligns). Knows market holidays, FOMC dates, earnings dates. Adjusts cycle timing automatically. No trades on holidays. Skip 0DTE on FOMC days. | Workflow on Wednesday at 1:55 PM: "SPX weekly calendar window opens in 5 min. Template prepared. Ready to review?" | NOT STARTED |
| 7 | **WhatIf → Order conversion** — Workflow can stage WhatIf trades, get approval, then convert to real broker orders. Paper trading mode first. Real orders require explicit "go live" flag + position size verification. Two-step approval for real orders: "I want to do this" → "I'm really sure". | `--paper` mode books WhatIf only. `--live` mode converts approved WhatIf to TastyTrade order after double confirmation. | NOT STARTED |
| 8 | **Daily/weekly reporting** — Automated end-of-day summary: trades entered, trades closed, P&L, capital deployment, risk utilization, playbook compliance. Weekly digest with performance vs targets. All emailed automatically. | Every day at 4:15 PM ET: email with today's activity, portfolio snapshot, outstanding decisions, tomorrow's calendar. | NOT STARTED |
| 9 | **Circuit breakers & trading halts** — Rule-based automatic trading halts. Daily loss limit (3% of portfolio = halt for day). Weekly loss limit (5% = halt for week, review required). Per-portfolio drawdown limit (Core 15%, Med 20%, High 30%). Consecutive loss limit (3 in a row = pause strategy, 5 = pause portfolio). VIX spike halt (VIX >35 = no new entries). All halts logged with reason. Override requires written rationale + confirmation. Cannot be silently bypassed. | Workflow blocks new trades: "HALTED: Daily loss 3.2% exceeded 3% limit. No new entries until tomorrow. Override requires written rationale." | NOT STARTED |
| 10 | **Rule-based trading constraints** — Configurable rules enforced by workflow, not memory. Max trades per day (e.g., 3). Max trades per week per portfolio. No trading in first 15 min of market (unless 0DTE). No trading in last 30 min (unless closing). No undefined risk without explicit approval per trade. No adding to losing positions without rationale. Position size must follow Kelly criterion or fixed fractional. All rules in YAML, all violations logged. | "BLOCKED: Attempting 4th trade today (max 3). Rule: max_trades_per_day=3 in workflow_rules.yaml." | NOT STARTED |

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

**Risk Analysis (VaR):**
- Real parametric VaR (delta-normal) using yfinance historical returns + covariance
- Historical VaR using actual past return distributions (captures fat tails)
- Incremental VaR: calculate portfolio VaR → add WhatIf trade → compare incremental impact
- Expected Shortfall (CVaR) at all confidence levels
- Per-underlying VaR contribution breakdown (standalone, component, marginal VaR)
- Correlation matrix from real yfinance data (1-day cache, fallback to estimates if offline)
- All risk module imports fixed (`trading_cotrader.services.risk.*`)

**Testing:**
- Harness: `python -m trading_cotrader.harness.runner --skip-sync` — 14/16 pass (2 skip without broker), 17 steps
- Unit tests: `pytest trading_cotrader/tests/ -v` — 79 tests, all pass (55 original + 24 VaR/correlation)

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
| **Risk/VaR** | `services/risk/var_calculator.py` (parametric + historical + incremental VaR, yfinance data), `services/risk/correlation.py` (real covariance + volatility from yfinance), `services/risk/` (concentration, margin, limits), `services/risk_manager.py`, `services/hedging/hedge_calculator.py` |
| **Performance** | `services/performance_metrics_service.py` (win rate, CAGR, Sharpe, drawdown, source breakdown) |
| **Events/ML** | `services/event_logger.py`, `core/models/events.py`, `ai_cotrader/` (feature extraction, RL — needs data) |
| **Pricing** | `analytics/pricing/` (BS, P&L), `analytics/greeks/engine.py`, `services/pricing/` |
| **DB/ORM** | `core/database/schema.py` (11 tables), `core/database/session.py`, `repositories/` |
| **Broker** | `adapters/tastytrade_adapter.py`, `services/position_sync.py`, `services/portfolio_sync.py` |
| **Server** | `server/api_v2.py` (FastAPI), `server/websocket_server.py`, `runners/run_grid_server.py` |
| **Tests** | `tests/` (79 pytest — includes 24 VaR/correlation tests), `harness/` (17 integration steps) |
| **Templates** | `config/templates/` (27 templates: 1 0DTE, 4 weekly, 16 monthly, 5 LEAPS, 1 custom). Entry conditions + P&L drivers on all. |

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
pytest trading_cotrader/tests/ -v                        # 79 unit tests

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
