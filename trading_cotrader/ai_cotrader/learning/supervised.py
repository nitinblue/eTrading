"""
Supervised Learning Module

Learn from YOUR trading patterns using supervised learning.
This model learns what YOU would do in a given situation.

Phase 1: Classification - "Given this state, what action would the trader take?"
Phase 2: Regression - "Given this state, what is the expected P&L?"
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime
import numpy as np
import logging
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# Action Labels
# =============================================================================

class ActionLabels:
    """Standard action labels for classification"""
    
    HOLD = 0
    CLOSE = 1
    CLOSE_HALF = 2
    ROLL = 3
    ADJUST = 4
    
    @classmethod
    def from_string(cls, action: str) -> int:
        """Convert string action to label"""
        mapping = {
            'hold': cls.HOLD,
            'close': cls.CLOSE,
            'close_full': cls.CLOSE,
            'close_half': cls.CLOSE_HALF,
            'close_partial': cls.CLOSE_HALF,
            'roll': cls.ROLL,
            'roll_out': cls.ROLL,
            'adjust': cls.ADJUST,
        }
        return mapping.get(action.lower(), cls.HOLD)
    
    @classmethod
    def to_string(cls, label: int) -> str:
        """Convert label to string"""
        mapping = {
            cls.HOLD: 'hold',
            cls.CLOSE: 'close',
            cls.CLOSE_HALF: 'close_half',
            cls.ROLL: 'roll',
            cls.ADJUST: 'adjust',
        }
        return mapping.get(label, 'hold')
    
    @classmethod
    def num_classes(cls) -> int:
        return 5


# =============================================================================
# Simple Decision Tree Classifier (No sklearn dependency)
# =============================================================================

class SimpleDecisionNode:
    """Single node in decision tree"""
    
    def __init__(self):
        self.feature_idx: int = 0
        self.threshold: float = 0.0
        self.left = None   # <= threshold
        self.right = None  # > threshold
        self.is_leaf: bool = False
        self.prediction: int = 0
        self.confidence: float = 0.0


class SimpleDecisionTree:
    """
    Simple decision tree classifier.
    
    Implements basic CART algorithm without external dependencies.
    Good enough for pattern recognition with small datasets.
    """
    
    def __init__(self, max_depth: int = 5, min_samples_split: int = 5):
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.root: Optional[SimpleDecisionNode] = None
        self.n_features: int = 0
        self.n_classes: int = 0
    
    def fit(self, X: np.ndarray, y: np.ndarray):
        """
        Fit decision tree to data.
        
        Args:
            X: Features (n_samples, n_features)
            y: Labels (n_samples,)
        """
        self.n_features = X.shape[1]
        self.n_classes = len(np.unique(y))
        self.root = self._build_tree(X, y, depth=0)
        logger.info(f"Trained decision tree with {self.n_features} features")
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict class labels"""
        if self.root is None:
            raise ValueError("Tree not fitted")
        
        predictions = np.array([self._predict_single(x) for x in X])
        return predictions
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict class probabilities (simplified)"""
        predictions = self.predict(X)
        # Return one-hot with confidence
        proba = np.zeros((len(X), self.n_classes))
        for i, pred in enumerate(predictions):
            proba[i, pred] = 1.0
        return proba
    
    def _build_tree(self, X: np.ndarray, y: np.ndarray, depth: int) -> SimpleDecisionNode:
        """Recursively build tree"""
        node = SimpleDecisionNode()
        
        # Check stopping conditions
        if depth >= self.max_depth or len(y) < self.min_samples_split or len(np.unique(y)) == 1:
            node.is_leaf = True
            node.prediction = self._most_common(y)
            node.confidence = np.mean(y == node.prediction)
            return node
        
        # Find best split
        best_feature, best_threshold, best_gain = self._find_best_split(X, y)
        
        if best_gain <= 0:
            node.is_leaf = True
            node.prediction = self._most_common(y)
            node.confidence = np.mean(y == node.prediction)
            return node
        
        # Split data
        left_mask = X[:, best_feature] <= best_threshold
        right_mask = ~left_mask
        
        node.feature_idx = best_feature
        node.threshold = best_threshold
        node.left = self._build_tree(X[left_mask], y[left_mask], depth + 1)
        node.right = self._build_tree(X[right_mask], y[right_mask], depth + 1)
        
        return node
    
    def _find_best_split(self, X: np.ndarray, y: np.ndarray) -> Tuple[int, float, float]:
        """Find best feature and threshold to split on"""
        best_gain = -float('inf')
        best_feature = 0
        best_threshold = 0.0
        
        current_gini = self._gini(y)
        
        for feature_idx in range(X.shape[1]):
            thresholds = np.unique(X[:, feature_idx])
            
            for threshold in thresholds:
                left_mask = X[:, feature_idx] <= threshold
                right_mask = ~left_mask
                
                if np.sum(left_mask) < 2 or np.sum(right_mask) < 2:
                    continue
                
                left_gini = self._gini(y[left_mask])
                right_gini = self._gini(y[right_mask])
                
                n_left = np.sum(left_mask)
                n_right = np.sum(right_mask)
                n_total = len(y)
                
                weighted_gini = (n_left / n_total) * left_gini + (n_right / n_total) * right_gini
                gain = current_gini - weighted_gini
                
                if gain > best_gain:
                    best_gain = gain
                    best_feature = feature_idx
                    best_threshold = threshold
        
        return best_feature, best_threshold, best_gain
    
    def _gini(self, y: np.ndarray) -> float:
        """Calculate Gini impurity"""
        if len(y) == 0:
            return 0.0
        
        counts = np.bincount(y)
        probs = counts / len(y)
        return 1.0 - np.sum(probs ** 2)
    
    def _most_common(self, y: np.ndarray) -> int:
        """Find most common class"""
        if len(y) == 0:
            return 0
        counts = np.bincount(y)
        return int(np.argmax(counts))
    
    def _predict_single(self, x: np.ndarray) -> int:
        """Predict single sample"""
        node = self.root
        while not node.is_leaf:
            if x[node.feature_idx] <= node.threshold:
                node = node.left
            else:
                node = node.right
        return node.prediction


# =============================================================================
# Pattern Recognizer
# =============================================================================

@dataclass
class PatternMatch:
    """Result of pattern matching"""
    pattern_name: str
    confidence: float
    suggested_action: str
    historical_win_rate: float
    historical_avg_pnl: float
    similar_events: List[str] = field(default_factory=list)


class PatternRecognizer:
    """
    Recognize patterns from historical trades.
    
    Uses supervised learning to identify:
    1. What action you typically take in similar situations
    2. What the typical outcome is
    
    Usage:
        recognizer = PatternRecognizer()
        
        # Train on your history
        recognizer.fit(X_train, y_train, outcomes)
        
        # Predict for new situation
        pattern = recognizer.predict(current_state)
        print(f"Suggested action: {pattern.suggested_action}")
        print(f"Historical win rate: {pattern.historical_win_rate}")
    """
    
    def __init__(self, model_path: str = None):
        self.action_model = SimpleDecisionTree(max_depth=6)
        self.outcome_model = SimpleDecisionTree(max_depth=4)
        self.is_fitted = False
        self.model_path = model_path
        
        # Statistics per action
        self.action_stats: Dict[int, Dict] = {}
        
        # Feature names for interpretability
        self.feature_names: List[str] = []
    
    def fit(
        self,
        X: np.ndarray,
        y_actions: np.ndarray,
        y_outcomes: np.ndarray = None,
        feature_names: List[str] = None
    ):
        """
        Fit the recognizer on historical data.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y_actions: Action labels taken (n_samples,)
            y_outcomes: Binary outcome - 1=win, 0=loss (optional)
            feature_names: Names of features for interpretability
        """
        if len(X) < 10:
            logger.warning(f"Only {len(X)} samples - need more data for reliable patterns")
        
        # Store feature names
        self.feature_names = feature_names or [f"feature_{i}" for i in range(X.shape[1])]
        
        # Fit action predictor
        logger.info(f"Training action predictor on {len(X)} samples...")
        self.action_model.fit(X, y_actions.astype(int))
        
        # Fit outcome predictor if outcomes provided
        if y_outcomes is not None:
            logger.info("Training outcome predictor...")
            self.outcome_model.fit(X, y_outcomes.astype(int))
        
        # Calculate per-action statistics
        self._calculate_action_stats(y_actions, y_outcomes)
        
        self.is_fitted = True
        logger.info("Pattern recognizer training complete")
    
    def predict(self, X: np.ndarray) -> List[PatternMatch]:
        """
        Predict patterns for new states.
        
        Args:
            X: Feature matrix (n_samples, n_features) or single sample
            
        Returns:
            List of PatternMatch objects
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted - call fit() first")
        
        # Handle single sample
        if X.ndim == 1:
            X = X.reshape(1, -1)
        
        results = []
        
        for i, x in enumerate(X):
            # Predict action
            action_pred = self.action_model.predict(x.reshape(1, -1))[0]
            action_name = ActionLabels.to_string(action_pred)
            
            # Get confidence (simplified)
            confidence = 0.7  # Placeholder - would use predict_proba
            
            # Get historical stats for this action
            stats = self.action_stats.get(action_pred, {})
            win_rate = stats.get('win_rate', 0.5)
            avg_pnl = stats.get('avg_pnl', 0.0)
            
            pattern = PatternMatch(
                pattern_name=f"{action_name}_pattern",
                confidence=confidence,
                suggested_action=action_name,
                historical_win_rate=win_rate,
                historical_avg_pnl=avg_pnl
            )
            results.append(pattern)
        
        return results
    
    def _calculate_action_stats(self, y_actions: np.ndarray, y_outcomes: np.ndarray = None):
        """Calculate statistics per action"""
        unique_actions = np.unique(y_actions)
        
        for action in unique_actions:
            mask = y_actions == action
            count = np.sum(mask)
            
            stats = {
                'count': int(count),
                'frequency': count / len(y_actions)
            }
            
            if y_outcomes is not None:
                action_outcomes = y_outcomes[mask]
                stats['win_rate'] = float(np.mean(action_outcomes))
                stats['avg_pnl'] = 0.0  # Would need actual P&L data
            
            self.action_stats[int(action)] = stats
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance (simplified)"""
        # For decision tree, importance is based on how often feature is used
        # This is a simplified version
        importance = {name: 0.0 for name in self.feature_names}
        
        def traverse(node, depth=0):
            if node is None or node.is_leaf:
                return
            
            feature_name = self.feature_names[node.feature_idx]
            importance[feature_name] += 1.0 / (depth + 1)
            
            traverse(node.left, depth + 1)
            traverse(node.right, depth + 1)
        
        traverse(self.action_model.root)
        
        # Normalize
        total = sum(importance.values())
        if total > 0:
            importance = {k: v / total for k, v in importance.items()}
        
        return importance
    
    def save(self, filepath: str = None):
        """Save model to file"""
        path = filepath or self.model_path
        if not path:
            raise ValueError("No filepath specified")
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'wb') as f:
            pickle.dump({
                'action_model': self.action_model,
                'outcome_model': self.outcome_model,
                'action_stats': self.action_stats,
                'feature_names': self.feature_names,
                'is_fitted': self.is_fitted
            }, f)
        
        logger.info(f"Saved model to {path}")
    
    def load(self, filepath: str = None):
        """Load model from file"""
        path = filepath or self.model_path
        if not path:
            raise ValueError("No filepath specified")
        
        with open(path, 'rb') as f:
            data = pickle.load(f)
        
        self.action_model = data['action_model']
        self.outcome_model = data['outcome_model']
        self.action_stats = data['action_stats']
        self.feature_names = data['feature_names']
        self.is_fitted = data['is_fitted']
        
        logger.info(f"Loaded model from {path}")


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    # Generate synthetic training data
    np.random.seed(42)
    
    n_samples = 100
    n_features = 10
    
    # Features: profit%, dte, delta, iv_rank, etc.
    X = np.random.randn(n_samples, n_features)
    
    # Simulate labels: high profit -> CLOSE, low DTE -> CLOSE, else HOLD
    y_actions = np.zeros(n_samples, dtype=int)
    y_actions[X[:, 0] > 0.5] = ActionLabels.CLOSE  # High profit -> close
    y_actions[X[:, 1] < -1.0] = ActionLabels.CLOSE  # Low DTE -> close
    y_actions[X[:, 2] > 1.0] = ActionLabels.ROLL    # High delta -> roll
    
    # Outcomes: 60% win rate
    y_outcomes = (np.random.rand(n_samples) > 0.4).astype(int)
    
    # Train
    recognizer = PatternRecognizer()
    recognizer.fit(
        X, y_actions, y_outcomes,
        feature_names=[f"feature_{i}" for i in range(n_features)]
    )
    
    # Test prediction
    test_sample = np.random.randn(1, n_features)
    test_sample[0, 0] = 1.0  # High profit
    
    patterns = recognizer.predict(test_sample)
    
    print("Pattern Recognition Results:")
    for pattern in patterns:
        print(f"  Suggested: {pattern.suggested_action}")
        print(f"  Confidence: {pattern.confidence:.2f}")
        print(f"  Historical Win Rate: {pattern.historical_win_rate:.2f}")
    
    print("\nFeature Importance:")
    importance = recognizer.get_feature_importance()
    for name, imp in sorted(importance.items(), key=lambda x: -x[1])[:5]:
        print(f"  {name}: {imp:.3f}")
    
    print("\nAction Statistics:")
    for action, stats in recognizer.action_stats.items():
        print(f"  {ActionLabels.to_string(action)}: {stats}")
