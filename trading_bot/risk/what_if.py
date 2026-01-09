# risk/what_if.py
from copy import deepcopy
from risk.engine import evaluate_portfolio


def what_if_add_trade(portfolio, new_trade, configs):
    new_trades = portfolio.trades + [new_trade]
    simulated = portfolio.__class__(
        trades=new_trades,
        realized_pnl=portfolio.realized_pnl,
        unrealized_pnl=portfolio.unrealized_pnl
    )
    return evaluate_portfolio(simulated, configs)
