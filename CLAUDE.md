# CLAUDE.md - AI Assistant Guide for trading_cotrader

This document provides comprehensive guidance for AI assistants working on the `trading_cotrader` codebase.

## Project Overview

**Trading Co-Trader** is an event-sourced, AI-learning trading application designed for options trading with the Tastytrade broker. It focuses on:

- **Real-time Greeks calculation** with Black-Scholes pricing
- **Event sourcing** for capturing every trading decision with full context
- **AI/ML pattern recognition** to learn from historical trades
- **Professional risk management** with configurable limits
- **P&L attribution** by Greeks components

## Tech Stack

- **Python 3.10+**
- **SQLAlchemy** for ORM and database management
- **Pydantic** for configuration and data validation
- **Tastytrade API** for broker integration (with DXLink streaming)
- **SQLite/PostgreSQL** for data persistence
- **pytest** for testing

## Directory Structure

```
trading_cotrader/
├── adapters/                    # Broker integrations
│   └── tastytrade_adapter.py    # Tastytrade API implementation
├── ai_cotrader/                 # AI/ML learning components
│   ├── feature_engineering/     # Feature extraction for ML
│   ├── learning/                # ML model training
│   └── models/                  # Trained model storage
├── analytics/                   # Financial calculations
│   ├── greeks/
│   │   └── engine.py            # Black-Scholes Greeks engine
│   ├── pricing/
│   │   ├── option_pricer.py     # Option valuation
│   │   └── pnl_calculator.py    # P&L calculations
│   ├── risk/                    # Risk metrics
│   ├── performance/             # Performance analytics
│   ├── functional_portfolio.py  # DAG-based scenario analysis
│   └── volatility_surface.py    # Volatility term structure
├── cli/
│   └── log_event.py             # CLI for logging trading decisions
├── config/
│   └── settings.py              # Pydantic configuration management
├── core/
│   ├── database/
│   │   ├── schema.py            # SQLAlchemy ORM models
│   │   └── session.py           # Database session management
│   ├── models/
│   │   ├── domain.py            # Core domain models (Trade, Position, Leg, Greeks)
│   │   ├── events.py            # Event sourcing models
│   │   └── calculations.py      # Business logic calculations
│   └── validation/
│       └── validators.py        # Data validation utilities
├── repositories/                # Data access layer
│   ├── base.py                  # Generic CRUD base class
│   ├── position.py              # Position repository
│   ├── trade.py                 # Trade repository
│   ├── portfolio.py             # Portfolio repository
│   └── event.py                 # Event repository
├── runners/                     # Application entry points
│   ├── sync_portfolio.py        # Main daily sync workflow
│   ├── sync_with_greeks.py      # Greeks calculation runner
│   ├── portfolio_analyzer.py    # Portfolio analysis
│   └── validate_data.py         # Data validation runner
├── scripts/
│   └── setup_database.py        # Database initialization
├── services/                    # Business logic services
│   ├── risk_manager.py          # Risk limit enforcement
│   ├── position_sync.py         # Broker position sync
│   ├── greeks_service.py        # Real-time Greeks updates
│   ├── event_analytics.py       # Trading pattern analysis
│   ├── snapshot_service.py      # Daily snapshots
│   └── real_risk_check.py       # Real-time risk validation
└── tests/                       # Test suite
```

## Key Files to Understand

| File | Purpose |
|------|---------|
| `core/models/domain.py` | Core domain entities: Trade, Position, Leg, Greeks, Symbol, Portfolio |
| `core/models/events.py` | Event sourcing: TradeEvent, MarketContext, DecisionContext |
| `core/database/schema.py` | SQLAlchemy ORM table definitions |
| `services/risk_manager.py` | Risk validation before trade execution |
| `adapters/tastytrade_adapter.py` | Tastytrade API integration with DXLink streaming |
| `analytics/greeks/engine.py` | Black-Scholes Greeks calculation engine |
| `config/settings.py` | Pydantic settings with environment variable support |
| `runners/sync_portfolio.py` | Main entry point for daily portfolio sync |

## Development Commands

### Setup

```bash
# Initialize database
python -m trading_cotrader.scripts.setup_database

# Create .env file (see config/settings.py for ENV_EXAMPLE)
```

### Running the Application

```bash
# Sync portfolio from Tastytrade
python -m trading_cotrader.runners.sync_portfolio

# Calculate Greeks for positions
python -m trading_cotrader.runners.sync_with_greeks

# Analyze portfolio
python -m trading_cotrader.runners.portfolio_analyzer

# Validate data integrity
python -m trading_cotrader.runners.validate_data

# Log a trading decision (for AI learning)
python -m trading_cotrader.cli.log_event --underlying SPY --strategy iron_condor --rationale "High IV rank"
```

### Testing

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_risk_manager.py
```

## Architecture Patterns

### 1. Repository Pattern
Data access is abstracted through repositories:
```python
from core.database.session import session_scope
from repositories.position import PositionRepository

with session_scope() as session:
    repo = PositionRepository(session)
    positions = repo.get_by_portfolio(portfolio_id)
```

### 2. Event Sourcing
Every trading decision is captured as an immutable event:
```python
# Events include MarketContext (spot, IV, RSI, etc.) and
# DecisionContext (rationale, confidence, risk tolerance)
```

### 3. Service Layer
Business logic lives in services, not models:
- `RiskManager` - validates trades against limits
- `PositionSyncService` - syncs from broker
- `GreeksService` - real-time Greeks updates

### 4. Configuration via Pydantic Settings
```python
from config.settings import get_settings
settings = get_settings()
print(settings.database_url)
```

## Domain Models

### Key Enumerations
- `AssetType`: EQUITY, OPTION, FUTURE, CRYPTO
- `OptionType`: CALL, PUT
- `OrderSide`: BUY, SELL, BUY_TO_OPEN, SELL_TO_OPEN, BUY_TO_CLOSE, SELL_TO_CLOSE
- `StrategyType`: IRON_CONDOR, VERTICAL_SPREAD, STRADDLE, STRANGLE, etc.

### Core Entities
- **Symbol**: Immutable representation of a tradable instrument
- **Greeks**: Delta, gamma, theta, vega, rho snapshot
- **Leg**: Single leg of a trade (quantity, entry/exit prices, Greeks)
- **Trade**: Collection of legs representing a complete position
- **Position**: Current holding snapshot
- **Portfolio**: Top-level container with cash, buying power, aggregated Greeks

## Configuration

### Environment Variables (.env)
```bash
# Database
DATABASE_URL=sqlite:///trading_cotrader.db

# Tastytrade (credentials loaded from YAML)
IS_PAPER_TRADING=false

# Risk Management
MAX_PORTFOLIO_DELTA=100.0
MAX_POSITION_SIZE_PERCENT=20.0

# Feature Flags
ENABLE_AI_LEARNING=true
ENABLE_GREEKS_CALCULATION=true
ENABLE_PNL_ATTRIBUTION=true

# Logging
LOG_LEVEL=INFO
```

### YAML Configuration (config.yaml)
The main `config.yaml` at project root contains:
- Broker credentials (environment variable references)
- Strategy configurations (iron condor, verticals, wheel, etc.)
- Risk limits (per-trade, daily, weekly stops)
- Technical indicator settings (RSI, SMA, MACD, etc.)

## Risk Management

The `RiskManager` service enforces:

| Check | Description | Default Limit |
|-------|-------------|---------------|
| Portfolio Delta | Maximum gross directional exposure | 100 units |
| Position Size | Max % of portfolio per position | 20% |
| Concentration | Max exposure to single underlying | Configurable |
| Buying Power | Available margin validation | Account balance |

## Coding Conventions

### Python Style
- Use type hints for all function signatures
- Dataclasses for domain models (prefer frozen=True for value objects)
- Decimal for all money/price values (never float)
- UUID strings for entity IDs

### Imports
```python
# Standard library
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List

# Third-party
from sqlalchemy import Column, String
from pydantic import Field

# Local
from core.models.domain import Position, Trade
from config.settings import get_settings
```

### Database Sessions
Always use the context manager for automatic transaction handling:
```python
from core.database.session import session_scope

with session_scope() as session:
    # Operations here
    # Auto-commits on success, rollback on error
```

### Error Handling
- Use specific exceptions, not generic Exception
- Log errors with context before re-raising
- Validate inputs at system boundaries

## Common Tasks for AI Assistants

### Adding a New Strategy Type
1. Add enum value to `StrategyType` in `core/models/domain.py`
2. Add strategy config in `config.yaml` under `strategies.defined` or `strategies.undefined`
3. Implement strategy logic if needed

### Adding a New Risk Check
1. Add method to `RiskManager` in `services/risk_manager.py`
2. Call from `validate_trade()` method
3. Add tests in `tests/`

### Modifying Database Schema
1. Update ORM models in `core/database/schema.py`
2. Run `setup_database.py` to recreate (or use migrations for production)
3. Update corresponding domain models in `core/models/domain.py`

### Adding a New Broker Adapter
1. Create new file in `adapters/` implementing the broker interface
2. Implement methods: `connect()`, `get_positions()`, `get_account_balance()`, `submit_order()`
3. Register in configuration

## Testing Conventions

- Unit tests in `tests/unit/`
- Integration tests in `tests/integration/`
- Use pytest fixtures for common setup
- Mock external services (broker API, market data)

## Important Notes

1. **Never store credentials in code** - use environment variables or YAML with ${VAR} syntax
2. **Greeks come from DXLink streaming**, not REST API - the adapter handles this
3. **Event sourcing is critical** - every trade decision should be logged for AI learning
4. **Paper trading mode** - always test with `IS_PAPER_TRADING=true` first
5. **Decimal precision** - never use float for financial calculations

## File Naming Conventions

- Snake_case for Python files: `risk_manager.py`
- Classes use PascalCase: `RiskManager`
- Constants use UPPER_SNAKE_CASE: `MAX_PORTFOLIO_DELTA`
- Private methods/attributes prefixed with underscore: `_validate_delta()`
