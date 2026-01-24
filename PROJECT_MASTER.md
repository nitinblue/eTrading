# Trading Co-Trader: Master Project Document

> **Purpose**: Single source of truth for architecture, capabilities, progress tracking, and decision-making.
> **Last Updated**: January 24, 2026
> **Philosophy**: Build solid foundations with atomic concepts. Complex emerges from simple done right.

---

## Table of Contents

1. [Vision & First Principles](#1-vision--first-principles)
2. [Technical Architecture](#2-technical-architecture)
3. [Trading Platform Capabilities](#3-trading-platform-capabilities)
4. [Module Specifications](#4-module-specifications)
5. [Progress Tracker](#5-progress-tracker)
6. [Decision Log](#6-decision-log)
7. [Implementation Priorities](#7-implementation-priorities)
8. [Open Questions](#8-open-questions)

---

## 1. Vision & First Principles

### 1.1 What Problem Are We Solving?

Options trading suffers from:
- **Information overload**: Too many metrics, not enough actionable insights
- **Reactive decision-making**: Traders respond to markets rather than having pre-planned responses
- **Inconsistent execution**: Good analysis, poor follow-through
- **Learning stagnation**: No systematic capture of what worked/didn't work

### 1.2 Core Philosophy

| Principle | What It Means | How It Manifests |
|-----------|---------------|------------------|
| **Objects over values** | Everything that can be reasoned about should be an object | Trades, risks, what-ifs are first-class objects, not just numbers |
| **Pre-computed decisions** | Know what you'll do before it happens | Exit rules defined at entry, adjustments pre-planned |
| **DAG-based computation** | Dependencies flow clearly | Change one input, everything downstream recomputes |
| **Learn from yourself** | Your history is your edge | Event sourcing captures every decision for pattern recognition |
| **Simple atoms, complex emergence** | Master the basics | Greeks, probability, expected value - combined intelligently |

### 1.3 What Success Looks Like

**Phase 1 (Manual but Informed)**: Trader uses system for analysis, makes manual decisions
**Phase 2 (Assisted)**: System suggests actions, trader approves/modifies
**Phase 3 (Autonomous with Oversight)**: System executes within parameters, trader monitors

---

## 2. Technical Architecture

### 2.1 Current State (✅ Built)

```
trading_cotrader/
├── adapters/                    # Broker integrations
│   ├── tastytrade_adapter.py   ✅ Working - positions, balance, auth
│   └── tastytrade_broker.yaml  ✅ Config with env var resolution
│
├── analytics/                   # Analytics modules (EXISTING)
│   ├── pricing/
│   │   └── option_pricer.py    ✅ Black-Scholes implementation
│   ├── greeks/
│   │   └── engine.py           ✅ Greeks calculations
│   ├── volatility_surface.py   ✅ IV surface analysis
│   ├── functional_portfolio.py ✅ Functional portfolio analytics
│   └── pricing/pnl_calculator.py ✅ P&L calculations
│
├── config/
│   ├── settings.py             ✅ Pydantic settings, .env support
│   ├── risk_config.yaml        ✅ NEW - Risk parameters YAML
│   └── risk_config_loader.py   ✅ NEW - Typed config loader
│
├── core/
│   ├── database/
│   │   ├── schema.py           ✅ Full ORM schema (11 tables)
│   │   └── session.py          ✅ Session management, transactions
│   ├── models/
│   │   ├── domain.py           ✅ Core domain models
│   │   ├── events.py           ✅ Event sourcing models
│   │   ├── calculations.py     ✅ Calculation models
│   │   └── what_if.py          ✅ NEW - What-If scenario object
│   └── validation/
│       └── validators.py       ✅ Position & trade validation
│
├── repositories/               ✅ Repository pattern implemented
│   ├── base.py                 ✅ Generic CRUD operations
│   ├── portfolio.py            ✅ Portfolio repository
│   ├── position.py             ✅ Position & Symbol repositories
│   ├── trade.py                ✅ Trade & Strategy repositories
│   └── event.py                ✅ Event & Pattern repositories
│
├── services/
│   ├── position_sync.py        ✅ Clear-and-rebuild sync strategy
│   ├── greeks_service.py       ✅ Greeks service
│   ├── event_logger.py         ✅ Event logging service
│   ├── event_analytics.py      ✅ Event analytics
│   ├── risk/                   ✅ NEW - Risk module
│   │   ├── var_calculator.py   ✅ VaR calculations
│   │   ├── portfolio_risk.py   ✅ Portfolio risk analyzer
│   │   ├── correlation.py      ✅ Correlation analysis
│   │   ├── concentration.py    ✅ Concentration limits
│   │   ├── margin.py           ✅ Margin estimation
│   │   └── limits.py           ✅ Risk limits manager
│   └── position_mgmt/          ✅ NEW - Position management
│       └── rules_engine.py     ✅ Exit rules engine
│
├── cli/
│   └── log_event.py            ✅ CLI for logging events
│
├── ai_cotrader/                # AI/ML Module (EXISTING - needs data)
│   ├── feature_engineering/    ⚠️ Structure exists, needs implementation
│   ├── learning/               ⚠️ Structure exists, needs implementation
│   └── models/                 ⚠️ Structure exists, needs trained models
│
├── runners/
│   ├── sync_portfolio.py       ✅ Main sync workflow
│   ├── sync_with_greeks.py     ✅ Sync with Greeks
│   ├── validate_data.py        ✅ Data validation runner
│   ├── portfolio_analyzer.py   ✅ Portfolio analysis
│   └── auto_trader.py          ⚠️ Auto trading (needs completion)
│
└── scripts/
    └── setup_database.py       ✅ DB initialization
```

### 2.2 Target State (📋 To Build)

```
trading_cotrader/
├── adapters/
│   ├── tastytrade_adapter.py   ✅
│   ├── market_data/            📋 NEW
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract market data provider
│   │   ├── dxfeed_adapter.py   # Real-time quotes via Tastytrade
│   │   └── cache.py            # Quote caching with TTL
│   └── tastytrade_broker.yaml  ✅
│
├── config/                     ✅
│
├── core/
│   ├── database/               ✅
│   ├── models/
│   │   ├── domain.py           ✅
│   │   ├── events.py           ✅
│   │   ├── risk.py             📋 NEW - Risk objects
│   │   └── analytics.py        📋 NEW - Analytics objects
│   ├── validation/             ✅
│   └── computation/            📋 NEW
│       ├── __init__.py
│       ├── dag.py              # DAG computation engine
│       └── reactive.py         # Reactive value propagation
│
├── repositories/               ✅
│
├── services/
│   ├── position_sync.py        ✅
│   │
│   ├── risk/                   📋 NEW - Risk Management Module
│   │   ├── __init__.py
│   │   ├── var_calculator.py   # Value at Risk calculations
│   │   ├── portfolio_risk.py   # Portfolio-level risk assessment
│   │   ├── correlation.py      # Correlation analysis
│   │   ├── concentration.py    # Concentration risk checks
│   │   ├── margin.py           # Margin requirement estimation
│   │   └── limits.py           # Risk limit enforcement
│   │
│   ├── pricing/                📋 NEW - Options Pricing Module
│   │   ├── __init__.py
│   │   ├── black_scholes.py    # BS model implementation
│   │   ├── greeks.py           # Greeks calculations
│   │   ├── implied_vol.py      # IV calculations & smile
│   │   ├── probability.py      # POP, expected move
│   │   └── scenarios.py        # What-if scenario engine
│   │
│   ├── market/                 📋 NEW - Market Analysis Module
│   │   ├── __init__.py
│   │   ├── regime.py           # VIX regime, trend detection
│   │   ├── iv_rank.py          # IV rank/percentile tracking
│   │   ├── earnings.py         # Earnings calendar
│   │   └── events.py           # Economic event calendar
│   │
│   ├── strategy/               📋 NEW - Strategy Module
│   │   ├── __init__.py
│   │   ├── catalog.py          # Strategy definitions & docs
│   │   ├── constructor.py      # Build trades from strategies
│   │   ├── selector.py         # Which strategy for conditions
│   │   └── concentration.py    # Strategy concentration tracking
│   │
│   ├── position_mgmt/          📋 NEW - Position Management Module
│   │   ├── __init__.py
│   │   ├── rules_engine.py     # Exit rules, adjustment triggers
│   │   ├── adjustments.py      # Roll, add leg, hedge
│   │   ├── profit_taking.py    # Profit target management
│   │   └── stop_loss.py        # Stop loss management
│   │
│   ├── recommendations/        📋 NEW - Trade Recommendations
│   │   ├── __init__.py
│   │   ├── scanner.py          # Scan for opportunities
│   │   ├── ranker.py           # Rank by expected value
│   │   └── presenter.py        # Format recommendations
│   │
│   └── analytics/              📋 NEW - Performance Analytics
│       ├── __init__.py
│       ├── performance.py      # Win rate, expectancy, Sharpe
│       ├── attribution.py      # Greeks-based P&L attribution
│       └── review.py           # Trade review system
│
├── ai_cotrader/                📋 EXPAND
│   ├── feature_engineering/
│   │   ├── __init__.py
│   │   └── extractors.py       # Extract features from events
│   ├── learning/
│   │   ├── __init__.py
│   │   ├── pattern_recognition.py  # Find patterns in your trading
│   │   └── reinforcement.py    # RL for decision optimization
│   └── models/
│       ├── __init__.py
│       └── trained/            # Saved models directory
│
├── runners/                    ✅ + 📋 EXPAND
│   ├── sync_portfolio.py       ✅
│   ├── validate_data.py        ✅
│   ├── daily_analysis.py       📋 NEW - Morning analysis routine
│   ├── position_monitor.py     📋 NEW - Real-time position monitoring
│   └── trade_review.py         📋 NEW - End-of-day review
│
├── ui/                         📋 NEW - UI Proof of Concept
│   ├── __init__.py
│   ├── grid/                   # Grid-based workspace
│   │   ├── __init__.py
│   │   ├── cell.py             # Cell that holds objects
│   │   ├── grid.py             # Grid container
│   │   └── formulas.py         # Excel-like formulas on objects
│   └── web/                    # Web interface (later)
│       └── __init__.py
│
└── evaluation/                 📋 NEW - System Evaluation
    ├── __init__.py
    ├── backtest.py             # Forward testing framework
    ├── metrics.py              # Performance metrics
    └── reports.py              # Generate evaluation reports
```

### 2.3 Key Technical Decisions

| Decision | Rationale | Status |
|----------|-----------|--------|
| SQLite for storage | Simplicity, no infrastructure, portable | ✅ Implemented |
| Repository pattern | Clean data access, testable | ✅ Implemented |
| Event sourcing | Learn from history, audit trail | ✅ Schema ready |
| DAG computation | Reactive updates, clear dependencies | 📋 To design |
| Objects in UI | Trade objects, not just values | 📋 To design |

---

## 3. Trading Platform Capabilities

### 3.1 Capability Matrix

| Category | Capability | Priority | Status | Notes |
|----------|------------|----------|--------|-------|
| **Core Data** | Portfolio sync | CRITICAL | ✅ Done | Clear-and-rebuild strategy |
| | Position tracking | CRITICAL | ✅ Done | With Greeks |
| | Trade tracking | CRITICAL | ✅ Schema | Needs population |
| | Event capture | HIGH | ✅ Schema | Needs integration |
| **Pre-Trade Risk** | VaR calculation | CRITICAL | 📋 TODO | Before and after new trade |
| | Correlation analysis | CRITICAL | 📋 TODO | Avoid correlated baskets |
| | Max loss scenarios | CRITICAL | 📋 TODO | Worst case analysis |
| | Margin requirements | CRITICAL | 📋 TODO | Broker margin estimation |
| | Concentration limits | HIGH | 📋 TODO | Strategy & direction |
| **Position Mgmt** | Exit rules engine | CRITICAL | 📋 TODO | 50% profit, 21 DTE, etc. |
| | Adjustment triggers | CRITICAL | 📋 TODO | When to adjust |
| | Roll vs close decision | CRITICAL | 📋 TODO | Decision framework |
| | Stop-loss management | CRITICAL | 📋 TODO | Automated monitoring |
| **Market Analysis** | VIX regime detection | HIGH | 📋 TODO | Low/medium/high |
| | Trend detection | HIGH | 📋 TODO | Bull/bear/sideways |
| | IV rank tracking | HIGH | 📋 TODO | Per underlying |
| | Earnings awareness | HIGH | 📋 TODO | Calendar integration |
| **Pricing** | Greeks calculation | MEDIUM | ✅ Basic | From broker, enhance |
| | Probability of profit | MEDIUM | 📋 TODO | POP calculation |
| | P&L attribution | MEDIUM | 📋 TODO | Delta/theta/vega split |
| | Implied move | MEDIUM | 📋 TODO | Expected range |
| **Recommendations** | Opportunity scanner | HIGH | 📋 TODO | What to trade today |
| | Expected value calc | HIGH | 📋 TODO | EV for each trade |
| | Strategy selector | MEDIUM | 📋 TODO | Best strategy for conditions |
| **Analytics** | Win rate tracking | MEDIUM | 📋 TODO | By strategy |
| | Expectancy | MEDIUM | 📋 TODO | Avg win vs avg loss |
| | Max drawdown | MEDIUM | 📋 TODO | Risk metric |
| | Trade review | MEDIUM | 📋 TODO | Systematic review |
| **AI/ML** | Pattern recognition | FUTURE | 📋 TODO | Learn from your trades |
| | Reinforcement learning | FUTURE | 📋 TODO | Optimize decisions |

### 3.2 The "What-If" Object

A core concept: **What-If scenarios should be first-class objects**

```python
# Conceptual design
class WhatIfScenario:
    """
    A What-If is an OBJECT that can be:
    - Created with parameters
    - Stored in the UI grid
    - Re-evaluated when parameters change
    - Compared with other What-Ifs
    """
    
    # Inputs (changeable)
    proposed_trade: Trade
    market_assumptions: MarketAssumptions
    
    # Computed outputs (reactive)
    portfolio_var_before: Decimal
    portfolio_var_after: Decimal
    var_impact: Decimal
    
    margin_required: Decimal
    buying_power_impact: Decimal
    
    correlation_with_existing: Dict[str, float]
    concentration_after: Dict[str, float]
    
    max_loss_scenario: Decimal
    probability_of_profit: float
    expected_value: Decimal
    
    # Decision
    passes_risk_checks: bool
    warnings: List[str]
    recommendation: str
```

### 3.3 Risk Object Model

```python
class PortfolioRisk:
    """
    Risk is an OBJECT that:
    - Updates when portfolio changes
    - Can be queried for specific metrics
    - Triggers alerts when limits breached
    """
    
    # Current state
    portfolio_var_1d: Decimal  # 1-day VaR at 95%
    portfolio_var_5d: Decimal  # 5-day VaR
    
    # Greek risks
    delta_dollars: Decimal     # $ change per 1% underlying move
    gamma_risk: Decimal        # Acceleration of delta
    theta_daily: Decimal       # Daily time decay
    vega_dollars: Decimal      # $ change per 1% IV change
    
    # Concentration
    by_underlying: Dict[str, float]  # % exposure per underlying
    by_strategy: Dict[str, float]    # % in each strategy type
    by_direction: Dict[str, float]   # Long/short/neutral split
    
    # Correlation matrix
    correlation_matrix: pd.DataFrame
    
    # Limits
    limit_breaches: List[LimitBreach]
    
    # Methods
    def impact_of_trade(self, trade: Trade) -> RiskImpact: ...
    def passes_limits(self, new_var: Decimal) -> Tuple[bool, List[str]]: ...
```

---

## 4. Module Specifications

### 4.1 Risk Module (`services/risk/`)

**Purpose**: Answer "Should I take this trade?" from a risk perspective.

#### 4.1.1 VaR Calculator (`var_calculator.py`)

```python
# Input/Output Contract
class VaRCalculator:
    def calculate_parametric_var(
        self,
        positions: List[Position],
        confidence: float = 0.95,
        horizon_days: int = 1
    ) -> VaRResult:
        """
        Calculate Value at Risk using parametric (variance-covariance) method.
        
        Returns:
            VaRResult with var_amount, var_percent, contributing_positions
        """
        pass
    
    def calculate_historical_var(
        self,
        positions: List[Position],
        lookback_days: int = 252,
        confidence: float = 0.95
    ) -> VaRResult:
        """
        Calculate VaR using historical simulation.
        """
        pass
    
    def calculate_monte_carlo_var(
        self,
        positions: List[Position],
        simulations: int = 10000,
        confidence: float = 0.95
    ) -> VaRResult:
        """
        Calculate VaR using Monte Carlo simulation.
        """
        pass
```

#### 4.1.2 Portfolio Risk (`portfolio_risk.py`)

```python
class PortfolioRiskAnalyzer:
    def analyze(self, portfolio: Portfolio, positions: List[Position]) -> PortfolioRisk:
        """Full portfolio risk analysis."""
        pass
    
    def impact_analysis(
        self, 
        current_risk: PortfolioRisk, 
        proposed_trade: Trade
    ) -> RiskImpact:
        """What happens to risk if we add this trade?"""
        pass
    
    def stress_test(
        self,
        positions: List[Position],
        scenarios: List[StressScenario]
    ) -> List[StressResult]:
        """Run stress scenarios (2008, COVID, etc.)"""
        pass
```

#### 4.1.3 Correlation (`correlation.py`)

```python
class CorrelationAnalyzer:
    def calculate_correlation_matrix(
        self,
        underlyings: List[str],
        lookback_days: int = 60
    ) -> pd.DataFrame:
        """Calculate correlation matrix for underlyings."""
        pass
    
    def find_correlated_positions(
        self,
        positions: List[Position],
        threshold: float = 0.7
    ) -> List[CorrelatedPair]:
        """Find highly correlated position pairs."""
        pass
    
    def diversification_score(
        self,
        positions: List[Position]
    ) -> float:
        """0-1 score of how diversified the portfolio is."""
        pass
```

### 4.2 Pricing Module (`services/pricing/`)

**Purpose**: Accurate pricing, Greeks, and probability calculations.

#### 4.2.1 Black-Scholes (`black_scholes.py`)

```python
class BlackScholesModel:
    def price(
        self,
        spot: Decimal,
        strike: Decimal,
        time_to_expiry: float,  # in years
        rate: float,
        volatility: float,
        option_type: OptionType
    ) -> Decimal:
        """Calculate option price."""
        pass
    
    def greeks(
        self,
        spot: Decimal,
        strike: Decimal,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        option_type: OptionType
    ) -> Greeks:
        """Calculate all Greeks."""
        pass
    
    def implied_volatility(
        self,
        market_price: Decimal,
        spot: Decimal,
        strike: Decimal,
        time_to_expiry: float,
        rate: float,
        option_type: OptionType
    ) -> float:
        """Back out implied volatility from market price."""
        pass
```

#### 4.2.2 Probability (`probability.py`)

```python
class ProbabilityCalculator:
    def probability_of_profit(
        self,
        trade: Trade,
        current_price: Decimal,
        iv: float
    ) -> float:
        """Calculate probability that trade is profitable at expiration."""
        pass
    
    def probability_itm(
        self,
        option: Symbol,
        current_price: Decimal,
        iv: float
    ) -> float:
        """Probability option expires in the money."""
        pass
    
    def expected_move(
        self,
        underlying_price: Decimal,
        iv: float,
        days: int
    ) -> Tuple[Decimal, Decimal]:
        """Expected 1-sigma move range."""
        pass
    
    def expected_value(
        self,
        trade: Trade,
        pop: float,
        max_profit: Decimal,
        max_loss: Decimal
    ) -> Decimal:
        """Expected value of trade."""
        pass
```

### 4.3 Position Management Module (`services/position_mgmt/`)

**Purpose**: Know what to do with positions once opened.

#### 4.3.1 Rules Engine (`rules_engine.py`)

```python
class ExitRule:
    """Base class for exit rules."""
    name: str
    description: str
    
    def evaluate(self, position: Position, trade: Trade, market: MarketData) -> RuleResult:
        """Check if rule is triggered."""
        pass

class ProfitTargetRule(ExitRule):
    """Close at X% profit."""
    target_percent: float = 50.0

class DaysToExpirationRule(ExitRule):
    """Close at X days to expiration."""
    dte_threshold: int = 21

class StopLossRule(ExitRule):
    """Close at X% loss."""
    max_loss_percent: float = 200.0

class RulesEngine:
    def __init__(self, rules: List[ExitRule]):
        self.rules = rules
    
    def evaluate_all(
        self,
        position: Position,
        trade: Trade,
        market: MarketData
    ) -> List[RuleResult]:
        """Evaluate all rules against position."""
        pass
    
    def get_action(self, results: List[RuleResult]) -> PositionAction:
        """Determine recommended action from rule results."""
        pass
```

### 4.4 Market Analysis Module (`services/market/`)

**Purpose**: Understand current market conditions.

#### 4.4.1 Regime Detection (`regime.py`)

```python
class MarketRegime(Enum):
    LOW_VOL_BULL = "low_vol_bull"
    LOW_VOL_BEAR = "low_vol_bear"
    LOW_VOL_SIDEWAYS = "low_vol_sideways"
    HIGH_VOL_BULL = "high_vol_bull"
    HIGH_VOL_BEAR = "high_vol_bear"
    HIGH_VOL_SIDEWAYS = "high_vol_sideways"
    CRISIS = "crisis"

class RegimeDetector:
    def detect_current_regime(self) -> MarketRegime:
        """Determine current market regime."""
        pass
    
    def get_vix_regime(self, vix: float) -> str:
        """Low/Medium/High classification."""
        if vix < 15:
            return "low"
        elif vix < 25:
            return "medium"
        else:
            return "high"
    
    def detect_trend(
        self,
        symbol: str,
        lookback_days: int = 20
    ) -> Trend:
        """Detect trend for symbol."""
        pass
```

#### 4.4.2 IV Rank (`iv_rank.py`)

```python
class IVRankCalculator:
    def calculate_iv_rank(
        self,
        symbol: str,
        current_iv: float,
        lookback_days: int = 252
    ) -> float:
        """
        IV Rank: Where is current IV relative to 52-week range?
        0 = lowest, 100 = highest
        """
        pass
    
    def calculate_iv_percentile(
        self,
        symbol: str,
        current_iv: float,
        lookback_days: int = 252
    ) -> float:
        """
        IV Percentile: What % of days had lower IV?
        """
        pass
    
    def get_high_iv_underlyings(
        self,
        min_iv_rank: float = 50
    ) -> List[IVRankResult]:
        """Find underlyings with elevated IV."""
        pass
```

---

## 5. Progress Tracker

### 5.1 Milestone Definitions

| Milestone | Definition | Target |
|-----------|------------|--------|
| **M1: Foundation** | Tech infrastructure working | ✅ DONE |
| **M2: Risk Core** | VaR, correlation, limits working | Week 1-2 |
| **M3: Pricing Core** | BS model, Greeks, probability | Week 2-3 |
| **M4: Position Mgmt** | Rules engine, exit triggers | Week 3-4 |
| **M5: Market Intel** | Regime, IV rank, earnings | Week 4-5 |
| **M6: Recommendations** | Scanner, ranker working | Week 5-6 |
| **M7: Analytics** | Performance tracking | Week 6-7 |
| **M8: AI/ML** | Pattern recognition | Week 7+ |
| **M9: UI POC** | Grid-based workspace | Week 8+ |

### 5.2 Weekly Progress Log

#### Week 0 (Foundation) - COMPLETE ✅

**Completed:**
- [x] Database schema (11 tables)
- [x] Domain models (Symbol, Position, Trade, etc.)
- [x] Event sourcing models
- [x] Repository pattern
- [x] Tastytrade adapter (auth, positions, balance)
- [x] Position sync service
- [x] Basic validation

#### Week 1 (Current) - Risk & Pricing Infrastructure

**Completed:**
- [x] Risk configuration YAML (`config/risk_config.yaml`)
- [x] Risk config loader with typed access
- [x] VaR Calculator (parametric, historical, Monte Carlo stubs)
- [x] Portfolio Risk Analyzer with PortfolioRisk object
- [x] Correlation Analyzer
- [x] Concentration Checker
- [x] Margin Estimator
- [x] Risk Limits Manager
- [x] Black-Scholes Model (full implementation with Greeks)
- [x] Probability Calculator (POP, expected move, expected value)
- [x] Implied Volatility Calculator (Newton-Raphson + bisection)
- [x] Scenario Engine (what-if price/vol/time)
- [x] **What-If Object** as first-class citizen
- [x] Position Management Rules Engine
- [x] Exit Rules (profit targets, stop losses, DTE, delta-based, combined)

**Key Decisions:**
- All risk parameters in YAML config
- What-If is a reactive object that re-evaluates on input change
- Rules engine loads from config for consistency

---

### 5.3 Task Backlog

#### Priority 1: Risk Module (Next)

| Task | Estimate | Dependencies | Status |
|------|----------|--------------|--------|
| Create `services/risk/` directory structure | 1h | None | 📋 TODO |
| Implement `VaRCalculator` (parametric) | 4h | Market data | 📋 TODO |
| Implement `CorrelationAnalyzer` | 3h | Historical data | 📋 TODO |
| Implement `ConcentrationChecker` | 2h | Positions | 📋 TODO |
| Implement `MarginEstimator` | 3h | Broker rules | 📋 TODO |
| Implement `RiskLimits` | 2h | VaR | 📋 TODO |
| Create `PortfolioRisk` object | 2h | All above | 📋 TODO |
| Write tests for risk module | 3h | Implementation | 📋 TODO |

#### Priority 2: Pricing Module

| Task | Estimate | Dependencies | Status |
|------|----------|--------------|--------|
| Create `services/pricing/` directory structure | 1h | None | 📋 TODO |
| Implement `BlackScholesModel` | 3h | None | 📋 TODO |
| Implement `ImpliedVolCalculator` | 2h | BS model | 📋 TODO |
| Implement `ProbabilityCalculator` | 3h | BS model | 📋 TODO |
| Implement `ScenarioEngine` | 4h | BS model | 📋 TODO |
| Write tests | 3h | Implementation | 📋 TODO |

#### Priority 3: Position Management

| Task | Estimate | Dependencies | Status |
|------|----------|--------------|--------|
| Create `services/position_mgmt/` structure | 1h | None | 📋 TODO |
| Design `ExitRule` base class | 2h | None | 📋 TODO |
| Implement standard rules | 3h | Base class | 📋 TODO |
| Implement `RulesEngine` | 3h | Rules | 📋 TODO |
| Implement `AdjustmentAdvisor` | 4h | Pricing | 📋 TODO |
| Write tests | 3h | Implementation | 📋 TODO |

---

## 6. Decision Log

| Date | Decision | Rationale | Alternatives Considered |
|------|----------|-----------|------------------------|
| 2026-01-20 | Clear-and-rebuild for position sync | Simpler, no duplicates, no merge logic | Update-or-insert |
| 2026-01-20 | Event sourcing for AI | Complete audit trail, patterns from history | Just store trades |
| 2026-01-24 | Objects in UI, not just values | Enables reactivity, formulas, what-ifs | Traditional dashboards |
| 2026-01-24 | Module-per-service structure | Clear boundaries, testable, replaceable | Monolithic services |

---

## 7. Implementation Priorities

### 7.1 Immediate (This Week)

1. **Create directory structure** for all new modules (empty files with type hints)
2. **Implement VaR calculator** (parametric method first)
3. **Implement concentration checker** (simple but critical)
4. **Fix Greeks fetching** from Tastytrade (options showing zero)

### 7.2 Short-term (2-3 Weeks)

1. Complete Risk module
2. Complete Pricing module (BS model, probability)
3. Implement basic Rules Engine
4. Create first runner: `daily_analysis.py`

### 7.3 Medium-term (4-6 Weeks)

1. Market analysis module
2. Recommendations engine
3. Performance analytics
4. Trade review system

### 7.4 Longer-term (7+ Weeks)

1. AI/ML pattern recognition
2. Reinforcement learning exploration
3. UI proof of concept (grid-based)
4. Forward testing framework

---

## 8. AI/ML & Reinforcement Learning

### 8.1 Current AI/ML State

| Component | Status | Location | Notes |
|-----------|--------|----------|-------|
| Event Models | ✅ Done | `core/models/events.py` | TradeEvent, MarketContext, DecisionContext |
| Event Logging | ✅ Done | `services/event_logger.py` | Captures decisions |
| Event Analytics | ✅ Done | `services/event_analytics.py` | Analyzes patterns |
| Event Repository | ✅ Done | `repositories/event.py` | CRUD for events |
| Event CLI | ✅ Done | `cli/log_event.py` | Manual event logging |
| Feature Engineering | ✅ Done | `ai_cotrader/feature_engineering/` | FeatureExtractor, RLState |
| Learning Module | ✅ Done | `ai_cotrader/learning/` | PatternRecognizer, QLearningAgent |
| Trained Models | ❌ None | `ai_cotrader/models/trained/` | Need data first |

### 8.2 Data Collection Status

**Problem**: ML needs data. Current data collection:

| Data Type | Collected? | Volume | Quality |
|-----------|------------|--------|---------|
| Trade Events | ⚠️ Schema ready | Low | Need to log more |
| Market Context | ⚠️ Schema ready | Low | Need to capture at decision time |
| Decision Context | ⚠️ Schema ready | Low | Need trader input |
| Outcomes | ⚠️ Schema ready | Low | Need closed trades |
| Greeks History | ⚠️ Schema ready | Low | Need regular snapshots |
| Price History | ❌ Not yet | None | Need market data integration |

**Minimum Data for ML**: ~100-500 completed trades with full context

### 8.3 Reinforcement Learning Design

#### State Space (What the agent observes)

```python
@dataclass
class RLState:
    # Portfolio state
    portfolio_delta: float
    portfolio_theta: float
    portfolio_vega: float
    cash_balance: float
    buying_power: float
    
    # Position state (per position)
    position_pnl_percent: float
    position_dte: int
    position_delta: float
    
    # Market state
    underlying_price: float
    underlying_iv_rank: float
    vix_level: float
    market_regime: str  # bull/bear/sideways
    
    # Time state
    days_in_trade: int
    day_of_week: int
    hours_to_close: float
```

#### Action Space (What the agent can do)

```python
class RLAction(Enum):
    HOLD = 0              # Do nothing
    CLOSE_FULL = 1        # Close entire position
    CLOSE_HALF = 2        # Close 50%
    ROLL_OUT = 3          # Roll to next expiration
    ROLL_OUT_AND_UP = 4   # Roll out + adjust strikes
    ROLL_OUT_AND_DOWN = 5
    ADD_HEDGE = 6         # Add protective position
    TAKE_PROFIT = 7       # Close at current profit
```

#### Reward Function

```python
def calculate_reward(
    action_taken: RLAction,
    pnl_after: float,
    risk_after: float,
    time_held: int
) -> float:
    """
    Reward function balances:
    1. P&L (primary)
    2. Risk-adjusted returns (Sharpe-like)
    3. Time efficiency (don't hold forever)
    4. Rule compliance (followed the plan)
    """
    
    # P&L component (normalized)
    pnl_reward = pnl_after / max_position_risk
    
    # Risk penalty (don't blow up)
    risk_penalty = -0.1 * (risk_after / initial_risk) if risk_after > initial_risk else 0
    
    # Time decay bonus (close winners early)
    time_bonus = 0.01 * (max_dte - time_held) / max_dte if pnl_after > 0 else 0
    
    # Consistency bonus (followed rules)
    rule_bonus = 0.05 if action_matches_rules else 0
    
    return pnl_reward + risk_penalty + time_bonus + rule_bonus
```

#### Training Pipeline (Future)

```
1. COLLECT: Log every trade with full context (events system)
2. EXTRACT: Feature engineering from events → state vectors
3. LABEL: Outcomes become rewards
4. TRAIN: Train RL agent (DQN, PPO, or simpler Q-learning)
5. VALIDATE: Paper trade with agent suggestions
6. DEPLOY: Agent suggests, human approves
```

### 8.4 Pragmatic Path to RL

**Phase 1: Data Collection (Current)**
- Use the system manually
- Log every decision via event system
- Capture market context at decision time
- Record outcomes when trades close

**Phase 2: Pattern Recognition (Before RL)**
- Analyze collected events
- Find patterns: "When I do X in condition Y, outcome is Z"
- Rules-based suggestions from patterns

**Phase 3: Supervised Learning**
- Train classifier: "Given state, what did the trader do?"
- This learns YOUR style, not optimal play

**Phase 4: Reinforcement Learning**
- Only after 500+ trades with outcomes
- Start with simple Q-learning
- Agent suggests, you approve/reject
- Agent learns from your feedback

### 8.5 Implementation Priority

| Task | Priority | Depends On | Status |
|------|----------|------------|--------|
| Log events on every trade | HIGH | Event system | ⚠️ Ready, need usage |
| Capture Greeks snapshots daily | HIGH | Sync runner | 📋 TODO |
| Feature extractor from events | MEDIUM | 100+ events | 📋 TODO |
| Pattern finder | MEDIUM | Feature extractor | 📋 TODO |
| Q-learning agent | LOW | 500+ events | 📋 FUTURE |
| PPO/DQN agent | LOW | Q-learning working | 📋 FUTURE |

---

## 9. Open Questions

### 9.1 Technical Questions

| Question | Context | Options | Decision |
|----------|---------|---------|----------|
| How to get historical IV data? | Needed for IV rank | Broker API, external provider, calculate from prices | TBD |
| DAG computation engine? | Reactive updates | Custom, existing library (RxPY) | TBD |
| Real-time vs batch? | Position monitoring | WebSocket streaming, polling | TBD |

### 9.2 Trading Questions

| Question | Your Thoughts? |
|----------|----------------|
| What VaR confidence level matters to you? | 95%? 99%? |
| What's your max portfolio VaR tolerance? | % of equity? |
| Concentration limits per underlying? | 20% max? |
| Preferred exit rules? | 50% profit? 21 DTE? |
| Which underlyings do you typically trade? | For IV rank tracking |

### 9.3 UI Questions

| Question | Your Thoughts? |
|----------|----------------|
| Grid like Excel or more like Notion databases? | |
| What objects should cells hold? | Trades, positions, what-ifs, scenarios? |
| Formulas between cells? | `=CELL(A1).position.greeks.delta`? |

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **VaR** | Value at Risk - max loss at given confidence level |
| **IV Rank** | Where current IV sits in 52-week range (0-100) |
| **IV Percentile** | % of days with lower IV than current |
| **POP** | Probability of Profit at expiration |
| **DTE** | Days to Expiration |
| **DAG** | Directed Acyclic Graph - computation dependency graph |

---

## Appendix B: Strategy Catalog

| Strategy | When to Use | Max Profit | Max Loss | Preferred Conditions |
|----------|-------------|------------|----------|---------------------|
| Short Put | Bullish, want to own stock | Premium | Strike - Premium | High IV, support level |
| Iron Condor | Neutral, range-bound | Net credit | Width - credit | High IV, low expected move |
| Put Credit Spread | Bullish | Net credit | Width - credit | Elevated IV, support |
| Call Credit Spread | Bearish | Net credit | Width - credit | Elevated IV, resistance |
| Straddle | Big move expected | Unlimited | Premium paid | Low IV, event coming |
| Strangle | Big move expected | Unlimited | Premium paid | Low IV, cheaper than straddle |

---

## Appendix C: Session Log

Track every session here for continuity.

### Session: January 24, 2026

**Focus**: Risk module, pricing foundation, position management, AI/ML foundation

**Built**:
- `config/risk_config.yaml` - Risk parameters YAML
- `config/risk_config_loader.py` - Typed config loader
- `services/risk/*` - Complete risk module
- `services/position_mgmt/rules_engine.py` - Exit rules
- `core/models/what_if.py` - What-If object
- `ai_cotrader/feature_engineering/feature_extractor.py` - ML feature extraction
- `ai_cotrader/learning/supervised.py` - Pattern recognition (Decision Tree)
- `ai_cotrader/learning/reinforcement.py` - Q-Learning & DQN agents
- `ai_cotrader/__init__.py` - Module exports with TradingAdvisor

**AI/ML Components**:
- FeatureExtractor: Converts events → ML feature vectors
- MarketFeatures, PositionFeatures, PortfolioFeatures: Structured features
- RLState: Combined state for RL (55 dimensions)
- DatasetBuilder: Build training datasets from events
- PatternRecognizer: Supervised learning on your decisions
- QLearningAgent: Tabular Q-learning for small state spaces
- DQNAgent: Deep Q-Network (numpy implementation)
- TradingAdvisor: Combines supervised + RL + rules for recommendations
- RewardFunction: Risk-adjusted P&L reward calculation

**Discovered Existing** (was not aware of):
- `analytics/pricing/option_pricer.py` - You have Black-Scholes
- `analytics/greeks/engine.py` - You have Greeks
- `services/event_logger.py` - Event logging exists

**Integration Status**: Pending your integration

**Next Session Should**:
1. Upload `analytics/pricing/option_pricer.py` and `services/event_logger.py`
2. Wire AI module to use existing event system
3. Create training pipeline script
4. Focus on data collection for ML

---

### Session: [DATE]

**Focus**: [What we worked on]

**Built**:
- [Files created/modified]

**Integration Status**: [Did previous session's code get integrated?]

**Issues Found**:
- [What broke, what didn't work]

**Next Session Should**:
- [Priority items]

---

*Add new session entries above this line*

---

*This document is the single source of truth. Update it at the end of every session.*

