# risk/engine.py
from trading_bot.risk.metrics import *
from trading_bot.risk.validators import *

def evaluate_portfolio(portfolio, configs):
    trades = portfolio.trades

    agg_risk = aggregate_risk(trades)
    delta = net_delta(trades)
    symbol_risk = risk_by_symbol(trades)

    violations = []
    violations += check_allocation(agg_risk, configs["portfolio"])
    violations += check_single_symbol(symbol_risk, configs["portfolio"])

    return {
        "agg_risk": agg_risk,
        "net_delta": delta,
        "violations": violations
    }
