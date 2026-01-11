def init_state():
    return {
        # Global
        "broker": None,
        "accounts": [],
        "config": {},

        # Market context
        "market_regime": None,
        "news_summary": None,

        # Portfolio
        "portfolio_snapshot": {},
        "portfolio_performance": {},

        # Risk
        "risk_limits": {},
        "risk_usage": {},
        "risk_report": {},

        # Trades
        "trade_ideas": [],
        "validated_trades": [],
        "executed_trades": [],

        # Adjustments
        "adjustments": [],

        # Control flags
        "can_trade": True,
    }
