"""
Step 7: Risk Limits
===================

Check current portfolio against risk limits.
"""

from decimal import Decimal
from trading_cotrader.harness.base import (
    TestStep, StepResult, rich_table, format_currency, format_greek,
    format_percent
)


class RiskLimitsStep(TestStep):
    """Check portfolio against risk limits."""
    
    name = "Step 7: Risk Limits"
    description = "Validate portfolio against configured risk limits"
    
    def execute(self) -> StepResult:
        tables = []
        messages = []
        
        try:
            from services.risk_manager import RiskManager
        except ImportError:
            messages.append("RiskManager not available")
            return self._success_result(messages=messages)
        
        try:
            risk_manager = RiskManager()
        except Exception as e:
            messages.append(f"Could not load risk limits: {e}")
            return self._success_result(messages=messages)
        
        # Get limits
        limits = risk_manager.limits
        
        # Display configured limits
        limit_data = []
        
        # Portfolio limits
        if 'portfolio' in limits:
            port_limits = limits['portfolio']
            limit_data.append(["Portfolio", "Max Single Trade Risk", 
                              f"{port_limits.get('max_single_trade_risk_percent', '-')}%", ""])
            limit_data.append(["Portfolio", "Max Open Positions", 
                              port_limits.get('max_open_positions', '-'), ""])
            limit_data.append(["Portfolio", "Max Daily Loss", 
                              format_currency(Decimal(str(port_limits.get('max_daily_loss', 0)))), ""])
        
        # Greek limits
        if 'greeks' in limits:
            greek_limits = limits['greeks']
            limit_data.append(["Greeks", "Max Portfolio Delta", 
                              f"±{greek_limits.get('max_portfolio_delta', '-')}", ""])
            limit_data.append(["Greeks", "Max Portfolio Gamma", 
                              greek_limits.get('max_portfolio_gamma', '-'), ""])
            limit_data.append(["Greeks", "Min Portfolio Theta", 
                              greek_limits.get('min_portfolio_theta', '-'), ""])
            limit_data.append(["Greeks", "Max Portfolio Vega", 
                              greek_limits.get('max_portfolio_vega', '-'), ""])
        
        # Concentration limits
        if 'concentration' in limits:
            conc_limits = limits['concentration']
            limit_data.append(["Concentration", "Max Single Underlying", 
                              f"{conc_limits.get('max_single_underlying_percent', '-')}%", ""])
            limit_data.append(["Concentration", "Max Strategy Type", 
                              f"{conc_limits.get('max_strategy_type_percent', '-')}%", ""])
        
        tables.append(rich_table(
            limit_data,
            headers=["Category", "Limit", "Value", "Note"],
            title="⚙️ Configured Risk Limits"
        ))
        
        # Check current state against limits
        portfolio = self.context.get('portfolio')
        if portfolio and portfolio.portfolio_greeks:
            greeks = portfolio.portfolio_greeks
            greek_limits = limits.get('greeks', {})
            
            status_data = []
            
            # Delta check
            max_delta = greek_limits.get('max_portfolio_delta', 100)
            delta_pct = (abs(float(greeks.delta)) / max_delta) * 100
            delta_status = "🟢" if delta_pct < 70 else "🟡" if delta_pct < 90 else "🔴"
            status_data.append([
                "Delta", format_greek(greeks.delta), f"±{max_delta}", 
                f"{delta_pct:.0f}%", delta_status
            ])
            
            # Gamma check
            max_gamma = greek_limits.get('max_portfolio_gamma', 50)
            gamma_pct = (abs(float(greeks.gamma)) / max_gamma) * 100
            gamma_status = "🟢" if gamma_pct < 70 else "🟡" if gamma_pct < 90 else "🔴"
            status_data.append([
                "Gamma", format_greek(greeks.gamma, 4), f"{max_gamma}", 
                f"{gamma_pct:.0f}%", gamma_status
            ])
            
            # Theta check
            min_theta = greek_limits.get('min_portfolio_theta', -200)
            if greeks.theta >= min_theta:
                theta_status = "🟢"
                theta_pct = 0
            else:
                theta_pct = (float(min_theta - greeks.theta) / abs(min_theta)) * 100
                theta_status = "🟡" if theta_pct < 50 else "🔴"
            status_data.append([
                "Theta", format_greek(greeks.theta), f">{min_theta}", 
                f"{theta_pct:.0f}% over" if theta_pct > 0 else "OK", theta_status
            ])
            
            # Vega check  
            max_vega = greek_limits.get('max_portfolio_vega', 500)
            vega_pct = (abs(float(greeks.vega)) / max_vega) * 100
            vega_status = "🟢" if vega_pct < 70 else "🟡" if vega_pct < 90 else "🔴"
            status_data.append([
                "Vega", format_greek(greeks.vega), f"±{max_vega}", 
                f"{vega_pct:.0f}%", vega_status
            ])
            
            tables.append(rich_table(
                status_data,
                headers=["Greek", "Current", "Limit", "Usage", "Status"],
                title="📊 Current Risk Status"
            ))
        else:
            messages.append("No portfolio data for limit checking")
        
        # Show limit breaches if any
        buckets = self.context.get('risk_buckets', {})
        if buckets:
            conc_limits = limits.get('concentration', {})
            max_underlying = conc_limits.get('max_single_underlying_percent', 20)
            
            # Check concentration
            total_positions = sum(b.position_count for b in buckets.values())
            if total_positions > 0:
                conc_data = []
                for underlying, bucket in sorted(buckets.items(), 
                                                  key=lambda x: x[1].position_count, 
                                                  reverse=True):
                    pct = (bucket.position_count / total_positions) * 100
                    status = "🟢" if pct < max_underlying else "🔴"
                    conc_data.append([
                        underlying, bucket.position_count, f"{pct:.1f}%", status
                    ])
                
                tables.append(rich_table(
                    conc_data[:10],
                    headers=["Underlying", "Positions", "% of Total", "Status"],
                    title="📈 Concentration by Underlying"
                ))
        
        messages.append("Risk limits checked")
        return self._success_result(tables=tables, messages=messages)
