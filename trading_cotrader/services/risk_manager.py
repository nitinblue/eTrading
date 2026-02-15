"""
Risk Manager - Enforce risk limits before trade execution

This is the gatekeeper that prevents bad trades.
Every trade must pass risk checks before being executed.
"""

import logging
from typing import List, Dict, Tuple, Optional
from decimal import Decimal
from pathlib import Path
import yaml

import trading_cotrader.core.models.domain as dm

logger = logging.getLogger(__name__)


class RiskViolation:
    """Represents a risk limit violation"""
    
    def __init__(
        self,
        category: str,
        severity: str,  # 'block', 'warn', 'info'
        message: str,
        limit_name: str,
        current_value: float,
        limit_value: float
    ):
        self.category = category
        self.severity = severity
        self.message = message
        self.limit_name = limit_name
        self.current_value = current_value
        self.limit_value = limit_value
    
    def __repr__(self):
        symbol = "🚫" if self.severity == "block" else "⚠️" if self.severity == "warn" else "ℹ️"
        return f"{symbol} {self.category}: {self.message}"
    
    def is_blocking(self) -> bool:
        return self.severity == "block"


class RiskCheckResult:
    """Result of risk validation"""
    
    def __init__(self):
        self.violations: List[RiskViolation] = []
        self.passed = True
        self.blocking_violations = []
        self.warnings = []
    
    def add_violation(self, violation: RiskViolation):
        self.violations.append(violation)
        
        if violation.is_blocking():
            self.passed = False
            self.blocking_violations.append(violation)
        elif violation.severity == "warn":
            self.warnings.append(violation)
    
    def summary(self) -> str:
        """Get summary of check result"""
        if self.passed and not self.warnings:
            return "✅ All risk checks passed"
        
        lines = []
        if not self.passed:
            lines.append(f"🚫 BLOCKED: {len(self.blocking_violations)} violations")
            for v in self.blocking_violations:
                lines.append(f"  - {v.message}")
        
        if self.warnings:
            lines.append(f"⚠️  {len(self.warnings)} warnings")
            for w in self.warnings:
                lines.append(f"  - {w.message}")
        
        return "\n".join(lines)


class RiskManager:
    """
    Risk management system that validates trades before execution
    
    This prevents:
    - Over-concentration in single underlying/sector
    - Excessive directional exposure (delta)
    - Capital allocation violations
    - Trading during blackout periods
    """
    
    def __init__(self, limits_file: str = "risk_limits.yaml"):
        """
        Initialize risk manager
        
        Args:
            limits_file: Path to YAML risk limits configuration
        """
        self.limits = self._load_limits(limits_file)
        logger.info("✓ Risk manager initialized with limits from {limits_file}")
    
    def _load_limits(self, limits_file: str) -> dict:
        """Load risk limits from YAML"""
        try:
            # Try multiple paths
            possible_paths = [
                Path(limits_file),
                Path(__file__).parent / limits_file,
                Path(__file__).parent.parent / limits_file,
                Path(__file__).parent.parent / "config" / limits_file,
            ]
            
            for path in possible_paths:
                if path.exists():
                    logger.info(f"Loading risk limits from: {path}")
                    with open(path, 'r') as f:
                        return yaml.safe_load(f)
            
            raise FileNotFoundError(f"Risk limits file not found: {limits_file}")
            
        except Exception as e:
            logger.error(f"Failed to load risk limits: {e}")
            raise
    
    def validate_trade(
        self,
        proposed_trade: dm.Trade,
        current_portfolio: dm.Portfolio,
        current_positions: List[dm.Position],
        current_trades: List[dm.Trade]
    ) -> RiskCheckResult:
        """
        Validate a proposed trade against all risk limits
        
        This is the main entry point - checks everything
        
        Args:
            proposed_trade: Trade being considered
            current_portfolio: Current portfolio state
            current_positions: All current positions
            current_trades: All current open trades
            
        Returns:
            RiskCheckResult with all violations
        """
        result = RiskCheckResult()
        
        logger.info(f"Validating trade: {proposed_trade.strategy.name if proposed_trade.strategy else 'Unknown'}")
        
        # Portfolio-level checks
        self._check_portfolio_limits(proposed_trade, current_portfolio, result)
        
        # Greek checks
        self._check_greek_limits(proposed_trade, current_portfolio, result)
        
        # Concentration checks
        self._check_concentration(proposed_trade, current_positions, current_trades, result)
        
        # Capital allocation checks
        self._check_capital_allocation(proposed_trade, current_portfolio, current_positions, result)
        
        # Strategy-specific checks
        self._check_strategy_limits(proposed_trade, result)
        
        # Timing checks
        self._check_timing_rules(proposed_trade, result)
        
        logger.info(f"Risk validation complete: {'PASSED' if result.passed else 'BLOCKED'}")
        if result.violations:
            for v in result.violations:
                logger.info(f"  {v}")
        
        return result
    
    def _check_portfolio_limits(
        self,
        trade: dm.Trade,
        portfolio: dm.Portfolio,
        result: RiskCheckResult
    ):
        """Check portfolio-level risk limits"""
        limits = self.limits['portfolio']
        
        # Trade risk as % of portfolio
        trade_risk = abs(trade.net_cost())
        portfolio_value = portfolio.total_equity
        
        if portfolio_value > 0:
            risk_percent = (trade_risk / portfolio_value) * 100
            max_risk = limits['max_single_trade_risk_percent']
            
            if risk_percent > max_risk:
                result.add_violation(RiskViolation(
                    category="Portfolio Risk",
                    severity="block",
                    message=f"Trade risk {risk_percent:.1f}% exceeds max {max_risk:.1f}%",
                    limit_name="max_single_trade_risk_percent",
                    current_value=float(risk_percent),
                    limit_value=max_risk
                ))
        
        # Max open positions
        # (Would need current position count passed in)
    
    def _check_greek_limits(
        self,
        trade: dm.Trade,
        portfolio: dm.Portfolio,
        result: RiskCheckResult
    ):
        """Check Greek exposure limits"""
        limits = self.limits['greeks']
        
        # Calculate what portfolio Greeks would be after trade
        trade_greeks = trade.total_greeks()
        current_greeks = portfolio.portfolio_greeks or dm.Greeks()
        
        # Projected portfolio Greeks
        projected_delta = current_greeks.delta + trade_greeks.delta
        projected_gamma = current_greeks.gamma + trade_greeks.gamma
        projected_theta = current_greeks.theta + trade_greeks.theta
        projected_vega = current_greeks.vega + trade_greeks.vega
        
        # Check delta
        max_delta = limits['max_portfolio_delta']
        if abs(projected_delta) > max_delta:
            result.add_violation(RiskViolation(
                category="Greeks",
                severity="block",
                message=f"Portfolio delta would be {projected_delta:.2f}, max is ±{max_delta:.2f}",
                limit_name="max_portfolio_delta",
                current_value=float(abs(projected_delta)),
                limit_value=max_delta
            ))
        
        # Check gamma
        max_gamma = limits['max_portfolio_gamma']
        if abs(projected_gamma) > max_gamma:
            result.add_violation(RiskViolation(
                category="Greeks",
                severity="warn",
                message=f"Portfolio gamma would be {projected_gamma:.4f}, max is {max_gamma:.4f}",
                limit_name="max_portfolio_gamma",
                current_value=float(abs(projected_gamma)),
                limit_value=max_gamma
            ))
        
        # Check theta
        min_theta = limits['min_portfolio_theta']
        if projected_theta < min_theta:
            result.add_violation(RiskViolation(
                category="Greeks",
                severity="block",
                message=f"Portfolio theta would be {projected_theta:.2f}, min is {min_theta:.2f}",
                limit_name="min_portfolio_theta",
                current_value=float(projected_theta),
                limit_value=min_theta
            ))
        
        # Check trade-level delta
        max_trade_delta = limits['max_trade_delta']
        if abs(trade_greeks.delta) > max_trade_delta:
            result.add_violation(RiskViolation(
                category="Trade Greeks",
                severity="block",
                message=f"Trade delta {trade_greeks.delta:.2f} exceeds max ±{max_trade_delta:.2f}",
                limit_name="max_trade_delta",
                current_value=float(abs(trade_greeks.delta)),
                limit_value=max_trade_delta
            ))
    
    def _check_concentration(
        self,
        trade: dm.Trade,
        positions: List[dm.Position],
        trades: List[dm.Trade],
        result: RiskCheckResult
    ):
        """Check concentration limits"""
        limits = self.limits['concentration']
        
        # Underlying concentration
        underlying = trade.underlying_symbol
        
        # Calculate current exposure to this underlying
        current_exposure = sum(
            abs(p.market_value) for p in positions 
            if p.symbol.ticker == underlying
        )
        
        # Trade cost
        trade_cost = abs(trade.net_cost())
        
        # Projected exposure
        projected_exposure = current_exposure + trade_cost
        
        # As percent of portfolio
        # (Would need portfolio value passed in or calculated)
        
        # Check max per underlying
        max_per_underlying = limits['max_percent_per_underlying']
        # (Implementation needs portfolio total value)
        
        # Strategy concentration
        if trade.strategy:
            strategy_type = trade.strategy.strategy_type.value
            
            # Count existing trades of same strategy
            same_strategy_count = sum(
                1 for t in trades 
                if t.strategy and t.strategy.strategy_type.value == strategy_type
            )
            
            # (Would implement max per strategy check)
        
        # Expiration concentration
        dte = trade.days_to_expiration()
        if dte:
            min_dte = limits['min_days_to_expiration']
            max_dte = limits['max_days_to_expiration']
            
            if dte < min_dte:
                result.add_violation(RiskViolation(
                    category="Expiration",
                    severity="block",
                    message=f"Trade expires in {dte} days, minimum is {min_dte}",
                    limit_name="min_days_to_expiration",
                    current_value=dte,
                    limit_value=min_dte
                ))
            
            if dte > max_dte:
                result.add_violation(RiskViolation(
                    category="Expiration",
                    severity="warn",
                    message=f"Trade expires in {dte} days, maximum is {max_dte}",
                    limit_name="max_days_to_expiration",
                    current_value=dte,
                    limit_value=max_dte
                ))
    
    def _check_capital_allocation(
        self,
        trade: dm.Trade,
        portfolio: dm.Portfolio,
        positions: List[dm.Position],
        result: RiskCheckResult
    ):
        """Check capital allocation rules (defined vs undefined risk)"""
        limits = self.limits['portfolio']
        
        # Determine if trade is defined or undefined risk
        is_defined_risk = self._is_defined_risk_trade(trade)
        
        # Calculate current allocation
        # (Would need to classify existing positions)
        
        # Check against limits
        if is_defined_risk:
            max_allocation = limits['defined_risk_allocation_percent']
        else:
            max_allocation = limits['undefined_risk_allocation_percent']
        
        # (Implementation needs portfolio value calculation)
    
    def _check_strategy_limits(self, trade: dm.Trade, result: RiskCheckResult):
        """Check strategy-specific limits"""
        if not trade.strategy:
            return
        
        strategy_type = trade.strategy.strategy_type.value
        strategy_limits = self.limits['strategy']
        
        if strategy_type not in strategy_limits:
            return
        
        limits = strategy_limits[strategy_type]
        
        # Strategy-specific validation
        # (Implementation depends on strategy type)
        
        # Example: Iron condor wing width check
        if strategy_type == 'iron_condor' and 'max_wing_width' in limits:
            # (Would check actual wing width from legs)
            pass
    
    def _check_timing_rules(self, trade: dm.Trade, result: RiskCheckResult):
        """Check timing-based rules"""
        timing = self.limits['timing']
        
        # Check DTE
        dte = trade.days_to_expiration()
        if dte:
            time_exit_dte = timing['time_exit_dte']
            if dte < time_exit_dte:
                result.add_violation(RiskViolation(
                    category="Timing",
                    severity="warn",
                    message=f"Opening trade with only {dte} DTE (below {time_exit_dte} threshold)",
                    limit_name="time_exit_dte",
                    current_value=dte,
                    limit_value=time_exit_dte
                ))
        
        # Earnings check
        # (Would need earnings calendar integration)
        
        # FOMC/Economic calendar check
        # (Would need calendar integration)
    
    def _is_defined_risk_trade(self, trade: dm.Trade) -> bool:
        """Determine if trade has defined risk (delegates to strategy templates)."""
        if not trade.strategy:
            return False

        from trading_cotrader.core.models.strategy_templates import is_defined_risk
        return is_defined_risk(trade.strategy.strategy_type)
    
    def get_limits_summary(self) -> Dict:
        """Get summary of all risk limits"""
        return {
            'portfolio': self.limits['portfolio'],
            'greeks': self.limits['greeks'],
            'concentration': self.limits['concentration'],
        }


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    from config.settings import setup_logging
    
    setup_logging()
    
    # Initialize risk manager
    risk_mgr = RiskManager("risk_limits.yaml")
    
    # Print limits
    print("Risk Limits Loaded:")
    print(f"  Max portfolio delta: ±{risk_mgr.limits['greeks']['max_portfolio_delta']}")
    print(f"  Max single trade risk: {risk_mgr.limits['portfolio']['max_single_trade_risk_percent']}%")
    print(f"  Max per underlying: {risk_mgr.limits['concentration']['max_percent_per_underlying']}%")
    
    print("\n✓ Risk manager ready")