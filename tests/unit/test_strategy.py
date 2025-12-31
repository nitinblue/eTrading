# tests/unit/test_strategy.py
import pytest
from trading_bot.strategy import ShortPutStrategy
from trading_bot.brokers import NeutralOrder, OrderAction, PriceEffect
from unittest.mock import MagicMock

@pytest.fixture
def mock_executor():
    return MagicMock()

def test_evaluate_entry_met(mock_market_data, mock_executor):
    config = {'min_iv': 30, 'max_delta': 0.3}
    strategy = ShortPutStrategy(mock_market_data, mock_executor, config)
    data = {'iv': 35, 'delta': -0.25}
    assert strategy.evaluate_entry(data) is True

def test_evaluate_entry_high_iv_rejected(mock_market_data, mock_executor):
    config = {'min_iv': 40, 'max_delta': 0.3}
    strategy = ShortPutStrategy(mock_market_data, mock_executor, config)
    data = {'iv': 35, 'delta': -0.25}
    assert strategy.evaluate_entry(data) is False

def test_generate_order(mock_market_data, mock_executor):
    config = {'dry_run': True}
    strategy = ShortPutStrategy(mock_market_data, mock_executor, config)
    data = {'symbol': 'TEST', 'quantity': 2, 'limit_price': 3.5}
    order = strategy.generate_order(data)
    assert isinstance(order, NeutralOrder)
    assert order.legs[0].quantity == 2
    assert order.price_effect == PriceEffect.CREDIT
    assert order.limit_price == 3.5

def test_execute_entry_success(mock_market_data, mock_executor):
    config = {'min_iv': 30, 'max_delta': 0.3}
    strategy = ShortPutStrategy(mock_market_data, mock_executor, config)
    data = {'iv': 35, 'delta': -0.25, 'symbol': 'TEST'}
    mock_executor.execute.return_value = {"status": "success"}
    result = strategy.execute_entry(data)
    assert result["status"] == "success"

def test_execute_entry_no_met(mock_market_data, mock_executor):
    config = {'min_iv': 40, 'max_delta': 0.3}
    strategy = ShortPutStrategy(mock_market_data, mock_executor, config)
    data = {'iv': 35, 'delta': -0.25}
    result = strategy.execute_entry(data)
    assert result["status"] == "entry_not_met"

# Edge case: Invalid data
def test_evaluate_entry_invalid_data(mock_market_data, mock_executor):
    config = {'min_iv': 30, 'max_delta': 0.3}
    strategy = ShortPutStrategy(mock_market_data, mock_executor, config)
    data = {'iv': 'invalid', 'delta': -0.25}
    with pytest.raises(KeyError or TypeError):
        strategy.evaluate_entry(data)

# Add for evaluate_exit, etc.