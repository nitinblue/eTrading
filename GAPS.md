# Money-Making Machine — Standing Gap Analysis
# Last Updated: 2026-03-09 (Session 37)
# Review this every session. Cross off what's done. Add what emerges.

## THE MISSION
Deploy $250K systematically. Generate cash flow through options trading.
Every gap below is a blocker between "software project" and "money-making machine."

---

## ✅ CLOSED GAPS (Done this session)

| Gap | What | How |
|-----|------|-----|
| ~~Maverick → Booking Bridge~~ | Maverick consumes Scout rankings, books WhatIf trades | `maverick.py` rewritten: 5 gates → proposals → `book_proposals()` |
| ~~Agent Pipeline Disabled~~ | Engine never ran agents | `engine.py` calls `_run_agent_pipeline()` in BOOTING + MONITORING |
| ~~Position Sizing~~ | All trades were 1-lot | `_compute_position_size()`: 2% of capital / max_risk_per_spread |
| ~~Duplicate Prevention~~ | Same trade booked every 30 min | `underlying:strategy_type` key check against open WhatIf trades |
| ~~P&L Mark-to-Market~~ | Trades frozen at entry price | `services/mark_to_market.py`: fetches quotes+Greeks, updates DB |
| ~~Exit Monitoring~~ | No one watched exit rules | `services/exit_monitor.py`: profit target, stop loss, DTE, expired |
| ~~CLI Workflow~~ | No way to scan/propose/deploy | `scan`, `propose`, `deploy`, `mark`, `exits` commands |
| ~~Hardcoded Market Data~~ | Correlations, rates, limits hardcoded | Audit utility + all violations fixed, config-driven |
| ~~Context Propagation~~ | TradeSpec was dict, not Pydantic | Maverick works with dicts via `.get()` — clean and working |

---

## 🔴 OPEN GAPS — Blocking Real Money

### GAP A: Order Execution (CRITICAL — #1 blocker)
**Current:** `deploy` books to WhatIf DB. `execute` command exists but is dry-run only.
**Needed:** Place real orders on TastyTrade via broker adapter.
**What's missing:**
1. `TastytradeAdapter.place_order(legs, order_type, price)` — the actual API call
2. Order lifecycle: submit → working → filled → update trade
3. Fill confirmation: update TradeORM with actual fill prices, fees
4. OCO/bracket orders vs system-triggered exits (see Gap B)
**Approach:** System triggers exit orders (not resting OCO on broker). Our exit monitor
detects conditions every 30 min → places closing order when triggered.
**Files:** `adapters/tastytrade_adapter.py`, `agents/workflow/interaction.py`

### GAP B: Exit Order Placement (CRITICAL — #2 blocker)
**Current:** ExitMonitorService generates signals (PROFIT_TARGET, STOP_LOSS, DTE_EXIT).
Signals are displayed via `exits` CLI command. Nothing acts on them.
**Needed:** When exit signal fires, automatically (or with approval) place closing order.
**Two exit models by strategy:**
- **0DTE / Defined-risk:** No stop loss needed (risk capped by wings). Profit target 90%.
  Hold through expiration if target not hit — max loss is already defined.
- **Standard trades:** Both profit target (50%) and stop loss (2× credit or 50% debit).
  System places closing order when triggered.
**Exit profiles** already coded in `exit_monitor.py` → `_get_exit_profile()`.
**Files:** `agents/domain/maverick.py`, `adapters/tastytrade_adapter.py`

### GAP C: Approval Workflow Before Real Execution
**Current:** `approve`/`reject` commands exist but don't connect to order placement.
**Needed:** Human-in-the-loop before any real money moves:
1. `scan` generates proposals (automatic)
2. `propose` shows them (human reviews)
3. `approve <id>` or `deploy --approve` (human confirms)
4. System places order (automatic)
5. `orders` shows fill status (automatic)
**Status:** Partially wired. Needs approval → order flow.

### GAP D: Real Broker Position Sync for WhatIf P&L
**Current:** Mark-to-market fetches quotes via broker DXLink. Works for real positions.
For WhatIf trades, need the same symbols to be quote-able.
**Risk:** WhatIf trades may reference options that have expired or been delisted.
**Needed:** Graceful handling when quotes unavailable (keep last known price).

---

## 🟡 IMPORTANT GAPS — Revenue Enablers

### GAP E: Portfolio Selection & Capital Allocation
**Current:** All proposals go to `tastytrade_whatif`. No per-portfolio capital budgets.
**Needed:**
- Route trades to appropriate portfolio based on strategy type and account type
- IRA: conservative (covered calls, collars, cash-secured puts)
- Personal: aggressive (IC, verticals, 0DTE)
- Capital allocation: what % goes to each strategy bucket

### GAP F: Daily P&L Dashboard
**Current:** `positions` and `portfolios` CLI commands show state. No daily P&L summary.
**Needed:** Morning report: overnight changes, today's theta decay earned, exit signals,
positions approaching expiration, total cash flow generated this week/month.

### GAP G: Trade Journal / Decision Tracking
**Current:** TradeEventORM captures events. Nothing aggregates or analyzes.
**Needed:** After closing a trade: what did we learn? Win/loss, how close to max profit,
did exit rules fire correctly, was entry timing good?
Performance metrics service exists but isn't wired to trade lifecycle.

### GAP H: Live Streaming vs Polling
**Current:** Mark-to-market runs every 30 min via scheduler. For 0DTE trades this is
too slow — a 30-min-old quote could miss a stop or profit target.
**Needed for 0DTE:** Real-time price streaming via DXLink WebSocket.
Non-0DTE can stay on 30-min polling.

### GAP I: Multi-Account Order Routing
**Current:** BrokerRouter exists but routes to one broker. Real setup: TastyTrade (options),
Fidelity IRA (conservative), Fidelity personal (moderate).
**Needed:** Order router that knows: this strategy on this portfolio → this broker.

---

## 🟢 NICE-TO-HAVE GAPS — Polish

### GAP J: Notifications (Slack/Email)
Alert when: exit signal fires, trade booked, P&L threshold hit, black swan detected.

### GAP K: UI Dashboard
React frontend exists. Needs: real-time P&L chart, trade proposal cards, exit signal alerts.

### GAP L: Backtesting
Run historical data through the full pipeline to validate strategy selection.

---

## MARKET ANALYZER REQUIREMENTS (for their backlog)

See `MARKET_ANALYZER_REQUIREMENTS.md` for detailed specs. Summary:
1. **REQ-1:** Add `dxlink_symbols` property to TradeSpec (DXLink format, not OCC)
2. **REQ-2:** Position sizing method on TradeSpec (capital, risk_pct → contracts)
3. **REQ-3:** Exit plan as first-class object on TradeSpec
4. **REQ-4:** Strategy-level expected value (risk/reward without Black-Scholes)
5. **REQ-5:** Intraday signals for 0DTE management
6. **REQ-6:** Backtest harness for strategy validation

---

## WEEKLY SCORECARD

Track these metrics to know if the machine is working:

| Metric | Target | Current |
|--------|--------|---------|
| Trades proposed per week | 5-10 | TBD (run `scan` daily) |
| WhatIf P&L this week | Track | TBD (run `mark` daily) |
| Exit signals acted on | 100% | TBD |
| Win rate (closed trades) | >60% | TBD |
| Average days held | 15-30 | TBD |
| Capital utilization | 50-80% | TBD |
| Theta decay earned/day | >0 | TBD |

---

## NEXT ACTIONS (Priority Order)

1. **Run `scan` end-to-end** with live broker to validate the full pipeline
2. **Build `TastytradeAdapter.place_order()`** — the #1 blocker to real money
3. **Wire exit signals → closing orders** — the #2 blocker
4. **Add approval-before-execution** guard for real trades
5. **Daily P&L report** CLI command
