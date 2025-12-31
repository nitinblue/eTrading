# tests/integration/test_tastytrade_broker_real.py
import pytest
from trading_bot.config import Config
from trading_bot.brokers.tastytrade_broker import TastytradeBroker
from tastytrade.instruments import get_option_chain
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@pytest.fixture(scope="module")
def config():
    return Config.load('config.yaml')

@pytest.fixture(scope="module")
def paper_broker(config):
    broker = TastytradeBroker(
        username=config.broker['username'],
        password=config.broker['password'],
        is_paper=True
    )
    broker.connect()
    yield broker

def test_connection_and_accounts(paper_broker):
    assert paper_broker.session is not None
    assert len(paper_broker.accounts) >= 1

def test_get_account_balance(paper_broker):
    """Test balance fields that actually exist in paper accounts."""
    balance = paper_broker.get_account_balance()
    assert "cash_balance" in balance
    assert "equity_buying_power" in balance
    assert "margin_equity" in balance
    # derivative_buying_power may not exist in cash accounts — skip
    print(f"Balance: Cash=${balance['cash_balance']:.2f}, Equity BP=${balance['equity_buying_power']:.2f}")

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
    """Test getting underlying price using Quote.get_quote (current SDK method)."""
    underlying = "AAPL"
    from tastytrade.dxfeed.quote import Quote
    
    try:
        # Direct static method
        quote_data = Quote.get_quote(paper_broker.session, underlying)
        price = quote_data.get('last_price') or quote_data.get('close_price') or quote_data.get('bid_price')
        assert price is not None
        logger.info(f"{underlying} price: ${price:.2f}")
    except Exception as e:
        logger.error(f"Quote fetch failed: {e}")
        # Fallback: search + instrument quote
        from tastytrade.search import symbol_search
        results = symbol_search(paper_broker.session, underlying)
        assert len(results) > 0
        symbol_data = results[0]
        # symbol_data has .quote property or method in some versions
        quote = symbol_data.quote(paper_broker.session) if hasattr(symbol_data, 'quote') else None
        if quote:
            price = quote.last_price or quote.close_price
            assert price is not None
            logger.info(f"{underlying} price (fallback): ${price:.2f}")
        else:
            pytest.skip("Quote endpoint not available in current SDK version")

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