# trading_bot/agents/data_dude.py
"""
DataDude: Fetches market data.
"""

from typing import Dict
import logging

logger = logging.getLogger(__name__)

def data_dude(state: Dict) -> Dict:
    logger.info("DataDude: Fetching market data...")
    underlying = state.get('underlying', 'MSFT')
    # Simulated - replace with market_data.get_option_chain(underlying)
    state['data'] = {
        'price': 425.0,
        'option_chain_expiries': ['2026-01-16', '2026-09-18']
    }
    state['output'] = state.get('output', "") + f"\nData for {underlying}: Price $425.00"
    return state