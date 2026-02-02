"""
Position Management Rules Engine

Evaluates positions against exit rules to determine:
- When to take profits
- When to cut losses
- When to roll or adjust
- When time-based exits apply

Rules are loaded from configuration YAML.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of actions the rules engine can recommend"""
    HOLD = "hold"                    # No action needed
    CLOSE = "close"                  # Close the position
    CLOSE_PARTIAL = "close_partial"  # Close part of the position
    ROLL = "roll"                    # Roll to new expiration
    ADJUST = "adjust"                # Adjust strikes/legs
    HEDGE = "hedge"                  # Add a hedge


class RulePriority(Enum):
    """Priority levels for rules"""
    CRITICAL = 1    # Must act immediately (stop loss hit)
    HIGH = 2        # Should act soon (profit target)
    MEDIUM = 3      # Consider acting (time-based)
    LOW = 4         # Optional action (optimization)


@dataclass
class RuleEvaluation:
    """Result of evaluating a single rule"""
    rule_name: str
    triggered: bool
    action: ActionType
    priority: RulePriority
    current_value: Any
    threshold_value: Any
    message: str
    details: Dict = field(default_factory=dict)


@dataclass
class PositionAction:
    """
    Recommended action for a position.
    
    This is what the rules engine outputs.
    """
    position_id: str
    symbol: str
    
    # Recommended action
    action: ActionType
    priority: RulePriority
    
    # Why this action
    triggered_rules: List[RuleEvaluation]
    primary_reason: str
    
    # Details for the action
    close_quantity: Optional[int] = None
    roll_to_expiration: Optional[datetime] = None
    adjustment_details: Dict = field(default_factory=dict)
    
    # Timing
    urgency: str = "normal"  # immediate, today, this_week, when_convenient
    
    # Timestamp
    evaluated_at: datetime = field(default_factory=datetime.utcnow)
    
    def should_act(self) -> bool:
        """Should we act on this recommendation?"""
        return self.action != ActionType.HOLD


# =============================================================================
# Rule Base Classes
# =============================================================================

class ExitRule(ABC):
    """Base class for exit rules"""
    
    def __init__(self, name: str, enabled: bool = True, priority: int = 1):
        self.name = name
        self.enabled = enabled
        self.priority = priority
    
    @abstractmethod
    def evaluate(
        self,
        position,  # Position
        trade,  # Trade (optional, for multi-leg)
        market_data: Dict
    ) -> RuleEvaluation:
        """
        Evaluate the rule against a position.
        
        Args:
            position: Position object
            trade: Associated Trade object (if any)
            market_data: Current market data
            
        Returns:
            RuleEvaluation with results
        """
        pass


# =============================================================================
# Profit Target Rules
# =============================================================================

class ProfitTargetRule(ExitRule):
    """Close when profit reaches X% of max profit"""
    
    def __init__(self, target_percent: float, **kwargs):
        super().__init__(**kwargs)
        self.target_percent = target_percent
    
    def evaluate(self, position, trade, market_data) -> RuleEvaluation:
        # Get current P&L
        current_pnl = float(position.unrealized_pnl() if hasattr(position, 'unrealized_pnl') else 0)
        
        # Get max profit (from trade if available)
        max_profit = float(getattr(trade, 'max_profit', 0) or 0)
        
        if max_profit == 0:
            # Estimate from position
            max_profit = abs(float(getattr(position, 'total_cost', 0)))
        
        if max_profit == 0:
            return RuleEvaluation(
                rule_name=self.name,
                triggered=False,
                action=ActionType.HOLD,
                priority=RulePriority(self.priority),
                current_value=0,
                threshold_value=self.target_percent,
                message="Cannot calculate profit target (no max profit)",
            )
        
        profit_percent = (current_pnl / max_profit) * 100
        triggered = profit_percent >= self.target_percent
        
        return RuleEvaluation(
            rule_name=self.name,
            triggered=triggered,
            action=ActionType.CLOSE if triggered else ActionType.HOLD,
            priority=RulePriority.HIGH if triggered else RulePriority.LOW,
            current_value=profit_percent,
            threshold_value=self.target_percent,
            message=f"Profit at {profit_percent:.1f}% (target: {self.target_percent}%)",
            details={'current_pnl': current_pnl, 'max_profit': max_profit}
        )


# =============================================================================
# Stop Loss Rules
# =============================================================================

class StopLossRule(ExitRule):
    """Close when loss reaches X% of max loss (or premium received)"""
    
    def __init__(self, max_loss_percent: float, **kwargs):
        super().__init__(**kwargs)
        self.max_loss_percent = max_loss_percent
    
    def evaluate(self, position, trade, market_data) -> RuleEvaluation:
        current_pnl = float(position.unrealized_pnl() if hasattr(position, 'unrealized_pnl') else 0)
        
        # For credit trades, max loss = width - credit
        # For simplicity, use premium received as reference
        premium = abs(float(getattr(position, 'total_cost', 0)))
        
        if premium == 0:
            return RuleEvaluation(
                rule_name=self.name,
                triggered=False,
                action=ActionType.HOLD,
                priority=RulePriority(self.priority),
                current_value=0,
                threshold_value=self.max_loss_percent,
                message="Cannot calculate stop loss (no premium)",
            )
        
        # Loss as percentage of premium
        loss_percent = (-current_pnl / premium) * 100 if current_pnl < 0 else 0
        triggered = loss_percent >= self.max_loss_percent
        
        return RuleEvaluation(
            rule_name=self.name,
            triggered=triggered,
            action=ActionType.CLOSE if triggered else ActionType.HOLD,
            priority=RulePriority.CRITICAL if triggered else RulePriority.LOW,
            current_value=loss_percent,
            threshold_value=self.max_loss_percent,
            message=f"Loss at {loss_percent:.1f}% (max: {self.max_loss_percent}%)",
            details={'current_pnl': current_pnl, 'premium': premium}
        )


# =============================================================================
# Time-Based Rules
# =============================================================================

class DTEExitRule(ExitRule):
    """Close when position reaches X days to expiration"""
    
    def __init__(self, dte_threshold: int, **kwargs):
        super().__init__(**kwargs)
        self.dte_threshold = dte_threshold
    
    def evaluate(self, position, trade, market_data) -> RuleEvaluation:
        symbol = getattr(position, 'symbol', None)
        expiration = getattr(symbol, 'expiration', None) if symbol else None
        
        if not expiration:
            return RuleEvaluation(
                rule_name=self.name,
                triggered=False,
                action=ActionType.HOLD,
                priority=RulePriority(self.priority),
                current_value=None,
                threshold_value=self.dte_threshold,
                message="No expiration date found",
            )
        
        dte = (expiration - datetime.utcnow()).days
        triggered = dte <= self.dte_threshold
        
        return RuleEvaluation(
            rule_name=self.name,
            triggered=triggered,
            action=ActionType.CLOSE if triggered else ActionType.HOLD,
            priority=RulePriority.MEDIUM if triggered else RulePriority.LOW,
            current_value=dte,
            threshold_value=self.dte_threshold,
            message=f"{dte} DTE (threshold: {self.dte_threshold})",
            details={'expiration': expiration.isoformat()}
        )


# =============================================================================
# Delta-Based Rules
# =============================================================================

class DeltaBreachRule(ExitRule):
    """Close when option delta exceeds threshold (for short options)"""
    
    def __init__(self, max_delta: float, applies_to: List[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.max_delta = max_delta
        self.applies_to = applies_to or ['short_put', 'short_call']
    
    def evaluate(self, position, trade, market_data) -> RuleEvaluation:
        # Check if this rule applies to this position type
        position_type = self._get_position_type(position)
        if position_type not in self.applies_to:
            return RuleEvaluation(
                rule_name=self.name,
                triggered=False,
                action=ActionType.HOLD,
                priority=RulePriority(self.priority),
                current_value=None,
                threshold_value=self.max_delta,
                message=f"Rule doesn't apply to {position_type}",
            )
        
        greeks = getattr(position, 'greeks', None)
        delta = abs(float(getattr(greeks, 'delta', 0))) if greeks else 0
        
        # Normalize to per-contract delta
        quantity = abs(getattr(position, 'quantity', 1))
        per_contract_delta = delta / quantity if quantity > 0 else delta
        
        triggered = per_contract_delta >= self.max_delta
        
        return RuleEvaluation(
            rule_name=self.name,
            triggered=triggered,
            action=ActionType.CLOSE if triggered else ActionType.HOLD,
            priority=RulePriority.HIGH if triggered else RulePriority.LOW,
            current_value=per_contract_delta,
            threshold_value=self.max_delta,
            message=f"Delta at {per_contract_delta:.2f} (max: {self.max_delta})",
        )
    
    def _get_position_type(self, position) -> str:
        """Determine position type."""
        quantity = getattr(position, 'quantity', 0)
        symbol = getattr(position, 'symbol', None)
        option_type = getattr(symbol, 'option_type', None) if symbol else None
        
        if not option_type:
            return 'equity'
        
        opt_type_value = getattr(option_type, 'value', str(option_type)).lower()
        
        if quantity < 0:
            return f"short_{opt_type_value}"
        else:
            return f"long_{opt_type_value}"


# =============================================================================
# Combined Rules
# =============================================================================

class CombinedRule(ExitRule):
    """Rule that combines multiple conditions with AND logic"""
    
    def __init__(
        self,
        profit_percent_min: float = None,
        dte_max: int = None,
        description: str = "",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.profit_percent_min = profit_percent_min
        self.dte_max = dte_max
        self.description = description
    
    def evaluate(self, position, trade, market_data) -> RuleEvaluation:
        conditions_met = []
        conditions_failed = []
        
        # Check profit condition
        if self.profit_percent_min is not None:
            current_pnl = float(position.unrealized_pnl() if hasattr(position, 'unrealized_pnl') else 0)
            premium = abs(float(getattr(position, 'total_cost', 0))) or 1
            profit_percent = (current_pnl / premium) * 100
            
            if profit_percent >= self.profit_percent_min:
                conditions_met.append(f"profit {profit_percent:.0f}%")
            else:
                conditions_failed.append(f"profit {profit_percent:.0f}% < {self.profit_percent_min}%")
        
        # Check DTE condition
        if self.dte_max is not None:
            symbol = getattr(position, 'symbol', None)
            expiration = getattr(symbol, 'expiration', None) if symbol else None
            if expiration:
                dte = (expiration - datetime.utcnow()).days
                if dte <= self.dte_max:
                    conditions_met.append(f"DTE {dte}")
                else:
                    conditions_failed.append(f"DTE {dte} > {self.dte_max}")
        
        # All conditions must be met
        triggered = len(conditions_failed) == 0 and len(conditions_met) > 0
        
        return RuleEvaluation(
            rule_name=self.name,
            triggered=triggered,
            action=ActionType.CLOSE if triggered else ActionType.HOLD,
            priority=RulePriority(self.priority),
            current_value=conditions_met,
            threshold_value=f"profit>={self.profit_percent_min}% AND DTE<={self.dte_max}",
            message=f"{'All conditions met' if triggered else 'Not all conditions met'}: {', '.join(conditions_met + conditions_failed)}",
            details={'description': self.description}
        )


# =============================================================================
# Rules Engine
# =============================================================================

class RulesEngine:
    """
    Main rules engine for position management.
    
    Usage:
        engine = RulesEngine.from_config(risk_config)
        
        # Evaluate single position
        action = engine.evaluate_position(position, trade, market_data)
        if action.should_act():
            print(f"Recommended: {action.action.value} - {action.primary_reason}")
        
        # Evaluate all positions
        actions = engine.evaluate_all(positions, trades, market_data)
        for action in actions:
            if action.should_act():
                print(f"{action.symbol}: {action.action.value}")
    """
    
    def __init__(self, rules: List[ExitRule] = None):
        self.rules = rules or []
    
    @classmethod
    def from_config(cls, config) -> 'RulesEngine':
        """Create rules engine from configuration."""
        rules = []
        
        if not config or not hasattr(config, 'exit_rules'):
            return cls(rules)
        
        exit_rules = config.exit_rules
        
        # Add profit target rules
        for rule in getattr(exit_rules, 'profit_targets', []):
            if rule.enabled:
                rules.append(ProfitTargetRule(
                    target_percent=rule.target_percent,
                    name=rule.name,
                    enabled=rule.enabled,
                    priority=rule.priority
                ))
        
        # Add stop loss rules
        for rule in getattr(exit_rules, 'stop_losses', []):
            if rule.enabled:
                rules.append(StopLossRule(
                    max_loss_percent=rule.max_loss_percent,
                    name=rule.name,
                    enabled=rule.enabled,
                    priority=rule.priority
                ))
        
        # Add DTE rules
        for rule in getattr(exit_rules, 'time_based', []):
            if rule.enabled:
                rules.append(DTEExitRule(
                    dte_threshold=rule.days_to_expiry,
                    name=rule.name,
                    enabled=rule.enabled,
                    priority=rule.priority
                ))
        
        # Add delta rules
        for rule in getattr(exit_rules, 'delta_based', []):
            if rule.enabled:
                rules.append(DeltaBreachRule(
                    max_delta=rule.max_delta,
                    applies_to=rule.applies_to,
                    name=rule.name,
                    enabled=rule.enabled,
                    priority=rule.priority
                ))
        
        # Add combined rules
        for rule in getattr(exit_rules, 'combined', []):
            if rule.enabled:
                rules.append(CombinedRule(
                    profit_percent_min=rule.conditions.get('profit_percent_min'),
                    dte_max=rule.conditions.get('dte_max'),
                    description=rule.description,
                    name=rule.name,
                    enabled=rule.enabled,
                    priority=rule.priority
                ))
        
        return cls(rules)
    
    def add_rule(self, rule: ExitRule):
        """Add a rule to the engine."""
        self.rules.append(rule)
    
    def evaluate_position(
        self,
        position,  # Position
        trade=None,  # Trade
        market_data: Dict = None
    ) -> PositionAction:
        """
        Evaluate all rules against a position.
        
        Args:
            position: Position to evaluate
            trade: Associated trade (optional)
            market_data: Current market data
            
        Returns:
            PositionAction with recommended action
        """
        market_data = market_data or {}
        evaluations = []
        
        # Evaluate all rules
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            try:
                result = rule.evaluate(position, trade, market_data)
                evaluations.append(result)
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.name}: {e}")
        
        # Find triggered rules
        triggered = [e for e in evaluations if e.triggered]
        
        # Determine action based on highest priority triggered rule
        if not triggered:
            return PositionAction(
                position_id=getattr(position, 'id', ''),
                symbol=getattr(getattr(position, 'symbol', None), 'ticker', 'UNKNOWN'),
                action=ActionType.HOLD,
                priority=RulePriority.LOW,
                triggered_rules=[],
                primary_reason="No rules triggered"
            )
        
        # Sort by priority (lower number = higher priority)
        triggered.sort(key=lambda e: e.priority.value)
        highest = triggered[0]
        
        # Determine urgency
        urgency = "normal"
        if highest.priority == RulePriority.CRITICAL:
            urgency = "immediate"
        elif highest.priority == RulePriority.HIGH:
            urgency = "today"
        
        return PositionAction(
            position_id=getattr(position, 'id', ''),
            symbol=getattr(getattr(position, 'symbol', None), 'ticker', 'UNKNOWN'),
            action=highest.action,
            priority=highest.priority,
            triggered_rules=triggered,
            primary_reason=highest.message,
            urgency=urgency
        )
    
    def evaluate_all(
        self,
        positions: List,
        trades: Dict = None,  # position_id -> Trade
        market_data: Dict = None
    ) -> List[PositionAction]:
        """
        Evaluate all positions.
        
        Returns list of PositionAction, sorted by priority.
        """
        trades = trades or {}
        actions = []
        
        for position in positions:
            pos_id = getattr(position, 'id', '')
            trade = trades.get(pos_id)
            action = self.evaluate_position(position, trade, market_data)
            actions.append(action)
        
        # Sort by priority
        actions.sort(key=lambda a: a.priority.value)
        
        return actions
    
    def get_actionable(self, actions: List[PositionAction]) -> List[PositionAction]:
        """Filter to only actionable items."""
        return [a for a in actions if a.should_act()]


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    # Create engine with manual rules
    engine = RulesEngine([
        ProfitTargetRule(target_percent=50, name="50% Profit", priority=1),
        StopLossRule(max_loss_percent=100, name="100% Stop", priority=1),
        DTEExitRule(dte_threshold=21, name="21 DTE", priority=2),
    ])
    
    # Mock position
    class MockPosition:
        id = "pos_123"
        class symbol:
            ticker = "SPY"
            expiration = datetime.utcnow() + timedelta(days=15)
        quantity = -1
        total_cost = Decimal('150')  # $150 credit
        
        def unrealized_pnl(self):
            return Decimal('90')  # $90 profit = 60%
    
    # Evaluate
    action = engine.evaluate_position(MockPosition())
    
    print(f"Position: {action.symbol}")
    print(f"Action: {action.action.value}")
    print(f"Urgency: {action.urgency}")
    print(f"Reason: {action.primary_reason}")
    print(f"\nTriggered Rules:")
    for rule in action.triggered_rules:
        print(f"  - {rule.rule_name}: {rule.message}")
