"""
Tests for MaverickAgent — domain orchestrator: ranking → gates → proposals.

Tests:
1. Agent has correct name
2. Safety check always passes
3. Agent is BaseAgent subclass
4. Agent class metadata
5. Agent in registry
6. Registry entry has required fields
7. run() with no container_manager returns COMPLETED
8. run() with positions + research produces trading signals
9. run() with no positions produces empty signals
10. run() with ranking produces proposals
11. run() filters NO_GO verdicts
12. run() filters low scores
13. run() prevents duplicate trades
14. Engine has maverick agent
15. Engine instantiates maverick with container_manager
"""

import pytest
from unittest.mock import MagicMock, PropertyMock
from decimal import Decimal

from trading_cotrader.agents.domain.maverick import MaverickAgent, _trade_spec_to_leg_inputs
from trading_cotrader.agents.protocol import AgentStatus


class TestMaverickAgentIdentity:
    """Test agent identity and metadata."""

    def test_agent_has_correct_name(self):
        agent = MaverickAgent()
        assert agent.name == "maverick"

    def test_safety_check_always_passes(self):
        agent = MaverickAgent()
        ok, reason = agent.safety_check({})
        assert ok is True
        assert reason == ""

    def test_agent_is_base_agent(self):
        from trading_cotrader.agents.base import BaseAgent
        agent = MaverickAgent()
        assert isinstance(agent, BaseAgent)

    def test_agent_class_metadata(self):
        meta = MaverickAgent.get_metadata()
        assert meta['name'] == 'maverick'
        assert meta['display_name'] == 'Maverick (Trader)'
        assert meta['category'] == 'domain'
        assert 'booting' in meta['runs_during']
        assert 'monitoring' in meta['runs_during']

    def test_agent_in_registry(self):
        from trading_cotrader.web.api_agents import AGENT_REGISTRY
        assert 'maverick' in AGENT_REGISTRY

    def test_registry_entry_has_required_fields(self):
        from trading_cotrader.web.api_agents import AGENT_REGISTRY
        entry = AGENT_REGISTRY['maverick']
        assert entry['category'] == 'domain'
        assert 'booting' in entry['runs_during']
        assert 'monitoring' in entry['runs_during']
        assert 'Consume Scout rankings' in entry['responsibilities']
        assert 'Trade proposal generation' in entry['responsibilities']


class TestMaverickRun:
    """Test run() — position analysis + proposal generation."""

    def test_run_no_container_manager(self):
        """run() with no container_manager returns COMPLETED with skip message."""
        agent = MaverickAgent(container_manager=None)
        result = agent.run({})
        assert result.status == AgentStatus.COMPLETED
        assert "no container_manager" in result.messages[0]

    def test_run_with_positions_and_research(self):
        """run() cross-references positions with research to produce signals."""
        mock_cm = MagicMock()

        # Mock position
        mock_pos = MagicMock()
        mock_pos.delta = Decimal('50')

        # Mock bundle with positions
        mock_bundle = MagicMock()
        mock_bundle.config_name = 'tastytrade'
        mock_bundle.positions.underlyings = ['SPY', 'QQQ']
        mock_bundle.positions.get_by_underlying.side_effect = lambda u: [mock_pos]

        # Mock trades (for duplicate check)
        mock_bundle.trades.get_what_if_trades.return_value = []

        mock_cm.get_all_bundles.return_value = [mock_bundle]

        # Mock research entries
        mock_entry = MagicMock()
        mock_entry.hmm_regime_label = 'R1_LOW_VOL_MR'
        mock_entry.phase_name = 'Accumulation'
        mock_entry.rsi_14 = 45.0
        mock_entry.levels_direction = 'bullish'
        mock_cm.research.get.side_effect = lambda u: mock_entry if u == 'SPY' else None

        agent = MaverickAgent(container_manager=mock_cm)
        context = {}
        result = agent.run(context)

        assert result.status == AgentStatus.COMPLETED
        assert result.data['position_signals'] == 2
        assert len(context['trading_signals']) == 2

        # SPY signal should have research data
        spy_signal = next(s for s in context['trading_signals'] if s['underlying'] == 'SPY')
        assert spy_signal['regime'] == 'R1_LOW_VOL_MR'
        assert spy_signal['phase'] == 'Accumulation'
        assert spy_signal['net_delta'] == 50.0

        # QQQ signal should NOT have research data (returned None)
        qqq_signal = next(s for s in context['trading_signals'] if s['underlying'] == 'QQQ')
        assert 'regime' not in qqq_signal
        assert qqq_signal['net_delta'] == 50.0

    def test_run_no_positions(self):
        """run() with empty bundles produces no signals."""
        mock_cm = MagicMock()
        mock_bundle = MagicMock()
        mock_bundle.positions.underlyings = []
        mock_bundle.trades.get_what_if_trades.return_value = []
        mock_cm.get_all_bundles.return_value = [mock_bundle]

        agent = MaverickAgent(container_manager=mock_cm)
        context = {}
        result = agent.run(context)

        assert result.status == AgentStatus.COMPLETED
        assert result.data['position_signals'] == 0
        assert context['trading_signals'] == []

    def test_run_with_ranking_produces_proposals(self):
        """run() with ranking produces trade proposals."""
        mock_cm = MagicMock()
        mock_bundle = MagicMock()
        mock_bundle.positions.underlyings = []
        mock_bundle.trades.get_what_if_trades.return_value = []
        mock_cm.get_all_bundles.return_value = [mock_bundle]

        agent = MaverickAgent(container_manager=mock_cm)
        context = {
            'ranking': [
                {
                    'ticker': 'SPY',
                    'strategy_name': 'iron_condor',
                    'strategy_type': 'iron_condor',
                    'verdict': 'go',
                    'composite_score': 0.72,
                    'direction': 'neutral',
                    'rationale': 'R1 regime, low vol environment',
                    'risk_notes': [],
                    'trade_spec': {
                        'ticker': 'SPY',
                        'legs': [
                            {'action': 'STO', 'quantity': 1, 'option_type': 'put',
                             'strike': 560.0, 'expiration': '2026-04-17',
                             'strike_label': '1 ATR OTM put', 'days_to_expiry': 39,
                             'atm_iv_at_expiry': 0.18},
                            {'action': 'BTO', 'quantity': 1, 'option_type': 'put',
                             'strike': 555.0, 'expiration': '2026-04-17',
                             'strike_label': 'wing put', 'days_to_expiry': 39,
                             'atm_iv_at_expiry': 0.18},
                            {'action': 'STO', 'quantity': 1, 'option_type': 'call',
                             'strike': 600.0, 'expiration': '2026-04-17',
                             'strike_label': '1 ATR OTM call', 'days_to_expiry': 39,
                             'atm_iv_at_expiry': 0.18},
                            {'action': 'BTO', 'quantity': 1, 'option_type': 'call',
                             'strike': 605.0, 'expiration': '2026-04-17',
                             'strike_label': 'wing call', 'days_to_expiry': 39,
                             'atm_iv_at_expiry': 0.18},
                        ],
                        'profit_target_pct': 0.50,
                        'stop_loss_pct': 2.0,
                        'exit_dte': 7,
                    },
                },
            ],
        }
        result = agent.run(context)

        assert result.status == AgentStatus.COMPLETED
        proposals = context['trade_proposals']
        proposed = [p for p in proposals if p['status'] == 'proposed']
        assert len(proposed) == 1
        assert proposed[0]['ticker'] == 'SPY'
        assert proposed[0]['strategy_name'] == 'iron_condor'
        assert len(proposed[0]['leg_inputs']) == 4
        assert proposed[0]['exit_rules']['profit_target_pct'] == 0.50

    def test_run_filters_no_go(self):
        """run() rejects NO_GO verdicts."""
        mock_cm = MagicMock()
        mock_bundle = MagicMock()
        mock_bundle.positions.underlyings = []
        mock_bundle.trades.get_what_if_trades.return_value = []
        mock_cm.get_all_bundles.return_value = [mock_bundle]

        agent = MaverickAgent(container_manager=mock_cm)
        context = {
            'ranking': [
                {
                    'ticker': 'TSLA', 'strategy_name': 'iron_condor',
                    'strategy_type': 'iron_condor',
                    'verdict': 'no_go', 'composite_score': 0.15,
                    'direction': 'neutral', 'rationale': 'Too volatile',
                    'risk_notes': [], 'trade_spec': {'legs': []},
                },
            ],
        }
        result = agent.run(context)
        proposals = context['trade_proposals']
        assert all(p['status'] == 'rejected' for p in proposals)

    def test_run_filters_low_score(self):
        """run() rejects low scores below threshold."""
        mock_cm = MagicMock()
        mock_bundle = MagicMock()
        mock_bundle.positions.underlyings = []
        mock_bundle.trades.get_what_if_trades.return_value = []
        mock_cm.get_all_bundles.return_value = [mock_bundle]

        agent = MaverickAgent(container_manager=mock_cm)
        context = {
            'ranking': [
                {
                    'ticker': 'GLD', 'strategy_name': 'calendar',
                    'strategy_type': 'calendar',
                    'verdict': 'caution', 'composite_score': 0.20,
                    'direction': 'neutral', 'rationale': 'Low confidence',
                    'risk_notes': [],
                    'trade_spec': {'legs': [
                        {'action': 'STO', 'quantity': 1, 'option_type': 'call',
                         'strike': 200.0, 'expiration': '2026-04-17',
                         'strike_label': 'ATM', 'days_to_expiry': 39,
                         'atm_iv_at_expiry': 0.15},
                    ]},
                },
            ],
        }
        result = agent.run(context)
        proposals = context['trade_proposals']
        rejected = [p for p in proposals if p['status'] == 'rejected']
        assert len(rejected) == 1
        assert 'Score' in rejected[0]['gate_result']

    def test_run_prevents_duplicates(self):
        """run() rejects trades on underlyings with open WhatIf positions."""
        mock_cm = MagicMock()
        mock_bundle = MagicMock()
        mock_bundle.positions.underlyings = []

        # Existing open WhatIf trade on SPY iron condor
        mock_trade = MagicMock()
        mock_trade.underlying = 'SPY'
        mock_trade.strategy_type = 'iron_condor'
        mock_bundle.trades.get_what_if_trades.return_value = [mock_trade]
        mock_cm.get_all_bundles.return_value = [mock_bundle]

        agent = MaverickAgent(container_manager=mock_cm)
        context = {
            'ranking': [
                {
                    'ticker': 'SPY', 'strategy_name': 'iron_condor',
                    'strategy_type': 'iron_condor',
                    'verdict': 'go', 'composite_score': 0.80,
                    'direction': 'neutral', 'rationale': 'Great setup',
                    'risk_notes': [],
                    'trade_spec': {'legs': [
                        {'action': 'STO', 'quantity': 1, 'option_type': 'put',
                         'strike': 560.0, 'expiration': '2026-04-17',
                         'strike_label': 'OTM put', 'days_to_expiry': 39,
                         'atm_iv_at_expiry': 0.18},
                    ]},
                },
            ],
        }
        result = agent.run(context)
        proposals = context['trade_proposals']
        rejected = [p for p in proposals if p['status'] == 'rejected']
        assert len(rejected) == 1
        assert 'Duplicate' in rejected[0]['gate_result']


class TestTradeSpecToLegInputs:
    """Test the TradeSpec → LegInput converter."""

    def test_iron_condor_conversion(self):
        """4-leg iron condor converts to correct DXLink streamer symbols."""
        spec = {
            'legs': [
                {'action': 'STO', 'quantity': 1, 'option_type': 'put',
                 'strike': 560.0, 'expiration': '2026-04-17',
                 'strike_label': 'OTM put', 'days_to_expiry': 39, 'atm_iv_at_expiry': 0.18},
                {'action': 'BTO', 'quantity': 1, 'option_type': 'put',
                 'strike': 555.0, 'expiration': '2026-04-17',
                 'strike_label': 'wing put', 'days_to_expiry': 39, 'atm_iv_at_expiry': 0.18},
                {'action': 'STO', 'quantity': 1, 'option_type': 'call',
                 'strike': 600.0, 'expiration': '2026-04-17',
                 'strike_label': 'OTM call', 'days_to_expiry': 39, 'atm_iv_at_expiry': 0.18},
                {'action': 'BTO', 'quantity': 1, 'option_type': 'call',
                 'strike': 605.0, 'expiration': '2026-04-17',
                 'strike_label': 'wing call', 'days_to_expiry': 39, 'atm_iv_at_expiry': 0.18},
            ]
        }
        legs = _trade_spec_to_leg_inputs('SPY', spec)

        assert len(legs) == 4
        assert legs[0]['streamer_symbol'] == '.SPY260417P560'
        assert legs[0]['quantity'] == -1  # STO = sell
        assert legs[1]['streamer_symbol'] == '.SPY260417P555'
        assert legs[1]['quantity'] == 1   # BTO = buy
        assert legs[2]['streamer_symbol'] == '.SPY260417C600'
        assert legs[2]['quantity'] == -1  # STO = sell
        assert legs[3]['streamer_symbol'] == '.SPY260417C605'
        assert legs[3]['quantity'] == 1   # BTO = buy


class TestMaverickEngineWiring:
    """Test Maverick is wired into the workflow engine."""

    def test_engine_has_maverick_agent(self):
        from trading_cotrader.agents.domain import maverick as maverick_mod
        assert hasattr(maverick_mod, 'MaverickAgent')

    def test_engine_instantiates_maverick_with_container_manager(self):
        import inspect
        from trading_cotrader.agents.workflow.engine import WorkflowEngine
        source = inspect.getsource(WorkflowEngine.__init__)
        assert 'maverick' in source
        assert 'MaverickAgent' in source
        assert 'container_manager' in source
