# SaaS / Cloud — Go-Live Gap Analysis
# Last Updated: 2026-03-14 (Session 41)
# Single source of truth for cloud deployment readiness.

## Vision

Cloud-hosted SaaS. Multi-tenant. Users sign up, connect broker, configure desks, and the system trades for them.
Agent desk performance IS the product's track record. Numbers speak.

---

## MASTER GAP TABLE

| # | Category | Gap | Priority | Effort | Status |
|---|----------|-----|----------|--------|--------|
| **S1** | Auth | User model + registration | **CRITICAL** | Large | TODO |
| **S2** | Auth | OAuth/SSO login (Google, GitHub) | **CRITICAL** | Medium | TODO |
| **S3** | Auth | JWT token-based API auth | **CRITICAL** | Medium | TODO |
| **S4** | Auth | Session management + refresh tokens | **HIGH** | Medium | TODO |
| **S5** | Multi-tenant | Tenant-scoped DB queries (all tables) | **CRITICAL** | Large | TODO |
| **S6** | Multi-tenant | User → tenant → portfolios isolation | **CRITICAL** | Medium | TODO |
| **S7** | Multi-tenant | Per-tenant config (desks, risk limits, strategies) | **HIGH** | Medium | TODO |
| **S8** | Broker | Broker account linking per user | **CRITICAL** | Large | TODO |
| **S9** | Broker | TastyTrade stored token auth (not user/pass) | **HIGH** | Medium | TODO |
| **S10** | Broker | TastyTrade API key / session token | **HIGH** | Small | TODO |
| **S11** | Broker | Multi-broker support (Schwab, IBKR) | MEDIUM | Large | TODO |
| **S12** | Database | PostgreSQL migration (from SQLite) | **CRITICAL** | Large | TODO |
| **S13** | Database | Alembic migrations | **HIGH** | Medium | TODO |
| **S14** | Database | Connection pooling | **HIGH** | Small | TODO |
| **S15** | Infra | Docker containerization | **CRITICAL** | Medium | TODO |
| **S16** | Infra | Docker Compose (API + worker + DB + Redis) | **HIGH** | Medium | TODO |
| **S17** | Infra | Kubernetes manifests | MEDIUM | Medium | TODO |
| **S18** | Infra | Async task queue (Celery/ARQ + Redis) | **HIGH** | Large | TODO |
| **S19** | Infra | WebSocket for real-time updates | MEDIUM | Medium | TODO |
| **S20** | Infra | Rate limiting per user | **HIGH** | Small | TODO |
| **S21** | Onboarding | Desk setup wizard UI | **HIGH** | Medium | TODO |
| **S22** | Onboarding | Broker connection flow UI | **HIGH** | Medium | TODO |
| **S23** | Onboarding | Risk profile questionnaire | MEDIUM | Medium | TODO |
| **S24** | Security | Credential encryption at rest | **CRITICAL** | Medium | TODO |
| **S25** | Security | HTTPS / TLS termination | **CRITICAL** | Small | TODO |
| **S26** | Security | CORS policy | **HIGH** | Small | TODO |
| **S27** | Security | Trade execution rail guard (env var + adapter) | **CRITICAL** | Small | PARTIAL |
| **S28** | Billing | Subscription tiers | MEDIUM | Large | TODO |
| **S29** | Billing | Usage tracking (scans, trades, API calls) | LOW | Medium | TODO |
| **S30** | Monitoring | Application health endpoints | **HIGH** | Small | TODO |
| **S31** | Monitoring | Error tracking (Sentry) | **HIGH** | Small | TODO |
| **S32** | Monitoring | Structured logging | MEDIUM | Small | TODO |
| **S33** | Monitoring | Metrics (Prometheus/Grafana) | MEDIUM | Medium | TODO |

---

## PHASE PLAN

### Phase 0: Pre-Cloud Foundation (do BEFORE cloud)

| # | What | Why | Effort |
|---|------|-----|--------|
| S27 | Trade execution rail guard | MUST have before any real trading. Env var + read-only adapter. | Small |
| S12 | PostgreSQL migration | SQLite doesn't scale. Must migrate before multi-tenant. | Large |
| S13 | Alembic migrations | Need versioned schema changes for production. | Medium |
| S15 | Docker containerization | Package app for deployment anywhere. | Medium |

### Phase 1: Auth + Single-User Cloud

| # | What | Why | Effort |
|---|------|-----|--------|
| S1 | User model | Table: users (id, email, name, password_hash, created_at) | Medium |
| S2 | OAuth login | Google + GitHub SSO. FastAPI + python-jose + httpx. | Medium |
| S3 | JWT API auth | Protect all /api/ endpoints. Token in header. | Medium |
| S4 | Session management | Refresh tokens, expiry, logout. | Medium |
| S24 | Credential encryption | Broker tokens encrypted with per-user key. | Medium |
| S25 | HTTPS | TLS cert via Let's Encrypt or cloud LB. | Small |

### Phase 2: Multi-Tenant

| # | What | Why | Effort |
|---|------|-----|--------|
| S5 | Tenant-scoped queries | Every DB query filtered by tenant_id. | Large |
| S6 | User → tenant isolation | Users can't see each other's data. | Medium |
| S7 | Per-tenant config | Each user has own desks, capital, risk limits. | Medium |
| S8 | Broker linking per user | Each user connects their own TastyTrade account. | Large |

### Phase 3: Infrastructure

| # | What | Why | Effort |
|---|------|-----|--------|
| S16 | Docker Compose | API + worker + PostgreSQL + Redis. One command start. | Medium |
| S18 | Task queue | Background: scans, mark-to-market, ML learning. Not blocking API. | Large |
| S19 | WebSocket | Real-time: price updates, trade notifications, health alerts. | Medium |
| S20 | Rate limiting | Prevent abuse. Per-user quotas on scan/deploy. | Small |

### Phase 4: Onboarding + Polish

| # | What | Why | Effort |
|---|------|-----|--------|
| S21 | Desk wizard | New user: "How much capital? What strategies? What risk tolerance?" → auto-create desks. | Medium |
| S22 | Broker connection UI | "Connect TastyTrade" button → OAuth flow → stored token. | Medium |
| S23 | Risk profile | Questionnaire → maps to risk_config.yaml parameters. | Medium |
| S26 | CORS | Allow frontend domain only. | Small |
| S30 | Health endpoints | /health, /ready for K8s probes. | Small |
| S31 | Sentry | Error tracking + alerting. | Small |

---

## BROKER AUTH — TastyTrade Options

### Current: Username/Password in .env
```
TASTYTRADE_USERNAME=xxx
TASTYTRADE_PASSWORD=xxx
```
Works for single-user. Not SaaS-ready.

### Option A: Stored Session Token
TastyTrade SDK supports session token auth. User authenticates once → token stored (encrypted) → reused until expiry.
```python
from tastytrade import Session
session = Session.from_token(stored_token)  # No credentials needed
```
- **Pro:** No password stored. Token can be revoked.
- **Con:** Token expires (24h?). Need refresh flow.

### Option B: API Key (if TastyTrade supports)
Some brokers offer long-lived API keys for programmatic access.
- **Pro:** Set once, works until revoked.
- **Con:** TastyTrade may not offer this.

### Option C: OAuth Flow
TastyTrade may support OAuth2 redirect flow.
- **Pro:** Industry standard. User never shares password.
- **Con:** Requires callback URL, more complex.

### Recommendation
**Start with Option A (stored token).** User logs into TastyTrade in our UI → we capture the session token → encrypt and store → reuse. When token expires → prompt re-auth.

For SaaS:
```
User clicks "Connect TastyTrade"
  → Opens TastyTrade login in popup/iframe
  → User enters credentials DIRECTLY to TastyTrade (not to us)
  → We receive session token
  → Store encrypted in DB (per user)
  → Use for all MA + portfolio operations
```

---

## CREDENTIAL PATTERN (already SaaS-ready)

eTrading already separates auth from usage:
```
eTrading owns auth → creates TastyTrade session
  → passes session to MA via connect_from_sessions()
  → MA never sees credentials
```

For SaaS: same pattern, but per-user:
```
User authenticates → stored token in DB (encrypted)
  → per-request: load token → create session → pass to MA
  → MA processes → returns results
  → session discarded (or cached short-term)
```

---

## DATABASE MIGRATION: SQLite → PostgreSQL

### Tables to Migrate (23 tables)
- Core: symbols, portfolios, positions, trades, legs, orders, strategies
- Events: trade_events, recognized_patterns
- Performance: daily_performance, position_greeks_snapshots, position_pnl_snapshots, greeks_history
- Workflow: workflow_state, decision_log, agent_runs, agent_objectives
- Research: research_snapshots, macro_snapshots
- Config: what_if_portfolio_configs, market_data_snapshots
- New: ml_state, system_events

### Migration Strategy
1. Create PostgreSQL schema from ORM models
2. Use Alembic for versioned migrations
3. One-time SQLite → PostgreSQL data migration script
4. Update session_scope() to use PostgreSQL connection string
5. Add connection pooling (SQLAlchemy pool_size=10)

### Key Changes
- `session_scope()` → reads `DATABASE_URL` env var (default: SQLite for dev)
- JSON columns → PostgreSQL JSONB (better indexing)
- DateTime → PostgreSQL TIMESTAMP WITH TIME ZONE
- Boolean → PostgreSQL BOOLEAN (not INTEGER)

---

## ARCHITECTURE: SaaS

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▷│   API Server │────▷│  PostgreSQL   │
│  (React/Vite)│     │  (FastAPI)   │     │  (per-tenant) │
└──────────────┘     └──────┬───────┘     └──────────────┘
                           │
                     ┌─────▼──────┐     ┌──────────────┐
                     │   Worker   │────▷│    Redis      │
                     │  (Celery)  │     │  (task queue) │
                     └─────┬──────┘     └──────────────┘
                           │
                     ┌─────▼──────┐
                     │  MA Library │
                     │ (stateless) │
                     └─────┬──────┘
                           │
                     ┌─────▼──────┐
                     │  Broker    │
                     │ (per-user) │
                     └────────────┘
```

### Per-User Isolation
- Each user has: own broker session, own desk configs, own ML state
- All DB queries scoped by `tenant_id`
- MA library is stateless — shared across users, no cross-contamination
- Broker sessions are per-user — never shared

### Task Queue (Background)
- Scans run as background tasks (not blocking API)
- Mark-to-market as periodic task per user
- ML learning as scheduled task
- Results pushed via WebSocket to frontend

---

---

## MULTI-BROKER & GLOBAL MARKETS

### Current State
- Single broker: TastyTrade (US options)
- MA has 4 ABCs: MarketDataProvider, MarketMetricsProvider, AccountProvider, WatchlistProvider
- eTrading has BrokerRouter (single broker wired)

### Target Brokers

| Broker | Market | Instruments | Auth Method | Status |
|--------|--------|-------------|-------------|--------|
| **TastyTrade** | US | Options, Equities | Session token / user+pass | **DONE** |
| **Dhan** | India (NSE/BSE) | F&O, Equities, Commodities | API key + access token | TODO |
| **Zerodha** | India (NSE/BSE) | F&O, Equities | Kite Connect API (OAuth) | TODO |
| Schwab | US | Options, Equities | OAuth2 | Future |
| IBKR | Global | Everything | TWS API / Client Portal | Future |

### Architecture: Multi-Broker

```
User Account
  ├── Broker Connection: TastyTrade (US) ─── session token
  ├── Broker Connection: Dhan (India)    ─── API key + token
  └── Broker Connection: Zerodha (India) ─── Kite Connect token
         │
         ▼
  Desk Routing (per broker):
    desk_us_0dte   → TastyTrade  ($10K, SPY/QQQ)
    desk_us_medium → TastyTrade  ($15K, top US)
    desk_india_fo  → Dhan/Zerodha (₹5L, NIFTY/BANKNIFTY)
```

### What Each Broker Needs

For each broker, implement MA's 4 ABCs:

| ABC | TastyTrade | Dhan | Zerodha |
|-----|-----------|------|---------|
| MarketDataProvider | DXLink streaming | Dhan Market Feed API | Kite Ticker WebSocket |
| MarketMetricsProvider | tastytrade metrics API | Dhan options chain | Kite instruments + computed |
| AccountProvider | Account balances API | Dhan funds API | Kite margins API |
| WatchlistProvider | TT watchlists | Dhan watchlists | Kite GTT / portfolio |

### Implementation per Broker

**Dhan (India NSE/BSE)**
```
Package: market_analyzer/broker/dhan/
Files:
  - __init__.py        → connect_dhan(api_key, access_token)
  - market_data.py     → DhanMarketData(MarketDataProvider)
  - metrics.py         → DhanMetrics(MarketMetricsProvider)
  - account.py         → DhanAccount(AccountProvider)
  - watchlist.py       → DhanWatchlist(WatchlistProvider)

Auth: API Key (long-lived) + Access Token (daily, from login)
Docs: https://dhanhq.co/docs/v2/
Options chain: GET /v2/optionchain
Positions: GET /v2/positions
Orders: POST /v2/orders
```

**Zerodha (India NSE/BSE)**
```
Package: market_analyzer/broker/zerodha/
Files:
  - __init__.py        → connect_zerodha(api_key, access_token)
  - market_data.py     → ZerodhaMarketData(MarketDataProvider)
  - metrics.py         → ZerodhaMetrics(MarketMetricsProvider)
  - account.py         → ZerodhaAccount(AccountProvider)
  - watchlist.py       → ZerodhaWatchlist(WatchlistProvider)

Auth: Kite Connect API Key + Access Token (OAuth2 redirect)
Docs: https://kite.trade/docs/connect/v3/
Ticker: WebSocket for real-time quotes
Instruments: GET /instruments (master list)
Positions: GET /portfolio/positions
Orders: POST /orders/regular
```

### Global Market Considerations

| Consideration | Design Decision |
|--------------|-----------------|
| **Currency** | PortfolioORM has `currency` field. Desks tied to broker's currency. No cross-currency mixing. |
| **Market hours** | WorkflowConfig has `market_hours` (timezone-aware). India: 9:15-15:30 IST. US: 9:30-16:00 ET. Per-broker scheduling. |
| **Options chain format** | MA's MarketDataProvider ABC abstracts this. Each broker maps to OptionQuote model. |
| **Strike formatting** | India: strike in ₹ (integers). US: strike in $ (decimals). TradeSpec handles both. |
| **Contract size** | India F&O: lot size varies (NIFTY=25, BANKNIFTY=15). US: standard 100. Symbol multiplier. |
| **Expiry conventions** | India: weekly (Thu), monthly (last Thu). US: weekly (Fri), monthly (3rd Fri). |
| **Settlement** | India: cash-settled (no assignment risk). US: physically settled (assignment possible). |
| **Strategy differences** | India F&O: iron condors work on NIFTY/BANKNIFTY. LEAPs not common. 0DTE = weekly expiry. |
| **Regulatory** | India: SEBI margin rules (peak margin). US: Reg-T / portfolio margin. |

### Desk Templates per Market

**India desks:**
```yaml
desk_india_weekly:
  display_name: "India Weekly (NIFTY/BANKNIFTY)"
  broker_firm: dhan  # or zerodha
  currency: INR
  initial_capital: 500000  # ₹5 Lakh
  allowed_strategies: [iron_condor, credit_spread, straddle]
  target_dte: 0-7  # weekly expiry

desk_india_monthly:
  display_name: "India Monthly (FO)"
  broker_firm: zerodha
  currency: INR
  initial_capital: 1000000  # ₹10 Lakh
  allowed_strategies: [iron_condor, calendar, diagonal]
  target_dte: 15-45
```

**US desks (existing):**
```yaml
desk_0dte:    $10K, TastyTrade, 0DTE
desk_medium:  $15K, TastyTrade, ~45 DTE
desk_leaps:   $20K, TastyTrade, 180+ DTE
```

### Multi-Broker Gaps

| # | Gap | Priority | Effort | Status |
|---|-----|----------|--------|--------|
| MB1 | Dhan MarketDataProvider | **HIGH** | Medium | TODO |
| MB2 | Dhan AccountProvider | **HIGH** | Small | TODO |
| MB3 | Dhan order execution | **HIGH** | Medium | TODO |
| MB4 | Zerodha MarketDataProvider | **HIGH** | Medium | TODO |
| MB5 | Zerodha AccountProvider | **HIGH** | Small | TODO |
| MB6 | Zerodha order execution | **HIGH** | Medium | TODO |
| MB7 | Per-broker market hours scheduling | MEDIUM | Small | TODO |
| MB8 | Currency-aware P&L display | MEDIUM | Small | TODO |
| MB9 | India-specific strategy assessors (NIFTY/BANKNIFTY) | MEDIUM | Medium | TODO |
| MB10 | Lot size handling (India contracts ≠ 100) | **HIGH** | Small | TODO |
| MB11 | SEBI peak margin calculation | MEDIUM | Medium | TODO |

---

---

## CI/CD PIPELINE

### Pipeline Stages

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│   LINT   │───▷│   TEST   │───▷│  BUILD   │───▷│  DEPLOY  │───▷│  VERIFY  │
│ ruff/mypy│    │ pytest   │    │ docker   │    │ staging  │    │ smoke    │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

### Stage 1: Lint + Type Check
```yaml
# .github/workflows/ci.yml
lint:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: '3.12' }
    - run: pip install ruff mypy
    - run: ruff check trading_cotrader/
    - run: mypy trading_cotrader/ --ignore-missing-imports
```

### Stage 2: Test
```yaml
test:
  runs-on: ubuntu-latest
  needs: lint
  services:
    postgres:
      image: postgres:16
      env: { POSTGRES_DB: test_cotrader, POSTGRES_USER: test, POSTGRES_PASSWORD: test }
      ports: ['5432:5432']
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: '3.12' }
    - run: pip install -e ../market_analyzer
    - run: pip install -r requirements.txt
    - run: pytest trading_cotrader/tests/ -v --tb=short
      env:
        DATABASE_URL: postgresql://test:test@localhost:5432/test_cotrader
```

### Stage 3: Build Docker Image
```yaml
build:
  runs-on: ubuntu-latest
  needs: test
  steps:
    - uses: actions/checkout@v4
    - uses: docker/setup-buildx-action@v3
    - uses: docker/login-action@v3
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    - uses: docker/build-push-action@v5
      with:
        context: .
        file: docker/Dockerfile
        push: true
        tags: ghcr.io/${{ github.repository }}/cotrader:${{ github.sha }}
```

### Stage 4: Deploy to Staging
```yaml
deploy-staging:
  runs-on: ubuntu-latest
  needs: build
  if: github.ref == 'refs/heads/main'
  steps:
    - name: Deploy to staging
      run: |
        # SSH to staging server or use cloud CLI
        # Pull latest image, run migrations, restart
        ssh staging "cd /app && docker-compose pull && docker-compose up -d"
        ssh staging "cd /app && alembic upgrade head"
```

### Stage 5: Smoke Test
```yaml
verify:
  runs-on: ubuntu-latest
  needs: deploy-staging
  steps:
    - name: Health check
      run: curl -f https://staging.cotrader.app/api/v2/health || exit 1
    - name: Auth test
      run: |
        TOKEN=$(curl -s -X POST https://staging.cotrader.app/api/auth/login \
          -H "Content-Type: application/json" \
          -d '{"email":"test@test.com","password":"test123"}' | jq -r '.access_token')
        curl -f -H "Authorization: Bearer $TOKEN" https://staging.cotrader.app/api/v2/desks || exit 1
```

### Branch Strategy
```
main ─────────────────────────────── production
  └── develop ────────────────────── staging
        └── feature/xyz ──────────── PR → develop
```

- `feature/*` → PR to `develop` → runs lint + test
- `develop` merge → deploys to staging
- `develop` → PR to `main` → manual approval → deploys to production

---

## DOCKER TESTING — How To Test Locally

### Prerequisites
```bash
# Install Docker Desktop (Windows/Mac) or Docker Engine (Linux)
# Ensure docker and docker-compose are available
docker --version
docker-compose --version
```

### Start the Stack
```bash
cd eTrading/docker

# Start PostgreSQL + Redis + API
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api
```

### What Starts
- **PostgreSQL** at localhost:5432 (user: cotrader, db: cotrader)
- **Redis** at localhost:6379
- **API server** at http://localhost:8080

### First-Time Setup
```bash
# Run database migrations
docker-compose exec api alembic upgrade head

# Create first user
curl -X POST http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"nitin@cotrader.app","password":"your_password","name":"Nitin"}'
```

### Test It Works
```bash
# Health check
curl http://localhost:8080/api/v2/desks

# Login
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"nitin@cotrader.app","password":"your_password"}'

# Use the token from login response
curl -H "Authorization: Bearer <token>" http://localhost:8080/api/v2/desks
```

### Stop
```bash
docker-compose down        # Stop containers (keep data)
docker-compose down -v     # Stop + delete data volumes
```

### Troubleshooting
```bash
# View specific service logs
docker-compose logs api
docker-compose logs db

# Shell into container
docker-compose exec api bash
docker-compose exec db psql -U cotrader

# Rebuild after code changes
docker-compose build api
docker-compose up -d api
```

---

## WEEKLY SCORECARD — Go-Live Readiness

| Metric | Target | Current |
|--------|--------|---------|
| Auth system | Working login + JWT | Not started |
| PostgreSQL | Migrated, tested | SQLite only |
| Docker | Containerized, running | Not started |
| Multi-tenant | Isolated queries | Not started |
| Broker linking | Per-user flow | Single-user .env |
| Trade execution guard | Fully enforced | Partial |
| Health endpoints | /health, /ready | Not started |
| Error tracking | Sentry wired | Not started |
| SSL/TLS | HTTPS enforced | Not started |
