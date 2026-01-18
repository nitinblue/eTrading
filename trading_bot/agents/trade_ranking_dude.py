def rank_trades(state: dict):

    all_trades = (
        state.get("defined_risk_trades", []) +
        state.get("undefined_risk_trades", [])
    )

    ranked = []

    for t in all_trades:
        prob = t.get("prob_profit", 0.5)
        risk = t.get("max_loss", t.get("notional", 1))
        reward = t.get("expected_profit", risk * 0.3)

        score = (prob * reward) / max(risk, 1)

        ranked.append({
            **t,
            "score": round(score, 4)
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked
