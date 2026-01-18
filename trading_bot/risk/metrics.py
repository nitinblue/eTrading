# risk/metrics.py
from collections import defaultdict

def aggregate_risk(trades):
    risk = defaultdict(float)
    for t in trades:
        risk[t.risk_type] += t.max_loss
    return dict(risk)

def net_delta(trades):
    return sum(t.delta for t in trades)

def risk_by_symbol(trades):
    agg = defaultdict(float)
    for t in trades:
        agg[t.symbol] += t.max_loss
    return dict(agg)
