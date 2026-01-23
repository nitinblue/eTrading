# trading_bot/agents/market_news_dude.py
"""
MarketNewsDude: Fetches market levels, alerts, and sentiment (neutral, bullish, bearish).
- Based on average % change in major indices.
- Passes 'market_sentiment' and 'alerts' in state.
"""

from typing import Dict
import yfinance as yf
import logging
import numpy as np

logger = logging.getLogger(__name__)

def market_news_dude(state: Dict) -> Dict:
    logger.info("MarketNewsDude: Fetching market update...")

    # Major indices for sentiment
    indices = {
        'S&P 500': '^GSPC',
        'Nifty 50': '^NSEI'
    }

    changes = []
    report_lines = []
    alerts = []

    for name, symbol in indices.items():
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="2d")
            if len(hist) < 2:
                continue

            current = hist['Close'].iloc[-1]
            previous = hist['Close'].iloc[-2]
            change_pct = (current - previous) / previous * 100
            changes.append(change_pct)

            report_lines.append(f"{name}: ${current:.2f} ({change_pct:+.2f}%)")

            if abs(change_pct) > 1.5:
                alerts.append(f"⚠️ Big move in {name} ({change_pct:+.2f}%)")

        except Exception as e:
            logger.warning(f"Failed for {name}: {e}")

    # Sentiment based on average change
    avg_change = np.mean(changes) if changes else 0.0
    thresholds = state.get('config', {}).get('technical', {}).get('sentiment_thresholds', {'bullish_change': 0.5, 'bearish_change': -0.5})
    if avg_change > thresholds['bullish_change']:
        sentiment = 'bullish'
    elif avg_change < thresholds['bearish_change']:
        sentiment = 'bearish'
    else:
        sentiment = 'neutral'

    state['market_sentiment'] = sentiment
    state['market_alerts'] = alerts
    state['market_report'] = "\n".join(report_lines)

    logger.info(f"Market sentiment: {sentiment} | Alerts: {len(alerts)}")

    state['output'] = state.get('output', "") + f"\nMarket Sentiment: {sentiment}"
    return state