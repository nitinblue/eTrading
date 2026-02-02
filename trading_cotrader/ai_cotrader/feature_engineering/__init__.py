"""
Feature Engineering Module

Extracts ML features from trade events, positions, and market data.
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

__all__ = [
    'FeatureExtractor',
    'MarketFeatures',
    'PositionFeatures',
    'PortfolioFeatures',
    'RLState',
    'DatasetBuilder',
    'TrainingExample',
]
