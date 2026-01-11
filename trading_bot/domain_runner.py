import os
import logging
import time
from trading_bot.brokers.tastytrade_broker import TastytradeBroker
from trading_bot.domain.state import TradingState
from trading_bot.agents.portfolio_dude import portfolio_dude
from trading_bot.agents.risk_dude import risk_dude
from trading_bot.agents.trader_dude import trader_dude
from trading_bot.config_folder.config_loader import load_yaml_with_env

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    base_dir = os.path.dirname(os.path.dirname(__file__))

    broker_cfg_path = os.path.join(
        base_dir,
        "trading_bot\\config_folder",
        "tastytrade_broker.yaml"
    )

    broker_cfg = load_yaml_with_env(broker_cfg_path)

    broker = TastytradeBroker(broker_cfg)

    account_id = broker.get_account(broker_cfg)

    logger.info(f"Connected to Tastytrade | Accounts: {broker.get_accounts()}")
    
  # -------------------------------------------------
    # INITIAL SHARED STATE
    # -------------------------------------------------
   # Create orchestrator (graph)
   
    state = TradingState(
    broker_name="TASTYTRADE",
    account_id=account_id
    )

    state = portfolio_dude(state, broker)
    state = risk_dude(state)
    state = trader_dude(state)

    print("\n✅ Graph cycle completed cleanly")

if __name__ == "__main__":
    main()