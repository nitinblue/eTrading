import logging
from trading_bot.domain.state import TradingState

logger = logging.getLogger(__name__)


def risk_dude(state: TradingState):
    logger.info("⚠️ RiskDude: Assessing portfolio risk")

    total_delta = sum(p.delta or 0 for p in state.positions)
    total_pnl = sum(p.unrealized_pnl for p in state.positions)

    state.portfolio_metrics = {
        "total_delta": total_delta,
        "unrealized_pnl": total_pnl
    }

    state.risk_report = {
        "delta_risk": "HIGH" if abs(total_delta) > 500 else "OK",
        "pnl_status": "LOSS" if total_pnl < 0 else "PROFIT"
    }

    print("\n=== RISK REPORT ===")
    for k, v in state.risk_report.items():
        print(f"{k}: {v}")

    state.messages.append("Risk evaluated")
    return state
