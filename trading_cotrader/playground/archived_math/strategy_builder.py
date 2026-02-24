"""
Strategy Builder — Generates ranked strategy proposals for a ticker.

Uses ResearchEntry data (regime, opportunities, levels) to determine
applicable strategies, constructs legs, computes payoff, checks fitness,
and returns a scored/ranked list.

Extracted construct_legs() from api_trading_sheet.py lives here as the
canonical leg-construction utility.
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional
import logging
import math

from trading_cotrader.services.pricing.probability import ProbabilityCalculator, ProbabilityResult
from trading_cotrader.services.portfolio_fitness import PortfolioFitnessChecker

logger = logging.getLogger(__name__)

_prob_calc = ProbabilityCalculator()
_fitness_checker = PortfolioFitnessChecker()


# ---------------------------------------------------------------------------
# Strategy Catalog
# ---------------------------------------------------------------------------

STRATEGY_CATALOG: Dict[str, Dict[str, Any]] = {
    'iron_condor': {
        'display_name': 'Iron Condor',
        'legs': 4,
        'risk_profile': 'defined',
        'default_dte': 45,
        'regimes': ['R1', 'R2'],
    },
    'put_credit_spread': {
        'display_name': 'Put Credit Spread',
        'legs': 2,
        'risk_profile': 'defined',
        'default_dte': 45,
        'regimes': ['R1', 'R3'],
    },
    'call_credit_spread': {
        'display_name': 'Call Credit Spread',
        'legs': 2,
        'risk_profile': 'defined',
        'default_dte': 45,
        'regimes': ['R1', 'R3'],
    },
    'iron_butterfly': {
        'display_name': 'Iron Butterfly',
        'legs': 4,
        'risk_profile': 'defined',
        'default_dte': 14,
        'regimes': ['R1'],
    },
    'strangle': {
        'display_name': 'Short Strangle',
        'legs': 2,
        'risk_profile': 'undefined',
        'default_dte': 45,
        'regimes': ['R1'],
    },
    'long_put': {
        'display_name': 'Long Put',
        'legs': 1,
        'risk_profile': 'defined',
        'default_dte': 45,
        'regimes': ['R4'],
    },
    'long_call': {
        'display_name': 'Long Call',
        'legs': 1,
        'risk_profile': 'defined',
        'default_dte': 45,
        'regimes': ['R4'],
    },
}

# Regime -> strategy mapping
REGIME_STRATEGIES: Dict[str, List[str]] = {
    'R1': ['iron_condor', 'put_credit_spread', 'strangle'],
    'R2': ['iron_condor', 'put_credit_spread', 'call_credit_spread'],
    'R3': ['put_credit_spread', 'call_credit_spread'],
    'R4': ['long_put', 'long_call', 'put_credit_spread'],
}


# ---------------------------------------------------------------------------
# Leg Construction (extracted from api_trading_sheet.py)
# ---------------------------------------------------------------------------

def construct_legs(
    strategy_type: str,
    spot: float,
    iv: float,
    dte: int,
    direction: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Construct option legs for a given strategy type.

    Returns list of dicts with: strike, option_type, quantity, side, expiration.
    """
    stype = strategy_type.lower()
    expiration = (date.today() + timedelta(days=dte)).isoformat()

    # Ensure IV is reasonable for strike math
    safe_iv = max(iv, 0.10)

    if stype in ('iron_condor',):
        put_short = round(spot * (1 - 0.20 * safe_iv), 0)
        put_long = round(put_short - spot * 0.03, 0)
        call_short = round(spot * (1 + 0.20 * safe_iv), 0)
        call_long = round(call_short + spot * 0.03, 0)
        return [
            {'strike': put_long, 'option_type': 'put', 'quantity': 1, 'side': 'buy', 'expiration': expiration},
            {'strike': put_short, 'option_type': 'put', 'quantity': -1, 'side': 'sell', 'expiration': expiration},
            {'strike': call_short, 'option_type': 'call', 'quantity': -1, 'side': 'sell', 'expiration': expiration},
            {'strike': call_long, 'option_type': 'call', 'quantity': 1, 'side': 'buy', 'expiration': expiration},
        ]

    if stype == 'iron_butterfly':
        atm = round(spot, 0)
        wing = round(spot * 0.05, 0)
        return [
            {'strike': atm - wing, 'option_type': 'put', 'quantity': 1, 'side': 'buy', 'expiration': expiration},
            {'strike': atm, 'option_type': 'put', 'quantity': -1, 'side': 'sell', 'expiration': expiration},
            {'strike': atm, 'option_type': 'call', 'quantity': -1, 'side': 'sell', 'expiration': expiration},
            {'strike': atm + wing, 'option_type': 'call', 'quantity': 1, 'side': 'buy', 'expiration': expiration},
        ]

    if stype in ('put_credit_spread',):
        short_strike = round(spot * (1 - 0.30 * safe_iv), 0)
        long_strike = round(short_strike - spot * 0.03, 0)
        return [
            {'strike': short_strike, 'option_type': 'put', 'quantity': -1, 'side': 'sell', 'expiration': expiration},
            {'strike': long_strike, 'option_type': 'put', 'quantity': 1, 'side': 'buy', 'expiration': expiration},
        ]

    if stype in ('call_credit_spread',):
        short_strike = round(spot * (1 + 0.30 * safe_iv), 0)
        long_strike = round(short_strike + spot * 0.03, 0)
        return [
            {'strike': short_strike, 'option_type': 'call', 'quantity': -1, 'side': 'sell', 'expiration': expiration},
            {'strike': long_strike, 'option_type': 'call', 'quantity': 1, 'side': 'buy', 'expiration': expiration},
        ]

    if stype in ('strangle', 'short_strangle'):
        put_strike = round(spot * (1 - 0.20 * safe_iv), 0)
        call_strike = round(spot * (1 + 0.20 * safe_iv), 0)
        return [
            {'strike': put_strike, 'option_type': 'put', 'quantity': -1, 'side': 'sell', 'expiration': expiration},
            {'strike': call_strike, 'option_type': 'call', 'quantity': -1, 'side': 'sell', 'expiration': expiration},
        ]

    if stype == 'long_put':
        strike = round(spot * (1 - 0.05), 0)  # slightly OTM
        return [
            {'strike': strike, 'option_type': 'put', 'quantity': 1, 'side': 'buy', 'expiration': expiration},
        ]

    if stype == 'long_call':
        strike = round(spot * (1 + 0.05), 0)  # slightly OTM
        return [
            {'strike': strike, 'option_type': 'call', 'quantity': 1, 'side': 'buy', 'expiration': expiration},
        ]

    # Fallback: put credit spread
    short_strike = round(spot * 0.95, 0)
    long_strike = round(spot * 0.92, 0)
    return [
        {'strike': short_strike, 'option_type': 'put', 'quantity': -1, 'side': 'sell', 'expiration': expiration},
        {'strike': long_strike, 'option_type': 'put', 'quantity': 1, 'side': 'buy', 'expiration': expiration},
    ]


# ---------------------------------------------------------------------------
# Core: Build Strategy Proposals
# ---------------------------------------------------------------------------

def build_strategy_proposals(
    ticker: str,
    research_entry: Any,  # ResearchEntry dataclass
    spot: float,
    iv: float,
    portfolio_state: Dict[str, Any],
    risk_limits: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Generate ranked strategy proposals for a ticker based on research data.

    Uses regime, opportunity verdicts, and levels direction to determine
    applicable strategies. Constructs legs, computes payoff, checks fitness,
    and returns sorted by score.
    """
    # Diagnostics trace — always built, returned alongside proposals
    diag: List[str] = []

    if spot <= 0 or iv <= 0:
        diag.append(f"EARLY EXIT: spot={spot}, iv={iv}. Need both > 0.")
        return [], diag

    diag.append(f"Inputs: spot=${spot:.2f}, iv={iv:.4f} ({iv*100:.1f}%)")

    # 1. Determine applicable strategies from 3 sources
    candidates: List[Dict[str, Any]] = []

    # Source A: Regime-based strategies
    regime_label = getattr(research_entry, 'hmm_regime_label', None) or ''
    regime_key = regime_label.split('_')[0] if regime_label else ''  # "R1", "R2", etc.
    if not regime_key and getattr(research_entry, 'hmm_regime_id', None):
        regime_key = f"R{research_entry.hmm_regime_id}"

    regime_strats = REGIME_STRATEGIES.get(regime_key, ['put_credit_spread'])
    diag.append(f"Regime: key={regime_key or '(none)'}, label={regime_label or '(none)'} -> strategies: {regime_strats}")
    for stype in regime_strats:
        candidates.append({
            'strategy_type': stype,
            'source': f'regime:{regime_key}',
            'regime_match': True,
            'opp_confidence': 0.0,
        })

    # Source B: Opportunity verdicts
    opp_map = {
        'zero_dte': ('opp_zero_dte_verdict', 'opp_zero_dte_confidence', 'opp_zero_dte_strategy'),
        'leap': ('opp_leap_verdict', 'opp_leap_confidence', 'opp_leap_strategy'),
        'breakout': ('opp_breakout_verdict', 'opp_breakout_confidence', 'opp_breakout_strategy'),
        'momentum': ('opp_momentum_verdict', 'opp_momentum_confidence', 'opp_momentum_strategy'),
    }

    for opp_name, (v_attr, c_attr, s_attr) in opp_map.items():
        verdict = getattr(research_entry, v_attr, None)
        confidence = getattr(research_entry, c_attr, None) or 0.0
        strategy_hint = getattr(research_entry, s_attr, None)

        verdict_str = verdict.upper() if verdict else '(none)'
        diag.append(f"Opp[{opp_name}]: verdict={verdict_str}, conf={confidence:.2f}, hint={strategy_hint or '(none)'}")

        if verdict and verdict.upper() in ('GO', 'CAUTION'):
            opp_stype = _map_opp_to_strategy(opp_name, strategy_hint, regime_key)
            if opp_stype:
                already = any(c['strategy_type'] == opp_stype for c in candidates)
                if not already:
                    adj_confidence = confidence if verdict.upper() == 'GO' else confidence * 0.5
                    candidates.append({
                        'strategy_type': opp_stype,
                        'source': f'opportunity:{opp_name}',
                        'regime_match': opp_stype in regime_strats,
                        'opp_confidence': adj_confidence,
                    })
                    diag.append(f"  -> Added candidate: {opp_stype} (source: {opp_name})")
                else:
                    diag.append(f"  -> Skipped {opp_stype} (already in candidates)")

    # Source C: Levels direction bias
    direction = getattr(research_entry, 'levels_direction', None)
    diag.append(f"Levels: direction={direction or '(none)'}")
    if direction == 'long':
        _ensure_candidate(candidates, 'put_credit_spread', 'levels:long', regime_strats)
    elif direction == 'short':
        _ensure_candidate(candidates, 'call_credit_spread', 'levels:short', regime_strats)

    diag.append(f"Total candidates: {len(candidates)} -> {[c['strategy_type'] for c in candidates]}")

    # 2. For each candidate, construct legs + compute payoff + check fitness + score
    proposals: List[Dict[str, Any]] = []
    seen_types = set()

    for cand in candidates:
        stype = cand['strategy_type']
        if stype in seen_types:
            continue
        seen_types.add(stype)

        catalog = STRATEGY_CATALOG.get(stype, {})
        dte = catalog.get('default_dte', 45)

        legs = construct_legs(stype, spot, iv, dte, direction)
        if not legs:
            diag.append(f"  [{stype}] construct_legs returned empty -> SKIP")
            continue

        payoff_result = _safe_compute_payoff(legs, spot, iv, dte)
        if payoff_result is None:
            diag.append(f"  [{stype}] payoff computation FAILED -> SKIP")
            continue

        pop = payoff_result.probability_of_profit
        ev = payoff_result.expected_value
        max_profit = payoff_result.max_profit
        max_loss = payoff_result.max_loss

        trade_margin = max_loss if max_loss != float('inf') else abs(ev) * 10
        fitness = _safe_check_fitness(
            portfolio_state, risk_limits,
            ticker, trade_margin, spot,
        )

        levels_data = {
            'stop_price': getattr(research_entry, 'levels_stop_price', None),
            'stop_distance_pct': getattr(research_entry, 'levels_stop_distance_pct', None),
            'best_target_price': getattr(research_entry, 'levels_best_target_price', None),
            'best_target_rr': getattr(research_entry, 'levels_best_target_rr', None),
        }

        rr = levels_data['best_target_rr'] or 0
        rr_normalized = min(rr / 5.0, 1.0)
        fits = fitness.get('fits_portfolio', False)
        regime_match = cand.get('regime_match', False)
        opp_conf = cand.get('opp_confidence', 0.0)

        score = (
            pop * 30
            + rr_normalized * 30
            + opp_conf * 20
            + (10 if fits else 0)
            + (10 if regime_match else 0)
        )

        diag.append(
            f"  [{stype}] POP={pop:.2f} EV=${ev:.0f} MaxLoss=${max_loss:.0f} "
            f"R:R={rr:.1f} fits={fits} regime={regime_match} -> score={score:.1f}"
        )

        proposals.append({
            'strategy_type': stype,
            'display_name': catalog.get('display_name', stype.replace('_', ' ').title()),
            'source': cand['source'],
            'dte': dte,
            'legs': legs,
            'payoff': {
                'pop': round(pop, 4),
                'ev': round(ev, 2),
                'max_profit': round(max_profit, 2) if max_profit != float('inf') else None,
                'max_loss': round(max_loss, 2) if max_loss != float('inf') else None,
                'breakevens': [round(b, 2) for b in payoff_result.breakeven_prices],
            },
            'levels': levels_data,
            'fitness': fitness,
            'score': round(score, 2),
        })

    proposals.sort(key=lambda p: p['score'], reverse=True)
    for i, p in enumerate(proposals):
        p['rank'] = i + 1

    diag.append(f"Result: {len(proposals)} proposals returned")
    return proposals, diag


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _map_opp_to_strategy(
    opp_name: str,
    strategy_hint: Optional[str],
    regime_key: str,
) -> Optional[str]:
    """Map an opportunity type to a concrete strategy type."""
    if strategy_hint:
        hint_lower = strategy_hint.lower()
        for stype in STRATEGY_CATALOG:
            if stype in hint_lower or hint_lower in stype:
                return stype

    # Default mapping by opportunity type
    defaults = {
        'zero_dte': 'iron_condor',
        'leap': 'long_call',
        'breakout': 'long_call' if regime_key != 'R4' else 'long_put',
        'momentum': 'put_credit_spread',
    }
    return defaults.get(opp_name)


def _ensure_candidate(
    candidates: List[Dict],
    stype: str,
    source: str,
    regime_strats: List[str],
) -> None:
    """Add a candidate if not already present."""
    if not any(c['strategy_type'] == stype for c in candidates):
        candidates.append({
            'strategy_type': stype,
            'source': source,
            'regime_match': stype in regime_strats,
            'opp_confidence': 0.0,
        })


def _safe_compute_payoff(
    legs: List[Dict], spot: float, iv: float, dte: int,
) -> Optional[ProbabilityResult]:
    """Compute payoff, returning None on error."""
    try:
        return _prob_calc.compute_trade_payoff(
            legs=legs, spot=spot, iv=max(iv, 0.10), dte=dte,
        )
    except Exception as e:
        logger.warning(f"Payoff computation failed: {e}")
        return None


def _safe_check_fitness(
    portfolio_state: Dict,
    risk_limits: Dict,
    ticker: str,
    trade_margin: float,
    spot: float,
) -> Dict[str, Any]:
    """Check portfolio fitness, returning dict with fits_portfolio + warnings."""
    try:
        result = _fitness_checker.check_trade_fitness(
            portfolio_state,
            {
                'underlying': ticker,
                'delta': -0.30 * 100,  # conservative estimate
                'margin_required': trade_margin,
                'var_impact': 0.30 * spot * 0.02,
            },
            risk_limits,
        )
        return result.to_dict()
    except Exception as e:
        logger.warning(f"Fitness check failed: {e}")
        return {
            'fits_portfolio': True,
            'fitness_warnings': [f'Fitness check unavailable: {e}'],
        }
