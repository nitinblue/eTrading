"""
Risk Configuration Loader

Loads risk parameters from YAML configuration file.
Provides typed access to all risk settings.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path
from decimal import Decimal
import yaml
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Data Classes
# =============================================================================

@dataclass
class VaRConfig:
    """VaR configuration"""
    confidence_level: float = 0.95
    horizon_days: int = 1
    max_var_percent: float = 3.0
    warning_threshold: float = 0.8


@dataclass
class GreeksLimitsConfig:
    """Greeks limits configuration"""
    max_portfolio_delta: float = 100
    max_portfolio_gamma: float = 50
    max_portfolio_theta_percent: float = 0.1
    max_portfolio_vega_percent: float = 1.0


@dataclass
class DrawdownConfig:
    """Drawdown limits"""
    max_drawdown_percent: float = 15
    daily_loss_limit_percent: float = 3


@dataclass
class ConcentrationLimitConfig:
    """Single concentration limit"""
    max_percent: float
    warning_percent: float


@dataclass
class ConcentrationConfig:
    """All concentration limits"""
    single_underlying: ConcentrationLimitConfig = field(default_factory=lambda: ConcentrationLimitConfig(20.0, 15.0))
    strategy_type: ConcentrationLimitConfig = field(default_factory=lambda: ConcentrationLimitConfig(40.0, 30.0))
    direction: ConcentrationLimitConfig = field(default_factory=lambda: ConcentrationLimitConfig(60.0, 50.0))
    expiration: ConcentrationLimitConfig = field(default_factory=lambda: ConcentrationLimitConfig(50.0, 40.0))
    sector: ConcentrationLimitConfig = field(default_factory=lambda: ConcentrationLimitConfig(30.0, 25.0))


@dataclass
class ExitRule:
    """Single exit rule"""
    name: str
    enabled: bool = True
    priority: int = 1
    
    # Rule parameters (only one set applies per rule type)
    target_percent: Optional[float] = None      # For profit targets
    max_loss_percent: Optional[float] = None    # For stop losses
    days_to_expiry: Optional[int] = None        # For time-based
    max_delta: Optional[float] = None           # For delta-based
    applies_to: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass
class ExitRulesConfig:
    """All exit rules"""
    profit_targets: List[ExitRule] = field(default_factory=list)
    stop_losses: List[ExitRule] = field(default_factory=list)
    time_based: List[ExitRule] = field(default_factory=list)
    delta_based: List[ExitRule] = field(default_factory=list)
    combined: List[ExitRule] = field(default_factory=list)
    
    def get_active_rules(self) -> List[ExitRule]:
        """Get all enabled rules, sorted by priority."""
        all_rules = (
            self.profit_targets + 
            self.stop_losses + 
            self.time_based + 
            self.delta_based + 
            self.combined
        )
        enabled = [r for r in all_rules if r.enabled]
        return sorted(enabled, key=lambda r: r.priority)


@dataclass
class WatchedUnderlying:
    """Underlying to track"""
    symbol: str
    description: str = ""
    sector: str = ""
    typical_strategies: List[str] = field(default_factory=list)


@dataclass
class UnderlyingsConfig:
    """Watched underlyings"""
    core: List[WatchedUnderlying] = field(default_factory=list)
    stocks: List[WatchedUnderlying] = field(default_factory=list)
    custom: List[WatchedUnderlying] = field(default_factory=list)
    
    def all_symbols(self) -> List[str]:
        """Get all watched symbols."""
        all_underlyings = self.core + self.stocks + self.custom
        return [u.symbol for u in all_underlyings]
    
    def get_by_symbol(self, symbol: str) -> Optional[WatchedUnderlying]:
        """Get underlying config by symbol."""
        for u in self.core + self.stocks + self.custom:
            if u.symbol == symbol:
                return u
        return None


@dataclass
class ExitRuleProfile:
    """Exit rule profile (conservative/balanced/aggressive)"""
    name: str = ""
    profit_target_pct: float = 50
    stop_loss_multiplier: float = 1.0
    roll_dte: int = 21
    close_dte: int = 7


@dataclass
class PortfolioRiskLimits:
    """Risk limits for a single portfolio tier"""
    max_portfolio_delta: float = 500
    max_positions: int = 10
    max_single_position_pct: float = 10
    max_single_trade_risk_pct: float = 5
    max_total_risk_pct: float = 25
    min_cash_reserve_pct: float = 10
    max_concentration_pct: float = 20


@dataclass
class PortfolioConfig:
    """Configuration for a single portfolio tier"""
    name: str                        # internal key (e.g. "core_holdings")
    display_name: str = ""
    description: str = ""
    capital_allocation_pct: float = 0
    initial_capital: float = 0
    target_annual_return_pct: float = 0
    exit_rule_profile: str = "balanced"
    tags: List[str] = field(default_factory=list)
    allowed_strategies: List[str] = field(default_factory=list)
    active_strategies: List[str] = field(default_factory=list)  # subset of allowed; empty = all allowed
    risk_limits: PortfolioRiskLimits = field(default_factory=PortfolioRiskLimits)
    preferred_underlyings: List[str] = field(default_factory=list)
    requires_rationale: bool = False
    requires_exit_commentary: bool = False

    def get_active_strategies(self) -> List[str]:
        """Get active strategies, falling back to allowed_strategies if not set."""
        return self.active_strategies if self.active_strategies else self.allowed_strategies


@dataclass
class PortfoliosConfig:
    """Container for all portfolio configurations"""
    portfolios: Dict[str, PortfolioConfig] = field(default_factory=dict)

    def get_by_name(self, name: str) -> Optional[PortfolioConfig]:
        """Get portfolio config by internal name."""
        return self.portfolios.get(name)

    def get_all(self) -> List[PortfolioConfig]:
        """Get all portfolio configs."""
        return list(self.portfolios.values())

    def total_allocation_pct(self) -> float:
        """Sum of all portfolio allocations."""
        return sum(p.capital_allocation_pct for p in self.portfolios.values())

    def validate_allocations(self) -> bool:
        """Check that allocations sum to <= 100%."""
        return self.total_allocation_pct() <= 100.0


@dataclass
class LiquidityThreshold:
    """Liquidity thresholds for a single context (entry or adjustment)"""
    min_open_interest: int = 100
    max_bid_ask_spread_pct: float = 5.0
    min_daily_volume: int = 500


@dataclass
class LiquidityThresholds:
    """Entry and adjustment liquidity thresholds"""
    entry: LiquidityThreshold = field(default_factory=LiquidityThreshold)
    adjustment: LiquidityThreshold = field(default_factory=lambda: LiquidityThreshold(
        min_open_interest=500, max_bid_ask_spread_pct=3.0, min_daily_volume=1000
    ))


@dataclass
class IVConfig:
    """IV settings"""
    high_iv_threshold: float = 50
    very_high_iv_threshold: float = 70
    low_iv_threshold: float = 20
    iv_lookback_days: int = 252


@dataclass
class EntryFilters:
    """Technical entry filter criteria for a strategy."""
    rsi_range: Optional[List[float]] = None       # [min, max] RSI for entry
    directional_regime: Optional[List[str]] = None  # allowed regimes: "U", "F", "D"
    volatility_regime: Optional[List[str]] = None   # allowed: "LOW", "NORMAL", "HIGH"
    min_atr_percent: Optional[float] = None
    max_atr_percent: Optional[float] = None
    min_iv_percentile: Optional[float] = None
    max_iv_percentile: Optional[float] = None
    min_pct_from_high: Optional[float] = None     # for LEAPS: min correction depth
    max_pct_from_high: Optional[float] = None


@dataclass
class StrategyRule:
    """Strategy selection rule"""
    name: str
    min_iv_rank: Optional[float] = None
    max_iv_rank: Optional[float] = None
    preferred_iv_rank: Optional[float] = None
    market_outlook: List[str] = field(default_factory=list)
    dte_range: List[int] = field(default_factory=lambda: [30, 45])
    requires: Optional[str] = None
    entry_filters: Optional[EntryFilters] = None


@dataclass
class MarginConfig:
    """Margin settings"""
    min_buying_power_reserve: float = 20
    margin_warning_percent: float = 70
    margin_critical_percent: float = 85
    max_single_trade_margin_percent: float = 10


@dataclass
class RiskConfig:
    """
    Complete risk configuration.
    
    This is the main configuration object used throughout the application.
    """
    # Risk limits
    var: VaRConfig = field(default_factory=VaRConfig)
    greeks_limits: GreeksLimitsConfig = field(default_factory=GreeksLimitsConfig)
    drawdown: DrawdownConfig = field(default_factory=DrawdownConfig)
    concentration: ConcentrationConfig = field(default_factory=ConcentrationConfig)
    
    # Trading rules
    exit_rules: ExitRulesConfig = field(default_factory=ExitRulesConfig)
    
    # Underlyings
    underlyings: UnderlyingsConfig = field(default_factory=UnderlyingsConfig)
    
    # IV settings
    iv: IVConfig = field(default_factory=IVConfig)

    # Liquidity thresholds
    liquidity: LiquidityThresholds = field(default_factory=LiquidityThresholds)

    # Strategy rules
    strategy_rules: Dict[str, StrategyRule] = field(default_factory=dict)
    
    # Margin
    margin: MarginConfig = field(default_factory=MarginConfig)
    
    # Alerts
    enabled_alerts: List[str] = field(default_factory=list)
    earnings_warning_days: int = 7
    
    # Portfolios
    portfolios: PortfoliosConfig = field(default_factory=PortfoliosConfig)

    # Exit rule profiles
    exit_rule_profiles: Dict[str, ExitRuleProfile] = field(default_factory=dict)

    # Performance tracking
    track_metrics: List[str] = field(default_factory=list)
    track_by: List[str] = field(default_factory=list)


# =============================================================================
# Configuration Loader
# =============================================================================

class RiskConfigLoader:
    """
    Load risk configuration from YAML file.
    
    Usage:
        loader = RiskConfigLoader()
        config = loader.load()  # Loads from default location
        
        # Or specify path
        config = loader.load('/path/to/risk_config.yaml')
        
        # Access settings
        print(config.var.confidence_level)
        print(config.concentration.single_underlying.max_percent)
        print(config.exit_rules.get_active_rules())
    """
    
    DEFAULT_PATHS = [
        Path('config/risk_config.yaml'),
        Path(__file__).parent / 'risk_config.yaml',
        Path(__file__).parent.parent / 'config' / 'risk_config.yaml',
    ]
    
    def __init__(self):
        self._config: Optional[RiskConfig] = None
        self._config_path: Optional[Path] = None
    
    def load(self, config_path: str = None) -> RiskConfig:
        """
        Load configuration from YAML file.
        
        Args:
            config_path: Path to config file (optional, will search defaults)
            
        Returns:
            RiskConfig object
        """
        # Find config file
        if config_path:
            path = Path(config_path)
            if not path.exists():
                raise FileNotFoundError(f"Config file not found: {config_path}")
        else:
            path = self._find_config_file()
        
        self._config_path = path
        logger.info(f"Loading risk config from: {path}")
        
        # Load YAML
        with open(path, 'r') as f:
            raw_config = yaml.safe_load(f)
        
        # Parse into typed config
        self._config = self._parse_config(raw_config)
        
        logger.info(f"✓ Loaded risk configuration")
        return self._config
    
    def get_config(self) -> RiskConfig:
        """Get loaded config (load if not already loaded)."""
        if self._config is None:
            return self.load()
        return self._config
    
    def reload(self) -> RiskConfig:
        """Reload configuration from file."""
        if self._config_path:
            return self.load(str(self._config_path))
        return self.load()
    
    def _find_config_file(self) -> Path:
        """Find config file in default locations."""
        for path in self.DEFAULT_PATHS:
            if path.exists():
                return path
        
        raise FileNotFoundError(
            f"Risk config file not found. Tried: {[str(p) for p in self.DEFAULT_PATHS]}"
        )
    
    def _parse_config(self, raw: Dict) -> RiskConfig:
        """Parse raw YAML into typed config."""
        config = RiskConfig()
        
        # Portfolio risk
        if 'portfolio_risk' in raw:
            pr = raw['portfolio_risk']
            
            if 'var' in pr:
                config.var = VaRConfig(**pr['var'])
            
            if 'greeks' in pr:
                config.greeks_limits = GreeksLimitsConfig(**pr['greeks'])
            
            if 'drawdown' in pr:
                config.drawdown = DrawdownConfig(**pr['drawdown'])
        
        # Concentration
        if 'concentration' in raw:
            conc = raw['concentration']
            config.concentration = ConcentrationConfig(
                single_underlying=ConcentrationLimitConfig(**conc.get('single_underlying', {})),
                strategy_type=ConcentrationLimitConfig(**conc.get('strategy_type', {})),
                direction=ConcentrationLimitConfig(
                    max_percent=conc.get('direction', {}).get('max_long_percent', 60),
                    warning_percent=conc.get('direction', {}).get('warning_percent', 50)
                ),
                expiration=ConcentrationLimitConfig(**conc.get('expiration', {})),
                sector=ConcentrationLimitConfig(**conc.get('sector', {}))

            )
        
        # Exit rules
        if 'exit_rules' in raw:
            er = raw['exit_rules']
            config.exit_rules = ExitRulesConfig(
                profit_targets=[ExitRule(**r) for r in er.get('profit_targets', [])],
                stop_losses=[ExitRule(**r) for r in er.get('stop_losses', [])],
                time_based=[ExitRule(**r) for r in er.get('time_based', [])],
                delta_based=[ExitRule(**r) for r in er.get('delta_based', [])],
                combined=[ExitRule(**r) for r in er.get('combined', [])]
            )
        
        # Underlyings
        if 'underlyings' in raw:
            ul = raw['underlyings']
            config.underlyings = UnderlyingsConfig(
                core=[WatchedUnderlying(**u) for u in ul.get('core', [])],
                stocks=[WatchedUnderlying(**u) for u in ul.get('stocks', [])],
                custom=[WatchedUnderlying(**u) for u in ul.get('custom', [])]
            )
        
        # IV settings
        if 'iv_settings' in raw:
            config.iv = IVConfig(**raw['iv_settings'])

        # Liquidity thresholds
        if 'liquidity_thresholds' in raw:
            lt = raw['liquidity_thresholds']
            config.liquidity = LiquidityThresholds(
                entry=LiquidityThreshold(**lt.get('entry', {})),
                adjustment=LiquidityThreshold(**lt.get('adjustment', {})),
            )
        
        # Strategy rules
        if 'strategy_rules' in raw:
            for name, rule_data in raw['strategy_rules'].items():
                entry_filters_data = rule_data.pop('entry_filters', None)
                entry_filters = None
                if entry_filters_data and isinstance(entry_filters_data, dict):
                    entry_filters = EntryFilters(**entry_filters_data)
                config.strategy_rules[name] = StrategyRule(
                    name=name, entry_filters=entry_filters, **rule_data
                )
        
        # Margin
        if 'margin' in raw:
            config.margin = MarginConfig(**raw['margin'])
        
        # Alerts
        if 'alerts' in raw:
            config.enabled_alerts = raw['alerts'].get('enabled', [])
            config.earnings_warning_days = raw['alerts'].get('earnings_warning_days', 7)
        
        # Exit rule profiles
        if 'exit_rule_profiles' in raw:
            for name, profile_data in raw['exit_rule_profiles'].items():
                config.exit_rule_profiles[name] = ExitRuleProfile(
                    name=name, **profile_data
                )

        # Portfolios
        if 'portfolios' in raw:
            portfolios_dict = {}
            for name, pdata in raw['portfolios'].items():
                risk_limits_data = pdata.get('risk_limits', {})
                risk_limits = PortfolioRiskLimits(**risk_limits_data)

                portfolios_dict[name] = PortfolioConfig(
                    name=name,
                    display_name=pdata.get('display_name', name),
                    description=pdata.get('description', ''),
                    capital_allocation_pct=pdata.get('capital_allocation_pct', 0),
                    initial_capital=pdata.get('initial_capital', 0),
                    target_annual_return_pct=pdata.get('target_annual_return_pct', 0),
                    exit_rule_profile=pdata.get('exit_rule_profile', 'balanced'),
                    tags=pdata.get('tags', []),
                    allowed_strategies=pdata.get('allowed_strategies', []),
                    active_strategies=pdata.get('active_strategies', []),
                    risk_limits=risk_limits,
                    preferred_underlyings=pdata.get('preferred_underlyings', []),
                    requires_rationale=pdata.get('requires_rationale', False),
                    requires_exit_commentary=pdata.get('requires_exit_commentary', False),
                )
            config.portfolios = PortfoliosConfig(portfolios=portfolios_dict)
            logger.info(f"Loaded {len(portfolios_dict)} portfolio configs "
                        f"(total allocation: {config.portfolios.total_allocation_pct():.0f}%)")

        # Performance
        if 'performance' in raw:
            config.track_metrics = raw['performance'].get('track_metrics', [])
            config.track_by = raw['performance'].get('track_by', [])

        return config


# =============================================================================
# Global Config Instance
# =============================================================================

_risk_config_loader: Optional[RiskConfigLoader] = None


def get_risk_config() -> RiskConfig:
    """
    Get global risk configuration (singleton).
    
    Usage:
        from config.risk_config_loader import get_risk_config
        
        config = get_risk_config()
        max_var = config.var.max_var_percent
    """
    global _risk_config_loader
    if _risk_config_loader is None:
        _risk_config_loader = RiskConfigLoader()
    return _risk_config_loader.get_config()


def reload_risk_config() -> RiskConfig:
    """Reload risk configuration from file."""
    global _risk_config_loader
    if _risk_config_loader is None:
        _risk_config_loader = RiskConfigLoader()
    return _risk_config_loader.reload()


# =============================================================================
# Example Usage
# =============================================================================

if __name__ == "__main__":
    # Load config
    try:
        config = get_risk_config()
        
        print("Risk Configuration Loaded:")
        print(f"  VaR Confidence: {config.var.confidence_level * 100}%")
        print(f"  Max VaR: {config.var.max_var_percent}% of portfolio")
        print(f"  Max Single Underlying: {config.concentration.single_underlying.max_percent}%")
        print(f"  Max Portfolio Delta: {config.greeks_limits.max_portfolio_delta}")
        
        print(f"\nWatched Underlyings: {len(config.underlyings.all_symbols())}")
        for sym in config.underlyings.all_symbols()[:5]:
            print(f"  - {sym}")
        
        print(f"\nActive Exit Rules:")
        for rule in config.exit_rules.get_active_rules():
            print(f"  - {rule.name}")
            
    except FileNotFoundError as e:
        print(f"Config not found: {e}")
        print("Creating default configuration...")
