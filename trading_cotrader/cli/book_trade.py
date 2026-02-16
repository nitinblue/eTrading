"""
CLI: Book a WhatIf trade from a JSON (or YAML) file
=====================================================

Usage:
    python -m trading_cotrader.cli.book_trade --file trade.json
    python -m trading_cotrader.cli.book_trade --file trade.json --dry-run
    python -m trading_cotrader.cli.book_trade --file trade.json --no-broker

Multi-strategy file (strategies array):
    python -m trading_cotrader.cli.book_trade --file strategy_trade_templates.json --index 2 --no-broker
    python -m trading_cotrader.cli.book_trade --file strategy_trade_templates.json --all --no-broker
    python -m trading_cotrader.cli.book_trade --file strategy_trade_templates.json --list

Template:
    See trading_cotrader/config/trade_template.json
    See trading_cotrader/config/strategy_trade_templates.json (all 18 strategies)

Supports:
    - Past-dated trades via trade_date field
    - Manual Greeks override (no broker needed)
    - Portfolio routing with strategy validation
    - Multi-strategy files with --index or --all
"""

import argparse
import json
import sys
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any, Optional

from trading_cotrader.services.trade_booking_service import (
    TradeBookingService, LegInput, TradeBookingResult
)
from trading_cotrader.harness.base import rich_table, format_currency, format_greek


def load_raw_file(filepath: str) -> Dict[str, Any]:
    """Load a JSON or YAML file (auto-detects by extension). Returns raw dict."""
    path = Path(filepath)
    if not path.exists():
        print(f"ERROR: File not found: {filepath}")
        sys.exit(1)

    ext = path.suffix.lower()
    if ext in ('.yaml', '.yml'):
        import yaml
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    else:
        with open(path, 'r') as f:
            return json.load(f)


def validate_trade_data(data: Dict[str, Any]) -> None:
    """Validate a single trade dict has required fields."""
    required = ['underlying', 'strategy_type', 'legs']
    for field in required:
        if field not in data:
            print(f"ERROR: Missing required field: {field}")
            sys.exit(1)

    if not data['legs'] or len(data['legs']) == 0:
        print("ERROR: At least one leg is required")
        sys.exit(1)

    for i, leg in enumerate(data['legs']):
        if 'streamer_symbol' not in leg:
            print(f"ERROR: Leg {i} missing streamer_symbol")
            sys.exit(1)
        if 'quantity' not in leg:
            print(f"ERROR: Leg {i} missing quantity")
            sys.exit(1)


def load_trade_file(filepath: str, index: int = None) -> Dict[str, Any]:
    """Load and validate a trade JSON or YAML file.

    If the file has a 'strategies' array:
      - index=N returns the Nth strategy
      - index=None returns the first strategy (for backward compat)
    Otherwise returns the file as a single trade dict.
    """
    data = load_raw_file(filepath)

    # Multi-strategy file
    if 'strategies' in data:
        strategies = data['strategies']
        if index is not None:
            if index < 0 or index >= len(strategies):
                print(f"ERROR: Index {index} out of range (0-{len(strategies)-1})")
                sys.exit(1)
            trade = strategies[index]
        else:
            trade = strategies[0]
        validate_trade_data(trade)
        return trade

    # Single trade file
    validate_trade_data(data)
    return data


def list_strategies(filepath: str) -> None:
    """List all strategies in a multi-strategy file."""
    data = load_raw_file(filepath)
    if 'strategies' not in data:
        print("Not a multi-strategy file (no 'strategies' array).")
        return

    strategies = data['strategies']
    print(f"\n{'='*70}")
    print(f"  {len(strategies)} strategies in {filepath}")
    print(f"{'='*70}\n")

    rows = []
    for s in strategies:
        idx = s.get('_index', '?')
        name = s.get('_name', s.get('strategy_type', '?'))
        underlying = s.get('underlying', '?')
        portfolio = s.get('portfolio_name', '—')
        legs = len(s.get('legs', []))
        rows.append([str(idx), name, underlying, portfolio, str(legs)])

    print(rich_table(rows, headers=["#", "Strategy", "Underlying", "Portfolio", "Legs"],
                     title="Available Strategy Templates"))
    print(f"\nBook one:  python -m trading_cotrader.cli.book_trade --file {filepath} --index 2 --no-broker")
    print(f"Book all:  python -m trading_cotrader.cli.book_trade --file {filepath} --all --no-broker")


def book_with_manual_greeks(
    trade_data: Dict[str, Any],
    trade_date: Optional[date] = None,
) -> TradeBookingResult:
    """Book a trade using manual Greeks (no broker connection needed)."""
    import uuid
    import trading_cotrader.core.models.domain as dm
    import trading_cotrader.core.models.events as ev
    from trading_cotrader.core.database.session import session_scope
    from trading_cotrader.repositories.trade import TradeRepository
    from trading_cotrader.repositories.event import EventRepository
    from trading_cotrader.repositories.portfolio import PortfolioRepository
    from trading_cotrader.core.models.strategy_templates import get_strategy_type_from_string
    from trading_cotrader.services.trade_booking_service import LegResult
    import re

    underlying = trade_data['underlying']
    strategy_type = trade_data['strategy_type']
    legs_input = trade_data['legs']
    manual = trade_data.get('manual_greeks', {})
    manual_legs = manual.get('legs', [])
    notes = trade_data.get('notes', '')
    rationale = trade_data.get('rationale', '')
    confidence = trade_data.get('confidence', 5)
    portfolio_name = trade_data.get('portfolio_name')

    # Validate portfolio permissions
    if portfolio_name:
        from trading_cotrader.services.portfolio_manager import PortfolioManager
        with session_scope() as session:
            pm = PortfolioManager(session)
            check = pm.validate_trade_for_portfolio(portfolio_name, strategy_type)
            if not check['allowed']:
                return TradeBookingResult(success=False, error=check['reason'])

    trade_id = str(uuid.uuid4())
    domain_legs = []
    leg_results = []
    total_delta = Decimal('0')
    total_gamma = Decimal('0')
    total_theta = Decimal('0')
    total_vega = Decimal('0')
    net_entry_price = Decimal('0')

    # Option symbol regex
    option_re = re.compile(r'^\.([A-Z]+)(\d{6})([PC])(\d+)$')

    created_at = datetime.utcnow()
    if trade_date:
        created_at = datetime.combine(trade_date, datetime.min.time().replace(hour=12))

    for i, leg_input in enumerate(legs_input):
        symbol_str = leg_input['streamer_symbol']
        qty = int(leg_input['quantity'])
        is_short = qty < 0

        # Parse symbol
        if symbol_str.startswith('.'):
            match = option_re.match(symbol_str)
            if not match:
                return TradeBookingResult(
                    success=False, error=f"Invalid option symbol: {symbol_str}"
                )
            ticker, exp_str, opt_type_char, strike_str = match.groups()
            exp_date = datetime.strptime(exp_str, '%y%m%d').date()
            option_type = dm.OptionType.CALL if opt_type_char == 'C' else dm.OptionType.PUT
            strike = Decimal(strike_str)
            symbol = dm.Symbol(
                ticker=ticker, asset_type=dm.AssetType.OPTION,
                option_type=option_type, strike=strike,
                expiration=exp_date, multiplier=100,
            )
        else:
            symbol = dm.Symbol(
                ticker=symbol_str, asset_type=dm.AssetType.EQUITY, multiplier=1,
            )

        multiplier = symbol.multiplier

        # Get Greeks from manual override or default to zeros
        if i < len(manual_legs):
            mg = manual_legs[i]
            leg_delta = Decimal(str(mg.get('delta', 0)))
            leg_gamma = Decimal(str(mg.get('gamma', 0)))
            leg_theta = Decimal(str(mg.get('theta', 0)))
            leg_vega = Decimal(str(mg.get('vega', 0)))
            mid_price = Decimal(str(mg.get('mid_price', 0)))
            bid = Decimal(str(mg.get('bid', 0)))
            ask = Decimal(str(mg.get('ask', 0)))
        else:
            leg_delta = Decimal('1') if not symbol.is_option else Decimal('0')
            leg_gamma = leg_theta = leg_vega = Decimal('0')
            mid_price = bid = ask = Decimal('0')

        # Position Greeks
        pos_delta = leg_delta * qty * multiplier
        pos_gamma = leg_gamma * abs(qty) * multiplier
        pos_theta = leg_theta * qty * multiplier
        pos_vega = leg_vega * qty * multiplier

        total_delta += pos_delta
        total_gamma += pos_gamma
        total_theta += pos_theta
        total_vega += pos_vega

        leg_cost = mid_price * abs(qty) * multiplier
        net_entry_price += leg_cost if is_short else -leg_cost

        per_contract_greeks = dm.Greeks(
            delta=leg_delta, gamma=leg_gamma,
            theta=leg_theta, vega=leg_vega,
        )
        domain_leg = dm.Leg(
            id=f"{trade_id}_leg_{i}",
            symbol=symbol,
            quantity=qty,
            side=dm.OrderSide.SELL_TO_OPEN if is_short else dm.OrderSide.BUY_TO_OPEN,
            entry_price=mid_price,
            current_price=mid_price,
            entry_greeks=per_contract_greeks,
            current_greeks=per_contract_greeks,
        )
        domain_legs.append(domain_leg)

        leg_results.append(LegResult(
            streamer_symbol=symbol_str,
            underlying=symbol.ticker,
            asset_type=symbol.asset_type.value,
            option_type=symbol.option_type.value if symbol.option_type else None,
            strike=symbol.strike,
            expiration=symbol.expiration,
            quantity=qty,
            side='sell' if is_short else 'buy',
            mid_price=mid_price,
            bid=bid,
            ask=ask,
            per_contract_greeks={
                'delta': float(leg_delta), 'gamma': float(leg_gamma),
                'theta': float(leg_theta), 'vega': float(leg_vega),
            },
            position_greeks={
                'delta': float(pos_delta), 'gamma': float(pos_gamma),
                'theta': float(pos_theta), 'vega': float(pos_vega),
            },
        ))

    trade_greeks = dm.Greeks(
        delta=total_delta, gamma=total_gamma,
        theta=total_theta, vega=total_vega,
    )

    st = get_strategy_type_from_string(strategy_type)

    trade = dm.Trade.create_what_if(
        underlying=underlying,
        strategy_type=st,
        legs=domain_legs,
        entry_price=net_entry_price,
        current_price=net_entry_price,
        entry_greeks=trade_greeks,
        current_greeks=trade_greeks,
        notes=notes,
        created_at=created_at,
    )
    trade.id = trade_id
    trade.intent_at = created_at

    # Create event
    event = ev.TradeEvent(
        event_type=ev.EventType.TRADE_OPENED,
        trade_id=trade.id,
        timestamp=created_at,
        strategy_type=strategy_type,
        underlying_symbol=underlying,
        entry_delta=trade_greeks.delta,
        entry_gamma=trade_greeks.gamma,
        entry_theta=trade_greeks.theta,
        entry_vega=trade_greeks.vega,
        net_credit_debit=net_entry_price,
        decision_context=ev.DecisionContext(
            rationale=rationale or notes,
            confidence_level=confidence,
        ),
        tags=['what_if', strategy_type],
    )

    # Persist
    with session_scope() as session:
        trade_repo = TradeRepository(session)
        event_repo = EventRepository(session)
        portfolio_repo = PortfolioRepository(session)

        target = None
        if portfolio_name:
            from trading_cotrader.services.portfolio_manager import PortfolioManager
            pm = PortfolioManager(session)
            target = pm.get_portfolio_by_name(portfolio_name)

        if not target:
            target = portfolio_repo.get_by_account(broker='whatif', account_id='whatif')
            if not target:
                target = dm.Portfolio(
                    name="What-If Portfolio",
                    broker="whatif",
                    account_id="whatif",
                )
                target = portfolio_repo.create_from_domain(target)

        created = trade_repo.create_from_domain(trade, target.id)
        if not created:
            return TradeBookingResult(success=False, error="Failed to save trade to DB")

        event_repo.create_from_domain(event)

    return TradeBookingResult(
        success=True,
        trade_id=trade.id,
        underlying=underlying,
        strategy_type=strategy_type,
        legs=leg_results,
        total_greeks={
            'delta': float(total_delta), 'gamma': float(total_gamma),
            'theta': float(total_theta), 'vega': float(total_vega),
        },
        entry_price=net_entry_price,
        event_id=event.event_id,
    )


def book_with_broker(trade_data: Dict[str, Any], trade_date: Optional[date] = None) -> TradeBookingResult:
    """Book a trade using live broker connection for Greeks."""
    from trading_cotrader.adapters.tastytrade_adapter import TastytradeAdapter

    print("Connecting to broker...")
    broker = TastytradeAdapter(is_paper=True)
    if not broker.authenticate():
        return TradeBookingResult(success=False, error="Broker authentication failed")
    print("Connected!")

    service = TradeBookingService(broker=broker)

    legs = [LegInput(streamer_symbol=l['streamer_symbol'], quantity=l['quantity'])
            for l in trade_data['legs']]

    result = service.book_whatif_trade(
        underlying=trade_data['underlying'],
        strategy_type=trade_data['strategy_type'],
        legs=legs,
        notes=trade_data.get('notes', ''),
        rationale=trade_data.get('rationale', ''),
        confidence=trade_data.get('confidence', 5),
        portfolio_name=trade_data.get('portfolio_name'),
        trade_date=trade_date,
    )
    return result


def display_result(result: TradeBookingResult) -> None:
    """Display booking result in rich table format."""
    if not result.success:
        print(f"\nFAILED: {result.error}")
        return

    # Trade summary
    trade_data = [
        ["Trade ID", result.trade_id[:12] + "..."],
        ["Strategy", result.strategy_type],
        ["Underlying", result.underlying],
        ["Entry Price", format_currency(result.entry_price)],
        ["Delta", f"{result.total_greeks.get('delta', 0):.4f}"],
        ["Gamma", f"{result.total_greeks.get('gamma', 0):.4f}"],
        ["Theta", f"{result.total_greeks.get('theta', 0):.4f}"],
        ["Vega", f"{result.total_greeks.get('vega', 0):.4f}"],
        ["Event ID", result.event_id[:12] + "..."],
    ]
    print(rich_table(trade_data, headers=["Field", "Value"], title="Trade Booked"))

    # Legs
    if result.legs:
        leg_data = []
        for leg in result.legs:
            leg_data.append([
                leg.streamer_symbol,
                str(leg.quantity),
                f"${leg.mid_price:.2f}",
                f"{leg.per_contract_greeks['delta']:.4f}",
                f"{leg.per_contract_greeks['theta']:.4f}",
                f"{leg.position_greeks['delta']:.2f}",
                f"{leg.position_greeks['theta']:.2f}",
            ])
        print(rich_table(
            leg_data,
            headers=["Symbol", "Qty", "Mid", "d/ct", "th/ct", "Pos d", "Pos th"],
            title="Leg Details"
        ))


def _book_one(trade_data: Dict[str, Any], no_broker: bool, dry_run: bool, label: str = "") -> bool:
    """Book a single trade. Returns True on success."""
    prefix = f"[{label}] " if label else ""

    print(f"  {prefix}Underlying: {trade_data['underlying']}")
    print(f"  {prefix}Strategy: {trade_data['strategy_type']}")
    print(f"  {prefix}Legs: {len(trade_data['legs'])}")
    if trade_data.get('portfolio_name'):
        print(f"  {prefix}Portfolio: {trade_data['portfolio_name']}")
    print()

    trade_date = None
    if trade_data.get('trade_date'):
        trade_date = datetime.strptime(str(trade_data['trade_date']), '%Y-%m-%d').date()

    if dry_run:
        print(f"  {prefix}DRY RUN — validated but not booked")
        for i, leg in enumerate(trade_data['legs']):
            print(f"    Leg {i}: {leg['streamer_symbol']} x {leg['quantity']}")
        print()
        return True

    if no_broker or trade_data.get('manual_greeks'):
        result = book_with_manual_greeks(trade_data, trade_date)
    else:
        result = book_with_broker(trade_data, trade_date)

    display_result(result)
    return result.success


def main():
    parser = argparse.ArgumentParser(
        description="Book a WhatIf trade from JSON (or YAML)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single trade
  python -m trading_cotrader.cli.book_trade --file trade.json --no-broker

  # Multi-strategy file
  python -m trading_cotrader.cli.book_trade --file strategy_trade_templates.json --list
  python -m trading_cotrader.cli.book_trade --file strategy_trade_templates.json --index 2 --no-broker
  python -m trading_cotrader.cli.book_trade --file strategy_trade_templates.json --all --no-broker
        """
    )

    parser.add_argument('--file', '-f', required=True, help='Path to trade JSON file')
    parser.add_argument('--index', '-i', type=int, default=None,
                       help='Strategy index in multi-strategy file (0-based)')
    parser.add_argument('--all', action='store_true',
                       help='Book ALL strategies in a multi-strategy file')
    parser.add_argument('--list', action='store_true',
                       help='List all strategies in a multi-strategy file')
    parser.add_argument('--dry-run', action='store_true', help='Parse and validate only, do not book')
    parser.add_argument('--no-broker', action='store_true',
                       help='Book without broker (uses manual_greeks or zeros)')

    args = parser.parse_args()

    # --list: just show what's available
    if args.list:
        list_strategies(args.file)
        return 0

    # --all: book every strategy in the array
    if args.all:
        raw = load_raw_file(args.file)
        if 'strategies' not in raw:
            print("ERROR: --all requires a file with 'strategies' array")
            return 1

        strategies = raw['strategies']
        print("=" * 60)
        print(f"  BOOKING ALL {len(strategies)} STRATEGIES")
        print("=" * 60)
        print()

        success = 0
        failed = 0
        for s in strategies:
            idx = s.get('_index', '?')
            name = s.get('_name', s.get('strategy_type', '?'))
            print(f"--- [{idx}] {name} ---")
            validate_trade_data(s)
            if _book_one(s, args.no_broker, args.dry_run, label=str(idx)):
                success += 1
            else:
                failed += 1
            print()

        print("=" * 60)
        print(f"  Done: {success} booked, {failed} failed, {len(strategies)} total")
        print("=" * 60)
        return 0 if failed == 0 else 1

    # Single trade (or --index from multi-strategy)
    trade_data = load_trade_file(args.file, index=args.index)

    print("=" * 60)
    print("  TRADE BOOKING")
    print("=" * 60)
    print(f"  File: {args.file}")
    if args.index is not None:
        print(f"  Index: {args.index}")
        name = trade_data.get('_name', '')
        if name:
            print(f"  Name: {name}")

    ok = _book_one(trade_data, args.no_broker, args.dry_run)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
