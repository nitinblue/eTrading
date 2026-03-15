# CoTrader — Master Status
# Session 41 | March 15, 2026 (overnight)
# ONE PAGE to rule them all.

---

## BY THE NUMBERS

| Metric | Value |
|--------|-------|
| eTrading tests | 185 |
| MA tests | 1331+ |
| MA capabilities (functions) | 57 |
| MA models (classes) | 208 |
| eTrading services | 10 |
| Maverick gates | 12 (including trade quality) |
| Frontend pages | 12 |
| CLI commands | 25+ |
| API endpoints | 40+ |
| DB tables | 27 |
| Supported brokers | 3 (TastyTrade, Dhan, Zerodha) |
| Supported markets | 2 (US, India) |

---

## WHAT'S DONE (not touching again)

### Core Pipeline (P1-P8) — ALL DONE
- TradeSpec bridge, MA-driven exits, health checks
- 12 Maverick gates (verdict, score, spec, BP, duplicate, limit, ML, drift, POP, EV, income entry, time window, liquidity, trade quality)
- Adjustment pipeline (recommend_action, overnight risk)
- 0DTE fast cycle (2-min), decision lineage, ML learning
- Frontend: Overview, Trade Journey, Desks, Manual, Agents with characters

### ML Systems — ALL WIRED
- Drift detection → Gate 6b
- Thompson Sampling → Scout strategy selection
- Threshold optimization → gate cutoffs
- POP calibration → regime factors
- Q-learning → Gate 6 ML score
- Bandit auto-update on trade close

### Multi-Market Foundation — DONE
- MarketRegistry (lot sizes, strike intervals, settlement, expiry conventions)
- Currency-aware formatting ($ vs ₹)
- Timezone-aware entry windows (zoneinfo)
- Broker factory (TastyTrade, Dhan, Zerodha)
- Market-grouped desk cards with flags + open/closed status

### Security — DONE
- Trade execution rail guard (env var + read-only adapter)
- Credentials in env vars only (YAML deleted)
- .env in .gitignore

### SaaS Foundation — DONE
- User model + JWT auth + auth API endpoints
- BrokerConnectionORM (per-user, encrypted tokens)
- Alembic setup
- Docker + docker-compose (API + PostgreSQL + Redis)

---

## WHAT'S IN PROGRESS

### From CAPABILITY_AUDIT.md — Tier 1 (Data exists, wire to UI)

| # | Gap | Backend | Frontend | Status |
|---|-----|---------|----------|--------|
| A | Sharpe/drawdown per desk | API exists | Panel on Desks | **DONE** |
| B | Explain trade button | API exists | Modal on Desks | **DONE** |
| C | Exit signal detail | API exists | Not in UI yet | API ONLY |
| D | Adjustment recommendation | API exists | Not in UI yet | API ONLY |
| E | Daily P&L report | API exists | Panel on Desks | **DONE** |
| F | System alerts | API exists | Panel on Desks | **DONE** |
| G | Income yield ROC | In serialization | Column in grid | **DONE** |
| H | Overnight risk indicator | In desk data | Not highlighted | API ONLY |

### From CAPABILITY_AUDIT.md — Tier 2 (Need backend + UI)

| # | Gap | Status |
|---|-----|--------|
| I | Assessment breakdown per trade (why this strategy) | CLI `explain` works. UI modal shows gates. Missing: per-assessor scores. |
| J | Advanced technicals (Fibonacci, ADX, Donchian, Keltner, Pivots, VWAP) | MA computes. ResearchSnapshot doesn't store. Not in UI. |
| K | ML dashboard (drift, bandits, thresholds, POP calibration) | CLI `ml` works. Not in UI. |
| L | Volatility surface (term structure + skew) | MA computes. Not wired or displayed. |
| M | Intraday signals panel for 0DTE | Engine runs signals. Not in UI. |
| N | Margin estimation per trade | MA has `estimate_margin()`. Not called. |
| O | Strategy availability matrix (per market) | MA has `strategy_available()`. Not displayed. |

### From AGENTS.md — Agent Gaps

| Agent | Immediate Gaps | Status |
|-------|---------------|--------|
| **Chanakya (Scout)** | Sector rotation, multi-timeframe, sentiment | Not started |
| **Kubera (Steward)** | Dynamic desk allocation (ML), Greek attribution enhancement, benchmark comparison | K6 (desk perf comparison) DONE. Rest TODO. |
| **Bhishma (Sentinel)** | Cross-desk net delta (B14 in Atlas now), correlation breakdown, threshold retrospective | B14 DONE. Rest TODO. |
| **Arjuna (Maverick)** | Multi-leg order generation (A17), roll execution (A19), partial close (A18), trailing stop (A20) | A20 trailing stop DONE. A17/A18/A19 TODO. |
| **Vishwakarma (Atlas)** | V1-V6 health checks DONE. ML freshness auto-trigger, position reconciliation, notification system | V1-V6 DONE. Rest TODO. |

### From SAAS.md — Cloud Gaps

| Phase | Items | Status |
|-------|-------|--------|
| Phase 0 (Pre-Cloud) | PostgreSQL, Alembic, Docker, rail guard | Rail guard DONE. Docker DONE. Alembic setup DONE. PostgreSQL migration script TODO. |
| Phase 1 (Auth) | User model, JWT, login page | Backend DONE. Frontend login page NOT DONE. API enforcement NOT DONE. |
| Phase 2 (Multi-Tenant) | tenant_id on tables, scoped queries, per-user broker | **tenant_id DONE** (8 tables). tenant.py helper DONE. Scoped queries TODO. |
| Phase 3 (Workers) | Celery + Redis, background tasks, per-user scheduling | Docker-compose has Redis. Celery not configured. |
| Phase 4 (Scale) | Multiple instances, WebSocket, CDN, monitoring | Not started. |

---

## PRIORITY STACK — What To Attack Next

### Tonight (High Impact, Quick Wins)

| # | What | Time | Why |
|---|------|------|-----|
| 1 | **Frontend: Wire C + D (exit signals + adjustment)** into Trading Terminal as expandable row | 30 min | Users can't see WHY a trade should close or HOW to adjust |
| 2 | **Frontend: ML dashboard tab** on Agents page (drift alerts, bandit rankings, thresholds) | 30 min | `ml` CLI works but 80% of users are on UI |
| 3 | **Frontend: Macro indicators panel** on Research page | 20 min | `/api/v2/macro` exists but not rendered |
| 4 | **Frontend: Cross-market panel** on Research page | 20 min | `/api/v2/cross-market` exists but not rendered |
| 5 | **A17: Multi-leg order generation** for adjustments | 45 min | Biggest functional gap — system can't generate roll legs |

### This Weekend (Foundation)

| # | What | Time | Why |
|---|------|------|-----|
| 6 | **PostgreSQL migration script** (SQLite → PostgreSQL data) | 1 hr | Can't go cloud without this |
| 7 | **Frontend: Login page** | 1 hr | Auth backend exists but no UI |
| 8 | **Tier 2-J: Advanced technicals** in Research page | 1 hr | 6 MA indicators computed but never shown |
| 9 | **Tier 2-K: ML dashboard** full page (not just tab) | 1 hr | Drift, bandits, thresholds, POP calibration visualization |
| 10 | **Steward: Dynamic desk allocation (ML)** | 2 hr | Kubera's main value prop — shift capital to high-Sharpe desks |

### Next Week (SaaS)

| # | What | Time | Why |
|---|------|------|-----|
| 11 | API auth enforcement (JWT middleware on all endpoints) | 2 hr | Currently anonymous |
| 12 | tenant_id migration (all tables) | 3 hr | Multi-user isolation |
| 13 | Celery task queue setup | 2 hr | Background agent pipeline |
| 14 | Dhan broker adapter (real connection) | 3 hr | India market live |
| 15 | Notification system (Slack webhook) | 2 hr | Alerts, trade booked, P&L threshold |

---

## FILES TO REFERENCE

| File | What | Current |
|------|------|---------|
| `GAPS.md` | Integration gaps + MA delivery tracking | 25/27 done + E-series + ML-E series |
| `AGENTS.md` | Agent capabilities, gaps, naming, plan | 5 agents documented, gaps prioritized |
| `CAPABILITY_AUDIT.md` | Every MA capability vs UI visibility | 20% in UI, 60% not wired |
| `SAAS.md` | Cloud go-live gaps + multi-broker | 33 SaaS gaps + 11 multi-broker gaps |
| `ARCHITECTURE.md` | SaaS target architecture | Designed, not implemented |
| `MARKETS.md` | Exchange specs (in MA repo) | US + India complete |
| `GETTING_STARTED.md` | Priyanka's guide | Written |
| `WEEKEND_PLAN.md` | Weekend battle plan | Partially executed |

---

## HONEST ASSESSMENT

**What works well:**
- Full trading pipeline (scan → gate → book → monitor → exit → learn)
- 12 Maverick gates with ML intelligence
- Multi-market foundation (US + India)
- 5 agents with clear roles
- Comprehensive documentation

**What's weak:**
- **Frontend lags backend by 40%** — many capabilities exist but aren't visible
- **No real trades yet** — pipeline validated but weekend blocked live data
- **SaaS auth not enforced** — endpoints wide open
- **PostgreSQL not migrated** — still on SQLite
- **India brokers not connected** — stubs only

**What should we do tonight:**
Items 1-5 from the priority stack. All are frontend or functional gaps that make the system more complete and visible. 2-3 hours of work.
