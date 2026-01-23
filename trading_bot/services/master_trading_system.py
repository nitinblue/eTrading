"""
Integrated Market Regime Advisory System
Tells you: Deploy, Halt, or Go All-In based on market conditions
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from tabulate import tabulate
import warnings
warnings.filterwarnings('ignore')

class MarketRegimeAdvisor:
    def __init__(self):
        """Initialize the market advisor."""
        self.indicators = {}
        self.regime_score = 0
        self.action = None
        
    def fetch_crash_indicators(self):
        """Fetch all crash pre-warning indicators."""
        print("\n" + "=" * 90)
        print(" " * 30 + "🔍 MARKET HEALTH SCAN")
        print("=" * 90)
        
        indicators_data = []
        
        # 1. VIX Fear Gauge
        try:
            vix = yf.Ticker("^VIX").history(period="10d")['Close']
            if len(vix) >= 5:
                vix_current = vix.iloc[-1]
                vix_5d_ago = vix.iloc[-5] if len(vix) >= 5 else vix.iloc[0]
                vix_spike = (vix_current / vix_5d_ago - 1) * 100
                
                if vix_current > 35:
                    vix_status = "🔴 PANIC"
                    vix_score = -3
                elif vix_current > 30:
                    vix_status = "🟠 EXTREME FEAR"
                    vix_score = -2
                elif vix_current > 25:
                    vix_status = "🟡 ELEVATED"
                    vix_score = -1
                elif vix_current > 20:
                    vix_status = "🟢 NORMAL"
                    vix_score = 0
                else:
                    vix_status = "🟢 COMPLACENT"
                    vix_score = 1
                
                self.indicators['vix'] = {'value': vix_current, 'spike': vix_spike, 'score': vix_score}
                indicators_data.append([
                    "VIX Fear Gauge",
                    f"{vix_current:.2f}",
                    f"{vix_spike:+.2f}%",
                    vix_status,
                    vix_score
                ])
        except Exception as e:
            indicators_data.append(["VIX Fear Gauge", "ERROR", "-", "⚠️ DATA UNAVAILABLE", 0])
        
        # 2. Credit Spreads (HYG vs TLT)
        try:
            hyg = yf.Ticker("HYG").history(period="20d")['Close']
            tlt = yf.Ticker("TLT").history(period="20d")['Close']
            
            if len(hyg) > 1 and len(tlt) > 1:
                hyg_ret = hyg.pct_change().iloc[-1]
                tlt_ret = tlt.pct_change().iloc[-1]
                spread = hyg_ret - tlt_ret
                
                # 20-day trend
                hyg_trend = (hyg.iloc[-1] / hyg.iloc[-20] - 1) * 100 if len(hyg) >= 20 else 0
                
                if spread < -0.015:
                    credit_status = "🔴 SEVERE STRESS"
                    credit_score = -3
                elif spread < -0.01:
                    credit_status = "🟠 WIDENING"
                    credit_score = -2
                elif spread < -0.005:
                    credit_status = "🟡 WATCH"
                    credit_score = -1
                else:
                    credit_status = "🟢 STABLE"
                    credit_score = 0
                
                self.indicators['credit_spread'] = {'value': spread, 'trend': hyg_trend, 'score': credit_score}
                indicators_data.append([
                    "Credit Spread (HYG-TLT)",
                    f"{spread:.4f}",
                    f"{hyg_trend:.2f}% (20D)",
                    credit_status,
                    credit_score
                ])
        except Exception as e:
            indicators_data.append(["Credit Spread", "ERROR", "-", "⚠️ DATA UNAVAILABLE", 0])
        
        # 3. Valuation (SPY P/E)
        try:
            spy_info = yf.Ticker("SPY").info
            fwd_pe = spy_info.get('forwardPE') or spy_info.get('trailingPE') or 0
            
            if fwd_pe > 28:
                pe_status = "🔴 EXTREME OVERVALUATION"
                pe_score = -2
            elif fwd_pe > 25:
                pe_status = "🟠 OVERVALUED"
                pe_score = -1
            elif fwd_pe > 22:
                pe_status = "🟡 ELEVATED"
                pe_score = 0
            elif fwd_pe > 18:
                pe_status = "🟢 FAIR"
                pe_score = 1
            else:
                pe_status = "🟢 CHEAP"
                pe_score = 2
            
            self.indicators['valuation'] = {'value': fwd_pe, 'score': pe_score}
            indicators_data.append([
                "SPY P/E Ratio",
                f"{fwd_pe:.2f}" if fwd_pe > 0 else "N/A",
                "Forward PE",
                pe_status,
                pe_score
            ])
        except Exception as e:
            indicators_data.append(["SPY P/E Ratio", "ERROR", "-", "⚠️ DATA UNAVAILABLE", 0])
        
        # 4. Yield Curve (10Y-2Y Spread)
        try:
            tnx = yf.Ticker("^TNX").history(period="5d")['Close']  # 10Y
            fvx = yf.Ticker("^FVX").history(period="5d")['Close']  # 5Y (proxy for 2Y)
            
            if len(tnx) > 0 and len(fvx) > 0:
                spread = tnx.iloc[-1] - fvx.iloc[-1]
                
                if spread < -0.5:
                    curve_status = "🔴 DEEPLY INVERTED"
                    curve_score = -3
                elif spread < 0:
                    curve_status = "🟠 INVERTED"
                    curve_score = -2
                elif spread < 0.5:
                    curve_status = "🟡 FLAT"
                    curve_score = -1
                else:
                    curve_status = "🟢 NORMAL"
                    curve_score = 0
                
                self.indicators['yield_curve'] = {'value': spread, 'score': curve_score}
                indicators_data.append([
                    "Yield Curve (10Y-5Y)",
                    f"{spread:.2f} bps",
                    f"10Y: {tnx.iloc[-1]:.2f}%",
                    curve_status,
                    curve_score
                ])
        except Exception as e:
            indicators_data.append(["Yield Curve", "ERROR", "-", "⚠️ DATA UNAVAILABLE", 0])
        
        # 5. Market Breadth (SPY vs RSP)
        try:
            spy = yf.Ticker("SPY").history(period="20d")['Close']
            rsp = yf.Ticker("RSP").history(period="20d")['Close']  # Equal-weight S&P
            
            if len(spy) >= 20 and len(rsp) >= 20:
                spy_ret = (spy.iloc[-1] / spy.iloc[-20] - 1) * 100
                rsp_ret = (rsp.iloc[-1] / rsp.iloc[-20] - 1) * 100
                divergence = spy_ret - rsp_ret
                
                if divergence > 8:
                    breadth_status = "🔴 EXTREME NARROW"
                    breadth_score = -2
                elif divergence > 5:
                    breadth_status = "🟠 NARROW"
                    breadth_score = -1
                elif divergence < -3:
                    breadth_status = "🟢 BROAD RALLY"
                    breadth_score = 1
                else:
                    breadth_status = "🟢 HEALTHY"
                    breadth_score = 0
                
                self.indicators['breadth'] = {'value': divergence, 'score': breadth_score}
                indicators_data.append([
                    "Market Breadth (SPY-RSP)",
                    f"{divergence:+.2f}%",
                    f"SPY: {spy_ret:+.2f}%",
                    breadth_status,
                    breadth_score
                ])
        except Exception as e:
            indicators_data.append(["Market Breadth", "ERROR", "-", "⚠️ DATA UNAVAILABLE", 0])
        
        # 6. Dollar Strength (DXY)
        try:
            dxy = yf.Ticker("DX-Y.NYB").history(period="20d")['Close']
            
            if len(dxy) >= 20:
                dxy_chg = (dxy.iloc[-1] / dxy.iloc[-20] - 1) * 100
                
                if dxy_chg > 7:
                    dollar_status = "🔴 EXTREME STRENGTH"
                    dollar_score = -2
                elif dxy_chg > 4:
                    dollar_status = "🟠 STRONG"
                    dollar_score = -1
                elif dxy_chg < -4:
                    dollar_status = "🟢 WEAK (RISK-ON)"
                    dollar_score = 1
                else:
                    dollar_status = "🟢 STABLE"
                    dollar_score = 0
                
                self.indicators['dollar'] = {'value': dxy.iloc[-1], 'change': dxy_chg, 'score': dollar_score}
                indicators_data.append([
                    "Dollar Index (DXY)",
                    f"{dxy.iloc[-1]:.2f}",
                    f"{dxy_chg:+.2f}% (20D)",
                    dollar_status,
                    dollar_score
                ])
        except Exception as e:
            indicators_data.append(["Dollar Index", "ERROR", "-", "⚠️ DATA UNAVAILABLE", 0])
        
        # 7. Gold (Safe Haven Demand)
        try:
            gld = yf.Ticker("GLD").history(period="20d")['Close']
            
            if len(gld) >= 20:
                gld_chg = (gld.iloc[-1] / gld.iloc[-20] - 1) * 100
                
                if gld_chg > 8:
                    gold_status = "🔴 FLIGHT TO SAFETY"
                    gold_score = -2
                elif gld_chg > 5:
                    gold_status = "🟡 ELEVATED DEMAND"
                    gold_score = -1
                else:
                    gold_status = "🟢 NORMAL"
                    gold_score = 0
                
                self.indicators['gold'] = {'value': gld.iloc[-1], 'change': gld_chg, 'score': gold_score}
                indicators_data.append([
                    "Gold (GLD)",
                    f"${gld.iloc[-1]:.2f}",
                    f"{gld_chg:+.2f}% (20D)",
                    gold_status,
                    gold_score
                ])
        except Exception as e:
            indicators_data.append(["Gold", "ERROR", "-", "⚠️ DATA UNAVAILABLE", 0])
        
        # Print indicators table
        print(tabulate(
            indicators_data,
            headers=["Indicator", "Value", "Trend/Context", "Status", "Score"],
            tablefmt="fancy_grid",
            numalign="right"
        ))
        
        return indicators_data
    
    def calculate_regime_score(self):
        """Calculate composite regime score."""
        total_score = sum(ind['score'] for ind in self.indicators.values() if 'score' in ind)
        
        # Determine regime and action
        if total_score <= -10:
            regime = "⚫ CAPITULATION / CRASH"
            action = "🚀 ALL-IN: Use ALL remaining powder!"
            color = "red"
        elif total_score <= -6:
            regime = "🔴 SEVERE BEAR MARKET"
            action = "💰 DEPLOY 50%: Great opportunity"
        elif total_score <= -3:
            regime = "🟠 CORRECTION / BEAR"
            action = "⏸️  HALT: Wait for stabilization"
        elif total_score <= 0:
            regime = "🟡 OVERHEATED / CAUTION"
            action = "🛑 HALT: Market overheated, reduce exposure"
        elif total_score <= 3:
            regime = "🟢 NORMAL BULL"
            action = "✅ DEPLOY: Normal deployment OK"
        else:
            regime = "🟢 STRONG BULL"
            action = "✅ DEPLOY: Favorable conditions"
        
        self.regime_score = total_score
        self.action = action
        self.regime = regime
        
        return total_score, regime, action
    
    def print_regime_assessment(self):
        """Print detailed regime assessment."""
        score, regime, action = self.calculate_regime_score()
        
        print("\n" + "=" * 90)
        print(" " * 30 + "📊 REGIME ASSESSMENT")
        print("=" * 90)
        
        assessment_data = [
            ["Composite Score", score, f"Range: -15 (crash) to +10 (euphoria)"],
            ["Market Regime", regime, "Current market state"],
            ["Recommended Action", action, "What to do NOW"]
        ]
        
        print(tabulate(
            assessment_data,
            headers=["Metric", "Value", "Description"],
            tablefmt="fancy_grid"
        ))
        
        # Detailed guidance
        print("\n" + "=" * 90)
        print(" " * 30 + "💡 DETAILED GUIDANCE")
        print("=" * 90)
        
        guidance = []
        
        if score <= -10:
            guidance.append(["Position Type", "Buy EVERYTHING", "Stocks, long calls, aggressive spreads"])
            guidance.append(["Sizing", "100% of powder", "This is the opportunity of years"])
            guidance.append(["Duration", "6-12 months", "Hold through recovery"])
            guidance.append(["Risk Level", "🟢 LOW", "Buying at panic lows"])
            guidance.append(["Expected Return", "30-100%+", "Historical crash recoveries"])
        elif score <= -6:
            guidance.append(["Position Type", "Aggressive buying", "Long shares, bull spreads"])
            guidance.append(["Sizing", "50% of powder", "Scale in over 2-4 weeks"])
            guidance.append(["Duration", "3-6 months", "Bear markets average 9 months"])
            guidance.append(["Risk Level", "🟡 MEDIUM", "Still declining but good value"])
            guidance.append(["Expected Return", "20-40%", "Buying in correction"])
        elif score <= -3:
            guidance.append(["Position Type", "HALT new entries", "Close risky positions"])
            guidance.append(["Sizing", "0% deployment", "Preserve capital"])
            guidance.append(["Duration", "Wait for reversal", "Monitor daily for improvement"])
            guidance.append(["Risk Level", "🔴 HIGH", "Correction underway"])
            guidance.append(["Action Items", "Raise cash, hedge", "Defensive positioning"])
        elif score <= 0:
            guidance.append(["Position Type", "HALT deployment", "Market overheated"])
            guidance.append(["Sizing", "0% new capital", "Reduce if heavily long"])
            guidance.append(["Duration", "Wait for pullback", "Be patient"])
            guidance.append(["Risk Level", "🔴 ELEVATED", "Overvalued conditions"])
            guidance.append(["Action Items", "Take profits", "Build cash reserves"])
        else:
            guidance.append(["Position Type", "Normal deployment", "Spreads, condors, CSPs"])
            guidance.append(["Sizing", "10-20% per month", "Gradual ladder approach"])
            guidance.append(["Duration", "Ongoing", "Build positions systematically"])
            guidance.append(["Risk Level", "🟢 NORMAL", "Healthy market conditions"])
            guidance.append(["Action Items", "Follow plan", "Use deployment planner"])
        
        print(tabulate(
            guidance,
            headers=["Category", "Recommendation", "Details"],
            tablefmt="fancy_grid"
        ))
    
    def check_specific_conditions(self):
        """Check for specific extreme conditions."""
        print("\n" + "=" * 90)
        print(" " * 30 + "🚨 SPECIAL CONDITIONS CHECK")
        print("=" * 90)
        
        conditions = []
        
        # VIX spike condition
        if 'vix' in self.indicators:
            vix_val = self.indicators['vix']['value']
            vix_spike = self.indicators['vix']['spike']
            
            if vix_val > 40:
                conditions.append([
                    "VIX > 40",
                    "🔴 EXTREME PANIC",
                    "🚀 BUYING OPPORTUNITY",
                    "Buy puts on VIX, long equities"
                ])
            elif vix_spike > 30:
                conditions.append([
                    f"VIX Spike +{vix_spike:.0f}%",
                    "🔴 RAPID FEAR SPIKE",
                    "⚠️ VOLATILITY EVENT",
                    "Wait 1-2 days for stabilization"
                ])
        
        # Credit stress
        if 'credit_spread' in self.indicators:
            spread = self.indicators['credit_spread']['value']
            if spread < -0.015:
                conditions.append([
                    "Credit Spread < -1.5%",
                    "🔴 CREDIT CRISIS",
                    "🚨 SYSTEMIC RISK",
                    "Extreme caution - possible contagion"
                ])
        
        # Yield curve inversion
        if 'yield_curve' in self.indicators:
            curve = self.indicators['yield_curve']['value']
            if curve < -0.5:
                conditions.append([
                    "Deep Inversion",
                    "🔴 RECESSION SIGNAL",
                    "⏰ 6-18 MONTH LEAD",
                    "Recession historically follows"
                ])
        
        # Market concentration
        if 'breadth' in self.indicators:
            breadth = self.indicators['breadth']['value']
            if breadth > 8:
                conditions.append([
                    "SPY>>RSP (+8%)",
                    "🔴 EXTREME CONCENTRATION",
                    "⚠️ TOP-HEAVY MARKET",
                    "Few stocks driving index - fragile"
                ])
        
        # No special conditions
        if not conditions:
            conditions.append([
                "No Extremes Detected",
                "🟢 NORMAL CONDITIONS",
                "✅ PROCEED NORMALLY",
                "Follow standard deployment protocol"
            ])
        
        print(tabulate(
            conditions,
            headers=["Condition", "Status", "Implication", "Action"],
            tablefmt="fancy_grid"
        ))
    
    def get_daily_protocol(self):
        """Output daily trading protocol."""
        score = self.regime_score
        
        print("\n" + "=" * 90)
        print(" " * 30 + "📋 TODAY'S TRADING PROTOCOL")
        print("=" * 90)
        
        if score <= -10:
            protocol = [
                ["1", "🚀 GO ALL-IN", "Deploy ALL remaining capital"],
                ["2", "Focus on", "Long stocks, long calls, bull spreads"],
                ["3", "Avoid", "Selling premium, short positions"],
                ["4", "Size", "Max position size: 10-20% per trade"],
                ["5", "Mindset", "This is a GIFT - buy the panic"],
                ["6", "Re-check", "Daily - stay aggressive until score > -8"]
            ]
        elif score <= -6:
            protocol = [
                ["1", "💰 AGGRESSIVE DEPLOY", "Use 50% of remaining capital"],
                ["2", "Focus on", "Long bias - bull spreads, CSPs"],
                ["3", "Avoid", "Bear positions, iron condors"],
                ["4", "Size", "5-10% per trade"],
                ["5", "Mindset", "Scale in over 1-2 weeks"],
                ["6", "Re-check", "Every 2-3 days"]
            ]
        elif score <= -3:
            protocol = [
                ["1", "⏸️  HALT ALL DEPLOYMENT", "No new positions"],
                ["2", "Close", "Risky directional positions"],
                ["3", "Keep", "Theta-positive, defined-risk trades"],
                ["4", "Hedge", "Consider buying puts on longs"],
                ["5", "Cash", "Build reserves for opportunity"],
                ["6", "Re-check", "Daily - wait for score > -2"]
            ]
        elif score <= 0:
            protocol = [
                ["1", "🛑 HALT DEPLOYMENT", "Market overheated"],
                ["2", "Reduce", "Take profits on winning positions"],
                ["3", "Avoid", "New bullish positions"],
                ["4", "Consider", "Bear spreads, protective puts"],
                ["5", "Build", "Cash for coming correction"],
                ["6", "Re-check", "Daily - wait for pullback"]
            ]
        else:
            protocol = [
                ["1", "✅ NORMAL DEPLOYMENT", "Follow standard plan"],
                ["2", "Add", "1-2 positions per day max"],
                ["3", "Focus", "High-probability trades (70%+ win rate)"],
                ["4", "Size", "2-5% per trade"],
                ["5", "Check VaR", "Run portfolio_drawdown_risk.py after each trade"],
                ["6", "Re-check", "Every morning before trading"]
            ]
        
        print(tabulate(
            protocol,
            headers=["Step", "Action", "Details"],
            tablefmt="fancy_grid"
        ))
    
    def generate_alert_summary(self):
        """Generate summary of critical alerts."""
        print("\n" + "=" * 90)
        print(" " * 30 + "🔔 ALERT SUMMARY")
        print("=" * 90)
        
        alerts = []
        priority_map = {"🔴": 1, "🟠": 2, "🟡": 3, "🟢": 4}
        
        # Check each indicator for alerts
        for name, data in self.indicators.items():
            if data['score'] <= -2:
                alerts.append(["🔴 HIGH", name.upper(), f"Score: {data['score']}", "Immediate attention"])
            elif data['score'] == -1:
                alerts.append(["🟡 MEDIUM", name.upper(), f"Score: {data['score']}", "Monitor closely"])
        
        if not alerts:
            alerts.append(["🟢 CLEAR", "No Critical Alerts", "All systems normal", "Proceed with trading"])
        
        # Sort by priority
        alerts.sort(key=lambda x: priority_map.get(x[0][:2], 5))
        
        print(tabulate(
            alerts,
            headers=["Priority", "Alert", "Value", "Action"],
            tablefmt="fancy_grid"
        ))

def main():
    """Run complete market regime advisory system."""
    
    print("\n" + "🎯" * 45)
    print()
    print(" " * 20 + "MARKET REGIME ADVISORY SYSTEM")
    print(" " * 25 + f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("🎯" * 45)
    
    advisor = MarketRegimeAdvisor()
    
    # Run all checks
    advisor.fetch_crash_indicators()
    advisor.print_regime_assessment()
    advisor.check_specific_conditions()
    advisor.get_daily_protocol()
    advisor.generate_alert_summary()
    
    # Final recommendation box
    print("\n" + "=" * 90)
    print(" " * 30 + "⚡ FINAL RECOMMENDATION")
    print("=" * 90)
    
    score = advisor.regime_score
    
    if score <= -10:
        rec = [
            ["🚀 ACTION", "DEPLOY EVERYTHING NOW", "This is a crash - buy aggressively"],
            ["📊 Score", str(score), "Capitulation level"],
            ["💵 Cash Usage", "100%", "Use all remaining powder"],
            ["⏰ Next Check", "Daily", "Monitor for regime change"]
        ]
        box_char = "🚀"
    elif score <= -6:
        rec = [
            ["💰 ACTION", "AGGRESSIVE BUYING", "Deploy 50% of capital"],
            ["📊 Score", str(score), "Severe bear - great opportunity"],
            ["💵 Cash Usage", "50%", "Scale in over 1-2 weeks"],
            ["⏰ Next Check", "Every 2-3 days", "Watch for improvement"]
        ]
        box_char = "💰"
    elif score <= -3:
        rec = [
            ["⏸️  ACTION", "HALT DEPLOYMENT", "Correction in progress"],
            ["📊 Score", str(score), "Risk elevated"],
            ["💵 Cash Usage", "0%", "No new positions"],
            ["⏰ Next Check", "Daily", "Wait for score > -2"]
        ]
        box_char = "⏸️"
    elif score <= 0:
        rec = [
            ["🛑 ACTION", "STOP TRADING", "Market overheated"],
            ["📊 Score", str(score), "Valuation concerns"],
            ["💵 Cash Usage", "0%", "Preserve capital"],
            ["⏰ Next Check", "Daily", "Wait for pullback"]
        ]
        box_char = "🛑"
    else:
        rec = [
            ["✅ ACTION", "NORMAL DEPLOYMENT", "Proceed with plan"],
            ["📊 Score", str(score), "Healthy conditions"],
            ["💵 Cash Usage", "10-20%/month", "Gradual deployment"],
            ["⏰ Next Check", "Daily before trading", "Standard protocol"]
        ]
        box_char = "✅"
    
    print(tabulate(
        rec,
        headers=["Category", "Recommendation", "Details"],
        tablefmt="fancy_grid"
    ))
    
    print("\n" + box_char * 90)
    print()
    print(f"💡 TIP: Run this script EVERY MORNING before trading")
    print(f"📧 Consider setting up a cron job to email you this report daily")
    print()
    print("=" * 90 + "\n")

if __name__ == "__main__":
    main()