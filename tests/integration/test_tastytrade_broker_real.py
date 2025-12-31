# tests/integration/test_tastytrade_broker_real.py
import pytest
from trading_bot.config import Config
from trading_bot.brokers.tastytrade_broker import TastytradeBroker

@pytest.fixture(scope="module")
def config():
    return Config.load('config.yaml')  # Loads your real config

@pytest.fixture(scope="module")
def paper_broker(config):
    """Use real paper credentials from config.yaml."""
    broker = TastytradeBroker(
        username=config.broker['username'],
        password=config.broker['password'],
        is_paper=True  # Force paper mode for safety
    )
    broker.connect()  # Raises if auth fails
    yield broker

def test_connection_and_accounts(paper_broker):
    """Test successful connection and account loading."""
    assert paper_broker.session is not None
    assert len(paper_broker.accounts) >= 1
    account_numbers = list(paper_broker.accounts.keys())
    print(f"Connected accounts: {account_numbers}")

def test_get_account_balance(paper_broker):
    """Test fetching account balances."""
    balance = paper_broker.get_account_balance()
    assert "cash_balance" in balance
    assert "buying_power" in balance
    assert "equity" in balance
    assert isinstance(balance["cash_balance"], float)
    print(f"Balance: Cash=${balance['cash_balance']:.2f}, BP=${balance['buying_power']:.2f}")

def test_get_positions(paper_broker):
    """Test fetching current positions."""
    positions = paper_broker.get_positions()
    assert isinstance(positions, list)
    if positions:
        pos = positions[0]
        assert "symbol" in pos
        assert "quantity" in pos
        assert "current_price" in pos
        print(f"Sample position: {pos['symbol']} Qty: {pos['quantity']}")
    else:
        print("No open positions (normal for new paper account)")

def test_option_chain_fetch(paper_broker):
    """Test fetching option chain for a popular underlying."""
    underlying = "AAPL"
    chain = get_option_chain(paper_broker.session, underlying)
    assert isinstance(chain, dict)
    assert len(chain) > 0  # Should have expiries
    first_expiry = next(iter(chain))
    assert len(chain[first_expiry]) > 0  # Should have strikes
    sample_opt = chain[first_expiry][0]
    assert hasattr(sample_opt, 'symbol')
    assert hasattr(sample_opt, 'strike_price')
    print(f"Option chain loaded: {len(chain)} expiries for {underlying}")

def test_underlying_quote(paper_broker):
    """Test getting underlying price via quote."""
    underlying = "AAPL"
    equities = Equity.get_equities(paper_broker.session, [underlying])
    assert len(equities) == 1
    equity = equities[0]
    quote = equity.get_quote(paper_broker.session)
    assert quote.last_price is not None or quote.close_price is not None
    price = quote.last_price or quote.close_price
    print(f"{underlying} price: ${price:.2f}")

def test_dry_run_order_execution(paper_broker):
    """Test dry-run order execution (no real trade)."""
    from trading_bot.order_model import UniversalOrder, OrderLeg, OrderAction, PriceEffect, OrderType

    order = UniversalOrder(
        legs=[OrderLeg(symbol=".AAPL260116C00200000", quantity=1, action=OrderAction.BUY_TO_OPEN)],
        price_effect=PriceEffect.DEBIT,
        order_type=OrderType.LIMIT,
        limit_price=10.0,
        dry_run=True  # Safety
    )

    result = paper_broker.execute_order(order)
    assert result["status"] == "dry_run_success"
    print("Dry-run order succeeded (as expected)")