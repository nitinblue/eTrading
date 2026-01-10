from trading_bot.domain.portfolio import PortfolioState
from trading_bot.adapters.tastytrade_adapter import tasty_position_to_trade
from collections import defaultdict


def build_portfolio(tasty_positions, realized_pnl=0.0, unrealized_pnl=0.0):
    trades = [
        tasty_position_to_trade(pos)
        for pos in tasty_positions
        #if pos.is_open
    ]
    return trades