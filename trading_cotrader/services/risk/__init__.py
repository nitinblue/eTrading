"""
Risk Management Module

VaR calculations and PortfolioRiskAnalyzer moved to playground/archived_math/.
Remaining: correlation, concentration, margin, limits.
"""

from trading_cotrader.services.risk.correlation import CorrelationAnalyzer, CorrelatedPair
from trading_cotrader.services.risk.concentration import ConcentrationChecker, ConcentrationResult
from trading_cotrader.services.risk.margin import MarginEstimator, MarginRequirement
from trading_cotrader.services.risk.limits import RiskLimits, LimitBreach, LimitCheckResult

__all__ = [
    'CorrelationAnalyzer',
    'CorrelatedPair',
    'ConcentrationChecker',
    'ConcentrationResult',
    'MarginEstimator',
    'MarginRequirement',
    'RiskLimits',
    'LimitBreach',
    'LimitCheckResult',
]
