# trading_bot/main.py
"""
Comprehensive main function for the trading bot.
Each functionality is in its own def — comment out calls in main() to skip.
Covers account listing, balances, option chain, trade booking, position reading, risk display, and Sheets sync.
"""

from cmath import exp
from datetime import datetime
import logging
from trading_bot.config import Config
from trading_bot.config_folder.loader import load_all_configs

from trading_bot.broker_mock import MockBroker
from trading_bot.brokers.tastytrade_broker import TastytradeBroker
from trading_bot.trade_execution import TradeExecutor
#from trading_bot.strategy import ShortPutStrategy
from tastytrade.order import Leg
from trading_bot.portfolio import Portfolio
from trading_bot.positions import PositionsManager
from trading_bot.risk_main import RiskManager
from trading_bot.options_sheets_sync import OptionsSheetsSync
from trading_bot.strategy_screener import StrategyScreener
from trading_bot.utils.trade_utils import print_option_chain
from trading_bot.strategies.orb_0dte import ORB0DTEStrategy
from tastytrade.instruments import get_option_chain
from trading_bot.trades import sell_otm_put, buy_atm_leap_call,book_butterfly
from trading_bot.agents import tech_orchestrator_dude
from tastytrade.account import Account
from trading_bot.technicals.technical_indicators import classify_regime
from trading_bot.brokers.broker_factory import create_broker

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# trading_bot/main.py
def get_data_broker(config, broker_name: str = None, mode: str = 'live'):
    """Always connect to LIVE Tastytrade for production-quality market data."""

    creds = config.broker['data']
    broker = TastytradeBroker(
        client_secret=creds['client_secret'],
        refresh_token=creds['refresh_token'],
        is_paper=False  # Force live for data
    )
    broker.connect()
    logger.info("Market data broker connected (LIVE account)")
    return broker


def get_execution_broker(config, broker_name: str = None):
    """Connect execution broker based on execution_mode."""
    mode = config.general.get('execution_mode', 'mock').lower()

    if mode == 'mock':
        broker = MockBroker()
        broker.connect()
        logger.info("Execution broker: Mock")
        return broker

    creds_key = 'paper' if mode == 'paper' else 'live'
    creds = config.broker[creds_key]

    #broker = create_broker(config, broker_name=broker_name, mode=mode)
    #broker.connect()
    #logger.info(f"Execution broker: {mode.upper()} account")
    #return broker   


    broker = TastytradeBroker(
        client_secret=creds['client_secret'],
        refresh_token=creds['refresh_token'],
        is_paper=(mode == 'paper')
    )
    broker.connect()
    logger.info(f"Execution broker: {mode.upper()} account")
    return broker


def list_all_accounts(broker):
    """List all Tastytrade accounts (skip in mock mode)."""
    if not hasattr(broker, 'session') or broker.session is None:
        logger.info("Skipping account listing (mock mode)")
        return

    try:
        from tastytrade.account import Account
        accounts = Account.get(broker.session)
        logger.info("\n=== ALL ACCOUNTS ===")
        for acc in accounts:
            logger.info(f"Account Number: {acc.account_number}")
            logger.info(f"  Type: {acc.account_type_name}")
            logger.info(f"  Opened: {acc.opened_at}")
            logger.info("---")
    except Exception as e:
        logger.error(f"Failed to list accounts: {e}")

def get_account_balances(broker):
    """Get account balances (skip in mock mode)."""
    if not hasattr(broker, 'session') or broker.session is None:
        logger.info("Skipping account balances (mock mode)")
        return

    try:
        balance = broker.get_account_balance()
        logger.info("\n=== ACCOUNT BALANCE ===")
        logger.info(f"Cash Balance: ${balance.get('cash_balance', 0):.2f}")
        logger.info(f"Equity Buying Power: ${balance.get('equity_buying_power', 0):.2f}")
        logger.info(f"Derivative Buying Power: ${balance.get('derivative_buying_power', 0):.2f}")
        logger.info(f"Margin Equity: ${balance.get('margin_equity', 0):.2f}")
    except Exception as e:
        logger.error(f"Failed to get balances: {e}")

def fetch_sample_option_chain(broker, underlying: str = "MSFT"):
    """Fetch and print option chain (skip in mock mode)."""
    if not hasattr(broker, 'session') or broker.session is None:
        logger.info("Skipping option chain fetch (mock mode)")
        return

    print_option_chain(underlying, broker.session)

def book_sample_option_position(broker):
    """Book sample butterfly (skip in mock mode)."""
    if not hasattr(broker, 'session') or broker.session is None:
        logger.info("Skipping butterfly booking (mock mode)")
        return
def test_butterfly_full(data_broker, execution_broker):
    # print_option_chain("MSFT",data_broker.session)
    
    # From table output
    exp = "2026-01-16"  # Copy from print_option_chain
    strikes = [160.0, 165.0, 170.0]  # Copy from table
    
    print("\n" + "="*60)       
    preview = place_butterfly_preview(execution_broker.session, "MSFT", exp, strikes)
    
    if preview:
        # Uncomment for paper trade
        result = submit_butterfly(execution_broker, "MSFT", exp, strikes)
        print("✅ Ready for paper trade!{result}")
        
        # Check positions
        positions = execution_broker.get_positions()
        print(f"Current positions: {len([p for p in positions if 'MSFT' in p.instrument])}")

def place_butterfly_preview(session, underlying, exp, strikes, quantity=1):
    """
    PREVIEW butterfly (no submission) - validates symbols/pricing
    """
    chain = get_option_chain(session, underlying)  
    target_date = datetime.strptime(exp, "%Y-%m-%d").date()  
  
    if target_date not in chain:
        print(f"No {exp} expiry")
        return None
    
    options = chain[target_date]
    
    # Find legs
    wing1_put = next((o for o in options if float(o.strike_price) == strikes[0] and o.option_type == "P"), None)
    body_put = next((o for o in options if float(o.strike_price) == strikes[1] and o.option_type == "P"), None)
    wing2_put = next((o for o in options if float(o.strike_price) == strikes[2] and o.option_type == "P"), None)
    
    if not all([wing1_put, body_put, wing2_put]):
        print("Missing option symbols")
        return None
    
    print(f"✅ Butterfly legs found: {wing1_put.symbol}", f"{body_put.symbol}", f"{wing2_put.symbol}")
    # print(f"  Buy 1x {wing1_put.symbol} @ ${wing1_put.bid or 0:.2f}")
    # print(f"  Sell 2x {body_put.symbol} @ ${body_put.bid or 0:.2f}")
    # print(f"  Buy 1x {wing2_put.symbol} @ ${wing2_put.bid or 0:.2f}")
    
    # Theoretical debit (use quotes if available)
    # debit = (float(wing1_put.bid or 0) + float(wing2_put.bid or 0) - 2 * float(body_put.bid or 0))
    # print(f"📊 Est debit: ${debit:.2f}")       
    return [wing1_put, body_put, wing2_put]

def submit_butterfly(session, underlying, exp_date, strikes, quantity=1, max_debit=8.50):
    """
    SUBMIT live paper order (use with caution!)
    """
    preview = place_butterfly_preview(session.session, underlying, exp_date, strikes, quantity)    
    if not preview:
        return None
    return book_butterfly(session,preview,underlying, quantity=1, max_debit=8.50)
          
def read_all_orders(broker):
    """Read and display all orders."""
    orders = broker.get_all_orders()
    logger.info("\n=== ALL ORDERS ===")
    for order in orders:
        logger.info(f"Order ID: {order['order_id']} | Status: {order['status']} | Created At: {order['updated_at']}")
        logger.info(f"  Type: {order['order_type']} | Price Effect: {order['price_effect']} ")
        logger.info(f"  Legs:")
        for leg in order['legs']:
            logger.info(f"    Symbol: {leg['symbol']} | Action: {leg['action']} | Quantity: {leg['quantity']}")
        logger.info("---")
def read_current_positions(broker):
    """Read and display current positions."""
    positions = broker.get_positions()
    logger.info("\n=== CURRENT POSITIONS ===")
    for pos in positions:
        logger.info(f"Symbol: {pos['symbol']} | Quantity: {pos['quantity']} | Entry Price: ${pos['entry_price']:.2f} | Current Price: ${pos['current_price']:.2f}")
        logger.info(f"Greeks: {pos['greeks']}")
        logger.info("---")

def display_position_risk(broker):
    """Display position-level risk."""
    positions_manager = PositionsManager(broker)
    risk_manager = RiskManager(config.risk)
    portfolio = Portfolio(positions_manager, risk_manager)

    portfolio.update()
    capital = broker.get_account_balance().get('equity', 100000.0)
    position_risks = risk_manager.list_positions_api(positions_manager.positions, capital)

    logger.info("\n=== POSITION RISK REPORT ===")
    for risk in position_risks:
        logger.info(f"Trade: {risk['trade_id']} | Strategy: {risk['strategy']} | Symbol: {risk['symbol']}")
        logger.info(f"  Qty: {risk['quantity']} | Entry: ${risk['entry_price']:.2f} | Current: ${risk['current_price']:.2f}")
        logger.info(f"  PnL: ${risk['pnl']:.2f} | Allocation: {risk['allocation']:.2%}")
        logger.info(f"  Driver: {risk['pnl_driver']} | Vol: {risk['volume']} | OI: {risk['open_interest']}")
        logger.info(f"  Stop Loss: ${risk['stop_loss']:.2f} {'(HIT)' if risk['stop_hit'] else ''}")
        logger.info(f"  Take Profit: ${risk['take_profit']:.2f} {'(HIT)' if risk['tp_hit'] else ''}")
        if risk['violations']:
            logger.warning(f"  Violations: {'; '.join(risk['violations'])}")
        logger.info("---")

def display_portfolio_risk(broker):
    """Display portfolio-level risk."""
    positions_manager = PositionsManager(broker)
    risk_manager = RiskManager(config.risk)
    portfolio = Portfolio(positions_manager, risk_manager)

    portfolio.update()  # This calls risk_manager.assess() internally

    capital = broker.get_account_balance().get('equity', 100000.0)
    # Use list_positions_api for reporting (returns list)
    position_risks = risk_manager.list_positions_api(positions_manager.positions, capital)

    logger.info("\n=== PORTFOLIO RISK SUMMARY ===")
    net_greeks = portfolio.get_net_greeks()
    logger.info(f"Net Greeks: {net_greeks}")

    # Calculate summary from position_risks
    total_undefined = sum(r['buying_power_used'] for r in position_risks if r['is_undefined_risk']) / capital if capital > 0 else 0
    available_margin = capital * (1 - risk_manager.reserved_margin) - sum(r['buying_power_used'] for r in position_risks)

    logger.info(f"Total Undefined Risk: {total_undefined:.2%}")
    logger.info(f"Available Margin: ${available_margin:.2f}")

def sync_google_sheets(broker):
    """Sync to Google Sheets (if configured)."""
    sheets = OptionsSheetsSync(config)
    balance = broker.get_account_balance()
    positions_manager = PositionsManager(broker)
    risk_manager = RiskManager(config.risk)
    portfolio = Portfolio(positions_manager, risk_manager)
    portfolio.update()
    capital = balance.get('equity', 100000.0)
    position_risks = risk_manager.list_positions_api(positions_manager.positions, capital)
    sheets.sync_all(broker, portfolio, position_risks)

def run_strategy_screener(broker):
    screener = StrategyScreener(config, broker.session)
    underlyings = ["SPY", "QQQ", "IWM", "MSFT", "AAPL", "TSLA", "NVDA"]
    screener.run_all_screeners(underlyings)

# check out implementation of a strategy screener
def run_0dte_orb_strategy(broker):
    """Run 0DTE Opening Range Breakout strategy."""
    strategy = ORB0DTEStrategy(broker.session, config)
    strategy.run()

def run_wheel_strategy(broker):
    """Run the Wheel Strategy."""
    from trading_bot.strategies.wheel import WheelStrategy
    risk_manager = RiskManager(config.risk)
    underlying = "MSFT"  # Or from config, or list for multiple wheels
    strategy = WheelStrategy(broker.session, config, risk_manager, underlying)
    strategy.run()

def test_book_trades(broker):
    """Book sample trades to test positions."""
    from trading_bot.utils.trade_utils import sell_otm_put, buy_atm_leap_call

    # Sell OTM put
    sell_otm_put("MSFT", broker.session, dte=45, delta_target=-0.16, quantity=1, dry_run=True)

    # Buy ATM LEAP call
    buy_atm_leap_call("MSFT", broker.session, dte=365, delta_target=0.50, quantity=1, dry_run=True)
    


# New function
def test_book_sample_trades(broker, dry_run=False):
    logger.info("\n=== BOOKING HARDCODED TRADES (Paper Account) ===")
    sell_otm_put(broker, dry_run=dry_run)
    buy_atm_leap_call(broker, dry_run=dry_run)

# In main.py — add these test functions

def test_rsi_ma_signal():
    from trading_bot.technical_analyzer import TechnicalAnalyzer

    analyzer = TechnicalAnalyzer(config)

    underlying = "MSFT"
    data = analyzer.fetch_historical_data(underlying, period="2y")
    if data.empty:
        logger.error(f"No data for {underlying}")
        return

    indicators = analyzer.calculate_indicators(data)
    phase = analyzer.detect_phases(data, indicators)
    levels = analyzer.find_order_blocks_support_resistance(data)

    logger.info(f"\n=== TECHNICAL ANALYSIS TEST: {underlying} ===")
    logger.info(f"Current Price: ${data['Close'].iloc[-1]:.2f}" if not data.empty else "N/A")
    logger.info(f"RSI (14): {indicators.get('rsi', 'N/A'):.2f}")
    logger.info(f"SMA Short (50): ${indicators.get('sma_short', 'N/A'):.2f}")
    logger.info(f"SMA Long (200): ${indicators.get('sma_long', 'N/A'):.2f}")
    logger.info(f"Phase: {phase.upper()}")
    logger.info(f"Support: ${levels['support']:.2f} | Resistance: ${levels['resistance']:.2f} | Order Block: ${levels['order_block']:.2f}")

    bullish = analyzer.get_positive_signal(underlying, 'bullish')
    bearish = analyzer.get_positive_signal(underlying, 'bearish')
    neutral = analyzer.get_positive_signal(underlying, 'neutral')

    logger.info(f"Signal — Bullish: {bullish} | Bearish: {bearish} | Neutral: {neutral}")

def test_multiple_stocks():
    from trading_bot.technical_analyzer import TechnicalAnalyzer

    analyzer = TechnicalAnalyzer(config)

    stocks = ["MSFT", "AAPL", "SPY", "TSLA", "NVDA"]
    logger.info("\n=== MULTI-STOCK TECHNICAL SCAN ===")
    for stock in stocks:
        try:
            bullish = analyzer.get_positive_signal(stock, 'bullish')
            bearish = analyzer.get_positive_signal(stock, 'bearish')
            neutral = analyzer.get_positive_signal(stock, 'neutral')
            logger.info(f"{stock}: Bullish={bullish} | Bearish={bearish} | Neutral={neutral}")
        except Exception as e:
            logger.error(f"Scan failed for {stock}: {e}")

def test_phase_detection():
    from trading_bot.technical_analyzer import TechnicalAnalyzer

    analyzer = TechnicalAnalyzer(config)

    underlying = "AAPL"
    data = analyzer.fetch_historical_data(underlying, period="1y")
    indicators = analyzer.calculate_indicators(data)
    phase = analyzer.detect_phases(data, indicators)

    logger.info(f"\n=== PHASE DETECTION TEST: {underlying} ===")
    logger.info(f"Detected Phase: {phase.upper()}")

def test_agentic_system(broker, config):
    from trading_bot.agents import TechOrchestratorDude

    orchestrator = TechOrchestratorDude(config, broker.session)
    result = orchestrator.run("Analyze MSFT for Wheel entry")
    logger.info(f"Agentic System Result: {result}")

    result = classify_regime("^GSPC")  # SPX
    print(result)

    # Example: Nasdaq
    print(classify_regime("^NDX"))

    # Example: Russell
    print(classify_regime("^RUT"))
    
    
def main():
    print("Starting trading bot...")
    global config
    config = Config.load('config.yaml')
    #configs = load_all_configs()
    #config = configs["broker"]
    # Separate brokers
    data_broker = get_data_broker(config, broker_name='tastytrade')        # Always live for data
    execution_broker = get_execution_broker(config, broker_name='tastytrade')  # Configurable

    # =
    get_account_balances(data_broker)

    # New test functions to book simple trades.
    # test_book_sample_trades(execution_broker,dry_run=False)

    fetch_sample_option_chain(data_broker, "MSFT")  # market data from live broker

    # book_sample_option_position(execution_broker)
    
    # test_butterfly_full(data_broker,execution_broker) ## working butterfly test
    # read_all_orders(data_broker)

    # read_current_positions(data_broker)

    # display_position_risk(data_broker)

    # display_portfolio_risk(data_broker)
    
    
    # Test technical analysis
    # test_rsi_ma_signal()
    # test_multiple_stocks()
    # test_phase_detection()

    # run_strategy_screener(execution_broker)

    # run_0dte_orb_strategy(execution_broker)

    # Need to work on Polygon API keys and setup, read PendingTasks.txt
    # run_wheel_strategy(execution_broker)
    
    # test_agentic_system(execution_broker, config)  # Add this
    
    result = classify_regime("^GSPC")  # SPX
    print(result)

    # Example: Nasdaq
    print(classify_regime("^NDX"))

    # Example: Russell
    print(classify_regime("^RUT"))
    
    # python objects for trade, leg..populate data objects with fields that are specific to tastytrade api...for legs use domain.legs.py.. trade.py
    sync_google_sheets(data_broker)  # Uncomment to sync Sheets
    logger.info("Bot run complete.")

if __name__ == "__main__":
    main()
    
    
    

    