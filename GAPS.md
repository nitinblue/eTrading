# Money-Making Machine — Standing Gap Analysis
# Last Updated: 2026-03-11 (Session 40)
# Review this every session. Cross off what's done. Add what emerges.

## THE MISSION
Deploy $250K systematically. Generate cash flow through options trading.
Agents own their desk WhatIf P&L — fully, no excuses.
Humans promote WhatIf → real when the track record proves out.

---

## ✅ FULL PIPELINE — BUILT AND WORKING

The end-to-end trading lifecycle is implemented:

| Step | Command | What | Service/File |
|------|---------|------|-------------|
| Screen + rank | `scan` | Scout screens watchlist, Maverick applies 6 gates | scout.py, maverick.py |
| Review proposals | `propose` | Show scored trade specs with rationale | interaction.py |
| Book to WhatIf | `deploy` | Book trades to WhatIf portfolio | trade_booking_service.py |
| Go live preview | `execute <id>` | Dry-run preflight: buying power, fees, risk | tastytrade_adapter.py |
| Place real order | `execute <id> --confirm` | Place order on TastyTrade | adapter.place_order() |
| Check fills | `orders` | Auto-update trade status on fill | interaction.py |
| Mark to market | `mark` | Live quotes + Greeks via DXLink | mark_to_market.py |
| Exit signals | `exits` | Profit target, stop loss, DTE, expired | exit_monitor.py |
| Close trades | `close auto` | Auto-close URGENT + profit target signals | trade_lifecycle.py |
| Close specific | `close <id>` | Manual close with reason | trade_lifecycle.py |
| ML learning | `learn` | Q-learning from closed trade outcomes | trade_learner.py |
| Performance | `perf [desk]` | Win rate, Sharpe, P&L by desk | performance_metrics.py |

Supporting infrastructure:
- 3 trading desks (0DTE $10K, medium $10K, LEAPs $20K)
- Position sizing (2% capital / max risk per spread)
- Duplicate prevention (underlying:strategy key)
- Exit profiles by strategy type (0DTE: no stop/90% TP, credit: 50% TP/2× SL, etc.)
- Event system with full audit trail (market + decision context)
- SaaS credential pattern (broker sessions passed to MarketAnalyzer)
- Expired options handled gracefully (keep last price, exit monitor catches DTE ≤ 0)

---

## 🔴 MUST VALIDATE — Prove the Machine Works

### V1: End-to-End with Live Broker
**What:** Run full `scan → propose → deploy → mark → exits` with real broker connection and real market data.
**Why:** Ranking bug (.ranked → .top_trades) was preventing proposals from flowing. Fixed s38b. Need to validate the fix produces real proposals.
**How:** Connect broker, run `scan`, verify proposals flow, `deploy` to WhatIf, `mark` to get live prices, `exits` to check.

### V2: Track WhatIf Performance Over 5+ Trading Days
**What:** Book trades via the pipeline, let mark-to-market and exit monitor run daily, close when signals fire.
**Why:** This IS the product. Agent desk P&L is what proves the system works. No excuses on cloud.

---

## 🟡 BUILD NEXT — Product Quality

### Trade Execution Rail Guard
Prevent accidental trade execution by Claude or automation. Defense in depth:
1. **Environment variable gate** — `TRADE_EXECUTION_ENABLED=false` in `.env`. Execute endpoint refuses to place orders unless explicitly `true`. Default off.
2. **Read-only broker mode** — `TastytradeAdapter(read_only=True)` disables all order-placement methods at the adapter level. Even if `execute --confirm` is called, adapter refuses.
Both layers required. API-level + adapter-level = no single point of failure.

### Confidence Framework
Every event gets a confidence level based on data lineage. Over time: report habitual vs merit-based actions. "I would rather take no action than compulsions."
- Data freshness (how old is the quote/regime/ranking?)
- Data completeness (how many fields populated vs empty?)
- Decision lineage (which data points informed each gate?)

### Daily P&L Report
Morning report: overnight changes, theta decay earned, exit signals, positions approaching expiration, cash flow this week/month.

### Real-Time Streaming for 0DTE
30-min polling too slow for day trades. IntradayService (REQ-5) built in market_analyzer —
needs to be wired into engine's monitoring cycle with shorter interval for 0DTE desk.

### Trade Journal / Decision Analysis
Events exist but nothing aggregates learnings. After closing: was entry timing good? Did exit rules fire correctly?

### Notifications
Slack/email on: exit signal, trade booked, black swan, P&L threshold.

---

## 🟢 SAAS — Multi-User Platform

| Item | What | Status |
|------|------|--------|
| User model + auth | OAuth/SSO, user table, login | Not started |
| Multi-tenancy | Tenant-scoped DB queries | Not started |
| Desk onboarding UI | Wizard for new users (create desks, allocate capital) | CLI only (`setup-desks`) |
| Broker account linking | Each user connects their own broker | Single-user only |
| PostgreSQL | Replace SQLite | Not started |
| Cloud deployment | Docker, K8s, async task queue | Not started |
| API rate limiting | Quotas per user | Not started |
| Multi-broker routing | Route orders by portfolio/broker | BrokerRouter exists, single broker |

---

## MARKET ANALYZER REQUIREMENTS

| Req | What | Status |
|-----|------|--------|
| ~~REQ-1~~ | `dxlink_symbols` on TradeSpec → `.SPY260327P580` format | ✅ DONE (s38b) |
| ~~REQ-2~~ | `position_size(capital, risk_pct)` on TradeSpec | ✅ DONE (s38b) |
| ~~REQ-3~~ | `exit_plan: ExitPlan` field on TradeSpec | ✅ DONE (s38b) |
| ~~REQ-5~~ | IntradayService for 0DTE signals (`ma.intraday.monitor()`) | ✅ DONE (s38b) |
| REQ-6 | Backtest harness | Deferred (not needed now) |

---

## WEEKLY SCORECARD

| Metric | Target | Current |
|--------|--------|---------|
| Trades proposed per week | 5-10 | TBD (validate with live scan) |
| WhatIf P&L this week | Track | TBD |
| Exit signals acted on | 100% | TBD |
| Win rate (closed trades) | >60% | TBD |
| Average days held | 15-30 | TBD |
| Capital utilization | 50-80% | TBD |
| Theta decay earned/day | >0 | TBD |
