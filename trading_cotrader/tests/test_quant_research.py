"""
Tests for QuantResearchAgent — research template evaluation pipeline.

Migrated from screener-based tests to research template tests (session 24).
Config-driven via config/research_templates.yaml.

Tests:
1. Agent loads research templates from YAML
2. Agent evaluates entry conditions and generates recommendations
3. Agent auto-accepts recommendations into research portfolios
4. Parameter variants generate separate evaluations
5. Disabled templates are skipped
6. Agent handles missing symbols gracefully
7. Research portfolios exist in risk_config.yaml
8. TradeSource enum values
9. Agent registry includes quant_research
10. Agent wired into workflow engine
"""

import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from pathlib import Path

from trading_cotrader.agents.analysis.quant_research import QuantResearchAgent
from trading_cotrader.agents.protocol import AgentStatus
from trading_cotrader.core.models.domain import TradeSource
from trading_cotrader.services.research.template_loader import (
    load_research_templates, ResearchTemplate, ParameterVariant,
)


class TestQuantResearchAgentConfig:
    """Test research template loading and validation."""

    def test_agent_has_correct_name(self):
        agent = QuantResearchAgent()
        assert agent.name == "quant_research"

    def test_safety_check_always_passes(self):
        agent = QuantResearchAgent()
        ok, reason = agent.safety_check({})
        assert ok is True
        assert reason == ""

    def test_loads_research_templates(self):
        templates = load_research_templates()
        assert isinstance(templates, dict)
        assert len(templates) >= 7

    def test_templates_have_expected_names(self):
        templates = load_research_templates()
        assert 'correction_premium_sell' in templates
        assert 'earnings_iv_crush' in templates
        assert 'black_swan_hedge' in templates
        assert 'vol_arbitrage_calendar' in templates

    def test_templates_have_required_fields(self):
        templates = load_research_templates()
        for name, t in templates.items():
            assert t.target_portfolio, f"{name} missing target_portfolio"
            assert len(t.entry_conditions) > 0, f"{name} missing entry_conditions"
            assert len(t.exit_conditions) > 0, f"{name} missing exit_conditions"

    def test_variants_have_variant_id(self):
        templates = load_research_templates()
        for name, t in templates.items():
            for variant in t.variants:
                assert variant.variant_id, f"{name} variant missing variant_id"

    def test_correction_has_parameter_variants(self):
        templates = load_research_templates()
        t = templates['correction_premium_sell']
        assert len(t.variants) >= 2, "Expected at least base + 1 variant"
        variant_ids = [v.variant_id for v in t.variants]
        assert 'base' in variant_ids
        assert 'delta_tight' in variant_ids


class TestQuantResearchAgentExecution:
    """Test agent execution with mocked evaluation."""

    @patch('trading_cotrader.agents.analysis.quant_research.QuantResearchAgent._is_research_enabled')
    def test_disabled_returns_early(self, mock_enabled):
        mock_enabled.return_value = False
        agent = QuantResearchAgent()
        result = agent.run({})
        assert result.status == AgentStatus.COMPLETED
        assert result.data.get('enabled') is False

    @patch('trading_cotrader.agents.analysis.quant_research.get_enabled_templates')
    @patch('trading_cotrader.agents.analysis.quant_research.QuantResearchAgent._is_research_enabled')
    def test_no_templates_returns_early(self, mock_enabled, mock_templates):
        mock_enabled.return_value = True
        mock_templates.return_value = {}
        agent = QuantResearchAgent()
        result = agent.run({})
        assert result.status == AgentStatus.COMPLETED
        assert result.data.get('template_count') == 0

    @patch('trading_cotrader.agents.analysis.quant_research.QuantResearchAgent._evaluate_template_variant')
    @patch('trading_cotrader.agents.analysis.quant_research.get_enabled_templates')
    @patch('trading_cotrader.agents.analysis.quant_research.QuantResearchAgent._is_research_enabled')
    def test_runs_all_enabled_templates(self, mock_enabled, mock_templates, mock_eval):
        mock_enabled.return_value = True
        mock_templates.return_value = {
            'correction': ResearchTemplate(
                name='correction', enabled=True, universe=['SPY', 'QQQ'],
                target_portfolio='research_correction',
                variants=[ParameterVariant(variant_id='base')],
            ),
            'arbitrage': ResearchTemplate(
                name='arbitrage', enabled=True, universe=['SPY'],
                target_portfolio='research_arbitrage',
                variants=[ParameterVariant(variant_id='base')],
            ),
        }
        mock_eval.return_value = (3, 3, 0)
        agent = QuantResearchAgent()
        result = agent.run({})
        assert result.status == AgentStatus.COMPLETED
        assert mock_eval.call_count == 2
        assert result.data['trades_booked'] == 6  # 3 per template

    @patch('trading_cotrader.agents.analysis.quant_research.QuantResearchAgent._evaluate_template_variant')
    @patch('trading_cotrader.agents.analysis.quant_research.get_enabled_templates')
    @patch('trading_cotrader.agents.analysis.quant_research.QuantResearchAgent._is_research_enabled')
    def test_variants_each_trigger_evaluation(self, mock_enabled, mock_templates, mock_eval):
        mock_enabled.return_value = True
        mock_templates.return_value = {
            'correction': ResearchTemplate(
                name='correction', enabled=True, universe=['SPY'],
                target_portfolio='research_correction',
                variants=[
                    ParameterVariant(variant_id='base'),
                    ParameterVariant(variant_id='tight', overrides={'short_delta': 0.25}),
                    ParameterVariant(variant_id='wide', overrides={'short_delta': 0.35}),
                ],
            ),
        }
        mock_eval.return_value = (1, 1, 0)
        agent = QuantResearchAgent()
        result = agent.run({})
        assert mock_eval.call_count == 3  # One per variant
        assert result.data['trades_booked'] == 3

    @patch('trading_cotrader.agents.analysis.quant_research.QuantResearchAgent._evaluate_template_variant')
    @patch('trading_cotrader.agents.analysis.quant_research.get_enabled_templates')
    @patch('trading_cotrader.agents.analysis.quant_research.QuantResearchAgent._is_research_enabled')
    def test_context_updated_with_booked_trades(self, mock_enabled, mock_templates, mock_eval):
        mock_enabled.return_value = True
        mock_templates.return_value = {
            'correction_premium_sell': ResearchTemplate(
                name='correction_premium_sell', enabled=True,
                universe=['SPY'], target_portfolio='research_correction',
                variants=[ParameterVariant(variant_id='base')],
            ),
        }
        mock_eval.return_value = (2, 2, 0)
        context = {}
        agent = QuantResearchAgent()
        agent.run(context)
        assert 'research_trades_booked' in context
        assert len(context['research_trades_booked']) == 1
        assert context['research_trades_booked'][0]['template'] == 'correction_premium_sell'
        assert context['research_trades_booked'][0]['count'] == 2

    @patch('trading_cotrader.agents.analysis.quant_research.QuantResearchAgent._evaluate_template_variant')
    @patch('trading_cotrader.agents.analysis.quant_research.get_enabled_templates')
    @patch('trading_cotrader.agents.analysis.quant_research.QuantResearchAgent._is_research_enabled')
    def test_empty_universe_skipped(self, mock_enabled, mock_templates, mock_eval):
        mock_enabled.return_value = True
        mock_templates.return_value = {
            'empty': ResearchTemplate(
                name='empty', enabled=True, universe=[],
                target_portfolio='research_custom',
                variants=[ParameterVariant(variant_id='base')],
            ),
        }
        agent = QuantResearchAgent()
        result = agent.run({})
        # No symbols → no evaluation
        assert mock_eval.call_count == 0


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
    """Test quant_research is in the agent registry."""

    def test_agent_in_registry(self):
        from trading_cotrader.web.api_agents import AGENT_REGISTRY
        assert 'quant_research' in AGENT_REGISTRY

    def test_registry_entry_has_required_fields(self):
        from trading_cotrader.web.api_agents import AGENT_REGISTRY
        entry = AGENT_REGISTRY['quant_research']
        assert entry['category'] == 'domain'
        assert 'monitoring' in entry['runs_during']
        assert 'Auto-booking' in entry['responsibilities']

    def test_agent_class_metadata(self):
        """Test metadata comes from BaseAgent.get_metadata() classmethod."""
        meta = QuantResearchAgent.get_metadata()
        assert meta['name'] == 'quant_research'
        assert meta['display_name'] == 'Quant Research'
        assert meta['category'] == 'domain'
        assert 'monitoring' in meta['runs_during']

    def test_agent_is_base_agent(self):
        """Test QuantResearchAgent extends BaseAgent."""
        from trading_cotrader.agents.base import BaseAgent
        agent = QuantResearchAgent()
        assert isinstance(agent, BaseAgent)


class TestWorkflowEngineWiring:
    """Test QuantResearchAgent is wired into the workflow engine."""

    def test_engine_has_quant_research_agent(self):
        from trading_cotrader.workflow import engine as eng
        assert hasattr(eng, 'QuantResearchAgent')

    def test_engine_instantiates_quant_research(self):
        import inspect
        from trading_cotrader.workflow.engine import WorkflowEngine
        source = inspect.getsource(WorkflowEngine.__init__)
        assert 'quant_research' in source
        assert 'QuantResearchAgent' in source
