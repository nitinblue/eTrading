def portfolio_dude(state):
    broker = state.broker
    cfg = state.config

    # --------------------------------------------------
    # Pull real values if available, else mock
    # --------------------------------------------------
    try:
        acct = next(iter(broker.accounts.values()))
        state.net_liquidation = float(acct.net_liquidation)
        state.buying_power = float(acct.buying_power)
    except Exception:
        mock = cfg.get("mock", {})
        state.net_liquidation = mock.get("net_liquidation", 100_000)
        state.buying_power = mock.get("buying_power", 50_000)

    # --------------------------------------------------
    # Risk allocation
    # --------------------------------------------------
    state.defined_risk_limit = state.net_liquidation * 0.80
    state.undefined_risk_limit = state.net_liquidation * 0.20

    return state
