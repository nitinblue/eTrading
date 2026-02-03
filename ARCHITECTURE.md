# Trading Co-Trader: Architecture & Flow

> This document contains system architecture, data flows, and component diagrams.
> Uses Mermaid format for diagrams (renders in GitHub).

---

## 1. System Overview

```mermaid
graph TB
    subgraph External
        BROKER[Tastytrade API]
        MARKET[Market Data]
    end
    
    subgraph Adapters
        TA[TastytradeAdapter]
    end
    
    subgraph Services
        SYNC[PortfolioSyncService]
        EVENT[EventLogger]
        SNAP[SnapshotService]
        RISK[RiskChecker]
        RULES[RulesEngine]
    end
    
    subgraph Repositories
        PREPO[PortfolioRepository]
        POSREPO[PositionRepository]
        EREPO[EventRepository]
        TREPO[TradeRepository]
    end
    
    subgraph Database
        DB[(SQLite)]
    end
    
    subgraph AI/ML
        FEAT[FeatureExtractor]
        SUP[PatternRecognizer]
        RL[QLearningAgent]
        ADV[TradingAdvisor]
    end
    
    BROKER --> TA
    TA --> SYNC
    SYNC --> PREPO
    SYNC --> POSREPO
    PREPO --> DB
    POSREPO --> DB
    
    EVENT --> EREPO
    EREPO --> DB
    
    SNAP --> DB
    
    DB --> FEAT
    FEAT --> SUP
    FEAT --> RL
    SUP --> ADV
    RL --> ADV
```

---

## 2. Current Data Flow (What's Working)

### 2.1 Portfolio Sync Flow

```mermaid
sequenceDiagram
    participant User
    participant AutoTrader
    participant TastytradeAdapter
    participant PortfolioSyncService
    participant PortfolioRepo
    participant PositionRepo
    participant Database
    
    User->>AutoTrader: run_full_cycle()
    AutoTrader->>TastytradeAdapter: authenticate()
    TastytradeAdapter-->>AutoTrader: success
    
    AutoTrader->>PortfolioSyncService: sync_portfolio()
    PortfolioSyncService->>TastytradeAdapter: get_account_balance()
    TastytradeAdapter-->>PortfolioSyncService: balance data
    
    PortfolioSyncService->>TastytradeAdapter: get_positions()
    TastytradeAdapter-->>PortfolioSyncService: positions[]
    
    Note over PortfolioSyncService: BUG: May create new portfolio<br/>instead of finding existing
    
    PortfolioSyncService->>PortfolioRepo: get_by_account(broker, account_id)
    PortfolioRepo->>Database: SELECT
    Database-->>PortfolioRepo: portfolio or None
    
    alt Portfolio not found
        PortfolioSyncService->>PortfolioRepo: create_from_domain()
        Note right of PortfolioRepo: Creates duplicate!
    else Portfolio found
        PortfolioSyncService->>PortfolioRepo: update_from_domain()
    end
    
    PortfolioSyncService->>PositionRepo: delete_by_portfolio()
    PositionRepo->>Database: DELETE
    
    loop For each position
        PortfolioSyncService->>PositionRepo: create_from_domain()
        PositionRepo->>Database: INSERT
    end
    
    PortfolioSyncService-->>AutoTrader: SyncResult
```

### 2.2 Event Logging Flow

```mermaid
sequenceDiagram
    participant User
    participant EventLogger
    participant TradeRepo
    participant EventRepo
    participant Database
    
    User->>EventLogger: log_trade_opened(underlying, strategy, rationale)
    
    EventLogger->>EventLogger: create Trade object (status=INTENT)
    EventLogger->>TradeRepo: create_from_domain(trade)
    TradeRepo->>Database: INSERT trade
    
    EventLogger->>EventLogger: create TradeEvent object
    EventLogger->>EventRepo: create_from_domain(event)
    EventRepo->>Database: INSERT event
    
    EventLogger-->>User: LogResult(trade_id, event_id)
```

### 2.3 Snapshot Flow (For ML)

```mermaid
sequenceDiagram
    participant AutoTrader
    participant SnapshotService
    participant PositionRepo
    participant Database
    
    AutoTrader->>SnapshotService: capture_daily_snapshot(portfolio, positions)
    
    SnapshotService->>SnapshotService: Calculate metrics
    Note over SnapshotService: total_equity, delta, theta<br/>pnl, position_count
    
    SnapshotService->>Database: INSERT daily_performance
    SnapshotService->>Database: INSERT greeks_history (per position)
    
    SnapshotService-->>AutoTrader: success
    
    Note over Database: Data accumulates for ML training
```

---

## 3. Future Data Flow (After Integration)

### 3.1 Complete Trading Cycle with AI

```mermaid
graph TB
    subgraph "1. Data Collection"
        SYNC[Sync from Broker]
        SNAP[Daily Snapshot]
        EVENT[Log Events]
    end
    
    subgraph "2. Analysis"
        RISK[Risk Analysis]
        WHATIF[What-If Scenarios]
        RULES[Exit Rules Check]
    end
    
    subgraph "3. ML Training"
        FEAT[Feature Extraction]
        TRAIN[Model Training]
    end
    
    subgraph "4. Recommendations"
        SUP[Pattern Recognition]
        RL[RL Agent]
        ADV[Trading Advisor]
    end
    
    subgraph "5. Action"
        DISPLAY[Display to User]
        APPROVE[User Approval]
        EXEC[Execute Trade]
    end
    
    SYNC --> SNAP
    SNAP --> FEAT
    EVENT --> FEAT
    FEAT --> TRAIN
    
    SYNC --> RISK
    RISK --> WHATIF
    WHATIF --> RULES
    
    TRAIN --> SUP
    TRAIN --> RL
    SUP --> ADV
    RL --> ADV
    RULES --> ADV
    
    ADV --> DISPLAY
    DISPLAY --> APPROVE
    APPROVE --> EXEC
    EXEC --> EVENT
```

### 3.2 ML Data Pipeline

```mermaid
graph LR
    subgraph "Data Sources"
        E[Trade Events]
        S[Portfolio Snapshots]
        G[Greeks History]
        P[Positions]
    end
    
    subgraph "Feature Engineering"
        MF[Market Features]
        PF[Position Features]
        PtF[Portfolio Features]
    end
    
    subgraph "Dataset"
        X[Feature Matrix X]
        Y[Labels y]
    end
    
    subgraph "Models"
        DT[Decision Tree<br/>Supervised]
        QL[Q-Learning<br/>RL]
    end
    
    E --> MF
    E --> Y
    S --> PtF
    G --> PF
    P --> PF
    
    MF --> X
    PF --> X
    PtF --> X
    
    X --> DT
    X --> QL
    Y --> DT
```

---

## 4. Database Schema Overview

```mermaid
erDiagram
    PORTFOLIO ||--o{ POSITION : contains
    PORTFOLIO ||--o{ TRADE : has
    PORTFOLIO ||--o{ ORDER : has
    PORTFOLIO ||--o{ DAILY_PERFORMANCE : tracks
    
    TRADE ||--o{ LEG : contains
    TRADE ||--o{ TRADE_EVENT : generates
    TRADE }o--|| STRATEGY : uses
    
    POSITION }o--|| SYMBOL : references
    POSITION ||--o{ GREEKS_HISTORY : tracks
    LEG }o--|| SYMBOL : references
    
    TRADE_EVENT }o--o{ RECOGNIZED_PATTERN : matches
    
    PORTFOLIO {
        string id PK
        string name
        string broker
        string account_id
        decimal cash_balance
        decimal buying_power
        decimal portfolio_delta
        decimal portfolio_theta
    }
    
    POSITION {
        string id PK
        string portfolio_id FK
        string symbol_id FK
        int quantity
        decimal average_price
        decimal current_price
        decimal delta
        decimal theta
    }
    
    TRADE {
        string id PK
        string portfolio_id FK
        string underlying_symbol
        string trade_type
        string trade_status
        decimal max_risk
        boolean is_open
    }
    
    TRADE_EVENT {
        string event_id PK
        string trade_id FK
        string event_type
        json market_context
        json decision_context
        json outcome
    }
    
    DAILY_PERFORMANCE {
        string id PK
        string portfolio_id FK
        date date
        decimal total_equity
        decimal daily_pnl
        decimal portfolio_delta
    }
```

---

## 5. Module Dependencies

```mermaid
graph TD
    subgraph "Config Layer"
        SETTINGS[settings.py]
        RISKCONF[risk_config.yaml]
    end
    
    subgraph "Core Layer"
        DOMAIN[domain.py]
        EVENTS[events.py]
        SCHEMA[schema.py]
        SESSION[session.py]
    end
    
    subgraph "Repository Layer"
        BASEREPO[base.py]
        PORTFOLIOREPO[portfolio.py]
        POSITIONREPO[position.py]
        TRADEREPO[trade.py]
        EVENTREPO[event.py]
    end
    
    subgraph "Service Layer"
        SYNC[portfolio_sync.py]
        EVENTLOG[event_logger.py]
        SNAPSHOT[snapshot_service.py]
        RISKCHECK[risk_checker.py]
    end
    
    subgraph "Adapter Layer"
        TASTY[tastytrade_adapter.py]
    end
    
    subgraph "Runner Layer"
        AUTO[auto_trader.py]
    end
    
    SETTINGS --> TASTY
    RISKCONF --> RISKCHECK
    
    DOMAIN --> SCHEMA
    EVENTS --> SCHEMA
    SESSION --> SCHEMA
    
    BASEREPO --> SESSION
    PORTFOLIOREPO --> BASEREPO
    POSITIONREPO --> BASEREPO
    TRADEREPO --> BASEREPO
    EVENTREPO --> BASEREPO
    
    SYNC --> PORTFOLIOREPO
    SYNC --> POSITIONREPO
    SYNC --> TASTY
    
    EVENTLOG --> TRADEREPO
    EVENTLOG --> EVENTREPO
    
    SNAPSHOT --> PORTFOLIOREPO
    
    AUTO --> SYNC
    AUTO --> EVENTLOG
    AUTO --> SNAPSHOT
    AUTO --> RISKCHECK
```

---

## 6. Component Status

| Component | Status | Notes |
|-----------|--------|-------|
| TastytradeAdapter | ✅ Working | Auth, positions, balance |
| PortfolioSyncService | ⚠️ Bug | May create duplicate portfolios |
| EventLogger | ✅ Working | Logs trade intents/events |
| SnapshotService | ✅ Working | Daily snapshots for ML |
| RiskChecker | ✅ Working | Basic risk checks |
| PortfolioRiskAnalyzer | 📋 New | VaR, correlation - needs integration |
| RulesEngine | 📋 New | Exit rules - needs integration |
| FeatureExtractor | 📋 New | ML features - needs integration |
| PatternRecognizer | 📋 New | Supervised learning - needs data |
| QLearningAgent | 📋 New | RL agent - needs data |
| TradingAdvisor | 📋 New | Combined advisor - needs integration |

---

## 7. File Organization

```
trading_cotrader/
├── PROJECT_STATUS.yaml      # YOU edit - current state
├── ARCHITECTURE.md          # This file - diagrams/flows
│
├── adapters/                # External integrations
├── analytics/               # Your existing analytics
├── config/                  # Configuration
├── core/                    # Domain models, DB schema
├── repositories/            # Data access
├── services/                # Business logic
├── ai_cotrader/            # ML/RL modules
└── runners/
    └── auto_trader.py       # Main entry point
```

---

*Last updated: 2026-01-24*
