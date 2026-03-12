# CLAUDE.md — Trading CoTrader
# Last Updated: March 11, 2026 (session 40)

## PRIME DIRECTIVE

**We are building a money-making machine, not a tech project.**

$250K capital ($50K personal, $200K self-directed IRA). Goal: deploy systematically to fund Nitin's daughter's college education through options trading.

### Non-Negotiable Rules

1. **Never book a bogus trade.** Every trade must come from the full pipeline with real market data.
2. **Never take action for the sake of taking action.** 90%+ confidence required. Call out gaps honestly.
3. **No mocked data in production flow.** Everything must be tradeable.
4. **Every event is data.** Log everything. Feed ML/RL. The system becomes intelligent over time.
5. **Measure progress by: can Maverick execute a real trade today?**

### Accountability Model

**Agents own their WhatIf desk P&L — fully, no excuses.**
- Each desk has a WhatIf portfolio. Agent is 100% accountable: win rate, P&L, Sharpe, drawdown.
- On cloud (SaaS), agent desk performance IS the product's track record. Numbers speak.

**Agents never touch real portfolio P&L.**
- Humans promote WhatIf → real. Human bears responsibility for actual capital.
- System's job: make the WhatIf track record so compelling that promotion is obvious.

### Before Every Session
- Ask: **"Does this move us closer to real trades with real money?"**
- Review `GAPS.md` — the standing gap analysis. Always update it.
- Force reinstall: `pip install --force-reinstall --no-deps -e ../market_analyzer`
- Update CLAUDE.md and GAPS.md after major changes.

---

## HOW MONEY GETS MADE

```
Market Data (TastyTrade DXLink) → Scout (screen + rank) → Maverick (6 gates + sizing)
  → WhatIf Portfolio (paper) → Human Review → Real Order (TastyTrade API)
  → Exit Monitor → Close Order → P&L → ML/RL Learning Loop
```

### The Pipeline

| Step | Command | What |
|------|---------|------|
| Screen + rank | `scan` | Scout screens watchlist, Maverick applies 6 gates |
| Review proposals | `propose` | Show scored trade specs with rationale |
| Book to WhatIf | `deploy` | Book trades to WhatIf portfolio |
| Go live preview | `execute <id>` | Dry-run: buying power, fees, risk |
| Place real order | `execute <id> --confirm` | Place order on TastyTrade |
| Check fills | `orders` | Auto-update trade status on fill |
| Mark to market | `mark` | Live quotes + Greeks via DXLink |
| Exit signals | `exits` | Profit target, stop loss, DTE, expired |
| Close trades | `close auto` | Auto-close URGENT + profit target signals |
| Close specific | `close <id>` | Manual close with reason |
| ML learning | `learn` | Q-learning from closed trade outcomes |
| Performance | `perf [desk]` | Win rate, Sharpe, P&L by desk |
| Daily plan | `plan` | Desk-aware trading plan for today |

### Maverick's 6 Gates (every trade must pass ALL)

1. **Verdict** — MarketAnalyzer says GO or CAUTION (not NO_GO)
2. **Score** — Composite score ≥ 0.35
3. **Trade spec** — Valid legs, strikes, expiration exist
4. **Duplicate** — Not already in portfolio (underlying:strategy key)
5. **Position limit** — Under desk max positions
6. **ML score** — Pattern recognition doesn't flag negative (when data exists)

### Trading Desks

| Desk | Capital | DTE | Underlyings | Exit Rules |
|------|---------|-----|-------------|------------|
| desk_0dte | $10K | 0 DTE | SPY, QQQ, IWM | No stop (defined risk), 90% TP |
| desk_medium | $10K | ~45 DTE | Top 10 | 50% TP, 2× credit SL, close ≤21 DTE |
| desk_leaps | $20K | 180+ DTE | Blue chips | 100% TP, 50% SL |

### Exit Rules by Strategy Type

- **0DTE / defined-risk**: No stop loss (risk capped by wings). 90% profit target. Hold to expiry.
- **Standard credit**: 50% profit target, 2× credit stop, close ≤21 DTE.
- **Standard debit**: 100% profit, 50% loss, close ≤21 DTE.

---

## AGENTS — Who Does What

| Agent | Role | Owns |
|-------|------|------|
| **Scout** (Quant) | Screen, rank, regime, technicals, opportunities | Market intelligence |
| **Steward** (Portfolio Mgr) | Portfolio state, positions, P&L, capital | Position tracking |
| **Sentinel** (Risk Mgr) | Circuit breakers, constraints, risk limits | Risk enforcement |
| **Maverick** (Trader) | THE workflow agent — scan, propose, book, exit | Trade decisions |
| **Atlas** (Tech Architect) | Infrastructure | Not prioritized |

**Pipeline order:** Steward.populate → Sentinel.run → Steward.run → Scout.populate → Scout.run → Maverick.run

---

## EVENT & LEARNING SYSTEM

Every trade action creates a `TradeEvent` with:
- **MarketContext**: VIX, IV rank, regime, technicals, macro
- **DecisionContext**: rationale, confidence (1-10), outlook, alternatives
- **TradeOutcomeData**: WIN/LOSS, P&L, close reason, Greeks attribution

**Learning loop:** TradeLearner reads closed trades → builds patterns (regime:iv:strategy:dte:side) → scores future trades → feeds Maverick gate 6.

---

## DAILY PLAN

Desk-aware daily plan generated via `plan` command or `/api/v2/plan`:
- Merges all desk tickers + strategies into ONE `plan.generate()` call
- Splits results by desk membership
- **skip_intraday=True** — skips DXLink/ORB fetches (saves 45s+, ORB not needed for daily plan)
- Returns: day verdict, risk budget, ranked trades per desk, expiry events

---

## RAIL GUARDS

**Trade execution is human-only.** Claude has broker access for market data (plan, quotes, positions, portfolio) but must NEVER execute trades or place orders. See GAPS.md for the implementation plan (env var gate + read-only adapter mode).

---

## SAAS VISION

Cloud-hosted SaaS. Multi-tenant. Design every feature with this in mind.

- **Desks** are the core concept — onboarding creates desks, allocates capital, selects underlyings
- Credential pattern already SaaS-ready (eTrading owns auth, MarketAnalyzer gets sessions)
- Agent desk performance IS the product's track record
- Target: PostgreSQL, async task queue, WebSocket, Docker/K8s

---

## OPEN GAPS → see GAPS.md

Always review and update GAPS.md. It is the standing agenda.

---

## DEV COMMANDS

```bash
pip install --force-reinstall --no-deps -e ../market_analyzer
pytest trading_cotrader/tests/ -v
python -m trading_cotrader.runners.run_workflow --paper --web
python -m trading_cotrader.runners.run_workflow --once --no-broker --mock
cd frontend && pnpm dev
cd frontend && pnpm build
```

---

## TECHNICAL REFERENCE

For architecture, key files, coding standards, data flows, and DB schema → see `ARCHITECTURE.md`

---

## SESSION LOG

| Session | Date | Key Outcome |
|---------|------|-------------|
| s40 | Mar 11 | Fixed plan timeout (skip_intraday=True eliminates 45s+ DXLink blocking). Plan now works. CLAUDE.md refocused on trading. Rail guard for trade execution added to GAPS.md. |
| s39 | Mar 11 | Fixed ranking bug (.ranked→.top_trades). CLAUDE.md rewritten. MarketAnalyzer REQ-1→5. 168+940 tests. |
| s38 | Mar 10 | UI consolidation. Desk-aware daily plan. SaaS credential refactoring. Stallion deletion. |
| s37b | Mar 9 | Trading desks + full lifecycle. 3 desks. Auto-booking. 170 tests. |
| s37 | Mar 9 | Full trading workflow. Maverick 6 gates + proposals + booking + sizing. 163 tests. |
| s36 | Feb 26 | Tech debt mega-cleanup. Deleted legacy agents, dead services. 149 tests. |
