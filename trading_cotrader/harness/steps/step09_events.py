"""
Step 09: Events & Event Analytics
==================================

Shows:
- Event table stats (total, by type, by underlying)
- Top 5 recent trade events with details
- Decision patterns and rationale history
"""

from typing import List
from trading_cotrader.harness.base import (
    TestStep, StepResult, rich_table, format_currency, format_greek
)


class EventsStep(TestStep):
    """Harness step for events and event analytics."""

    name = "Step 9: Events & Analytics"
    description = "Show event table stats and recent trade events"

    def execute(self) -> StepResult:
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.repositories.event import EventRepository
        from trading_cotrader.core.database.schema import TradeEventORM
        from sqlalchemy import func

        tables = []
        messages = []

        with session_scope() as session:
            event_repo = EventRepository(session)

            # 1. Table stats — counts by event type
            type_counts = (
                session.query(
                    TradeEventORM.event_type,
                    func.count(TradeEventORM.event_id)
                )
                .group_by(TradeEventORM.event_type)
                .all()
            )

            total_events = sum(c for _, c in type_counts)

            if total_events == 0:
                messages.append("No events in DB yet — book trades to generate events")
                return self._success_result(tables=tables, messages=messages)

            # Stats table
            stats_data = [["Total Events", total_events, ""]]
            for event_type, count in sorted(type_counts, key=lambda x: -x[1]):
                pct = f"{count / total_events * 100:.0f}%"
                stats_data.append([f"  {event_type}", count, pct])

            # Count by underlying
            underlying_counts = (
                session.query(
                    TradeEventORM.underlying_symbol,
                    func.count(TradeEventORM.event_id)
                )
                .group_by(TradeEventORM.underlying_symbol)
                .order_by(func.count(TradeEventORM.event_id).desc())
                .limit(10)
                .all()
            )
            stats_data.append(["", "", ""])
            stats_data.append(["By Underlying", "", ""])
            for underlying, count in underlying_counts:
                stats_data.append([f"  {underlying or 'N/A'}", count, ""])

            # Events with outcomes (for ML readiness)
            events_with_outcomes = (
                session.query(func.count(TradeEventORM.event_id))
                .filter(TradeEventORM.outcome.isnot(None))
                .scalar()
            ) or 0
            stats_data.append(["", "", ""])
            stats_data.append(["With Outcomes", events_with_outcomes,
                              "Ready for ML" if events_with_outcomes >= 100 else "Need more"])

            tables.append(rich_table(
                stats_data,
                headers=["Metric", "Count", "Note"],
                title="Event Table Stats"
            ))

            # 2. Top 5 recent events
            recent_events_orm = (
                session.query(TradeEventORM)
                .order_by(TradeEventORM.timestamp.desc())
                .limit(5)
                .all()
            )

            if recent_events_orm:
                recent_data = []
                for e in recent_events_orm:
                    ts = e.timestamp.strftime('%m/%d %H:%M') if e.timestamp else '-'

                    # Extract rationale from decision_context JSON
                    rationale = ''
                    if e.decision_context and isinstance(e.decision_context, dict):
                        rationale = e.decision_context.get('rationale', '')[:40]

                    delta_str = f"{float(e.entry_delta):.2f}" if e.entry_delta else '-'
                    theta_str = f"{float(e.entry_theta):.2f}" if e.entry_theta else '-'
                    credit = format_currency(e.net_credit_debit) if e.net_credit_debit else '-'

                    recent_data.append([
                        ts,
                        e.event_type or '-',
                        e.underlying_symbol or '-',
                        e.strategy_type or '-',
                        delta_str,
                        theta_str,
                        credit,
                        rationale,
                    ])

                tables.append(rich_table(
                    recent_data,
                    headers=["Time", "Type", "Underlying", "Strategy",
                             "Delta", "Theta", "Credit/Debit", "Rationale"],
                    title="5 Most Recent Events"
                ))

            messages.append(f"{total_events} events, {events_with_outcomes} with outcomes")

        return self._success_result(tables=tables, messages=messages)
