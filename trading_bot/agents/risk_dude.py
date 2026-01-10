from decimal import Decimal

def risk_dude(state: dict) -> dict:
    trade = state.get("proposed_trade")

    state["risk_hard_stop"] = False
    state["needs_adjustment"] = False

    if not trade:
        return state

    bucket = state["active_risk_bucket"]
    remaining = state["risk_remaining"]

    # Defined risk
    if bucket == "defined":
        max_loss = trade["max_loss"]
        if max_loss > remaining:
            state["proposed_trade"] = None
        else:
            state["risk_remaining"] -= max_loss

    # Undefined risk
    else:
        margin = trade["margin_required"]
        if margin > remaining:
            state["proposed_trade"] = None
        else:
            state["risk_remaining"] -= margin

    return state
