def route_after_portfolio(state):
    if state["defined_risk_used"] < state["defined_risk_limit"]:
        return "defined"
    if state["undefined_risk_used"] < state["undefined_risk_limit"]:
        return "undefined"
    return "end"
