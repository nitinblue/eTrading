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
from trading_bot.options_sheets_sync import OptionsSheetsSync

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
    use_mock = config.general.get('use_mock', True)

    if use_mock:
        broker = MockBroker()
        broker.connect()
        logger.info("Using MockBroker (dry-run mode)")
    else:
        broker = TastytradeBroker(
            username=config.broker['username'],
            password=config.broker['password'],
            is_paper=config.broker.get('environment', 'paper') == 'paper'
        )
        broker.connect()
        logger.info("Using real Tastytrade broker")

    # Core components
    executor = TradeExecutor(broker)
    positions_manager = PositionsManager(broker)
    risk_manager = RiskManager(config.risk)
    portfolio = Portfolio(positions_manager, risk_manager)

    # Update portfolio to get current positions
    portfolio.update()

    # === NEW: List all positions with risk attributes ===
    capital = portfolio.total_value or 100000.0  # Use actual equity or fallback
    position_risks = risk_manager.list_positions_api(positions_manager.positions, capital)  # Use list_positions_api for list

    logger.info("\n=== POSITION RISK REPORT ===")
    for risk in position_risks:
        logger.info(f"Trade ID: {risk['trade_id']} | Leg: {risk['leg_id']} | Strategy: {risk['strategy']}")
        logger.info(f"  Allocation: {risk['allocation']:.2%} | PnL: ${risk['pnl']:.2f} | Driver: {risk['pnl_driver']}")
        logger.info(f"  Buying Power Used: ${risk['buying_power_used']:.2f}")
        logger.info(f"  Stop Loss: ${risk['stop_loss']:.2f} | Take Profit: ${risk['take_profit']:.2f}")
        logger.info(f"  Undefined Risk: {risk['is_undefined_risk']}")
        if risk['violations']:
            logger.warning(f"  VIOLATIONS: {'; '.join(risk['violations'])}")
        logger.info("---")

    # Portfolio-level summary (use assess_portfolio if you have it, or skip if not)
    try:
        portfolio_risk = risk_manager.assess_portfolio(positions_manager.positions, capital)
        logger.info("\n=== PORTFOLIO RISK SUMMARY ===")
        logger.info(f"Net Greeks: {portfolio.get_net_greeks()}")
        logger.info(f"Total Undefined Risk: {portfolio_risk['total_undefined_risk']:.2%}")
        logger.info(f"Available Margin: ${portfolio_risk['available_margin']:.2f}")
        logger.info("Strategy Concentration:")
        for strat, conc in portfolio_risk['strategy_concentration'].items():
            logger.info(f"  {strat}: {conc:.2%}")
    except AttributeError:
        logger.info("assess_portfolio not available — skipping portfolio summary")
    except ValueError as e:
        logger.error(f"Portfolio risk violation: {e}")

    # Sample order execution
    strategy_config = config.strategies.get('short_put', {})
    strategy = ShortPutStrategy(None, executor, strategy_config)

    sample_signal = {
        'symbol': '.AAPL260131P00195000',
        'iv': 45,
        'delta': -0.17,
        'quantity': 4,
        'limit_price': 5.10
    }

    result = strategy.execute_entry(sample_signal)
    logger.info(f"Sample Order Result: {result}")

        # Get position risk report
    capital = broker.get_account_balance().get('equity', 100000.0)
    position_risks = risk_manager.list_positions_api(positions_manager.positions, capital)

    # Print report (your existing loop)
    logger.info("\n=== POSITION RISK REPORT ===")
    # ... your print loop

    # Google Sheets sync
    try:
        sheets_sync = OptionsSheetsSync(config)
        sheets_sync.sync_all(
            balance=broker.get_account_balance(),
            position_risks=position_risks
        )
    except Exception as e:
        logger.error(f"Google Sheets sync failed: {e}")

    logger.info("Bot run complete.")


def main_1():
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

    risks = RiskManager.list_positions_api(PositionsManager.positions, Portfolio.total_value)
    print(risks)  # Or write to Sheet
    
    logger.info("Bot run complete.")
    

if __name__ == "__main__":
    main()