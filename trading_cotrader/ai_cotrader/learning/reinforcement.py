"""
Reinforcement Learning Module

Implements RL agents for learning optimal trading decisions.
Starts simple (Q-learning), can extend to DQN/PPO later.

Key Concepts:
- State: Market + Position + Portfolio features
- Action: HOLD, CLOSE, ROLL, etc.
- Reward: Risk-adjusted P&L
- Policy: What action to take in each state
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any, Callable
from datetime import datetime
from collections import defaultdict
import numpy as np
import logging
import pickle
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# RL Actions
# =============================================================================

class RLActions:
    """Action space for RL agent"""
    
    HOLD = 0
    CLOSE_FULL = 1
    CLOSE_HALF = 2
    ROLL_OUT = 3
    ROLL_UP = 4
    ROLL_DOWN = 5
    TAKE_PROFIT = 6
    
    ALL_ACTIONS = [HOLD, CLOSE_FULL, CLOSE_HALF, ROLL_OUT, ROLL_UP, ROLL_DOWN, TAKE_PROFIT]
    
    @classmethod
    def num_actions(cls) -> int:
        return len(cls.ALL_ACTIONS)
    
    @classmethod
    def to_string(cls, action: int) -> str:
        mapping = {
            cls.HOLD: 'hold',
            cls.CLOSE_FULL: 'close_full',
            cls.CLOSE_HALF: 'close_half',
            cls.ROLL_OUT: 'roll_out',
            cls.ROLL_UP: 'roll_up',
            cls.ROLL_DOWN: 'roll_down',
            cls.TAKE_PROFIT: 'take_profit',
        }
        return mapping.get(action, 'unknown')


# =============================================================================
# Reward Functions
# =============================================================================

class RewardFunction:
    """
    Calculate rewards for RL training.
    
    The reward function is CRITICAL - it defines what "good" means.
    """
    
    def __init__(
        self,
        pnl_weight: float = 1.0,
        risk_penalty_weight: float = 0.1,
        time_efficiency_weight: float = 0.05,
        rule_compliance_weight: float = 0.02
    ):
        self.pnl_weight = pnl_weight
        self.risk_penalty = risk_penalty_weight
        self.time_efficiency = time_efficiency_weight
        self.rule_compliance = rule_compliance_weight
    
    def calculate(
        self,
        action: int,
        pnl_before: float,
        pnl_after: float,
        max_risk: float,
        current_risk: float,
        days_held: int,
        max_days: int,
        followed_rules: bool = True
    ) -> float:
        """
        Calculate reward for a state transition.
        
        Args:
            action: Action taken
            pnl_before: P&L before action
            pnl_after: P&L after action (next state)
            max_risk: Maximum risk for position
            current_risk: Current risk
            days_held: Days in trade
            max_days: Max expected days (DTE at entry)
            followed_rules: Did action follow predefined rules?
            
        Returns:
            Reward value
        """
        # Normalize P&L by max risk
        normalized_pnl = pnl_after / max(max_risk, 1.0)
        pnl_reward = self.pnl_weight * normalized_pnl
        
        # Risk penalty - penalize if risk increased
        risk_ratio = current_risk / max(max_risk, 1.0)
        risk_penalty = -self.risk_penalty * max(0, risk_ratio - 1.0)
        
        # Time efficiency - bonus for closing winners early
        time_bonus = 0.0
        if pnl_after > 0 and action in [RLActions.CLOSE_FULL, RLActions.TAKE_PROFIT]:
            time_remaining_pct = max(0, (max_days - days_held) / max(max_days, 1))
            time_bonus = self.time_efficiency * time_remaining_pct
        
        # Rule compliance bonus
        rule_bonus = self.rule_compliance if followed_rules else 0.0
        
        total_reward = pnl_reward + risk_penalty + time_bonus + rule_bonus
        
        return float(total_reward)
    
    def calculate_terminal(
        self,
        final_pnl: float,
        max_risk: float,
        days_held: int,
        max_days: int
    ) -> float:
        """
        Calculate terminal reward when trade closes.
        
        This is the main signal - did we make or lose money?
        """
        # Normalize by risk
        pnl_ratio = final_pnl / max(max_risk, 1.0)
        
        # Base reward: simple P&L
        reward = self.pnl_weight * pnl_ratio
        
        # Bonus for quick wins
        if final_pnl > 0:
            efficiency = 1.0 - (days_held / max(max_days, 1))
            reward += self.time_efficiency * efficiency
        
        # Penalty for holding losers too long
        if final_pnl < 0 and days_held > max_days * 0.8:
            reward -= self.time_efficiency * 0.5
        
        return float(reward)


# =============================================================================
# Experience Replay Buffer
# =============================================================================

@dataclass
class Experience:
    """Single experience tuple for replay"""
    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool


class ReplayBuffer:
    """
    Experience replay buffer for RL training.
    
    Stores transitions and samples mini-batches for training.
    """
    
    def __init__(self, capacity: int = 10000):
        self.capacity = capacity
        self.buffer: List[Experience] = []
        self.position = 0
    
    def push(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool
    ):
        """Add experience to buffer"""
        exp = Experience(state, action, reward, next_state, done)
        
        if len(self.buffer) < self.capacity:
            self.buffer.append(exp)
        else:
            self.buffer[self.position] = exp
        
        self.position = (self.position + 1) % self.capacity
    
    def sample(self, batch_size: int) -> List[Experience]:
        """Sample random batch"""
        indices = np.random.choice(len(self.buffer), min(batch_size, len(self.buffer)), replace=False)
        return [self.buffer[i] for i in indices]
    
    def __len__(self) -> int:
        return len(self.buffer)


# =============================================================================
# Tabular Q-Learning Agent
# =============================================================================

class QLearningAgent:
    """
    Tabular Q-Learning agent.
    
    Simple but effective for small state spaces.
    Uses state discretization for continuous features.
    
    Usage:
        agent = QLearningAgent(state_dim=10, n_actions=7)
        
        # Training loop
        for episode in episodes:
            state = env.reset()
            done = False
            
            while not done:
                action = agent.select_action(state)
                next_state, reward, done = env.step(action)
                agent.update(state, action, reward, next_state, done)
                state = next_state
        
        # Use trained agent
        action = agent.select_action(state, explore=False)
    """
    
    def __init__(
        self,
        state_dim: int,
        n_actions: int = 7,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.1,
        epsilon_decay: float = 0.995,
        n_bins: int = 10
    ):
        """
        Args:
            state_dim: Dimension of state vector
            n_actions: Number of possible actions
            learning_rate: Q-learning rate (alpha)
            discount_factor: Future reward discount (gamma)
            epsilon_start: Initial exploration rate
            epsilon_end: Minimum exploration rate
            epsilon_decay: Epsilon decay per episode
            n_bins: Number of bins for state discretization
        """
        self.state_dim = state_dim
        self.n_actions = n_actions
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.n_bins = n_bins
        
        # Q-table: maps discretized state -> action values
        self.q_table: Dict[tuple, np.ndarray] = defaultdict(
            lambda: np.zeros(n_actions)
        )
        
        # Statistics
        self.episode_rewards: List[float] = []
        self.training_steps = 0
    
    def discretize_state(self, state: np.ndarray) -> tuple:
        """
        Convert continuous state to discrete bins.
        
        Each feature is mapped to one of n_bins.
        """
        # Clip to reasonable range and bin
        clipped = np.clip(state, -3, 3)  # Assume normalized features
        binned = np.digitize(clipped, np.linspace(-3, 3, self.n_bins))
        return tuple(binned)
    
    def select_action(self, state: np.ndarray, explore: bool = True) -> int:
        """
        Select action using epsilon-greedy policy.
        
        Args:
            state: Current state vector
            explore: Whether to use exploration (False for inference)
            
        Returns:
            Selected action index
        """
        if explore and np.random.random() < self.epsilon:
            return np.random.randint(self.n_actions)
        
        discrete_state = self.discretize_state(state)
        q_values = self.q_table[discrete_state]
        return int(np.argmax(q_values))
    
    def update(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool
    ):
        """
        Update Q-values using Q-learning update rule.
        
        Q(s,a) = Q(s,a) + α * (r + γ * max(Q(s',a')) - Q(s,a))
        """
        discrete_state = self.discretize_state(state)
        discrete_next_state = self.discretize_state(next_state)
        
        current_q = self.q_table[discrete_state][action]
        
        if done:
            target = reward
        else:
            next_max_q = np.max(self.q_table[discrete_next_state])
            target = reward + self.gamma * next_max_q
        
        # Q-learning update
        self.q_table[discrete_state][action] += self.lr * (target - current_q)
        
        self.training_steps += 1
    
    def decay_epsilon(self):
        """Decay exploration rate after each episode"""
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)
    
    def get_q_values(self, state: np.ndarray) -> np.ndarray:
        """Get Q-values for a state"""
        discrete_state = self.discretize_state(state)
        return self.q_table[discrete_state].copy()
    
    def get_best_action(self, state: np.ndarray) -> Tuple[int, float]:
        """Get best action and its Q-value"""
        q_values = self.get_q_values(state)
        best_action = int(np.argmax(q_values))
        return best_action, q_values[best_action]
    
    def save(self, filepath: str):
        """Save agent to file"""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'wb') as f:
            pickle.dump({
                'q_table': dict(self.q_table),
                'state_dim': self.state_dim,
                'n_actions': self.n_actions,
                'lr': self.lr,
                'gamma': self.gamma,
                'epsilon': self.epsilon,
                'epsilon_end': self.epsilon_end,
                'epsilon_decay': self.epsilon_decay,
                'n_bins': self.n_bins,
                'episode_rewards': self.episode_rewards,
                'training_steps': self.training_steps
            }, f)
        
        logger.info(f"Saved Q-learning agent to {filepath}")
    
    def load(self, filepath: str):
        """Load agent from file"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        
        self.q_table = defaultdict(lambda: np.zeros(self.n_actions), data['q_table'])
        self.state_dim = data['state_dim']
        self.n_actions = data['n_actions']
        self.lr = data['lr']
        self.gamma = data['gamma']
        self.epsilon = data['epsilon']
        self.epsilon_end = data['epsilon_end']
        self.epsilon_decay = data['epsilon_decay']
        self.n_bins = data['n_bins']
        self.episode_rewards = data['episode_rewards']
        self.training_steps = data['training_steps']
        
        logger.info(f"Loaded Q-learning agent from {filepath}")


# =============================================================================
# Deep Q-Network Agent (Simple Implementation)
# =============================================================================

class SimpleNeuralNetwork:
    """
    Simple neural network using only numpy.
    Two hidden layers with ReLU activation.
    """
    
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        
        # Initialize weights (Xavier initialization)
        self.W1 = np.random.randn(input_dim, hidden_dim) * np.sqrt(2.0 / input_dim)
        self.b1 = np.zeros(hidden_dim)
        self.W2 = np.random.randn(hidden_dim, hidden_dim) * np.sqrt(2.0 / hidden_dim)
        self.b2 = np.zeros(hidden_dim)
        self.W3 = np.random.randn(hidden_dim, output_dim) * np.sqrt(2.0 / hidden_dim)
        self.b3 = np.zeros(output_dim)
    
    def forward(self, x: np.ndarray) -> np.ndarray:
        """Forward pass"""
        # Layer 1
        h1 = np.dot(x, self.W1) + self.b1
        h1 = np.maximum(0, h1)  # ReLU
        
        # Layer 2
        h2 = np.dot(h1, self.W2) + self.b2
        h2 = np.maximum(0, h2)  # ReLU
        
        # Output layer
        out = np.dot(h2, self.W3) + self.b3
        
        return out
    
    def copy_from(self, other: 'SimpleNeuralNetwork'):
        """Copy weights from another network"""
        self.W1 = other.W1.copy()
        self.b1 = other.b1.copy()
        self.W2 = other.W2.copy()
        self.b2 = other.b2.copy()
        self.W3 = other.W3.copy()
        self.b3 = other.b3.copy()


class DQNAgent:
    """
    Deep Q-Network agent (simplified numpy implementation).
    
    For production, use PyTorch/TensorFlow version.
    This is educational/prototype only.
    
    Usage:
        agent = DQNAgent(state_dim=55, n_actions=7)
        
        # Training loop
        for state, action, reward, next_state, done in experiences:
            agent.store(state, action, reward, next_state, done)
            agent.train()
        
        # Inference
        action = agent.select_action(state, explore=False)
    """
    
    def __init__(
        self,
        state_dim: int,
        n_actions: int = 7,
        hidden_dim: int = 64,
        learning_rate: float = 0.001,
        discount_factor: float = 0.95,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.1,
        epsilon_decay: float = 0.995,
        batch_size: int = 32,
        target_update_freq: int = 100,
        buffer_size: int = 10000
    ):
        self.state_dim = state_dim
        self.n_actions = n_actions
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.target_update_freq = target_update_freq
        
        # Networks
        self.q_network = SimpleNeuralNetwork(state_dim, hidden_dim, n_actions)
        self.target_network = SimpleNeuralNetwork(state_dim, hidden_dim, n_actions)
        self.target_network.copy_from(self.q_network)
        
        # Replay buffer
        self.replay_buffer = ReplayBuffer(buffer_size)
        
        # Statistics
        self.training_steps = 0
    
    def select_action(self, state: np.ndarray, explore: bool = True) -> int:
        """Select action using epsilon-greedy"""
        if explore and np.random.random() < self.epsilon:
            return np.random.randint(self.n_actions)
        
        q_values = self.q_network.forward(state)
        return int(np.argmax(q_values))
    
    def store(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool
    ):
        """Store experience in replay buffer"""
        self.replay_buffer.push(state, action, reward, next_state, done)
    
    def train(self):
        """Train on a batch from replay buffer"""
        if len(self.replay_buffer) < self.batch_size:
            return
        
        # Sample batch
        batch = self.replay_buffer.sample(self.batch_size)
        
        # This is a simplified version - real DQN uses backprop
        # Here we just demonstrate the structure
        for exp in batch:
            # Calculate target
            if exp.done:
                target = exp.reward
            else:
                next_q = self.target_network.forward(exp.next_state)
                target = exp.reward + self.gamma * np.max(next_q)
            
            # Update Q-network (simplified - real version uses gradient descent)
            current_q = self.q_network.forward(exp.state)
            td_error = target - current_q[exp.action]
            
            # Simple update (not real backprop)
            # In production, use autograd framework
        
        self.training_steps += 1
        
        # Update target network periodically
        if self.training_steps % self.target_update_freq == 0:
            self.target_network.copy_from(self.q_network)
    
    def decay_epsilon(self):
        """Decay exploration rate"""
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)
    
    def save(self, filepath: str):
        """Save agent"""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'wb') as f:
            pickle.dump({
                'q_network': self.q_network,
                'target_network': self.target_network,
                'epsilon': self.epsilon,
                'training_steps': self.training_steps
            }, f)
    
    def load(self, filepath: str):
        """Load agent"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        self.q_network = data['q_network']
        self.target_network = data['target_network']
        self.epsilon = data['epsilon']
        self.training_steps = data['training_steps']


# =============================================================================
# Trading Advisor (Combines Supervised + RL)
# =============================================================================

class TradingAdvisor:
    """
    High-level advisor that combines supervised learning and RL.
    
    - Supervised: "What would I normally do?"
    - RL: "What's optimal based on outcomes?"
    - Combined: Weighted recommendation
    
    Usage:
        advisor = TradingAdvisor()
        
        # Load trained models
        advisor.load('models/')
        
        # Get recommendation
        rec = advisor.recommend(current_state)
        print(f"Suggested: {rec['action']}")
        print(f"Confidence: {rec['confidence']}")
        print(f"Source: {rec['source']}")  # 'supervised', 'rl', 'rules'
    """
    
    def __init__(
        self,
        supervised_model=None,
        rl_agent=None,
        supervised_weight: float = 0.4,
        rl_weight: float = 0.4,
        rules_weight: float = 0.2
    ):
        self.supervised = supervised_model
        self.rl = rl_agent
        
        self.supervised_weight = supervised_weight
        self.rl_weight = rl_weight
        self.rules_weight = rules_weight
        
        # External rules engine (optional)
        self.rules_engine = None
    
    def set_rules_engine(self, rules_engine):
        """Set external rules engine for rule-based suggestions"""
        self.rules_engine = rules_engine
    
    def recommend(
        self,
        state: np.ndarray,
        position=None,
        portfolio=None
    ) -> Dict[str, Any]:
        """
        Get combined recommendation.
        
        Args:
            state: Current state vector
            position: Position object (optional, for rules)
            portfolio: Portfolio object (optional, for rules)
            
        Returns:
            Dict with action, confidence, reasoning
        """
        recommendations = []
        
        # Get supervised prediction
        if self.supervised and self.supervised.is_fitted:
            patterns = self.supervised.predict(state)
            if patterns:
                pattern = patterns[0]
                recommendations.append({
                    'source': 'supervised',
                    'action': pattern.suggested_action,
                    'confidence': pattern.confidence,
                    'weight': self.supervised_weight,
                    'reasoning': f"Based on similar past decisions (win rate: {pattern.historical_win_rate:.0%})"
                })
        
        # Get RL prediction
        if self.rl:
            action, q_value = self.rl.get_best_action(state)
            action_name = RLActions.to_string(action)
            
            # Convert Q-value to pseudo-confidence
            q_values = self.rl.get_q_values(state)
            confidence = np.exp(q_value) / np.sum(np.exp(q_values))  # Softmax
            
            recommendations.append({
                'source': 'rl',
                'action': action_name,
                'confidence': float(confidence),
                'weight': self.rl_weight,
                'reasoning': f"RL agent suggests based on expected value (Q={q_value:.2f})"
            })
        
        # Get rules-based prediction
        if self.rules_engine and position:
            from services.position_mgmt import ActionType
            rule_action = self.rules_engine.evaluate_position(position)
            if rule_action.should_act():
                recommendations.append({
                    'source': 'rules',
                    'action': rule_action.action.value,
                    'confidence': 0.9 if rule_action.priority.value <= 2 else 0.7,
                    'weight': self.rules_weight,
                    'reasoning': rule_action.primary_reason
                })
        
        # Combine recommendations
        if not recommendations:
            return {
                'action': 'hold',
                'confidence': 0.5,
                'source': 'default',
                'reasoning': 'No models available, defaulting to hold',
                'all_recommendations': []
            }
        
        # Weighted voting
        action_scores = defaultdict(float)
        for rec in recommendations:
            score = rec['confidence'] * rec['weight']
            action_scores[rec['action']] += score
        
        # Select highest scoring action
        best_action = max(action_scores, key=action_scores.get)
        total_weight = sum(rec['weight'] for rec in recommendations)
        best_confidence = action_scores[best_action] / total_weight
        
        # Find primary source
        primary = max(
            [r for r in recommendations if r['action'] == best_action],
            key=lambda r: r['confidence'] * r['weight']
        )
        
        return {
            'action': best_action,
            'confidence': float(best_confidence),
            'source': primary['source'],
            'reasoning': primary['reasoning'],
            'all_recommendations': recommendations
        }
    
    def save(self, model_dir: str):
        """Save all models"""
        path = Path(model_dir)
        path.mkdir(parents=True, exist_ok=True)
        
        if self.supervised:
            self.supervised.save(str(path / 'supervised.pkl'))
        
        if self.rl:
            self.rl.save(str(path / 'rl_agent.pkl'))
    
    def load(self, model_dir: str):
        """Load all models"""
        path = Path(model_dir)
        
        supervised_path = path / 'supervised.pkl'
        if supervised_path.exists():
            from ai_cotrader.learning.supervised import PatternRecognizer
            self.supervised = PatternRecognizer()
            self.supervised.load(str(supervised_path))
        
        rl_path = path / 'rl_agent.pkl'
        if rl_path.exists():
            self.rl = QLearningAgent(state_dim=55, n_actions=7)
            self.rl.load(str(rl_path))


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    # Create Q-learning agent
    state_dim = 10
    agent = QLearningAgent(state_dim=state_dim, n_actions=RLActions.num_actions())
    
    # Simulate training
    print("Training Q-learning agent...")
    
    for episode in range(100):
        state = np.random.randn(state_dim)
        episode_reward = 0
        
        for step in range(20):
            # Select action
            action = agent.select_action(state)
            
            # Simulate environment (fake rewards)
            next_state = state + np.random.randn(state_dim) * 0.1
            
            # Reward: positive for CLOSE when "profit" is high
            fake_profit = state[0]  # First feature is "profit"
            if action == RLActions.CLOSE_FULL and fake_profit > 0.5:
                reward = 1.0
            elif action == RLActions.HOLD and fake_profit < 0.5:
                reward = 0.1
            else:
                reward = -0.1
            
            done = step == 19
            
            # Update agent
            agent.update(state, action, reward, next_state, done)
            
            episode_reward += reward
            state = next_state
        
        agent.decay_epsilon()
        agent.episode_rewards.append(episode_reward)
        
        if (episode + 1) % 20 == 0:
            avg_reward = np.mean(agent.episode_rewards[-20:])
            print(f"Episode {episode + 1}, Avg Reward: {avg_reward:.2f}, Epsilon: {agent.epsilon:.2f}")
    
    # Test trained agent
    print("\nTesting trained agent:")
    test_state = np.random.randn(state_dim)
    test_state[0] = 1.5  # High "profit"
    
    action, q_value = agent.get_best_action(test_state)
    print(f"State (profit={test_state[0]:.2f}): Action={RLActions.to_string(action)}, Q={q_value:.2f}")
    
    test_state[0] = -0.5  # Low "profit"
    action, q_value = agent.get_best_action(test_state)
    print(f"State (profit={test_state[0]:.2f}): Action={RLActions.to_string(action)}, Q={q_value:.2f}")
