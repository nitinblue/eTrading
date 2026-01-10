# trading_bot/domain_runner.py

import logging
from trading_bot.config_folder.loader import load_all_configs
from trading_bot.brokers.tastytrade_broker import TastytradeBroker
from trading_bot.agents.tech_orchestrator_dude import build_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from trading_bot.config import Config


def main():
    logger.info("🚀 Starting eTrading domain runner")

    # Load config
    configs = load_all_configs()

    # Broker
    # temp measure, need to switch to config from load_all_configs

    config = Config.load('config.yaml')

    creds = config.broker['data']
    broker = TastytradeBroker(
        client_secret=creds['client_secret'],
        refresh_token=creds['refresh_token'],
        is_paper=False  # Force live for data
    )
    # broker.connect()

 
    # Build agent graph
    graph = build_graph()

    # Initial state
    initial_state = {
        "broker": broker,
        "config": configs,
    }

    # Invoke agentic flow
    final_state = graph.invoke(initial_state)

    logger.info("🏁 Run completed")
    logger.info("Final output: %s", final_state.get("output"))


if __name__ == "__main__":
    main()
