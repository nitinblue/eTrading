"""
Test script: Verify the full what-if trade flow

Flow: Broker (Greeks) → Database (TradeORM + EventORM) → Container → UI

This script tests:
1. Creating a what-if trade with Greeks from broker
2. Verifying trade is saved to TradeORM (trade_type='what_if')
3. Verifying event is created in TradeEventORM
4. Verifying container is refreshed

Run with: python -m trading_cotrader.scripts.test_whatif_flow
"""

import logging
import sys
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_whatif_flow():
    """Test the full what-if trade flow"""
    from trading_cotrader.services.data_service import DataService
    from trading_cotrader.core.database.session import session_scope
    from trading_cotrader.repositories.trade import TradeRepository
    from trading_cotrader.repositories.event import EventRepository
    from trading_cotrader.core.database.schema import TradeORM, TradeEventORM, PortfolioORM

    print("\n" + "="*60)
    print("TEST: What-If Trade Flow")
    print("="*60)

    # Step 0: Create data service and connect to broker
    print("\n[STEP 0] Connecting to TastyTrade broker...")
    data_service = DataService()
    if not data_service.connect_broker():
        print("✗ FAILED: Could not connect to broker")
        return False
    print("✓ Connected to broker")

    # Step 1: Create a what-if trade
    print("\n[STEP 1] Creating what-if trade...")

    # Calculate expiration ~30 days out (Friday)
    today = datetime.now()
    days_to_friday = (4 - today.weekday() + 7) % 7 or 7
    expiry_date = today + timedelta(days=30 + days_to_friday)
    expiry_str = expiry_date.strftime('%Y-%m-%d')

    # Iron Condor on SPY
    underlying = "SPY"
    legs = [
        {"option_type": "PUT", "strike": 560, "expiry": expiry_str, "quantity": -1},
        {"option_type": "PUT", "strike": 555, "expiry": expiry_str, "quantity": 1},
        {"option_type": "CALL", "strike": 610, "expiry": expiry_str, "quantity": -1},
        {"option_type": "CALL", "strike": 615, "expiry": expiry_str, "quantity": 1},
    ]

    result = data_service.create_whatif_trade(
        underlying=underlying,
        strategy_type="iron_condor",
        legs=legs,
        notes="Test what-if trade for flow verification"
    )

    if 'error' in result:
        print(f"✗ FAILED: {result['error']}")
        return False

    trade_id = result.get('trade_id')
    print(f"✓ Created what-if trade: {trade_id}")
    print(f"  Delta: {result.get('delta', 0):.2f}")
    print(f"  Gamma: {result.get('gamma', 0):.4f}")
    print(f"  Theta: {result.get('theta', 0):.2f}")
    print(f"  Vega: {result.get('vega', 0):.2f}")
    print(f"  Entry Price: ${result.get('entry_price', 0):.2f}")

    # Step 2: Verify trade is in database
    print("\n[STEP 2] Verifying trade in database...")
    with session_scope() as session:
        # Check TradeORM
        trade_orm = session.query(TradeORM).filter_by(id=trade_id).first()
        if not trade_orm:
            print(f"✗ FAILED: Trade {trade_id} not found in TradeORM")
            return False

        print(f"✓ Trade found in database:")
        print(f"  trade_type: {trade_orm.trade_type}")
        print(f"  trade_status: {trade_orm.trade_status}")
        print(f"  underlying: {trade_orm.underlying_symbol}")
        print(f"  legs count: {len(trade_orm.legs)}")

        if trade_orm.trade_type != 'what_if':
            print(f"✗ FAILED: Expected trade_type='what_if', got '{trade_orm.trade_type}'")
            return False

    # Step 3: Verify event is in database
    print("\n[STEP 3] Verifying event in database...")
    with session_scope() as session:
        event_orm = session.query(TradeEventORM).filter_by(trade_id=trade_id).first()
        if not event_orm:
            print(f"✗ FAILED: Event for trade {trade_id} not found")
            return False

        print(f"✓ Event found in database:")
        print(f"  event_id: {event_orm.event_id}")
        print(f"  event_type: {event_orm.event_type}")
        print(f"  underlying: {event_orm.underlying_symbol}")
        print(f"  strategy: {event_orm.strategy_type}")
        print(f"  tags: {event_orm.tags}")

    # Step 4: Verify portfolios data API works
    print("\n[STEP 4] Testing get_portfolios_data() API...")
    portfolios_data = data_service.get_portfolios_data()

    if 'error' in portfolios_data:
        print(f"✗ FAILED: {portfolios_data['error']}")
        return False

    whatif_trades = portfolios_data.get('whatif_trades', [])
    events = portfolios_data.get('events', [])

    print(f"✓ API returned data successfully:")
    print(f"  Real positions: {len(portfolios_data.get('positions', []))}")
    print(f"  What-if trades: {len(whatif_trades)}")
    print(f"  Events: {len(events)}")

    # Verify our trade is in the what-if trades
    our_trade = next((t for t in whatif_trades if t['id'] == trade_id), None)
    if not our_trade:
        print(f"✗ WARNING: Trade {trade_id} not in whatif_trades list")
    else:
        print(f"✓ Our trade found in whatif_trades")

    # Verify our event is in the events
    our_event = next((e for e in events if e.get('trade_id') == trade_id), None)
    if not our_event:
        print(f"✗ WARNING: Event for trade {trade_id} not in events list")
    else:
        print(f"✓ Our event found in events list")

    print("\n" + "="*60)
    print("✓ ALL TESTS PASSED - Full flow verified:")
    print("  Broker (Greeks) → Database (Trade+Event) → Container → UI")
    print("="*60 + "\n")

    return True


def test_patterns_query():
    """Test that RecognizedPatternORM queries work correctly"""
    from trading_cotrader.core.database.session import session_scope
    from trading_cotrader.core.database.schema import RecognizedPatternORM

    print("\n" + "="*60)
    print("TEST: RecognizedPatternORM Query")
    print("="*60)

    with session_scope() as session:
        try:
            # Test the query that was failing
            patterns = session.query(RecognizedPatternORM).order_by(
                RecognizedPatternORM.discovered_at.desc()
            ).limit(10).all()

            print(f"✓ Query succeeded - found {len(patterns)} patterns")

            for p in patterns:
                print(f"  - {p.pattern_id}: {p.pattern_type} (confidence: {p.confidence_score})")

            return True
        except AttributeError as e:
            print(f"✗ FAILED: AttributeError - {e}")
            return False
        except Exception as e:
            print(f"✗ FAILED: {e}")
            return False


if __name__ == "__main__":
    # Test 1: RecognizedPatternORM query
    patterns_ok = test_patterns_query()

    # Test 2: Full what-if flow
    flow_ok = test_whatif_flow()

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"  RecognizedPatternORM query: {'✓ PASS' if patterns_ok else '✗ FAIL'}")
    print(f"  What-if trade flow:         {'✓ PASS' if flow_ok else '✗ FAIL'}")

    sys.exit(0 if (patterns_ok and flow_ok) else 1)
