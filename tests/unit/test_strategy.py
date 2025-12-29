# tests/unit/test_strategy.py
from trading_bot.broker import NeutralOrder, OrderAction, PriceEffect

def test_short_put_entry_met(short_put_strategy, sample_entry_data):
    assert short_put_strategy.evaluate_entry(sample_entry_data) is True

def test_short_put_generate_order(short_put_strategy, sample_entry_data):
    order = short_put_strategy.generate_order(sample_entry_data)
    assert isinstance(order, NeutralOrder)
    assert len(order.legs) == 1
    assert order.legs[0].action == OrderAction.SELL_TO_OPEN
    assert order.price_effect == PriceEffect.CREDIT
    assert order.limit_price == 4.20
    assert order.dry_run is True

def test_short_put_execute_entry(short_put_strategy, sample_entry_data):
    response = short_put_strategy.execute_entry(sample_entry_data, account_id="test_acc_123")
    assert 'status' in response