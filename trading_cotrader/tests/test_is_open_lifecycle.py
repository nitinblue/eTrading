"""
Tests for the is_open bug fix.

Validates that is_open is always computed from trade_status in the repository,
and the domain Trade.is_open @property is consistent with trade_status.
"""

import pytest
from decimal import Decimal
from datetime import datetime

import trading_cotrader.core.models.domain as dm
from trading_cotrader.repositories.trade import TradeRepository
from trading_cotrader.repositories.portfolio import PortfolioRepository


class TestDomainIsOpenProperty:
    """Test that the domain Trade.is_open property matches trade_status."""

    def test_executed_is_open(self):
        t = dm.Trade(
            underlying_symbol='SPY',
            trade_status=dm.TradeStatus.EXECUTED,
            trade_type=dm.TradeType.WHAT_IF,
        )
        assert t.is_open is True

    def test_partial_is_open(self):
        t = dm.Trade(
            underlying_symbol='SPY',
            trade_status=dm.TradeStatus.PARTIAL,
            trade_type=dm.TradeType.WHAT_IF,
        )
        assert t.is_open is True

    def test_intent_not_open(self):
        t = dm.Trade(
            underlying_symbol='SPY',
            trade_status=dm.TradeStatus.INTENT,
            trade_type=dm.TradeType.WHAT_IF,
        )
        assert t.is_open is False

    def test_closed_not_open(self):
        t = dm.Trade(
            underlying_symbol='SPY',
            trade_status=dm.TradeStatus.CLOSED,
            trade_type=dm.TradeType.WHAT_IF,
        )
        assert t.is_open is False


class TestIsOpenDBRoundTrip:
    """Test that is_open in the DB matches trade_status after round-trips."""

    def test_executed_trade_is_open_in_db(self, session, persisted_portfolio, sample_trade):
        """EXECUTED trade → is_open=True in DB."""
        repo = TradeRepository(session)
        created = repo.create_from_domain(sample_trade, persisted_portfolio.id)

        assert created is not None
        assert created.is_open is True
        assert created.trade_status == dm.TradeStatus.EXECUTED

    def test_intent_trade_not_open_in_db(self, session, persisted_portfolio, sample_leg):
        """INTENT trade → is_open=False in DB."""
        trade = dm.Trade(
            underlying_symbol='SPY',
            trade_status=dm.TradeStatus.INTENT,
            trade_type=dm.TradeType.WHAT_IF,
            legs=[sample_leg],
        )

        repo = TradeRepository(session)
        created = repo.create_from_domain(trade, persisted_portfolio.id)

        assert created is not None
        assert created.is_open is False
        assert created.trade_status == dm.TradeStatus.INTENT

    def test_close_trade_sets_is_open_false(self, session, persisted_portfolio, sample_trade):
        """close_trade() → is_open=False and trade_status='closed'."""
        repo = TradeRepository(session)
        created = repo.create_from_domain(sample_trade, persisted_portfolio.id)
        assert created is not None

        success = repo.close_trade(
            created.id,
            exit_price=Decimal('1.25'),
            exit_reason='Profit target',
        )
        assert success is True

        # Re-read from DB
        closed = repo.to_domain(repo.get_by_id(created.id))
        assert closed.is_open is False
        assert closed.trade_status == dm.TradeStatus.CLOSED

    def test_round_trip_preserves_is_open(self, session, persisted_portfolio, sample_trade):
        """Create → read → verify is_open matches trade_status."""
        repo = TradeRepository(session)
        created = repo.create_from_domain(sample_trade, persisted_portfolio.id)
        assert created is not None

        # Read back via get_by_portfolio
        trades = repo.get_by_portfolio(persisted_portfolio.id, open_only=True)
        assert len(trades) == 1
        assert trades[0].is_open is True
        assert trades[0].trade_status == dm.TradeStatus.EXECUTED

    def test_update_status_updates_is_open(self, session, persisted_portfolio, sample_trade):
        """Updating trade_status via update_from_domain → is_open follows."""
        repo = TradeRepository(session)
        created = repo.create_from_domain(sample_trade, persisted_portfolio.id)
        assert created is not None
        assert created.is_open is True

        # Change status to CLOSED on the domain object
        created.trade_status = dm.TradeStatus.CLOSED
        created.closed_at = datetime.utcnow()
        updated = repo.update_from_domain(created)

        assert updated is not None
        assert updated.is_open is False
        assert updated.trade_status == dm.TradeStatus.CLOSED
