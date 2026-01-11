import logging
from trading_bot.brokers.broker_factory import create_tastytrade_broker
from trading_bot.domain.state import TradingState
from trading_bot.agents.tech_orchestrator_dude import run_trading_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    broker = create_tastytrade_broker()
    account_id = broker.get_default_account()

    state = TradingState(
        broker_name="TASTYTRADE",
        account_id=account_id,
        broker=broker,
    )

    run_trading_graph(state)


if __name__ == "__main__":
    main()
