"""
CLI: Run Screener against a watchlist.

Usage:
    python -m trading_cotrader.cli.run_screener --screener vix --watchlist "My Watchlist"
    python -m trading_cotrader.cli.run_screener --screener vix --symbols SPY,QQQ,IWM --no-broker
    python -m trading_cotrader.cli.run_screener --screener leaps --symbols AAPL,MSFT --no-broker
    python -m trading_cotrader.cli.run_screener --screener all --watchlist "My Watchlist"
    python -m trading_cotrader.cli.run_screener --screener vix --symbols SPY --macro-outlook uncertain --expected-vol extreme
"""

import argparse
import sys
from decimal import Decimal

from trading_cotrader.core.database.session import session_scope


def main():
    parser = argparse.ArgumentParser(
        description="Run a screener and generate trade recommendations"
    )
    parser.add_argument(
        '--screener', required=True,
        choices=['vix', 'iv_rank', 'leaps', 'all'],
        help='Screener to run (or "all" to run all screeners)'
    )
    parser.add_argument(
        '--watchlist', default=None,
        help='Watchlist name to screen against'
    )
    parser.add_argument(
        '--symbols', default=None,
        help='Comma-separated symbols to screen (alternative to --watchlist)'
    )
    parser.add_argument(
        '--no-broker', action='store_true',
        help='Run without broker connection (uses mock data)'
    )
    parser.add_argument(
        '--mock-vix', type=float, default=None,
        help='Override VIX value for testing'
    )

    # Macro override args
    parser.add_argument(
        '--macro-outlook', default=None,
        choices=['bullish', 'neutral', 'bearish', 'uncertain'],
        help='Market outlook override (short-circuits screening if uncertain)'
    )
    parser.add_argument(
        '--expected-vol', default=None,
        choices=['low', 'normal', 'high', 'extreme'],
        help='Expected volatility override'
    )
    parser.add_argument(
        '--macro-notes', default='',
        help='Free-text notes for macro context'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("  SCREENER CLI")
    print("=" * 70)
    print()

    broker = None
    if not args.no_broker:
        try:
            from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter
            broker = TastytradeAdapter(is_paper=True)
            if not broker.authenticate():
                print("WARNING: Broker auth failed, running in mock mode")
                broker = None
            else:
                print("Broker connected")
        except Exception as e:
            print(f"WARNING: Could not connect to broker: {e}")

    # Build macro override if provided
    macro_override = None
    if args.macro_outlook or args.expected_vol:
        from trading_cotrader.services.macro_context_service import MacroOverride
        macro_override = MacroOverride(
            market_probability=args.macro_outlook,
            expected_volatility=args.expected_vol,
            notes=args.macro_notes,
        )
        print(f"Macro override: outlook={args.macro_outlook}, vol={args.expected_vol}")
        if args.macro_notes:
            print(f"  Notes: {args.macro_notes}")

    # Initialize TechnicalAnalysisService
    technical_service = None
    try:
        from trading_cotrader.services.technical_analysis_service import TechnicalAnalysisService
        use_mock = args.no_broker
        technical_service = TechnicalAnalysisService(use_mock=use_mock)
        print(f"Technical analysis: {'mock' if use_mock else 'live (yfinance)'}")
    except Exception as e:
        print(f"WARNING: TechnicalAnalysisService unavailable: {e}")

    print()

    with session_scope() as session:
        from trading_cotrader.services.recommendation_service import RecommendationService
        from trading_cotrader.services.watchlist_service import WatchlistService

        svc = RecommendationService(
            session, broker=broker,
            technical_service=technical_service,
        )

        # Handle --symbols by creating a temporary watchlist
        if args.symbols and not args.watchlist:
            symbols = [s.strip() for s in args.symbols.split(',')]
            wl_svc = WatchlistService(session)
            wl_svc.create_custom(
                name="CLI Symbols",
                symbols=symbols,
                description="Created from --symbols CLI argument",
            )
            watchlist_name = "CLI Symbols"
        elif args.watchlist:
            watchlist_name = args.watchlist
        else:
            # Default mock watchlist
            wl_svc = WatchlistService(session)
            wl_svc.create_custom(
                name="Default Screener",
                symbols=['SPY', 'QQQ', 'IWM', 'AAPL', 'MSFT'],
                description="Default screener watchlist",
            )
            watchlist_name = "Default Screener"

        # Extra kwargs for screener
        screener_kwargs = {}
        if args.mock_vix is not None:
            screener_kwargs['mock_vix'] = Decimal(str(args.mock_vix))

        print(f"Running: {args.screener} screener")
        print(f"Watchlist: {watchlist_name}")
        print()

        recs = svc.run_screener(
            screener_name=args.screener,
            watchlist_name=watchlist_name,
            macro_override=macro_override,
            **screener_kwargs,
        )

        if not recs:
            print("No recommendations generated.")
            if macro_override and args.macro_outlook == 'uncertain':
                print("  (Macro short-circuit may have prevented screening)")
            return 0

        # Display recommendations
        try:
            from tabulate import tabulate
        except ImportError:
            tabulate = None

        print(f"\n{len(recs)} Recommendation(s) Generated:")
        print("-" * 70)

        rows = []
        for rec in recs:
            rows.append([
                rec.id[:8] + "...",
                rec.underlying,
                rec.strategy_type,
                rec.confidence,
                rec.suggested_portfolio or "—",
                rec.rationale[:50] + "..." if len(rec.rationale) > 50 else rec.rationale,
            ])

        if tabulate:
            print(tabulate(
                rows,
                headers=["ID", "Symbol", "Strategy", "Conf", "Portfolio", "Rationale"],
                tablefmt="rounded_grid",
            ))
        else:
            for row in rows:
                print(f"  {row[0]}  {row[1]:6s}  {row[2]:20s}  conf={row[3]}  {row[5]}")

        print()
        print(f"Use 'python -m trading_cotrader.cli.accept_recommendation --list' to review")
        print(f"Use 'python -m trading_cotrader.cli.accept_recommendation --accept <ID>' to accept")

    return 0


if __name__ == '__main__':
    sys.exit(main())
