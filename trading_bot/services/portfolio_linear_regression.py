import numpy as np
from sklearn.linear_model import LinearRegression

def ensure_float(val):
    """Converts possible list-wrapped values to single floats for 2026 analysis."""
    if isinstance(val, (list, np.ndarray)):
        return float(val[0])
    return float(val)

def calculate_enhanced_hedge(portfolio_greeks, target_config, candidate_trades, total_capital, current_regime):
    """Regression-based hedge weights with target_config gap calculation."""
    # 1. Prepare X: Matrix of Candidate Greeks [Delta, Theta, Vega]
    X = np.array([[t['delta'] * 100, t['theta'] * 100, t['vega'] * 100] for t in candidate_trades])
    
    # 2. Prepare y: The Greek Gaps (fixes 'int' and 'list' subtraction error)
    y = np.array([
        ensure_float(target_config['delta']) - ensure_float(portfolio_greeks['delta']),
        ensure_float(target_config['theta']) - ensure_float(portfolio_greeks['theta']),
        ensure_float(target_config['vega']) - ensure_float(portfolio_greeks['vega'])
    ])
    
    # 3. Regression Logic
    model = LinearRegression(fit_intercept=False)
    model.fit(X.T, y)
    weights = model.coef_
    
    results = []
    for i, trade in enumerate(candidate_trades):
        qty = round(weights[i], 2)
        if qty == 0: continue
        
        action_desc = f"BUY {abs(qty)}" if qty > 0 else f"SELL {abs(qty)}"
        est_risk = trade.get('max_loss_per_unit', -500) * abs(qty)
        
        results.append({
            "Action": action_desc,
            "Asset": trade['name'],
            "Est Risk [STATIC]": f"${est_risk:,.2f}",
            "Risk Impact %": f"{(abs(est_risk)/total_capital)*100:.2f}%",
            "Commentary": f"[HARDCODED] {trade.get('commentary', '')}"
        })
    return results

def scan_and_net_portfolio(trades):
    """Scans for physical leg offsets across strategies."""
    net_map = {}
    for leg in trades:
        key = (leg['ticker'], leg.get('expiration', 'N/A'), leg['strike'], leg['option_type'])
        qty = 1 if leg['position'].lower() == 'long' else -1
        net_map[key] = net_map.get(key, 0) + qty

    report = [f"FULL NET: {k} - FLAT" for k, v in net_map.items() if v == 0]
    return report
