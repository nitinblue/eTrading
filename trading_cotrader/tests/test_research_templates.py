"""
Tests for Research Template system — YAML loading, validation, agent integration.

Tests:
1. YAML loading — all 7 templates load correctly
2. Template validation — fields parsed correctly
3. Earnings template uses universe_from
4. Entry/exit conditions parsed as Condition objects
5. Variants parsed correctly
6. TradeStrategyConfig for equity vs option
7. Integration: QuantResearchAgent uses research templates
8. Agent disabled returns early
9. Agent with no templates returns early
10. TradeSource.RESEARCH_TEMPLATE exists
11. Research portfolios include research_custom
"""

import pytest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch, MagicMock

from trading_cotrader.services.research.template_loader import (
    load_research_templates, get_enabled_templates,
    ResearchTemplate, TradeStrategyConfig, StrategyVariant, ParameterVariant,
)
from trading_cotrader.services.research.condition_evaluator import Condition
from trading_cotrader.agents.analysis.quant_research import QuantResearchAgent
from trading_cotrader.agents.protocol import AgentStatus
from trading_cotrader.core.models.domain import TradeSource


class TestYamlLoading:
    """Test research_templates.yaml loads correctly."""

    def test_all_templates_load(self):
        templates = load_research_templates()
        assert len(templates) >= 7

    def test_expected_templates_present(self):
        templates = load_research_templates()
        expected = [
            'correction_premium_sell', 'earnings_iv_crush',
            'black_swan_hedge', 'vol_arbitrage_calendar',
            'ma_crossover_rsi', 'bollinger_bounce', 'high_iv_iron_condor',
        ]
        for name in expected:
            assert name in templates, f"Missing template: {name}"

    def test_all_templates_enabled(self):
        templates = load_research_templates()
        for name, t in templates.items():
            assert t.enabled is True, f"{name} should be enabled"

    def test_get_enabled_filters(self):
        enabled = get_enabled_templates()
        assert len(enabled) >= 7


class TestTemplateFields:
    """Test individual template fields are parsed correctly."""

    def setup_method(self):
        self.templates = load_research_templates()

    def test_correction_template(self):
        t = self.templates['correction_premium_sell']
        assert t.display_name == "Market Correction - Sell Premium"
        assert t.author == "system"
        assert 'SPY' in t.universe
        assert t.target_portfolio == "research_correction"
        assert t.cadence == "opportunistic"
        assert t.auto_approve is True

    def test_earnings_uses_universe_from(self):
        t = self.templates['earnings_iv_crush']
        assert t.universe == [] or t.universe is not None
        assert t.universe_from == "earnings_calendar"

    def test_black_swan_not_auto_approve(self):
        t = self.templates['black_swan_hedge']
        assert t.auto_approve is False

    def test_equity_template_instrument(self):
        t = self.templates['ma_crossover_rsi']
        assert t.trade_strategy.instrument == 'equity'
        assert t.trade_strategy.position_type == 'long'
        assert len(t.trade_strategy.strategies) == 0  # equity has no strategy variants

    def test_option_template_has_strategies(self):
        t = self.templates['correction_premium_sell']
        assert t.trade_strategy.instrument == 'option'
        assert len(t.trade_strategy.strategies) >= 2

    def test_high_iv_has_trade_template_ref(self):
        t = self.templates['high_iv_iron_condor']
        assert t.trade_strategy.trade_template == 'monthly_iron_condor'

    def test_strategy_variant_fields(self):
        t = self.templates['correction_premium_sell']
        strats = t.trade_strategy.strategies
        vs = strats[0]  # vertical_spread
        assert vs.strategy_type == 'vertical_spread'
        assert vs.option_type == 'put'
        assert vs.direction == 'sell'
        assert vs.dte_target == 45
        assert vs.short_delta == 0.30
        assert vs.confidence == 7
        assert vs.risk_category == 'defined'


class TestConditionsParsing:
    """Test entry and exit conditions are parsed as Condition objects."""

    def setup_method(self):
        self.templates = load_research_templates()

    def test_correction_entry_conditions(self):
        t = self.templates['correction_premium_sell']
        assert len(t.entry_conditions) == 4
        assert all(isinstance(c, Condition) for c in t.entry_conditions)

        # Check specific conditions
        indicators = [c.indicator for c in t.entry_conditions]
        assert 'pct_from_52w_high' in indicators
        assert 'vix' in indicators
        assert 'rsi_14' in indicators
        assert 'directional_regime' in indicators

    def test_correction_exit_conditions(self):
        t = self.templates['correction_premium_sell']
        assert len(t.exit_conditions) == 3
        indicators = [c.indicator for c in t.exit_conditions]
        assert 'pnl_pct' in indicators
        assert 'days_held' in indicators

    def test_between_operator_parsed(self):
        t = self.templates['correction_premium_sell']
        pct_cond = next(c for c in t.entry_conditions if c.indicator == 'pct_from_52w_high')
        assert pct_cond.operator == 'between'
        assert pct_cond.value == [-15.0, -8.0]

    def test_in_operator_parsed(self):
        t = self.templates['correction_premium_sell']
        regime_cond = next(c for c in t.entry_conditions if c.indicator == 'directional_regime')
        assert regime_cond.operator == 'in'
        assert regime_cond.value == ["D", "F"]

    def test_reference_condition_parsed(self):
        t = self.templates['ma_crossover_rsi']
        price_cond = next(c for c in t.entry_conditions if c.indicator == 'price')
        assert price_cond.reference == 'sma_20'
        assert price_cond.operator == 'gt'

    def test_multiplier_condition_parsed(self):
        t = self.templates['ma_crossover_rsi']
        vol_cond = next(c for c in t.entry_conditions if c.indicator == 'volume')
        assert vol_cond.reference == 'avg_volume_20'
        assert vol_cond.multiplier == 1.5


class TestVariantsParsing:
    """Test parameter variants are parsed correctly."""

    def setup_method(self):
        self.templates = load_research_templates()

    def test_correction_has_variants(self):
        t = self.templates['correction_premium_sell']
        assert len(t.variants) >= 3
        variant_ids = [v.variant_id for v in t.variants]
        assert 'base' in variant_ids
        assert 'delta_tight' in variant_ids
        assert 'delta_wide' in variant_ids

    def test_variant_overrides(self):
        t = self.templates['correction_premium_sell']
        tight = next(v for v in t.variants if v.variant_id == 'delta_tight')
        assert tight.overrides.get('short_delta') == 0.25

    def test_base_variant_no_overrides(self):
        t = self.templates['correction_premium_sell']
        base = next(v for v in t.variants if v.variant_id == 'base')
        assert base.overrides == {}

    def test_bollinger_has_single_variant(self):
        t = self.templates['bollinger_bounce']
        assert len(t.variants) == 1
        assert t.variants[0].variant_id == 'base'


class TestTradeSourceEnum:
    """Test TradeSource enum has research template value."""

    def test_research_template_source_exists(self):
        assert TradeSource.RESEARCH_TEMPLATE.value == "research_template"

    def test_quant_research_source_still_exists(self):
        assert TradeSource.QUANT_RESEARCH.value == "quant_research"

    def test_scenario_sources_still_exist(self):
        assert TradeSource.SCENARIO_CORRECTION.value == "scenario_correction"
        assert TradeSource.SCENARIO_EARNINGS.value == "scenario_earnings"
        assert TradeSource.SCENARIO_BLACK_SWAN.value == "scenario_black_swan"
        assert TradeSource.SCENARIO_ARBITRAGE.value == "scenario_arbitrage"


class TestResearchPortfolioConfig:
    """Test research portfolios including new research_custom."""

    def test_research_custom_exists(self):
        import yaml
        config_path = Path(__file__).parent.parent / 'config' / 'risk_config.yaml'
        with open(config_path) as f:
            config = yaml.safe_load(f)

        portfolios = config.get('portfolios', {})
        assert 'research_custom' in portfolios

    def test_research_custom_is_research_type(self):
        import yaml
        config_path = Path(__file__).parent.parent / 'config' / 'risk_config.yaml'
        with open(config_path) as f:
            config = yaml.safe_load(f)

        p = config['portfolios']['research_custom']
        assert p['portfolio_type'] == 'research'
        assert p['initial_capital'] == 0
        assert 'research' in p.get('tags', [])

    def test_all_research_portfolios_exist(self):
        import yaml
        config_path = Path(__file__).parent.parent / 'config' / 'risk_config.yaml'
        with open(config_path) as f:
            config = yaml.safe_load(f)

        portfolios = config.get('portfolios', {})
        for name in ['research_correction', 'research_earnings',
                      'research_black_swan', 'research_arbitrage', 'research_custom']:
            assert name in portfolios, f"Missing portfolio: {name}"


class TestQuantResearchAgentExecution:
    """Test the rewritten QuantResearchAgent."""

    def test_agent_has_correct_name(self):
        agent = QuantResearchAgent()
        assert agent.name == "quant_research"

    def test_safety_check_always_passes(self):
        agent = QuantResearchAgent()
        ok, reason = agent.safety_check({})
        assert ok is True

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
            'template_a': ResearchTemplate(
                name='template_a', enabled=True, universe=['SPY'],
                target_portfolio='research_custom',
                variants=[ParameterVariant(variant_id='base')],
            ),
            'template_b': ResearchTemplate(
                name='template_b', enabled=True, universe=['QQQ'],
                target_portfolio='research_custom',
                variants=[ParameterVariant(variant_id='base')],
            ),
        }
        mock_eval.return_value = (3, 3, 0)

        agent = QuantResearchAgent()
        result = agent.run({})

        assert result.status == AgentStatus.COMPLETED
        assert mock_eval.call_count == 2
        assert result.data['trades_booked'] == 6

    @patch('trading_cotrader.agents.analysis.quant_research.QuantResearchAgent._evaluate_template_variant')
    @patch('trading_cotrader.agents.analysis.quant_research.get_enabled_templates')
    @patch('trading_cotrader.agents.analysis.quant_research.QuantResearchAgent._is_research_enabled')
    def test_variants_each_trigger_evaluation(self, mock_enabled, mock_templates, mock_eval):
        mock_enabled.return_value = True
        mock_templates.return_value = {
            'template_a': ResearchTemplate(
                name='template_a', enabled=True, universe=['SPY'],
                target_portfolio='research_custom',
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

        assert mock_eval.call_count == 3
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
        mock_eval.return_value = (0, 0, 0)

        agent = QuantResearchAgent()
        result = agent.run({})

        # Should NOT call _evaluate_template_variant since no symbols
        assert mock_eval.call_count == 0


class TestAgentRegistry:
    """Test quant_research is in the agent registry."""

    def test_agent_in_registry(self):
        from trading_cotrader.web.api_agents import AGENT_REGISTRY
        assert 'quant_research' in AGENT_REGISTRY

    def test_registry_entry_has_required_fields(self):
        from trading_cotrader.web.api_agents import AGENT_REGISTRY
        entry = AGENT_REGISTRY['quant_research']
        assert entry['category'] == 'analysis'
        assert 'monitoring' in entry['runs_during']


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


class TestLegConstruction:
    """Test option leg building in QuantResearchAgent."""

    def setup_method(self):
        self.agent = QuantResearchAgent()

    def test_vertical_spread_legs(self):
        strategy = StrategyVariant(
            strategy_type='vertical_spread',
            option_type='put', direction='sell',
            dte_target=45, short_delta=0.30, wing_width_pct=0.05,
        )
        legs = self.agent._build_option_legs('SPY', strategy, Decimal('500'))
        assert len(legs) == 2
        # Long put (lower strike) and short put (higher strike)
        quantities = sorted([l.quantity for l in legs])
        assert quantities == [-1, 1]

    def test_iron_condor_legs(self):
        strategy = StrategyVariant(
            strategy_type='iron_condor',
            short_delta=0.20, wing_width_pct=0.08,
        )
        legs = self.agent._build_option_legs('SPY', strategy, Decimal('500'))
        assert len(legs) == 4
        puts = [l for l in legs if l.option_type == 'put']
        calls = [l for l in legs if l.option_type == 'call']
        assert len(puts) == 2
        assert len(calls) == 2

    def test_single_put_leg(self):
        strategy = StrategyVariant(
            strategy_type='single',
            option_type='put', direction='buy',
            delta_target=0.20,
        )
        legs = self.agent._build_option_legs('SPY', strategy, Decimal('500'))
        assert len(legs) == 1
        assert legs[0].quantity == 1
        assert legs[0].option_type == 'put'

    def test_equity_legs(self):
        template = ResearchTemplate(
            name='test', trade_strategy=TradeStrategyConfig(
                instrument='equity', position_type='long',
            ),
        )
        legs = self.agent._build_equity_legs('AAPL', template)
        assert len(legs) == 1
        assert legs[0].quantity == 1
        assert legs[0].streamer_symbol == 'AAPL'

    def test_equity_short_legs(self):
        template = ResearchTemplate(
            name='test', trade_strategy=TradeStrategyConfig(
                instrument='equity', position_type='short',
            ),
        )
        legs = self.agent._build_equity_legs('AAPL', template)
        assert len(legs) == 1
        assert legs[0].quantity == -1

    def test_calendar_spread_legs(self):
        strategy = StrategyVariant(
            strategy_type='calendar_spread',
            option_type='call',
            near_dte_target=7, far_dte_target=30,
            delta_target=0.40,
        )
        legs = self.agent._build_option_legs('SPY', strategy, Decimal('500'))
        assert len(legs) == 2
        # Near month sold, far month bought
        assert legs[0].quantity == -1
        assert legs[1].quantity == 1

    def test_strangle_legs(self):
        strategy = StrategyVariant(
            strategy_type='strangle',
            direction='sell', delta_target=0.16,
        )
        legs = self.agent._build_option_legs('SPY', strategy, Decimal('500'))
        assert len(legs) == 2
        assert all(l.quantity == -1 for l in legs)
        types = {l.option_type for l in legs}
        assert types == {'put', 'call'}
