# test_risk.py
from trading_cotrader.services.risk_manager import RiskManager
import trading_cotrader.core.models.domain as dm
from decimal import Decimal

# Initialize
risk_mgr = RiskManager("risk_limits.yaml")

# Create a mock trade (big delta)
trade = dm.Trade(
    underlying_symbol="SPY",
    legs=[
        dm.Leg(
            symbol=dm.Symbol(ticker="SPY", asset_type=dm.AssetType.EQUITY),
            quantity=100,  # 100 shares = 100 delta!
            greeks=dm.Greeks(delta=Decimal('100'))
        )
    ]
)

# Create mock portfolio
portfolio = dm.Portfolio(
    total_equity=Decimal('100000'),
    portfolio_greeks=dm.Greeks(delta=Decimal('150'))  # Already at 150
)

# Validate
result = risk_mgr.validate_trade(trade, portfolio, [], [])

print(result.summary())