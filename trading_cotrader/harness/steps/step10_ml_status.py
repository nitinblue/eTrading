"""
Step 10: AI/ML Status
======================

Shows:
- ML data readiness (event counts, snapshot counts)
- Trade table stats (total trades, by type, by status)
- Top 5 recent trades
- Feature extraction readiness
"""

from trading_cotrader.harness.base import (
    TestStep, StepResult, rich_table, format_currency
)


class MLStatusStep(TestStep):
    """Harness step for AI/ML status and data readiness."""

    name = "Step 10: AI/ML Status"
    description = "Show ML data readiness, trade stats, and feature extraction status"

    def execute(self) -> StepResult:
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.core.database.schema import (
            TradeORM, TradeEventORM
        )
        from sqlalchemy import func

        tables = []
        messages = []

        with session_scope() as session:
            # 1. ML Data Pipeline stats
            total_events = session.query(func.count(TradeEventORM.event_id)).scalar() or 0
            events_with_outcomes = (
                session.query(func.count(TradeEventORM.event_id))
                .filter(TradeEventORM.outcome.isnot(None))
                .scalar()
            ) or 0

            # Snapshot count (from MarketDataSnapshotORM if available)
            total_snapshots = 0
            try:
                from trading_cotrader.core.database.schema import MarketDataSnapshotORM
                total_snapshots = session.query(func.count(MarketDataSnapshotORM.id)).scalar() or 0
            except Exception:
                pass

            # Trade counts
            total_trades = session.query(func.count(TradeORM.id)).scalar() or 0

            # By type
            type_counts = (
                session.query(TradeORM.trade_type, func.count(TradeORM.id))
                .group_by(TradeORM.trade_type)
                .all()
            )

            # By status
            status_counts = (
                session.query(TradeORM.trade_status, func.count(TradeORM.id))
                .group_by(TradeORM.trade_status)
                .all()
            )

            # ML readiness table
            ready_supervised = events_with_outcomes >= 100
            ready_rl = events_with_outcomes >= 500

            ml_data = [
                ["Total Events", total_events, ""],
                ["Events with Outcomes", events_with_outcomes,
                 "OK" if events_with_outcomes > 0 else "None yet"],
                ["Portfolio Snapshots", total_snapshots, ""],
                ["Total Trades", total_trades, ""],
                ["", "", ""],
                ["Supervised Learning", "READY" if ready_supervised else "NOT READY",
                 f"Need {max(0, 100 - events_with_outcomes)} more outcomes"],
                ["Reinforcement Learning", "READY" if ready_rl else "NOT READY",
                 f"Need {max(0, 500 - events_with_outcomes)} more outcomes"],
            ]

            tables.append(rich_table(
                ml_data,
                headers=["Metric", "Value", "Note"],
                title="ML Data Readiness"
            ))

            # Trade stats table
            if total_trades > 0:
                trade_stats = []
                trade_stats.append(["Total Trades", total_trades, ""])
                for trade_type, count in sorted(type_counts, key=lambda x: -x[1]):
                    trade_stats.append([f"  type={trade_type}", count, ""])
                trade_stats.append(["", "", ""])
                for status, count in sorted(status_counts, key=lambda x: -x[1]):
                    trade_stats.append([f"  status={status}", count, ""])

                tables.append(rich_table(
                    trade_stats,
                    headers=["Category", "Count", "Note"],
                    title="Trade Table Stats"
                ))

                # Top 5 recent trades
                recent_trades = (
                    session.query(TradeORM)
                    .order_by(TradeORM.created_at.desc())
                    .limit(5)
                    .all()
                )

                if recent_trades:
                    recent_data = []
                    for t in recent_trades:
                        created = t.created_at.strftime('%m/%d %H:%M') if t.created_at else '-'
                        delta = f"{float(t.entry_delta):.2f}" if t.entry_delta else '-'
                        theta = f"{float(t.entry_theta):.2f}" if t.entry_theta else '-'
                        entry = format_currency(t.entry_price) if t.entry_price else '-'

                        recent_data.append([
                            t.underlying_symbol or '-',
                            (t.trade_type or '-')[:8],
                            (t.trade_status or '-')[:8],
                            entry,
                            delta,
                            theta,
                            created,
                        ])

                    tables.append(rich_table(
                        recent_data,
                        headers=["Underlying", "Type", "Status", "Entry",
                                 "Delta", "Theta", "Created"],
                        title="5 Most Recent Trades"
                    ))

            # 2. Feature extraction check
            try:
                from trading_cotrader.ai_cotrader.feature_engineering.feature_extractor import FeatureExtractor
                extractor = FeatureExtractor()
                messages.append("FeatureExtractor: importable, 55-dim state vectors")
            except ImportError:
                messages.append("FeatureExtractor: import failed")

            # 3. Model check
            try:
                from trading_cotrader.ai_cotrader.learning.supervised import PatternRecognizer
                recognizer = PatternRecognizer()
                fitted = "TRAINED" if recognizer.is_fitted else "NOT TRAINED"
                messages.append(f"PatternRecognizer: {fitted}")
            except ImportError:
                messages.append("PatternRecognizer: import failed")

            try:
                from trading_cotrader.ai_cotrader.learning.reinforcement import TradingAdvisor
                messages.append("TradingAdvisor: importable")
            except ImportError:
                messages.append("TradingAdvisor: import failed")

            messages.append(f"Summary: {total_trades} trades, {total_events} events, "
                          f"{events_with_outcomes} with outcomes, {total_snapshots} snapshots")

        return self._success_result(tables=tables, messages=messages)
