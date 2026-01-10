import logging
from typing import Dict
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def adjustment_dude(state: Dict) -> Dict:
    logger.info("AdjustmentDude: Evaluating adjustment opportunities...")

    portfolio = state.get("portfolio", {})
    risk = state.get("risk", {})
    trades = portfolio.get("trades", [])

    suggestions = []

    for t in trades:
        if t["strategy"] == "IRON_CONDOR" and t["dte"] < 14:
            suggestions.append({
                "trade_id": t["id"],
                "action": "ROLL_OUT",
                "reason": "LOW_DTE"
            })

        if t["risk_type"] == "UNDEFINED" and t["delta"] < -30:
            suggestions.append({
                "trade_id": t["id"],
                "action": "ROLL_DOWN_OUT",
                "reason": "DELTA_BREACH"
            })

    state["adjustments"] = suggestions
    return state
