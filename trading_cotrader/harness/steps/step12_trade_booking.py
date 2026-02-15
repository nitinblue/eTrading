"""
Step 12: Trade Booking Service
==============================

Tests the end-to-end WhatIf trade booking flow:
    Streamer symbols → DXLink Greeks/Quotes → Trade → DB → Containers → Snapshot → ML

Requires broker connection (skipped in --mock mode).
"""

from typing import Dict, Any

from trading_cotrader.harness.base import TestStep, StepResult, rich_table


class TradeBookingStep(TestStep):
    name = "Trade Booking Service"
    description = "Book a WhatIf trade with live Greeks from DXLink"

    def execute(self) -> StepResult:
        from trading_cotrader.services.trade_booking_service import (
            TradeBookingService, LegInput
        )
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.repositories.trade import TradeRepository
        from trading_cotrader.repositories.event import EventRepository

        tables = []
        messages = []

        # Check if broker is available from earlier steps
        broker = self.context.get('broker')
        if not broker:
            return self._fail_result(
                "No broker in context — step requires broker connection (run without --mock)"
            )

        # Create service
        container_manager = self.context.get('container_manager')
        service = TradeBookingService(
            broker=broker,
            container_manager=container_manager,
        )

        # Book a sample put credit spread
        messages.append("Booking WhatIf: SPY put credit spread")
        messages.append("  Sell .SPY260320P550 × -1")
        messages.append("  Buy  .SPY260320P540 × +1")

        result = service.book_whatif_trade(
            underlying="SPY",
            strategy_type="vertical_spread",
            legs=[
                LegInput(streamer_symbol=".SPY260320P550", quantity=-1),
                LegInput(streamer_symbol=".SPY260320P540", quantity=1),
            ],
            notes="Harness step 12 test trade",
            rationale="Automated test of trade booking flow",
            confidence=5,
        )

        if not result.success:
            return self._fail_result(f"Trade booking failed: {result.error}")

        # Trade details table
        trade_data = [
            ["Trade ID", result.trade_id[:12] + "..."],
            ["Strategy", result.strategy_type],
            ["Entry Price", f"${result.entry_price:.2f}"],
            ["Delta", f"{result.total_greeks.get('delta', 0):.4f}"],
            ["Gamma", f"{result.total_greeks.get('gamma', 0):.4f}"],
            ["Theta", f"{result.total_greeks.get('theta', 0):.4f}"],
            ["Vega", f"{result.total_greeks.get('vega', 0):.4f}"],
            ["Event ID", result.event_id[:12] + "..."],
        ]
        tables.append(rich_table(
            trade_data,
            headers=["Field", "Value"],
            title="📋 WhatIf Trade Booked"
        ))

        # Legs table
        leg_data = []
        for leg in result.legs:
            leg_data.append([
                leg.streamer_symbol,
                str(leg.quantity),
                f"${leg.mid_price:.2f}",
                f"${leg.bid:.2f}",
                f"${leg.ask:.2f}",
                f"{leg.per_contract_greeks['delta']:.4f}",
                f"{leg.per_contract_greeks['theta']:.4f}",
                f"{leg.position_greeks['delta']:.2f}",
                f"{leg.position_greeks['theta']:.2f}",
            ])
        tables.append(rich_table(
            leg_data,
            headers=["Symbol", "Qty", "Mid", "Bid", "Ask",
                      "Δ/ct", "Θ/ct", "Pos Δ", "Pos Θ"],
            title="📊 Leg Details"
        ))

        # Verify DB persistence
        with session_scope() as session:
            trade_repo = TradeRepository(session)
            event_repo = EventRepository(session)

            db_trade = trade_repo.get_by_id(result.trade_id)
            db_events = event_repo.get_by_trade(result.trade_id)

            verify_data = [
                ["Trade in DB", "YES" if db_trade else "NO"],
                ["Trade type", getattr(db_trade, 'trade_type', 'N/A')],
                ["Trade status", getattr(db_trade, 'trade_status', 'N/A')],
                ["Events count", str(len(db_events))],
            ]
            tables.append(rich_table(
                verify_data,
                headers=["Check", "Result"],
                title="✅ DB Verification"
            ))

            if not db_trade:
                return self._fail_result("Trade not found in database", tables=tables)

        messages.append(f"Trade {result.trade_id[:8]}... booked successfully")
        return self._success_result(tables=tables, messages=messages)
