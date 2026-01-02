# trading_bot/main.py
"""
Comprehensive main function for the trading bot.
Each functionality is in its own def — comment out calls in main() to skip.
Covers account listing, balances, option chain, trade booking, position reading, risk display, and Sheets sync.
"""

import logging
from trading_bot.config import Config
from trading_bot.broker_mock import MockBroker
from trading_bot.brokers.tastytrade_broker import TastytradeBroker
from trading_bot.trade_execution import TradeExecutor
from trading_bot.strategy import ShortPutStrategy
from trading_bot.portfolio import Portfolio
from trading_bot.positions import PositionsManager
from trading_bot.risk import RiskManager
from trading_bot.options_sheets_sync import OptionsSheetsSync
from trading_bot.utils.trade_utils import book_butterfly, print_option_chain
from tastytrade.instruments import get_option_chain
from tastytrade.account import Account

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# trading_bot/main.py
def get_data_broker(config):
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

def get_execution_broker(config):
    """Connect execution broker based on execution_mode."""
    mode = config.general.get('execution_mode', 'mock').lower()

    if mode == 'mock':
        broker = MockBroker()
        broker.connect()
        logger.info("Execution broker: Mock")
        return broker

    creds_key = 'paper' if mode == 'paper' else 'live'
    creds = config.broker[creds_key]

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
        accounts = Account.get_accounts(broker.session)
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

    book_butterfly("MSFT", broker.session, quantity=1, limit_credit=3.00, dry_run=True)

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
        logger.info(f"Trade: {risk['trade_id']} | Strategy: {risk['strategy']}")
        logger.info(f"  PnL: ${risk['pnl']:.2f} | Allocation: {risk['allocation']:.2%}")
        logger.info(f"  Driver: {risk['pnl_driver']} | Violations: {risk['violations']}")
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
    sheets.sync_all(balance, position_risks)

def main():
    print("Starting trading bot...")
    global config
    config = Config.load('config.yaml')

    # Separate brokers
    #data_broker = get_data_broker(config)        # Always live for data
    execution_broker = get_execution_broker(config)  # Configurable

    # === Comprehensive Workflow — Comment out what you don't want ===
    list_all_accounts(execution_broker)

    get_account_balances(execution_broker)

    fetch_sample_option_chain(execution_broker, "MSFT")  # market data from live broker

    book_sample_option_position(execution_broker)

    read_current_positions(execution_broker)

    display_position_risk(execution_broker)

    display_portfolio_risk(execution_broker)

    # sync_google_sheets(execution_broker)  # Uncomment to sync Sheets
    logger.info("Bot run complete.")

if __name__ == "__main__":
    main()