from trading_bot.domain.models import Trade

STRATEGY_MAP = {
    "IRON_CONDOR": "IRON_CONDOR",
    "VERTICAL": "VERTICAL",
    "CSP": "CSP",
    "COVERED_CALL": "COVERED_CALL",
    "STRANGLE": "STRANGLE",
}

def tasty_position_to_trade(position) -> Trade:
    """
    position = tastytrade position object (mocked shape)
    """

    strategy = STRATEGY_MAP[position.strategy_type]

    # === MAX LOSS MODELING ===
    if position.defined_risk:
        max_loss = position.max_loss
        risk_type = "DEFINED"
    else:
        max_loss = model_undefined_risk(position)
        risk_type = "UNDEFINED"

    return Trade(
        trade_id=position.id,
        symbol=position.symbol,
        strategy=strategy,
        risk_type=risk_type,
        credit=position.credit_received,
        max_loss=max_loss,
        delta=position.net_delta,
        dte=position.dte,
        sector=position.sector or "UNKNOWN"
    )

def model_undefined_risk(position) -> float:
    """
    Conservative worst-case risk model.
    Can be replaced later with ATR / vol based model.
    """

    if position.strategy_type == "CSP":
        stop_price = position.strike - (1.5 * position.atr)
        return max(0, (position.strike - stop_price) * 100)

    if position.strategy_type == "STRANGLE":
        return position.credit_received * 4

    return position.credit_received * 3
