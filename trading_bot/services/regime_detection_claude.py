"""
Market Regime Detection using Hidden Markov Models and K-Means Clustering
States: Bull, Correction, Bear, Capitulation
"""

import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from hmmlearn import hmm
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

class MarketRegimeDetector:
    def __init__(self, ticker="SPY", history_years=10):
        """
        Initialize regime detector.
        
        Args:
            ticker: Market index to analyze (default SPY)
            history_years: Years of historical data to train on
        """
        self.ticker = ticker
        self.history_years = history_years
        self.data = None
        self.features = None
        self.hmm_model = None
        self.kmeans_model = None
        self.regime_history = None
        
        # Regime definitions
        self.regime_names = {
            0: "🟢 BULL",
            1: "🟡 CORRECTION", 
            2: "🔴 BEAR",
            3: "⚫ CAPITULATION"
        }
        
    def fetch_data(self):
        """Download historical market data."""
        print(f"📥 Fetching {self.history_years} years of {self.ticker} data...")
        
        try:
            ticker_obj = yf.Ticker(self.ticker)
            self.data = ticker_obj.history(period=f"{self.history_years}y")
            
            if len(self.data) == 0:
                raise ValueError("No data returned")
                
            print(f"✅ Downloaded {len(self.data)} trading days")
            return True
            
        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            return False
    
    def engineer_features(self, window=60):
        """
        Create features for regime detection.
        
        Features:
        - Returns (1d, 5d, 20d)
        - Volatility (rolling std)
        - Volume trends
        - RSI
        - Distance from moving averages
        """
        df = self.data.copy()
        
        # Returns
        df['return_1d'] = df['Close'].pct_change()
        df['return_5d'] = df['Close'].pct_change(5)
        df['return_20d'] = df['Close'].pct_change(20)
        
        # Volatility (annualized)
        df['volatility'] = df['return_1d'].rolling(window=20).std() * np.sqrt(252)
        
        # Volume ratio (current vs 20-day average)
        df['volume_ratio'] = df['Volume'] / df['Volume'].rolling(window=20).mean()
        
        # RSI (14-day)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Moving average distances
        df['ma_50'] = df['Close'].rolling(window=50).mean()
        df['ma_200'] = df['Close'].rolling(window=200).mean()
        df['dist_ma50'] = (df['Close'] / df['ma_50'] - 1) * 100
        df['dist_ma200'] = (df['Close'] / df['ma_200'] - 1) * 100
        
        # Drawdown from peak
        df['peak'] = df['Close'].expanding().max()
        df['drawdown'] = (df['Close'] / df['peak'] - 1) * 100
        
        # Rolling max drawdown over 60 days
        df['max_dd_60d'] = df['drawdown'].rolling(window=60).min()
        
        # Select features for modeling
        feature_cols = [
            'return_1d', 'return_5d', 'return_20d',
            'volatility', 'volume_ratio', 'rsi',
            'dist_ma50', 'dist_ma200', 'drawdown', 'max_dd_60d'
        ]
        
        self.features = df[feature_cols].dropna()
        print(f"✅ Engineered {len(feature_cols)} features for {len(self.features)} days")
        
        return self.features
    
    def train_kmeans(self, n_clusters=4):
        """
        Train K-Means clustering model.
        
        Args:
            n_clusters: Number of market regimes (default 4)
        """
        print(f"\n🔄 Training K-Means with {n_clusters} regimes...")
        
        # Normalize features
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(self.features)
        
        # Train K-Means
        self.kmeans_model = KMeans(
            n_clusters=n_clusters,
            random_state=42,
            n_init=50,
            max_iter=500
        )
        
        clusters = self.kmeans_model.fit_predict(features_scaled)
        
        # Map clusters to regimes based on average returns
        cluster_stats = {}
        for i in range(n_clusters):
            mask = clusters == i
            cluster_stats[i] = {
                'avg_return': self.features.loc[mask, 'return_20d'].mean(),
                'avg_vol': self.features.loc[mask, 'volatility'].mean(),
                'avg_dd': self.features.loc[mask, 'drawdown'].mean(),
                'count': mask.sum()
            }
        
        # Sort by return (highest to lowest) and assign regime labels
        sorted_clusters = sorted(cluster_stats.items(), 
                                key=lambda x: x[1]['avg_return'], 
                                reverse=True)
        
        # Map: Best performing = Bull, Worst = Capitulation
        cluster_to_regime = {}
        for idx, (cluster_id, stats) in enumerate(sorted_clusters):
            if idx == 0:
                cluster_to_regime[cluster_id] = 0  # Bull
            elif idx == len(sorted_clusters) - 1:
                cluster_to_regime[cluster_id] = 3  # Capitulation
            elif stats['avg_dd'] < -15:
                cluster_to_regime[cluster_id] = 2  # Bear
            else:
                cluster_to_regime[cluster_id] = 1  # Correction
        
        # Apply mapping
        regimes = np.array([cluster_to_regime[c] for c in clusters])
        
        self.regime_history = pd.DataFrame({
            'date': self.features.index,
            'regime': regimes,
            'regime_name': [self.regime_names[r] for r in regimes]
        })
        
        print("✅ K-Means training complete")
        self._print_regime_stats(cluster_stats, cluster_to_regime)
        
        return regimes
    
    def train_hmm(self, n_states=4):
        """
        Train Hidden Markov Model for regime detection.
        
        Args:
            n_states: Number of hidden states (market regimes)
        """
        print(f"\n🔄 Training Hidden Markov Model with {n_states} states...")
        
        # Use returns and volatility as observations
        observations = self.features[['return_1d', 'volatility']].values
        
        # Initialize HMM with Gaussian emissions
        self.hmm_model = hmm.GaussianHMM(
            n_components=n_states,
            covariance_type="full",
            n_iter=1000,
            random_state=42
        )
        
        # Train model
        self.hmm_model.fit(observations)
        
        # Predict states
        states = self.hmm_model.predict(observations)
        
        # Map states to regimes (similar logic as K-Means)
        state_stats = {}
        for i in range(n_states):
            mask = states == i
            state_stats[i] = {
                'avg_return': self.features.loc[mask, 'return_20d'].mean(),
                'avg_vol': self.features.loc[mask, 'volatility'].mean(),
                'count': mask.sum()
            }
        
        sorted_states = sorted(state_stats.items(), 
                              key=lambda x: x[1]['avg_return'], 
                              reverse=True)
        
        state_to_regime = {state: idx for idx, (state, _) in enumerate(sorted_states)}
        regimes = np.array([state_to_regime[s] for s in states])
        
        self.regime_history = pd.DataFrame({
            'date': self.features.index,
            'regime': regimes,
            'regime_name': [self.regime_names[r] for r in regimes]
        })
        
        print("✅ HMM training complete")
        
        return regimes
    
    def _print_regime_stats(self, stats, mapping):
        """Print regime statistics."""
        print("\n📊 Regime Characteristics:")
        print("─" * 80)
        
        for cluster_id, regime_id in mapping.items():
            s = stats[cluster_id]
            print(f"\n{self.regime_names[regime_id]}:")
            print(f"  • Average 20D Return: {s['avg_return']*100:.2f}%")
            print(f"  • Average Volatility: {s['avg_vol']:.2f}%")
            print(f"  • Average Drawdown: {s['avg_dd']:.2f}%")
            print(f"  • Days in regime: {s['count']} ({s['count']/len(self.features)*100:.1f}%)")
    
    def calculate_transition_matrix(self):
        """Calculate regime transition probabilities."""
        if self.regime_history is None:
            print("❌ No regime history available. Train a model first.")
            return None
        
        regimes = self.regime_history['regime'].values
        n_states = len(self.regime_names)
        
        # Initialize transition matrix
        transitions = np.zeros((n_states, n_states))
        
        # Count transitions
        for i in range(len(regimes) - 1):
            current = regimes[i]
            next_state = regimes[i + 1]
            transitions[current, next_state] += 1
        
        # Normalize to get probabilities
        transition_probs = transitions / transitions.sum(axis=1, keepdims=True)
        transition_probs = np.nan_to_num(transition_probs)  # Handle division by zero
        
        return transition_probs
    
    def print_transition_matrix(self):
        """Display transition probability matrix."""
        trans_matrix = self.calculate_transition_matrix()
        
        if trans_matrix is None:
            return
        
        print("\n" + "=" * 80)
        print("REGIME TRANSITION PROBABILITY MATRIX")
        print("=" * 80)
        print("\nProbability of transitioning FROM (rows) TO (columns):\n")
        
        # Header
        header = "FROM \\ TO    |"
        for i in range(len(self.regime_names)):
            header += f" {self.regime_names[i]:^15} |"
        print(header)
        print("─" * len(header))
        
        # Rows
        for i in range(len(self.regime_names)):
            row = f"{self.regime_names[i]:13} |"
            for j in range(len(self.regime_names)):
                prob = trans_matrix[i, j]
                row += f"    {prob:>6.1%}      |"
            print(row)
        
        print("\n💡 Insights:")
        # Find most stable regime (highest diagonal probability)
        diagonal = np.diag(trans_matrix)
        most_stable = np.argmax(diagonal)
        print(f"  • Most stable regime: {self.regime_names[most_stable]} ({diagonal[most_stable]:.1%} persistence)")
        
        # Find most volatile regime (lowest diagonal)
        most_volatile = np.argmin(diagonal)
        print(f"  • Most volatile regime: {self.regime_names[most_volatile]} ({diagonal[most_volatile]:.1%} persistence)")
    
    def get_current_regime(self):
        """Detect current market regime."""
        if self.regime_history is None:
            print("❌ No regime history. Train a model first.")
            return None
        
        current = self.regime_history.iloc[-1]
        
        print("\n" + "=" * 80)
        print("CURRENT MARKET REGIME DETECTION")
        print("=" * 80)
        print(f"\n📅 Date: {current['date'].strftime('%Y-%m-%d')}")
        print(f"🎯 Current Regime: {current['regime_name']}")
        
        # Get recent regime history (last 20 days)
        recent = self.regime_history.tail(20)
        regime_counts = recent['regime_name'].value_counts()
        
        print(f"\n📊 Last 20 Days Regime Distribution:")
        for regime, count in regime_counts.items():
            print(f"  • {regime}: {count} days ({count/20*100:.0f}%)")
        
        # Transition probabilities from current state
        trans_matrix = self.calculate_transition_matrix()
        current_regime_id = current['regime']
        
        print(f"\n🔮 Transition Probabilities from {current['regime_name']}:")
        for i, prob in enumerate(trans_matrix[current_regime_id]):
            if prob > 0.01:  # Only show significant probabilities
                print(f"  • → {self.regime_names[i]}: {prob:.1%}")
        
        return current
    
    def plot_regime_history(self, last_n_days=252):
        """Plot price with regime overlays."""
        try:
            import matplotlib.pyplot as plt
            
            recent_data = self.data.tail(last_n_days)
            recent_regimes = self.regime_history.tail(last_n_days)
            
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
            
            # Plot 1: Price with regime colors
            ax1.plot(recent_data.index, recent_data['Close'], 
                    color='black', linewidth=1, label='Price')
            
            # Color background by regime
            regime_colors = {0: 'green', 1: 'yellow', 2: 'red', 3: 'darkred'}
            for regime_id in range(4):
                mask = recent_regimes['regime'] == regime_id
                if mask.any():
                    regime_dates = recent_regimes.loc[mask, 'date']
                    for date in regime_dates:
                        ax1.axvspan(date, date + pd.Timedelta(days=1), 
                                   alpha=0.2, color=regime_colors[regime_id])
            
            ax1.set_ylabel('Price ($)', fontsize=12)
            ax1.set_title(f'{self.ticker} Price with Market Regimes', fontsize=14, fontweight='bold')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            
            # Plot 2: Regime timeline
            ax2.scatter(recent_regimes['date'], recent_regimes['regime'], 
                       c=[regime_colors[r] for r in recent_regimes['regime']], 
                       s=10, alpha=0.6)
            ax2.set_yticks(range(4))
            ax2.set_yticklabels([self.regime_names[i] for i in range(4)])
            ax2.set_ylabel('Regime', fontsize=12)
            ax2.set_xlabel('Date', fontsize=12)
            ax2.grid(True, alpha=0.3, axis='x')
            
            plt.tight_layout()
            plt.savefig('regime_detection.png', dpi=150, bbox_inches='tight')
            print("\n📊 Chart saved as 'regime_detection.png'")
            plt.show()
            
        except ImportError:
            print("\n⚠️  matplotlib not installed. Skipping plot.")

def main():
    """Run complete regime detection analysis."""
    
    # Initialize detector
    detector = MarketRegimeDetector(ticker="SPY", history_years=10)
    
    # Fetch data
    if not detector.fetch_data():
        return
    
    # Engineer features
    detector.engineer_features(window=60)
    
    # Train K-Means model (more interpretable)
    detector.train_kmeans(n_clusters=4)
    
    # Analyze transitions
    detector.print_transition_matrix()
    
    # Current regime
    detector.get_current_regime()
    
    # Optional: Train HMM for comparison
    # print("\n" + "="*80)
    # print("ALTERNATIVE: HIDDEN MARKOV MODEL")
    # print("="*80)
    # detector.train_hmm(n_states=4)
    # detector.print_transition_matrix()
    # detector.get_current_regime()
    
    # Plot results
    detector.plot_regime_history(last_n_days=504)  # Last 2 years
    
    print("\n✅ Analysis complete!")

if __name__ == "__main__":
    main()