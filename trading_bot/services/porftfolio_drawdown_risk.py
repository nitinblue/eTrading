"""
Portfolio-Specific Drawdown Risk Analyzer
Analyzes drawdown risk for your actual option positions and trades
"""

import json
import os
import yfinance as yf
import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class PortfolioDrawdownAnalyzer:
    def __init__(self, trades_file="sample_trade.json"):
        """
        Initialize portfolio analyzer.
        
        Args:
            trades_file: Path to JSON file with trade data
        """
        self.trades_file = trades_file
        self.trades = None
        self.portfolio_value = 0
        self.portfolio_greeks = {}
        self.position_details = []
        
    def load_trades(self):
        """Load trades from JSON file."""
        print("📂 Loading trades from file...")
        
        try:
        
            with open(self.trades_file, 'r') as f:
                self.trades = json.load(f)
            
            print(f"✅ Loaded {len(self.trades)} trades")
            return True
            
        except FileNotFoundError:
            print(f"❌ File not found: {self.trades_file}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON: {e}")
            return False
    
    def analyze_current_portfolio(self):
        """Analyze current portfolio positions."""
        print("\n" + "=" * 80)
        print("CURRENT PORTFOLIO ANALYSIS")
        print("=" * 80)
        
        total_value = 0
        total_max_loss = 0
        total_delta = 0
        total_theta = 0
        
        for trade in self.trades:
            trade_value = 0
            trade_max_loss = 0
            trade_delta = 0
            trade_theta = 0
            
            print(f"\n📊 Trade: {trade['trade_id']} ({trade['ticker']})")
            print(f"   Strategy: {trade['strategy_type']}")
            print(f"   Underlying: ${trade['underlying_current_price']:.2f} (opened at ${trade['underlying_open_price']:.2f})")
            
            for leg in trade['legs']:
                leg_pnl = leg['current_value'] - leg['cost_basis']
                trade_value += leg['current_value']
                trade_max_loss += leg.get('max_loss_leg', 0)
                trade_delta += leg['current_greeks']['delta']
                trade_theta += leg['current_greeks']['theta']
                
                print(f"   • {leg['position']} {leg['option_type']} ${leg['strike']}: "
                      f"P&L ${leg_pnl:+.2f} | Δ={leg['current_greeks']['delta']:+.2f}")
            
            trade_pnl = trade_value - sum(leg['cost_basis'] for leg in trade['legs'])
            print(f"   → Trade P&L: ${trade_pnl:+.2f} | Max Loss: ${trade_max_loss:.2f}")
            print(f"   → Portfolio Delta: {trade_delta:+.2f} | Theta: {trade_theta:+.2f}")
            
            total_value += trade_value
            total_max_loss += trade_max_loss
            total_delta += trade_delta
            total_theta += trade_theta
            
            self.position_details.append({
                'trade_id': trade['trade_id'],
                'ticker': trade['ticker'],
                'strategy': trade['strategy_type'],
                'current_value': trade_value,
                'max_loss': trade_max_loss,
                'delta': trade_delta,
                'theta': trade_theta,
                'underlying_price': trade['underlying_current_price']
            })
        
        self.portfolio_value = total_value
        self.portfolio_greeks = {
            'delta': total_delta,
            'theta': total_theta
        }
        
        print("\n" + "─" * 80)
        print("💼 PORTFOLIO SUMMARY:")
        print(f"   • Total Current Value: ${total_value:,.2f}")
        print(f"   • Total Max Loss Potential: ${total_max_loss:,.2f}")
        print(f"   • Portfolio Delta: {total_delta:+.2f} (directional exposure)")
        print(f"   • Portfolio Theta: {total_theta:+.2f} (daily time decay)")
        
        # Risk interpretation
        delta_risk = abs(total_delta)
        if delta_risk < 10:
            delta_status = "🟢 DELTA NEUTRAL"
        elif delta_risk < 50:
            delta_status = "🟡 MODERATE DIRECTIONAL"
        else:
            delta_status = "🔴 HIGH DIRECTIONAL"
        
        print(f"   • Delta Risk: {delta_status}")
        
        return {
            'total_value': total_value,
            'max_loss': total_max_loss,
            'greeks': self.portfolio_greeks
        }
    
    def fetch_underlying_data(self, lookback_days=252):
        """Fetch price data for all underlying securities."""
        print(f"\n📥 Fetching {lookback_days} days of price data for underlyings...")
        
        tickers = list(set([trade['ticker'] for trade in self.trades]))
        self.underlying_data = {}
        
        for ticker in tickers:
            try:
                data = yf.Ticker(ticker).history(period=f"{lookback_days}d")
                if len(data) > 0:
                    self.underlying_data[ticker] = data
                    print(f"   ✅ {ticker}: {len(data)} days")
                else:
                    print(f"   ⚠️  {ticker}: No data")
            except Exception as e:
                print(f"   ❌ {ticker}: {e}")
        
        return self.underlying_data
    
    def estimate_position_volatility(self):
        """Estimate volatility for each position based on underlying."""
        print("\n" + "=" * 80)
        print("POSITION VOLATILITY ANALYSIS")
        print("=" * 80)
        
        position_vols = {}
        
        for pos in self.position_details:
            ticker = pos['ticker']
            
            if ticker in self.underlying_data:
                data = self.underlying_data[ticker]
                returns = data['Close'].pct_change().dropna()
                
                # Calculate various volatility measures
                vol_20d = returns.tail(20).std() * np.sqrt(252) * 100
                vol_60d = returns.tail(60).std() * np.sqrt(252) * 100
                vol_historical = returns.std() * np.sqrt(252) * 100
                
                position_vols[pos['trade_id']] = {
                    'ticker': ticker,
                    'vol_20d': vol_20d,
                    'vol_60d': vol_60d,
                    'vol_historical': vol_historical,
                    'current_price': pos['underlying_price']
                }
                
                print(f"\n📊 {pos['trade_id']} ({ticker}):")
                print(f"   • 20-day Vol: {vol_20d:.2f}%")
                print(f"   • 60-day Vol: {vol_60d:.2f}%")
                print(f"   • Historical Vol: {vol_historical:.2f}%")
        
        return position_vols
    
    def monte_carlo_portfolio_simulation(self, days_forward=30, num_simulations=10000):
        """
        Run Monte Carlo simulation for PORTFOLIO drawdown.
        Simulates underlying price movements and recalculates option values.
        
        Args:
            days_forward: Days to simulate (default 30 for options)
            num_simulations: Number of simulation paths
        """
        print(f"\n🎲 Running {num_simulations:,} portfolio simulations for {days_forward} days...")
        
        # Get volatility for each underlying
        position_vols = self.estimate_position_volatility()
        
        # Initialize arrays to store portfolio values
        portfolio_paths = np.zeros((days_forward + 1, num_simulations))
        portfolio_paths[0] = self.portfolio_value
        
        # For each simulation
        for sim in range(num_simulations):
            portfolio_value = self.portfolio_value
            
            for day in range(1, days_forward + 1):
                daily_pnl = 0
                
                # Simulate each position
                for pos in self.position_details:
                    trade_id = pos['trade_id']
                    
                    if trade_id not in position_vols:
                        continue
                    
                    vol_data = position_vols[trade_id]
                    daily_vol = vol_data['vol_60d'] / np.sqrt(252) / 100
                    
                    # Simulate price change
                    price_change = np.random.normal(0, daily_vol)
                    
                    # Estimate P&L using delta (simplified)
                    # Real implementation would use Black-Scholes
                    underlying_move = pos['underlying_price'] * price_change
                    delta_pnl = pos['delta'] * underlying_move * 100  # Delta * move * contract size
                    
                    # Add theta decay
                    theta_pnl = pos['theta'] * 1  # 1 day of theta
                    
                    # Total position P&L for the day
                    position_pnl = delta_pnl + theta_pnl
                    daily_pnl += position_pnl
                
                # Update portfolio value
                portfolio_value += daily_pnl
                portfolio_paths[day, sim] = portfolio_value
        
        # Calculate max drawdown for each simulation
        max_drawdowns = np.zeros(num_simulations)
        
        for sim in range(num_simulations):
            path = portfolio_paths[:, sim]
            running_max = np.maximum.accumulate(path)
            drawdown = (path / running_max - 1) * 100
            max_drawdowns[sim] = drawdown.min()
        
        # Calculate final P&L
        final_values = portfolio_paths[-1, :]
        final_pnl = final_values - self.portfolio_value
        
        print(f"✅ Portfolio simulation complete")
        
        return {
            'portfolio_paths': portfolio_paths,
            'max_drawdowns': max_drawdowns,
            'final_pnl': final_pnl,
            'initial_value': self.portfolio_value
        }
    
    def calculate_portfolio_var(self, simulation_results, confidence_levels=[0.95, 0.99]):
        """Calculate VaR and CVaR for the portfolio."""
        max_drawdowns = simulation_results['max_drawdowns']
        final_pnl = simulation_results['final_pnl']
        
        print("\n" + "=" * 80)
        print("PORTFOLIO VALUE AT RISK (VaR) & CVaR")
        print("=" * 80)
        
        for conf in confidence_levels:
            alpha = 1 - conf
            
            # VaR for drawdown
            var_dd_pct = np.percentile(max_drawdowns, alpha * 100)
            var_dd_dollars = self.portfolio_value * var_dd_pct / 100
            
            # CVaR for drawdown
            cvar_dd_pct = max_drawdowns[max_drawdowns <= var_dd_pct].mean()
            cvar_dd_dollars = self.portfolio_value * cvar_dd_pct / 100
            
            # VaR for P&L
            var_pnl = np.percentile(final_pnl, alpha * 100)
            
            # CVaR for P&L
            cvar_pnl = final_pnl[final_pnl <= var_pnl].mean()
            
            print(f"\n🎯 {conf:.0%} Confidence Level:")
            print(f"   Drawdown VaR:  {var_dd_pct:.2f}% (${var_dd_dollars:,.2f})")
            print(f"   Drawdown CVaR: {cvar_dd_pct:.2f}% (${cvar_dd_dollars:,.2f})")
            print(f"   P&L VaR:       ${var_pnl:,.2f}")
            print(f"   P&L CVaR:      ${cvar_pnl:,.2f}")
            print(f"   ")
            print(f"   💡 There's a {(1-conf)*100:.0f}% chance of:")
            print(f"      • Portfolio dropping by at least ${abs(var_dd_dollars):,.2f}")
            print(f"      • Losing at least ${abs(var_pnl):,.2f}")
        
        # Probability of hitting max loss
        total_max_loss = sum(pos['max_loss'] for pos in self.position_details)
        if total_max_loss < 0:
            prob_max_loss = (max_drawdowns * self.portfolio_value / 100 <= total_max_loss).sum() / len(max_drawdowns)
            print(f"\n🚨 Probability of Max Loss (${total_max_loss:,.2f}): {prob_max_loss:.2%}")
        
        # Expected drawdown
        expected_dd = max_drawdowns.mean()
        expected_dd_dollars = self.portfolio_value * expected_dd / 100
        print(f"\n📉 Expected Maximum Drawdown: {expected_dd:.2f}% (${expected_dd_dollars:,.2f})")
        
        return {
            'var_95_dd': var_dd_pct,
            'var_99_dd': np.percentile(max_drawdowns, 1),
            'var_95_pnl': var_pnl,
            'var_99_pnl': np.percentile(final_pnl, 1),
            'expected_dd': expected_dd
        }
    
    def stress_test_scenarios(self):
        """Run stress tests with extreme market scenarios."""
        print("\n" + "=" * 80)
        print("STRESS TEST SCENARIOS")
        print("=" * 80)
        
        scenarios = [
            {"name": "Flash Crash (-10% in 1 day)", "move": -0.10, "days": 1},
            {"name": "Bear Market (-20% over 30 days)", "move": -0.20, "days": 30},
            {"name": "Black Swan (-30% in 5 days)", "move": -0.30, "days": 5},
            {"name": "Rally (+15% over 20 days)", "move": 0.15, "days": 20},
            {"name": "High Vol Chop (±5% daily)", "move": 0.05, "days": 10, "choppy": True}
        ]
        
        for scenario in scenarios:
            total_pnl = 0
            
            print(f"\n📊 Scenario: {scenario['name']}")
            
            for pos in self.position_details:
                # Calculate underlying move
                if scenario.get('choppy'):
                    # Simulate choppy market
                    avg_pnl = 0
                    for _ in range(10):  # Average of 10 random paths
                        cumulative_move = 0
                        daily_pnl = 0
                        for day in range(scenario['days']):
                            daily_move = np.random.choice([-1, 1]) * scenario['move']
                            cumulative_move += daily_move
                            move_dollars = pos['underlying_price'] * daily_move
                            delta_pnl = pos['delta'] * move_dollars * 100
                            theta_pnl = pos['theta'] * 1
                            daily_pnl += delta_pnl + theta_pnl
                        avg_pnl += daily_pnl
                    position_pnl = avg_pnl / 10
                else:
                    # Linear move
                    daily_move = scenario['move'] / scenario['days']
                    total_move = pos['underlying_price'] * scenario['move']
                    
                    # Delta P&L
                    delta_pnl = pos['delta'] * total_move * 100
                    
                    # Theta P&L
                    theta_pnl = pos['theta'] * scenario['days']
                    
                    position_pnl = delta_pnl + theta_pnl
                
                total_pnl += position_pnl
                print(f"   • {pos['trade_id']}: ${position_pnl:+,.2f}")
            
            final_value = self.portfolio_value + total_pnl
            pct_change = (total_pnl / self.portfolio_value) * 100
            
            print(f"   → Total P&L: ${total_pnl:+,.2f} ({pct_change:+.2f}%)")
            print(f"   → Final Portfolio Value: ${final_value:,.2f}")
    
    def plot_portfolio_simulation(self, simulation_results, num_paths=100):
        """Plot portfolio simulation results."""
        try:
            import matplotlib.pyplot as plt
            
            paths = simulation_results['portfolio_paths']
            drawdowns = simulation_results['max_drawdowns']
            pnl = simulation_results['final_pnl']
            
            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            
            # Plot 1: Portfolio value paths
            ax1 = axes[0, 0]
            for i in range(min(num_paths, paths.shape[1])):
                ax1.plot(paths[:, i], alpha=0.1, color='blue')
            
            p5 = np.percentile(paths, 5, axis=1)
            p50 = np.percentile(paths, 50, axis=1)
            p95 = np.percentile(paths, 95, axis=1)
            
            ax1.plot(p50, color='red', linewidth=2, label='Median')
            ax1.fill_between(range(len(p5)), p5, p95, alpha=0.3, color='gray')
            ax1.axhline(self.portfolio_value, color='green', linestyle='--', label='Current Value')
            ax1.set_title('Portfolio Value Simulation Paths', fontweight='bold')
            ax1.set_xlabel('Days')
            ax1.set_ylabel('Portfolio Value ($)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # Plot 2: Drawdown distribution
            ax2 = axes[0, 1]
            ax2.hist(drawdowns, bins=50, alpha=0.7, color='red', edgecolor='black')
            ax2.axvline(np.percentile(drawdowns, 5), color='darkred', linestyle='--', linewidth=2, label='5% VaR')
            ax2.axvline(drawdowns.mean(), color='orange', linestyle='--', linewidth=2, label='Expected')
            ax2.set_title('Maximum Drawdown Distribution', fontweight='bold')
            ax2.set_xlabel('Max Drawdown (%)')
            ax2.set_ylabel('Frequency')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
            
            # Plot 3: P&L distribution
            ax3 = axes[1, 0]
            ax3.hist(pnl, bins=50, alpha=0.7, color='green', edgecolor='black')
            ax3.axvline(np.percentile(pnl, 5), color='darkred', linestyle='--', linewidth=2, label='5% VaR')
            ax3.axvline(pnl.mean(), color='blue', linestyle='--', linewidth=2, label='Expected')
            ax3.axvline(0, color='black', linestyle='-', linewidth=1)
            ax3.set_title('P&L Distribution', fontweight='bold')
            ax3.set_xlabel('P&L ($)')
            ax3.set_ylabel('Frequency')
            ax3.legend()
            ax3.grid(True, alpha=0.3)
            
            # Plot 4: Metrics summary
            ax4 = axes[1, 1]
            ax4.axis('off')
            
            metrics = f"""
            PORTFOLIO RISK SUMMARY
            ═══════════════════════════════════
            
            Current Value: ${self.portfolio_value:,.2f}
            Portfolio Delta: {self.portfolio_greeks['delta']:+.2f}
            Portfolio Theta: ${self.portfolio_greeks['theta']:+.2f}/day
            
            DRAWDOWN RISK
            ───────────────────────────────────
            Expected Max DD: {drawdowns.mean():.2f}%
            5% VaR: {np.percentile(drawdowns, 5):.2f}%
            1% VaR: {np.percentile(drawdowns, 1):.2f}%
            
            P&L RISK
            ───────────────────────────────────
            Expected P&L: ${pnl.mean():,.2f}
            5% VaR: ${np.percentile(pnl, 5):,.2f}
            95% Upside: ${np.percentile(pnl, 95):,.2f}
            
            PROBABILITIES
            ───────────────────────────────────
            P(Loss): {(pnl < 0).sum() / len(pnl):.1%}
            P(Loss > $1000): {(pnl < -1000).sum() / len(pnl):.1%}
            P(DD > -10%): {(drawdowns < -10).sum() / len(drawdowns):.1%}
            """
            
            ax4.text(0.1, 0.9, metrics, transform=ax4.transAxes,
                    fontsize=9, verticalalignment='top', fontfamily='monospace',
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.3))
            
            plt.tight_layout()
            plt.savefig('portfolio_drawdown_analysis.png', dpi=150, bbox_inches='tight')
            print("\n📊 Chart saved as 'portfolio_drawdown_analysis.png'")
            plt.show()
            
        except ImportError:
            print("\n⚠️  matplotlib not installed. Skipping plot.")

def main():
    """Run complete portfolio drawdown analysis."""
    base_path = os.path.dirname(os.path.abspath(__file__))
    trades_path = os.path.join(base_path, "sample_trade.json")
    # Initialize analyzer
    analyzer = PortfolioDrawdownAnalyzer(trades_file=trades_path)
    
    # Load trades
    if not analyzer.load_trades():
        return
    
    # Analyze current portfolio
    analyzer.analyze_current_portfolio()
    
    # Fetch underlying data
    analyzer.fetch_underlying_data(lookback_days=252)
    
    # Run volatility analysis
    analyzer.estimate_position_volatility()
    
    # Monte Carlo simulation
    sim_results = analyzer.monte_carlo_portfolio_simulation(
        days_forward=30,  # Options typically 30-60 days
        num_simulations=10000
    )
    
    # Calculate VaR/CVaR
    risk_metrics = analyzer.calculate_portfolio_var(sim_results)
    
    # Stress tests
    analyzer.stress_test_scenarios()
    
    # Plot results
    analyzer.plot_portfolio_simulation(sim_results)
    
    print("\n" + "=" * 80)
    print("✅ PORTFOLIO DRAWDOWN ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()