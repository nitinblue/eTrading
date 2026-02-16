"""
CLI: Evaluate portfolio and generate exit/roll/adjust recommendations.

Usage:
    python -m trading_cotrader.cli.evaluate_portfolio --portfolio high_risk --no-broker --dry-run
    python -m trading_cotrader.cli.evaluate_portfolio --all --no-broker
"""

import argparse
import sys
from pathlib import Path

# Ensure project root on path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate portfolio and generate exit/roll/adjust recommendations"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--portfolio', type=str,
        help='Portfolio config name (e.g. high_risk, medium_risk, core_holdings)',
    )
    group.add_argument(
        '--all', action='store_true',
        help='Evaluate all managed portfolios',
    )
    parser.add_argument(
        '--no-broker', action='store_true',
        help='Run without broker connection (mock mode)',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Preview recommendations without saving to DB',
    )
    args = parser.parse_args()

    # Setup
    broker = None
    if not args.no_broker:
        try:
            from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter
            broker = TastytradeAdapter(is_paper=True)
            if not broker.authenticate():
                print("ERROR: Could not authenticate with broker")
                return 1
        except Exception as e:
            print(f"ERROR: Broker connection failed: {e}")
            return 1

    from trading_cotrader.core.database.session import session_scope
    from trading_cotrader.services.portfolio_evaluation_service import PortfolioEvaluationService

    with session_scope() as session:
        svc = PortfolioEvaluationService(session, broker=broker)

        if args.all:
            results = svc.evaluate_all_portfolios(dry_run=args.dry_run)
            if not results:
                print("\nNo exit/roll/adjust recommendations generated for any portfolio.")
                return 0

            for portfolio_name, recs in results.items():
                _print_recommendations(portfolio_name, recs, args.dry_run)
        else:
            recs = svc.evaluate_portfolio(args.portfolio, dry_run=args.dry_run)
            if not recs:
                print(f"\nNo exit/roll/adjust recommendations for '{args.portfolio}'.")
                print("  (Either no open trades, or no rules triggered.)")
                return 0

            _print_recommendations(args.portfolio, recs, args.dry_run)

    return 0


def _print_recommendations(portfolio_name: str, recs, dry_run: bool):
    """Print recommendations in a readable format."""
    mode = "[DRY RUN] " if dry_run else ""
    print(f"\n{'=' * 70}")
    print(f"  {mode}Portfolio: {portfolio_name} — {len(recs)} recommendation(s)")
    print(f"{'=' * 70}")

    for i, rec in enumerate(recs, 1):
        rec_type = rec.recommendation_type.value.upper()
        urgency = rec.exit_urgency or "normal"
        rules = ", ".join(rec.triggered_rules) if rec.triggered_rules else "—"

        print(f"\n  [{i}] {rec_type}: {rec.underlying} ({rec.strategy_type})")
        print(f"      Action:    {rec.exit_action or '—'}")
        print(f"      Urgency:   {urgency}")
        print(f"      Rules:     {rules}")
        print(f"      Conf:      {rec.confidence}/10")
        print(f"      Rationale: {rec.rationale}")
        if rec.trade_id_to_close:
            print(f"      Trade ID:  {rec.trade_id_to_close[:12]}...")
        if rec.legs:
            print(f"      Legs:      {len(rec.legs)}")
            for leg in rec.legs:
                print(f"        {leg.streamer_symbol}  qty={leg.quantity}")

    print()
    if not dry_run:
        print("  Recommendations saved to DB. Use `accept_recommendation` CLI to act.")
    else:
        print("  [DRY RUN] Not saved. Remove --dry-run to persist.")


if __name__ == "__main__":
    sys.exit(main())
