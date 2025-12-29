# tests/conftest.py
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import MagicMock

from trading_bot.broker import Broker, NeutralOrder, OrderLeg, OrderAction, PriceEffect, OrderType
from trading_bot.broker_mock import MockBroker
from trading_bot.trade_execution import TradeExecutor
from trading_bot.market_data import MarketDataProvider
from trading_bot.strategy import ShortPutStrategy

@pytest.fixture
def mock_market_data():
    md = MagicMock(spec=MarketDataProvider)
    md.get_option_greeks.return_value = {
        'delta': -0.16,
        'gamma': 0.05,
        'theta': 0.90,
        'vega': 12.5,
        'rho': 0.07
    }
    return md

@pytest.fixture
def mock_broker():
    broker = MockBroker()
    broker.connect()  # Connect to avoid RuntimeError
    return broker

@pytest.fixture
def trade_executor(mock_broker):
    return TradeExecutor(mock_broker)

@pytest.fixture
def short_put_strategy(mock_market_data, trade_executor):
    config = {
        'min_iv': 30,
        'max_delta': 0.25,
        'target_profit': 50,
        'max_loss': 100,
        'dry_run': True
    }
    return ShortPutStrategy(mock_market_data, trade_executor, config)

@pytest.fixture
def sample_entry_data():
    return {
        'symbol': '.AAPL260131P00195000',
        'iv': 42,
        'delta': -0.18,
        'quantity': 5,
        'limit_price': 4.20
    }

@pytest.fixture
def risk_config():
    return {
        'max_risk_per_trade': 0.01,
        'max_portfolio_risk': 0.05
    }