from trading_bot.domain.models import TradeIdea, TradeStatus
from trading_bot.engines.risk_engine import validate_trade
from trading_bot.engines.what_if_engine import simulate_trade
from trading_bot.engines.trade_ranking import rank_trades
import logging

logger = logging.getLogger(__name__)


def trader_dude(state, broker, account_id, risk_type, available_risk):
    """
    Trader decides WHAT to trade.
    """

    logger.info(
        f"[Trader] Looking for {risk_type.value} risk trades "
        f"(capacity={available_risk:.2f})"
    )

    # ---- MOCKED TRADE GENERATION ----
    trade_ideas = [
        TradeIdea(
            symbol="SPY",
            strategy="IRON_CONDOR",
            risk_type=risk_type,
            max_loss=1500,
            prob_profit=0.68,
            metadata={}
        )
    ]

    validated = []

    for trade in trade_ideas:
        ok, reason = validate_trade(trade, available_risk)

        if not ok:
            trade.status = TradeStatus.REJECTED
            logger.info(f"[Trader] Rejected {trade.strategy}: {reason}")
            continue

        trade.status = TradeStatus.VALIDATED
        trade.metadata["what_if"] = simulate_trade(trade, state)
        validated.append(trade)

    if not validated:
        return

    ranked = rank_trades(validated)
    best = ranked[0]

    logger.info(f"[Trader] SELECTED TRADE → {best}")

    # 🔴 NO EXECUTION YET
    logger.info("[Trader] WOULD EXECUTE (paper/live later)")
