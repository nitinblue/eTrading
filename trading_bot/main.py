# trading_bot/main.py
"""
Main entry point for the trading bot.
Clean broker selection with one config line switch.
"""

import logging
from config import Config
from broker_mock import MockBroker
from brokers.tastytrade_broker import TastytradeBroker
from market_data.tastytrade_market_data import TastytradeMarketData  # Optional for real broker
from trade_execution import TradeExecutor
from strategy import ShortPutStrategy
from portfolio import Portfolio
from positions import PositionsManager
from risk import RiskManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
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