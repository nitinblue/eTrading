# trading_bot/main.py
import logging
from trading_bot.config import Config
from trading_bot.brokers.tastytrade_broker import TastytradeBroker, PriceEffect
from trading_bot.broker_mock import MockBroker
from trading_bot.market_data.tastytrade_market_data import TastytradeMarketData  # Or your own
from trading_bot.trade_execution import TradeExecutor
from trading_bot.strategy import ShortPutStrategy
from trading_bot.portfolio import Portfolio
from trading_bot.positions import PositionsManager
from trading_bot.risk import RiskManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    config = Config.load('config.yaml')

    # Choose broker
    if config.general.get('use_mock', True):
        broker = MockBroker()
        logger.info("Using MockBroker for dry run")
    else:
        broker = TastytradeBroker(
            username=config.broker['username'],
            password=config.broker['password'],
            is_paper=config.broker.get('environment', 'paper') == 'paper'
        )
        broker.connect()

    # Core components
    executor = TradeExecutor(broker)
    market_data = TastytradeMarketData(broker.session) if hasattr(broker, 'session') else None

    positions_manager = PositionsManager(broker)
    risk_manager = RiskManager(config.risk)
    portfolio = Portfolio(positions_manager, risk_manager)

    # Strategy
    strategy_config = config.strategies.get('short_put', {})
    strategy = ShortPutStrategy(market_data, executor, strategy_config)

    # Example trade signal
    sample_signal = {
        'symbol': '.AAPL260131P00195000',
        'iv': 45,
        'delta': -0.17,
        'quantity': 4,
        'limit_price': 5.10
    }

    account_id = config.broker.get('default_account_id', None)  # Optional multi-account

    logger.info("Evaluating entry...")
    result = strategy.execute_entry(sample_signal, account_id=account_id)

    logger.info(f"Execution result: {result}")

    # Refresh portfolio
    portfolio.update()
    logger.info(f"Net portfolio Greeks: {portfolio.get_net_greeks()}")

if __name__ == '__main__':
    main()