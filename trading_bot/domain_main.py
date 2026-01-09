# main.py
from config.loader import load_all_configs
from services.portfolio_builder import build_portfolio
from services.risk_service import run_risk_check
from services.what_if_service import run_what_if, build_what_if_trade

def main():
    # 1️⃣ Load configs
    configs = load_all_configs()

    # 2️⃣ Get positions from tastytrade (you already have this)
    tasty_positions = tasty_client.get_open_positions()

    # 3️⃣ Build portfolio
    portfolio = build_portfolio(
        tasty_positions,
        realized_pnl=tasty_client.get_realized_pnl(),
        unrealized_pnl=tasty_client.get_unrealized_pnl()
    )

    # 4️⃣ Run live risk check
    risk_snapshot = run_risk_check(portfolio, configs)

    # 5️⃣ Run what-if
    what_if_trade = build_what_if_trade()
    what_if_result = run_what_if(portfolio, what_if_trade, configs)

    if what_if_result["violations"]:
        print("❌ Trade REJECTED")
    else:
        print("✅ Trade APPROVED")

if __name__ == "__main__":
    main()
