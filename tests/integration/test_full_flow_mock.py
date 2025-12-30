# tests/integration/test_full_flow_mock.py
from trading_bot.trade_execution import TradeExecutor
from trading_bot.strategy import ShortPutStrategy
# from trading_bot.broker import PriceEffect
# Import everything needed from broker.py

def test_full_entry_and_execution_flow(mock_broker, mock_market_data):
    executor = TradeExecutor(mock_broker)

    config = {
        'min_iv': 25,
        'max_delta': 0.30,
        'dry_run': False  # Test real mock execution
    }
    strategy = ShortPutStrategy(mock_market_data, executor, config)

    data = {
        'symbol': '.NVDA260207P00800000',
        'iv': 38,
        'delta': -0.14,
        'quantity': 3,
        'limit_price': 15.50
    }

    response = strategy.execute_entry(data, account_id="mock_account_456")

    assert response["status"] == "mock_success"
    assert len(mock_broker.order_history.get("mock_account_456", [])) == 1

    positions = mock_broker.get_positions("mock_account_456")
    assert any(p['symbol'] == data['symbol'] for p in positions)