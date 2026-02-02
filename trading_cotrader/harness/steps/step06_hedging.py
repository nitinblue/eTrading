"""
Step 6: Hedge Calculator
========================

Hedges each risk factor independently, matching institutional_trading_v4.py:
- Delta hedge: Stock/Futures (lowest cost, no time decay)
- Gamma hedge: ATM options (highest gamma per contract)
- Vega hedge: Long-dated options (higher vega per unit)
- Theta hedge: Short options/iron condor (collect premium)
- Rho hedge: Long-dated options (higher rho sensitivity)

Each underlying's risk factors are hedged separately.
"""

from decimal import Decimal
from typing import Dict, List, Any
from trading_cotrader.harness.base import (
    TestStep, StepResult, rich_table, format_currency, format_greek,
)
from trading_cotrader.services.hedging.hedge_calculator import HedgeCalculator


class HedgeCalculatorStep(TestStep):
    """Calculate hedge recommendations for each risk factor."""
    
    name = "Step 6: Hedge Calculator"
    description = "Hedge each risk factor independently per underlying"
    
    def execute(self) -> StepResult:
        tables = []
        messages = []
        
        # Get risk matrix from Step 5
        matrix = self.context.get('risk_matrix')
        
        if not matrix:
            messages.append("No risk matrix - using mock data")
            matrix = self._get_mock_matrix()
        
        # Create hedge calculator
        calc = HedgeCalculator(
            risk_free_rate=0.05,
            default_vol=0.25,
            default_expiry=30/365
        )
        
        # Mock market data
        market_data = self._get_mock_market_data()
        
        # Get aggregated risk factors
        aggregated = matrix.get_aggregated_risk_factors()
        
        # =====================================================================
        # Delta Hedges - like hedge_delta() in institutional_trading_v4.py
        # =====================================================================
        delta_hedges = []
        for underlying, agg in sorted(aggregated.items()):
            if abs(agg.total_delta) > Decimal('10'):  # Threshold
                hedge_qty = -agg.total_delta  # Opposite sign to neutralize
                spot = market_data.get(underlying, Decimal('100'))
                cost = abs(hedge_qty) * spot
                
                action = "SELL" if hedge_qty < 0 else "BUY"
                
                delta_hedges.append([
                    underlying,
                    format_greek(agg.total_delta),
                    f"{action} {abs(hedge_qty):.0f}",
                    f"{underlying}_Stock",
                    format_currency(cost),
                    "Low cost, no time decay",
                ])
        
        if delta_hedges:
            tables.append(rich_table(
                delta_hedges,
                headers=["Underlying", "Current Δ", "Hedge", "Instrument", "Est. Cost", "Rationale"],
                title="🛡️ Delta Hedges (Stock/Futures)"
            ))
        
        # =====================================================================
        # Gamma Hedges - like hedge_gamma() in institutional_trading_v4.py
        # =====================================================================
        gamma_hedges = []
        for underlying, agg in sorted(aggregated.items()):
            if abs(agg.total_gamma) > Decimal('1'):  # Threshold
                spot = market_data.get(underlying, Decimal('100'))
                
                # ATM option gamma (approximate)
                atm_gamma = Decimal('0.02')  # Simplified
                hedge_qty = -agg.total_gamma / atm_gamma if atm_gamma != 0 else Decimal('0')
                
                action = "SELL" if hedge_qty < 0 else "BUY"
                
                gamma_hedges.append([
                    underlying,
                    format_greek(agg.total_gamma, 4),
                    f"{action} {abs(hedge_qty):.1f}",
                    f"{underlying}_ATM_Call",
                    "~" + format_currency(abs(hedge_qty) * spot * Decimal('0.02')),
                    "Highest gamma per contract",
                ])
        
        if gamma_hedges:
            tables.append(rich_table(
                gamma_hedges,
                headers=["Underlying", "Current Γ", "Hedge", "Instrument", "Est. Cost", "Rationale"],
                title="🛡️ Gamma Hedges (ATM Options)"
            ))
        
        # =====================================================================
        # Vega Hedges - like hedge_vega() in institutional_trading_v4.py
        # =====================================================================
        vega_hedges = []
        for underlying, agg in sorted(aggregated.items()):
            if abs(agg.total_vega) > Decimal('50'):  # Threshold
                spot = market_data.get(underlying, Decimal('100'))
                
                # Long-dated option vega (approximate)
                long_vega = Decimal('0.30')  # Higher for longer dated
                hedge_qty = -agg.total_vega / long_vega if long_vega != 0 else Decimal('0')
                
                action = "SELL" if hedge_qty < 0 else "BUY"
                
                vega_hedges.append([
                    underlying,
                    format_greek(agg.total_vega),
                    f"{action} {abs(hedge_qty):.1f}",
                    f"{underlying}_LongDated_Put",
                    "~" + format_currency(abs(hedge_qty) * spot * Decimal('0.03')),
                    "Higher vega per unit, lower theta bleed",
                ])
        
        if vega_hedges:
            tables.append(rich_table(
                vega_hedges,
                headers=["Underlying", "Current V", "Hedge", "Instrument", "Est. Cost", "Rationale"],
                title="🛡️ Vega Hedges (Long-Dated Options)"
            ))
        
        # =====================================================================
        # Theta Summary - theta is typically earned, not hedged directly
        # =====================================================================
        total_theta = matrix.get_total_theta()
        theta_status = "🟢 Collecting" if total_theta > 0 else "🔴 Paying"
        
        theta_data = [[
            "Portfolio",
            format_greek(total_theta),
            f"${float(total_theta):,.2f}/day",
            theta_status,
            "Theta typically managed via position sizing, not hedged directly"
        ]]
        
        tables.append(rich_table(
            theta_data,
            headers=["Scope", "Theta", "Daily $", "Status", "Note"],
            title="⏱️ Theta Summary"
        ))
        
        # =====================================================================
        # Hedge Summary
        # =====================================================================
        total_hedges = len(delta_hedges) + len(gamma_hedges) + len(vega_hedges)
        
        summary_data = [
            ["Delta Hedges", len(delta_hedges), "Stock/Futures - neutralize directional risk"],
            ["Gamma Hedges", len(gamma_hedges), "ATM Options - stabilize delta changes"],
            ["Vega Hedges", len(vega_hedges), "Long-dated Options - manage vol exposure"],
            ["Total Hedges", total_hedges, "Independent hedges per risk factor"],
        ]
        
        tables.append(rich_table(
            summary_data,
            headers=["Type", "Count", "Description"],
            title="📊 Hedge Summary"
        ))
        
        # =====================================================================
        # What-If Scenarios
        # =====================================================================
        scenario_data = []
        for underlying, agg in sorted(aggregated.items()):
            spot = market_data.get(underlying, Decimal('100'))
            
            for move_pct in [-5, -2, 2, 5]:
                move = spot * Decimal(str(move_pct)) / 100
                
                # P&L = Delta × Move + 0.5 × Gamma × Move²
                delta_pnl = agg.total_delta * move
                gamma_pnl = Decimal("0.5") * agg.total_gamma * (move ** 2)
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
                scenario_data[:16],
                headers=["Underlying", "Move", "$ Move", "Δ P&L", "Γ P&L", "Total P&L", ""],
                title="📈 What-If Scenarios"
            ))
        
        messages.append(f"Calculated {total_hedges} hedges for {len(aggregated)} underlyings")
        
        # Store for next steps
        self.context['hedge_summary'] = {
            'delta_hedges': len(delta_hedges),
            'gamma_hedges': len(gamma_hedges),
            'vega_hedges': len(vega_hedges),
            'total_theta': float(total_theta),
        }
        
        return self._success_result(tables=tables, messages=messages)
    
    def _get_mock_matrix(self):
        """Create mock risk matrix for testing."""
        from trading_cotrader.services.risk_factors.models import RiskFactorMatrix
        
        matrix = RiskFactorMatrix()
        
        # MSFT position
        matrix.add_instrument(
            streamer_symbol="MSFT_Call_400",
            position_quantity=100,
            multiplier=100,
            underlying="MSFT",
            delta=Decimal("0.65"),
            gamma=Decimal("0.015"),
            theta=Decimal("-0.45"),
            vega=Decimal("0.25"),
        )
        
        # SPY position  
        matrix.add_instrument(
            streamer_symbol="SPY_Put_580",
            position_quantity=-5,
            multiplier=100,
            underlying="SPY",
            delta=Decimal("-0.30"),
            gamma=Decimal("0.015"),
            theta=Decimal("0.20"),
            vega=Decimal("-0.55"),
        )
        
        return matrix
    
    def _get_mock_market_data(self) -> Dict[str, Decimal]:
        """Mock spot prices."""
        return {
            "MSFT": Decimal("425.50"),
            "SPY": Decimal("588.25"),
            "QQQ": Decimal("510.00"),
            "AAPL": Decimal("185.00"),
            "GLD": Decimal("185.00"),
            "SLV": Decimal("22.50"),
            "IWM": Decimal("220.00"),
        }
