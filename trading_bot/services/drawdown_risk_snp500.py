"""
Drawdown Risk Forecasting System
- Monte Carlo simulations
- VaR and CVaR calculations
- Historical analog matching
"""

import yfinance as yf
import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class DrawdownRiskForecaster:
    def __init__(self, ticker="SPY", history_years=15):
        """
        Initialize drawdown risk forecaster.
        
        Args:
            ticker: Market index to analyze
            history_years: Years of historical data
        """
        self.ticker = ticker
        self.history_years = history_years
        self.data = None
        self.returns = None
        self.current_regime = None
        
    def fetch_data(self):
        """Download historical market data."""
        print(f"📥 Fetching {self.history_years} years of {self.ticker} data...")
        
        try:
            ticker_obj = yf.Ticker(self.ticker)
            self.data = ticker_obj.history(period=f"{self.history_years}y")
            
            if len(self.data) == 0:
                raise ValueError("No data returned")
            
            # Calculate returns
            self.returns = self.data['Close'].pct_change().dropna()
            
            print(f"✅ Downloaded {len(self.data)} days, {len(self.returns)} returns")
            return True
            
        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            return False
    
    def detect_volatility_regime(self, window=60):
        """
        Detect current volatility regime.
        
        Returns:
            dict: Current volatility stats
        """
        recent_returns = self.returns.tail(window)
        
        # Calculate current volatility (annualized)
        current_vol = recent_returns.std() * np.sqrt(252)
        
        # Historical volatility distribution
        historical_vols = self.returns.rolling(window=window).std() * np.sqrt(252)
        historical_vols = historical_vols.dropna()
        
        # Percentile rank
        vol_percentile = stats.percentileofscore(historical_vols, current_vol)
        
        # Classify regime
        if vol_percentile < 25:
            regime = "🟢 LOW VOLATILITY"
        elif vol_percentile < 50:
            regime = "🟡 NORMAL VOLATILITY"
        elif vol_percentile < 75:
            regime = "🟠 ELEVATED VOLATILITY"
        else:
            regime = "🔴 HIGH VOLATILITY"
        
        self.current_regime = {
            'volatility': current_vol,
            'percentile': vol_percentile,
            'regime': regime,
            'mean_return': recent_returns.mean() * 252,  # Annualized
            'skewness': recent_returns.skew(),
            'kurtosis': recent_returns.kurtosis()
        }
        
        print("\n" + "=" * 80)
        print("CURRENT VOLATILITY REGIME")
        print("=" * 80)
        print(f"📊 Current Volatility: {current_vol:.2%}")
        print(f"📈 Historical Percentile: {vol_percentile:.1f}%")
        print(f"🎯 Regime: {regime}")
        print(f"📉 Mean Return (annualized): {self.current_regime['mean_return']:.2%}")
        print(f"⚖️  Skewness: {self.current_regime['skewness']:.3f} {'(left tail risk)' if self.current_regime['skewness'] < 0 else '(right skewed)'}")
        print(f"📊 Kurtosis: {self.current_regime['kurtosis']:.3f} {'(fat tails)' if self.current_regime['kurtosis'] > 3 else '(normal)'}")
        
        return self.current_regime
    
    def monte_carlo_simulation(self, days_forward=252, num_simulations=10000, use_regime=True):
        """
        Run Monte Carlo simulations for drawdown forecasting.
        
        Args:
            days_forward: Trading days to simulate
            num_simulations: Number of simulation paths
            use_regime: Use current regime stats vs all history
            
        Returns:
            dict: Simulation results
        """
        print(f"\n🎲 Running {num_simulations:,} Monte Carlo simulations for {days_forward} days...")
        
        # Get parameters
        if use_regime and self.current_regime:
            mu = self.current_regime['mean_return'] / 252  # Daily mean
            sigma = self.current_regime['volatility'] / np.sqrt(252)  # Daily vol
            print(f"   Using current regime: μ={mu*252:.2%}/year, σ={sigma*np.sqrt(252):.2%}/year")
        else:
            mu = self.returns.mean()
            sigma = self.returns.std()
            print(f"   Using historical: μ={mu*252:.2%}/year, σ={sigma*np.sqrt(252):.2%}/year")
        
        # Initialize price paths
        current_price = self.data['Close'].iloc[-1]
        dt = 1  # Daily steps
        
        # Generate random returns (geometric Brownian motion)
        random_returns = np.random.normal(mu, sigma, (days_forward, num_simulations))
        
        # Calculate price paths
        price_paths = np.zeros((days_forward + 1, num_simulations))
        price_paths[0] = current_price
        
        for t in range(1, days_forward + 1):
            price_paths[t] = price_paths[t-1] * (1 + random_returns[t-1])
        
        # Calculate drawdowns for each path
        max_drawdowns = np.zeros(num_simulations)
        
        for i in range(num_simulations):
            path = price_paths[:, i]
            running_max = np.maximum.accumulate(path)
            drawdown = (path / running_max - 1) * 100
            max_drawdowns[i] = drawdown.min()
        
        # Calculate final returns
        final_returns = (price_paths[-1] / current_price - 1) * 100
        
        results = {
            'price_paths': price_paths,
            'max_drawdowns': max_drawdowns,
            'final_returns': final_returns,
            'current_price': current_price,
            'params': {'mu': mu, 'sigma': sigma}
        }
        
        print(f"✅ Simulation complete")
        
        return results
    
    def calculate_var_cvar(self, simulation_results, confidence_levels=[0.95, 0.99]):
        """
        Calculate Value at Risk (VaR) and Conditional VaR (CVaR).
        
        Args:
            simulation_results: Output from monte_carlo_simulation
            confidence_levels: List of confidence levels
        """
        max_drawdowns = simulation_results['max_drawdowns']
        final_returns = simulation_results['final_returns']
        
        print("\n" + "=" * 80)
        print("VALUE AT RISK (VaR) & CONDITIONAL VAR (CVaR) ANALYSIS")
        print("=" * 80)
        
        for conf in confidence_levels:
            alpha = 1 - conf
            
            # VaR for drawdown (worst drawdown at confidence level)
            var_dd = np.percentile(max_drawdowns, alpha * 100)
            
            # CVaR for drawdown (average of drawdowns worse than VaR)
            cvar_dd = max_drawdowns[max_drawdowns <= var_dd].mean()
            
            # VaR for returns (worst return at confidence level)
            var_ret = np.percentile(final_returns, alpha * 100)
            
            # CVaR for returns
            cvar_ret = final_returns[final_returns <= var_ret].mean()
            
            print(f"\n🎯 {conf:.0%} Confidence Level:")
            print(f"   Maximum Drawdown VaR:  {var_dd:.2f}%")
            print(f"   Maximum Drawdown CVaR: {cvar_dd:.2f}%")
            print(f"   Return VaR:            {var_ret:.2f}%")
            print(f"   Return CVaR:           {cvar_ret:.2f}%")
            print(f"   ")
            print(f"   💡 Interpretation: There's a {(1-conf)*100:.0f}% chance of losing")
            print(f"      at least {abs(var_dd):.1f}% from peak, or getting")
            print(f"      a return worse than {var_ret:.1f}%")
        
        # Probability of specific drawdown levels
        print("\n📊 Drawdown Probability Distribution:")
        thresholds = [-5, -10, -15, -20, -30, -40]
        for threshold in thresholds:
            prob = (max_drawdowns <= threshold).sum() / len(max_drawdowns)
            print(f"   • P(drawdown ≤ {threshold}%): {prob:.2%}")
        
        # Expected maximum drawdown
        expected_max_dd = max_drawdowns.mean()
        print(f"\n📉 Expected Maximum Drawdown: {expected_max_dd:.2f}%")
        
        return {
            'var_95_dd': np.percentile(max_drawdowns, 5),
            'cvar_95_dd': max_drawdowns[max_drawdowns <= np.percentile(max_drawdowns, 5)].mean(),
            'var_99_dd': np.percentile(max_drawdowns, 1),
            'cvar_99_dd': max_drawdowns[max_drawdowns <= np.percentile(max_drawdowns, 1)].mean(),
            'expected_dd': expected_max_dd
        }
    
    def find_historical_analogs(self, lookback_window=60, n_analogs=5):
        """
        Find historical periods similar to current market conditions.
        
        Args:
            lookback_window: Days to compare
            n_analogs: Number of similar periods to find
        """
        print("\n" + "=" * 80)
        print("HISTORICAL ANALOG MATCHING")
        print("=" * 80)
        
        # Current window features
        current = self.returns.tail(lookback_window)
        current_vol = current.std() * np.sqrt(252)
        current_mean = current.mean() * 252
        current_trend = (self.data['Close'].iloc[-1] / self.data['Close'].iloc[-lookback_window] - 1) * 100
        
        print(f"\n🔍 Searching for periods similar to last {lookback_window} days:")
        print(f"   • Volatility: {current_vol:.2%}")
        print(f"   • Mean Return: {current_mean:.2%}")
        print(f"   • Trend: {current_trend:.2f}%")
        
        # Calculate rolling similarity scores
        similarities = []
        
        # Need at least lookback_window + forward_window for analysis
        forward_window = 126  # 6 months forward
        total_required = lookback_window + forward_window
        
        for i in range(len(self.returns) - total_required):
            window = self.returns.iloc[i:i+lookback_window]
            
            # Feature matching
            window_vol = window.std() * np.sqrt(252)
            window_mean = window.mean() * 252
            window_trend = (self.data['Close'].iloc[i+lookback_window] / self.data['Close'].iloc[i] - 1) * 100
            
            # Calculate similarity score (lower is better)
            vol_diff = abs(window_vol - current_vol)
            mean_diff = abs(window_mean - current_mean)
            trend_diff = abs(window_trend - current_trend)
            
            # Weighted score
            score = (vol_diff * 2) + (mean_diff * 1) + (trend_diff * 0.5)
            
            # Forward performance
            forward_start = i + lookback_window
            forward_end = forward_start + forward_window
            forward_returns = self.data['Close'].iloc[forward_start:forward_end]
            
            if len(forward_returns) > 0:
                forward_ret = (forward_returns.iloc[-1] / forward_returns.iloc[0] - 1) * 100
                
                # Maximum drawdown in forward period
                running_max = forward_returns.expanding().max()
                drawdowns = (forward_returns / running_max - 1) * 100
                max_dd = drawdowns.min()
                
                similarities.append({
                    'date': self.data.index[i+lookback_window],
                    'score': score,
                    'forward_return_6m': forward_ret,
                    'max_dd_6m': max_dd,
                    'vol': window_vol,
                    'mean': window_mean,
                    'trend': window_trend
                })
        
        # Sort by similarity score
        similarities_df = pd.DataFrame(similarities).sort_values('score')
        top_analogs = similarities_df.head(n_analogs)
        
        print(f"\n📜 Top {n_analogs} Historical Analogs:")
        print("─" * 80)
        
        for idx, row in top_analogs.iterrows():
            print(f"\n📅 {row['date'].strftime('%Y-%m-%d')} (Similarity Score: {row['score']:.3f})")
            print(f"   • 6M Forward Return: {row['forward_return_6m']:+.2f}%")
            print(f"   • Max Drawdown (6M): {row['max_dd_6m']:.2f}%")
            print(f"   • Vol: {row['vol']:.2%}, Mean: {row['mean']:.2%}, Trend: {row['trend']:+.2f}%")
        
        # Aggregate statistics from analogs
        print("\n" + "─" * 80)
        print("📊 AGGREGATE ANALOG STATISTICS:")
        print(f"   • Average 6M Return: {top_analogs['forward_return_6m'].mean():+.2f}%")
        print(f"   • Median 6M Return: {top_analogs['forward_return_6m'].median():+.2f}%")
        print(f"   • Average Max Drawdown: {top_analogs['max_dd_6m'].mean():.2f}%")
        print(f"   • Worst Max Drawdown: {top_analogs['max_dd_6m'].min():.2f}%")
        print(f"   • Best 6M Return: {top_analogs['forward_return_6m'].max():+.2f}%")
        print(f"   • Worst 6M Return: {top_analogs['forward_return_6m'].min():+.2f}%")
        
        return top_analogs
    
    def plot_simulation_results(self, simulation_results, num_paths_to_plot=100):
        """Plot Monte Carlo simulation results."""
        try:
            import matplotlib.pyplot as plt
            
            price_paths = simulation_results['price_paths']
            max_drawdowns = simulation_results['max_drawdowns']
            
            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            
            # Plot 1: Sample price paths
            ax1 = axes[0, 0]
            for i in range(min(num_paths_to_plot, price_paths.shape[1])):
                ax1.plot(price_paths[:, i], alpha=0.1, color='blue')
            
            # Add percentile bands
            p5 = np.percentile(price_paths, 5, axis=1)
            p25 = np.percentile(price_paths, 25, axis=1)
            p50 = np.percentile(price_paths, 50, axis=1)
            p75 = np.percentile(price_paths, 75, axis=1)
            p95 = np.percentile(price_paths, 95, axis=1)
            
            ax1.plot(p50, color='red', linewidth=2, label='Median')
            ax1.fill_between(range(len(p5)), p5, p95, alpha=0.3, color='gray', label='5th-95th percentile')
            ax1.fill_between(range(len(p25)), p25, p75, alpha=0.3, color='blue', label='25th-75th percentile')
            ax1.set_title('Monte Carlo Price Paths', fontweight='bold')
            ax1.set_xlabel('Days')
            ax1.set_ylabel('Price ($)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # Plot 2: Drawdown distribution
            ax2 = axes[0, 1]
            ax2.hist(max_drawdowns, bins=50, alpha=0.7, color='red', edgecolor='black')
            ax2.axvline(np.percentile(max_drawdowns, 5), color='darkred', 
                       linestyle='--', linewidth=2, label='5% VaR')
            ax2.axvline(max_drawdowns.mean(), color='orange', 
                       linestyle='--', linewidth=2, label='Mean')
            ax2.set_title('Maximum Drawdown Distribution', fontweight='bold')
            ax2.set_xlabel('Maximum Drawdown (%)')
            ax2.set_ylabel('Frequency')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            # Plot 3: Final return distribution
            ax3 = axes[1, 0]
            final_returns = simulation_results['final_returns']
            ax3.hist(final_returns, bins=50, alpha=0.7, color='green', edgecolor='black')
            ax3.axvline(np.percentile(final_returns, 5), color='darkred', 
                       linestyle='--', linewidth=2, label='5% VaR')
            ax3.axvline(final_returns.mean(), color='blue', 
                       linestyle='--', linewidth=2, label='Mean')
            ax3.set_title('Final Return Distribution', fontweight='bold')
            ax3.set_xlabel('Return (%)')
            ax3.set_ylabel('Frequency')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
            
            # Plot 4: Risk metrics summary
            ax4 = axes[1, 1]
            ax4.axis('off')
            
            metrics_text = f"""
            SIMULATION SUMMARY
            ═══════════════════════════════════
            
            Simulations: {price_paths.shape[1]:,}
            Days Forward: {price_paths.shape[0]-1}
            
            DRAWDOWN METRICS
            ───────────────────────────────────
            Expected Max DD: {max_drawdowns.mean():.2f}%
            5% VaR (Max DD): {np.percentile(max_drawdowns, 5):.2f}%
            1% VaR (Max DD): {np.percentile(max_drawdowns, 1):.2f}%
            
            RETURN METRICS
            ───────────────────────────────────
            Expected Return: {final_returns.mean():.2f}%
            5% VaR (Return): {np.percentile(final_returns, 5):.2f}%
            95% Upside: {np.percentile(final_returns, 95):.2f}%
            
            PROBABILITY OF LOSS
            ───────────────────────────────────
            P(Return < 0%): {(final_returns < 0).sum() / len(final_returns):.1%}
            P(Return < -10%): {(final_returns < -10).sum() / len(final_returns):.1%}
            P(DD > -20%): {(max_drawdowns < -20).sum() / len(max_drawdowns):.1%}
            """
            
            ax4.text(0.1, 0.9, metrics_text, transform=ax4.transAxes,
                    fontsize=10, verticalalignment='top', fontfamily='monospace',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
            
            plt.tight_layout()
            plt.savefig('drawdown_forecast.png', dpi=150, bbox_inches='tight')
            print("\n📊 Chart saved as 'drawdown_forecast.png'")
            plt.show()
            
        except ImportError:
            print("\n⚠️  matplotlib not installed. Skipping plot.")

def main():
    """Run complete drawdown risk analysis."""
    
    # Initialize forecaster
    forecaster = DrawdownRiskForecaster(ticker="SPY", history_years=15)
    
    # Fetch data
    if not forecaster.fetch_data():
        return
    
    # Detect current regime
    forecaster.detect_volatility_regime(window=60)
    
    # Run Monte Carlo simulation
    sim_results = forecaster.monte_carlo_simulation(
        days_forward=252,  # 1 year
        num_simulations=10000,
        use_regime=True
    )
    
    # Calculate VaR and CVaR
    risk_metrics = forecaster.calculate_var_cvar(sim_results)
    
    # Find historical analogs
    analogs = forecaster.find_historical_analogs(lookback_window=60, n_analogs=5)
    
    # Plot results
    forecaster.plot_simulation_results(sim_results)
    
    print("\n" + "=" * 80)
    print("✅ DRAWDOWN RISK ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()