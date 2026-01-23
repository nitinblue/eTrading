import asyncio
from trading_claude.broker_adapters import TastytradeAdapter
from trading_claude.data_model import init_database, get_session, PortfolioORM
from datetime import datetime
from trading_claude.service_layer import PortfolioService

async def main():
      # 1. Initialize DB
    engine = init_database("sqlite:///trading.db")
    session = get_session(engine)

    # 2. Connect to broker
    adapter = TastytradeAdapter()
    
    if adapter.authenticate():
        print(f"Connected to account: {adapter.account_id}")
        # Get account balance
        balance = adapter.get_account_balance()
        print(f"Cash Balance: ${balance.get('cash_balance', 0)}")
        
        # Get positions
        positions = adapter.get_positions()
        print(f"Found {len(positions)} positions")
        
        # Get orders
        orders = adapter.get_orders()
        print(f"Found {len(orders)} orders")

      # ---------- SERVICE ----------
    portfolio_service = PortfolioService(
        session=session,
        broker_adapter=adapter
    )

    # ---------- CREATE / SYNC PORTFOLIO ----------
    portfolio = await portfolio_service.create_portfolio_from_broker(
        broker_name="TastyTrade",
        account_id=adapter.account_id,
        name="Main Trading Portfolio"
    )

    print("✅ Portfolio synced successfully")

    # ---------- SUMMARY ----------
    summary = portfolio_service.get_portfolio_summary(portfolio.id)

    print("\n📊 Portfolio Summary")
    print(f"Name: {summary['name']}")
    print(f"Cash Balance: ${summary['cash_balance']}")
    print(f"Buying Power: ${summary['buying_power']}")
    print(f"Total Equity: ${summary['total_equity']}")
    print(f"Total PnL: ${summary['total_pnl']}")
    print(f"Positions: {summary['positions_count']}")
    print(f"Open Trades: {summary['open_trades_count']}")


if __name__ == "__main__":   
   asyncio.run(main())