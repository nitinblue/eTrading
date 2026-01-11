def trade_defined_risk(state):
    
    # hardcoded for testing revisit later
    remaining = 1000.0 
    #remaining = state["defined_risk_limit"] - state["defined_risk_used"]

    if remaining <= 0:
        return state

    trade = {
        "strategy": "IRON_CONDOR",
        "symbol": "SPY",
        "max_loss": 1500,
        "prob_profit": 0.68
    }

    if trade["max_loss"] <= remaining:
        state["defined_risk_trades"].append(trade)
        state["defined_risk_used"] += trade["max_loss"]

    return state

def trade_undefined_risk(state):
    # hardcoded for testing revisit later
    remaining = 1000.0 
    #remaining = state["undefined_risk_limit"] - state["undefined_risk_used"]

    if remaining <= 0:
        return state

    trade = {
        "strategy": "CASH_SECURED_PUT",
        "symbol": "AAPL",
        "notional": 25_000,
        "delta": 0.20
    }

    if trade["notional"] <= remaining:
        state["undefined_risk_trades"].append(trade)
        state["undefined_risk_used"] += trade["notional"]

    return state
