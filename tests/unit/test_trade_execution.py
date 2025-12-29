# tests/unit/test_trade_execution.py
from trading_bot.broker import NeutralOrder, OrderLeg, OrderAction, PriceEffect

def test_trade_executor_dry_run(mock_broker, trade_executor):
    order = NeutralOrder(
        legs=[OrderLeg(symbol=".AAPL260131P00195000", quantity=5, action=OrderAction.SELL_TO_OPEN)],
        price_effect=PriceEffect.CREDIT,
        limit_price=4.20,
        dry_run=True
    )
    response = trade_executor.execute("ShortPut", order, account_id="test_acc_123")
    assert response["status"] == "mock_dry_run_success"