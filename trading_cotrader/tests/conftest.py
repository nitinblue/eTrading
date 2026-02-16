"""
Test Fixtures — Shared across all unit tests.

Provides:
- In-memory SQLite database (fresh per test)
- Sample domain objects (Trade, Portfolio, Leg, Symbol, etc.)
- Known Decimal constants for reproducibility
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
import uuid

from trading_cotrader.core.database.session import create_test_database
import trading_cotrader.core.models.domain as dm


# =============================================================================
# Known constants for deterministic tests
# =============================================================================

KNOWN_ENTRY_PRICE = Decimal('2.50')
KNOWN_EXIT_PRICE = Decimal('1.25')
KNOWN_UNDERLYING_PRICE = Decimal('450.00')
KNOWN_STRIKE = Decimal('455.00')
KNOWN_DELTA = Decimal('-0.30')
KNOWN_GAMMA = Decimal('0.02')
KNOWN_THETA = Decimal('-0.05')
KNOWN_VEGA = Decimal('0.12')


# =============================================================================
# Database fixtures
# =============================================================================

@pytest.fixture
def db_manager():
    """Create a fresh in-memory SQLite database for each test."""
    return create_test_database()


@pytest.fixture
def session(db_manager):
    """Yield a session from the in-memory database, auto-commits on success."""
    with db_manager.session_scope() as s:
        yield s


# =============================================================================
# Domain object fixtures
# =============================================================================

@pytest.fixture
def sample_symbol():
    """A known SPY put option symbol."""
    return dm.Symbol(
        ticker='SPY',
        asset_type=dm.AssetType.OPTION,
        option_type=dm.OptionType.PUT,
        strike=KNOWN_STRIKE,
        expiration=datetime(2026, 3, 20),
        description='SPY Mar 2026 455 Put',
        multiplier=100,
    )


@pytest.fixture
def sample_call_symbol():
    """A known SPY call option symbol."""
    return dm.Symbol(
        ticker='SPY',
        asset_type=dm.AssetType.OPTION,
        option_type=dm.OptionType.CALL,
        strike=KNOWN_STRIKE,
        expiration=datetime(2026, 3, 20),
        description='SPY Mar 2026 455 Call',
        multiplier=100,
    )


@pytest.fixture
def sample_greeks():
    """Known Greeks snapshot."""
    return dm.Greeks(
        delta=KNOWN_DELTA,
        gamma=KNOWN_GAMMA,
        theta=KNOWN_THETA,
        vega=KNOWN_VEGA,
    )


@pytest.fixture
def sample_leg(sample_symbol, sample_greeks):
    """A short put leg with known entry state."""
    return dm.Leg(
        id=str(uuid.uuid4()),
        symbol=sample_symbol,
        quantity=-1,
        side=dm.OrderSide.SELL_TO_OPEN,
        entry_price=KNOWN_ENTRY_PRICE,
        entry_time=datetime(2026, 2, 15, 10, 0, 0),
        entry_greeks=sample_greeks,
        entry_underlying_price=KNOWN_UNDERLYING_PRICE,
        entry_iv=Decimal('0.22'),
        current_price=Decimal('2.00'),
    )


@pytest.fixture
def sample_trade(sample_leg, sample_greeks):
    """An EXECUTED what-if trade with one leg."""
    return dm.Trade(
        id=str(uuid.uuid4()),
        legs=[sample_leg],
        strategy=dm.Strategy(
            name='Short Put',
            strategy_type=dm.StrategyType.SINGLE,
            risk_category=dm.RiskCategory.UNDEFINED,
        ),
        trade_type=dm.TradeType.WHAT_IF,
        trade_status=dm.TradeStatus.EXECUTED,
        underlying_symbol='SPY',
        entry_price=KNOWN_ENTRY_PRICE,
        entry_underlying_price=KNOWN_UNDERLYING_PRICE,
        entry_greeks=sample_greeks,
        entry_iv=Decimal('0.22'),
        trade_source=dm.TradeSource.MANUAL,
        notes='Test trade',
        tags=['test'],
        executed_at=datetime(2026, 2, 15, 10, 0, 0),
    )


@pytest.fixture
def sample_portfolio():
    """A what-if portfolio with known capital."""
    return dm.Portfolio.create_what_if(
        name='Test Portfolio',
        capital=Decimal('25000'),
        description='Unit test portfolio',
        risk_limits={
            'max_delta': 100,
            'max_position_pct': 20,
            'max_trade_risk_pct': 10,
        },
        broker='test_broker',
        account_id='test_portfolio',
    )


@pytest.fixture
def persisted_portfolio(session, sample_portfolio):
    """A portfolio that has been saved to the in-memory DB."""
    from trading_cotrader.repositories.portfolio import PortfolioRepository
    repo = PortfolioRepository(session)
    saved = repo.create_from_domain(sample_portfolio)
    session.flush()
    return saved
