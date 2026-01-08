# trading_bot/bot_runner.py
"""
Local forever loop runner.
- Passes config and broker to initial_state.
- Runs agentic cycle every 5 minutes.
"""

import time
import logging
from trading_bot.config import Config
from trading_bot.agents.tech_orchestrator_dude import TechOrchestratorDude
from trading_bot.brokers.tastytrade_broker import TastytradeBroker

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_forever():
    config = Config.load('config.yaml')
    creds = config.broker['data']
    mode = config.general.get('execution_mode', 'mock').lower()

    # Create broker
    broker = TastytradeBroker(
        client_secret=creds['client_secret'],
        refresh_token=creds['refresh_token'],
        is_paper=(mode == 'paper')
    )
    logger.info("Broker initialized from bot_runner: ", {broker})

    orchestrator = TechOrchestratorDude()

    logger.info("Bot runner started — forever loop (Ctrl+C to stop)")
    cycle_interval = 300  # 5 minutes

    try:
        while True:
            logger.info("\n=== NEW CYCLE START ===")
            initial_state = {
                "input": "Run full trading cycle",
                "output": "",
                "current_bucket": "defined",
                "config": config,  # ← THIS FIXES KeyError
                "broker": broker   # Broker for real calls
            }
            orchestrator.run_cycle(initial_state)
            logger.info(f"Cycle complete — sleeping {cycle_interval} seconds")
            time.sleep(cycle_interval)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")

if __name__ == "__main__":
    run_forever()