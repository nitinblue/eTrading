def simulate_portfolio(state, ranked_trades):
    """
    Simulates portfolio impact if top trades are placed
    """

    net_liq = state["net_liquidation"]
    bp = state["buying_power"]

    used_defined = state["defined_risk_used"]
    used_undefined = state["undefined_risk_used"]
    simulation_log = []

    for trade in ranked_trades:
        if trade["strategy"] in ["IRON_CONDOR", "VERTICAL"]:
            used_defined += trade["max_loss"]
            net_liq -= trade["max_loss"]

        else:
            used_undefined += trade.get("notional", 0)
            bp -= trade.get("notional", 0)

        simulation_log.append({
            "trade": trade,
            "net_liq_after": net_liq,
            "bp_after": bp,
            "defined_risk_used": used_defined,
            "undefined_risk_used": used_undefined
        })

    return simulation_log
