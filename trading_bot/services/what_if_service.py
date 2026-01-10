from trading_bot.domain.models import Trade
from trading_bot.risk.what_if import what_if_add_trade

def build_what_if_trade():
    return Trade(
        trade_id="WHATIF_001",
        symbol="NVDA",
        strategy="IRON_CONDOR",
        risk_type="DEFINED",
        credit=420,
        max_loss=1580,
        delta=6,
        dte=45,
        sector="TECH"
    )


def run_what_if(portfolio, new_trade, configs):
    result = what_if_add_trade(portfolio, new_trade, configs)

    print("\n=== WHAT-IF RESULT ===")
    print("Violations:", result["violations"])
    print("Projected Risk:", result["agg_risk"])

    return result
