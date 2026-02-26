"""
Tests for MaverickAgent — domain orchestrator cross-referencing Scout + Steward.

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
10. Engine has maverick agent
11. Engine instantiates maverick with container_manager
"""

import pytest
from unittest.mock import MagicMock, PropertyMock
from decimal import Decimal

from trading_cotrader.agents.domain.maverick import MaverickAgent
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
        assert 'Trading orchestration' in entry['responsibilities']
        assert 'Scout/Steward cross-reference' in entry['responsibilities']


class TestMaverickRun:
    """Test run() — cross-referencing Scout + Steward."""

    def test_run_no_container_manager(self):
        """run() with no container_manager returns COMPLETED with skip message."""
        agent = MaverickAgent(container_manager=None)
        result = agent.run({})
        assert result.status == AgentStatus.COMPLETED
        assert "no container_manager" in result.messages[0]

    def test_run_with_positions_and_research(self):
        """run() cross-references positions with research to produce signals."""
        # Mock container manager
        mock_cm = MagicMock()

        # Mock position
        mock_pos = MagicMock()
        mock_pos.delta = Decimal('50')

        # Mock bundle with positions
        mock_bundle = MagicMock()
        mock_bundle.config_name = 'tastytrade'
        mock_bundle.positions.underlyings = ['SPY', 'QQQ']
        mock_bundle.positions.get_by_underlying.side_effect = lambda u: [mock_pos] if u == 'SPY' else [mock_pos]

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
        assert result.data['signal_count'] == 2
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
        mock_cm.get_all_bundles.return_value = [mock_bundle]

        agent = MaverickAgent(container_manager=mock_cm)
        context = {}
        result = agent.run(context)

        assert result.status == AgentStatus.COMPLETED
        assert result.data['signal_count'] == 0
        assert context['trading_signals'] == []


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
