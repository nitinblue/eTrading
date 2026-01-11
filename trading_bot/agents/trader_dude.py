import logging
from trading_bot.domain.state import TradingState

logger = logging.getLogger(__name__)


def trader_dude(state: TradingState):
    logger.info("🧠 TraderDude: Reviewing reports")

    print("\n=== TRADER CONTEXT ===")
    for msg in state.messages:
        print("-", msg)

    print("\nTrader can now act manually using above reports.")
    return state
