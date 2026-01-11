def rank_trades(trades):
    """
    Simple deterministic ranking.
    """
    for t in trades:
        t.metadata["score"] = t.prob_profit / max(t.max_loss, 1)

    return sorted(
        trades,
        key=lambda t: t.metadata["score"],
        reverse=True
    )
