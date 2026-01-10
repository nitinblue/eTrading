from decimal import Decimal
from trading_bot.services.portfolio_builder import build_portfolio

from decimal import Decimal, InvalidOperation

def safe_decimal(value, default=0):
    """
    Convert a value (string, int, float) to Decimal.
    If conversion fails, returns default as Decimal.
    """
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)
    
def portfolio_dude(state: dict) -> dict:
    broker = state["broker"]
    config = state["config"]

    positions = broker.get_positions()
    portfolio = build_portfolio(positions)

    #net_liq = Decimal(str(broker.get_net_liquidation()))
    net_liq = Decimal("0")
    net_liq += safe_decimal(portfolio.get("defined_used", 0))
    net_liq += safe_decimal(portfolio.get("undefined_used", 0))

    defined_cap = net_liq * safe_decimal(config["risk"]["defined_capital_pct"])
    undefined_cap = net_liq * safe_decimal(config["risk"]["undefined_capital_pct"])

    state["trades"] = portfolio["trades"]

    state["defined_risk_used"] = portfolio["defined_used"]
    state["undefined_risk_used"] = portfolio["undefined_used"]

    state["defined_risk_available"] = max(
        Decimal("0"), defined_cap - portfolio["defined_used"]
    )
    state["undefined_risk_available"] = max(
        Decimal("0"), undefined_cap - portfolio["undefined_used"]
    )

    # Decide which bucket to work on
    if state["defined_risk_available"] > 0:
        state["active_risk_bucket"] = "defined"
        state["risk_remaining"] = state["defined_risk_available"]
    elif state["undefined_risk_available"] > 0:
        state["active_risk_bucket"] = "undefined"
        state["risk_remaining"] = state["undefined_risk_available"]
    else:
        state["active_risk_bucket"] = None
        state["risk_remaining"] = Decimal("0")

    return state
