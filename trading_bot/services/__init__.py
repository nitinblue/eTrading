from trading_bot.risk.engine import evaluate_portfolio

def run_risk_check(portfolio, configs):
    result = evaluate_portfolio(portfolio, configs)

    print("\n=== RISK SNAPSHOT ===")
    print("Aggregated Risk:", result["agg_risk"])
    print("Net Delta:", result["net_delta"])
    print("Violations:", result["violations"])

    return result
