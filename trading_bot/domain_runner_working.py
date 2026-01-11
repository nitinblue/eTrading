import os
import logging

from trading_bot.config_folder.config_loader import load_yaml_with_env
from trading_bot.brokers.tastytrade_broker import TastytradeBroker
from trading_bot.agents.tech_orchestrator_dude import build_trading_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    logger.info("🚀 Starting Trading Bot (Domain Runner)")

    # -------------------------------------------------
    # CONFIG LOADING
    # -------------------------------------------------
    base_dir = os.path.dirname(__file__)  # trading_bot/

    broker_cfg_path = os.path.join(
        base_dir,
        "config_folder",
        "tastytrade_broker.yaml"
    )

    broker_cfg = load_yaml_with_env(broker_cfg_path)

    # -------------------------------------------------
    # BROKER INITIALIZATION
    # -------------------------------------------------
    broker = TastytradeBroker(broker_cfg)

    logger.info(f"Connected accounts: {broker.get_accounts()}")

    # -------------------------------------------------
    # INITIAL SHARED STATE
    # -------------------------------------------------
    state = {
        "broker": broker,
        "config": broker_cfg,
        "risk_usage": {},
        "trade_ideas": [],
        "ranked_trades": [],
        "adjustments": [],
        "news_summary": None,
    }

    # -------------------------------------------------
    # ORCHESTRATION
    # -------------------------------------------------
    graph = build_trading_graph()
    final_state = graph.invoke(state)

    # -------------------------------------------------
    # OUTPUT (TEMPORARY)
    # -------------------------------------------------
    logger.info("==== FINAL TRADE PLAN ====")
    for trade in final_state.get("ranked_trades", []):
        logger.info(trade)

    logger.info("==== ADJUSTMENT SUGGESTIONS ====")
    for adj in final_state.get("adjustments", []):
        logger.info(adj)

    logger.info("🏁 Trading Bot finished successfully")


if __name__ == "__main__":
    main()
