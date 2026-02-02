"""
Step 5: Risk Aggregation
========================

Aggregate risk by underlying using the new RiskBucket model.
This is the key view for a trader.
"""

from decimal import Decimal
from harness.base import (
    TestStep, StepResult, rich_table, format_currency, format_greek,
    format_percent
)
from services.hedging import HedgeCalculator #RiskBucket
from services.market_data import Greeks

class RiskAggregationStep(TestStep):
    """Aggregate and display risk by underlying."""
    
    name = "Step 5: Risk Aggregation"
    description = "Aggregate Greeks by underlying - the trader's primary view"
    
    def execute(self) -> StepResult:
        tables = []
        messages = []
        
        registry = self.context.get('instrument_registry')
        if not registry:
            return self._fail_result("No instrument registry - run step 4 first")
        
        calc = HedgeCalculator(registry)
        
        # Build positions with Greeks
        # In real usage, Greeks come from DXLink; here we mock them
        positions_with_greeks = self._build_positions_with_greeks(registry)
        
        if not positions_with_greeks:
            messages.append("No option positions found - using mock data")
            positions_with_greeks = self._get_mock_positions_with_greeks()
        
        # Aggregate by underlying
        buckets = calc.aggregate_risk_by_underlying(positions_with_greeks)
        self.context['risk_buckets'] = buckets
        
        messages.append(f"Aggregated {len(buckets)} underlyings")
        
        # Main risk view - THE trader's view
        risk_data = []
        portfolio_delta = Decimal(0)
        portfolio_gamma = Decimal(0)
        portfolio_theta = Decimal(0)
        portfolio_vega = Decimal(0)
        
        for underlying in sorted(buckets.keys()):
            bucket = buckets[underlying]
            
            # Accumulate portfolio totals
            portfolio_delta += bucket.delta
            portfolio_gamma += bucket.gamma
            portfolio_theta += bucket.theta
            portfolio_vega += bucket.vega
            
            # Direction indicator
            if bucket.delta > Decimal("0.5"):
                direction = "🟢 Long"
            elif bucket.delta < Decimal("-0.5"):
                direction = "🔴 Short"
            else:
                direction = "⚪ Neutral"
            
            # Theta quality
            theta_indicator = "🟢" if bucket.theta > 0 else "🔴" if bucket.theta < -10 else "🟡"
            
            risk_data.append([
                underlying,
                bucket.position_count,
                format_greek(bucket.delta),
                direction,
                format_greek(bucket.gamma, 4),
                f"{theta_indicator} {format_greek(bucket.theta)}",
                format_greek(bucket.vega),
            ])
        
        tables.append(rich_table(
            risk_data,
            headers=["Underlying", "Pos", "Delta", "Direction", "Gamma", "Theta", "Vega"],
            title="⚡ Risk by Underlying (Primary Trading View)"
        ))
        
        # Portfolio totals
        portfolio_direction = "🟢 Net Long" if portfolio_delta > 0 else "🔴 Net Short" if portfolio_delta < 0 else "⚪ Neutral"
        
        totals_data = [
            ["Portfolio Delta", format_greek(portfolio_delta), portfolio_direction],
            ["Portfolio Gamma", format_greek(portfolio_gamma, 4), 
             "Positive = gains accelerate" if portfolio_gamma > 0 else "Negative = losses accelerate"],
            ["Portfolio Theta", format_greek(portfolio_theta), 
             f"${float(portfolio_theta):,.0f}/day decay"],
            ["Portfolio Vega", format_greek(portfolio_vega),
             "Long vol" if portfolio_vega > 0 else "Short vol"],
        ]
        
        tables.append(rich_table(
            totals_data,
            headers=["Greek", "Value", "Interpretation"],
            title="💼 Portfolio Risk Summary"
        ))
        
        # Delta by expiry (term structure)
        expiry_data = []
        all_expiries = set()
        for bucket in buckets.values():
            all_expiries.update(bucket.delta_by_expiry.keys())
        
        if all_expiries:
            for expiry in sorted(all_expiries)[:8]:  # Limit to 8 expiries
                expiry_delta = sum(
                    bucket.delta_by_expiry.get(expiry, Decimal(0)) 
                    for bucket in buckets.values()
                )
                expiry_theta = sum(
                    bucket.theta_by_expiry.get(expiry, Decimal(0))
                    for bucket in buckets.values()
                )
                
                expiry_data.append([
                    expiry[:10],
                    format_greek(expiry_delta),
                    format_greek(expiry_theta),
                ])
            
            if expiry_data:
                tables.append(rich_table(
                    expiry_data,
                    headers=["Expiry", "Delta", "Theta"],
                    title="📅 Risk by Expiration (Term Structure)"
                ))
        
        return self._success_result(tables=tables, messages=messages)
    
    def _build_positions_with_greeks(self, registry) -> list:
        """Build positions with Greeks from registry instruments."""
        from services.market_data import Greeks
        
        positions = []
        for inst in registry.get_all():
            if inst.is_option():
                # In production, Greeks come from DXLink
                # Here we simulate based on option type
                delta = Decimal("-0.30") if inst.option_type.value == "PUT" else Decimal("0.40")
                
                positions.append({
                    "instrument_id": inst.instrument_id,
                    "quantity": -2,  # Assume short for testing
                    "greeks": Greeks(
                        delta=delta,
                        gamma=Decimal("0.02"),
                        theta=Decimal("0.15"),  # Positive for short options
                        vega=Decimal("-0.50")   # Negative for short options
                    )
                })
        
        return positions
    
    def _get_mock_positions_with_greeks(self) -> list:
        """Mock positions for testing."""
        from services.market_data import Greeks
        
        return [
            {
                "instrument_id": "SPY   260331P00580000",
                "quantity": -5,
                "greeks": Greeks(
                    delta=Decimal("-0.30"),
                    gamma=Decimal("0.015"),
                    theta=Decimal("0.20"),
                    vega=Decimal("-0.55")
                )
            },
            {
                "instrument_id": "MSFT  260331P00400000",
                "quantity": -2,
                "greeks": Greeks(
                    delta=Decimal("-0.25"),
                    gamma=Decimal("0.01"),
                    theta=Decimal("0.12"),
                    vega=Decimal("-0.40")
                )
            },
            {
                "instrument_id": "QQQ   260228C00500000",
                "quantity": 3,
                "greeks": Greeks(
                    delta=Decimal("0.45"),
                    gamma=Decimal("0.02"),
                    theta=Decimal("-0.18"),
                    vega=Decimal("0.60")
                )
            },
        ]
