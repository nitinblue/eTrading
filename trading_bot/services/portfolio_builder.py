from decimal import Decimal

def build_portfolio(positions):
    trades = []
    defined_used = Decimal("0")
    undefined_used = Decimal("0")

    for pos in positions:
        # BE DEFENSIVE
        try:
            trade = pos  # or adapter
            trades.append(trade)

            if getattr(trade, "defined_risk", False):
                defined_used += trade.max_loss
            else:
                undefined_used += getattr(trade, "margin_requirement", Decimal("0"))

        except Exception:
            continue

    return {
        "trades": trades,
        "defined_used": defined_used,
        "undefined_used": undefined_used,
    }
