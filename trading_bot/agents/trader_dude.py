# trading_bot/agents/trader_dude.py
"""
TraderDude: Runs basket of strategies for current bucket.
- Selects strategy based on market conditions (IV, greeks from analysis).
- Identifies underlying.
- Prints signal (for now).
"""

from typing import Dict
import logging

logger = logging.getLogger(__name__)

# Simulated strategy basket
DEFINED_STRATEGIES = ['iron_condor', 'butterfly', 'credit_spread']
UNDEFINED_STRATEGIES = ['short_strangle', 'short_straddle']

def trader_dude(state: Dict) -> Dict:
    bucket = state.get('current_bucket')
    if bucket not in ['defined', 'undefined']:
        state['output'] = state.get('output', "") + "\nTrader: No bucket"
        return state

    logger.info(f"TraderDude: Running for {bucket} risk bucket")

    # Run basket for bucket
    strategies = DEFINED_STRATEGIES if bucket == 'defined' else UNDEFINED_STRATEGIES

    # Market conditions from analysis
    iv = state.get('analysis', {}).get('iv_rank', 50)
    selected = 'iron_condor' if iv > 50 and bucket == 'defined' else 'short_strangle' if bucket == 'undefined' else 'none'

    if selected != 'none':
        state['trade_signal'] = {"strategy": selected, "underlying": "MSFT", "bucket": bucket}
        state['output'] = state.get('output', "") + f"\nSIGNAL: {selected} on MSFT ({bucket} bucket)"
    else:
        state['output'] = state.get('output', "") + "\nNo signal"

    # After trader, go back to portfolio for next bucket
    return state