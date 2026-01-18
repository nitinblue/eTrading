def simulate_trade(trade, state):
    """
    Placeholder what-if simulation.
    """
    return {
        "expected_pnl": trade.prob_profit * trade.max_loss * 0.3,
        "worst_case": -trade.max_loss
    }
