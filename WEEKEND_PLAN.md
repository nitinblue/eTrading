# Weekend Battle Plan — March 15-16, 2026
# Priority order. Attack top-down. Each item is independently testable.

---

## Priority 1: CAN WE MAKE A REAL TRADE? (Validation)

Before building more features, prove the machine works end-to-end with live broker.

| # | What | Time | Blocker? |
|---|------|------|----------|
| W1 | Connect broker (--paper --web), run `scan` | 15 min | Must verify scan produces real proposals |
| W2 | Review proposals — do they make sense? | 10 min | Quality check on POP, EV, legs |
| W3 | `deploy` to WhatIf desks | 5 min | Verify trades route to correct desk |
| W4 | `mark` — get live prices | 10 min | Verify DXLink streaming works |
| W5 | `exits` — check exit conditions | 5 min | Verify MA monitor fires correctly |
| W6 | `health` — position health check | 5 min | Verify health status updates |
| W7 | `explain <id>` — decision lineage | 5 min | Verify full audit trail stored |
| W8 | `deskperf` — desk comparison | 5 min | Verify Sharpe/drawdown computation |
| W9 | `syscheck` — system health | 5 min | Verify Atlas checks pass |
| W10 | `ml run` — ML learning cycle | 5 min | Verify drift/bandits/thresholds work |

**If W1-W10 pass: the systematic trading pipeline is validated. Real trades can begin.**

---

## Priority 2: FUNCTIONAL GAPS (Make It Complete)

| # | What | Agent | Effort | Why Now |
|---|------|-------|--------|---------|
| W11 | Multi-leg order generation for adjustments | Arjuna | Medium | When MA says ROLL_AWAY, generate exact close+open legs. Currently flags for human. |
| W12 | Trailing stop in exit monitor | Arjuna | Small | ExitPlan has trailing_stop. Exit monitor ignores it. Free P&L improvement. |
| W13 | Partial close (scale out at TP1) | Arjuna | Medium | ExitPlan supports multi-target. "Close 50% at TP1, hold rest." |
| W14 | Wire `debug=True` to all MA calls in Scout | Chanakya | Small | Commentary captures step-by-step reasoning. Currently only on context.assess(). |
| W15 | On trade close: auto-update bandit | Arjuna | Small | `update_single_bandit()` exists. Not called when trade_lifecycle closes a trade. |
| W16 | Daily report auto-trigger at EOD | Kubera | Small | Report method exists. Not wired into scheduler EOD cycle. |

---

## Priority 3: AGENT CAPABILITIES (Make Agents Earn Their Keep)

| # | What | Agent | Effort | Why |
|---|------|-------|--------|-----|
| W17 | Steward: Greek P&L attribution per desk (enhanced) | Kubera | Medium | "Is P&L from theta or delta?" Per-desk breakdown. |
| W18 | Steward: Daily report in engine EOD + API endpoint | Kubera | Small | `/api/v2/report/daily` for frontend consumption |
| W19 | Sentinel: Cross-desk net delta constraint | Bhishma | Small | Gate checks per-desk only. Need aggregate across all desks. |
| W20 | Atlas: ML model freshness auto-trigger | Vishwakarma | Small | When bandits > 7 days stale, auto-run ML cycle. Don't wait for engine step 9b. |
| W21 | Atlas: System events API endpoint | Vishwakarma | Small | `/api/v2/system/events` — show recent alerts in UI |

---

## Priority 4: FRONTEND (Make It Visible)

| # | What | Page | Effort | Why |
|---|------|------|--------|-----|
| W22 | DeskPerformance: show Sharpe/drawdown from `/desks/performance` API | Desks | Small | API exists, not rendered in cards |
| W23 | DeskPerformance: add `deskperf` button | Desks | Tiny | Action button like scan/deploy/mark |
| W24 | System events panel on Agents page | Agents | Small | Show Atlas alerts from system_events table |
| W25 | Daily report view in Reports page | Reports | Medium | Render Steward's daily report in UI |
| W26 | Broker status card on landing page | Overview | Small | Show connected broker, market, currency |

---

## Priority 5: SAAS FOUNDATION (Start the Journey)

| # | What | Effort | Why Now |
|---|------|--------|---------|
| W27 | PostgreSQL migration script | Large | Foundation for everything SaaS. SQLite is the ceiling. |
| W28 | Alembic setup + initial migration | Medium | Versioned schema changes. Required for production. |
| W29 | Dockerfile (API + worker) | Medium | Package for deployment. Docker = deployable anywhere. |
| W30 | User model + bcrypt auth (no OAuth yet) | Medium | Simplest auth. Email + password. JWT tokens. |

---

## Recommended Weekend Schedule

### Saturday Morning: VALIDATE (W1-W10)
Run the full pipeline with live broker. Fix any issues. This is the most important work.

### Saturday Afternoon: FUNCTIONAL (W11-W16)
Multi-leg adjustments, trailing stop, bandit auto-update, daily report trigger.
These make the system genuinely autonomous.

### Saturday Evening: AGENTS (W17-W21)
Steward Greek attribution, Sentinel cross-desk, Atlas freshness auto-trigger.
Each agent earns its place.

### Sunday Morning: FRONTEND (W22-W26)
Wire APIs to UI. Make everything visible. Quick wins.

### Sunday Afternoon: SAAS (W27-W30)
PostgreSQL + Docker + basic auth. Start the SaaS journey.

---

## What NOT To Do This Weekend

- Don't build Dhan/Zerodha eTrading adapter (MA stubs ready, but focus on TastyTrade first)
- Don't build notifications (Slack/email — nice to have, not blocking)
- Don't build backtesting (MA doesn't have it, premature)
- Don't optimize performance (premature)
- Don't refactor agents (they work, don't touch working code)

---

## Success Criteria

By end of weekend:
1. **One real scan → propose → deploy cycle validated with live broker** (W1-W10)
2. **Adjustment legs auto-generated** (W11)
3. **Trailing stop wired** (W12)
4. **PostgreSQL running** (W27-W28)
5. **Docker containerized** (W29)

If we achieve these 5, the system is production-ready for single-user with real money.
