"""
Step 13: Strategy Template Booking
===================================

Books a WhatIf trade for each testable strategy template using live DXLink
Greeks/quotes and near-ATM SPY strikes.

Tests 12 pure-option strategies (excludes covered call, protective put, collar
which require equity legs, calendar/diagonal which need two expirations, and custom).

Requires broker connection (skipped without one).
"""

from typing import Dict, Any, List, Tuple

from trading_cotrader.harness.base import TestStep, StepResult, rich_table


# Strategy definitions: (strategy_name, [(streamer_symbol, quantity), ...])
# Using SPY March 20, 2026 expiration, near-ATM strikes around 600
_STRATEGY_LEGS: List[Tuple[str, List[Tuple[str, int]]]] = [
    ("single", [
        (".SPY260320P600", -1),
    ]),
    ("vertical_spread", [
        (".SPY260320P600", -1),
        (".SPY260320P590", 1),
    ]),
    ("iron_condor", [
        (".SPY260320P580", 1),
        (".SPY260320P590", -1),
        (".SPY260320C610", -1),
        (".SPY260320C620", 1),
    ]),
    ("iron_butterfly", [
        (".SPY260320P590", 1),
        (".SPY260320P600", -1),
        (".SPY260320C600", -1),
        (".SPY260320C610", 1),
    ]),
    ("straddle", [
        (".SPY260320P600", -1),
        (".SPY260320C600", -1),
    ]),
    ("strangle", [
        (".SPY260320P590", -1),
        (".SPY260320C610", -1),
    ]),
    ("butterfly", [
        (".SPY260320P590", 1),
        (".SPY260320P600", -2),
        (".SPY260320P610", 1),
    ]),
    ("condor", [
        (".SPY260320P580", 1),
        (".SPY260320P590", -1),
        (".SPY260320P610", -1),
        (".SPY260320P620", 1),
    ]),
    ("jade_lizard", [
        (".SPY260320P590", -1),
        (".SPY260320C610", -1),
        (".SPY260320C620", 1),
    ]),
    ("big_lizard", [
        (".SPY260320P600", -1),
        (".SPY260320C600", -1),
        (".SPY260320C620", 1),
    ]),
    ("ratio_spread", [
        (".SPY260320P600", 1),
        (".SPY260320P590", -2),
    ]),
    ("calendar_spread", [
        (".SPY260320P600", -1),
        (".SPY260417P600", 1),
    ]),
]


class StrategyTemplateStep(TestStep):
    name = "Strategy Template Booking"
    description = "Book WhatIf trades for all 12 testable strategy templates with live Greeks"

    def execute(self) -> StepResult:
        from trading_cotrader.services.trade_booking_service import (
            TradeBookingService, LegInput
        )
        from trading_cotrader.core.models.strategy_templates import (
            get_all_templates, get_template, get_strategy_type_from_string
        )

        tables = []
        messages = []

        # Check broker
        broker = self.context.get('broker')
        if not broker:
            return self._fail_result(
                "No broker in context - step requires broker connection (run without --mock)"
            )

        # Template validation table (static, no broker needed)
        all_templates = get_all_templates()
        template_data = []
        for st, tmpl in sorted(all_templates.items(), key=lambda x: x[1].name):
            template_data.append([
                tmpl.name,
                tmpl.risk_category.value,
                tmpl.directional_bias.value,
                "+" if tmpl.is_theta_positive else "-",
                "-" if tmpl.is_vega_negative else "+",
                str(tmpl.leg_count),
            ])
        tables.append(rich_table(
            template_data,
            headers=["Strategy", "Risk", "Bias", "Theta", "Vega", "Legs"],
            title="Strategy Templates (all 18)"
        ))

        # Book each strategy
        container_manager = self.context.get('container_manager')
        service = TradeBookingService(
            broker=broker,
            container_manager=container_manager,
        )

        summary_data = []
        pass_count = 0
        fail_count = 0

        for strategy_name, leg_defs in _STRATEGY_LEGS:
            messages.append(f"Booking: {strategy_name} ({len(leg_defs)} legs)")

            leg_inputs = [
                LegInput(streamer_symbol=sym, quantity=qty)
                for sym, qty in leg_defs
            ]

            result = service.book_whatif_trade(
                underlying="SPY",
                strategy_type=strategy_name,
                legs=leg_inputs,
                notes=f"Harness step 13: {strategy_name}",
                rationale=f"Strategy template validation: {strategy_name}",
                confidence=5,
            )

            if result.success:
                pass_count += 1
                delta = result.total_greeks.get('delta', 0)
                theta = result.total_greeks.get('theta', 0)
                summary_data.append([
                    strategy_name,
                    "PASS",
                    f"${result.entry_price:.2f}",
                    f"{delta:.2f}",
                    f"{theta:.2f}",
                    result.trade_id[:8] + "...",
                ])
            else:
                fail_count += 1
                summary_data.append([
                    strategy_name,
                    "FAIL",
                    "-",
                    "-",
                    "-",
                    result.error[:30] if result.error else "unknown",
                ])

        tables.append(rich_table(
            summary_data,
            headers=["Strategy", "Status", "Entry$", "Delta", "Theta", "Trade ID"],
            title="Strategy Booking Results (12 strategies)"
        ))

        messages.append(f"Passed: {pass_count}/{len(_STRATEGY_LEGS)}, "
                        f"Failed: {fail_count}/{len(_STRATEGY_LEGS)}")

        if fail_count > 0:
            return self._fail_result(
                f"{fail_count} strategy bookings failed",
                tables=tables,
            )

        return self._success_result(tables=tables, messages=messages)
