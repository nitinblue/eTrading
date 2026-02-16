"""
Step 3: Portfolio Sync
======================

Sync portfolio from broker and display positions.
In mock/skip-sync modes, loads whatif trades from DB.
Always shows all virtual portfolios (cotrader-managed + whatif) side by side.
"""

from datetime import date
from decimal import Decimal
from trading_cotrader.harness.base import (
    TestStep, StepResult, rich_table, format_currency, format_greek,
    format_quantity, format_percent, warning
)


class PortfolioSyncStep(TestStep):
    """Sync portfolio from broker and display positions."""

    name = "Step 3: Portfolio Sync"
    description = "Sync positions from broker and display portfolio overview"

    def execute(self) -> StepResult:
        tables = []
        messages = []

        from trading_cotrader.repositories.portfolio import PortfolioRepository
        from trading_cotrader.repositories.position import PositionRepository
        from trading_cotrader.repositories.trade import TradeRepository
        from trading_cotrader.core.database.session import session_scope

        # Mock or skip-sync mode — load from DB (no broker needed)
        if self.context.get('use_mock') or self.context.get('skip_sync'):
            with session_scope() as session:
                portfolio_repo = PortfolioRepository(session)
                trade_repo = TradeRepository(session)
                position_repo = PositionRepository(session)

                all_portfolios = portfolio_repo.get_all_portfolios()

                if not all_portfolios:
                    return self._fail_result("No portfolios found in DB — run step 14 or book trades first")

                # Set first portfolio in context for downstream steps
                self.context['portfolio'] = all_portfolios[0]

                # Show all virtual portfolios side by side
                tables.append(self._all_portfolios_table(all_portfolios, trade_repo))

                # Show whatif trades if any exist
                whatif_trades = trade_repo.get_by_type('what_if')
                if whatif_trades:
                    tables.append(self._whatif_trades_table(whatif_trades))
                    messages.append(f"Found {len(whatif_trades)} WhatIf trades in DB")
                else:
                    messages.append("No WhatIf trades found — book some via step 12/13")

                # Show DB positions if any
                for portfolio in all_portfolios:
                    db_positions = position_repo.get_by_portfolio(portfolio.id)
                    if db_positions:
                        tables.append(self._db_positions_table(db_positions, portfolio.name))
                        self.context['db_positions'] = db_positions
                        break  # Show first portfolio with positions

                messages.append(f"Loaded {len(all_portfolios)} portfolios from DB")

            return self._success_result(tables=tables, messages=messages)

        # Full sync from broker
        broker = self.context.get('broker')
        if not broker:
            return self._fail_result("No broker connection")

        from trading_cotrader.services.portfolio_sync import PortfolioSyncService

        # Get raw positions for market data container FIRST (before sync might fail)
        try:
            broker_positions = broker.get_positions()
            self.context['broker_positions'] = broker_positions
            messages.append(f"Fetched {len(broker_positions)} raw positions from broker")
        except Exception as e:
            messages.append(f"Warning: Could not fetch raw positions: {e}")
            broker_positions = []

        # Show raw positions table regardless of sync outcome
        if broker_positions:
            tables.append(self._positions_table(broker_positions))

        with session_scope() as session:
            sync_service = PortfolioSyncService(session, broker)
            result = sync_service.sync_portfolio()

            if not result.success:
                messages.append(f"Sync had errors: {result.error}")
                # Don't fail completely - we still have raw positions for market data
                if broker_positions:
                    messages.append("Continuing with raw broker positions for market data")
                    return self._success_result(tables=tables, messages=messages)
                return self._fail_result(f"Sync failed: {result.error}")

            portfolio_repo = PortfolioRepository(session)
            trade_repo = TradeRepository(session)
            position_repo = PositionRepository(session)

            portfolio = portfolio_repo.get_by_id(result.portfolio_id)
            self.context['portfolio'] = portfolio

            db_positions = position_repo.get_by_portfolio(portfolio.id)
            self.context['db_positions'] = db_positions

            # Create tables
            tables.append(self._sync_summary_table(result))
            if db_positions:
                tables.append(self._db_positions_table(db_positions, portfolio.name))

            # Show all virtual portfolios side by side
            all_portfolios = portfolio_repo.get_all_portfolios()
            tables.append(self._all_portfolios_table(all_portfolios, trade_repo))

            messages.append(f"Synced {result.positions_synced} positions")

        return self._success_result(tables=tables, messages=messages)

    def _all_portfolios_table(self, portfolios: list, trade_repo) -> str:
        """Show all portfolios side by side with trade counts."""
        data = []
        for p in sorted(portfolios, key=lambda x: x.name):
            # Count trades for this portfolio
            trades = trade_repo.get_by_portfolio(p.id)
            open_trades = [t for t in trades if getattr(t, 'trade_status', None)
                          and t.trade_status.value != 'closed']

            portfolio_type = p.portfolio_type.value if hasattr(p.portfolio_type, 'value') else str(p.portfolio_type)
            broker_label = p.broker or '-'

            data.append([
                p.name[:25],
                portfolio_type[:10],
                broker_label,
                p.account_id or '-',
                format_currency(p.initial_capital),
                format_currency(p.total_equity),
                len(trades),
                len(open_trades),
                format_currency(p.total_pnl),
            ])

        return rich_table(
            data,
            headers=["Portfolio", "Type", "Broker", "Account", "Capital",
                      "Equity", "Trades", "Open", "P&L"],
            title="All Portfolios"
        )

    def _whatif_trades_table(self, trades: list) -> str:
        """Show whatif trades summary."""
        data = []
        for t in sorted(trades, key=lambda x: x.created_at or x.opened_at or '', reverse=True)[:15]:
            strategy = t.strategy.strategy_type.value if t.strategy else '-'
            status = t.trade_status.value if hasattr(t.trade_status, 'value') else str(t.trade_status)

            # Entry Greeks
            delta = format_greek(t.entry_greeks.delta) if t.entry_greeks else '-'
            theta = format_greek(t.entry_greeks.theta) if t.entry_greeks else '-'

            created = ''
            if t.created_at:
                created = t.created_at.strftime('%m/%d %H:%M')
            elif t.opened_at:
                created = t.opened_at.strftime('%m/%d %H:%M')

            data.append([
                t.underlying_symbol or '-',
                strategy[:18],
                status[:8],
                format_currency(t.entry_price),
                delta,
                theta,
                len(t.legs),
                created,
            ])

        return rich_table(
            data,
            headers=["Underlying", "Strategy", "Status", "Entry$",
                      "Delta", "Theta", "Legs", "Created"],
            title=f"WhatIf Trades ({len(trades)} total, showing latest 15)"
        )

    def _positions_table(self, positions: list) -> str:
        """Create table from broker positions (handles both dicts and Position objects)."""
        data = []
        for p in positions[:20]:  # Limit to 20
            # Handle Position domain objects
            if hasattr(p, 'symbol'):
                symbol_obj = p.symbol
                symbol = symbol_obj.ticker if hasattr(symbol_obj, 'ticker') else str(symbol_obj)
                inst_type = symbol_obj.asset_type.value if hasattr(symbol_obj, 'asset_type') else 'N/A'
                qty = p.quantity if hasattr(p, 'quantity') else 0
                underlying = symbol_obj.ticker if hasattr(symbol_obj, 'ticker') else '-'
                strike = str(symbol_obj.strike) if hasattr(symbol_obj, 'strike') and symbol_obj.strike else '-'
                expiry = symbol_obj.expiration.isoformat()[:10] if hasattr(symbol_obj, 'expiration') and symbol_obj.expiration else '-'
            else:
                # Handle dicts
                symbol = p.get('symbol', 'N/A')
                inst_type = p.get('instrument_type', 'N/A')
                qty = p.get('quantity', 0)
                underlying = p.get('underlying_symbol', '-')
                strike = p.get('strike_price', '-')
                expiry = str(p.get('expiration_date', '-'))[:10] if p.get('expiration_date') else '-'

            data.append([
                str(symbol)[:30],
                inst_type,
                format_quantity(int(qty)),
                underlying,
                strike,
                expiry,
            ])

        return rich_table(
            data,
            headers=["Symbol", "Type", "Qty", "Underlying", "Strike", "Expiry"],
            title=f"Broker Positions ({len(positions)} total)"
        )

    def _db_positions_table(self, positions: list, portfolio_name: str = "Portfolio") -> str:
        """Create table from DB positions with Greeks."""
        data = []

        for p in sorted(positions, key=lambda x: (x.symbol.ticker, str(x.symbol.expiration or ''))):
            symbol = p.symbol
            greeks = p.greeks

            # Calculate DTE
            dte = "-"
            if symbol.expiration:
                dte = (symbol.expiration - date.today()).days

            # P&L
            pnl = p.unrealized_pnl() if hasattr(p, 'unrealized_pnl') else Decimal(0)

            data.append([
                symbol.ticker,
                symbol.asset_type.value[:6],
                symbol.option_type.value[0] if symbol.option_type else "-",
                f"{float(symbol.strike):.0f}" if symbol.strike else "-",
                dte,
                format_quantity(p.quantity),
                format_currency(p.current_price * 100 if p.current_price else None),
                format_greek(greeks.delta) if greeks else "-",
                format_greek(greeks.gamma, 4) if greeks else "-",
                format_greek(greeks.theta) if greeks else "-",
                format_greek(greeks.vega) if greeks else "-",
                format_currency(pnl),
            ])

        return rich_table(
            data,
            headers=["Ticker", "Type", "P/C", "Strike", "DTE", "Qty",
                    "Value", "Delta", "Gamma", "Theta", "Vega", "P&L"],
            title=f"{portfolio_name} Positions ({len(positions)} positions)"
        )

    def _portfolio_summary_table(self, portfolio) -> str:
        """Portfolio summary with aggregated Greeks."""
        greeks = portfolio.portfolio_greeks

        data = [
            ["Total Equity", format_currency(portfolio.total_equity), ""],
            ["Total P&L", format_currency(portfolio.total_pnl),
             "+" if portfolio.total_pnl > 0 else "-" if portfolio.total_pnl < 0 else ""],
        ]

        if greeks:
            data.extend([
                ["Portfolio Delta", format_greek(greeks.delta),
                 "Long" if greeks.delta > 0 else "Short" if greeks.delta < 0 else "Neutral"],
                ["Portfolio Gamma", format_greek(greeks.gamma, 4), ""],
                ["Portfolio Theta", format_greek(greeks.theta),
                 f"${float(greeks.theta):,.0f}/day"],
                ["Portfolio Vega", format_greek(greeks.vega), ""],
            ])

        return rich_table(
            data,
            headers=["Metric", "Value", "Note"],
            title="Portfolio Summary"
        )

    def _sync_summary_table(self, result) -> str:
        """Sync operation summary."""
        data = [
            ["Positions Synced", result.positions_synced, "OK"],
            ["Positions Failed", result.positions_failed,
             "OK" if result.positions_failed == 0 else "WARN"],
            ["New Positions", getattr(result, 'new_positions', '-'), ""],
            ["Updated Positions", getattr(result, 'updated_positions', '-'), ""],
            ["Closed Positions", getattr(result, 'closed_positions', '-'), ""],
        ]

        return rich_table(
            data,
            headers=["Metric", "Count", "Status"],
            title="Sync Summary"
        )
