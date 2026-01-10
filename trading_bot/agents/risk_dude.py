import logging
from typing import Dict
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def risk_dude(state: Dict) -> Dict:
    logger.info("RiskDude: Evaluating real portfolio risk...")

    config = state["config"]
    portfolio = state.get("portfolio", {})
    trades = portfolio.get("trades", [])

    defined_risk = 0.0
    undefined_risk = 0.0
    net_delta = 0.0

    for t in trades:
        if t["risk_type"] == "DEFINED":
            defined_risk += t["max_loss"]
        else:
            undefined_risk += t["max_loss"]
        net_delta += t["delta"]

    violations = []
    warnings = []

    # Allocation checks
    if defined_risk > config["portfolio"]["defined_max_risk"]:
        violations.append("DEFINED_RISK_EXCEEDED")

    if undefined_risk > config["portfolio"]["undefined_max_risk"]:
        violations.append("UNDEFINED_RISK_EXCEEDED")

    # Delta drift (warning, not violation)
    if abs(net_delta) > config["risk"]["max_net_delta"]:
        warnings.append("NET_DELTA_HIGH")

    state["risk"] = {
        "metrics": {
            "defined_risk": defined_risk,
            "undefined_risk": undefined_risk,
            "net_delta": net_delta,
        },
        "violations": violations,
        "warnings": warnings,
        "approved": len(violations) == 0
    }

    state["output"] += f"\nRisk: D={defined_risk:.0f}, U={undefined_risk:.0f}, Δ={net_delta:.0f}"

    return state
