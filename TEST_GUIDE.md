# Test Guide — Trading CoTrader

Run from repo root: `C:\Users\nitin\PythonProjects\eTrading`

## Quick start

```bash
# All 157 tests at once
pytest trading_cotrader/tests/ -v

# One file at a time (recommended order below)
pytest trading_cotrader/tests/<file> -v
```

---

## Recommended order (bottom-up, simple → complex)

### 1. Pricing & numerics (14 tests)
**What it covers:** Black-Scholes pricing, put-call parity, Greeks bounds, P&L math, Decimal precision.
This is the math foundation — everything else depends on prices being correct.

```bash
pytest trading_cotrader/tests/test_numerics.py -v
```

Key tests:
- `test_put_call_parity` — BS call - put = S - K*exp(-rT), within 0.01
- `test_greeks_within_bounds` — delta [0,1], gamma > 0, theta < 0, vega > 0
- `test_decimal_precision` — money never uses float

### 2. Trade lifecycle (9 tests)
**What it covers:** The `is_open` property on trades — how status transitions (intent → executed → closed) map to open/closed. Both domain model and DB round-trips.

```bash
pytest trading_cotrader/tests/test_is_open_lifecycle.py -v
```

Key tests:
- `test_executed_is_open` / `test_closed_not_open` — domain property
- `test_close_trade_sets_is_open_false` — DB update propagates
- `test_round_trip_preserves_is_open` — write to DB, read back, still correct

### 3. Trade booking (8 tests)
**What it covers:** Creating trades from JSON templates, persisting to DB, reading back, closing trades. Also tests trade source tracking (where did this trade come from?) and manual Greeks.

```bash
pytest trading_cotrader/tests/test_trade_booking.py -v
```

Key tests:
- `test_create_and_read_trade` — full round-trip: domain → DB → domain
- `test_trade_source_tracking` — every trade tagged with origin (screener, manual, etc.)
- `test_close_trade` — books opposite side, marks original closed

### 4. Entry filters (9 tests)
**What it covers:** Pre-trade screening rules. Each strategy has configurable filters (RSI range, directional regime, ATR minimum). All must pass for a recommendation to survive.

```bash
pytest trading_cotrader/tests/test_entry_filters.py -v
```

Key tests:
- `test_rsi_in_range_passes` / `test_rsi_out_of_range_fails` — RSI gate
- `test_regime_match` / `test_regime_mismatch` — only trade in correct market regime
- `test_multiple_filters_all_must_pass` — AND logic, not OR

### 5. Macro context (8 tests)
**What it covers:** The macro gate that sits before all screeners. If macro outlook is "risk_off", nothing gets through. Cautious outlook reduces confidence scores. VIX auto-assessment.

```bash
pytest trading_cotrader/tests/test_macro_context.py -v
```

Key tests:
- `test_risk_off_blocks_screening` — hard stop, zero recommendations
- `test_cautious_reduces_confidence` — recs still generated but downgraded
- `test_vix_auto_assessment` — VIX level maps to risk outlook automatically

### 6. Portfolio manager (6 tests)
**What it covers:** Multi-tier portfolio system. Each portfolio has allowed strategies, active strategies, risk limits. Validates that strategy permissions are enforced.

```bash
pytest trading_cotrader/tests/test_portfolio_manager.py -v
```

Key tests:
- `test_active_strategies_subset` — active must be subset of allowed
- `test_strategy_validation` — can't book iron condor in a portfolio that doesn't allow it
- `test_portfolio_initialization` — creates portfolio records in DB from YAML config

### 7. Multi-broker & adapters (37 tests)
**What it covers:** The full broker stack — registry, portfolio config, execution routing, safety checks. This is the most comprehensive test file. Covers 4 brokers, 10 portfolios, cross-broker safety, currency isolation, adapter factory, container bundles.

```bash
pytest trading_cotrader/tests/test_broker_config.py -v
```

Run by class to understand each layer:

```bash
# Layer 1: Broker registry (brokers.yaml)
pytest trading_cotrader/tests/test_broker_config.py::TestBrokerRegistry -v       # 9 tests

# Layer 2: Portfolio config (risk_config.yaml)
pytest trading_cotrader/tests/test_broker_config.py::TestPortfolioConfig -v      # 8 tests
pytest trading_cotrader/tests/test_broker_config.py::TestWhatIfInheritance -v    # 1 test

# Layer 3: Execution routing
pytest trading_cotrader/tests/test_broker_config.py::TestBrokerRouter -v         # 10 tests

# Safety: Guardian cross-broker checks
pytest trading_cotrader/tests/test_broker_config.py::TestGuardianCrossBroker -v  # 3 tests

# Portfolio manager with multi-broker
pytest trading_cotrader/tests/test_broker_config.py::TestPortfolioManagerMultiBroker -v  # 6 tests

# Adapter factory + container bundles
pytest trading_cotrader/tests/test_broker_config.py::TestBrokerAdapterFactory -v # 6 tests
pytest trading_cotrader/tests/test_broker_config.py::TestContainerBundles -v     # 12 tests

# QA agent + YAML loading
pytest trading_cotrader/tests/test_broker_config.py::TestQAAgent -v              # 2 tests
pytest trading_cotrader/tests/test_broker_config.py::TestLoadBrokerRegistryFromYAML -v  # 1 test
```

Key tests:
- `test_read_only_stallion` — Stallion trades blocked (managed fund)
- `test_cross_broker_routing_blocked` — can't route Fidelity trade to Tastytrade
- `test_currency_mismatch_blocked` — USD trade can't go to INR broker
- `test_whatif_inherits_strategies` — WhatIf portfolio copies parent's strategy list

### 8. VaR & correlation (24 tests)
**What it covers:** Portfolio risk measurement. Parametric VaR (delta-normal), historical VaR, incremental VaR (what happens if I add this trade?), expected shortfall, correlation matrix.

```bash
pytest trading_cotrader/tests/test_var_calculator.py -v
```

Run by class:

```bash
# How positions map to dollar exposure
pytest trading_cotrader/tests/test_var_calculator.py::TestDeltaExposure -v       # 6 tests

# Core VaR calculation
pytest trading_cotrader/tests/test_var_calculator.py::TestParametricVaR -v       # 8 tests

# "What if I add this trade?" analysis
pytest trading_cotrader/tests/test_var_calculator.py::TestIncrementalVaR -v      # 3 tests

# Correlation and covariance from market data
pytest trading_cotrader/tests/test_var_calculator.py::TestCorrelationMatrix -v   # 5 tests
```

Key tests:
- `test_diversified_var_less_than_sum` — diversification benefit is real
- `test_expected_shortfall_greater_than_var` — ES always >= VaR (tail risk)
- `test_adding_hedge_may_reduce_var` — opposite direction trade lowers risk

### 9. Snapshots & ML pipeline (20 tests)
**What it covers:** Daily portfolio snapshots (performance + Greeks history), upsert logic, ML data accumulation. This is the data pipeline that feeds future AI/ML models.

```bash
pytest trading_cotrader/tests/test_snapshot_service.py -v
```

Key tests:
- `test_capture_daily_snapshot` — ORM-direct snapshot capture
- `test_upsert_updates_existing` — same day = update, not duplicate
- `test_deprecated_portfolios_skipped` — old portfolios ignored
- `test_ml_pipeline_accumulate` — training data grows over time
- `test_ml_pipeline_feature_extraction` — raw snapshots → ML features

---

## Integration harness (17 steps, not unit tests)

The harness runs the full system end-to-end — DB setup, trade booking, screening, evaluation, risk. Slower, requires more setup.

```bash
# Without broker connection (14/16 pass, 2 skip)
python -m trading_cotrader.harness.runner --skip-sync

# With mock market data
python -m trading_cotrader.harness.runner --mock
```

---

## Architecture in test order

```
                    test_numerics (math)
                         |
                  test_is_open_lifecycle (trade state)
                         |
                  test_trade_booking (persistence)
                         |
              +----------+----------+
              |                     |
      test_entry_filters    test_macro_context
       (per-strategy)        (global gate)
              |                     |
              +----------+----------+
                         |
                test_portfolio_manager (strategy permissions)
                         |
                test_broker_config (multi-broker routing + safety)
                         |
                test_var_calculator (portfolio risk)
                         |
              test_snapshot_service (daily capture + ML pipeline)
```
