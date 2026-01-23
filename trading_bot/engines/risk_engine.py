def validate_trade(trade, available_risk):
    """
    Deterministic risk validation.
    """
    if trade.max_loss > available_risk:
        return False, "Insufficient risk capacity"

    return True, "OK"
