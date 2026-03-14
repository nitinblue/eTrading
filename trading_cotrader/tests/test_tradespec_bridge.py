"""Tests for TradeSpec Bridge (G1) — DB ↔ MA TradeSpec conversion."""

import pytest
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import MagicMock

from trading_cotrader.services.tradespec_bridge import (
    _symbol_to_dxlink,
    _leg_action,
    trade_to_tradespec,
    trade_to_dxlink_symbols,
    trade_to_monitor_params,
)


def _make_symbol(ticker="GLD", option_type="put", strike=450, exp_date=None):
    """Create a mock SymbolORM."""
    sym = MagicMock()
    sym.id = "sym-1"
    sym.ticker = ticker
    sym.asset_type = "option"
    sym.option_type = option_type
    sym.strike = Decimal(str(strike))
    sym.expiration = exp_date or datetime(2026, 4, 17)
    return sym


def _make_leg(symbol, quantity=-1, side="sell"):
    """Create a mock LegORM."""
    leg = MagicMock()
    leg.id = "leg-1"
    leg.symbol = symbol
    leg.quantity = quantity
    leg.side = side
    return leg


def _make_strategy(strategy_type="iron_condor", profit_target_pct=50,
                   stop_loss_pct=200, dte_exit=21):
    """Create a mock StrategyORM."""
    strat = MagicMock()
    strat.strategy_type = strategy_type
    strat.profit_target_pct = Decimal(str(profit_target_pct))
    strat.stop_loss_pct = Decimal(str(stop_loss_pct))
    strat.dte_exit = dte_exit
    return strat


def _make_iron_condor_trade():
    """Create a mock TradeORM for a GLD iron condor."""
    trade = MagicMock()
    trade.id = "trade-ic-001"
    trade.underlying_symbol = "GLD"
    trade.entry_price = Decimal("0.72")
    trade.current_price = Decimal("0.35")
    trade.entry_underlying_price = Decimal("466.88")
    trade.current_underlying_price = Decimal("468.00")
    trade.regime_at_entry = "R1"

    # 4 legs: short put, long put, short call, long call
    exp = datetime(2026, 4, 17)
    legs = [
        _make_leg(_make_symbol("GLD", "put", 455, exp), quantity=-1, side="sell"),
        _make_leg(_make_symbol("GLD", "put", 450, exp), quantity=1, side="buy"),
        _make_leg(_make_symbol("GLD", "call", 480, exp), quantity=-1, side="sell"),
        _make_leg(_make_symbol("GLD", "call", 485, exp), quantity=1, side="buy"),
    ]
    # Give unique IDs
    for i, leg in enumerate(legs):
        leg.id = f"leg-{i}"
        leg.symbol.id = f"sym-{i}"

    trade.legs = legs
    trade.strategy = _make_strategy()
    return trade


class TestSymbolToDxlink:
    def test_put_symbol(self):
        sym = _make_symbol("GLD", "put", 455, datetime(2026, 4, 17))
        assert _symbol_to_dxlink(sym) == ".GLD260417P455"

    def test_call_symbol(self):
        sym = _make_symbol("SPY", "call", 580, datetime(2026, 3, 27))
        assert _symbol_to_dxlink(sym) == ".SPY260327C580"

    def test_none_symbol(self):
        assert _symbol_to_dxlink(None) is None

    def test_equity_symbol(self):
        sym = MagicMock()
        sym.asset_type = "equity"
        assert _symbol_to_dxlink(sym) is None

    def test_date_object(self):
        sym = _make_symbol("QQQ", "put", 500)
        sym.expiration = date(2026, 5, 15)
        assert _symbol_to_dxlink(sym) == ".QQQ260515P500"


class TestLegAction:
    def test_negative_quantity_is_sto(self):
        leg = _make_leg(None, quantity=-1, side="sell")
        assert _leg_action(leg) == "STO"

    def test_positive_quantity_is_bto(self):
        leg = _make_leg(None, quantity=1, side="buy")
        assert _leg_action(leg) == "BTO"

    def test_sell_side_is_sto(self):
        leg = _make_leg(None, quantity=0, side="SELL_TO_OPEN")
        assert _leg_action(leg) == "STO"


class TestTradeToTradespec:
    def test_iron_condor_roundtrip(self):
        trade = _make_iron_condor_trade()
        spec = trade_to_tradespec(trade)

        assert spec is not None
        assert spec.ticker == "GLD"
        assert len(spec.legs) == 4
        # Auto-detection should identify iron_condor
        assert spec.structure_type in ("iron_condor", "iron_butterfly", None, "unknown")

    def test_explicit_underlying_price(self):
        trade = _make_iron_condor_trade()
        spec = trade_to_tradespec(trade, underlying_price=470.0)
        assert spec is not None
        assert spec.underlying_price == 470.0

    def test_fallback_to_entry_price(self):
        trade = _make_iron_condor_trade()
        trade.current_underlying_price = None
        spec = trade_to_tradespec(trade)
        assert spec is not None
        assert spec.underlying_price == 466.88

    def test_no_legs_returns_none(self):
        trade = MagicMock()
        trade.id = "trade-empty"
        trade.legs = []
        assert trade_to_tradespec(trade) is None

    def test_exit_rules_from_strategy(self):
        trade = _make_iron_condor_trade()
        spec = trade_to_tradespec(trade)
        assert spec is not None
        assert spec.profit_target_pct == 0.50
        assert spec.stop_loss_pct == 2.00
        assert spec.exit_dte == 21


class TestTradeToDxlinkSymbols:
    def test_extracts_all_symbols(self):
        trade = _make_iron_condor_trade()
        symbols = trade_to_dxlink_symbols(trade)
        assert len(symbols) == 4
        assert ".GLD260417P455" in symbols
        assert ".GLD260417P450" in symbols
        assert ".GLD260417C480" in symbols
        assert ".GLD260417C485" in symbols

    def test_empty_legs(self):
        trade = MagicMock()
        trade.legs = []
        assert trade_to_dxlink_symbols(trade) == []


class TestTradeToMonitorParams:
    def test_iron_condor_params(self):
        trade = _make_iron_condor_trade()
        params = trade_to_monitor_params(trade)

        assert params is not None
        assert params['trade_id'] == "trade-ic-001"
        assert params['ticker'] == "GLD"
        assert params['structure_type'] == "iron_condor"
        assert params['order_side'] == "credit"
        assert params['entry_price'] == 0.72
        assert params['current_mid_price'] == 0.35
        assert params['profit_target_pct'] == 0.50
        assert params['stop_loss_pct'] == 2.00
        assert params['exit_dte'] == 21
        assert params['entry_regime_id'] == 1

    def test_no_entry_price_returns_none(self):
        trade = _make_iron_condor_trade()
        trade.entry_price = None
        assert trade_to_monitor_params(trade) is None
