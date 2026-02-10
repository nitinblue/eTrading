"""
Step 3: Portfolio Sync
======================

Sync portfolio from broker and display positions.
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
        
        # Mock mode
        if self.context.get('use_mock'):
            positions = self._get_mock_positions()
            self.context['broker_positions'] = positions
            messages.append(f"Using {len(positions)} mock positions")
            
            tables.append(self._positions_table(positions))
            return self._success_result(tables=tables, messages=messages)
        
        # Skip sync mode - load from DB
        if self.context.get('skip_sync'):
            from repositories.portfolio import PortfolioRepository
            from repositories.position import PositionRepository
            from core.database.session import session_scope
            
            with session_scope() as session:
                portfolio_repo = PortfolioRepository(session)
                portfolios = portfolio_repo.get_all_portfolios()
                
                if not portfolios:
                    return self._fail_result("No portfolio found - run without --skip-sync first")
                
                portfolio = portfolios[0]
                self.context['portfolio'] = portfolio
                
                position_repo = PositionRepository(session)
                db_positions = position_repo.get_by_portfolio(portfolio.id)
                
                messages.append(f"Loaded {len(db_positions)} positions from DB")
                tables.append(self._db_positions_table(db_positions))
                tables.append(self._portfolio_summary_table(portfolio))
                
            return self._success_result(tables=tables, messages=messages)
        
        # Full sync from broker
        broker = self.context.get('broker')
        if not broker:
            return self._fail_result("No broker connection")
        
        from services.portfolio_sync import PortfolioSyncService
        from repositories.portfolio import PortfolioRepository
        from repositories.position import PositionRepository
        from core.database.session import session_scope
        
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
            portfolio = portfolio_repo.get_by_id(result.portfolio_id)
            self.context['portfolio'] = portfolio
            
            position_repo = PositionRepository(session)
            db_positions = position_repo.get_by_portfolio(portfolio.id)
            
            # Store DB positions as well (for steps that need domain objects)
            self.context['db_positions'] = db_positions
            
            # Create tables
            tables.append(self._sync_summary_table(result))
            if db_positions:
                tables.append(self._db_positions_table(db_positions))
            tables.append(self._portfolio_summary_table(portfolio))
            
            messages.append(f"Synced {result.positions_synced} positions")
        
        return self._success_result(tables=tables, messages=messages)
    
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
            title=f"📋 Broker Positions ({len(positions)} total)"
        )
    
    def _db_positions_table(self, positions: list) -> str:
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
                    "Value", "Δ", "Γ", "Θ", "V", "P&L"],
            title=f"📊 Portfolio Positions ({len(positions)} positions)"
        )
    
    def _portfolio_summary_table(self, portfolio) -> str:
        """Portfolio summary with aggregated Greeks."""
        greeks = portfolio.portfolio_greeks
        
        data = [
            ["Total Equity", format_currency(portfolio.total_equity), ""],
            ["Total P&L", format_currency(portfolio.total_pnl), 
             "🟢" if portfolio.total_pnl > 0 else "🔴" if portfolio.total_pnl < 0 else ""],
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
            title="💼 Portfolio Summary"
        )
    
    def _sync_summary_table(self, result) -> str:
        """Sync operation summary."""
        data = [
            ["Positions Synced", result.positions_synced, "✓"],
            ["Positions Failed", result.positions_failed, 
             "✓" if result.positions_failed == 0 else "⚠"],
            ["New Positions", getattr(result, 'new_positions', '-'), ""],
            ["Updated Positions", getattr(result, 'updated_positions', '-'), ""],
            ["Closed Positions", getattr(result, 'closed_positions', '-'), ""],
        ]
        
        return rich_table(
            data,
            headers=["Metric", "Count", "Status"],
            title="🔄 Sync Summary"
        )
    
    def _get_mock_positions(self) -> list:
        """Generate mock positions for testing."""
        return [
            {"symbol": "MSFT", "instrument_type": "EQUITY", "quantity": 100,
             "underlying_symbol": "MSFT"},
            {"symbol": "MSFT  260331P00400000", "instrument_type": "EQUITY_OPTION",
             "underlying_symbol": "MSFT", "strike_price": "400.00",
             "expiration_date": "2026-03-31", "option_type": "PUT", 
             "multiplier": 100, "quantity": -2},
            {"symbol": "SPY   260331C00600000", "instrument_type": "EQUITY_OPTION",
             "underlying_symbol": "SPY", "strike_price": "600.00",
             "expiration_date": "2026-03-31", "option_type": "CALL",
             "multiplier": 100, "quantity": 5},
            {"symbol": "AAPL  260331P00180000", "instrument_type": "EQUITY_OPTION",
             "underlying_symbol": "AAPL", "strike_price": "180.00",
             "expiration_date": "2026-03-31", "option_type": "PUT",
             "multiplier": 100, "quantity": -3},
            {"symbol": "QQQ   260228P00480000", "instrument_type": "EQUITY_OPTION",
             "underlying_symbol": "QQQ", "strike_price": "480.00",
             "expiration_date": "2026-02-28", "option_type": "PUT",
             "multiplier": 100, "quantity": -4},
        ]
