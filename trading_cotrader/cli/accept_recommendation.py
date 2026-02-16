"""
CLI: Review and accept/reject recommendations.

Usage:
    python -m trading_cotrader.cli.accept_recommendation --list
    python -m trading_cotrader.cli.accept_recommendation --accept <ID> --notes "reason"
    python -m trading_cotrader.cli.accept_recommendation --reject <ID> --reason "too risky"
    python -m trading_cotrader.cli.accept_recommendation --accept <ID> --portfolio high_risk
"""

import argparse
import sys

from trading_cotrader.core.database.session import session_scope


def main():
    parser = argparse.ArgumentParser(
        description="Review and accept/reject trade recommendations"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--list', action='store_true', help='List pending recommendations')
    group.add_argument('--accept', metavar='ID', help='Accept a recommendation by ID')
    group.add_argument('--reject', metavar='ID', help='Reject a recommendation by ID')
    group.add_argument('--expire', action='store_true', help='Expire old recommendations')

    parser.add_argument('--notes', default='', help='Notes for acceptance')
    parser.add_argument('--reason', default='', help='Reason for rejection')
    parser.add_argument('--portfolio', default=None, help='Override portfolio name')
    parser.add_argument('--no-broker', action='store_true', help='Skip broker connection')
    parser.add_argument('--all', action='store_true', help='Show all statuses, not just pending')

    args = parser.parse_args()

    with session_scope() as session:
        from trading_cotrader.services.recommendation_service import RecommendationService

        broker = None
        if not args.no_broker and (args.accept):
            try:
                from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter
                broker = TastytradeAdapter(is_paper=True)
                if not broker.authenticate():
                    print("WARNING: Broker auth failed — trade will have mock Greeks")
                    broker = None
            except Exception:
                pass

        svc = RecommendationService(session, broker=broker)

        if args.list:
            _list_recommendations(svc, show_all=args.all)
        elif args.accept:
            _accept_recommendation(svc, args.accept, args.notes, args.portfolio)
        elif args.reject:
            _reject_recommendation(svc, args.reject, args.reason)
        elif args.expire:
            count = svc.expire_old_recommendations()
            print(f"Expired {count} old recommendations")

    return 0


def _list_recommendations(svc, show_all: bool = False):
    """List recommendations."""
    if show_all:
        from trading_cotrader.repositories.recommendation import RecommendationRepository
        recs = RecommendationRepository(svc.session).get_all()
        recs = [RecommendationRepository(svc.session).to_domain(r) for r in recs]
    else:
        recs = svc.get_pending()

    if not recs:
        print("No pending recommendations.")
        return

    try:
        from tabulate import tabulate
    except ImportError:
        tabulate = None

    print(f"\n{'All' if show_all else 'Pending'} Recommendations ({len(recs)}):")
    print("=" * 80)

    rows = []
    for rec in recs:
        vix_str = f"{float(rec.market_context.vix):.1f}" if rec.market_context.vix else "—"
        rows.append([
            rec.id[:12],
            rec.status.value,
            rec.underlying,
            rec.strategy_type,
            rec.source,
            f"VIX={vix_str}",
            rec.confidence,
            rec.suggested_portfolio or "—",
            rec.rationale[:40] + "..." if len(rec.rationale) > 40 else rec.rationale,
        ])

    if tabulate:
        print(tabulate(
            rows,
            headers=["ID", "Status", "Symbol", "Strategy", "Source", "Context", "Conf", "Portfolio", "Rationale"],
            tablefmt="rounded_grid",
        ))
    else:
        for row in rows:
            print(f"  {row[0]}  [{row[1]:8s}]  {row[2]:6s}  {row[3]:20s}  {row[8]}")

    print()
    print("Commands:")
    print(f"  --accept <ID> --notes 'reason'    Accept and book as WhatIf trade")
    print(f"  --reject <ID> --reason 'reason'   Reject recommendation")


def _accept_recommendation(svc, rec_id: str, notes: str, portfolio: str):
    """Accept a recommendation."""
    # Try to match partial ID
    full_id = _resolve_id(svc, rec_id)
    if not full_id:
        print(f"Recommendation '{rec_id}' not found")
        return

    print(f"Accepting recommendation {full_id[:12]}...")
    result = svc.accept_recommendation(
        rec_id=full_id,
        notes=notes,
        portfolio_name=portfolio,
    )

    if result['success']:
        print(f"  Trade booked: {result['trade_id'][:12]}...")
        if result.get('portfolio'):
            print(f"  Portfolio: {result['portfolio']}")
        print(f"  Notes: {notes}" if notes else "")
    else:
        print(f"  FAILED: {result['error']}")


def _reject_recommendation(svc, rec_id: str, reason: str):
    """Reject a recommendation."""
    full_id = _resolve_id(svc, rec_id)
    if not full_id:
        print(f"Recommendation '{rec_id}' not found")
        return

    if svc.reject_recommendation(full_id, reason=reason):
        print(f"Rejected recommendation {full_id[:12]}...")
        if reason:
            print(f"  Reason: {reason}")
    else:
        print(f"Failed to reject recommendation '{rec_id}'")


def _resolve_id(svc, partial_id: str) -> str:
    """Resolve a partial ID to full UUID."""
    # First try exact match
    rec = svc.get_by_id(partial_id)
    if rec:
        return partial_id

    # Try prefix match against pending
    pending = svc.get_pending()
    matches = [r for r in pending if r.id.startswith(partial_id)]
    if len(matches) == 1:
        return matches[0].id

    if len(matches) > 1:
        print(f"Ambiguous ID '{partial_id}' — matches {len(matches)} recommendations")
    return ""


if __name__ == '__main__':
    sys.exit(main())
