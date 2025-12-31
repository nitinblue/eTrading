# tests/integration/test_tastytrade_broker_real.py
import pytest
from trading_bot.config import Config
from trading_bot.brokers.tastytrade_broker import TastytradeBroker
from tastytrade.instruments import get_option_chain  # ← Add this import
from tastytrade.instruments import Equity  # ← Add this for underlying quote

@pytest.fixture(scope="module")
def config():
    return Config.load('config.yaml')

@pytest.fixture(scope="module")
def paper_broker(config):
    """Use real paper credentials from config.yaml."""
    broker = TastytradeBroker(
        username=config.broker['username'],
        password=config.broker['password'],
        is_paper=True  # Force paper for safety
    )
    broker.connect()
    yield broker

def test_connection_and_accounts(paper_broker):
    assert paper_broker.session is not None
    assert len(paper_broker.accounts) >= 1

def test_get_account_balance(paper_broker):
    balance = paper_broker.get_account_balance()
    assert "cash_balance" in balance
    assert "buying_power" in balance
    assert "equity" in balance

def test_get_positions(paper_broker):
    positions = paper_broker.get_positions()
    assert isinstance(positions, list)

def test_option_chain_fetch(paper_broker):
    underlying = "AAPL"
    chain = get_option_chain(paper_broker.session, underlying)
    assert isinstance(chain, dict)
    assert len(chain) > 0
    first_expiry = next(iter(chain))
    assert len(chain[first_expiry]) > 0

def test_underlying_quote(paper_broker):
    underlying = "AAPL"
    equities = Equity.get_equities(paper_broker.session, [underlying])
    assert len(equities) == 1
    equity = equities[0]
    quote = equity.get_quote(paper_broker.session)
    price = quote.last_price or quote.close_price or quote.bid or quote.ask
    assert price is not None

def test_dry_run_order_execution(paper_broker):
    from trading_bot.order_model import UniversalOrder, OrderLeg, OrderAction, PriceEffect, OrderType

    order = UniversalOrder(
        legs=[OrderLeg(symbol=".AAPL260116C00200000", quantity=1, action=OrderAction.BUY_TO_OPEN)],
        price_effect=PriceEffect.DEBIT,
        order_type=OrderType.LIMIT,
        limit_price=10.0,
        dry_run=True
    )

    result = paper_broker.execute_order(order)
    assert result["status"] == "dry_run_success"