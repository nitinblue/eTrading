"""
Portfolio Manager - Initialize and manage multi-broker portfolios from YAML config.

Responsibilities:
    - Create portfolios from risk_config.yaml definitions
    - Route trades to the correct portfolio based on broker + account
    - Enforce strategy permissions per portfolio
    - Provide portfolio lookup by config name
    - Distinguish real vs whatif, manual vs API brokers

Usage:
    from trading_cotrader.services.portfolio_manager import PortfolioManager
    from trading_cotrader.core.database.session import session_scope

    with session_scope() as session:
        pm = PortfolioManager(session)
        portfolios = pm.initialize_portfolios()
"""

from decimal import Decimal
from typing import List, Dict, Optional
import logging

import trading_cotrader.core.models.domain as dm
from trading_cotrader.config.risk_config_loader import (
    RiskConfigLoader, PortfolioConfig, PortfoliosConfig
)
from trading_cotrader.config.broker_config_loader import (
    BrokerRegistry, load_broker_registry
)
from trading_cotrader.repositories.portfolio import PortfolioRepository

logger = logging.getLogger(__name__)


class PortfolioManager:
    """
    Manages multi-broker portfolio creation and trade routing.

    Portfolios are identified by (broker_firm, account_number) from YAML config.
    This maps to the existing unique constraint (broker, account_id) in the DB.
    """

    def __init__(
        self,
        session,
        config: Optional[PortfoliosConfig] = None,
        broker_registry: Optional[BrokerRegistry] = None,
    ):
        """
        Args:
            session: SQLAlchemy session (must be inside session_scope)
            config: Optional PortfoliosConfig. If None, loads from YAML.
            broker_registry: Optional BrokerRegistry. If None, loads from YAML.
        """
        self.session = session
        self.repo = PortfolioRepository(session)

        if config is not None:
            self.portfolios_config = config
        else:
            loader = RiskConfigLoader()
            risk_config = loader.load()
            self.portfolios_config = risk_config.portfolios

        if broker_registry is not None:
            self.broker_registry = broker_registry
        else:
            try:
                self.broker_registry = load_broker_registry()
            except FileNotFoundError:
                self.broker_registry = BrokerRegistry()

    def initialize_portfolios(self) -> List[dm.Portfolio]:
        """
        Create or update portfolios from YAML config.

        If a portfolio with the same (broker, account_id) already exists,
        it is returned as-is (no overwrite). New portfolios are created.

        Returns:
            List of Portfolio domain objects (one per config entry).
        """
        created: List[dm.Portfolio] = []

        for pc in self.portfolios_config.get_all():
            capital = Decimal(str(pc.initial_capital))

            # Check if portfolio already exists by broker+account
            existing = self.repo.get_by_account(
                broker=pc.broker_firm, account_id=pc.account_number
            )
            if existing:
                logger.info(
                    f"Portfolio '{pc.display_name}' already exists "
                    f"(id={existing.id}, broker={pc.broker_firm})"
                )
                created.append(existing)
                continue

            # Create new portfolio
            risk_limits = {
                'max_delta': pc.risk_limits.max_portfolio_delta,
                'max_position_pct': pc.risk_limits.max_single_position_pct,
                'max_trade_risk_pct': pc.risk_limits.max_single_trade_risk_pct,
            }

            if pc.is_whatif:
                portfolio = dm.Portfolio.create_what_if(
                    name=pc.display_name,
                    capital=capital,
                    description=pc.description,
                    risk_limits=risk_limits,
                    broker=pc.broker_firm,
                    account_id=pc.account_number,
                    tags=pc.tags,
                )
            elif pc.is_research:
                portfolio = dm.Portfolio.create_research(
                    name=pc.display_name,
                    description=pc.description,
                    risk_limits=risk_limits,
                    broker=pc.broker_firm,
                    account_id=pc.account_number,
                    tags=pc.tags,
                )
            else:
                portfolio = dm.Portfolio.create_real(
                    name=pc.display_name,
                    broker=pc.broker_firm,
                    account_id=pc.account_number,
                    description=pc.description,
                    initial_capital=capital,
                    cash_balance=capital,
                    buying_power=capital,
                    total_equity=capital,
                    tags=pc.tags,
                )
                # Apply risk limits to real portfolios too
                if 'max_delta' in risk_limits:
                    portfolio.max_portfolio_delta = Decimal(str(risk_limits['max_delta']))
                if 'max_position_pct' in risk_limits:
                    portfolio.max_position_size_pct = Decimal(str(risk_limits['max_position_pct']))
                if 'max_trade_risk_pct' in risk_limits:
                    portfolio.max_single_trade_risk_pct = Decimal(str(risk_limits['max_trade_risk_pct']))

            saved = self.repo.create_from_domain(portfolio)
            if saved:
                logger.info(
                    f"Created portfolio '{pc.display_name}' "
                    f"broker={pc.broker_firm} account={pc.account_number} "
                    f"capital={capital:,.0f} {pc.currency} type={pc.portfolio_type}"
                )
                created.append(saved)
            else:
                logger.error(f"Failed to create portfolio '{pc.display_name}'")

        return created

    def get_portfolio_by_name(self, name: str) -> Optional[dm.Portfolio]:
        """
        Look up a portfolio by its config name (e.g. 'tastytrade', 'fidelity_ira').

        Uses config to determine the broker+account_number, then queries DB.
        """
        pc = self.portfolios_config.get_by_name(name)
        if not pc:
            return None
        return self.repo.get_by_account(
            broker=pc.broker_firm, account_id=pc.account_number
        )

    def get_all_managed_portfolios(self) -> List[dm.Portfolio]:
        """Get all portfolios managed by this system (defined in config)."""
        results = []
        for pc in self.portfolios_config.get_all():
            portfolio = self.repo.get_by_account(
                broker=pc.broker_firm, account_id=pc.account_number
            )
            if portfolio:
                results.append(portfolio)
        return results

    def get_config_name_for_portfolio(self, portfolio: dm.Portfolio) -> Optional[str]:
        """Reverse lookup: get config name from a Portfolio domain object."""
        return self.portfolios_config.get_config_name_for(
            portfolio.broker, portfolio.account_id
        )

    def get_portfolio_config(self, name: str) -> Optional[PortfolioConfig]:
        """Get the YAML config for a portfolio by name."""
        return self.portfolios_config.get_by_name(name)

    def is_manual_execution(self, name: str) -> bool:
        """Check if a portfolio's broker requires manual execution (no API)."""
        pc = self.portfolios_config.get_by_name(name)
        if not pc:
            return False
        bc = self.broker_registry.get_by_name(pc.broker_firm)
        if not bc:
            return False
        return bc.manual_execution

    def is_read_only(self, name: str) -> bool:
        """Check if a portfolio's broker is read-only (fully managed fund, no trading)."""
        pc = self.portfolios_config.get_by_name(name)
        if not pc:
            return False
        bc = self.broker_registry.get_by_name(pc.broker_firm)
        if not bc:
            return False
        return bc.read_only

    def get_currency(self, name: str) -> str:
        """Get the currency for a portfolio."""
        pc = self.portfolios_config.get_by_name(name)
        return pc.currency if pc else "USD"

    def validate_trade_for_portfolio(
        self,
        portfolio_name: str,
        strategy_type: str,
    ) -> Dict:
        """
        Check if a strategy type is allowed for a given portfolio.

        Args:
            portfolio_name: Internal portfolio name.
            strategy_type: Strategy type string (e.g. 'iron_condor').

        Returns:
            Dict with 'allowed' (bool), 'reason' (str), 'portfolio_config' (PortfolioConfig).
        """
        pc = self.portfolios_config.get_by_name(portfolio_name)
        if pc is None:
            return {
                'allowed': False,
                'reason': f"Unknown portfolio: {portfolio_name}",
                'portfolio_config': None,
            }

        if strategy_type in pc.allowed_strategies:
            return {
                'allowed': True,
                'reason': '',
                'portfolio_config': pc,
            }

        return {
            'allowed': False,
            'reason': (
                f"Strategy '{strategy_type}' not allowed in '{pc.display_name}'. "
                f"Allowed: {', '.join(pc.allowed_strategies)}"
            ),
            'portfolio_config': pc,
        }

    def get_active_strategies(self, portfolio_name: str) -> List[str]:
        """
        Get the currently active strategies for a portfolio.
        Falls back to allowed_strategies if active_strategies not configured.
        """
        pc = self.portfolios_config.get_by_name(portfolio_name)
        if pc is None:
            return []
        return pc.get_active_strategies()

    def is_strategy_active(self, portfolio_name: str, strategy_type: str) -> bool:
        """Check if a strategy type is actively being traded in a portfolio."""
        return strategy_type in self.get_active_strategies(portfolio_name)

    def get_portfolio_for_strategy(self, strategy_type: str) -> Optional[str]:
        """
        Find the best portfolio for a given strategy type.

        Returns the name of the first portfolio that allows the strategy,
        preferring real portfolios over whatif.
        """
        # Prefer real portfolios
        for pc in self.portfolios_config.get_real_portfolios():
            if strategy_type in pc.allowed_strategies:
                return pc.name
        # Fall back to whatif
        for pc in self.portfolios_config.get_whatif_portfolios():
            if strategy_type in pc.allowed_strategies:
                return pc.name
        return None
