# risk/validators.py
def check_allocation(agg_risk, portfolio_cfg):
    violations = []

    if agg_risk.get("DEFINED", 0) > portfolio_cfg["PORTFOLIO"]["ALLOCATION"]["DEFINED_RISK"]["MAX_RISK_DOLLARS"]:
        violations.append("DEFINED_RISK_EXCEEDED")

    if agg_risk.get("UNDEFINED", 0) > portfolio_cfg["PORTFOLIO"]["ALLOCATION"]["UNDEFINED_RISK"]["MAX_RISK_DOLLARS"]:
        violations.append("UNDEFINED_RISK_EXCEEDED")

    return violations


def check_single_symbol(risk_by_sym, portfolio_cfg):
    max_risk = portfolio_cfg["PORTFOLIO_EXPOSURE"]["MAX_SINGLE_UNDERLYING_RISK_PCT"] / 100
    cap = portfolio_cfg["PORTFOLIO"]["TOTAL_CAPITAL"]

    return [
        f"SYMBOL_RISK_EXCEEDED:{sym}"
        for sym, risk in risk_by_sym.items()
        if risk > cap * max_risk
    ]
