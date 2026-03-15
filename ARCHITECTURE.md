# CoTrader Architecture — SaaS Design
# Date: 2026-03-14 (Session 41)
# Purpose: Production architecture for multi-user, multi-broker, multi-market.

---

## CURRENT STATE

```
Single process. Single user. SQLite. In-memory state.

Python process (run_workflow.py)
  ├── FastAPI (port 8080)
  │    ├── React frontend (static)
  │    └── API endpoints (/api/v2/*)
  ├── WorkflowEngine (state machine)
  │    ├── 5 agents (Scout, Steward, Sentinel, Maverick, Atlas)
  │    ├── APScheduler (30min, 2min 0DTE, EOD)
  │    └── MarketAnalyzer (stateless library)
  ├── SQLite (trading_cotrader.db — 25 tables)
  └── Broker adapter (TastyTrade only)
```

---

## TARGET STATE

```
┌──────────────────────────────────────────────────────────┐
│                    LOAD BALANCER                          │
│                 (nginx / cloud ALB)                       │
│                   HTTPS + JWT auth                        │
└─────────┬──────────────────────────┬─────────────────────┘
          │                          │
┌─────────▼──────────┐    ┌─────────▼──────────┐
│   API SERVER (N)    │    │  FRONTEND (CDN)     │
│   FastAPI stateless │    │  React SPA           │
│   JWT middleware    │    │  S3 / CloudFront     │
│   Read/write DB    │    └─────────────────────┘
└─────────┬──────────┘
          │
┌─────────▼──────────┐    ┌─────────────────────┐
│   TASK QUEUE        │───▷│  Redis               │
│   (Celery / ARQ)    │    │  - task broker        │
│                     │    │  - session cache      │
│  Per-user tasks:    │    │  - rate limiting      │
│  - scan(user_id)    │    └─────────────────────┘
│  - mark(user_id)    │
│  - ml_learn(uid)    │    ┌─────────────────────┐
│  - health(uid)      │───▷│  PostgreSQL           │
└─────────┬──────────┘    │  - tenant-scoped      │
          │               │  - connection pool     │
┌─────────▼──────────┐    │  - JSONB columns      │
│   WORKER (N)        │    └─────────────────────┘
│   Agent pipeline    │
│   Per-user context  │
│   MA library        │
│   Broker sessions   │
│   (per-user, temp)  │
└────────────────────┘
```

---

## KEY DESIGN DECISIONS

### 1. API Server is STATELESS
No in-memory engine context. Every request: authenticate → read DB → compute → respond.
Horizontally scalable. Any API instance handles any user.

### 2. Workers run agent pipelines
One Celery task per user per cycle. Worker loads user config + broker token → runs agents → writes results to PostgreSQL → discards state.

### 3. Broker sessions are per-user, short-lived
User authenticates with broker → encrypted token stored in DB.
Worker loads token → creates session → runs pipeline → discards.
No persistent broker connections.

### 4. MA library is shared, stateless
One MarketAnalyzer instance per task. Broker providers injected per-user.
No cross-user contamination. MA never stores state.

### 5. Frontend is static SPA
React built → CDN. All data via API + JWT. Optional WebSocket for real-time.

### 6. Currency and timezone are first-class
Every broker connection has currency + timezone. Desks inherit from broker.
No cross-currency mixing within a desk. P&L in local currency per desk.

---

## DATA MODEL

### Multi-Tenant Tables

```
users
  ├── broker_connections (per broker, encrypted tokens)
  ├── portfolios (per desk, tenant_id scoped)
  │    ├── trades
  │    │    ├── legs
  │    │    └── trade_events
  │    ├── positions
  │    └── daily_performance
  ├── ml_state (bandits, thresholds, drift per user)
  ├── system_events (Atlas health log per user)
  └── research_snapshots (cached MA data per user)
```

All existing tables get `tenant_id UUID REFERENCES users(id)`.
All queries scoped by `tenant_id = current_user.id`.

### Broker Connections Table

```sql
CREATE TABLE broker_connections (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    broker_name VARCHAR(50) NOT NULL,  -- tastytrade, dhan, zerodha
    account_id VARCHAR(100),
    encrypted_token TEXT,              -- AES-256 encrypted
    token_expires_at TIMESTAMP,
    market VARCHAR(10) NOT NULL,       -- US, INDIA
    currency VARCHAR(5) NOT NULL,      -- USD, INR
    timezone VARCHAR(50) NOT NULL,     -- US/Eastern, Asia/Kolkata
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## SCHEDULING — Per-User, Per-Market

Users trade in different timezones. Same system handles both.

| Task | US (ET) | India (IST) | Frequency |
|------|---------|-------------|-----------|
| scan_and_propose | 9:30 AM - 4:00 PM | 9:15 AM - 3:30 PM | Every 30 min |
| mark_to_market | 9:30 AM - 4:00 PM | 9:15 AM - 3:30 PM | Every 30 min |
| intraday_0dte | 9:30 AM - 4:00 PM | 9:15 AM - 3:30 PM (Thu/Wed) | Every 2 min |
| overnight_risk | 3:30 PM ET | 3:00 PM IST | Once |
| daily_report | 4:15 PM ET | 3:45 PM IST | Once |
| ml_learning | 4:30 PM ET | 4:00 PM IST | Daily |

Per-user schedules created based on their broker connections.

---

## BROKER INTEGRATION

### Supported Brokers

| Broker | Market | Auth | SDK | Status |
|--------|--------|------|-----|--------|
| TastyTrade | US | Session token | `tastytrade` | Production |
| Dhan | India | API key + access token | `dhanhq` | MA providers ready |
| Zerodha | India | Kite API key + access token | `kiteconnect` | MA providers ready |

### Session Flow

```
User clicks "Connect Broker"
  → Redirects to broker login (or API key entry)
  → Token received
  → Encrypted (AES-256) and stored in broker_connections
  → On each pipeline run:
      Load token → decrypt → create MA providers → run agents → discard
```

---

## MIGRATION PATH

### Phase 0: Production-Ready Single User (NOW)
- [x] Trade execution rail guard (S27)
- [ ] PostgreSQL migration
- [ ] Alembic migrations
- [ ] Docker containerization
- [ ] Wire Dhan + Zerodha into adapter
- [ ] Multi-leg order generation

### Phase 1: Auth (Single User, Protected)
- [ ] User model + JWT
- [ ] Login page
- [ ] API middleware

### Phase 2: Multi-Tenant
- [ ] tenant_id on all tables
- [ ] Scoped queries
- [ ] Per-user broker connections
- [ ] BrokerSessionManager

### Phase 3: Background Workers
- [ ] Celery + Redis
- [ ] Agent pipeline as tasks
- [ ] Per-user scheduling

### Phase 4: Scale
- [ ] Multiple API instances
- [ ] CDN for frontend
- [ ] WebSocket
- [ ] Monitoring (Sentry, Prometheus)

---

## WHAT NOT TO BUILD YET

- Mobile app (web works on mobile)
- Social features (sharing, following)
- Backtesting (MA has no harness)
- Multi-currency P&L conversion (keep per-desk currency)
- Real-time streaming to frontend (polling is fine)
- AI chatbot / MCP (later)
