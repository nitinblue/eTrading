"""
Feature Engineering for ML/RL

Extracts features from trade events for machine learning.
Converts raw event data into structured feature vectors.

This is the bridge between your trading history and ML models.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
import numpy as np
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Feature Definitions
# =============================================================================

@dataclass
class MarketFeatures:
    """Features extracted from market state at decision time"""
    
    # Price features
    underlying_price: float = 0.0
    price_vs_20d_ma: float = 0.0      # Price relative to 20-day MA (%)
    price_vs_50d_ma: float = 0.0      # Price relative to 50-day MA (%)
    daily_return: float = 0.0          # Previous day return (%)
    weekly_return: float = 0.0         # Previous week return (%)
    
    # Volatility features
    iv_rank: float = 0.0              # 0-100 scale
    iv_percentile: float = 0.0        # 0-100 scale
    vix_level: float = 0.0
    vix_term_structure: float = 0.0   # VIX vs VIX3M ratio
    realized_vol_10d: float = 0.0     # 10-day realized vol
    realized_vol_30d: float = 0.0     # 30-day realized vol
    iv_rv_spread: float = 0.0         # IV - RV (vol risk premium)
    
    # Technical features
    rsi_14: float = 50.0              # RSI 14-day
    distance_to_support: float = 0.0  # % distance to support
    distance_to_resistance: float = 0.0
    
    # Market regime (one-hot encoded in vector)
    regime_bullish: float = 0.0
    regime_bearish: float = 0.0
    regime_neutral: float = 0.0
    
    # Time features
    day_of_week: int = 0              # 0=Monday, 4=Friday
    days_to_monthly_opex: int = 0     # Days to monthly options expiration
    is_earnings_week: float = 0.0     # Binary: earnings this week?
    
    def to_vector(self) -> np.ndarray:
        """Convert to numpy array for ML models"""
        return np.array([
            self.underlying_price,
            self.price_vs_20d_ma,
            self.price_vs_50d_ma,
            self.daily_return,
            self.weekly_return,
            self.iv_rank,
            self.iv_percentile,
            self.vix_level,
            self.vix_term_structure,
            self.realized_vol_10d,
            self.realized_vol_30d,
            self.iv_rv_spread,
            self.rsi_14,
            self.distance_to_support,
            self.distance_to_resistance,
            self.regime_bullish,
            self.regime_bearish,
            self.regime_neutral,
            float(self.day_of_week) / 4.0,  # Normalize to 0-1
            float(self.days_to_monthly_opex) / 30.0,
            self.is_earnings_week,
        ], dtype=np.float32)
    
    @staticmethod
    def feature_names() -> List[str]:
        return [
            'underlying_price', 'price_vs_20d_ma', 'price_vs_50d_ma',
            'daily_return', 'weekly_return', 'iv_rank', 'iv_percentile',
            'vix_level', 'vix_term_structure', 'realized_vol_10d',
            'realized_vol_30d', 'iv_rv_spread', 'rsi_14',
            'distance_to_support', 'distance_to_resistance',
            'regime_bullish', 'regime_bearish', 'regime_neutral',
            'day_of_week', 'days_to_monthly_opex', 'is_earnings_week'
        ]


@dataclass
class PositionFeatures:
    """Features extracted from position state"""
    
    # P&L features
    pnl_percent: float = 0.0          # Current P&L as % of max profit
    pnl_dollars: float = 0.0          # Current P&L in dollars
    pnl_vs_theta: float = 0.0         # P&L relative to expected theta decay
    
    # Time features
    dte: int = 0                      # Days to expiration
    dte_normalized: float = 0.0       # DTE / initial DTE
    days_held: int = 0
    time_in_trade_pct: float = 0.0    # days_held / initial_dte
    
    # Greeks features
    position_delta: float = 0.0
    position_gamma: float = 0.0
    position_theta: float = 0.0
    position_vega: float = 0.0
    delta_dollars: float = 0.0        # Delta * underlying price
    
    # Risk features
    current_risk_reward: float = 0.0  # Current risk / current reward
    distance_to_short_strike: float = 0.0  # % distance
    probability_itm: float = 0.0
    
    # Strategy type (one-hot)
    is_credit_spread: float = 0.0
    is_iron_condor: float = 0.0
    is_naked: float = 0.0
    is_defined_risk: float = 0.0
    
    def to_vector(self) -> np.ndarray:
        """Convert to numpy array"""
        return np.array([
            self.pnl_percent,
            self.pnl_dollars / 1000.0,  # Normalize
            self.pnl_vs_theta,
            float(self.dte) / 60.0,     # Normalize assuming max 60 DTE
            self.dte_normalized,
            float(self.days_held) / 60.0,
            self.time_in_trade_pct,
            self.position_delta,
            self.position_gamma * 100,   # Scale gamma
            self.position_theta / 100.0, # Normalize
            self.position_vega / 100.0,
            self.delta_dollars / 10000.0,
            self.current_risk_reward,
            self.distance_to_short_strike,
            self.probability_itm,
            self.is_credit_spread,
            self.is_iron_condor,
            self.is_naked,
            self.is_defined_risk,
        ], dtype=np.float32)
    
    @staticmethod
    def feature_names() -> List[str]:
        return [
            'pnl_percent', 'pnl_dollars', 'pnl_vs_theta',
            'dte', 'dte_normalized', 'days_held', 'time_in_trade_pct',
            'position_delta', 'position_gamma', 'position_theta', 'position_vega',
            'delta_dollars', 'current_risk_reward', 'distance_to_short_strike',
            'probability_itm', 'is_credit_spread', 'is_iron_condor',
            'is_naked', 'is_defined_risk'
        ]


@dataclass
class PortfolioFeatures:
    """Features from overall portfolio state"""
    
    # Greeks
    portfolio_delta: float = 0.0
    portfolio_gamma: float = 0.0
    portfolio_theta: float = 0.0
    portfolio_vega: float = 0.0
    
    # Normalized by portfolio size
    delta_per_10k: float = 0.0        # Delta per $10k equity
    theta_per_10k: float = 0.0
    
    # Concentration
    num_positions: int = 0
    largest_position_pct: float = 0.0
    correlation_score: float = 0.0
    
    # Capital
    buying_power_pct: float = 0.0     # Available BP as % of total
    margin_utilization: float = 0.0
    cash_pct: float = 0.0
    
    # Performance
    daily_pnl_pct: float = 0.0
    weekly_pnl_pct: float = 0.0
    drawdown_pct: float = 0.0
    
    def to_vector(self) -> np.ndarray:
        return np.array([
            self.portfolio_delta / 100.0,
            self.portfolio_gamma,
            self.portfolio_theta / 100.0,
            self.portfolio_vega / 100.0,
            self.delta_per_10k / 10.0,
            self.theta_per_10k / 10.0,
            float(self.num_positions) / 20.0,
            self.largest_position_pct,
            self.correlation_score,
            self.buying_power_pct,
            self.margin_utilization,
            self.cash_pct,
            self.daily_pnl_pct,
            self.weekly_pnl_pct,
            self.drawdown_pct,
        ], dtype=np.float32)


@dataclass 
class RLState:
    """
    Complete state representation for RL agent.
    
    Combines market, position, and portfolio features.
    """
    market: MarketFeatures = field(default_factory=MarketFeatures)
    position: PositionFeatures = field(default_factory=PositionFeatures)
    portfolio: PortfolioFeatures = field(default_factory=PortfolioFeatures)
    
    def to_vector(self) -> np.ndarray:
        """Concatenate all features into single vector"""
        return np.concatenate([
            self.market.to_vector(),
            self.position.to_vector(),
            self.portfolio.to_vector()
        ])
    
    @property
    def state_dim(self) -> int:
        """Total state dimension"""
        return len(self.to_vector())


# =============================================================================
# Feature Extractor
# =============================================================================

class FeatureExtractor:
    """
    Extract ML features from trade events and market data.
    
    Usage:
        extractor = FeatureExtractor()
        
        # From a trade event
        state = extractor.extract_from_event(trade_event, position, portfolio)
        
        # Get feature vector for ML
        vector = state.to_vector()
    """
    
    def __init__(self, market_data_provider=None):
        """
        Args:
            market_data_provider: Optional provider for historical prices
        """
        self.market_data = market_data_provider
    
    def extract_from_event(
        self,
        event,  # TradeEvent
        position=None,  # Position (optional)
        portfolio=None,  # Portfolio (optional)
        market_snapshot: Dict = None
    ) -> RLState:
        """
        Extract features from a trade event.
        
        Args:
            event: TradeEvent with market_context and decision_context
            position: Current position (for position management decisions)
            portfolio: Current portfolio state
            market_snapshot: Additional market data
            
        Returns:
            RLState with all features populated
        """
        state = RLState()
        
        # Extract market features from event context
        if hasattr(event, 'market_context') and event.market_context:
            state.market = self._extract_market_features(event.market_context)
        
        # Extract position features
        if position:
            state.position = self._extract_position_features(position, event)
        
        # Extract portfolio features
        if portfolio:
            state.portfolio = self._extract_portfolio_features(portfolio)
        
        return state
    
    def _extract_market_features(self, context) -> MarketFeatures:
        """Extract market features from MarketContext"""
        features = MarketFeatures()
        
        # Direct mappings
        features.underlying_price = float(getattr(context, 'underlying_price', 0) or 0)
        features.iv_rank = float(getattr(context, 'iv_rank', 0) or 0)
        features.iv_percentile = float(getattr(context, 'iv_percentile', 0) or 0)
        features.vix_level = float(getattr(context, 'vix', 0) or 0)
        features.rsi_14 = float(getattr(context, 'rsi', 50) or 50)
        
        # Market regime encoding
        regime = getattr(context, 'market_trend', 'neutral') or 'neutral'
        if 'bull' in regime.lower() or 'up' in regime.lower():
            features.regime_bullish = 1.0
        elif 'bear' in regime.lower() or 'down' in regime.lower():
            features.regime_bearish = 1.0
        else:
            features.regime_neutral = 1.0
        
        # Time features
        timestamp = getattr(context, 'timestamp', datetime.utcnow())
        if timestamp:
            features.day_of_week = timestamp.weekday()
            features.days_to_monthly_opex = self._days_to_monthly_opex(timestamp)
        
        # Earnings
        days_to_earnings = getattr(context, 'days_to_earnings', None)
        features.is_earnings_week = 1.0 if days_to_earnings and days_to_earnings <= 7 else 0.0
        
        # Support/resistance
        support = float(getattr(context, 'support_level', 0) or 0)
        resistance = float(getattr(context, 'resistance_level', 0) or 0)
        price = features.underlying_price
        
        if support and price:
            features.distance_to_support = (price - support) / price * 100
        if resistance and price:
            features.distance_to_resistance = (resistance - price) / price * 100
        
        return features
    
    def _extract_position_features(self, position, event=None) -> PositionFeatures:
        """Extract position features"""
        features = PositionFeatures()
        
        # P&L
        pnl = float(position.unrealized_pnl() if hasattr(position, 'unrealized_pnl') else 0)
        cost = abs(float(getattr(position, 'total_cost', 1) or 1))
        features.pnl_dollars = pnl
        features.pnl_percent = (pnl / cost * 100) if cost else 0
        
        # Time
        symbol = getattr(position, 'symbol', None)
        expiration = getattr(symbol, 'expiration', None) if symbol else None
        if expiration:
            features.dte = max(0, (expiration - datetime.utcnow()).days)
        
        # Greeks
        greeks = getattr(position, 'greeks', None)
        if greeks:
            features.position_delta = float(getattr(greeks, 'delta', 0) or 0)
            features.position_gamma = float(getattr(greeks, 'gamma', 0) or 0)
            features.position_theta = float(getattr(greeks, 'theta', 0) or 0)
            features.position_vega = float(getattr(greeks, 'vega', 0) or 0)
        
        # Strategy type (simplified detection)
        quantity = getattr(position, 'quantity', 0)
        asset_type = getattr(symbol, 'asset_type', None) if symbol else None
        
        if asset_type and hasattr(asset_type, 'value') and asset_type.value == 'option':
            features.is_defined_risk = 1.0  # Assume defined for now
            if quantity < 0:
                features.is_credit_spread = 1.0
        
        return features
    
    def _extract_portfolio_features(self, portfolio) -> PortfolioFeatures:
        """Extract portfolio features"""
        features = PortfolioFeatures()
        
        # Greeks
        greeks = getattr(portfolio, 'portfolio_greeks', None)
        if greeks:
            features.portfolio_delta = float(getattr(greeks, 'delta', 0) or 0)
            features.portfolio_gamma = float(getattr(greeks, 'gamma', 0) or 0)
            features.portfolio_theta = float(getattr(greeks, 'theta', 0) or 0)
            features.portfolio_vega = float(getattr(greeks, 'vega', 0) or 0)
        
        # Capital
        equity = float(getattr(portfolio, 'total_equity', 0) or 0)
        bp = float(getattr(portfolio, 'buying_power', 0) or 0)
        cash = float(getattr(portfolio, 'cash_balance', 0) or 0)
        
        if equity > 0:
            features.buying_power_pct = bp / equity
            features.cash_pct = cash / equity
            features.delta_per_10k = features.portfolio_delta / (equity / 10000)
            features.theta_per_10k = features.portfolio_theta / (equity / 10000)
        
        return features
    
    def _days_to_monthly_opex(self, date: datetime) -> int:
        """Calculate days to next monthly options expiration (3rd Friday)"""
        year = date.year
        month = date.month
        
        # Find 3rd Friday of this month
        first_day = datetime(year, month, 1)
        first_friday = first_day + timedelta(days=(4 - first_day.weekday() + 7) % 7)
        third_friday = first_friday + timedelta(weeks=2)
        
        if date > third_friday:
            # Move to next month
            month += 1
            if month > 12:
                month = 1
                year += 1
            first_day = datetime(year, month, 1)
            first_friday = first_day + timedelta(days=(4 - first_day.weekday() + 7) % 7)
            third_friday = first_friday + timedelta(weeks=2)
        
        return (third_friday - date).days


# =============================================================================
# Dataset Builder
# =============================================================================

@dataclass
class TrainingExample:
    """Single training example for ML"""
    state: np.ndarray           # State features
    action: int                 # Action taken (for supervised) or to learn (for RL)
    reward: float               # Outcome/reward
    next_state: np.ndarray      # Next state (for RL)
    done: bool                  # Episode ended?
    metadata: Dict = field(default_factory=dict)


class DatasetBuilder:
    """
    Build ML datasets from trade events.
    
    Usage:
        builder = DatasetBuilder()
        
        # Add events
        for event in events:
            builder.add_event(event, position, portfolio, outcome)
        
        # Get dataset
        X, y = builder.get_supervised_dataset()
        
        # Or for RL
        transitions = builder.get_rl_transitions()
    """
    
    def __init__(self):
        self.extractor = FeatureExtractor()
        self.examples: List[TrainingExample] = []
    
    def add_event(
        self,
        event,
        position=None,
        portfolio=None,
        action_taken: int = 0,
        outcome: float = 0.0,
        next_event=None
    ):
        """Add a training example from an event"""
        
        # Extract state
        state = self.extractor.extract_from_event(event, position, portfolio)
        state_vector = state.to_vector()
        
        # Extract next state if available
        next_state_vector = np.zeros_like(state_vector)
        done = True
        
        if next_event:
            next_state = self.extractor.extract_from_event(next_event, position, portfolio)
            next_state_vector = next_state.to_vector()
            done = False
        
        example = TrainingExample(
            state=state_vector,
            action=action_taken,
            reward=outcome,
            next_state=next_state_vector,
            done=done,
            metadata={
                'event_id': getattr(event, 'event_id', ''),
                'timestamp': str(getattr(event, 'timestamp', '')),
                'underlying': getattr(event, 'underlying_symbol', '')
            }
        )
        
        self.examples.append(example)
    
    def get_supervised_dataset(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get dataset for supervised learning.
        
        Returns:
            X: Feature matrix (n_samples, n_features)
            y: Labels (n_samples,)
        """
        if not self.examples:
            return np.array([]), np.array([])
        
        X = np.stack([ex.state for ex in self.examples])
        y = np.array([ex.action for ex in self.examples])
        
        return X, y
    
    def get_rl_transitions(self) -> List[Tuple]:
        """
        Get transitions for RL training.
        
        Returns:
            List of (state, action, reward, next_state, done) tuples
        """
        return [
            (ex.state, ex.action, ex.reward, ex.next_state, ex.done)
            for ex in self.examples
        ]
    
    def save(self, filepath: str):
        """Save dataset to file"""
        import pickle
        with open(filepath, 'wb') as f:
            pickle.dump(self.examples, f)
        logger.info(f"Saved {len(self.examples)} examples to {filepath}")
    
    def load(self, filepath: str):
        """Load dataset from file"""
        import pickle
        with open(filepath, 'rb') as f:
            self.examples = pickle.load(f)
        logger.info(f"Loaded {len(self.examples)} examples from {filepath}")


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    # Create extractor
    extractor = FeatureExtractor()
    
    # Mock event with market context
    class MockMarketContext:
        underlying_price = 500.0
        iv_rank = 65.0
        iv_percentile = 70.0
        vix = 18.5
        rsi = 55.0
        market_trend = 'bullish'
        timestamp = datetime.utcnow()
        days_to_earnings = 15
        support_level = 490.0
        resistance_level = 510.0
    
    class MockEvent:
        event_id = 'test_123'
        market_context = MockMarketContext()
        underlying_symbol = 'SPY'
        timestamp = datetime.utcnow()
    
    # Extract features
    state = extractor.extract_from_event(MockEvent())
    
    print("Market Features:")
    for name, val in zip(MarketFeatures.feature_names(), state.market.to_vector()):
        print(f"  {name}: {val:.4f}")
    
    print(f"\nTotal state dimension: {state.state_dim}")
    print(f"State vector shape: {state.to_vector().shape}")
