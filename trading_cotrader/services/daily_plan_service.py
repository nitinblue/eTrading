"""Daily Plan Service — desk-aware plan generation.

Shared between API /plan endpoint and CLI 'plan' command.
Strategy: merge all desk tickers + strategies into ONE plan.generate() call
to avoid redundant market data fetches, then split results by desk.
"""

from datetime import date as date_cls
from pathlib import Path
from typing import Any, Optional
import logging
import time

import yaml

logger = logging.getLogger(__name__)

# Map desk keys → market_analyzer StrategyType string values
DESK_STRATEGY_MAP: dict[str, list[str]] = {
    'desk_0dte': ['zero_dte'],
    'desk_medium': ['iron_condor', 'iron_butterfly', 'calendar', 'diagonal',
                    'breakout', 'momentum', 'mean_reversion'],
    'desk_leaps': ['leap'],
}

PLAN_TIMEOUT_S = 180  # Total timeout for plan generation (13 tickers × multi-strategy)


def load_desk_configs() -> list[dict]:
    """Load desk portfolio configs from risk_config.yaml."""
    config_path = Path(__file__).parent.parent / "config" / "risk_config.yaml"
    if not config_path.exists():
        return []
    with open(config_path, 'r') as f:
        cfg = yaml.safe_load(f)
    desks = []
    for key, pcfg in (cfg.get('portfolios', {}) or {}).items():
        if key.startswith('desk_'):
            desks.append({
                'key': key,
                'display_name': pcfg.get('display_name', key),
                'tickers': pcfg.get('preferred_underlyings', []),
                'capital': pcfg.get('initial_capital', 10000),
            })
    return desks


def generate_desk_plan(ma: Any, tickers: Optional[list[str]] = None) -> dict:
    """Generate a desk-aware daily trading plan.

    Args:
        ma: MarketAnalyzer instance (with broker-injected providers).
        tickers: Optional override tickers (fallback if no desks configured).

    Returns:
        Dict with day_verdict, risk_budget, all_trades, desk_plans, etc.
    """
    from market_analyzer.models.ranking import StrategyType

    desks = load_desk_configs()

    if not desks:
        # No desks — use old behavior with cap
        if tickers and len(tickers) > 8:
            tickers = tickers[:8]
        result = ma.plan.generate(tickers, skip_intraday=True)
        return result.model_dump(mode='json')

    # Build per-desk strategy sets and collect all unique tickers
    desk_meta: list[dict] = []
    all_tickers: set[str] = set()
    all_strategies: set = set()

    for desk in desks:
        desk_key = desk['key']
        desk_tickers = desk['tickers']
        if not desk_tickers:
            continue

        strategy_names = DESK_STRATEGY_MAP.get(desk_key, [])
        strategies = []
        for sn in strategy_names:
            try:
                strategies.append(StrategyType(sn))
            except ValueError:
                pass
        if not strategies:
            continue

        desk_meta.append({
            **desk,
            'strategies': strategies,
            'strategy_values': {s.value for s in strategies},
            'ticker_set': set(desk_tickers),
        })
        all_tickers.update(desk_tickers)
        all_strategies.update(strategies)

    if not desk_meta:
        return {
            'as_of_date': str(date_cls.today()),
            'plan_for_date': str(date_cls.today()),
            'day_verdict': 'trade',
            'day_verdict_reasons': [],
            'risk_budget': {'max_new_positions': 3, 'max_daily_risk_dollars': 500, 'position_size_factor': 1.0},
            'expiry_events': [], 'upcoming_expiries': [],
            'trades_by_horizon': {}, 'all_trades': [],
            'total_trades': 0, 'desk_plans': [],
            'summary': 'No desks with valid strategies',
        }

    # ONE call with all unique tickers and all strategies
    unique_tickers = sorted(all_tickers)
    unique_strategies = sorted(all_strategies, key=lambda s: s.value)
    logger.info(
        f"Plan: generating for {len(unique_tickers)} tickers × "
        f"{len(unique_strategies)} strategies across {len(desk_meta)} desks"
    )
    t0 = time.perf_counter()

    result = ma.plan.generate(
        unique_tickers, strategies=unique_strategies, skip_intraday=True,
    )

    elapsed = time.perf_counter() - t0
    logger.info(f"Plan: generated in {elapsed:.1f}s")

    plan_data = result.model_dump(mode='json')
    all_trades = plan_data.get('all_trades', [])

    # Split trades into desks by ticker + strategy membership
    desk_plans = []
    combined_trades = []

    for dm in desk_meta:
        desk_trades = []
        for t in all_trades:
            ticker = t.get('ticker', '')
            strat = t.get('strategy_type', '')
            if ticker in dm['ticker_set'] and strat in dm['strategy_values']:
                tagged = {**t, 'desk': dm['display_name'], 'desk_key': dm['key']}
                desk_trades.append(tagged)
                combined_trades.append(tagged)

        desk_plans.append({
            'desk_key': dm['key'],
            'display_name': dm['display_name'],
            'capital': dm['capital'],
            'tickers': dm['tickers'],
            'trades': desk_trades,
            'trade_count': len(desk_trades),
        })

    # Re-rank combined trades
    combined_trades.sort(key=lambda t: t.get('composite_score', 0), reverse=True)
    for i, t in enumerate(combined_trades):
        t['rank'] = i + 1

    # Bucket by horizon
    trades_by_horizon: dict[str, list] = {}
    for t in combined_trades:
        h = t.get('horizon', 'monthly')
        trades_by_horizon.setdefault(h, []).append(t)

    return {
        'as_of_date': str(date_cls.today()),
        'plan_for_date': str(date_cls.today()),
        'day_verdict': plan_data.get('day_verdict', 'trade'),
        'day_verdict_reasons': plan_data.get('day_verdict_reasons', []),
        'risk_budget': plan_data.get('risk_budget', {'max_new_positions': 3, 'max_daily_risk_dollars': 500, 'position_size_factor': 1.0}),
        'expiry_events': plan_data.get('expiry_events', []),
        'upcoming_expiries': plan_data.get('upcoming_expiries', []),
        'trades_by_horizon': trades_by_horizon,
        'all_trades': combined_trades,
        'total_trades': len(combined_trades),
        'desk_plans': desk_plans,
        'elapsed_s': round(elapsed, 1),
        'summary': f"{len(combined_trades)} trades across {len(desk_plans)} desks ({elapsed:.0f}s)",
    }
