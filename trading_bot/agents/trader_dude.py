from decimal import Decimal

def trader_dude(state: dict) -> dict:
    """
    Finds ONE opportunity per invocation.
    """

    bucket = state.get("active_risk_bucket")

    if not bucket:
        state["proposed_trade"] = None
        return state

    # MOCKED trade – replace with real scanners
    if bucket == "defined":
        trade = {
            "strategy": "IRON_CONDOR",
            "symbol": "SPY",
            "max_loss": Decimal("500"),
            "defined_risk": True,
        }
    else:
        trade = {
            "strategy": "CASH_SECURED_PUT",
            "symbol": "AAPL",
            "margin_required": Decimal("3000"),
            "defined_risk": False,
        }

    state["proposed_trade"] = trade
    return state
