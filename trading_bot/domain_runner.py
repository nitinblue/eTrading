import logging

from trading_bot.config_folder.config_loader import load_yaml_with_env
from trading_bot.brokers.tastytrade_broker import TastytradeBroker
from trading_bot.config_folder.loader import load_all_configs
from trading_bot.brokers.tastytrade_broker import TastytradeBroker
from trading_bot.agents.tech_orchestrator_dude import build_graph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    
    '''
        START
        ↓
        market_news_dude
        ↓
        portfolio_dude
        ↓
        if defined_risk_available → defined_risk_trader_dude
        ↓
        if undefined_risk_available → undefined_risk_trader_dude
        ↓
        END
    '''
    logger.info("Starting trading bot domain runner")


    # ------------------------------------------------------------------
    # Initialize and connect broker
    # ------------------------------------------------------------------
    broker_cfg = load_yaml_with_env("trading_bot/config_folder/tastytrade_broker.yaml")
    logger.info("Broker configuration loaded: {broker_cfg}")
    tastytrade_broker = TastytradeBroker(broker_cfg)
    tastytrade_broker.connect()
    logger.info(f"Tastytrade connected. Accounts: {list(tastytrade_broker.accounts.keys())}")

    # ------------------------------------------------------------------
    # PLACEHOLDER: Next phases (safe to keep commented for now)
    # ------------------------------------------------------------------
    # portfolio = PortfolioBuilder(broker).build()
    # risk_state = RiskEngine(portfolio).evaluate()
    # orchestrator = TechOrchestrator(...)
    # orchestrator.run()

    # Load config
    configs = load_all_configs()
        # Build agent graph
    graph = build_graph()

    # Initial state
    initial_state = {
        "broker": tastytrade_broker,
        "config": configs,
    }

    # Invoke agentic flow
    final_state = graph.invoke(initial_state)

    logger.info("🏁 Run completed")
    logger.info("Final output: %s", final_state.get("output"))
    logger.info("Domain runner completed successfully")


if __name__ == "__main__":
    main()
