# tests/unit/test_portfolio.py
from trading_bot.positions import PositionsManager
from trading_bot.risk import RiskManager
from trading_bot.portfolio import Portfolio

def test_portfolio_net_greeks(mock_broker):
    positions_mgr = PositionsManager(mock_broker)
    risk_mgr = RiskManager({'max_portfolio_risk': 0.05})
    portfolio = Portfolio(positions_mgr, risk_mgr)

    portfolio.update()

    net_greeks = portfolio.get_net_greeks()
    assert 'delta' in net_greeks