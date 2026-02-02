"""
Portfolio Risk Analyzer

Provides comprehensive portfolio-level risk assessment:
- Aggregated risk metrics
- Risk impact analysis for proposed trades
- Stress testing
- Risk object that can be queried

This is the main entry point for risk analysis.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from enum import Enum
import logging

from services.risk.var_calculator import VaRCalculator, VaRResult

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk classification levels"""
    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class GreekRisk:
    """Greeks-based risk metrics"""
    # Dollar values
    delta_dollars: Decimal = Decimal('0')  # $ change per 1% move
    gamma_dollars: Decimal = Decimal('0')  # Acceleration
    theta_daily: Decimal = Decimal('0')    # Daily decay
    vega_dollars: Decimal = Decimal('0')   # $ change per 1% IV change
    
    # Normalized values
    beta_weighted_delta: Decimal = Decimal('0')  # SPY-normalized delta
    
    # Scenarios
    up_1_percent_pnl: Decimal = Decimal('0')
    down_1_percent_pnl: Decimal = Decimal('0')
    up_5_percent_pnl: Decimal = Decimal('0')
    down_5_percent_pnl: Decimal = Decimal('0')


@dataclass
class ConcentrationRisk:
    """Concentration analysis"""
    by_underlying: Dict[str, float] = field(default_factory=dict)
    by_strategy: Dict[str, float] = field(default_factory=dict)
    by_direction: Dict[str, float] = field(default_factory=dict)  # long/short/neutral
    by_expiration: Dict[str, float] = field(default_factory=dict)
    
    max_single_underlying: float = 0.0
    max_single_strategy: float = 0.0
    
    diversification_score: float = 0.0  # 0-1, higher is better


@dataclass
class LimitStatus:
    """Status of risk limits"""
    limit_name: str
    current_value: Decimal
    limit_value: Decimal
    utilization: float  # current/limit as %
    breached: bool
    warning: bool  # > 80% utilization


@dataclass
class PortfolioRisk:
    """
    Complete portfolio risk assessment.
    
    This is an OBJECT that:
    - Updates when portfolio changes
    - Can be queried for specific metrics
    - Triggers alerts when limits breached
    - Can be displayed in UI grid
    """
    # Identity
    portfolio_id: str = ""
    assessment_time: datetime = field(default_factory=datetime.utcnow)
    
    # Portfolio context
    portfolio_value: Decimal = Decimal('0')
    cash_balance: Decimal = Decimal('0')
    buying_power: Decimal = Decimal('0')
    
    # VaR metrics
    var_1d_95: Optional[VaRResult] = None
    var_1d_99: Optional[VaRResult] = None
    var_5d_95: Optional[VaRResult] = None
    
    # Greeks risk
    greeks: GreekRisk = field(default_factory=GreekRisk)
    
    # Concentration
    concentration: ConcentrationRisk = field(default_factory=ConcentrationRisk)
    
    # Max loss scenarios
    max_loss_all_positions: Decimal = Decimal('0')
    max_loss_realistic: Decimal = Decimal('0')  # Based on historical moves
    
    # Correlation info
    correlation_risk_score: float = 0.0  # 0-1, higher = more correlated
    highly_correlated_pairs: List[Tuple[str, str, float]] = field(default_factory=list)
    
    # Margin
    maintenance_margin: Decimal = Decimal('0')
    margin_utilization: float = 0.0
    
    # Limit status
    limit_checks: List[LimitStatus] = field(default_factory=list)
    
    # Overall assessment
    risk_level: RiskLevel = RiskLevel.MODERATE
    warnings: List[str] = field(default_factory=list)
    
    def passes_limits(self) -> Tuple[bool, List[str]]:
        """Check if all risk limits are satisfied."""
        breaches = [lc for lc in self.limit_checks if lc.breached]
        return len(breaches) == 0, [lc.limit_name for lc in breaches]
    
    def get_limit_utilization(self, limit_name: str) -> Optional[float]:
        """Get utilization for a specific limit."""
        for lc in self.limit_checks:
            if lc.limit_name == limit_name:
                return lc.utilization
        return None
    
    def to_summary_dict(self) -> Dict:
        """Convert to summary dictionary for display."""
        return {
            'portfolio_value': float(self.portfolio_value),
            'var_1d_95': float(self.var_1d_95.var_amount) if self.var_1d_95 else None,
            'var_1d_95_pct': float(self.var_1d_95.var_percent) if self.var_1d_95 else None,
            'delta_dollars': float(self.greeks.delta_dollars),
            'theta_daily': float(self.greeks.theta_daily),
            'max_concentration': self.concentration.max_single_underlying,
            'risk_level': self.risk_level.value,
            'limits_ok': self.passes_limits()[0],
            'warnings': self.warnings
        }


@dataclass
class RiskImpact:
    """
    Impact of a proposed trade on portfolio risk.
    
    This is what you see BEFORE taking a trade.
    """
    # Trade info
    trade_description: str = ""
    
    # VaR impact
    var_before: Decimal = Decimal('0')
    var_after: Decimal = Decimal('0')
    var_change: Decimal = Decimal('0')
    var_change_percent: float = 0.0
    
    # Greeks impact
    delta_change: Decimal = Decimal('0')
    theta_change: Decimal = Decimal('0')
    vega_change: Decimal = Decimal('0')
    
    # Concentration impact
    concentration_before: Dict[str, float] = field(default_factory=dict)
    concentration_after: Dict[str, float] = field(default_factory=dict)
    new_concentration_warnings: List[str] = field(default_factory=list)
    
    # Correlation impact
    correlation_with_existing: Dict[str, float] = field(default_factory=dict)
    adds_correlated_risk: bool = False
    
    # Margin impact
    margin_required: Decimal = Decimal('0')
    buying_power_after: Decimal = Decimal('0')
    
    # Max loss
    trade_max_loss: Decimal = Decimal('0')
    portfolio_max_loss_after: Decimal = Decimal('0')
    
    # Decision support
    passes_risk_checks: bool = True
    warnings: List[str] = field(default_factory=list)
    recommendation: str = ""
    
    def should_proceed(self) -> Tuple[bool, str]:
        """Recommendation on whether to proceed with trade."""
        if not self.passes_risk_checks:
            return False, f"Risk checks failed: {', '.join(self.warnings)}"
        if len(self.warnings) > 2:
            return False, f"Multiple warnings: {', '.join(self.warnings)}"
        if self.warnings:
            return True, f"Proceed with caution: {', '.join(self.warnings)}"
        return True, "Trade passes all risk checks"


@dataclass
class StressScenario:
    """Definition of a stress scenario"""
    name: str
    description: str
    
    # Market shocks
    equity_shock_percent: float = 0.0      # e.g., -20 for 20% drop
    vix_shock_absolute: float = 0.0        # e.g., +30 for VIX to 30+
    rate_shock_bps: float = 0.0            # e.g., +100 for 1% rate rise
    
    # Historical reference
    historical_date: Optional[str] = None  # e.g., "2008-10-15"


@dataclass
class StressResult:
    """Result of stress test"""
    scenario: StressScenario
    portfolio_pnl: Decimal
    pnl_percent: Decimal
    positions_impacted: List[str]
    survives: bool  # Does portfolio survive this scenario?


# Standard stress scenarios
STRESS_SCENARIOS = [
    StressScenario(
        name="Market Crash",
        description="2008-style crash: -20% equities, VIX to 80",
        equity_shock_percent=-20.0,
        vix_shock_absolute=80.0,
        historical_date="2008-10-15"
    ),
    StressScenario(
        name="COVID Crash",
        description="COVID-19 style: -30% in 4 weeks, VIX to 82",
        equity_shock_percent=-30.0,
        vix_shock_absolute=82.0,
        historical_date="2020-03-23"
    ),
    StressScenario(
        name="Vol Spike",
        description="Sudden volatility spike: -5% equities, VIX to 40",
        equity_shock_percent=-5.0,
        vix_shock_absolute=40.0
    ),
    StressScenario(
        name="Grinding Bear",
        description="Slow decline: -10% equities, VIX to 25",
        equity_shock_percent=-10.0,
        vix_shock_absolute=25.0
    ),
    StressScenario(
        name="Flash Crash",
        description="Intraday crash: -10% then recovery",
        equity_shock_percent=-10.0,
        vix_shock_absolute=35.0,
        historical_date="2010-05-06"
    ),
]


class PortfolioRiskAnalyzer:
    """
    Main entry point for portfolio risk analysis.
    
    Usage:
        analyzer = PortfolioRiskAnalyzer(session)
        
        # Get current risk
        risk = analyzer.analyze(portfolio, positions)
        
        # Check if a trade is acceptable
        impact = analyzer.impact_analysis(risk, proposed_trade)
        if impact.should_proceed()[0]:
            # Trade is acceptable
            pass
        
        # Run stress tests
        results = analyzer.stress_test(positions, STRESS_SCENARIOS)
    """
    
    def __init__(self, session=None, market_data=None, risk_limits=None):
        """
        Initialize analyzer.
        
        Args:
            session: Database session (optional)
            market_data: Market data provider (optional)
            risk_limits: Risk limits configuration (optional)
        """
        self.session = session
        self.market_data = market_data
        self.risk_limits = risk_limits
        
        self.var_calculator = VaRCalculator(market_data)
    
    def analyze(
        self,
        portfolio,  # Portfolio
        positions: List,  # List[Position]
    ) -> PortfolioRisk:
        """
        Perform comprehensive portfolio risk analysis.
        
        Args:
            portfolio: Portfolio object
            positions: List of current positions
            
        Returns:
            PortfolioRisk object with all metrics
        """
        logger.info(f"Analyzing risk for portfolio {getattr(portfolio, 'id', 'unknown')}")
        
        risk = PortfolioRisk(
            portfolio_id=getattr(portfolio, 'id', ''),
            portfolio_value=getattr(portfolio, 'total_equity', Decimal('0')),
            cash_balance=getattr(portfolio, 'cash_balance', Decimal('0')),
            buying_power=getattr(portfolio, 'buying_power', Decimal('0'))
        )
        
        # Calculate VaR at multiple confidence levels
        risk.var_1d_95 = self.var_calculator.calculate_parametric_var(
            positions, risk.portfolio_value, confidence=0.95, horizon_days=1
        )
        risk.var_1d_99 = self.var_calculator.calculate_parametric_var(
            positions, risk.portfolio_value, confidence=0.99, horizon_days=1
        )
        risk.var_5d_95 = self.var_calculator.calculate_parametric_var(
            positions, risk.portfolio_value, confidence=0.95, horizon_days=5
        )
        
        # Calculate Greeks risk
        risk.greeks = self._calculate_greek_risk(positions, risk.portfolio_value)
        
        # Analyze concentration
        risk.concentration = self._analyze_concentration(positions, risk.portfolio_value)
        
        # Calculate max loss scenarios
        risk.max_loss_all_positions = self._calculate_max_loss(positions)
        
        # Analyze correlation
        risk.correlation_risk_score, risk.highly_correlated_pairs = self._analyze_correlation(positions)
        
        # Check limits
        if self.risk_limits:
            risk.limit_checks = self.risk_limits.check_all(risk)
        
        # Determine overall risk level
        risk.risk_level = self._classify_risk_level(risk)
        
        # Generate warnings
        risk.warnings = self._generate_warnings(risk)
        
        return risk
    
    def impact_analysis(
        self,
        current_risk: PortfolioRisk,
        proposed_trade,  # Trade
    ) -> RiskImpact:
        """
        Analyze how a proposed trade affects portfolio risk.
        
        This is CRITICAL for pre-trade risk management.
        
        Args:
            current_risk: Current portfolio risk
            proposed_trade: Trade being considered
            
        Returns:
            RiskImpact showing the effect of the trade
        """
        logger.info(f"Analyzing risk impact of proposed trade")
        
        impact = RiskImpact(
            trade_description=str(proposed_trade),
            var_before=current_risk.var_1d_95.var_amount if current_risk.var_1d_95 else Decimal('0')
        )
        
        # TODO: Full implementation
        # 1. Convert trade to positions
        # 2. Add to existing positions
        # 3. Recalculate all risk metrics
        # 4. Compare before/after
        # 5. Check if still within limits
        
        return impact
    
    def stress_test(
        self,
        positions: List,
        scenarios: List[StressScenario] = None
    ) -> List[StressResult]:
        """
        Run stress scenarios against the portfolio.
        
        Args:
            positions: Current positions
            scenarios: List of scenarios (defaults to standard scenarios)
            
        Returns:
            List of StressResult for each scenario
        """
        if scenarios is None:
            scenarios = STRESS_SCENARIOS
        
        results = []
        for scenario in scenarios:
            result = self._run_stress_scenario(positions, scenario)
            results.append(result)
        
        return results
    
    def _calculate_greek_risk(self, positions: List, portfolio_value: Decimal) -> GreekRisk:
        """Calculate aggregate Greeks-based risk."""
        greek_risk = GreekRisk()
        
        for pos in positions:
            greeks = getattr(pos, 'greeks', None)
            if greeks:
                # Aggregate Greeks (already position-level from broker)
                greek_risk.delta_dollars += getattr(greeks, 'delta', Decimal('0'))
                greek_risk.theta_daily += getattr(greeks, 'theta', Decimal('0'))
                greek_risk.vega_dollars += getattr(greeks, 'vega', Decimal('0'))
        
        # Calculate P&L scenarios
        if portfolio_value > 0:
            greek_risk.up_1_percent_pnl = greek_risk.delta_dollars * Decimal('0.01') * portfolio_value
            greek_risk.down_1_percent_pnl = -greek_risk.delta_dollars * Decimal('0.01') * portfolio_value
        
        return greek_risk
    
    def _analyze_concentration(self, positions: List, portfolio_value: Decimal) -> ConcentrationRisk:
        """Analyze position concentration."""
        concentration = ConcentrationRisk()
        
        if portfolio_value == 0:
            return concentration
        
        # Group by underlying
        by_underlying = {}
        for pos in positions:
            ticker = getattr(getattr(pos, 'symbol', None), 'ticker', 'UNKNOWN')
            value = abs(float(getattr(pos, 'market_value', 0)))
            by_underlying[ticker] = by_underlying.get(ticker, 0) + value
        
        # Calculate percentages
        total = float(portfolio_value)
        concentration.by_underlying = {k: v/total for k, v in by_underlying.items()}
        concentration.max_single_underlying = max(concentration.by_underlying.values()) if concentration.by_underlying else 0
        
        # Calculate diversification score (inverse of concentration)
        if concentration.by_underlying:
            # Herfindahl index
            hhi = sum(v**2 for v in concentration.by_underlying.values())
            concentration.diversification_score = 1 - hhi  # Higher is better
        
        return concentration
    
    def _calculate_max_loss(self, positions: List) -> Decimal:
        """Calculate maximum possible loss."""
        max_loss = Decimal('0')
        
        for pos in positions:
            # For options, max loss depends on position type
            # For now, use total cost as proxy
            total_cost = getattr(pos, 'total_cost', Decimal('0'))
            max_loss += abs(total_cost)
        
        return max_loss
    
    def _analyze_correlation(self, positions: List) -> Tuple[float, List[Tuple[str, str, float]]]:
        """Analyze correlation between positions."""
        # TODO: Implement with actual correlation calculation
        return 0.0, []
    
    def _classify_risk_level(self, risk: PortfolioRisk) -> RiskLevel:
        """Classify overall risk level."""
        # Simple classification based on VaR and concentration
        
        if risk.var_1d_95 and risk.portfolio_value > 0:
            var_pct = float(risk.var_1d_95.var_percent)
            
            if var_pct > 10:
                return RiskLevel.CRITICAL
            elif var_pct > 5:
                return RiskLevel.HIGH
            elif var_pct > 3:
                return RiskLevel.ELEVATED
            elif var_pct > 1.5:
                return RiskLevel.MODERATE
        
        if risk.concentration.max_single_underlying > 0.3:
            return RiskLevel.ELEVATED
        
        return RiskLevel.LOW
    
    def _generate_warnings(self, risk: PortfolioRisk) -> List[str]:
        """Generate risk warnings."""
        warnings = []
        
        if risk.concentration.max_single_underlying > 0.25:
            warnings.append(f"High concentration: {risk.concentration.max_single_underlying*100:.0f}% in single underlying")
        
        if risk.margin_utilization > 0.8:
            warnings.append(f"High margin utilization: {risk.margin_utilization*100:.0f}%")
        
        if risk.greeks.theta_daily < Decimal('-100'):
            warnings.append(f"High theta decay: ${risk.greeks.theta_daily}/day")
        
        # Check limit warnings
        for limit in risk.limit_checks:
            if limit.warning and not limit.breached:
                warnings.append(f"Approaching {limit.limit_name} limit ({limit.utilization*100:.0f}%)")
        
        return warnings
    
    def _run_stress_scenario(self, positions: List, scenario: StressScenario) -> StressResult:
        """Run a single stress scenario."""
        # TODO: Full implementation
        return StressResult(
            scenario=scenario,
            portfolio_pnl=Decimal('0'),
            pnl_percent=Decimal('0'),
            positions_impacted=[],
            survives=True
        )


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example usage
    analyzer = PortfolioRiskAnalyzer()
    
    # Would use actual portfolio and positions
    # risk = analyzer.analyze(portfolio, positions)
    # print(risk.to_summary_dict())
    
    print("Portfolio Risk Analyzer ready")
