import logging
from trading_bot.domain.models import RiskType
from trading_bot.agents.trader_dude import trader_dude

logger = logging.getLogger(__name__)


def portfolio_dude(state: dict):
    """
    Portfolio Manager Agent.
    Decides if trading is allowed and delegates to traders.
    """

    broker = state["broker"]
    config = state["config"]

    state.setdefault("risk_usage", {})

    # hardcoded for now, revisit later
    defined_pct = 0.8 #config["risk"]["defined_capital_pct"]
    undefined_pct = 0.2 #config["risk"]["undefined_capital_pct"]

    for account_id in broker.get_accounts():

        net_liq = broker.get_net_liquidation(account_id)
        buying_power = broker.get_buying_power(account_id)

        defined_limit = net_liq * defined_pct
        undefined_limit = net_liq * undefined_pct

        used_defined = state["risk_usage"].get(
            (account_id, RiskType.DEFINED), 0
        )
        used_undefined = state["risk_usage"].get(
            (account_id, RiskType.UNDEFINED), 0
        )

        defined_left = max(0, defined_limit - used_defined)
        undefined_left = max(0, undefined_limit - used_undefined)

        logger.info(
            f"[Portfolio] {account_id} | "
            f"DefinedLeft={defined_left:.2f} | "
            f"UndefinedLeft={undefined_left:.2f}"
        )

        if defined_left > 0:
            trader_dude(
                state,
                broker,
                account_id,
                RiskType.DEFINED,
                defined_left,
            )

        if undefined_left > 0:
            trader_dude(
                state,
                broker,
                account_id,
                RiskType.UNDEFINED,
                undefined_left,
            )

    return state


print("✅ portfolio_dude module loaded")
