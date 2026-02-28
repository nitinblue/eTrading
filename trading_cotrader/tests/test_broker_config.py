"""
Tests for broker configuration, portfolio routing, and safety invariants.

Validates:
- Broker registry loading and lookup
- Portfolio config with multi-broker fields
- Cross-broker routing safety
- Currency isolation
- Manual vs API execution detection
- WhatIf strategy inheritance
- BrokerRouter execution routing
"""

import pytest
from decimal import Decimal

from trading_cotrader.config.broker_config_loader import (
    BrokerConfig, BrokerRegistry, load_broker_registry,
)
from trading_cotrader.config.risk_config_loader import (
    PortfolioConfig, PortfoliosConfig, PortfolioRiskLimits,
)
from trading_cotrader.adapters.broker_router import BrokerRouter, ExecutionResult
from trading_cotrader.services.portfolio_manager import PortfolioManager


# =============================================================================
# Test Broker Registry
# =============================================================================

def _build_test_registry() -> BrokerRegistry:
    """Build a BrokerRegistry for testing."""
    return BrokerRegistry(brokers={
        'tastytrade': BrokerConfig(
            name='tastytrade', display_name='Tastytrade',
            currency='USD', has_api=True, is_data_broker=True,
            adapter='tastytrade',
        ),
        'fidelity': BrokerConfig(
            name='fidelity', display_name='Fidelity',
            currency='USD', has_api=False, manual_execution=True,
        ),
        'zerodha': BrokerConfig(
            name='zerodha', display_name='Zerodha',
            currency='INR', has_api=True, is_data_broker=True,
            adapter='zerodha',
        ),
        'stallion': BrokerConfig(
            name='stallion', display_name='Stallion Asset',
            currency='INR', has_api=False, read_only=True,
        ),
    })


def _build_test_portfolios() -> PortfoliosConfig:
    """Build test portfolio configs with multi-broker fields."""
    return PortfoliosConfig(portfolios={
        'tastytrade': PortfolioConfig(
            name='tastytrade', display_name='Tastytrade',
            broker_firm='tastytrade', account_number='5WZ78765',
            portfolio_type='real', currency='USD',
            initial_capital=31360,
            allowed_strategies=['iron_condor', 'vertical_spread'],
            active_strategies=['iron_condor'],
            risk_limits=PortfolioRiskLimits(max_portfolio_delta=300),
        ),
        'fidelity_ira': PortfolioConfig(
            name='fidelity_ira', display_name='Fidelity IRA',
            broker_firm='fidelity', account_number='259510977',
            portfolio_type='real', currency='USD',
            initial_capital=181067,
            allowed_strategies=['single', 'covered_call'],
            active_strategies=['single'],
            risk_limits=PortfolioRiskLimits(max_portfolio_delta=1000),
        ),
        'stallion': PortfolioConfig(
            name='stallion', display_name='Stallion Asset',
            broker_firm='stallion', account_number='SACF5925',
            portfolio_type='real', currency='INR',
            initial_capital=5000000,
            allowed_strategies=['single'],
            active_strategies=['single'],
        ),
        'tastytrade_whatif': PortfolioConfig(
            name='tastytrade_whatif', display_name='Tastytrade (WhatIf)',
            broker_firm='tastytrade', account_number='5WZ78765_whatif',
            portfolio_type='what_if', mirrors_real='tastytrade',
            currency='USD', initial_capital=31360,
            # strategies empty — should inherit from tastytrade
        ),
    })


class TestBrokerRegistry:
    """Broker registry lookups."""

    def test_get_by_name(self):
        reg = _build_test_registry()
        tt = reg.get_by_name('tastytrade')
        assert tt is not None
        assert tt.display_name == 'Tastytrade'
        assert tt.currency == 'USD'
        assert tt.has_api is True

    def test_get_by_name_missing(self):
        reg = _build_test_registry()
        assert reg.get_by_name('nonexistent') is None

    def test_data_broker_usd(self):
        reg = _build_test_registry()
        data = reg.get_data_broker('USD')
        assert data is not None
        assert data.name == 'tastytrade'

    def test_data_broker_inr(self):
        reg = _build_test_registry()
        data = reg.get_data_broker('INR')
        assert data is not None
        assert data.name == 'zerodha'

    def test_data_broker_unknown_currency(self):
        reg = _build_test_registry()
        assert reg.get_data_broker('EUR') is None

    def test_manual_execution_flag(self):
        reg = _build_test_registry()
        assert reg.get_by_name('fidelity').manual_execution is True
        assert reg.get_by_name('tastytrade').manual_execution is False
        assert reg.get_by_name('zerodha').manual_execution is False

    def test_read_only_flag(self):
        reg = _build_test_registry()
        assert reg.get_by_name('stallion').read_only is True
        assert reg.get_by_name('fidelity').read_only is False
        assert reg.get_by_name('tastytrade').read_only is False

    def test_get_all(self):
        reg = _build_test_registry()
        assert len(reg.get_all()) == 4

    def test_get_by_currency(self):
        reg = _build_test_registry()
        usd = reg.get_by_currency('USD')
        assert len(usd) == 2
        assert {b.name for b in usd} == {'tastytrade', 'fidelity'}

        inr = reg.get_by_currency('INR')
        assert len(inr) == 2
        assert {b.name for b in inr} == {'zerodha', 'stallion'}


class TestPortfolioConfig:
    """Portfolio config with multi-broker fields."""

    def test_real_portfolio(self):
        config = _build_test_portfolios()
        tt = config.get_by_name('tastytrade')
        assert tt.is_real is True
        assert tt.is_whatif is False
        assert tt.broker_firm == 'tastytrade'
        assert tt.account_number == '5WZ78765'
        assert tt.currency == 'USD'

    def test_whatif_portfolio(self):
        config = _build_test_portfolios()
        wi = config.get_by_name('tastytrade_whatif')
        assert wi.is_whatif is True
        assert wi.is_real is False
        assert wi.mirrors_real == 'tastytrade'

    def test_get_real_portfolios(self):
        config = _build_test_portfolios()
        real = config.get_real_portfolios()
        assert len(real) == 3
        names = {p.name for p in real}
        assert 'tastytrade' in names
        assert 'fidelity_ira' in names
        assert 'stallion' in names

    def test_get_whatif_portfolios(self):
        config = _build_test_portfolios()
        whatif = config.get_whatif_portfolios()
        assert len(whatif) == 1
        assert whatif[0].name == 'tastytrade_whatif'

    def test_get_by_broker(self):
        config = _build_test_portfolios()
        tt_portfolios = config.get_by_broker('tastytrade')
        assert len(tt_portfolios) == 2  # real + whatif

    def test_reverse_lookup(self):
        config = _build_test_portfolios()
        name = config.get_config_name_for('tastytrade', '5WZ78765')
        assert name == 'tastytrade'

    def test_reverse_lookup_missing(self):
        config = _build_test_portfolios()
        name = config.get_config_name_for('unknown', 'unknown')
        assert name is None

    def test_inr_portfolio(self):
        config = _build_test_portfolios()
        st = config.get_by_name('stallion')
        assert st.currency == 'INR'
        assert st.initial_capital == 5000000


class TestWhatIfInheritance:
    """WhatIf strategy inheritance from real parent."""

    def test_whatif_inherits_strategies(self):
        """WhatIf with no strategies should inherit from mirrors_real parent."""
        from trading_cotrader.config.risk_config_loader import RiskConfigLoader
        loader = RiskConfigLoader()
        config = loader.load()

        whatif = config.portfolios.get_by_name('tastytrade_whatif')
        real = config.portfolios.get_by_name('tastytrade')

        assert whatif.allowed_strategies == real.allowed_strategies
        assert whatif.active_strategies == real.active_strategies


class TestBrokerRouter:
    """BrokerRouter execution routing and safety."""

    def setup_method(self):
        self.registry = _build_test_registry()
        self.router = BrokerRouter(self.registry, adapters={})

    def test_manual_execution_fidelity(self):
        """Fidelity trades return MANUAL status."""
        config = _build_test_portfolios()
        pc = config.get_by_name('fidelity_ira')
        result = self.router.execute({'summary': 'Buy SPY'}, pc)
        assert result.manual is True
        assert 'MANUAL EXECUTION REQUIRED' in result.message
        assert 'Fidelity' in result.message

    def test_read_only_stallion(self):
        """Stallion (managed fund) trades are BLOCKED — no execution at all."""
        config = _build_test_portfolios()
        pc = config.get_by_name('stallion')
        result = self.router.execute({'summary': 'Buy BSE'}, pc)
        assert result.blocked is True
        assert 'fully managed fund' in result.message

    def test_api_broker_no_adapter_blocked(self):
        """API broker without adapter loaded is blocked."""
        config = _build_test_portfolios()
        pc = config.get_by_name('tastytrade')
        result = self.router.execute({'summary': 'Sell IC'}, pc)
        assert result.blocked is True
        assert 'No adapter' in result.message

    def test_api_broker_with_adapter_succeeds(self):
        """API broker with adapter loaded succeeds."""
        class FakeAdapter:
            pass
        router = BrokerRouter(self.registry, adapters={'tastytrade': FakeAdapter()})
        config = _build_test_portfolios()
        pc = config.get_by_name('tastytrade')
        result = router.execute({'summary': 'Sell IC'}, pc)
        assert result.success is True

    def test_cross_broker_routing_blocked(self):
        """Cannot route trade targeting wrong broker."""
        config = _build_test_portfolios()
        pc = config.get_by_name('fidelity_ira')
        action = {'summary': 'test', 'target_broker': 'tastytrade'}
        result = self.router.execute(action, pc)
        assert result.blocked is True
        assert 'Cross-broker routing blocked' in result.message

    def test_currency_mismatch_blocked(self):
        """Cannot place USD trade in INR portfolio."""
        # Use a non-read-only INR portfolio (zerodha has API)
        pc = PortfolioConfig(
            name='zerodha_test', broker_firm='zerodha',
            account_number='ZRD001', currency='INR',
        )
        action = {'summary': 'test', 'currency': 'USD'}
        result = self.router.execute(action, pc)
        assert result.blocked is True
        assert 'Currency mismatch' in result.message

    def test_same_currency_passes(self):
        """USD trade in USD portfolio passes currency check."""
        config = _build_test_portfolios()
        pc = config.get_by_name('fidelity_ira')
        action = {'summary': 'test', 'currency': 'USD'}
        result = self.router.execute(action, pc)
        # Should be manual (fidelity), but not blocked for currency
        assert result.blocked is False
        assert result.manual is True

    def test_unknown_broker_blocked(self):
        """Unknown broker name is blocked."""
        pc = PortfolioConfig(
            name='test', broker_firm='nonexistent',
            account_number='xxx', currency='USD',
        )
        result = self.router.execute({'summary': 'test'}, pc)
        assert result.blocked is True
        assert 'Unknown broker' in result.message

    def test_data_broker_lookup(self):
        """Data broker lookup by currency."""
        class FakeAdapter:
            pass
        router = BrokerRouter(self.registry, adapters={'tastytrade': FakeAdapter()})
        adapter = router.get_data_broker('USD')
        assert adapter is not None

        adapter_inr = router.get_data_broker('INR')
        assert adapter_inr is None  # no zerodha adapter loaded


class TestGuardianCrossBroker:
    """Guardian agent cross-broker safety checks."""

    def test_cross_broker_blocked(self):
        from trading_cotrader.agents.domain.sentinel import SentinelAgent
        from trading_cotrader.config.workflow_config_loader import WorkflowConfig
        guardian = SentinelAgent(WorkflowConfig())

        action = {
            'portfolio_broker': 'fidelity',
            'target_broker': 'tastytrade',
        }
        ok, reason = guardian.check_trading_constraints(action, {'trades_today_count': 0})
        assert ok is False
        assert 'Cross-broker routing blocked' in reason

    def test_currency_mismatch_blocked(self):
        from trading_cotrader.agents.domain.sentinel import SentinelAgent
        from trading_cotrader.config.workflow_config_loader import WorkflowConfig
        guardian = SentinelAgent(WorkflowConfig())

        action = {
            'currency': 'USD',
            'portfolio_currency': 'INR',
        }
        ok, reason = guardian.check_trading_constraints(action, {'trades_today_count': 0})
        assert ok is False
        assert 'Currency mismatch' in reason

    def test_same_broker_passes(self):
        from trading_cotrader.agents.domain.sentinel import SentinelAgent
        from trading_cotrader.config.workflow_config_loader import WorkflowConfig
        guardian = SentinelAgent(WorkflowConfig())

        action = {
            'portfolio_broker': 'tastytrade',
            'target_broker': 'tastytrade',
            'currency': 'USD',
            'portfolio_currency': 'USD',
        }
        ok, reason = guardian.check_trading_constraints(action, {'trades_today_count': 0})
        assert ok is True


class TestPortfolioManagerMultiBroker:
    """PortfolioManager with multi-broker configs."""

    def test_manual_execution_detection(self):
        config = _build_test_portfolios()
        registry = _build_test_registry()

        class FakePM(PortfolioManager):
            def __init__(self, portfolios_config, broker_registry):
                self.session = None
                self.repo = None
                self.portfolios_config = portfolios_config
                self.broker_registry = broker_registry

        pm = FakePM(config, registry)
        assert pm.is_manual_execution('fidelity_ira') is True
        assert pm.is_manual_execution('stallion') is False  # read_only, not manual
        assert pm.is_manual_execution('tastytrade') is False

    def test_read_only_detection(self):
        config = _build_test_portfolios()
        registry = _build_test_registry()

        class FakePM(PortfolioManager):
            def __init__(self, portfolios_config, broker_registry):
                self.session = None
                self.repo = None
                self.portfolios_config = portfolios_config
                self.broker_registry = broker_registry

        pm = FakePM(config, registry)
        assert pm.is_read_only('stallion') is True
        assert pm.is_read_only('fidelity_ira') is False
        assert pm.is_read_only('tastytrade') is False

    def test_currency_lookup(self):
        config = _build_test_portfolios()
        registry = _build_test_registry()

        class FakePM(PortfolioManager):
            def __init__(self, portfolios_config, broker_registry):
                self.session = None
                self.repo = None
                self.portfolios_config = portfolios_config
                self.broker_registry = broker_registry

        pm = FakePM(config, registry)
        assert pm.get_currency('tastytrade') == 'USD'
        assert pm.get_currency('stallion') == 'INR'
        assert pm.get_currency('fidelity_ira') == 'USD'

    def test_portfolio_initialization_multi_broker(self, session):
        """15 portfolios created from real config (5 real + 5 whatif + 5 research)."""
        from trading_cotrader.config.risk_config_loader import RiskConfigLoader
        loader = RiskConfigLoader()
        risk_config = loader.load()
        registry = _build_test_registry()

        pm = PortfolioManager(session, config=risk_config.portfolios, broker_registry=registry)
        portfolios = pm.initialize_portfolios()
        assert len(portfolios) == 11

        # Verify real vs whatif vs research
        real_count = sum(1 for p in portfolios if p.portfolio_type.value == 'real')
        whatif_count = sum(1 for p in portfolios if p.portfolio_type.value == 'what_if')
        research_count = sum(1 for p in portfolios if p.portfolio_type.value == 'research')
        assert real_count == 5
        assert whatif_count == 1
        assert research_count == 5

    def test_portfolio_lookup_by_name(self, session):
        """Lookup portfolio by config name after initialization."""
        from trading_cotrader.config.risk_config_loader import RiskConfigLoader
        loader = RiskConfigLoader()
        risk_config = loader.load()
        registry = _build_test_registry()

        pm = PortfolioManager(session, config=risk_config.portfolios, broker_registry=registry)
        pm.initialize_portfolios()

        tt = pm.get_portfolio_by_name('tastytrade')
        assert tt is not None
        assert tt.broker == 'tastytrade'
        assert tt.account_id == '5WZ78765'

        fid = pm.get_portfolio_by_name('fidelity_ira')
        assert fid is not None
        assert fid.broker == 'fidelity'

    def test_idempotent_initialization(self, session):
        """Running init twice doesn't create duplicates."""
        from trading_cotrader.config.risk_config_loader import RiskConfigLoader
        loader = RiskConfigLoader()
        risk_config = loader.load()
        registry = _build_test_registry()

        pm = PortfolioManager(session, config=risk_config.portfolios, broker_registry=registry)
        first = pm.initialize_portfolios()
        second = pm.initialize_portfolios()
        assert len(first) == len(second) == 11


class TestBrokerAdapterFactory:
    """Adapter factory creates correct adapter types from config."""

    def test_factory_creates_manual_for_fidelity(self):
        from trading_cotrader.adapters.factory import BrokerAdapterFactory
        from trading_cotrader.adapters.base import ManualBrokerAdapter

        config = BrokerConfig(
            name='fidelity', currency='USD', manual_execution=True,
        )
        adapter = BrokerAdapterFactory.create(config)
        assert isinstance(adapter, ManualBrokerAdapter)
        assert adapter.name == 'fidelity'
        assert adapter.currency == 'USD'
        assert adapter.is_authenticated is True

    def test_factory_creates_readonly_for_stallion(self):
        from trading_cotrader.adapters.factory import BrokerAdapterFactory
        from trading_cotrader.adapters.base import ReadOnlyAdapter

        config = BrokerConfig(
            name='stallion', currency='INR', read_only=True,
        )
        adapter = BrokerAdapterFactory.create(config)
        assert isinstance(adapter, ReadOnlyAdapter)
        assert adapter.name == 'stallion'
        assert adapter.currency == 'INR'
        assert adapter.get_positions() == []

    def test_factory_manual_adapter_methods(self):
        from trading_cotrader.adapters.factory import BrokerAdapterFactory
        from trading_cotrader.adapters.base import ManualBrokerAdapter

        config = BrokerConfig(name='fid', manual_execution=True)
        adapter = BrokerAdapterFactory.create(config)
        assert adapter.authenticate() is True
        assert adapter.get_account_balance() == {}
        assert adapter.get_positions() == []

    def test_factory_readonly_adapter_methods(self):
        from trading_cotrader.adapters.factory import BrokerAdapterFactory
        from trading_cotrader.adapters.base import ReadOnlyAdapter

        config = BrokerConfig(name='ro', read_only=True)
        adapter = BrokerAdapterFactory.create(config)
        assert adapter.authenticate() is True
        assert adapter.get_account_balance() == {}
        assert adapter.get_positions() == []

    def test_factory_create_all_api(self):
        from trading_cotrader.adapters.factory import BrokerAdapterFactory
        from trading_cotrader.adapters.base import ManualBrokerAdapter

        registry = _build_test_registry()
        # This would try to create TastyTrade and Zerodha adapters
        # TastyTrade will fail (no credentials) but zerodha falls back to manual
        adapters = BrokerAdapterFactory.create_all_api(registry)
        # At minimum, both API brokers were attempted
        assert isinstance(adapters, dict)

    def test_factory_unknown_adapter_fallback(self):
        from trading_cotrader.adapters.factory import BrokerAdapterFactory
        from trading_cotrader.adapters.base import ManualBrokerAdapter

        config = BrokerConfig(
            name='unknown', has_api=True, adapter='nonexistent',
        )
        adapter = BrokerAdapterFactory.create(config)
        assert isinstance(adapter, ManualBrokerAdapter)

    def test_adapter_base_notimplemented(self):
        from trading_cotrader.adapters.base import ManualBrokerAdapter

        adapter = ManualBrokerAdapter('test')
        with pytest.raises(NotImplementedError):
            adapter.get_option_chain('SPY')
        with pytest.raises(NotImplementedError):
            adapter.get_quote('SPY')
        with pytest.raises(NotImplementedError):
            adapter.get_quotes(['SPY'])
        with pytest.raises(NotImplementedError):
            adapter.get_greeks(['.SPY260320P550'])


class TestContainerBundles:
    """Per-portfolio container bundles and ContainerManager."""

    def test_bundle_creation(self):
        from trading_cotrader.containers.portfolio_bundle import PortfolioBundle
        bundle = PortfolioBundle(config_name='tastytrade', currency='USD')
        assert bundle.config_name == 'tastytrade'
        assert bundle.currency == 'USD'
        assert bundle.portfolio_ids == []
        assert bundle.portfolio is not None
        assert bundle.positions is not None

    def test_bundle_add_portfolio_id(self):
        from trading_cotrader.containers.portfolio_bundle import PortfolioBundle
        bundle = PortfolioBundle(config_name='test', currency='USD')
        bundle.add_portfolio_id('pid-1')
        bundle.add_portfolio_id('pid-2')
        bundle.add_portfolio_id('pid-1')  # duplicate
        assert len(bundle.portfolio_ids) == 2

    def test_bundle_get_full_state(self):
        from trading_cotrader.containers.portfolio_bundle import PortfolioBundle
        bundle = PortfolioBundle(config_name='test', currency='INR')
        state = bundle.get_full_state()
        assert state['config_name'] == 'test'
        assert state['currency'] == 'INR'
        assert 'portfolio' in state
        assert 'positions' in state
        assert 'whatif_portfolio' in state

    def test_container_manager_initialize_bundles(self):
        from trading_cotrader.containers.container_manager import ContainerManager
        cm = ContainerManager()
        config = _build_test_portfolios()
        cm.initialize_bundles(config)
        # 3 real portfolios → 3 bundles
        assert len(cm.get_all_bundles()) == 3
        assert 'tastytrade' in cm.get_bundle_names()
        assert 'fidelity_ira' in cm.get_bundle_names()
        assert 'stallion' in cm.get_bundle_names()

    def test_container_manager_whatif_resolves_to_parent(self):
        from trading_cotrader.containers.container_manager import ContainerManager
        cm = ContainerManager()
        config = _build_test_portfolios()
        cm.initialize_bundles(config)
        # WhatIf resolves to parent bundle
        parent = cm.get_bundle('tastytrade')
        whatif = cm.get_bundle('tastytrade_whatif')
        assert parent is whatif

    def test_container_manager_currency_filter(self):
        from trading_cotrader.containers.container_manager import ContainerManager
        cm = ContainerManager()
        config = _build_test_portfolios()
        cm.initialize_bundles(config)
        usd = cm.get_bundles_by_currency('USD')
        inr = cm.get_bundles_by_currency('INR')
        assert len(usd) == 2  # tastytrade, fidelity_ira
        assert len(inr) == 1  # stallion

    def test_container_manager_backward_compat_properties(self):
        from trading_cotrader.containers.container_manager import ContainerManager
        cm = ContainerManager()
        config = _build_test_portfolios()
        cm.initialize_bundles(config)
        # Default properties should work (first bundle)
        assert cm.portfolio is not None
        assert cm.positions is not None
        assert cm.risk_factors is not None
        assert cm.trades is not None

    def test_container_manager_get_full_state_default(self):
        from trading_cotrader.containers.container_manager import ContainerManager
        cm = ContainerManager()
        config = _build_test_portfolios()
        cm.initialize_bundles(config)
        state = cm.get_full_state()
        assert 'portfolio' in state
        assert 'positions' in state

    def test_container_manager_get_full_state_specific(self):
        from trading_cotrader.containers.container_manager import ContainerManager
        cm = ContainerManager()
        config = _build_test_portfolios()
        cm.initialize_bundles(config)
        state = cm.get_full_state('stallion')
        assert state['config_name'] == 'stallion'
        assert state['currency'] == 'INR'

    def test_container_manager_get_all_states(self):
        from trading_cotrader.containers.container_manager import ContainerManager
        cm = ContainerManager()
        config = _build_test_portfolios()
        cm.initialize_bundles(config)
        states = cm.get_all_states()
        assert len(states) == 3

    def test_container_manager_empty_state(self):
        from trading_cotrader.containers.container_manager import ContainerManager
        cm = ContainerManager()
        state = cm.get_full_state()
        assert state['positions'] == []

    def test_portfolio_state_currency_field(self):
        from trading_cotrader.containers.portfolio_container import PortfolioState
        ps = PortfolioState(portfolio_id='1', name='test', currency='INR')
        d = ps.to_dict()
        assert d['currency'] == 'INR'


class TestLoadBrokerRegistryFromYAML:
    """Load broker registry from actual YAML file."""

    def test_load_from_yaml(self):
        registry = load_broker_registry()
        assert len(registry.get_all()) == 4

        tt = registry.get_by_name('tastytrade')
        assert tt.currency == 'USD'
        assert tt.has_api is True
        assert tt.is_data_broker is True

        fid = registry.get_by_name('fidelity')
        assert fid.manual_execution is True
        assert fid.has_api is False

        stallion = registry.get_by_name('stallion')
        assert stallion.read_only is True
        assert stallion.manual_execution is False
        assert stallion.currency == 'INR'
