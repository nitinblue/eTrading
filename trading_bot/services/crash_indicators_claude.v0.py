import yfinance as yf
from tabulate import tabulate
import pandas as pd
import numpy as np
from datetime import datetime

from trading_bot.services.crash_indicators import get_crash_prewarning_indicators

class CrashRadar:
    def __init__(self):
        self.lookback = "5d"
        self.indicators = {}
        
    def fetch_price_data(self, ticker, period="5d"):
        """Safely fetch price data with error handling."""
        try:
            data = yf.Ticker(ticker).history(period=period)['Close']
            return data if len(data) > 0 else None
        except Exception as e:
            print(f"Error fetching {ticker}: {str(e)}")
            return None
    
    def safe_pct_change(self, series, start_idx, end_idx):
        """Calculate percentage change with bounds checking."""
        try:
            if series is None or len(series) <= max(abs(start_idx), abs(end_idx)):
                return None
            return (series.iloc[end_idx] / series.iloc[start_idx] - 1) * 100
        except:
            return None
    
    def calculate_z_score(self, current, series):
        """Calculate z-score for anomaly detection."""
        if series is None or len(series) < 2:
            return 0
        mean = series.mean()
        std = series.std()
        return (current - mean) / std if std > 0 else 0
    
    def get_volatility_indicators(self):
        """VIX, VVIX, and VIX term structure."""
        results = []
        
        # VIX Spike
        vix = self.fetch_price_data("^VIX", "20d")
        if vix is not None and len(vix) >= 6:
            spike = self.safe_pct_change(vix, -6, -1)
            if spike is not None:
                z = self.calculate_z_score(vix.iloc[-1], vix)
                status = "🔴 ALERT" if spike > 20 or z > 2 else "🟢 Normal"
                results.append(["VIX 5D Spike", f"{spike:.2f}%", "LIVE", status])
                results.append(["VIX Level", f"{vix.iloc[-1]:.2f}", "LIVE", 
                              "🔴 FEAR" if vix.iloc[-1] > 30 else "🟡 Elevated" if vix.iloc[-1] > 20 else "🟢 Low"])
                self.indicators['vix'] = vix.iloc[-1]
        
        if not results:
            results.append(["VIX Data", "N/A", "ERROR", "Data Unavailable"])
        
        # VIX Term Structure (VXX/VIX ratio as proxy)
        vxx = self.fetch_price_data("VXX", "5d")
        if vix is not None and vxx is not None and len(vix) > 0 and len(vxx) > 0:
            if vix.iloc[-1] > 0:
                term_structure = vxx.iloc[-1] / vix.iloc[-1]
                status = "🔴 INVERTED" if term_structure < 0.95 else "🟢 Normal"
                results.append(["VIX Term Structure", f"{term_structure:.3f}", "LIVE", status])
        
        return results
    
    def get_credit_indicators(self):
        """Credit spreads and high-yield bond stress."""
        results = []
        
        # HYG vs TLT (better spread proxy)
        hyg = self.fetch_price_data("HYG", "20d")
        tlt = self.fetch_price_data("TLT", "20d")
        
        if hyg is not None and tlt is not None and len(hyg) > 1 and len(tlt) > 1:
            hyg_ret = hyg.pct_change().iloc[-1]
            tlt_ret = tlt.pct_change().iloc[-1]
            spread = hyg_ret - tlt_ret
            
            status = "🔴 WIDENING" if spread < -0.01 else "🟡 Watch" if spread < 0 else "🟢 Stable"
            results.append(["Credit Spread (HYG-TLT)", f"{spread:.4f}", "LIVE", status])
            
            # HYG 20-day trend
            if len(hyg) >= 20:
                hyg_trend = self.safe_pct_change(hyg, -20, -1)
                if hyg_trend is not None:
                    results.append(["HYG 20D Trend", f"{hyg_trend:.2f}%", "LIVE",
                                  "🔴 Stress" if hyg_trend < -5 else "🟢 Healthy"])
        
        # LQD (Investment Grade) for comparison
        lqd = self.fetch_price_data("LQD", "5d")
        if lqd is not None and len(lqd) > 1:
            lqd_ret = lqd.pct_change().iloc[-1] * 100
            results.append(["LQD Daily Return", f"{lqd_ret:.3f}%", "LIVE", "Monitor"])
        
        if not results:
            results.append(["Credit Data", "N/A", "ERROR", "Data Unavailable"])
        
        return results
    
    def get_valuation_indicators(self):
        """P/E ratios and valuation metrics."""
        results = []
        
        try:
            spy_info = yf.Ticker("SPY").info
            fwd_pe = spy_info.get('forwardPE') or spy_info.get('trailingPE') or 0.0
            pe_display = f"{fwd_pe:.2f}" if fwd_pe > 0 else "[UNAVAILABLE]"
            pe_status = "🔴 OVERVALUED" if fwd_pe > 22 else "🟡 Fair" if fwd_pe > 18 else "🟢 Cheap" if fwd_pe > 0 else "❓ UNKNOWN"
            results.append(["SPY P/E Ratio", pe_display, "LIVE", pe_status])
        except:
            results.append(["SPY P/E Ratio", "[ERROR]", "ERROR", "API Issue"])
        
        # Shiller CAPE placeholder
        results.append(["Shiller CAPE", "[MULTPL.COM]", "STATIC", "Check multpl.com/shiller-pe"])
        
        return results
    
    def get_intermarket_indicators(self):
        """Cross-asset relationships and flight-to-safety flows."""
        results = []
        
        # Dollar Strength (DXY)
        dxy = self.fetch_price_data("DX-Y.NYB", "20d")
        if dxy is not None and len(dxy) >= 20:
            dxy_chg = self.safe_pct_change(dxy, -20, -1)
            if dxy_chg is not None:
                status = "🔴 Strong $" if dxy_chg > 5 else "🟡 Rising" if dxy_chg > 2 else "🟢 Weak"
                results.append(["Dollar Index (DXY)", f"{dxy.iloc[-1]:.2f}", "LIVE", 
                              f"{status} ({dxy_chg:+.2f}%)"])
        
        # Gold (safe haven)
        gld = self.fetch_price_data("GLD", "20d")
        if gld is not None and len(gld) >= 20:
            gld_chg = self.safe_pct_change(gld, -20, -1)
            if gld_chg is not None:
                status = "🟡 Bid" if gld_chg > 5 else "🟢 Normal"
                results.append(["Gold (GLD)", f"${gld.iloc[-1]:.2f}", "LIVE", 
                              f"{status} ({gld_chg:+.2f}%)"])
        
        # Silver (risk barometer)
        slv = self.fetch_price_data("SLV", "20d")
        if slv is not None and len(slv) >= 20:
            slv_chg = self.safe_pct_change(slv, -20, -1)
            if slv_chg is not None:
                results.append(["Silver (SLV)", f"${slv.iloc[-1]:.2f}", "LIVE", f"{slv_chg:+.2f}%"])
        
        # Crude Oil (economic activity)
        cl = self.fetch_price_data("CL=F", "20d")
        if cl is not None and len(cl) >= 20:
            cl_chg = self.safe_pct_change(cl, -20, -1)
            if cl_chg is not None:
                status = "🔴 Collapse" if cl_chg < -15 else "🟡 Weak" if cl_chg < -5 else "🟢 Healthy"
                results.append(["Crude Oil (WTI)", f"${cl.iloc[-1]:.2f}", "LIVE", 
                              f"{status} ({cl_chg:+.2f}%)"])
        
        # Copper (Dr. Copper recession indicator)
        hg = self.fetch_price_data("HG=F", "20d")
        if hg is not None and len(hg) >= 20:
            hg_chg = self.safe_pct_change(hg, -20, -1)
            if hg_chg is not None:
                status = "🔴 Warning" if hg_chg < -10 else "🟢 Healthy"
                results.append(["Copper (HG)", f"${hg.iloc[-1]:.4f}", "LIVE", 
                              f"{status} ({hg_chg:+.2f}%)"])
        
        # Bitcoin (speculative risk appetite)
        btc = self.fetch_price_data("BTC-USD", "20d")
        if btc is not None and len(btc) >= 20:
            btc_chg = self.safe_pct_change(btc, -20, -1)
            if btc_chg is not None:
                results.append(["Bitcoin", f"${btc.iloc[-1]:,.0f}", "LIVE", f"{btc_chg:+.2f}%"])
        
        if not results:
            results.append(["Intermarket Data", "N/A", "ERROR", "Data Unavailable"])
        
        return results
    
    def get_yield_curve_indicators(self):
        """Treasury yield curve analysis."""
        results = []
        
        # 10Y-2Y Spread
        tnx = self.fetch_price_data("^TNX", "5d")  # 10-year
        tyx = self.fetch_price_data("^FVX", "5d")  # 5-year
        
        if tnx is not None and tyx is not None and len(tnx) > 0 and len(tyx) > 0:
            spread = tnx.iloc[-1] - tyx.iloc[-1]
            status = "🔴 INVERTED" if spread < 0 else "🟡 Flat" if spread < 0.5 else "🟢 Normal"
            results.append(["10Y-5Y Spread", f"{spread:.2f} bps", "LIVE", status])
        
        # 10Y Yield Level
        if tnx is not None and len(tnx) > 0:
            results.append(["10Y Treasury Yield", f"{tnx.iloc[-1]:.2f}%", "LIVE", 
                          "🔴 High" if tnx.iloc[-1] > 5 else "🟢 Moderate"])
        
        # TLT (20Y Treasury ETF)
        tlt = self.fetch_price_data("TLT", "20d")
        if tlt is not None and len(tlt) >= 20:
            tlt_chg = self.safe_pct_change(tlt, -20, -1)
            if tlt_chg is not None:
                status = "🟡 Bid" if tlt_chg > 3 else "🟢 Normal"
                results.append(["TLT 20D Trend", f"{tlt_chg:+.2f}%", "LIVE", status])
        
        if not results:
            results.append(["Yield Curve Data", "N/A", "ERROR", "Data Unavailable"])
        
        return results
    
    def get_breadth_indicators(self):
        """Market breadth and participation metrics."""
        results = []
        
        # SPY vs RSP (equal-weight)
        spy = self.fetch_price_data("SPY", "20d")
        rsp = self.fetch_price_data("RSP", "20d")
        
        if spy is not None and rsp is not None and len(spy) >= 20 and len(rsp) >= 20:
            spy_ret = self.safe_pct_change(spy, -20, -1)
            rsp_ret = self.safe_pct_change(rsp, -20, -1)
            
            if spy_ret is not None and rsp_ret is not None:
                divergence = spy_ret - rsp_ret
                status = "🔴 NARROW" if divergence > 5 else "🟢 Healthy"
                results.append(["SPY vs RSP Divergence", f"{divergence:+.2f}%", "LIVE", status])
        
        # Put/Call Ratio placeholder
        results.append(["Put/Call Ratio", "[CBOE.COM]", "STATIC", "Check CBOE website"])
        
        # Advance/Decline Line placeholder
        results.append(["NYSE A/D Line", "[EXTERNAL]", "STATIC", "Requires NYSE data"])
        
        return results
    
    def get_sector_rotation_indicators(self):
        """Defensive vs cyclical sector rotation."""
        results = []
        
        # XLF/XLU ratio
        xlf = self.fetch_price_data("XLF", "20d")
        xlu = self.fetch_price_data("XLU", "20d")
        
        if xlf is not None and xlu is not None and len(xlf) >= 20 and len(xlu) >= 20:
            if xlu.iloc[-1] > 0 and xlu.iloc[-20] > 0:
                ratio = xlf.iloc[-1] / xlu.iloc[-1]
                ratio_old = xlf.iloc[-20] / xlu.iloc[-20]
                ratio_chg = (ratio / ratio_old - 1) * 100
                status = "🔴 Risk-Off" if ratio_chg < -5 else "🟢 Risk-On" if ratio_chg > 5 else "🟡 Neutral"
                results.append(["XLF/XLU Ratio", f"{ratio:.3f}", "LIVE", 
                              f"{status} ({ratio_chg:+.2f}%)"])
        
        # Defensive sectors strength
        xly = self.fetch_price_data("XLY", "20d")
        xlp = self.fetch_price_data("XLP", "20d")
        
        if xly is not None and len(xly) >= 20:
            xly_ret = self.safe_pct_change(xly, -20, -1)
            if xly_ret is not None:
                results.append(["XLY (Discretionary)", f"{xly_ret:+.2f}%", "LIVE", "20D Return"])
        
        if xlp is not None and len(xlp) >= 20:
            xlp_ret = self.safe_pct_change(xlp, -20, -1)
            if xlp_ret is not None:
                results.append(["XLP (Staples)", f"{xlp_ret:+.2f}%", "LIVE", "20D Return"])
        
        if not results:
            results.append(["Sector Data", "N/A", "ERROR", "Data Unavailable"])
        
        return results
    
    def get_money_supply_indicators(self):
        """Money supply metrics (require FRED API)."""
        results = [
            ["M1 Money Supply", "[FRED REQUIRED]", "STATIC", "YoY growth rate"],
            ["M2 Money Supply", "[FRED REQUIRED]", "STATIC", "YoY growth rate"],
            ["M2 Velocity", "[FRED REQUIRED]", "STATIC", "Liquidity indicator"],
            ["Fed Balance Sheet", "[FRED REQUIRED]", "STATIC", "QT/QE status"]
        ]
        return results
    
    def get_legacy_indicators(self):
        """Original indicators from your file."""
        results = []
        results.append(["Insider Selling Ratio", "1.45", "[STATIC]", "Monitor for > 2.0"])
        results.append(["Margin Debt Level", "820B", "[STATIC]", "Updated Monthly Only"])
        return results
    
    def calculate_composite_score(self):
        """Generate 0-100 crash risk score."""
        score = 0
        weights = []
        
        # VIX contribution
        if 'vix' in self.indicators:
            vix_score = min(self.indicators['vix'] / 40 * 100, 100)
            score += vix_score * 0.3
            weights.append(0.3)
        
        normalized_score = score / sum(weights) if weights else 0
        
        if normalized_score > 70:
            status = "🔴 EXTREME RISK"
        elif normalized_score > 50:
            status = "🟠 HIGH RISK"
        elif normalized_score > 30:
            status = "🟡 ELEVATED"
        else:
            status = "🟢 LOW RISK"
        
        return normalized_score, status
    
    def generate_report(self):
        """Compile full crash radar report."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print("\n" + "=" * 80)
        print(f"{'CRASH RADAR SYSTEM':^80}")
        print(f"{timestamp:^80}")
        print("=" * 80 + "\n")
        
        sections = [
            ("VOLATILITY INDICATORS", self.get_volatility_indicators()),
            ("CREDIT STRESS INDICATORS", self.get_credit_indicators()),
            ("VALUATION METRICS", self.get_valuation_indicators()),
            ("YIELD CURVE ANALYSIS", self.get_yield_curve_indicators()),
            ("INTERMARKET FLOWS", self.get_intermarket_indicators()),
            ("BREADTH & PARTICIPATION", self.get_breadth_indicators()),
            ("SECTOR ROTATION", self.get_sector_rotation_indicators()),
            ("MONEY SUPPLY (FRED)", self.get_money_supply_indicators()),
            ("LEGACY INDICATORS", self.get_legacy_indicators()),
        ]
        
        all_data = []
        for section_name, section_data in sections:
            print(f"\n{'─' * 80}")
            print(f"  {section_name}")
            print(f"{'─' * 80}")
            if section_data:
                print(tabulate(section_data, 
                             headers=["Metric", "Value", "Source", "Status"],
                             tablefmt="fancy_grid"))
                all_data.extend(section_data)
            else:
                print("  [No data available]")
        
        # Composite Score
        composite, status = self.calculate_composite_score()
        print("\n" + "=" * 80)
        print(f"  COMPOSITE CRASH RISK SCORE: {composite:.1f}/100 - {status}")
        print("=" * 80)
        
        return all_data

def get_deployment_signal():
    indicators = get_crash_prewarning_indicators()
    
    score = 0
    if indicators['vix_spike'] > 20: score += 2
    if indicators['fwd_pe'] > 25: score += 1
    # ... add other conditions
    
    if score >= 4:
        return "🔴 HALT DEPLOYMENT - High Risk"
    elif score >= 2:
        return "🟡 CAUTION - Reduce Size"
    else:
        return "🟢 CLEAR - Normal Deployment"
    
# Run the radar
if __name__ == "__main__":
    print("Todays deployment signal: " + get_deployment_signal())
    radar = CrashRadar()
    radar.generate_report()