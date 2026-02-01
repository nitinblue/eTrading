"""
Step 8: Trade History
=====================

Display trade history and analytics.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from harness.base import (
    TestStep, StepResult, rich_table, format_currency, format_percent
)


class TradeHistoryStep(TestStep):
    """Display trade history and analytics."""
    
    name = "Step 8: Trade History"
    description = "Show recent trades and performance metrics"
    
    def execute(self) -> StepResult:
        tables = []
        messages = []
        
        portfolio = self.context.get('portfolio')
        if not portfolio:
            messages.append("No portfolio - skipping trade history")
            return self._success_result(messages=messages)
        
        from repositories.trade import TradeRepository
        from core.database.session import session_scope
        
        with session_scope() as session:
            trade_repo = TradeRepository(session)
            
            all_trades = trade_repo.get_by_portfolio(portfolio.id)
            open_trades = trade_repo.get_by_portfolio(portfolio.id, open_only=True)
            
            messages.append(f"Found {len(all_trades)} total trades, {len(open_trades)} open")
            
            if not all_trades:
                messages.append("No trade history")
                return self._success_result(messages=messages)
            
            # Helper to get realized_pnl (handles method vs property)
            def get_realized_pnl(trade):
                if not hasattr(trade, 'realized_pnl'):
                    return None
                pnl_attr = trade.realized_pnl
                if callable(pnl_attr):
                    return pnl_attr()
                return pnl_attr
            
            # Summary stats
            closed_trades = [t for t in all_trades if hasattr(t, 'closed_at') and t.closed_at]
            winning = [t for t in closed_trades if get_realized_pnl(t) and get_realized_pnl(t) > 0]
            
            win_rate = (len(winning) / len(closed_trades) * 100) if closed_trades else 0
            total_pnl = sum(get_realized_pnl(t) or Decimal(0) for t in closed_trades) if closed_trades else Decimal(0)
            
            summary_data = [
                ["Total Trades", len(all_trades), ""],
                ["Open Trades", len(open_trades), "Active"],
                ["Closed Trades", len(closed_trades), ""],
                ["Winning Trades", len(winning), f"{win_rate:.1f}%"],
                ["Total Realized P&L", format_currency(total_pnl), 
                 "🟢" if total_pnl > 0 else "🔴" if total_pnl < 0 else ""],
            ]
            
            tables.append(rich_table(
                summary_data,
                headers=["Metric", "Value", "Note"],
                title="📈 Trade Performance Summary"
            ))
            
            # Open trades table
            if open_trades:
                open_data = []
                for t in open_trades[:15]:
                    strategy = t.strategy.name if hasattr(t, 'strategy') and t.strategy else "-"
                    underlying = t.underlying_symbol if hasattr(t, 'underlying_symbol') else "-"
                    opened = t.opened_at.strftime("%Y-%m-%d") if hasattr(t, 'opened_at') and t.opened_at else "-"
                    max_risk = format_currency(t.max_risk) if hasattr(t, 'max_risk') and t.max_risk else "-"
                    
                    # Days open
                    days = "-"
                    if hasattr(t, 'opened_at') and t.opened_at:
                        days = (datetime.now(t.opened_at.tzinfo) if t.opened_at.tzinfo else datetime.now() - t.opened_at).days
                    
                    open_data.append([
                        underlying,
                        strategy[:20],
                        opened,
                        days,
                        max_risk,
                        getattr(t, 'trade_status', '-').value if hasattr(getattr(t, 'trade_status', None), 'value') else str(getattr(t, 'trade_status', '-')),
                    ])
                
                tables.append(rich_table(
                    open_data,
                    headers=["Underlying", "Strategy", "Opened", "Days", "Max Risk", "Status"],
                    title="🔓 Open Trades"
                ))
            
            # Recent closed trades
            if closed_trades:
                recent_closed = sorted(closed_trades, 
                                       key=lambda t: t.closed_at if hasattr(t, 'closed_at') and t.closed_at else datetime.min,
                                       reverse=True)[:10]
                
                closed_data = []
                for t in recent_closed:
                    underlying = t.underlying_symbol if hasattr(t, 'underlying_symbol') else "-"
                    strategy = t.strategy.name if hasattr(t, 'strategy') and t.strategy else "-"
                    pnl = get_realized_pnl(t) or Decimal(0)
                    closed = t.closed_at.strftime("%Y-%m-%d") if hasattr(t, 'closed_at') and t.closed_at else "-"
                    
                    closed_data.append([
                        underlying,
                        strategy[:20],
                        closed,
                        format_currency(pnl),
                        "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪",
                    ])
                
                tables.append(rich_table(
                    closed_data,
                    headers=["Underlying", "Strategy", "Closed", "P&L", ""],
                    title="📜 Recent Closed Trades"
                ))
            
            # Strategy breakdown
            strategy_stats = {}
            for t in all_trades:
                strategy = t.strategy.name if hasattr(t, 'strategy') and t.strategy else "Unknown"
                if strategy not in strategy_stats:
                    strategy_stats[strategy] = {"count": 0, "pnl": Decimal(0), "wins": 0}
                strategy_stats[strategy]["count"] += 1
                
                # Handle realized_pnl - could be method, property, or attribute
                pnl = None
                if hasattr(t, 'realized_pnl'):
                    pnl_attr = t.realized_pnl
                    if callable(pnl_attr):
                        pnl = pnl_attr()  # It's a method
                    else:
                        pnl = pnl_attr  # It's a property/attribute
                
                if pnl is not None:
                    strategy_stats[strategy]["pnl"] += Decimal(str(pnl)) if pnl else Decimal(0)
                    if pnl > 0:
                        strategy_stats[strategy]["wins"] += 1
            
            if strategy_stats:
                strat_data = []
                for strategy, stats in sorted(strategy_stats.items(), 
                                              key=lambda x: x[1]["count"], 
                                              reverse=True):
                    win_rate = (stats["wins"] / stats["count"] * 100) if stats["count"] > 0 else 0
                    strat_data.append([
                        strategy[:25],
                        stats["count"],
                        f"{win_rate:.0f}%",
                        format_currency(stats["pnl"]),
                        "🟢" if stats["pnl"] > 0 else "🔴" if stats["pnl"] < 0 else "⚪",
                    ])
                
                tables.append(rich_table(
                    strat_data[:10],
                    headers=["Strategy", "Trades", "Win Rate", "P&L", ""],
                    title="🎯 Performance by Strategy"
                ))
        
        return self._success_result(tables=tables, messages=messages)