import os
import logging
import time
from trading_bot.config_folder.config_loader import load_yaml_with_env
from trading_bot.brokers.tastytrade_broker import TastytradeBroker
from trading_bot.agents.tech_orchestrator_dude import TechOrchestratorDude

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

    logger.info(f"Connected to Tastytrade | Accounts: {broker.get_accounts()}")
  # -------------------------------------------------
    # INITIAL SHARED STATE
    # -------------------------------------------------
   # Create orchestrator (graph)
    orchestrator = TechOrchestratorDude()

    cycle_interval = 300  # 5 minutes - adjust as needed

    logger.info("Bot runner active — Ctrl+C to stop")
    try:
        while True:
            logger.info("\n=== STARTING NEW CYCLE ===")

            # Build initial state for this cycle
            initial_state = {
                "input": "Run full trading cycle: Monitor, analyze, and recommend trades",
                "output": "",
                "current_bucket": "defined",  # Start with defined risk
                "config": broker_cfg,             # Inject config for all agents
                "broker": broker              # Inject broker for real calls
            }

            # Invoke the graph
            try:
                result = orchestrator.run_cycle(initial_state)
                logger.info(f"Cycle complete. Output summary:\n{result.get('output', 'No output')}")
            except Exception as e:
                logger.error(f"Cycle failed: {e}")
                # Optional: continue or exit

            logger.info(f"Sleeping for {cycle_interval} seconds...")
            time.sleep(cycle_interval)

    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt)")
    except Exception as e:
        logger.critical(f"Runner crashed: {e}")

if __name__ == "__main__":
    main()