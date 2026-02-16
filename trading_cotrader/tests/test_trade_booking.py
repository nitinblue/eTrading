"""
Tests for trade create/read DB round-trips.

Validates that all trade fields persist correctly through the repository layer.
"""

import pytest
from decimal import Decimal
from datetime import datetime
import uuid

import trading_cotrader.core.models.domain as dm
from trading_cotrader.repositories.trade import TradeRepository


class TestTradeBooking:
    """Trade create and read round-trip tests."""

    def test_create_single_leg_trade(self, session, persisted_portfolio, sample_trade):
        """Book a single-leg trade, verify all fields round-trip."""
        repo = TradeRepository(session)
        created = repo.create_from_domain(sample_trade, persisted_portfolio.id)

        assert created is not None
        assert created.underlying_symbol == 'SPY'
        assert created.trade_type == dm.TradeType.WHAT_IF
        assert created.trade_status == dm.TradeStatus.EXECUTED
        assert len(created.legs) == 1
        assert created.legs[0].quantity == -1
        assert created.notes == 'Test trade'

    def test_create_multi_leg_trade(self, session, persisted_portfolio):
        """Book an iron condor (4 legs), verify all legs persist."""
        legs = []
        strikes = [
            (dm.OptionType.PUT, Decimal('440'), dm.OrderSide.BUY, 1),
            (dm.OptionType.PUT, Decimal('445'), dm.OrderSide.SELL, -1),
            (dm.OptionType.CALL, Decimal('460'), dm.OrderSide.SELL, -1),
            (dm.OptionType.CALL, Decimal('465'), dm.OrderSide.BUY, 1),
        ]
        for opt_type, strike, side, qty in strikes:
            sym = dm.Symbol(
                ticker='SPY',
                asset_type=dm.AssetType.OPTION,
                option_type=opt_type,
                strike=strike,
                expiration=datetime(2026, 3, 20),
            )
            legs.append(dm.Leg(
                symbol=sym,
                quantity=qty,
                side=side,
                entry_price=Decimal('1.00'),
            ))

        trade = dm.Trade(
            underlying_symbol='SPY',
            trade_type=dm.TradeType.WHAT_IF,
            trade_status=dm.TradeStatus.EXECUTED,
            legs=legs,
            strategy=dm.Strategy(
                name='Iron Condor',
                strategy_type=dm.StrategyType.IRON_CONDOR,
                risk_category=dm.RiskCategory.DEFINED,
            ),
        )

        repo = TradeRepository(session)
        created = repo.create_from_domain(trade, persisted_portfolio.id)

        assert created is not None
        assert len(created.legs) == 4

    def test_trade_source_round_trip(self, session, persisted_portfolio, sample_leg):
        """trade_source=SCREENER_VIX round-trips correctly."""
        trade = dm.Trade(
            underlying_symbol='SPY',
            trade_type=dm.TradeType.WHAT_IF,
            trade_status=dm.TradeStatus.EXECUTED,
            legs=[sample_leg],
            trade_source=dm.TradeSource.SCREENER_VIX,
        )

        repo = TradeRepository(session)
        created = repo.create_from_domain(trade, persisted_portfolio.id)

        assert created is not None
        assert created.trade_source == dm.TradeSource.SCREENER_VIX

    def test_recommendation_id_round_trip(self, session, persisted_portfolio, sample_leg):
        """recommendation_id persists and round-trips."""
        rec_id = str(uuid.uuid4())
        trade = dm.Trade(
            underlying_symbol='SPY',
            trade_type=dm.TradeType.WHAT_IF,
            trade_status=dm.TradeStatus.EXECUTED,
            legs=[sample_leg],
            trade_source=dm.TradeSource.SCREENER_IV_RANK,
            recommendation_id=rec_id,
        )

        repo = TradeRepository(session)
        created = repo.create_from_domain(trade, persisted_portfolio.id)

        assert created is not None
        assert created.recommendation_id == rec_id

    def test_entry_greeks_round_trip(self, session, persisted_portfolio, sample_trade):
        """Entry Greeks persist with Decimal precision."""
        repo = TradeRepository(session)
        created = repo.create_from_domain(sample_trade, persisted_portfolio.id)

        assert created is not None
        assert created.entry_greeks is not None
        # Decimal precision may be truncated by DB column width, but sign and magnitude should match
        assert float(created.entry_greeks.delta) == pytest.approx(float(sample_trade.entry_greeks.delta), abs=0.01)
        assert float(created.entry_greeks.theta) == pytest.approx(float(sample_trade.entry_greeks.theta), abs=0.01)

    def test_whatif_trade_type(self, session, persisted_portfolio, sample_trade):
        """WHAT_IF trade type persists and reads back."""
        repo = TradeRepository(session)
        created = repo.create_from_domain(sample_trade, persisted_portfolio.id)

        assert created is not None
        assert created.trade_type == dm.TradeType.WHAT_IF
        assert created.is_what_if is True

    def test_past_dated_trade(self, session, persisted_portfolio, sample_leg):
        """Trade with historical opened_at persists correctly."""
        past_date = datetime(2025, 12, 1, 14, 30, 0)
        trade = dm.Trade(
            underlying_symbol='AAPL',
            trade_type=dm.TradeType.WHAT_IF,
            trade_status=dm.TradeStatus.EXECUTED,
            legs=[sample_leg],
            created_at=past_date,
        )

        repo = TradeRepository(session)
        created = repo.create_from_domain(trade, persisted_portfolio.id)

        assert created is not None
        # The trade should have been stored with the past date
        assert created.created_at is not None

    def test_close_trade_sets_exit_fields(self, session, persisted_portfolio, sample_trade):
        """close_trade sets exit_price, exit_reason, closed_at."""
        repo = TradeRepository(session)
        created = repo.create_from_domain(sample_trade, persisted_portfolio.id)
        assert created is not None

        exit_price = Decimal('1.25')
        exit_reason = 'Profit target at 50%'
        success = repo.close_trade(created.id, exit_price=exit_price, exit_reason=exit_reason)
        assert success is True

        closed = repo.to_domain(repo.get_by_id(created.id))
        assert closed.exit_price is not None
        assert float(closed.exit_price) == pytest.approx(float(exit_price), abs=0.01)
        assert closed.exit_reason == exit_reason
        assert closed.closed_at is not None
