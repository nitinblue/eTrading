# trading_bot/agents/market_news_dude.py
"""
MarketNewsDude: First agent in the workflow.
- Fetches current levels for US/India indices, USD/INR, commodities.
- Reports big jumps (>1.5% daily change) and high volatility (VIX >20, India VIX >15).
- Can trigger alerts on events (big moves, volatility spikes).
- Uses yfinance for free real-time data.
"""

from typing import Dict
import yfinance as yf
import logging
from tabulate import tabulate 

logger = logging.getLogger(__name__)

def market_news_dude(state: Dict) -> Dict:
    logger.info("MarketNewsDude: Fetching global market levels and alerts...")

    # Tickers
    tickers = {
        'S&P 500': '^GSPC',
        'Dow Jones': '^DJI',
        'Nasdaq': '^IXIC',
        'VIX': '^VIX',
        'Nifty 50': '^NSEI',
        'Sensex': '^BSESN',
        'USD/INR': 'INR=X',
        'Gold': 'GC=F',
        'Silver': 'SI=F',
        'Copper': 'HG=F',
        'Platinum': 'PL=F',
        'Palladium': 'PA=F',
        'Crude Oil': 'CL=F'
    }

    report = []
    alerts = []
    data = {}

    for name, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="2d")  # Today + yesterday
            if len(hist) < 2:
                report.append(f"{name}: Data unavailable")
                continue

            current = hist['Close'].iloc[-1]
            previous = hist['Close'].iloc[-2]
            change_pct = (current - previous) / previous * 100

            data[name] = {'current': current, 'change_pct': change_pct}

            report.append(f"{name}: ${current:.2f} ({change_pct:+.2f}%)")

            # Big jump alert
            if abs(change_pct) > 1.5 and name in ['S&P 500', 'Dow Jones', 'Nasdaq', 'Nifty 50', 'Sensex']:
                alerts.append(f"ALERT: Big move in {name} ({change_pct:+.2f}%)")

            # Volatility alert
            if name == 'VIX' and current > 20:
                alerts.append(f"ALERT: High US volatility (VIX {current:.2f})")
            if name == 'India VIX' and current > 15:  # Assuming you add '^INDIAVIX'
                alerts.append(f"ALERT: High India volatility ({current:.2f})")

        except Exception as e:
            logger.warning(f"Failed for {name} ({ticker}): {e}")
            report.append(f"{name}: Error fetching data")

    # Full report
    full_report = "\n".join(report)
    if alerts:
        full_report += "\n\n" + "\n".join(alerts)

    state['market_news'] = {
        'report': full_report,
        'alerts': alerts,
        'raw_data': data
    }
    state['output'] = state.get('output', "") + f"\nMarket News:\n{full_report}"

    logger.info(f"Market Report: {full_report}")
    logger.info(f"MarketNewsDude complete. Alerts: {len(alerts)}")
    return state