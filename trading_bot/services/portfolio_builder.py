from domain.portfolio import PortfolioState
from adapters.tastytrade_adapter import tasty_position_to_trade

def build_portfolio(tasty_positions, realized_pnl=0.0, unrealized_pnl=0.0):
    trades = [
        tasty_position_to_trade(pos)
        for pos in tasty_positions
        if pos.is_open
    ]

    return PortfolioState(
        trades=trades,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl
    )
