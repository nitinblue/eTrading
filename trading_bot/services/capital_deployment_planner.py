"""
Capital Deployment Planner with Risk Limits
Helps you deploy capital responsibly based on risk metrics
"""

import json
import numpy as np
import pandas as pd
from datetime import datetime

class DeploymentPlanner:
    def __init__(self, total_capital, risk_tolerance='conservative'):
        """
        Initialize deployment planner.
        
        Args:
            total_capital: Total capital available for deployment
            risk_tolerance: 'conservative', 'moderate', or 'aggressive'
        """
        self.total_capital = total_capital
        self.deployed_capital = 0
        self.positions = []
        
        # Risk tolerance settings
        self.risk_profiles = {
            'conservative': {
                'max_var_pct': 0.10,  # 10% max VaR
                'max_position_size': 0.02,  # 2% per position
                'max_deployment_per_month': 0.10,  # 10% per month
                'max_delta_exposure': 15,
                'min_theta': 0  # Must be positive theta
            },
            'moderate': {
                'max_var_pct': 0.15,  # 15% max VaR
                'max_position_size': 0.05,  # 5% per position
                'max_deployment_per_month': 0.20,  # 20% per month
                'max_delta_exposure': 30,
                'min_theta': -10
            },
            'aggressive': {
                'max_var_pct': 0.25,  # 25% max VaR
                'max_position_size': 0.10,  # 10% per position
                'max_deployment_per_month': 0.30,  # 30% per month
                'max_delta_exposure': 50,
                'min_theta': -50
            }
        }
        
        self.profile = self.risk_profiles[risk_tolerance]
        self.risk_tolerance = risk_tolerance
        
    def display_risk_profile(self):
        """Display current risk tolerance settings."""
        from tabulate import tabulate
        
        print("\n" + "=" * 80)
        print(f"RISK PROFILE: {self.risk_tolerance.upper()}")
        print("=" * 80)
        
        profile_data = [
            ["Total Capital", f"${self.total_capital:,.2f}", "Available for deployment"],
            ["Max Portfolio VaR", f"{self.profile['max_var_pct']*100:.0f}%", f"${self.total_capital * self.profile['max_var_pct']:,.2f}"],
            ["Max Position Size", f"{self.profile['max_position_size']*100:.0f}%", f"${self.total_capital * self.profile['max_position_size']:,.2f}"],
            ["Max Monthly Deploy", f"{self.profile['max_deployment_per_month']*100:.0f}%", f"${self.total_capital * self.profile['max_deployment_per_month']:,.2f}"],
            ["Max Delta Exposure", f"±{self.profile['max_delta_exposure']}", "Directional limit"],
            ["Min Theta Required", f"${self.profile['min_theta']:+.2f}/day", "Time decay income"]
        ]
        
        print(tabulate(profile_data, headers=["Setting", "Limit", "Dollar Amount"], tablefmt="fancy_grid"))
        
    def check_position_approval(self, position_details):
        """
        Check if a new position meets risk criteria.
        
        Args:
            position_details: dict with keys:
                - capital_required: float
                - max_loss: float
                - delta: float
                - theta: float
                - strategy: str
        
        Returns:
            dict: approval status and reasons
        """
        from tabulate import tabulate
        
        capital_req = position_details['capital_required']
        max_loss = abs(position_details['max_loss'])
        delta = position_details['delta']
        theta = position_details.get('theta', 0)
        
        checks = {
            'approved': True,
            'warnings': [],
            'blockers': []
        }
        
        check_results = []
        
        # Check 1: Position size
        position_size_pct = capital_req / self.total_capital
        max_allowed_pct = self.profile['max_position_size']
        
        if position_size_pct > max_allowed_pct:
            checks['approved'] = False
            checks['blockers'].append(f"Position too large: {position_size_pct*100:.1f}% vs {max_allowed_pct*100:.0f}% limit")
            check_results.append(["Position Size", f"{position_size_pct*100:.1f}%", f"{max_allowed_pct*100:.0f}%", "❌ FAIL"])
        elif position_size_pct > max_allowed_pct * 0.8:
            checks['warnings'].append(f"Position near limit: {position_size_pct*100:.1f}%")
            check_results.append(["Position Size", f"{position_size_pct*100:.1f}%", f"{max_allowed_pct*100:.0f}%", "⚠️ WARNING"])
        else:
            check_results.append(["Position Size", f"{position_size_pct*100:.1f}%", f"{max_allowed_pct*100:.0f}%", "✅ PASS"])
        
        # Check 2: Max loss
        max_loss_pct = max_loss / self.total_capital
        if max_loss_pct > self.profile['max_position_size'] * 2:
            checks['approved'] = False
            checks['blockers'].append(f"Max loss too high: ${max_loss:,.2f} ({max_loss_pct*100:.1f}%)")
            check_results.append(["Max Loss", f"${max_loss:,.2f}", f"{self.profile['max_position_size']*2*100:.0f}%", "❌ FAIL"])
        else:
            check_results.append(["Max Loss", f"${max_loss:,.2f}", f"{self.profile['max_position_size']*2*100:.0f}%", "✅ PASS"])
        
        # Check 3: Delta exposure
        current_delta = sum(p.get('delta', 0) for p in self.positions)
        new_total_delta = current_delta + delta
        
        if abs(new_total_delta) > self.profile['max_delta_exposure']:
            checks['approved'] = False
            checks['blockers'].append(f"Delta exceeds limit: {new_total_delta:+.2f} vs ±{self.profile['max_delta_exposure']}")
            check_results.append(["Portfolio Delta", f"{new_total_delta:+.2f}", f"±{self.profile['max_delta_exposure']}", "❌ FAIL"])
        elif abs(new_total_delta) > self.profile['max_delta_exposure'] * 0.8:
            checks['warnings'].append(f"Delta approaching limit: {new_total_delta:+.2f}")
            check_results.append(["Portfolio Delta", f"{new_total_delta:+.2f}", f"±{self.profile['max_delta_exposure']}", "⚠️ WARNING"])
        else:
            check_results.append(["Portfolio Delta", f"{new_total_delta:+.2f}", f"±{self.profile['max_delta_exposure']}", "✅ PASS"])
        
        # Check 4: Theta requirement
        current_theta = sum(p.get('theta', 0) for p in self.positions)
        new_total_theta = current_theta + theta
        
        if new_total_theta < self.profile['min_theta']:
            checks['approved'] = False
            checks['blockers'].append(f"Theta below minimum: ${new_total_theta:+.2f} vs ${self.profile['min_theta']:+.2f}")
            check_results.append(["Portfolio Theta", f"${new_total_theta:+.2f}", f"${self.profile['min_theta']:+.2f}", "❌ FAIL"])
        else:
            check_results.append(["Portfolio Theta", f"${new_total_theta:+.2f}", f"${self.profile['min_theta']:+.2f}", "✅ PASS"])
        
        # Check 5: Capital availability
        deployed_pct = (self.deployed_capital + capital_req) / self.total_capital
        if deployed_pct > 1.0:
            checks['approved'] = False
            checks['blockers'].append(f"Insufficient capital")
            check_results.append(["Capital Available", f"${self.total_capital - self.deployed_capital:,.2f}", f"${capital_req:,.2f}", "❌ FAIL"])
        else:
            check_results.append(["Capital Available", f"${self.total_capital - self.deployed_capital:,.2f}", f"${capital_req:,.2f}", "✅ PASS"])
        
        print("\n" + "─" * 80)
        print(f"🔍 Risk Checks for: {position_details.get('strategy', 'New Position')}")
        print("─" * 80)
        print(tabulate(check_results, headers=["Check", "Current/New", "Limit", "Status"], tablefmt="fancy_grid"))
        
        checks['check_results'] = check_results
        return checks
    
    def add_position(self, position_details):
        """Add a position to the portfolio if it passes risk checks."""
        checks = self.check_position_approval(position_details)
        
        print("\n" + "─" * 80)
        print(f"🔍 Evaluating Position: {position_details.get('strategy', 'Unknown')}")
        print("─" * 80)
        print(f"   Capital Required: ${position_details['capital_required']:,.2f}")
        print(f"   Max Loss: ${abs(position_details['max_loss']):,.2f}")
        print(f"   Delta: {position_details['delta']:+.2f}")
        print(f"   Theta: ${position_details.get('theta', 0):+.2f}/day")
        
        if checks['blockers']:
            print("\n❌ POSITION REJECTED:")
            for blocker in checks['blockers']:
                print(f"   • {blocker}")
            return False
        
        if checks['warnings']:
            print("\n⚠️  WARNINGS:")
            for warning in checks['warnings']:
                print(f"   • {warning}")
        
        print("\n✅ POSITION APPROVED")
        
        # Add position
        position_details['added_date'] = datetime.now()
        self.positions.append(position_details)
        self.deployed_capital += position_details['capital_required']
        
        print(f"\n📊 Updated Portfolio:")
        print(f"   Deployed Capital: ${self.deployed_capital:,.2f} ({self.deployed_capital/self.total_capital*100:.1f}%)")
        print(f"   Available Capital: ${self.total_capital - self.deployed_capital:,.2f}")
        print(f"   Total Delta: {sum(p.get('delta', 0) for p in self.positions):+.2f}")
        print(f"   Total Theta: ${sum(p.get('theta', 0) for p in self.positions):+.2f}/day")
        
        return True
    
    def get_deployment_capacity(self):
        """Show how much more capital can be deployed."""
        current_delta = sum(p.get('delta', 0) for p in self.positions)
        current_theta = sum(p.get('theta', 0) for p in self.positions)
        
        print("\n" + "=" * 80)
        print("DEPLOYMENT CAPACITY ANALYSIS")
        print("=" * 80)
        
        # Capital capacity
        available_capital = self.total_capital - self.deployed_capital
        print(f"\n💵 Capital Capacity:")
        print(f"   • Available: ${available_capital:,.2f} ({available_capital/self.total_capital*100:.1f}%)")
        print(f"   • Deployed: ${self.deployed_capital:,.2f} ({self.deployed_capital/self.total_capital*100:.1f}%)")
        
        # Position size capacity
        max_position_dollars = self.total_capital * self.profile['max_position_size']
        print(f"\n📏 Position Sizing:")
        print(f"   • Max Position Size: ${max_position_dollars:,.2f}")
        print(f"   • Positions Held: {len(self.positions)}")
        
        # Delta capacity
        delta_room_long = self.profile['max_delta_exposure'] - current_delta
        delta_room_short = self.profile['max_delta_exposure'] + current_delta
        print(f"\n📈 Delta Capacity:")
        print(f"   • Current Delta: {current_delta:+.2f}")
        print(f"   • Room for Long Delta: +{max(0, delta_room_long):.2f}")
        print(f"   • Room for Short Delta: {min(0, -delta_room_short):.2f}")
        
        # Theta capacity
        theta_needed = self.profile['min_theta'] - current_theta
        print(f"\n⏰ Theta Status:")
        print(f"   • Current Theta: ${current_theta:+.2f}/day")
        print(f"   • Required: ${self.profile['min_theta']:+.2f}/day")
        if theta_needed > 0:
            print(f"   • ⚠️  Need ${theta_needed:+.2f} more theta")
        else:
            print(f"   • ✅ Meeting theta requirement")
        
        return {
            'available_capital': available_capital,
            'max_position_size': max_position_dollars,
            'delta_capacity_long': delta_room_long,
            'delta_capacity_short': delta_room_short,
            'theta_needed': theta_needed
        }
    
    def suggest_positions(self):
        """Suggest position types based on current portfolio state."""
        capacity = self.get_deployment_capacity()
        
        print("\n" + "=" * 80)
        print("SUGGESTED POSITION TYPES")
        print("=" * 80)
        
        suggestions = []
        
        # If low/negative delta, suggest bullish positions
        current_delta = sum(p.get('delta', 0) for p in self.positions)
        if current_delta < -5:
            suggestions.append({
                'type': 'Bull Put Spread or Long Calls',
                'reason': f'Portfolio is bearish (Δ={current_delta:+.2f}), add bullish exposure',
                'size': f"${min(capacity['available_capital'], capacity['max_position_size']):,.2f}"
            })
        elif current_delta > 5:
            suggestions.append({
                'type': 'Bear Call Spread or Long Puts',
                'reason': f'Portfolio is bullish (Δ={current_delta:+.2f}), add bearish balance',
                'size': f"${min(capacity['available_capital'], capacity['max_position_size']):,.2f}"
            })
        else:
            suggestions.append({
                'type': 'Iron Condor or Credit Spreads',
                'reason': 'Portfolio is delta-neutral, continue range-bound strategies',
                'size': f"${min(capacity['available_capital'], capacity['max_position_size']):,.2f}"
            })
        
        # If need more theta
        if capacity['theta_needed'] > 0:
            suggestions.append({
                'type': 'Sell Premium (Covered Calls, Cash-Secured Puts)',
                'reason': f'Need ${capacity["theta_needed"]:+.2f} more daily theta income',
                'size': 'Multiple small positions'
            })
        
        # If lots of capital available
        if capacity['available_capital'] > self.total_capital * 0.20:
            suggestions.append({
                'type': 'Core Holdings (SPY/QQQ shares + protective puts)',
                'reason': f'Large capital available (${capacity["available_capital"]:,.2f})',
                'size': f'Deploy ${self.total_capital * 0.10:,.2f} per month'
            })
        
        for i, sug in enumerate(suggestions, 1):
            print(f"\n{i}. {sug['type']}")
            print(f"   Reason: {sug['reason']}")
            print(f"   Suggested Size: {sug['size']}")
    
    def generate_deployment_report(self):
        """Generate comprehensive deployment status report."""
        print("\n" + "=" * 80)
        print("DEPLOYMENT STATUS REPORT")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        self.display_risk_profile()
        self.get_deployment_capacity()
        
        if len(self.positions) > 0:
            print("\n" + "=" * 80)
            print("CURRENT POSITIONS")
            print("=" * 80)
            
            for i, pos in enumerate(self.positions, 1):
                print(f"\n{i}. {pos.get('strategy', 'Position')}")
                print(f"   Capital: ${pos['capital_required']:,.2f}")
                print(f"   Max Loss: ${abs(pos['max_loss']):,.2f}")
                print(f"   Delta: {pos['delta']:+.2f} | Theta: ${pos.get('theta', 0):+.2f}")
        
        self.suggest_positions()

def main():
    """Example usage of deployment planner."""
    
    print("💼 CAPITAL DEPLOYMENT PLANNER")
    print("=" * 80)
    
    # Example: Your situation
    # IRA: $200K + Trading: $40K = $240K total
    planner = DeploymentPlanner(
        total_capital=240000,
        risk_tolerance='conservative'  # Change to 'moderate' or 'aggressive' as needed
    )
    
    planner.display_risk_profile()
    
    # Example positions to evaluate
    
    # Position 1: Iron Condor on NVDA
    print("\n" + "=" * 80)
    print("POSITION EVALUATION EXAMPLES")
    print("=" * 80)
    
    nvda_condor = {
        'strategy': 'NVDA Iron Condor (45 DTE)',
        'capital_required': 1500,  # Max loss
        'max_loss': -1500,
        'delta': -0.5,  # Slightly bearish
        'theta': 12  # Earning $12/day
    }
    
    planner.add_position(nvda_condor)
    
    # Position 2: SPY shares with protective puts
    spy_hedge = {
        'strategy': 'SPY Shares + Protective Puts',
        'capital_required': 20000,  # $20K in shares
        'max_loss': -2000,  # 10% max loss with puts
        'delta': 38,  # Bullish (100 shares = ~40 delta, puts = -2 delta)
        'theta': -5  # Losing $5/day to put premium
    }
    
    planner.add_position(spy_hedge)
    
    # Position 3: Cash-secured put
    csp = {
        'strategy': 'TSLA Cash-Secured Put',
        'capital_required': 5000,
        'max_loss': -5000,
        'delta': -15,
        'theta': 25
    }
    
    planner.add_position(csp)
    
    # Generate full report
    print("\n")
    planner.generate_deployment_report()
    
    # Show what's possible next
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("""
    1. Run crash_indicators_claude.py to check market conditions
    2. Run regime_detection.py to confirm we're not in bear market
    3. If both green, use suggestions above to add next position
    4. After adding, re-run portfolio_drawdown_risk.py to verify VaR
    5. Repeat daily until deployed to target allocation
    """)

if __name__ == "__main__":
    main()