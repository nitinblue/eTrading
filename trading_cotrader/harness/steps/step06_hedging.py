"""
Step 6: Hedge Calculator
========================

Calculate and display hedge recommendations.
"""

from decimal import Decimal
from harness.base import (
    TestStep, StepResult, rich_table, format_currency, format_greek,
    format_quantity
)


class HedgeCalculatorStep(TestStep):
    """Calculate and display hedge recommendations."""
    
    name = "Step 6: Hedge Calculator"
    description = "Calculate delta hedges for each underlying"
    
    def execute(self) -> StepResult:
        tables = []
        messages = []
        
        from services.hedging import HedgeCalculator
        
        registry = self.context.get('instrument_registry')
        buckets = self.context.get('risk_buckets')
        
        if not registry:
            return self._fail_result("No instrument registry - run step 4 first")
        
        if not buckets:
            messages.append("No risk buckets - using mock data")
            buckets = self._get_mock_buckets()
        
        calc = HedgeCalculator(registry)
        
        # Calculate hedges for each underlying
        hedge_data = []
        total_hedge_cost = Decimal(0)
        
        for underlying, bucket in sorted(buckets.items()):
            # Mock underlying prices (in production, from market data)
            price = self._get_mock_price(underlying)
            
            hedge = calc.calculate_delta_hedge(
                underlying_symbol=underlying,
                current_delta=bucket.delta,
                underlying_price=price
            )
            
            if hedge:
                cost = hedge.estimated_cost or Decimal(0)
                total_hedge_cost += abs(cost)
                
                hedge_data.append([
                    underlying,
                    format_greek(bucket.delta),
                    hedge.action,
                    abs(hedge.quantity),
                    hedge.hedge_type.value,
                    format_currency(price),
                    format_currency(cost),
                    format_greek(hedge.post_hedge_exposure),
                ])
            else:
                hedge_data.append([
                    underlying,
                    format_greek(bucket.delta),
                    "-",
                    "-",
                    "-",
                    format_currency(price),
                    "-",
                    "Already neutral",
                ])
        
        tables.append(rich_table(
            hedge_data,
            headers=["Underlying", "Current Δ", "Action", "Qty", "Type", 
                    "Price", "Cost", "Post-Hedge Δ"],
            title="🛡️ Hedge Recommendations"
        ))
        
        # Summary
        summary_data = [
            ["Total Hedge Cost", format_currency(total_hedge_cost), "Approximate"],
            ["Underlyings with Exposure", 
             sum(1 for row in hedge_data if row[2] != "-"), 
             f"of {len(hedge_data)}"],
        ]
        
        tables.append(rich_table(
            summary_data,
            headers=["Metric", "Value", "Note"],
            title="📊 Hedge Summary"
        ))
        
        # What-if scenarios
        scenario_data = []
        for underlying, bucket in sorted(buckets.items()):
            price = self._get_mock_price(underlying)
            
            # Calculate P&L for various moves
            for move_pct in [-5, -2, -1, 1, 2, 5]:
                move = price * Decimal(move_pct) / 100
                
                # Simplified P&L: delta * move + 0.5 * gamma * move^2
                delta_pnl = bucket.delta * move * 100  # *100 for contract multiplier
                gamma_pnl = Decimal("0.5") * bucket.gamma * (move ** 2) * 100
                total_pnl = delta_pnl + gamma_pnl
                
                scenario_data.append([
                    underlying,
                    f"{move_pct:+d}%",
                    format_currency(move),
                    format_currency(delta_pnl),
                    format_currency(gamma_pnl),
                    format_currency(total_pnl),
                    "🟢" if total_pnl > 0 else "🔴"
                ])
        
        if scenario_data:
            tables.append(rich_table(
                scenario_data[:18],  # Limit rows
                headers=["Underlying", "Move", "$ Move", "Delta P&L", 
                        "Gamma P&L", "Total P&L", ""],
                title="📈 What-If Scenarios (Spot Moves)"
            ))
        
        messages.append(f"Calculated hedges for {len(buckets)} underlyings")
        
        return self._success_result(tables=tables, messages=messages)
    
    def _get_mock_buckets(self):
        """Mock risk buckets for testing."""
        from services.hedging import RiskBucket
        
        return {
            "SPY": RiskBucket(
                underlying="SPY",
                delta=Decimal("-1.50"),
                gamma=Decimal("-0.075"),
                theta=Decimal("1.00"),
                vega=Decimal("-2.75"),
                position_count=5
            ),
            "MSFT": RiskBucket(
                underlying="MSFT",
                delta=Decimal("0.50"),
                gamma=Decimal("0.02"),
                theta=Decimal("-0.24"),
                vega=Decimal("0.80"),
                position_count=2
            ),
        }
    
    def _get_mock_price(self, underlying: str) -> Decimal:
        """Mock prices for testing."""
        prices = {
            "SPY": Decimal("588.25"),
            "MSFT": Decimal("425.50"),
            "AAPL": Decimal("185.00"),
            "QQQ": Decimal("510.00"),
            "IWM": Decimal("220.00"),
            "/GC": Decimal("2050.00"),
            "/ES": Decimal("5900.00"),
        }
        return prices.get(underlying, Decimal("100.00"))
