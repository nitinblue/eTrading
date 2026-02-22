# Trading Co-Trader: Architecture & Data Flow

> Source of truth for system architecture and data flows.
> Uses Mermaid format for diagrams (renders in GitHub/VS Code).
> Last updated: 2026-02-21 (Session 28)

---

## 1. Position Data Flow: Broker to Screen

This is the critical path. Every number you see on screen traces back through this flow.

```mermaid
sequenceDiagram
    participant TT as TastyTrade API
    participant DX as DXLink (Streaming)
    participant AD as TastytradeAdapter
    participant SS as PortfolioSyncService
    participant DB as SQLite DB
    participant CM as ContainerManager
    participant API as FastAPI
    participant UI as React Frontend

    Note over TT,UI: === SYNC CYCLE (every 60s in monitoring state) ===

    AD->>TT: account.get_positions(include_marks=True)
    TT-->>AD: positions[] (qty, avg_open_price, mark_price, direction)

    AD->>DX: Subscribe Greeks for option symbols
    DX-->>AD: delta, gamma, theta, vega, IV (current only)

    Note over AD: Creates dm.Position objects:<br/>entry_price = average_open_price<br/>current_price = mark_price<br/>quantity = signed (+long, -short)<br/>total_cost = entry * qty * multiplier (signed)<br/>greeks = current from DXLink

    AD-->>SS: List[dm.Position]

    SS->>DB: DELETE all positions for this portfolio_id
    loop For each position
        SS->>DB: INSERT PositionORM (entry, current, qty, Greeks, total_pnl)
    end
    SS->>DB: UPDATE PortfolioORM (equity, cash, aggregate Greeks, total_pnl)

    Note over CM: === CONTAINER REFRESH ===

    CM->>DB: SELECT PositionORM WHERE portfolio_id matches bundle
    Note over CM: Bundle matched by broker_firm + account_number<br/>(NOT first-found — that was the duplication bug)
    DB-->>CM: positions[]

    CM->>CM: Compute P&L per position:<br/>(current - entry) * qty * multiplier
    CM->>CM: Aggregate RiskFactors per underlying:<br/>sum delta, gamma, theta, vega

    Note over API,UI: === API RESPONSE ===

    UI->>API: GET /api/v2/broker-positions
    API->>CM: bundle.positions.to_grid_rows()
    CM-->>API: [{symbol, qty, entry, mark, delta, pnl, ...}]
    API-->>UI: JSON response

    UI->>API: GET /api/v2/risk/factors
    API->>CM: bundle.risk_factors.to_grid_rows()
    CM-->>API: [{underlying, delta, gamma, theta, vega, delta_$}]
    API-->>UI: JSON response

    UI->>API: GET /api/v2/portfolios
    API->>DB: SELECT PortfolioORM
    DB-->>API: [{equity, cash, Greeks, pnl}]
    API-->>UI: JSON response
```

### What TastyTrade Provides vs What We Compute

| Data Point | Source | Notes |
|-----------|--------|-------|
| Entry price | TT `average_open_price` | Per-contract price at fill |
| Current price | TT `mark_price` | Mid of bid/ask |
| Quantity + direction | TT `quantity_direction` | Long/Short enum |
| Current Greeks | DXLink streaming | Real-time delta/gamma/theta/vega |
| **Entry Greeks** | **NOT AVAILABLE** | TT has no historical Greeks API |
| **P&L** | **We compute** | `(current - entry) * qty * multiplier` |
| **P&L attribution** | **NOT YET** | Needs entry Greeks + daily snapshots |

---

## 2. Container Architecture

```mermaid
graph TB
    subgraph "risk_config.yaml (5 real portfolios)"
        RC_TT["tastytrade<br/>broker=tastytrade<br/>account=5WZ78765"]
        RC_FI["fidelity_ira<br/>broker=fidelity<br/>account=259510977"]
        RC_FP["fidelity_personal<br/>broker=fidelity<br/>account=Z71212342"]
        RC_ZE["zerodha<br/>broker=zerodha"]
        RC_ST["stallion<br/>broker=stallion<br/>account=SACF5925"]
    end

    subgraph "ContainerManager (in-memory)"
        subgraph "Bundle: tastytrade"
            B1_PF["PortfolioContainer<br/>equity, cash, Greeks"]
            B1_PS["PositionContainer<br/>9 positions + P&L"]
            B1_RF["RiskFactorContainer<br/>per-underlying Greeks"]
            B1_TR["TradeContainer<br/>agent-booked trades"]
        end
        subgraph "Bundle: fidelity_ira"
            B2["Empty — no API broker"]
        end
        subgraph "Bundle: stallion"
            B5["INR fund — separate currency"]
        end
    end

    subgraph "SQLite DB"
        DB_P["PortfolioORM<br/>14 rows (5 real + 5 whatif + 4 research)"]
        DB_POS["PositionORM<br/>9 rows (all TastyTrade)"]
        DB_TR["TradeORM<br/>0 rows (no agent trades yet)"]
    end

    RC_TT -->|"broker+account match"| B1_PF
    DB_P -->|"WHERE broker=tastytrade<br/>AND account=5WZ78765"| B1_PF
    DB_POS -->|"WHERE portfolio_id IN bundle.portfolio_ids"| B1_PS
    B1_PS -->|"aggregate by underlying"| B1_RF
```

### Bundle-to-DB Matching (Fixed Bug)

**Before (broken):** `load_from_repositories()` grabbed the first portfolio from DB for every bundle. All 5 bundles got TastyTrade's portfolio_id → 5x duplication.

**After (fixed):** Each bundle stores `broker_firm` + `account_number` from risk_config.yaml. DB lookup uses `WHERE broker = ? AND account_id = ?`. Only the matching bundle gets positions.

---

## 3. Real Trades vs Agent Trades vs WhatIf

```mermaid
graph LR
    subgraph "Data Sources"
        BROKER["TastyTrade Broker"]
        AGENT["Agents/Screeners"]
        USER["User (Trading Sheet)"]
    end

    subgraph "DB Tables"
        POS["PositionORM<br/>(Live Positions)"]
        TRADE_REAL["TradeORM<br/>type=paper/live"]
        TRADE_WI["TradeORM<br/>type=what_if"]
    end

    subgraph "Frontend Sections"
        UI_LIVE["Live Positions<br/>(always shown)"]
        UI_AGENT["Agent-Booked Trades<br/>(shown when non-empty)"]
        UI_WI["WhatIf Trades<br/>(Trading Sheet only)"]
    end

    BROKER -->|"PortfolioSyncService<br/>clear+rebuild every 60s"| POS
    AGENT -->|"TradeBookingService"| TRADE_REAL
    USER -->|"POST /add-whatif"| TRADE_WI

    POS -->|"GET /broker-positions"| UI_LIVE
    TRADE_REAL -->|"GET /positions"| UI_AGENT
    TRADE_WI -->|"GET /trading-sheet"| UI_WI
```

| Concept | DB Table | Created By | Lifecycle | Has Entry Greeks? |
|---------|----------|-----------|-----------|-------------------|
| **Live Positions** | PositionORM | Broker sync | Destroyed + recreated every sync | No |
| **Agent Trades** | TradeORM (paper/live) | Agents/Screeners | Persist until closed | Yes (captured at booking) |
| **WhatIf Trades** | TradeORM (what_if) | User via UI | Persist until booked or deleted | Yes (computed at creation) |

---

## 4. Workflow Engine Lifecycle

```mermaid
stateDiagram-v2
    [*] --> INITIALIZING
    INITIALIZING --> MARKET_ANALYSIS: boot complete
    MARKET_ANALYSIS --> PORTFOLIO_STATE: market data fetched
    PORTFOLIO_STATE --> MONITORING: state loaded

    MONITORING --> OPPORTUNITY_SCAN: scheduled scan
    MONITORING --> EOD_EVALUATION: market close

    OPPORTUNITY_SCAN --> RECOMMENDATION: opportunities found
    RECOMMENDATION --> PENDING_APPROVAL: trades proposed
    PENDING_APPROVAL --> EXECUTION: user approves
    EXECUTION --> MONITORING: trades executed

    EOD_EVALUATION --> MONITORING: no action needed

    note right of MONITORING
        Every 60s:
        1. Sync broker positions
        2. Refresh containers
        3. Check capital utilization
    end note
```

### Engine Boot Sequence

```
1. _init_container_manager()     → Create bundles from risk_config.yaml
2. _authenticate_adapters()      → Auth TastyTrade API
3. _sync_broker_positions()      → Fetch positions → DB
4. _refresh_containers()         → Load DB → ContainerManager
5. Start FastAPI web server      → Serve API on :8080
6. Start APScheduler             → Monitor every 60s
```

---

## 5. P&L Calculation

### Formula (Fixed 2026-02-21)

```
unrealized_pnl = (current_price - entry_price) * quantity * multiplier
```

- **Long call** bought at $5, now at $3: `(3 - 5) * 1 * 100 = -$200`
- **Short put** sold at $7.47, now at $5.05: `(5.05 - 7.47) * (-2) * 100 = +$484`
- **Long stock** at $54.50, now at $52.79: `(52.79 - 54.50) * 100 * 1 = -$171`

### Previous Bug (Sessions 25-27)

Old formula: `current_price * qty * multiplier - abs(total_cost)`
- Short positions always showed massive losses because total_cost was unsigned
- Portfolio P&L was **-$6,260.50** when actual was **-$162.50**

---

## 6. Key File Map

| Layer | File | Purpose |
|-------|------|---------|
| **Adapter** | `adapters/tastytrade_adapter.py` | TastyTrade API + DXLink Greeks |
| **Sync** | `services/portfolio_sync.py` | Broker → DB (clear+rebuild) |
| **DB Schema** | `core/database/schema.py` | 21 ORM tables |
| **Domain** | `core/models/domain.py` | Position, Trade, Portfolio, Greeks |
| **Containers** | `containers/container_manager.py` | In-memory bundles, DB loading |
| **Bundle** | `containers/portfolio_bundle.py` | Per-portfolio container group |
| **Position Container** | `containers/position_container.py` | Position state + P&L computation |
| **Risk Factors** | `containers/risk_factor_container.py` | Per-underlying Greeks aggregation |
| **Engine** | `workflow/engine.py` | State machine + sync + refresh |
| **API v2** | `web/api_v2.py` | FastAPI endpoints for frontend |
| **Trading Sheet** | `web/api_trading_sheet.py` | 4 endpoints for trading view |
| **Config** | `config/risk_config.yaml` | 15 portfolios, risk limits |
| **Frontend** | `frontend/src/pages/PortfolioPage.tsx` | Portfolio + Positions + Risk |

---

## 7. Known Gaps

| Gap | Impact | Fix Needed |
|-----|--------|------------|
| No entry Greeks | Can't do P&L attribution (delta/theta/vega breakdown) | Capture Greeks at first sync of new position |
| No daily snapshots | Can't track Greeks evolution over time | PositionGreeksSnapshotORM exists but unpopulated |
| VaR not computed fresh | Shows stale DB value | Wire VaR calculator into sync cycle |
| No position health | Missing % of max profit, breakeven distance | Compute from entry/current/strikes |
| Fidelity/Zerodha no API | Positions only for TastyTrade | Manual entry or adapter stubs |

---

*This document is the single source of truth for data flow. Update it when the flow changes.*
