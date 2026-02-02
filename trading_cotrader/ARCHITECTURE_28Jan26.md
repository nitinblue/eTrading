# Trading CoTrader - Architecture & Vision Document

**Version:** 1.0  
**Created:** January 29, 2026  
**Author:** Claude + Nitin  
**Status:** Foundation Complete, Building Toward Production

---

## Executive Summary

Trading CoTrader is an **institutional-grade options trading platform** designed for serious traders who think in risk factors, not retail strategies. The platform's core differentiator is treating **trades as objects that behave**, not just values that display.

**Target User:** Independent trader managing $100K-$10M in options, who:
- Trades defined-risk strategies (iron condors, verticals, strangles)
- Needs to manage portfolio Greeks across multiple underlyings
- Wants to evaluate roll/adjustment scenarios before executing
- Requires real-time risk monitoring with customizable limits
- Demands P&L attribution to understand *why* money was made/lost

**The mental model of how I think as a trader:** 

MACRO CONTEXT
     │
     ▼
┌─────────────────┐
│  MARKET REGIME  │  ← "Is this risk-on or risk-off?"
│  Vol Regime     │  ← "Is vol high/low, expanding/compressing?"
│  Rate Regime    │  ← "Is money cheap or expensive?"
└─────────────────┘
     │
     ▼
┌─────────────────┐
│  MY POSITIONS   │  ← "How am I exposed to these regimes?"
│  Risk Factors   │  ← "Delta, Gamma, Vega, Theta by underlying"
│  P&L Impact     │  ← "If SPY -2%, I lose $X. If VIX +3pt, I make $Y"
└─────────────────┘
     │
     ▼
┌─────────────────┐
│  ACTIONS        │  ← "What do I need to do?"
│  Hedge?         │  ← "Am I outside my limits?"
│  Roll?          │  ← "Is theta decaying too fast?"
│  Adjust?        │  ← "Has my thesis changed?"
└─────────────────┘


**Revenue Model (Future):**
1. SaaS subscription for retail/semi-pro traders ($50-200/month)
2. Premium tier with advanced analytics ($500/month)
3. API access for algorithmic traders
4. White-label licensing to trading education platforms

---

## The Problem We're Solving

### What Retail Platforms Get Wrong

| Problem | ThinkorSwim/TastyTrade | Trading CoTrader |
|---------|------------------------|------------------|
| **View** | Strategy-centric ("my iron condor") | Risk-factor-centric ("my SPY delta exposure") |
| **What-If** | Separate tool, disconnected | First-class object, same as real trade |
| **P&L** | "You made $500" | "You made $200 from theta, lost $150 to delta, gained $450 from vega crush" |
| **Decisions** | Gut feel + basic Greeks | Scenario matrix + limit breaches + hedge recommendations |
| **Data** | Platform controls presentation | You control the view, objects expose their data |

### The Institutional Mindset

```
Retail Trader Thinks:          Institutional Trader Thinks:
───────────────────────        ────────────────────────────
"I have an iron condor"    →   "I have -150 SPY delta, -45 gamma, +$450 theta/day"
"It's profitable"          →   "Theta is working, but delta is hurting me"
"Should I close it?"       →   "What's my P&L at SPY ±2%? At VIX +3pt?"
"Let me check the chart"   →   "Am I within my risk limits? What hedge do I need?"
```

---

## Core Philosophy

### 1. Objects That Behave, Not Values That Display

Every entity in the system (Portfolio, Trade, Position, WhatIf) is a **domain object** with:
- **State** (prices, Greeks, P&L)
- **Behavior** (execute, close, roll, evaluate)
- **Lifecycle** (INTENT → EVALUATED → PENDING → EXECUTED → CLOSED/ROLLED)

The UI holds **references** to objects, not copies of values. Actions in the UI call **methods on the backend objects**.

### 2. Risk Factor Decomposition

The primary view is not "my trades" but "my exposure":
```
Portfolio P&L = Σ (Sensitivity × Position Size × Market Move)

P&L = Δ·dS + ½Γ·dS² + Θ·dt + V·dσ + ρ·dr + unexplained
```

Every P&L number should be decomposable into its Greek components.

### 3. What-If as First-Class Citizen

A WhatIf scenario is structurally identical to a real trade:
- Same object model
- Same Greeks calculation
- Same P&L attribution
- One-click promotion to real trade

### 4. Refresh-Ready, Streaming-Capable

Architecture assumes streaming but implements refresh:
- UI calls `GET /snapshot` on button click
- Backend fetches fresh data from broker
- Contract is identical whether data came from cache or API
- Swap `RefreshBasedProvider` → `StreamingProvider` without UI changes

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                   FRONTEND                                       │
│                          (React + AG Grid + WebSocket)                           │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                         Single-Screen Dashboard                              ││
│  │  ┌─────────────────────────────────────────────────────────────────────┐   ││
│  │  │ MARKET CONTEXT                                                       │   ││
│  │  │ Indices: SPY QQQ IWM DIA | Vol: VIX VVIX SKEW | Rates: 2s10s MOVE  │   ││
│  │  │ Commodities: /GC /CL /SI | FX: DXY EUR JPY | Regime: Risk-On/Off   │   ││
│  │  └─────────────────────────────────────────────────────────────────────┘   ││
│  │  ┌─────────────────────────────────────────────────────────────────────┐   ││
│  │  │ RISK MONITOR (by underlying)                                        │   ││
│  │  │ SPY: Δ=-150 [⚠️BREACH] Γ=-45 Θ=+$450 V=+2400 | Hedge: +150 shares  │   ││
│  │  │ QQQ: Δ=+80 [OK] Γ=-12 Θ=+$120 V=+800                               │   ││
│  │  │ PORTFOLIO: Δ=-70 Γ=-57 Θ=+$570 V=+3200                             │   ││
│  │  └─────────────────────────────────────────────────────────────────────┘   ││
│  │  ┌─────────────────────────────────────────────────────────────────────┐   ││
│  │  │ SCENARIO MATRIX                                                      │   ││
│  │  │        IV-2pt  IV-1pt  IV±0   IV+1pt  IV+2pt                        │   ││
│  │  │ SPY-2%  +$2850  +$2100  +$1350  +$600   -$150                       │   ││
│  │  │ SPY-1%  +$1600  +$1200  +$800   +$400   ±$0                         │   ││
│  │  │ SPY±0%  +$450   +$350   +$250   +$150   +$50                        │   ││
│  │  │ SPY+1%  -$700   -$500   -$300   -$100   +$100                       │   ││
│  │  │ SPY+2%  -$1850  -$1450  -$1050  -$650   -$250                       │   ││
│  │  └─────────────────────────────────────────────────────────────────────┘   ││
│  │  ┌─────────────────────────────────────────────────────────────────────┐   ││
│  │  │ POSITIONS GRID (AG Grid - editable, sortable, filterable)           │   ││
│  │  │ Sym|Type|Strike|Expiry|DTE|Qty|Bid|Ask|Δ|Γ|Θ|V|IV|P&L|P&L%|Actions │   ││
│  │  │ SPY  C   600   Jan31   5  -1  0.41 0.43 -8 -1 +4 -6 16% +$43 +51%  │   ││
│  │  │ SPY  C   605   Jan31   5  +1  0.17 0.19 +3 +1 -2 +3 15% -$27 -60%  │   ││
│  │  │ ... (grouped by trade/strategy optionally)                          │   ││
│  │  └─────────────────────────────────────────────────────────────────────┘   ││
│  │  ┌─────────────────────────────────────────────────────────────────────┐   ││
│  │  │ HEDGING BLOTTER                                                      │   ││
│  │  │ To neutralize SPY Δ: [BUY 150 SPY @ $588.25] Cost: $88K [EXECUTE]  │   ││
│  │  │ Alternative: [BUY 3 SPY 590C @ $4.20] Cost: $1.3K, adds Γ+15       │   ││
│  │  └─────────────────────────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                      │                                           │
│                        REST: GET /snapshot (on refresh)                          │
│                        WebSocket: /ws (future: continuous)                       │
└──────────────────────────────────────┼───────────────────────────────────────────┘
                                       │
┌──────────────────────────────────────┼───────────────────────────────────────────┐
│                                  BACKEND                                          │
│                              (FastAPI + Python)                                   │
│                                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                              API Layer (api.py)                              │ │
│  │  GET  /snapshot          → Complete MarketSnapshot                          │ │
│  │  POST /refresh           → Force data refresh, broadcast to WS              │ │
│  │  GET  /limits            → Current risk limits                              │ │
│  │  POST /limits            → Update risk limits                               │ │
│  │  POST /trades/{id}/execute → Execute a trade (what-if → real)              │ │
│  │  POST /trades/{id}/close   → Close a trade                                  │ │
│  │  POST /trades/{id}/roll    → Roll to new expiry/strike                      │ │
│  │  POST /whatif/create       → Create what-if scenario                        │ │
│  │  POST /whatif/evaluate     → Evaluate what-if (calculate Greeks)            │ │
│  │  WS   /ws                  → Real-time updates (future)                     │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                            │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                         Data Provider Layer                                  │ │
│  │                                                                              │ │
│  │  ┌──────────────────────┐  ┌──────────────────────┐  ┌───────────────────┐  │ │
│  │  │  RefreshBasedProvider │  │  StreamingProvider   │  │  MockDataProvider │  │ │
│  │  │  (Current)            │  │  (Future)            │  │  (Testing)        │  │ │
│  │  │  - Fetches on demand  │  │  - Maintains cache   │  │  - Static data    │  │ │
│  │  │  - Uses TastyTrade    │  │  - DXLink stream     │  │  - UI dev         │  │ │
│  │  └──────────────────────┘  └──────────────────────┘  └───────────────────┘  │ │
│  │                          All implement: async get_snapshot() → MarketSnapshot│ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                            │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                         Core Services                                        │ │
│  │                                                                              │ │
│  │  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────────┐ │ │
│  │  │  RiskAggregator    │  │  HedgeCalculator   │  │  ScenarioEngine        │ │ │
│  │  │  - Sum by underlying│  │  - Delta hedge     │  │  - Spot × Vol matrix  │ │ │
│  │  │  - Sum by expiry    │  │  - Gamma hedge     │  │  - Time decay         │ │ │
│  │  │  - Check limits     │  │  - Vega hedge      │  │  - P&L projection     │ │ │
│  │  │  - Detect breaches  │  │  - Cost comparison │  │  - Taylor expansion   │ │ │
│  │  └────────────────────┘  └────────────────────┘  └────────────────────────┘ │ │
│  │                                                                              │ │
│  │  ┌────────────────────┐  ┌────────────────────┐  ┌────────────────────────┐ │ │
│  │  │  GreeksEngine      │  │  PnLAttribution    │  │  MarketContextBuilder │ │ │
│  │  │  - Black-Scholes   │  │  - Delta P&L       │  │  - Index quotes       │ │ │
│  │  │  - IV solver       │  │  - Theta P&L       │  │  - Vol complex        │ │ │
│  │  │  - Greeks calc     │  │  - Vega P&L        │  │  - Rates/bonds        │ │ │
│  │  │  - 2nd order Greeks│  │  - Unexplained     │  │  - Commodities/FX     │ │ │
│  │  └────────────────────┘  └────────────────────┘  └────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                            │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                         Domain Layer (domain.py)                             │ │
│  │                                                                              │ │
│  │  Portfolio ─┬─ Trade ─┬─ Leg ─── Position                                   │ │
│  │             │         │                                                      │ │
│  │             │         └─ Entry/Current/Exit State                           │ │
│  │             │                                                                │ │
│  │             └─ WhatIfScenario (same structure, different type)              │ │
│  │                                                                              │ │
│  │  Trade Lifecycle: INTENT → EVALUATED → PENDING → EXECUTED → CLOSED/ROLLED  │ │
│  │  Portfolio Types: real | paper | what_if | backtest                         │ │
│  │                                                                              │ │
│  │  Key Objects:                                                               │ │
│  │  - Symbol (ticker, strike, expiry, option_type, multiplier)                 │ │
│  │  - Greeks (delta, gamma, theta, vega, rho, vanna, charm, volga)            │ │
│  │  - PnLAttribution (delta_pnl, theta_pnl, vega_pnl, gamma_pnl, unexplained) │ │
│  │  - RiskLimits (per portfolio, per underlying)                               │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                            │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                         Repository Layer                                     │ │
│  │                                                                              │ │
│  │  PortfolioRepository | TradeRepository | PositionRepository | EventLog      │ │
│  │                                                                              │ │
│  │  - to_domain() / from_domain() mapping                                      │ │
│  │  - SQLite persistence (schema.py)                                           │ │
│  │  - In-memory cache for fast access                                          │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                            │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │                         Broker Adapter Layer                                 │ │
│  │                                                                              │ │
│  │  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐  │ │
│  │  │  TastyTradeAdapter  │  │  IBKRAdapter        │  │  MockBrokerAdapter  │  │ │
│  │  │  (Primary)          │  │  (Future)           │  │  (Testing)          │  │ │
│  │  │                     │  │                     │  │                     │  │ │
│  │  │  - authenticate()   │  │  Same interface     │  │  Same interface     │  │ │
│  │  │  - get_positions()  │  │                     │  │                     │  │ │
│  │  │  - get_balance()    │  │                     │  │                     │  │ │
│  │  │  - get_quotes()     │  │                     │  │                     │  │ │
│  │  │  - submit_order()   │  │                     │  │                     │  │ │
│  │  │  - DXLink streaming │  │                     │  │                     │  │ │
│  │  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘  │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Contracts

### MarketSnapshot (The Master Object)

Everything the UI needs in one request:

```python
@dataclass
class MarketSnapshot:
    timestamp: datetime
    
    # Market Context (macro)
    market: MarketContext           # Indices, vol, rates, commodities, FX, regimes
    
    # Your positions with live data
    positions: List[PositionWithMarket]  # Bid/ask/Greeks/P&L per position
    
    # Aggregated risk
    risk_by_underlying: Dict[str, RiskBucket]  # SPY → {delta, gamma, theta, vega}
    portfolio_risk: RiskBucket      # Total portfolio Greeks
    
    # Monitoring
    limits: List[RiskLimit]
    breaches: List[LimitBreach]
    
    # Recommendations
    hedge_recommendations: List[HedgeRecommendation]
    
    # Analysis
    scenarios: Dict[str, ScenarioMatrix]  # Spot × Vol P&L matrices
    
    # Account
    account_value: Decimal
    buying_power: Decimal
    margin_used: Decimal
```

### Key Supporting Contracts

```python
@dataclass
class MarketContext:
    indices: Dict[str, IndexQuote]      # SPY, QQQ, IWM, DIA
    vix: VolatilityQuote
    vvix: VolatilityQuote
    skew: VolatilityQuote
    rates: Dict[str, RateQuote]         # US02Y, US10Y, US30Y
    curve_2s10s: Decimal                # Basis points
    move_index: Decimal                 # Bond vol
    commodities: Dict[str, FuturesQuote]  # /GC, /CL, /SI
    dxy: Decimal                        # Dollar index
    fx_pairs: Dict[str, FXQuote]
    market_regime: MarketRegime         # risk_on | risk_off | neutral
    vol_regime: VolRegime               # low_stable | elevated | high | crisis
    curve_regime: CurveRegime           # steep | normal | flat | inverted

@dataclass
class RiskBucket:
    underlying: str                     # "SPY" or "PORTFOLIO"
    delta: Decimal
    delta_dollars: Decimal              # Delta × spot × multiplier
    gamma: Decimal
    gamma_dollars: Decimal              # P&L from 1% move due to gamma
    theta: Decimal                      # Daily decay in $
    vega: Decimal                       # $ per 1pt IV change
    position_count: int
    delta_by_expiry: Dict[str, Decimal] # Term structure view
    theta_by_expiry: Dict[str, Decimal]

@dataclass
class PositionWithMarket:
    position_id: str
    symbol: str
    option_type: Optional[str]          # CALL | PUT | None for stock
    strike: Optional[Decimal]
    expiry: Optional[str]
    dte: Optional[int]
    quantity: int                       # Signed
    bid: Decimal
    ask: Decimal
    mark: Decimal
    greeks: PositionGreeks              # Already × quantity
    iv: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_pct: Decimal
    pnl_from_delta: Decimal
    pnl_from_theta: Decimal
    pnl_from_vega: Decimal
    pnl_from_gamma: Decimal
    pnl_unexplained: Decimal

@dataclass  
class LimitBreach:
    limit: RiskLimit
    current_value: Decimal
    breach_amount: Decimal
    severity: Literal["warning", "breach", "critical"]
    suggested_action: str

@dataclass
class HedgeRecommendation:
    underlying: str
    instrument: HedgeInstrument         # stock | atm_call | atm_put | straddle
    action: Literal["buy", "sell"]
    quantity: int
    estimated_price: Decimal
    estimated_cost: Decimal
    delta_impact: Decimal
    gamma_impact: Decimal
    rationale: str
```

---

## Component Inventory

### Currently Built ✅

| Component | File | Status |
|-----------|------|--------|
| Domain Objects | `core/models/domain.py` | ✅ Enhanced with WhatIf, PnL attribution |
| Database Schema | `core/database/schema.py` | ✅ Enhanced with entry/current state |
| Trade Repository | `repositories/trade.py` | ✅ Needs minor fixes |
| TastyTrade Adapter | `adapters/tastytrade_adapter.py` | ✅ DXLink Greeks streaming |
| Greeks Engine | `analytics/greeks/engine.py` | ✅ Black-Scholes, IV solver |
| Data Contracts | `backend/contracts.py` | ✅ Full MarketSnapshot |
| Data Provider | `backend/data_provider.py` | ✅ Mock + Refresh-based |
| API Layer | `backend/api_v2.py` | ✅ Basic endpoints |
| UI Dashboard | `institutional-dashboard.html` | ✅ Full single-screen layout |

### Needs Building 🔨

| Component | Priority | Description |
|-----------|----------|-------------|
| Live TastyTrade Integration | P0 | Wire RefreshBasedProvider to actual adapter |
| Quote Fetching | P0 | Bid/ask for all positions |
| Market Context Data | P1 | VIX, indices, rates from external APIs |
| Order Execution | P1 | Submit orders through TastyTrade |
| Trade Grouping | P1 | View positions grouped by trade/strategy |
| Historical P&L | P2 | Track P&L over time with attribution |
| What-If Creator UI | P2 | Build scenarios in the interface |
| Streaming Provider | P2 | DXLink continuous streaming |
| Roll Scenario Calculator | P2 | "What if I roll to next expiry?" |
| Alerts/Notifications | P3 | Push notifications on breach |
| Multi-Account | P3 | Support multiple broker accounts |
| Backtesting Engine | P3 | Test strategies on historical data |
| Mobile App | P4 | React Native companion |

---

## Milestones

### Milestone 0: Foundation (COMPLETE ✅)
- [x] Domain objects with WhatIf support
- [x] Enhanced schema with entry/current state
- [x] TastyTrade adapter with Greeks streaming
- [x] Data contracts (MarketSnapshot)
- [x] Mock data provider
- [x] Institutional UI layout

### Milestone 1: Live Connection 🎯
**Goal:** See real positions from TastyTrade in the UI

- [ ] Wire RefreshBasedProvider to TastyTradeAdapter
- [ ] Fetch positions with Greeks on refresh
- [ ] Display real P&L and Greeks
- [ ] Handle authentication/session management
- [ ] Error handling and retry logic

**Success Criteria:** Click REFRESH, see your actual TastyTrade positions with live Greeks

### Milestone 2: Risk Monitoring
**Goal:** Know when you're outside your limits

- [ ] Configurable risk limits per underlying
- [ ] Limit breach detection and alerting
- [ ] Hedge recommendations (delta neutral)
- [ ] Scenario matrix with real numbers
- [ ] P&L attribution (why did I make/lose money?)

**Success Criteria:** See breach alert when delta exceeds limit, get actionable hedge suggestion

### Milestone 3: What-If Scenarios
**Goal:** Evaluate trades before executing

- [ ] What-If creator UI (select underlying, strategy, strikes)
- [ ] Greeks calculation for hypothetical trades
- [ ] Side-by-side comparison (current vs what-if)
- [ ] One-click execute (what-if → real order)
- [ ] Roll scenario calculator

**Success Criteria:** Create iron condor what-if, see Greeks, click Execute, order goes to TastyTrade

### Milestone 4: Trade Execution
**Goal:** Execute trades from the platform

- [ ] Order builder UI
- [ ] Order preview with estimated Greeks impact
- [ ] Submit to TastyTrade API
- [ ] Order status tracking
- [ ] Trade confirmation and logging

**Success Criteria:** Build and execute a vertical spread entirely within CoTrader

### Milestone 5: Market Context
**Goal:** Full market awareness

- [ ] Live VIX/VVIX/SKEW from data provider
- [ ] Treasury rates (2Y, 10Y, 30Y)
- [ ] 2s10s spread calculation
- [ ] Commodity futures (/GC, /CL)
- [ ] Dollar index (DXY)
- [ ] Regime classification (risk-on/off, vol regime, curve regime)

**Success Criteria:** Glance at top bar, know the market environment

### Milestone 6: Historical Analysis
**Goal:** Learn from past trades

- [ ] Daily P&L snapshots
- [ ] P&L attribution over time (Greek contribution)
- [ ] Trade journal with notes
- [ ] Win/loss statistics by strategy
- [ ] Drawdown tracking

**Success Criteria:** See "This month: +$5,200. Theta contributed +$4,800, Delta -$1,200, Vega +$1,600"

### Milestone 7: Streaming & Performance
**Goal:** Real-time updates

- [ ] DXLink continuous streaming
- [ ] WebSocket push to UI
- [ ] Sub-second Greek updates
- [ ] Optimistic UI updates
- [ ] Connection resilience

**Success Criteria:** See Greeks update tick-by-tick without clicking refresh

### Milestone 8: Production Ready
**Goal:** Reliable enough to trade real money confidently

- [ ] Comprehensive error handling
- [ ] Audit logging
- [ ] Data backup/recovery
- [ ] Multi-device sync
- [ ] Security hardening
- [ ] Performance profiling
- [ ] Documentation

**Success Criteria:** Trade $100K+ with confidence the system won't fail

### Milestone 9: Monetization
**Goal:** Start making money from the product

- [ ] User authentication
- [ ] Subscription billing (Stripe)
- [ ] Feature tiers (Basic/Pro/Enterprise)
- [ ] Usage analytics
- [ ] Customer support system
- [ ] Marketing site

**Success Criteria:** 10 paying customers

---

## Technical Decisions

### Why These Choices

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend Language | Python | TastyTrade SDK, quant libraries (numpy, scipy), rapid development |
| Backend Framework | FastAPI | Async, WebSocket support, auto-docs, type hints |
| Frontend | React + AG Grid | Professional grid with cell editing, institutional standard |
| Database | SQLite → PostgreSQL | Start simple, migrate when needed |
| Broker | TastyTrade (Primary) | Good API, options-focused, retail-friendly |
| Greeks Calculation | Custom + Broker | Verify broker Greeks, detect arbitrage |
| Architecture | Refresh-first | Streaming-ready but practical for MVP |

### Non-Negotiables

1. **Objects with behavior** - Never reduce to value-only display
2. **Risk factor view** - Always aggregate by underlying, not strategy
3. **P&L attribution** - Every dollar traced to its Greek source
4. **What-If parity** - Hypothetical and real use identical code paths
5. **Single source of truth** - Backend owns state, UI holds references

---

## File Structure

```
trading_cotrader/
├── core/
│   ├── models/
│   │   └── domain.py              # Portfolio, Trade, Position, Greeks, etc.
│   ├── database/
│   │   ├── schema.py              # SQLAlchemy ORM models
│   │   └── session.py             # DB connection management
│   └── validation/
│       └── validators.py          # Input validation
│
├── adapters/
│   ├── tastytrade_adapter.py      # TastyTrade API integration
│   └── broker_adapter.py          # Base class / interface
│
├── repositories/
│   ├── portfolio.py
│   ├── trade.py
│   └── position.py
│
├── services/
│   ├── greeks_service.py          # Real-time Greeks updates
│   ├── risk_service.py            # Risk aggregation, limit monitoring
│   ├── pnl_service.py             # P&L calculation and attribution
│   └── order_service.py           # Order building and execution
│
├── analytics/
│   └── greeks/
│       └── engine.py              # Black-Scholes, IV solver
│
├── api/
│   ├── app.py                     # FastAPI application
│   ├── routes/
│   │   ├── snapshot.py            # GET /snapshot
│   │   ├── trades.py              # Trade CRUD and actions
│   │   ├── whatif.py              # What-if scenarios
│   │   └── limits.py              # Risk limits
│   └── websocket.py               # WebSocket handler
│
├── contracts/
│   └── contracts.py               # MarketSnapshot, RiskBucket, etc.
│
├── providers/
│   ├── data_provider.py           # Interface
│   ├── refresh_provider.py        # Refresh-based implementation
│   ├── streaming_provider.py      # Streaming implementation (future)
│   └── mock_provider.py           # Testing
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── MarketContext.tsx
│   │   │   ├── RiskMonitor.tsx
│   │   │   ├── ScenarioMatrix.tsx
│   │   │   ├── PositionsGrid.tsx
│   │   │   └── HedgingBlotter.tsx
│   │   └── hooks/
│   │       └── useSnapshot.ts
│   └── public/
│       └── index.html
│
├── runners/
│   ├── debug_autotrader.py        # Testing harness
│   └── validate_data.py           # Data validation
│
├── config/
│   └── settings.py                # Configuration management
│
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

---

## Quick Reference for Claude

When resuming this project, read this document first. Key points:

1. **Philosophy:** Objects that behave, not values that display
2. **User:** Serious trader thinking in risk factors (delta, gamma, theta, vega)
3. **Primary view:** Risk by underlying, not by strategy
4. **Data contract:** `MarketSnapshot` contains everything UI needs
5. **Architecture:** Refresh-based now, streaming-ready
6. **Broker:** TastyTrade via `TastyTradeAdapter`
7. **Current state:** Foundation complete, need to wire live data

**Do not ask:**
- "What are you trying to build?" → Read this document
- "How should the UI look?" → Single-screen institutional style
- "What broker?" → TastyTrade
- "Streaming or refresh?" → Refresh now, streaming architecture

**Do ask:**
- "Which milestone are we working on?"
- "What specific problem are you seeing?"
- "Should I focus on backend or frontend?"

---

## Success Definition

**Short-term (3 months):**
- Trading live with CoTrader as primary interface
- Real-time risk monitoring preventing blown accounts
- What-if scenarios evaluated before every trade

**Medium-term (12 months):**
- 100 active users
- $10K MRR
- Positive testimonials from serious traders

**Long-term (3 years):**
- Industry-recognized platform
- Multi-broker support
- Enterprise/institutional tier
- $1M+ ARR

---

*This document is the source of truth. Update it as decisions are made.*
