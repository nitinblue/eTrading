"""
Position Management Module

Provides:
- Rules engine for exit decisions
- Adjustment recommendations
- Roll vs close decisions
- Profit taking and stop loss management

Usage:
    from services.position_mgmt import RulesEngine, PositionAction
    
    # Create from config
    engine = RulesEngine.from_config(risk_config)
    
    # Evaluate positions
    actions = engine.evaluate_all(positions)
    
    for action in actions:
        if action.should_act():
            print(f"{action.symbol}: {action.action.value} - {action.primary_reason}")
"""

from services.position_mgmt.rules_engine import (
    RulesEngine,
    ExitRule,
    ProfitTargetRule,
    StopLossRule,
    DTEExitRule,
    DeltaBreachRule,
    CombinedRule,
    PositionAction,
    RuleEvaluation,
    ActionType,
    RulePriority,
)

__all__ = [
    'RulesEngine',
    'ExitRule',
    'ProfitTargetRule',
    'StopLossRule',
    'DTEExitRule',
    'DeltaBreachRule',
    'CombinedRule',
    'PositionAction',
    'RuleEvaluation',
    'ActionType',
    'RulePriority',
]
