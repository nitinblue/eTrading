# trading_bot/agents/portfolio_dude.py
"""
PortfolioDude: Manages allocation buckets using real broker positions.
"""

from typing import Dict
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

def portfolio_dude(state: Dict) -> Dict:
    logger.info("PortfolioDude: Assessing portfolio and allocation buckets...")

    broker = state.get('broker')
    config = state.get('config')
    if not broker or not config:
        logger.error("Broker or config not in state")
        state['output'] = state.get('output', "") + "\nERROR: Broker or config missing"
        state['current_bucket'] = 'done'
        return state

    # Fetch real balance
    try:
        balance = broker.get_account_balance()
        total_capital = float(balance.get('equity', balance.get('net-liquidating-value')))
        logger.info(f"Total capital: ${total_capital:.2f}")
    except Exception as e:
        logger.error(f"Balance fetch failed: {e}")
        total_capital = 100000.0

    # Safe Pydantic access for allocation
    strategies = getattr(config, 'strategies', None)
    if strategies is None:
        logger.error("strategies not in config")
        defined_alloc_pct = 0.8
        undefined_alloc_pct = 0.2
    else:
        allocation = getattr(strategies, 'allocation', {})
        defined_alloc_pct = allocation.get('defined_risk', 0.8)
        undefined_alloc_pct = allocation.get('undefined_risk', 0.2)

    defined_allocation = total_capital * defined_alloc_pct
    undefined_allocation = total_capital * undefined_alloc_pct

    # Fetch positions
    try:
        positions = broker.get_positions()
    except Exception as e:
        logger.error(f"Positions fetch failed: {e}")
        positions = []

    # Risk calculation (simulated — fix later)
    defined_used = 0
    undefined_used = 0
    for pos in positions:
        quantity = abs(pos.get('quantity', 0))
        if quantity == 0:
            continue
        # Simulated risk
        if 'spread' in pos.get('strategy', '').lower():
            defined_used = defined_used + (500 * quantity)
        else:
            undefined_used = undefined_used + (1000 * quantity)

    defined_available = max(0, defined_allocation - defined_used)
    undefined_available = max(0, undefined_allocation - undefined_used)

    state['portfolio'] = {
        'total_capital': total_capital,
        'defined_allocation': defined_allocation,
        'undefined_allocation': undefined_allocation,
        'defined_used': defined_used,
        'undefined_used': undefined_used,
        'defined_available': defined_available,
        'undefined_available': undefined_available,
        'positions': positions
    }

    logger.info(f"Defined available: ${defined_available:.2f}")
    logger.info(f"Undefined available: ${undefined_available:.2f}")

    state['output'] = state.get('output', "") + f"\nPortfolio: Defined ${defined_available:.2f} | Undefined ${undefined_available:.2f}"

    # Set next bucket
    current = state.get('current_bucket')
    if current is None:
        state['current_bucket'] = 'defined' if defined_available > 0 else 'undefined' if undefined_available > 0 else 'done'
    elif current == 'defined':
        state['current_bucket'] = 'undefined' if undefined_available > 0 else 'done'
    elif current == 'undefined':
        state['current_bucket'] = 'done'

    return state