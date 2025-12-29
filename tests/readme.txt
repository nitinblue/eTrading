

Run All Tests
Bash# From project root
pytest -v
# Or with coverage
pip install pytest-cov
pytest --cov=trading_bot -v
Expected Outcome of a Full Dry Run
Bash$ pytest -v
================================== test session starts ==================================
collected 12 items

tests/unit/test_strategy.py::test_short_put_entry_met PASSED                         [  8%]
tests/unit/test_strategy.py::test_short_put_entry_rejected_high_delta PASSED         [ 16%]
tests/unit/test_strategy.py::test_short_put_exit_profit_target PASSED                [ 25%]
tests/unit/test_strategy.py::test_short_put_exit_max_loss PASSED                     [ 33%]
tests/unit/test_risk.py::test_risk_manager_portfolio_limit_exceeded PASSED           [ 41%]
tests/unit/test_risk.py::test_risk_manager_within_limits PASSED                      [ 50%]
tests/unit/test_portfolio.py::test_portfolio_net_greeks PASSED                       [ 58%]
tests/unit/test_trade_execution.py::test_trade_executor_dry_run PASSED               [ 66%]
tests/integration/test_full_flow_mock.py::test_full_entry_flow PASSED                [ 75%]
tests/integration/test_full_flow_mock.py::test_kill_switch_closes_all PASSED        [ 83%]
...
================================== 12 passed in 0.8s ===================================