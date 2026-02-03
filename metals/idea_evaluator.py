def evaluate_trade(trade, market_state):
    reasons = []

    for leg in trade.legs:
        if leg.iv and leg.iv > 0.6 and trade.strategy in ["LEAPS", "CALENDAR"]:
            reasons.append("IV too high for long premium")

        if trade.strategy == "LEAPS" and leg.delta and leg.delta < 0.6:
            reasons.append("Delta too low for core exposure")

    if market_state.rsi > 60 and trade.strategy == "LEAPS":
        reasons.append("Underlying extended")

    if market_state.dxy_trend == "up":
        reasons.append("Dollar headwind")

    if reasons:
        trade.verdict = "WAIT"
        trade.why = reasons
    else:
        trade.verdict = "APPROVED"
        trade.why = ["Conditions favorable"]

    return trade
