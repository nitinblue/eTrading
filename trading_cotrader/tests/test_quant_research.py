"""
Tests for ScoutAgent — market analysis, screening, and ranking pipeline.

Scout owns the ResearchContainer and uses market_analyzer's screening + ranking
services to find actionable setups.

Tests:
1. Agent config and metadata
2. Agent run() with mocked market_analyzer screening/ranking
3. Agent populate() requires container
4. Research portfolios exist in risk_config.yaml
5. TradeSource enum values
6. Agent registry includes scout
7. Agent wired into workflow engine
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from decimal import Decimal
from pathlib import Path

from trading_cotrader.agents.domain.scout import ScoutAgent
from trading_cotrader.agents.protocol import AgentStatus
from trading_cotrader.core.models.domain import TradeSource


class TestScoutAgentConfig:
    """Test ScoutAgent metadata and configuration."""

    def test_agent_has_correct_name(self):
        agent = ScoutAgent()
        assert agent.name == "scout"

    def test_safety_check_always_passes(self):
        agent = ScoutAgent()
        ok, reason = agent.safety_check({})
        assert ok is True
        assert reason == ""

    def test_agent_metadata(self):
        meta = ScoutAgent.get_metadata()
        assert meta['name'] == 'scout'
        assert meta['display_name'] == 'Scout (Quant)'
        assert meta['category'] == 'domain'
        assert 'monitoring' in meta['runs_during']

    def test_agent_responsibilities(self):
        meta = ScoutAgent.get_metadata()
        assert 'Market screening (breakout, momentum, mean-reversion, income)' in meta['responsibilities']
        assert 'Candidate ranking' in meta['responsibilities']

    def test_agent_datasources(self):
        meta = ScoutAgent.get_metadata()
        assert 'market_analyzer library' in meta['datasources']
        assert 'ResearchContainer' in meta['datasources']


class TestScoutAgentRun:
    """Test agent run() with mocked market_analyzer."""

    def test_no_container_returns_error(self):
        agent = ScoutAgent(container=None)
        result = agent.run({})
        assert result.status == AgentStatus.ERROR

    def test_empty_watchlist_returns_completed(self):
        container = MagicMock()
        container.symbols = []
        agent = ScoutAgent(container=container)
        result = agent.run({})
        assert result.status == AgentStatus.COMPLETED
        assert result.data['tickers'] == 0

    def test_screening_and_ranking(self):
        """Test run() calls screening and ranking."""
        container = MagicMock()
        container.symbols = ['SPY', 'QQQ']

        # Mock market_analyzer
        mock_ma = MagicMock()

        # Mock screening result
        mock_candidate = MagicMock()
        mock_candidate.model_dump.return_value = {'ticker': 'SPY', 'screen': 'momentum', 'score': 0.8}
        mock_scan = MagicMock()
        mock_scan.candidates = [mock_candidate]
        mock_scan.tickers_scanned = 2
        mock_ma.screening.scan.return_value = mock_scan

        # Mock ranking result
        mock_ranked = MagicMock()
        mock_ranked.model_dump.return_value = {'ticker': 'SPY', 'score': 0.9, 'rank': 1}
        mock_rank_result = MagicMock()
        mock_rank_result.ranked = [mock_ranked]
        mock_ma.ranking.rank.return_value = mock_rank_result

        # Mock black swan
        mock_bs = MagicMock()
        mock_bs.alert_level = 'NORMAL'
        mock_bs.composite_score = 0.1
        mock_ma.black_swan.alert.return_value = mock_bs

        # Mock context
        mock_ctx = MagicMock()
        mock_ctx.environment_label = 'risk-on'
        mock_ctx.trading_allowed = True
        mock_ctx.position_size_factor = 1.0
        mock_ma.context.assess.return_value = mock_ctx

        agent = ScoutAgent(container=container)
        agent._market_analyzer = mock_ma

        context = {}
        result = agent.run(context)

        assert result.status == AgentStatus.COMPLETED
        assert result.data['candidates'] == 1
        assert result.data['ranked'] == 1
        assert result.data['black_swan'] == 'NORMAL'
        assert 'screening_candidates' in context
        assert 'ranking' in context
        assert context['trading_allowed'] is True

    def test_screening_failure_handled_gracefully(self):
        """Test run() handles screening failure without crashing."""
        container = MagicMock()
        container.symbols = ['SPY']

        mock_ma = MagicMock()
        mock_ma.screening.scan.side_effect = Exception("API timeout")
        mock_ma.ranking.rank.return_value = MagicMock(ranked=[])
        mock_ma.black_swan.alert.return_value = MagicMock(alert_level='NORMAL', composite_score=0.0)
        mock_ma.context.assess.return_value = MagicMock(
            environment_label='cautious', trading_allowed=True, position_size_factor=0.8
        )

        agent = ScoutAgent(container=container)
        agent._market_analyzer = mock_ma

        result = agent.run({})
        assert result.status == AgentStatus.COMPLETED
        assert result.data['candidates'] == 0

    def test_context_stores_black_swan_level(self):
        """Test elevated black swan level stored in context."""
        container = MagicMock()
        container.symbols = ['SPY']

        mock_ma = MagicMock()
        mock_ma.screening.scan.return_value = MagicMock(candidates=[], tickers_scanned=1)
        mock_ma.ranking.rank.return_value = MagicMock(ranked=[])
        mock_ma.black_swan.alert.return_value = MagicMock(alert_level='ELEVATED', composite_score=0.35)
        mock_ma.context.assess.return_value = MagicMock(
            environment_label='cautious', trading_allowed=True, position_size_factor=0.7
        )

        agent = ScoutAgent(container=container)
        agent._market_analyzer = mock_ma

        context = {}
        agent.run(context)
        assert context['black_swan_level'] == 'ELEVATED'


class TestScoutAgentPopulate:
    """Test populate() behavior."""

    def test_populate_without_container_returns_error(self):
        agent = ScoutAgent(container=None)
        result = agent.populate({})
        assert result.status == AgentStatus.ERROR

    def test_populate_empty_watchlist(self):
        container = MagicMock()
        container.watchlist_config = True
        container.symbols = []
        agent = ScoutAgent(container=container)
        result = agent.populate({})
        assert result.status == AgentStatus.COMPLETED
        assert result.data['tickers'] == 0


class TestTradeSourceEnum:
    """Test TradeSource enum has research values."""

    def test_quant_research_source_exists(self):
        assert TradeSource.QUANT_RESEARCH.value == "quant_research"

    def test_research_template_source_exists(self):
        assert TradeSource.RESEARCH_TEMPLATE.value == "research_template"

    def test_scenario_sources_exist(self):
        assert TradeSource.SCENARIO_CORRECTION.value == "scenario_correction"
        assert TradeSource.SCENARIO_EARNINGS.value == "scenario_earnings"
        assert TradeSource.SCENARIO_BLACK_SWAN.value == "scenario_black_swan"
        assert TradeSource.SCENARIO_ARBITRAGE.value == "scenario_arbitrage"


class TestResearchPortfolioConfig:
    """Test research portfolios are properly configured in risk_config.yaml."""

    def test_research_portfolios_exist_in_config(self):
        import yaml
        config_path = Path(__file__).parent.parent / 'config' / 'risk_config.yaml'
        with open(config_path) as f:
            config = yaml.safe_load(f)

        portfolios = config.get('portfolios', {})
        assert 'research_correction' in portfolios
        assert 'research_earnings' in portfolios
        assert 'research_black_swan' in portfolios
        assert 'research_arbitrage' in portfolios
        assert 'research_custom' in portfolios

    def test_research_portfolios_are_research_type(self):
        import yaml
        config_path = Path(__file__).parent.parent / 'config' / 'risk_config.yaml'
        with open(config_path) as f:
            config = yaml.safe_load(f)

        for name in ['research_correction', 'research_earnings', 'research_black_swan',
                      'research_arbitrage', 'research_custom']:
            portfolio = config['portfolios'][name]
            assert portfolio['portfolio_type'] == 'research', f"{name} not research type"
            assert portfolio['initial_capital'] == 0, f"{name} should have 0 capital"
            assert 'research' in portfolio.get('tags', []), f"{name} missing research tag"

    def test_research_portfolios_have_loose_risk_limits(self):
        import yaml
        config_path = Path(__file__).parent.parent / 'config' / 'risk_config.yaml'
        with open(config_path) as f:
            config = yaml.safe_load(f)

        for name in ['research_correction', 'research_earnings', 'research_black_swan',
                      'research_arbitrage', 'research_custom']:
            limits = config['portfolios'][name]['risk_limits']
            assert limits['max_positions'] >= 100, f"{name} should allow many positions"
            assert limits['min_cash_reserve_pct'] == 0, f"{name} should have 0 cash reserve"


class TestAgentRegistry:
    """Test scout is in the agent registry."""

    def test_agent_in_registry(self):
        from trading_cotrader.web.api_agents import AGENT_REGISTRY
        assert 'scout' in AGENT_REGISTRY

    def test_registry_entry_has_required_fields(self):
        from trading_cotrader.web.api_agents import AGENT_REGISTRY
        entry = AGENT_REGISTRY['scout']
        assert entry['category'] == 'domain'
        assert 'monitoring' in entry['runs_during']
        assert 'Candidate ranking' in entry['responsibilities']

    def test_agent_class_metadata(self):
        """Test metadata comes from BaseAgent.get_metadata() classmethod."""
        meta = ScoutAgent.get_metadata()
        assert meta['name'] == 'scout'
        assert meta['display_name'] == 'Scout (Quant)'
        assert meta['category'] == 'domain'
        assert 'monitoring' in meta['runs_during']

    def test_agent_is_base_agent(self):
        """Test ScoutAgent extends BaseAgent."""
        from trading_cotrader.agents.base import BaseAgent
        agent = ScoutAgent()
        assert isinstance(agent, BaseAgent)


class TestWorkflowEngineWiring:
    """Test ScoutAgent is wired into the workflow engine."""

    def test_engine_has_scout_agent(self):
        from trading_cotrader.agents.domain import scout as scout_mod
        assert hasattr(scout_mod, 'ScoutAgent')

    def test_engine_instantiates_scout(self):
        import inspect
        from trading_cotrader.workflow.engine import WorkflowEngine
        source = inspect.getsource(WorkflowEngine.__init__)
        assert 'scout' in source
        assert 'ScoutAgent' in source
