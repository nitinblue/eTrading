from trading_bot.adapters.tastytrade_adapter import tasty_position_to_trade
from decimal import Decimal

def build_portfolio(tasty_positions):
    trades = [
        tasty_position_to_trade(pos)
        for pos in tasty_positions
    ]

    defined_used = Decimal("0")
    undefined_used = Decimal("0")

    for t in trades:
        if t.defined_risk:
            defined_used += t.max_loss
        else:
            undefined_used += t.margin_requirement

    return {
        "trades": trades,
        "defined_used": defined_used,
        "undefined_used": undefined_used,
    }
