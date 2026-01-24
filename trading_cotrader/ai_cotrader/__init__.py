"""
AI Co-Trader: Machine Learning Module

This module learns from YOUR trading patterns to:
1. Recognize what action you typically take in each situation (Supervised)
2. Optimize decisions based on outcomes (Reinforcement Learning)
3. Provide intelligent suggestions while YOU stay in control

Modules:
- feature_engineering: Extract features from events/positions
- learning: ML models (supervised + RL)
- models: Trained model storage

Usage:
    from ai_cotrader import TradingAdvisor, FeatureExtractor
    
    # Extract features from current state
    extractor = FeatureExtractor()
    state = extractor.extract_from_event(event, position, portfolio)
    
    # Get recommendation
    advisor = TradingAdvisor()
    advisor.load('models/')
    recommendation = advisor.recommend(state.to_vector(), position, portfolio)
    
    print(f"Suggested: {recommendation['action']}")
    print(f"Confidence: {recommendation['confidence']}")
"""

from ai_cotrader.feature_engineering.feature_extractor import (
    FeatureExtractor,
    MarketFeatures,
    PositionFeatures,
    PortfolioFeatures,
    RLState,
    DatasetBuilder,
    TrainingExample,
)

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
    # Feature Engineering
    'FeatureExtractor',
    'MarketFeatures',
    'PositionFeatures',
    'PortfolioFeatures',
    'RLState',
    'DatasetBuilder',
    'TrainingExample',
    
    # Supervised Learning
    'PatternRecognizer',
    'PatternMatch',
    'ActionLabels',
    'SimpleDecisionTree',
    
    # Reinforcement Learning
    'QLearningAgent',
    'DQNAgent',
    'TradingAdvisor',
    'RewardFunction',
    'ReplayBuffer',
    'RLActions',
]
