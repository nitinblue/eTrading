"""
Learning Module

Contains ML models for trading decisions:
- Supervised: Learn from your past decisions
- Reinforcement: Optimize based on outcomes
"""

from ai_cotrader.learning.supervised import (
    PatternRecognizer,
    PatternMatch,
    ActionLabels,
    SimpleDecisionTree,
)

from ai_cotrader.learning.reinforcement import (
    QLearningAgent,
    DQNAgent,
    TradingAdvisor,
    RewardFunction,
    ReplayBuffer,
    RLActions,
)

__all__ = [
    # Supervised
    'PatternRecognizer',
    'PatternMatch',
    'ActionLabels',
    'SimpleDecisionTree',
    
    # Reinforcement
    'QLearningAgent',
    'DQNAgent',
    'TradingAdvisor',
    'RewardFunction',
    'ReplayBuffer',
    'RLActions',
]
