"""
Step 5: Risk Aggregation (2D Matrix)
====================================

Displays the risk matrix matching institutional_trading_v4.py:
- Y-axis: Instruments (keyed by streamer_symbol)
- X-axis: Greeks per underlying (Delta_MSFT, Gamma_MSFT, etc.)

Then aggregates to show total exposure per risk factor.
"""

from decimal import Decimal
from typing import Dict, List, Any
from trading_cotrader.harness.base import (
    TestStep, StepResult, rich_table, format_currency, format_greek,
)


class RiskAggregationStep(TestStep):
    """Display 2D risk matrix and aggregated risk factors."""
    
    name = "Step 5: Risk Aggregation"
    description = "2D Risk Matrix: Instruments × Greeks by Underlying"
    
    def execute(self) -> StepResult:
        tables = []
        messages = []
        
        # Build the risk matrix from positions
        matrix = self._build_risk_matrix()
        
        # Store for subsequent steps
        self.context['risk_matrix'] = matrix
        
        messages.append(f"Built matrix: {len(matrix.instruments)} instruments × {len(matrix.get_underlyings())} underlyings")
        
        # =====================================================================
        # Table 1: Raw Risk Matrix (like portfolio_risks_df in institutional_trading)
        # =====================================================================
        matrix_rows = matrix.to_dataframe_rows()
        
        if matrix_rows:
            # Get all column headers dynamically
            all_keys = set()
            for row in matrix_rows:
                all_keys.update(row.keys())
            
            # Order columns: Instrument, Position, then Greeks sorted
            base_cols = ['Instrument', 'Position']
            greek_cols = sorted([k for k in all_keys if k not in base_cols])
            headers = base_cols + greek_cols
            
            # Build table data
            table_data = []
            for row in matrix_rows:
                table_row = []
                for col in headers:
                    val = row.get(col, '')
                    if isinstance(val, float):
                        if 'Gamma' in col:
                            table_row.append(f"{val:.4f}")
                        else:
                            table_row.append(f"{val:.2f}")
                    else:
                        table_row.append(str(val))
                table_data.append(table_row)
            
            tables.append(rich_table(
                table_data,
                headers=headers,
                title="📊 Risk Matrix (Instruments × Greeks by Underlying)"
            ))
        
        # =====================================================================
        # Table 2: Aggregated Risk Factors (like aggregated_df in institutional_trading)
        # =====================================================================
        aggregated = matrix.get_aggregated_risk_factors()
        
        agg_data = []
        for underlying in sorted(aggregated.keys()):
            agg = aggregated[underlying]
            
            # Direction indicator for delta
            if agg.total_delta > Decimal("50"):
                direction = "🟢 Long"
            elif agg.total_delta < Decimal("-50"):
                direction = "🔴 Short"
            else:
                direction = "⚪ Neutral"
            
            agg_data.append([
                underlying,
                format_greek(agg.total_delta),
                direction,
                format_greek(agg.total_gamma, 4),
                format_greek(agg.total_vega),
                format_greek(agg.total_rho),
                agg.instrument_count,
            ])
        
        if agg_data:
            tables.append(rich_table(
                agg_data,
                headers=["Underlying", "Σ Delta", "Direction", "Σ Gamma", "Σ Vega", "Σ Rho", "# Inst"],
                title="⚡ Aggregated Risk Factors by Underlying"
            ))
        
        # =====================================================================
        # Table 3: Portfolio Totals
        # =====================================================================
        totals = matrix.get_portfolio_totals()
        total_theta = matrix.get_total_theta()
        
        portfolio_direction = "🟢 Net Long" if totals['delta'] > 0 else "🔴 Net Short" if totals['delta'] < 0 else "⚪ Neutral"
        
        totals_data = [
            ["Total Delta", format_greek(totals['delta']), portfolio_direction],
            ["Total Gamma", format_greek(totals['gamma'], 4), 
             "Positive = gains accelerate" if totals['gamma'] > 0 else "Negative = losses accelerate"],
            ["Total Theta", format_greek(total_theta), 
             f"${float(total_theta):,.0f}/day"],
            ["Total Vega", format_greek(totals['vega']),
             "Long vol" if totals['vega'] > 0 else "Short vol"],
            ["Total Rho", format_greek(totals['rho']),
             "Rate sensitive" if abs(totals['rho']) > 10 else "Low rate sensitivity"],
        ]
        
        tables.append(rich_table(
            totals_data,
            headers=["Risk Factor", "Value", "Interpretation"],
            title="💼 Portfolio Risk Summary"
        ))
        
        # =====================================================================
        # Table 4: Factors Needing Hedge
        # =====================================================================
        needs_hedge = matrix.get_factors_needing_hedge(
            delta_threshold=Decimal('50'),
            gamma_threshold=Decimal('5'),
            vega_threshold=Decimal('200'),
        )
        
        if needs_hedge:
            hedge_alert_data = []
            for agg in needs_hedge:
                alerts = []
                if abs(agg.total_delta) > 50:
                    alerts.append(f"Δ={format_greek(agg.total_delta)}")
                if abs(agg.total_gamma) > 5:
                    alerts.append(f"Γ={format_greek(agg.total_gamma, 4)}")
                if abs(agg.total_vega) > 200:
                    alerts.append(f"V={format_greek(agg.total_vega)}")
                
                hedge_alert_data.append([
                    agg.underlying,
                    ", ".join(alerts),
                    "⚠️ HEDGE NEEDED",
                ])
            
            tables.append(rich_table(
                hedge_alert_data,
                headers=["Underlying", "Exceeded Thresholds", "Status"],
                title="🚨 Risk Factors Exceeding Thresholds"
            ))
        else:
            messages.append("✓ All risk factors within thresholds")
        
        return self._success_result(tables=tables, messages=messages)
    
    def _build_risk_matrix(self):
        """Build risk matrix from registry or mock data."""
        from trading_cotrader.services.risk_factors.models import RiskFactorMatrix, InstrumentRiskRow
        
        matrix = RiskFactorMatrix()
        
        registry = self.context.get('instrument_registry')
        
        if registry:
            # Build from actual registry
            for inst in registry.get_all():
                if inst.is_option():
                    # Get underlying
                    underlying = inst.underlying_symbol or inst.ticker
                    
                    # Mock Greeks (in production, from DXLink)
                    delta = Decimal("-0.30") if inst.option_type and inst.option_type.value == "PUT" else Decimal("0.40")
                    
                    matrix.add_instrument(
                        streamer_symbol=inst.instrument_id,
                        description=f"{underlying} option",
                        position_quantity=-2,  # Assume short
                        multiplier=inst.multiplier or 100,
                        underlying=underlying,
                        delta=delta,
                        gamma=Decimal("0.02"),
                        theta=Decimal("0.15"),
                        vega=Decimal("-0.50"),
                    )
        else:
            # Use mock data matching institutional_trading_v4.py style
            matrix = self._get_mock_matrix()
        
        if len(matrix.instruments) == 0:
            matrix = self._get_mock_matrix()
        
        return matrix
    
    def _get_mock_matrix(self):
        """Create mock risk matrix for testing."""
        from trading_cotrader.services.risk_factors.models import RiskFactorMatrix
        
        matrix = RiskFactorMatrix()
        
        # MSFT Call - like institutional_trading_v4.py
        matrix.add_instrument(
            streamer_symbol="MSFT  260321C00400000",
            description="MSFT Mar21 400 Call",
            position_quantity=100,
            multiplier=100,
            underlying="MSFT",
            delta=Decimal("0.6548"),
            gamma=Decimal("0.0146"),
            theta=Decimal("-0.4444"),
            vega=Decimal("0.2534"),
            rho=Decimal("0.1028"),
        )
        
        # SPY Put - short position
        matrix.add_instrument(
            streamer_symbol="SPY   260321P00580000",
            description="SPY Mar21 580 Put",
            position_quantity=-5,
            multiplier=100,
            underlying="SPY",
            delta=Decimal("-0.30"),
            gamma=Decimal("0.015"),
            theta=Decimal("0.20"),
            vega=Decimal("-0.55"),
            rho=Decimal("-0.08"),
        )
        
        # QQQ Call - long position
        matrix.add_instrument(
            streamer_symbol="QQQ   260228C00500000",
            description="QQQ Feb28 500 Call",
            position_quantity=3,
            multiplier=100,
            underlying="QQQ",
            delta=Decimal("0.45"),
            gamma=Decimal("0.02"),
            theta=Decimal("-0.18"),
            vega=Decimal("0.60"),
            rho=Decimal("0.12"),
        )
        
        # Gold/Silver spread example - exposes to TWO underlyings
        row = matrix.add_instrument(
            streamer_symbol="GLD_SLV_SPREAD",
            description="Gold/Silver Spread",
            position_quantity=10,
            multiplier=1,
            underlying="GLD",  # First underlying
            delta=Decimal("1.0"),
            gamma=Decimal("0"),
            theta=Decimal("0"),
            vega=Decimal("0"),
        )
        # Add second underlying exposure to same instrument
        row.add_sensitivity(
            underlying="SLV",
            delta=Decimal("-1.0"),  # Short silver
            gamma=Decimal("0"),
            theta=Decimal("0"),
            vega=Decimal("0"),
        )
        matrix._underlyings.add("SLV")
        
        return matrix
