import os
import logging
from trading_bot.config_folder.config_loader import load_yaml_with_env

logger = logging.getLogger(__name__)


def portfolio_dude(state):
    """
    Portfolio Manager:
    - Loads portfolio / risk config
    - Pulls positions from broker
    - Computes portfolio-level metrics
    """

    # -----------------------------
    # Load portfolio config ONCE
    # -----------------------------
    if not state.portfolio_config:
        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))
        )

        cfg_path = os.path.join(
            base_dir,
            "trading_bot",
            "config_folder",
            "portfolio.yaml"  # 👈 use EXISTING file
        )

        state.portfolio_config = load_yaml_with_env(cfg_path)
        logger.info("📘 Portfolio config loaded")

    broker = state.broker
    account_id = state.account_id

    # -----------------------------
    # Pull live positions
    # -----------------------------
    positions = broker.get_positions(account_id)
    state.positions = positions

    # -----------------------------
    # Basic portfolio metrics
    # -----------------------------
    net_liq = broker.get_net_liquidation(account_id)
    buying_power = broker.get_buying_power(account_id)

    state.portfolio_metrics = {
        "net_liquidation": net_liq,
        "buying_power": buying_power,
        "num_positions": len(positions),
    }

    logger.info(
        f"[Portfolio] NetLiq={net_liq:.2f}, "
        f"BP={buying_power:.2f}, "
        f"Positions={len(positions)}"
    )

    return state
