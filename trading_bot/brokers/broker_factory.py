import os
from trading_bot.config_folder.config_loader import load_yaml_with_env
from trading_bot.brokers.tastytrade_broker import TastytradeBroker


def create_tastytrade_broker() -> TastytradeBroker:
    """
    SINGLE SOURCE OF TRUTH for Tastytrade broker creation.

    - Handles paths
    - Handles config loading
    - Handles env substitution
    - Domain runner will NEVER touch this again
    """

    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(__file__))
    )

    broker_cfg_path = os.path.join(
        base_dir,
        "trading_bot",
        "config_folder",
        "tastytrade_broker.yaml",
    )

    broker_cfg = load_yaml_with_env(broker_cfg_path)

    return TastytradeBroker(broker_cfg)
