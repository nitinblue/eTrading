"""
Tests for StewardAgent — portfolio state + capital utilization.

Mirrors test_quant_research.py structure (Scout exemplar).
Steward absorbs PortfolioStateAgent (populate) and CapitalUtilizationAgent (run).

Tests:
1. Agent has correct name
2. Safety check always passes
3. populate fills context keys from container manager
4. populate returns ERROR when no container_manager
5. run performs capital analysis and sets alerts
6. run with no portfolios produces no alerts
7. Agent is in registry
8. Agent class metadata
9. Agent is BaseAgent subclass
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from decimal import Decimal

from trading_cotrader.agents.domain.steward import StewardAgent
from trading_cotrader.agents.protocol import AgentStatus


class TestStewardAgentIdentity:
    """Test agent identity and metadata."""

    def test_agent_has_correct_name(self):
        agent = StewardAgent()
        assert agent.name == "steward"

    def test_safety_check_always_passes(self):
        agent = StewardAgent()
        ok, reason = agent.safety_check({})
        assert ok is True
        assert reason == ""

    def test_agent_is_base_agent(self):
        from trading_cotrader.agents.base import BaseAgent
        agent = StewardAgent()
        assert isinstance(agent, BaseAgent)

    def test_agent_class_metadata(self):
        meta = StewardAgent.get_metadata()
        assert meta['name'] == 'steward'
        assert meta['display_name'] == 'Steward (Portfolio)'
        assert meta['category'] == 'domain'
        assert 'booting' in meta['runs_during']
        assert 'monitoring' in meta['runs_during']

    def test_agent_in_registry(self):
        from trading_cotrader.web.api_agents import AGENT_REGISTRY
        assert 'steward' in AGENT_REGISTRY

    def test_registry_entry_has_required_fields(self):
        from trading_cotrader.web.api_agents import AGENT_REGISTRY
        entry = AGENT_REGISTRY['steward']
        assert entry['category'] == 'domain'
        assert 'booting' in entry['runs_during']
        assert 'Capital utilization' in entry['responsibilities']


class TestStewardPopulate:
    """Test populate() — fills containers from DB."""

    def test_populate_no_container_manager(self):
        """populate() returns ERROR when no container_manager."""
        agent = StewardAgent(container_manager=None)
        result = agent.populate({})
        assert result.status == AgentStatus.ERROR
        assert "No container_manager" in result.messages[0]

    @patch('trading_cotrader.core.database.session.session_scope')
    def test_populate_fills_context_keys(self, mock_session_scope):
        """populate() sets expected context keys."""
        # Mock container manager
        mock_cm = MagicMock()

        # Create a mock PortfolioState
        mock_pstate = MagicMock()
        mock_pstate.total_equity = Decimal('50000')
        mock_pstate.daily_pnl = Decimal('150')
        mock_pstate.cash_balance = Decimal('10000')
        mock_pstate.delta = Decimal('50')
        mock_pstate.theta = Decimal('-25')
        mock_pstate.portfolio_id = 'test-id'
        mock_pstate.name = 'test'
        mock_pstate.portfolio_type = 'real'

        # Create mock bundle
        mock_bundle = MagicMock()
        mock_bundle.portfolio.state = mock_pstate
        mock_bundle.config_name = 'test'
        mock_bundle.account_number = 'ACC123'
        mock_bundle.broker_firm = 'tastytrade'
        mock_bundle.trades.get_all.return_value = []

        mock_cm.get_all_bundles.return_value = [mock_bundle]
        mock_cm.load_all_bundles = MagicMock()

        # Mock DB session for trade counts
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.count.return_value = 0
        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_session_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_session_scope.return_value.__exit__ = MagicMock(return_value=False)

        agent = StewardAgent(container_manager=mock_cm)
        context = {}
        result = agent.populate(context)

        assert result.status == AgentStatus.COMPLETED
        assert 'portfolios' in context
        assert 'open_trades' in context
        assert 'total_equity' in context
        assert 'daily_pnl_pct' in context
        assert 'trades_today_count' in context
        assert 'weekly_trades_per_portfolio' in context
        assert context['total_equity'] == 50000.0
        assert result.data['portfolio_count'] == 1


class TestStewardRun:
    """Test run() — capital utilization analysis."""

    def test_run_no_config(self):
        """run() with no config returns empty utilization."""
        agent = StewardAgent(config=None)
        context = {'portfolios': []}
        result = agent.run(context)
        assert result.status == AgentStatus.COMPLETED
        assert context.get('capital_utilization') == {}
        assert context.get('capital_alerts') == []

    def test_run_no_portfolios(self):
        """run() with no portfolios produces no alerts."""
        from trading_cotrader.config.workflow_config_loader import WorkflowConfig
        config = WorkflowConfig()
        agent = StewardAgent(config=config)
        context = {'portfolios': []}
        result = agent.run(context)
        assert result.status == AgentStatus.COMPLETED
        assert result.data['alert_count'] == 0

    def test_run_capital_analysis(self):
        """run() computes capital utilization from context portfolios."""
        from trading_cotrader.config.workflow_config_loader import WorkflowConfig
        config = WorkflowConfig()
        agent = StewardAgent(config=config)
        context = {
            'portfolios': [{
                'account_id': 'test_portfolio',
                'name': 'test',
                'equity': 100000.0,
                'cash': 90000.0,  # 90% cash = very idle
            }],
            'engine_start_time': '2020-01-01T00:00:00',  # old enough to bypass ramp
        }
        result = agent.run(context)
        assert result.status == AgentStatus.COMPLETED
        assert 'capital_utilization' in context
        assert 'capital_alerts' in context


class TestStewardEngineWiring:
    """Test Steward is wired into the workflow engine."""

    def test_engine_has_steward_agent(self):
        from trading_cotrader.agents.domain import steward as steward_mod
        assert hasattr(steward_mod, 'StewardAgent')

    def test_engine_instantiates_steward(self):
        import inspect
        from trading_cotrader.workflow.engine import WorkflowEngine
        source = inspect.getsource(WorkflowEngine.__init__)
        assert 'steward' in source
        assert 'StewardAgent' in source
        assert 'container_manager' in source
