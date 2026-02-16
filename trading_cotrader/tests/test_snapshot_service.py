"""
Tests for SnapshotService and ML Data Pipeline.

Covers:
- Daily snapshot capture (portfolio-level + position Greeks)
- ORM-direct snapshot capture (capture_all_portfolio_snapshots)
- Upsert behavior (update existing snapshot)
- Portfolio history retrieval
- Summary statistics
- ML pipeline accumulation and status
- Boundary cases (empty portfolios, no positions, deprecated portfolios)
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from trading_cotrader.core.database.session import create_test_database
from trading_cotrader.core.database.schema import (
    PortfolioORM,
    PositionORM,
    SymbolORM,
    DailyPerformanceORM,
    GreeksHistoryORM,
    TradeORM,
)
from trading_cotrader.services.snapshot_service import SnapshotService


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def db_manager():
    return create_test_database()


@pytest.fixture
def session(db_manager):
    with db_manager.session_scope() as s:
        yield s


@pytest.fixture
def portfolio_orm(session):
    """Create a real portfolio in DB."""
    p = PortfolioORM(
        id=str(uuid.uuid4()),
        name='Test Core Portfolio',
        portfolio_type='real',
        broker='tastytrade',
        account_id='TT_123',
        initial_capital=Decimal('100000'),
        cash_balance=Decimal('75000'),
        total_equity=Decimal('100500'),
        daily_pnl=Decimal('250'),
        realized_pnl=Decimal('100'),
        unrealized_pnl=Decimal('150'),
        portfolio_delta=Decimal('-45.00'),
        portfolio_gamma=Decimal('2.50'),
        portfolio_theta=Decimal('125.00'),
        portfolio_vega=Decimal('-300.00'),
        var_1d_95=Decimal('1200.00'),
        var_1d_99=Decimal('1800.00'),
        tags=[],
    )
    session.add(p)
    session.flush()
    return p


@pytest.fixture
def deprecated_portfolio(session):
    """Create a deprecated portfolio in DB (should be skipped)."""
    p = PortfolioORM(
        id=str(uuid.uuid4()),
        name='Deprecated Old Portfolio',
        portfolio_type='real',
        broker='cotrader',
        account_id='old_core',
        cash_balance=Decimal('0'),
        total_equity=Decimal('0'),
        tags=['deprecated'],
    )
    session.add(p)
    session.flush()
    return p


@pytest.fixture
def whatif_portfolio(session):
    """Create a WhatIf portfolio."""
    p = PortfolioORM(
        id=str(uuid.uuid4()),
        name='Test WhatIf Portfolio',
        portfolio_type='what_if',
        broker='tastytrade',
        account_id='TT_123_WI',
        cash_balance=Decimal('100000'),
        total_equity=Decimal('100000'),
        daily_pnl=Decimal('0'),
        portfolio_delta=Decimal('0'),
        portfolio_theta=Decimal('0'),
        tags=[],
    )
    session.add(p)
    session.flush()
    return p


@pytest.fixture
def symbol_orm(session):
    """Create a symbol for positions."""
    s = SymbolORM(
        id=str(uuid.uuid4()),
        ticker='SPY',
        asset_type='OPTION',
        option_type='PUT',
        strike=Decimal('450'),
        expiration=datetime(2026, 3, 20),
        multiplier=100,
    )
    session.add(s)
    session.flush()
    return s


@pytest.fixture
def position_orm(session, portfolio_orm, symbol_orm):
    """Create a position with Greeks."""
    pos = PositionORM(
        id=str(uuid.uuid4()),
        portfolio_id=portfolio_orm.id,
        symbol_id=symbol_orm.id,
        quantity=-1,
        entry_price=Decimal('3.50'),
        total_cost=Decimal('350'),
        current_price=Decimal('2.80'),
        current_underlying_price=Decimal('452.50'),
        delta=Decimal('-0.28'),
        gamma=Decimal('0.015'),
        theta=Decimal('-0.04'),
        vega=Decimal('0.11'),
        rho=Decimal('-0.02'),
    )
    session.add(pos)
    session.flush()
    return pos


@pytest.fixture
def second_position(session, portfolio_orm, symbol_orm):
    """Second position in same portfolio."""
    pos = PositionORM(
        id=str(uuid.uuid4()),
        portfolio_id=portfolio_orm.id,
        symbol_id=symbol_orm.id,
        quantity=2,
        entry_price=Decimal('5.00'),
        total_cost=Decimal('1000'),
        current_price=Decimal('5.50'),
        current_underlying_price=Decimal('452.50'),
        delta=Decimal('0.55'),
        gamma=Decimal('0.020'),
        theta=Decimal('-0.06'),
        vega=Decimal('0.15'),
    )
    session.add(pos)
    session.flush()
    return pos


# =============================================================================
# SnapshotService — capture_all_portfolio_snapshots (ORM-direct)
# =============================================================================

class TestCaptureAllPortfolioSnapshots:
    """Test the ORM-direct batch snapshot method."""

    def test_captures_active_portfolio(self, session, portfolio_orm, position_orm):
        """Should capture snapshot for an active portfolio."""
        svc = SnapshotService(session)
        results = svc.capture_all_portfolio_snapshots()

        assert portfolio_orm.name in results
        assert results[portfolio_orm.name] is True

        # Verify DailyPerformanceORM was created
        snapshots = session.query(DailyPerformanceORM).filter_by(
            portfolio_id=portfolio_orm.id
        ).all()
        assert len(snapshots) == 1

        snap = snapshots[0]
        assert snap.total_equity == Decimal('100500')
        assert snap.cash_balance == Decimal('75000')
        assert snap.daily_pnl == Decimal('250')
        assert snap.portfolio_delta == Decimal('-45.00')
        assert snap.portfolio_theta == Decimal('125.00')
        assert snap.var_1d_95 == Decimal('1200.00')

    def test_captures_greeks_history(self, session, portfolio_orm, position_orm):
        """Should capture Greeks history for positions."""
        svc = SnapshotService(session)
        svc.capture_all_portfolio_snapshots()

        history = session.query(GreeksHistoryORM).filter_by(
            position_id=position_orm.id
        ).all()
        assert len(history) == 1

        h = history[0]
        assert h.delta == Decimal('-0.28')
        assert h.theta == Decimal('-0.04')
        assert h.underlying_price == Decimal('452.50')

    def test_captures_multiple_positions(
        self, session, portfolio_orm, position_orm, second_position
    ):
        """Should capture Greeks for all positions in portfolio."""
        svc = SnapshotService(session)
        svc.capture_all_portfolio_snapshots()

        history = session.query(GreeksHistoryORM).all()
        assert len(history) == 2

    def test_skips_deprecated_portfolio(
        self, session, portfolio_orm, deprecated_portfolio
    ):
        """Deprecated portfolios should NOT get snapshots."""
        svc = SnapshotService(session)
        results = svc.capture_all_portfolio_snapshots()

        assert portfolio_orm.name in results
        assert deprecated_portfolio.name not in results

        # Only one snapshot created (for active portfolio)
        count = session.query(DailyPerformanceORM).count()
        assert count == 1

    def test_includes_whatif_portfolio(
        self, session, portfolio_orm, whatif_portfolio
    ):
        """WhatIf portfolios should also get snapshots."""
        svc = SnapshotService(session)
        results = svc.capture_all_portfolio_snapshots()

        assert portfolio_orm.name in results
        assert whatif_portfolio.name in results
        assert len(results) == 2

    def test_upsert_updates_existing_snapshot(self, session, portfolio_orm, position_orm):
        """Running twice on same day should update, not duplicate."""
        svc = SnapshotService(session)

        # First capture
        svc.capture_all_portfolio_snapshots()
        count1 = session.query(DailyPerformanceORM).count()

        # Modify equity
        portfolio_orm.total_equity = Decimal('101000')
        session.flush()

        # Second capture (same day)
        svc.capture_all_portfolio_snapshots()
        count2 = session.query(DailyPerformanceORM).count()

        assert count1 == count2  # No duplicate
        snap = session.query(DailyPerformanceORM).filter_by(
            portfolio_id=portfolio_orm.id
        ).first()
        assert snap.total_equity == Decimal('101000')  # Updated value

    def test_empty_portfolio_no_positions(self, session, portfolio_orm):
        """Portfolio with zero positions should still get a snapshot."""
        svc = SnapshotService(session)
        results = svc.capture_all_portfolio_snapshots()

        assert results[portfolio_orm.name] is True
        snap = session.query(DailyPerformanceORM).filter_by(
            portfolio_id=portfolio_orm.id
        ).first()
        assert snap.num_positions == 0

    def test_position_without_greeks_skipped(self, session, portfolio_orm, symbol_orm):
        """Position with no Greeks data should not get history entry."""
        pos = PositionORM(
            id=str(uuid.uuid4()),
            portfolio_id=portfolio_orm.id,
            symbol_id=symbol_orm.id,
            quantity=100,
            entry_price=Decimal('150.00'),
            total_cost=Decimal('15000'),
            # No Greeks set (all default to 0 / None)
        )
        session.add(pos)
        session.flush()

        svc = SnapshotService(session)
        svc.capture_all_portfolio_snapshots()

        # No Greeks history for this position
        history = session.query(GreeksHistoryORM).filter_by(
            position_id=pos.id
        ).all()
        assert len(history) == 0

    def test_open_trade_count(self, session, portfolio_orm, symbol_orm):
        """Snapshot should count open trades."""
        # Create an open trade
        trade = TradeORM(
            id=str(uuid.uuid4()),
            portfolio_id=portfolio_orm.id,
            underlying_symbol='SPY',
            trade_type='what_if',
            trade_status='executed',
            is_open=True,
            entry_price=Decimal('2.50'),
        )
        session.add(trade)
        session.flush()

        svc = SnapshotService(session)
        svc.capture_all_portfolio_snapshots()

        snap = session.query(DailyPerformanceORM).filter_by(
            portfolio_id=portfolio_orm.id
        ).first()
        assert snap.num_trades == 1


# =============================================================================
# SnapshotService — history and stats
# =============================================================================

class TestPortfolioHistory:
    """Test snapshot retrieval methods."""

    def test_get_portfolio_history(self, session, portfolio_orm):
        """Should retrieve snapshots within date range."""
        svc = SnapshotService(session)

        # Insert 5 snapshots: oldest first (4 days ago) to newest (today)
        for i in range(5):
            snap = DailyPerformanceORM(
                id=str(uuid.uuid4()),
                portfolio_id=portfolio_orm.id,
                date=datetime.utcnow() - timedelta(days=4 - i),
                total_equity=Decimal('100000') + Decimal(str(i * 100)),
                cash_balance=Decimal('75000'),
                daily_pnl=Decimal(str(i * 50)),
                num_positions=3,
                created_at=datetime.utcnow(),
            )
            session.add(snap)
        session.flush()

        history = svc.get_portfolio_history(portfolio_orm.id, days=30)
        assert len(history) == 5
        # Should be ordered by date ascending — equity grows
        assert history[0].total_equity <= history[-1].total_equity

    def test_get_portfolio_history_respects_date_range(self, session, portfolio_orm):
        """Snapshots outside range should not be returned."""
        svc = SnapshotService(session)

        # Recent snapshot
        session.add(DailyPerformanceORM(
            id=str(uuid.uuid4()),
            portfolio_id=portfolio_orm.id,
            date=datetime.utcnow(),
            total_equity=Decimal('100000'),
            cash_balance=Decimal('75000'),
            created_at=datetime.utcnow(),
        ))

        # Old snapshot (60 days ago)
        session.add(DailyPerformanceORM(
            id=str(uuid.uuid4()),
            portfolio_id=portfolio_orm.id,
            date=datetime.utcnow() - timedelta(days=60),
            total_equity=Decimal('95000'),
            cash_balance=Decimal('70000'),
            created_at=datetime.utcnow(),
        ))
        session.flush()

        # Query last 30 days — should only get 1
        history = svc.get_portfolio_history(portfolio_orm.id, days=30)
        assert len(history) == 1

    def test_summary_stats(self, session, portfolio_orm):
        """Summary stats should calculate averages, min/max."""
        svc = SnapshotService(session)

        daily_pnls = [100, -50, 200, -25, 150]
        for i, pnl in enumerate(daily_pnls):
            session.add(DailyPerformanceORM(
                id=str(uuid.uuid4()),
                portfolio_id=portfolio_orm.id,
                date=datetime.utcnow() - timedelta(days=len(daily_pnls) - i),
                total_equity=Decimal('100000') + Decimal(str(sum(daily_pnls[:i+1]))),
                cash_balance=Decimal('75000'),
                daily_pnl=Decimal(str(pnl)),
                portfolio_delta=Decimal(str(-40 + i * 5)),
                created_at=datetime.utcnow(),
            ))
        session.flush()

        stats = svc.get_summary_stats(portfolio_orm.id, days=30)
        assert stats['days_tracked'] == 5
        assert stats['winning_days'] == 3
        assert stats['losing_days'] == 2
        assert stats['total_pnl'] == sum(daily_pnls)
        assert stats['win_rate'] == 60.0

    def test_summary_stats_empty_returns_empty(self, session, portfolio_orm):
        """No snapshots should return empty dict."""
        svc = SnapshotService(session)
        stats = svc.get_summary_stats(portfolio_orm.id, days=30)
        assert stats == {}


# =============================================================================
# SnapshotService — position Greeks history
# =============================================================================

class TestPositionGreeksHistory:
    """Test position-level Greeks retrieval."""

    def test_get_position_greeks_history(self, session, position_orm):
        """Should return Greeks evolution for a position."""
        svc = SnapshotService(session)

        for i in range(3):
            session.add(GreeksHistoryORM(
                id=str(uuid.uuid4()),
                position_id=position_orm.id,
                timestamp=datetime.utcnow() - timedelta(days=i),
                delta=Decimal(str(-0.28 + i * 0.02)),
                gamma=Decimal('0.015'),
                theta=Decimal('-0.04'),
                vega=Decimal('0.11'),
                underlying_price=Decimal(str(450 + i * 2)),
                created_at=datetime.utcnow(),
            ))
        session.flush()

        history = svc.get_position_greeks_history(position_orm.id, days=30)
        assert len(history) == 3


# =============================================================================
# ML Data Pipeline
# =============================================================================

class TestMLDataPipeline:
    """Test ML pipeline integration with snapshots."""

    def test_accumulate_captures_snapshot(self, session, portfolio_orm, position_orm):
        """ML accumulate should create a snapshot if none exists."""
        from trading_cotrader.ai_cotrader.data_pipeline import MLDataPipeline

        pipeline = MLDataPipeline(session)
        success = pipeline.accumulate_training_data(
            portfolio=portfolio_orm,
            positions=[position_orm],
        )
        assert success is True

        # Snapshot should exist
        count = session.query(DailyPerformanceORM).filter_by(
            portfolio_id=portfolio_orm.id
        ).count()
        assert count == 1

    def test_accumulate_skips_if_snapshot_exists(self, session, portfolio_orm):
        """Should not duplicate snapshots on same day."""
        from trading_cotrader.ai_cotrader.data_pipeline import MLDataPipeline

        # Pre-create today's snapshot
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        session.add(DailyPerformanceORM(
            id=str(uuid.uuid4()),
            portfolio_id=portfolio_orm.id,
            date=today,
            total_equity=Decimal('100000'),
            cash_balance=Decimal('75000'),
            created_at=datetime.utcnow(),
        ))
        session.flush()

        pipeline = MLDataPipeline(session)
        pipeline.accumulate_training_data(
            portfolio=portfolio_orm,
            positions=[],
        )

        # Still just 1 snapshot
        count = session.query(DailyPerformanceORM).filter_by(
            portfolio_id=portfolio_orm.id
        ).count()
        assert count == 1

    def test_ml_status_reports_correctly(self, session, portfolio_orm):
        """ML status should report snapshot and event counts."""
        from trading_cotrader.ai_cotrader.data_pipeline import MLDataPipeline

        pipeline = MLDataPipeline(session)
        status = pipeline.get_ml_status()

        assert 'snapshots' in status
        assert 'total_events' in status
        assert 'events_with_outcomes' in status
        assert 'ready_for_supervised' in status
        assert 'ready_for_rl' in status
        assert 'recommendation' in status

    def test_ml_not_ready_with_few_samples(self, session, portfolio_orm):
        """Should report not ready with insufficient data."""
        from trading_cotrader.ai_cotrader.data_pipeline import MLDataPipeline

        pipeline = MLDataPipeline(session)
        status = pipeline.get_ml_status()

        assert status['ready_for_supervised'] is False
        assert status['ready_for_rl'] is False

    def test_sample_count_starts_at_zero(self, session, portfolio_orm):
        """Fresh DB should have zero samples."""
        from trading_cotrader.ai_cotrader.data_pipeline import MLDataPipeline

        pipeline = MLDataPipeline(session)
        count = pipeline.get_sample_count()
        assert count == 0

    def test_portfolio_features_history(self, session, portfolio_orm):
        """Should return feature dicts from snapshots."""
        from trading_cotrader.ai_cotrader.data_pipeline import MLDataPipeline

        # Create some snapshots
        for i in range(3):
            session.add(DailyPerformanceORM(
                id=str(uuid.uuid4()),
                portfolio_id=portfolio_orm.id,
                date=datetime.utcnow() - timedelta(days=i),
                total_equity=Decimal('100000'),
                cash_balance=Decimal('75000'),
                daily_pnl=Decimal(str(i * 100)),
                portfolio_delta=Decimal('-40'),
                portfolio_theta=Decimal('100'),
                portfolio_vega=Decimal('-200'),
                num_positions=5,
                created_at=datetime.utcnow(),
            ))
        session.flush()

        pipeline = MLDataPipeline(session)
        features = pipeline.get_portfolio_features_history(portfolio_orm.id, days=30)
        assert len(features) == 3
        assert 'total_equity' in features[0]
        assert 'portfolio_delta' in features[0]
        assert 'daily_pnl' in features[0]
