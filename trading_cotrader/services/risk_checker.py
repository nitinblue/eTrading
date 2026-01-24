"""
Pre-Trade Risk Checking

Validates trades BEFORE execution to prevent stupid mistakes.
"""

import logging
from decimal import Decimal
from typing import List, Dict
from dataclasses import dataclass

import core.models.domain as dm

logger = logging.getLogger(__name__)


@dataclass
class RiskCheckResult:
    """Result of risk analysis"""
    approved: bool = True
    warnings: List[str] = None
    rejections: List[str] = None
    risk_metrics: Dict[str, Decimal] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.rejections is None:
            self.rejections = []
        if self.risk_metrics is None:
            self.risk_metrics = {}
    
    def reject(self, reason: str):
        """Reject the trade"""
        self.approved = False
        self.rejections.append(reason)
        logger.warning(f"Trade rejected: {reason}")
    
    def warn(self, message: str):
        """Add warning but don't reject"""
        self.warnings.append(message)
        logger.info(f"Trade warning: {message}")
    
    def add_metric(self, name: str, value):
        """Track risk metric"""
        self.risk_metrics[name] = value


class RiskChecker:
    """
    Run risk checks on intent trades before submission
    
    Usage:
        checker = RiskChecker(portfolio, settings)
        result = checker.check(intent_trade)
        if result.approved:
            submit_to_broker(intent_trade)
        else:
            print(f"Rejected: {result.rejections}")
    """
    
    def __init__(self, portfolio: dm.Portfolio, settings):
        self.portfolio = portfolio
        self.settings = settings
    
    def check(self, trade: dm.Trade) -> RiskCheckResult:
        """
        Run all risk checks on trade
        
        Args:
            trade: Intent trade to validate
            
        Returns:
            RiskCheckResult with approval/rejection
        """
        result = RiskCheckResult()
        
        logger.info(f"Running risk checks on {trade.underlying_symbol} {trade.strategy.name if trade.strategy else 'trade'}")
        
        # Run all checks
        self._check_position_size(trade, result)
        self._check_greeks_impact(trade, result)
        self._check_max_loss(trade, result)
        
        # Log summary
        if result.approved:
            logger.info(f"✓ Trade approved")
        else:
            logger.warning(f"✗ Trade rejected: {', '.join(result.rejections)}")
        
        return result
    
    def _check_position_size(self, trade: dm.Trade, result: RiskCheckResult):
        """Ensure position isn't too large relative to portfolio"""
        
        trade_cost = abs(trade.net_cost())
        portfolio_value = self.portfolio.total_equity
        
        if portfolio_value == 0:
            result.reject("Portfolio value is zero")
            return
        
        position_pct = (trade_cost / portfolio_value) * 100
        result.add_metric("position_size_pct", position_pct)
        result.add_metric("position_size_dollars", trade_cost)
        
        max_allowed = self.settings.max_position_size_percent
        
        if position_pct > max_allowed:
            result.reject(
                f"Position size {position_pct:.1f}% exceeds max {max_allowed}%"
            )
        elif position_pct > max_allowed * 0.8:
            result.warn(
                f"Position size {position_pct:.1f}% approaching limit {max_allowed}%"
            )
    
    def _check_greeks_impact(self, trade: dm.Trade, result: RiskCheckResult):
        """Check impact on portfolio Greeks"""
        
        # Current portfolio Greeks
        current_delta = self.portfolio.portfolio_greeks.delta if self.portfolio.portfolio_greeks else Decimal('0')
        current_theta = self.portfolio.portfolio_greeks.theta if self.portfolio.portfolio_greeks else Decimal('0')
        
        # Trade Greeks
        trade_greeks = trade.total_greeks()
        
        # New portfolio Greeks after trade
        new_delta = current_delta + trade_greeks.delta
        new_theta = current_theta + trade_greeks.theta
        
        result.add_metric("current_delta", current_delta)
        result.add_metric("trade_delta", trade_greeks.delta)
        result.add_metric("new_delta", new_delta)
        result.add_metric("new_theta", new_theta)
        
        # Delta check
        max_delta = self.settings.max_portfolio_delta
        if max_delta and abs(new_delta) > max_delta:
            result.reject(
                f"Trade pushes delta to {new_delta:.2f}, exceeds ±{max_delta} limit"
            )
        elif max_delta and abs(new_delta) > max_delta * 0.8:
            result.warn(
                f"Delta approaching limit: {new_delta:.2f} (limit ±{max_delta})"
            )
        
        # Theta check (excessive decay)
        if self.portfolio.total_equity > 0:
            daily_theta_pct = (abs(new_theta) / self.portfolio.total_equity) * 100
            result.add_metric("theta_pct_of_portfolio", daily_theta_pct)
            
            if daily_theta_pct > 1.0:
                result.warn(
                    f"High theta: ${abs(new_theta):.2f}/day ({daily_theta_pct:.2f}% of portfolio)"
                )
    
    def _check_max_loss(self, trade: dm.Trade, result: RiskCheckResult):
        """Validate maximum loss is acceptable"""
        
        # Check if max_risk is set on trade
        if trade.max_risk:
            max_loss = trade.max_risk
        elif trade.strategy and trade.strategy.max_loss:
            max_loss = trade.strategy.max_loss
        else:
            result.warn("Max loss not defined for this trade")
            return
        
        portfolio_value = self.portfolio.total_equity
        if portfolio_value == 0:
            return
        
        loss_pct = (max_loss / portfolio_value) * 100
        
        result.add_metric("max_loss_dollars", max_loss)
        result.add_metric("max_loss_pct", loss_pct)
        
        # No single trade should risk more than 5% of portfolio
        if loss_pct > 5.0:
            result.reject(
                f"Max loss ${max_loss:.2f} ({loss_pct:.1f}%) exceeds 5% limit"
            )
        elif loss_pct > 3.0:
            result.warn(
                f"Max loss is {loss_pct:.1f}% of portfolio"
            )