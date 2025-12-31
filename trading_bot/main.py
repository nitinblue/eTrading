# trading_bot/main.py
"""
Main entry point for the trading bot.
Clean broker selection with one config line switch.
"""
import logging
from trading_bot.config import Config
from trading_bot.broker_mock import MockBroker
from trading_bot.brokers.tastytrade_broker import TastytradeBroker
from trading_bot.market_data.tastytrade_market_data import TastytradeMarketData  # Optional for real broker
from trading_bot.trade_execution import TradeExecutor
from trading_bot.strategy import ShortPutStrategy
from trading_bot.portfolio import Portfolio
from trading_bot.positions import PositionsManager
from trading_bot.risk import RiskManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# trading_bot/main.py
"""
Main entry point for the trading bot.
Supports mock mode and real Tastytrade paper/live.
Now includes real connectivity test, option chain fetch, and market data display.
"""

import logging
from trading_bot.config import Config
from trading_bot.broker_mock import MockBroker
from trading_bot.brokers.tastytrade_broker import TastytradeBroker
from tastytrade.instruments import get_option_chain  # Direct import for demo
#from tastytrade.search import search_instruments  # For underlying price

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    print("Starting trading bot...")
    config = Config.load('config.yaml')

    # === ONE LINE TO SWITCH BROKER ===
    use_mock = config.general.get('use_mock', False)  # ← Set to False for real Tastytrade paper

    # Broker selection
    if use_mock:
        broker = MockBroker()
        broker.connect()
        logger.info("Using MockBroker (dry-run mode)")
        session = None  # No real session in mock
    else:
        broker = TastytradeBroker(
            username=config.broker['username'],
            password=config.broker['password'],
            is_paper=config.broker.get('environment', 'paper') == 'paper'
        )
        broker.connect()
        session = broker.session  # Real session for API calls
        logger.info("Connected to real Tastytrade account")

    # === Test Real Connectivity & Market Data ===
    if not use_mock and session:
        try:
            # 1. Get account balances
            balances = broker.get_account_balance()
            logger.info(f"Account Balance: Cash=${balances['cash_balance']:.2f}, Buying Power=${balances['equity_buying_power']:.2f}")

            # 2. Get current positions
            positions = broker.get_positions()
            logger.info(f"Current Positions: {len(positions)} found")
            for pos in positions[:5]:  # Show first 5
                logger.info(f"  {pos['symbol']} Qty: {pos['quantity']} @ ${pos['current_price']:.2f}")

           # 3. Fetch Option Chain for AAPL
            underlying = "GOOGL"
            logger.info(f"Fetching option chain for {underlying}...")
            chain = get_option_chain(session, underlying)

            expiries = list(chain.keys())[:3]
            for expiry in expiries:
                logger.info(f"Expiry: {expiry.date()} ({len(chain[expiry])} strikes)")
                for opt in list(chain[expiry])[:5]:
                    greeks_str = f"Delta:{opt.greeks.delta if opt.greeks else 'N/A'}"
                    logger.info(f"  {opt.symbol} Bid:{opt.bid} Ask:{opt.ask} {greeks_str}")

            # 4. Underlying price
            try:
                from tastytrade.instruments import Equity
                equity = Equity.get_equities(session, [underlying])[0]
                quote = equity.get_quote(session)
                underlying_price = quote.last_price or quote.close_price or quote.bid or quote.ask
                logger.info(f"{underlying} Current Price: ${underlying_price:.2f}")
            except Exception as e:
                logger.error(f"Underlying price fetch failed: {e}")

        except Exception as e:
            logger.error(f"Market data fetch failed: {e}")

    # === Sample Strategy Execution (dry-run even in real mode for safety) ===
    from trading_bot.trade_execution import TradeExecutor
    from trading_bot.strategy import ShortPutStrategy

    executor = TradeExecutor(broker)
    strategy_config = config.strategies.get('short_put', {})
    strategy = ShortPutStrategy(None, executor, strategy_config)  # market_data not needed for sample

    sample_signal = {
        'symbol': '.AAPL260131P00195000',  # Example OCC symbol
        'iv': 45,
        'delta': -0.17,
        'quantity': 1,
        'limit_price': 5.10
    }

    account_id = config.broker.get('default_account_id')
    result = strategy.execute_entry(sample_signal, account_id=account_id)
    logger.info(f"Sample Order Result: {result}")

    logger.info("Bot run complete.")
    
def main_1():
    print("Entering main function")
    config = Config.load('config.yaml')

    # === ONE LINE TO SWITCH BROKER ===
    use_mock = config.general.get('use_mock', False)  # ← Set to False for real Tastytrade

    # Broker selection
    if use_mock:
        broker = MockBroker()
        broker.connect()
        logger.info("Using MockBroker (dry-run mode)")
        market_data = None  # Not needed for mock
    else:
        broker = TastytradeBroker(          
            username=config.broker['username'],
            password=config.broker['password'],
            is_paper=config.broker.get('environment', 'paper') == 'paper'
        )
        broker.connect()
        logger.info("Using real Tastytrade broker")
        market_data = TastytradeMarketData(broker.session)  # Optional: for Greeks/prices

    # Core components
    executor = TradeExecutor(broker)
    positions_manager = PositionsManager(broker)
    risk_manager = RiskManager(config.risk)
    portfolio = Portfolio(positions_manager, risk_manager)

    # Strategy
    strategy_config = config.strategies.get('short_put', {})
    strategy = ShortPutStrategy(market_data, executor, strategy_config)

    # Sample trade signal (replace with Google Sheets input later)
    sample_signal = {
        'symbol': '.AAPL260131P00195000',
        'iv': 45,
        'delta': -0.17,
        'quantity': 4,
        'limit_price': 5.10
    }

    account_id = config.broker.get('default_account_id')

    # Execute sample trade
    result = strategy.execute_entry(sample_signal, account_id=account_id)
    logger.info(f"Execution Result: {result}")

    # Update portfolio and show net Greeks
    portfolio.update()
    logger.info(f"Net Portfolio Greeks: {portfolio.get_net_greeks()}")

if __name__ == "__main__":
    main()