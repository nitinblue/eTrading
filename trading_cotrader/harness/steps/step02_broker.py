"""
Step 2: Broker Connection
=========================

Connect to TastyTrade and fetch account info.
"""

from harness.base import (
    TestStep, StepResult, rich_table, format_currency, format_percent,
    success, warning
)


class BrokerConnectionStep(TestStep):
    """Connect to broker and display account information."""
    
    name = "Step 2: Broker Connection"
    description = "Connect to TastyTrade and retrieve account status"
    
    def execute(self) -> StepResult:
        tables = []
        messages = []
        
        # Check if we should skip
        if self.context.get('use_mock'):
            messages.append("Using mock mode - skipping broker connection")
            return self._success_result(messages=messages)
        
        if self.context.get('skip_sync'):
            messages.append("Skip sync mode - skipping broker connection")
            return self._success_result(messages=messages)
        
        # Import and connect
        from adapters.tastytrade_adapter import TastytradeAdapter
        from config.settings import get_settings
        
        settings = get_settings()
        
        broker = TastytradeAdapter(
            account_number=settings.tastytrade_account_number,
            is_paper=settings.is_paper_trading
        )
        
        if not broker.authenticate():
            return self._fail_result("Authentication failed")
        
        # Store in context for later steps
        self.context['broker'] = broker
        
        # Get account info
        account_info = broker.get_account_info() if hasattr(broker, 'get_account_info') else {}
        balances = broker.get_balances() if hasattr(broker, 'get_balances') else {}
        
        # Account summary table
        account_data = [
            ["Account ID", broker.account_id],
            ["Mode", "PAPER" if settings.is_paper_trading else "LIVE"],
            ["Status", "Connected ✓"],
        ]
        
        if balances:
            account_data.extend([
                ["Net Liquidating Value", format_currency(balances.get('net_liquidating_value'))],
                ["Cash Balance", format_currency(balances.get('cash_balance'))],
                ["Buying Power", format_currency(balances.get('buying_power'))],
                ["Maintenance Requirement", format_currency(balances.get('maintenance_requirement'))],
                ["Day Trading BP", format_currency(balances.get('day_trading_buying_power'))],
            ])
        
        tables.append(rich_table(
            account_data,
            headers=["Metric", "Value"],
            title="🏦 Account Summary"
        ))
        
        # If we have margin info, show it
        if balances:
            margin_used = balances.get('maintenance_requirement', 0)
            nlv = balances.get('net_liquidating_value', 1)
            if nlv and margin_used:
                margin_pct = (float(margin_used) / float(nlv)) * 100
                
                margin_data = [
                    ["Margin Used", format_currency(margin_used), f"{margin_pct:.1f}%", 
                     "🟢" if margin_pct < 50 else "🟡" if margin_pct < 75 else "🔴"],
                    ["Available", format_currency(float(nlv) - float(margin_used)), 
                     f"{100-margin_pct:.1f}%", ""],
                ]
                
                tables.append(rich_table(
                    margin_data,
                    headers=["Type", "Amount", "% of NLV", "Status"],
                    title="📊 Margin Status"
                ))
        
        messages.append(f"Connected to {broker.account_id}")
        
        return StepResult(
            step_name=self.name,
            passed=True,
            duration_ms=0,
            tables=tables,
            messages=messages
        )
