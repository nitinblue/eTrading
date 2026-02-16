"""
Portfolio Manager - Initialize and manage multi-tier portfolios from YAML config.

Responsibilities:
    - Create portfolios from risk_config.yaml definitions
    - Validate capital allocations sum to <= 100%
    - Route trades to the correct portfolio based on strategy type
    - Enforce strategy permissions per portfolio
    - Provide portfolio lookup by name

Usage:
    from trading_cotrader.services.portfolio_manager import PortfolioManager
    from trading_cotrader.core.database.session import session_scope

    with session_scope() as session:
        pm = PortfolioManager(session)
        portfolios = pm.initialize_portfolios(total_capital=250000)
"""

from decimal import Decimal
from typing import List, Dict, Optional
import logging

import trading_cotrader.core.models.domain as dm
from trading_cotrader.config.risk_config_loader import (
    RiskConfigLoader, PortfolioConfig, PortfoliosConfig
)
from trading_cotrader.repositories.portfolio import PortfolioRepository

logger = logging.getLogger(__name__)

# Portfolios created by this manager use broker="cotrader"
_BROKER_TAG = "cotrader"


class PortfolioManager:
    """
    Manages multi-tier portfolio creation and trade routing.

    Portfolios are identified by broker='cotrader' and account_id=<portfolio_name>.
    This reuses the existing unique constraint (broker, account_id) without schema changes.
    """

    def __init__(self, session, config: Optional[PortfoliosConfig] = None):
        """
        Args:
            session: SQLAlchemy session (must be inside session_scope)
            config: Optional PortfoliosConfig. If None, loads from YAML.
        """
        self.session = session
        self.repo = PortfolioRepository(session)

        if config is not None:
            self.portfolios_config = config
        else:
            loader = RiskConfigLoader()
            risk_config = loader.load()
            self.portfolios_config = risk_config.portfolios

    def initialize_portfolios(
        self,
        total_capital: Decimal = Decimal('250000'),
    ) -> List[dm.Portfolio]:
        """
        Create or update portfolios from YAML config.

        If a portfolio with the same (broker, account_id) already exists,
        it is returned as-is (no overwrite). New portfolios are created.

        Args:
            total_capital: Total capital across all accounts.

        Returns:
            List of Portfolio domain objects (one per config entry).
        """
        if not self.portfolios_config.validate_allocations():
            total = self.portfolios_config.total_allocation_pct()
            raise ValueError(
                f"Portfolio allocations sum to {total:.1f}% — must be <= 100%"
            )

        created: List[dm.Portfolio] = []

        for pc in self.portfolios_config.get_all():
            # Use explicit initial_capital from YAML if set,
            # otherwise derive from allocation percentage
            if pc.initial_capital > 0:
                capital = Decimal(str(pc.initial_capital))
            else:
                capital = total_capital * Decimal(str(pc.capital_allocation_pct)) / Decimal('100')

            # Check if portfolio already exists
            existing = self.repo.get_by_account(
                broker=_BROKER_TAG, account_id=pc.name
            )
            if existing:
                logger.info(f"Portfolio '{pc.display_name}' already exists (id={existing.id})")
                created.append(existing)
                continue

            # Create new portfolio
            portfolio = dm.Portfolio.create_what_if(
                name=pc.display_name,
                capital=capital,
                description=pc.description,
                risk_limits={
                    'max_delta': pc.risk_limits.max_portfolio_delta,
                    'max_position_pct': pc.risk_limits.max_single_position_pct,
                    'max_trade_risk_pct': pc.risk_limits.max_single_trade_risk_pct,
                },
                broker=_BROKER_TAG,
                account_id=pc.name,
                tags=pc.tags,
            )

            saved = self.repo.create_from_domain(portfolio)
            if saved:
                logger.info(
                    f"Created portfolio '{pc.display_name}' "
                    f"capital=${capital:,.0f} account_id={pc.name}"
                )
                created.append(saved)
            else:
                logger.error(f"Failed to create portfolio '{pc.display_name}'")

        return created

    def get_portfolio_by_name(self, name: str) -> Optional[dm.Portfolio]:
        """
        Look up a portfolio by its config name (e.g. 'core_holdings').

        Args:
            name: Internal portfolio name from YAML config.

        Returns:
            Portfolio domain object or None.
        """
        return self.repo.get_by_account(broker=_BROKER_TAG, account_id=name)

    def get_all_managed_portfolios(self) -> List[dm.Portfolio]:
        """Get all portfolios managed by this system (broker='cotrader')."""
        all_portfolios = self.repo.get_all_portfolios()
        return [p for p in all_portfolios if p.broker == _BROKER_TAG]

    def get_portfolio_config(self, name: str) -> Optional[PortfolioConfig]:
        """Get the YAML config for a portfolio by name."""
        return self.portfolios_config.get_by_name(name)

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
        preferring higher-risk tiers for undefined-risk strategies.

        Args:
            strategy_type: Strategy type string.

        Returns:
            Portfolio config name, or None if no portfolio allows it.
        """
        for pc in self.portfolios_config.get_all():
            if strategy_type in pc.allowed_strategies:
                return pc.name
        return None
