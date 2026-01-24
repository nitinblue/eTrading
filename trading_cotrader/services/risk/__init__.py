"""
Risk Management Module

Provides:
- Value at Risk (VaR) calculations
- Portfolio-level risk assessment
- Correlation analysis
- Concentration risk checks
- Margin requirement estimation
- Risk limit enforcement

Usage:
    from services.risk import PortfolioRiskAnalyzer, VaRCalculator
    
    risk_analyzer = PortfolioRiskAnalyzer(session)
    portfolio_risk = risk_analyzer.analyze(portfolio, positions)
    
    if portfolio_risk.passes_limits():
        print("Risk within acceptable bounds")
"""

from services.risk.var_calculator import VaRCalculator, VaRResult, VaRMethod
from services.risk.portfolio_risk import PortfolioRiskAnalyzer, PortfolioRisk, RiskImpact
from services.risk.correlation import CorrelationAnalyzer, CorrelatedPair
from services.risk.concentration import ConcentrationChecker, ConcentrationResult
from services.risk.margin import MarginEstimator, MarginRequirement
from services.risk.limits import RiskLimits, LimitBreach, LimitCheckResult

__all__ = [
    'VaRCalculator',
    'VaRResult',
    'VaRMethod',
    'PortfolioRiskAnalyzer',
    'PortfolioRisk',
    'RiskImpact',
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
