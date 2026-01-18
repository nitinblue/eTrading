def suggest_adjustments(state, simulation):
    """
    Rule-based rolling & adjustment engine
    """

    adjustments = []

    for entry in simulation:
        trade = entry["trade"]

        # ---- Defined Risk Adjustments ----
        if trade["strategy"] == "IRON_CONDOR":
            if trade.get("prob_profit", 1) < 0.55:
                adjustments.append({
                    "action": "ROLL",
                    "strategy": "IRON_CONDOR",
                    "symbol": trade["symbol"],
                    "reason": "Probability deteriorated",
                    "suggestion": "Roll untested side"
                })

        # ---- Undefined Risk Adjustments ----
        if trade["strategy"] == "CASH_SECURED_PUT":
            if trade.get("delta", 0.0) > 0.30:
                adjustments.append({
                    "action": "ROLL_DOWN_AND_OUT",
                    "strategy": "CSP",
                    "symbol": trade["symbol"],
                    "reason": "Delta too high",
                    "suggestion": "Extend duration, reduce delta"
                })

    return adjustments
