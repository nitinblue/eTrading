"""
Step 14: Portfolio Tiers & Performance Metrics
===============================================

Initializes 4 multi-tier portfolios from YAML config,
calculates performance metrics, and prints tabulate tables.

Does NOT require broker connection — works with existing DB data.
"""

from decimal import Decimal
from typing import Dict, Any, List

from trading_cotrader.harness.base import TestStep, StepResult, rich_table


class PortfolioPerformanceStep(TestStep):
    name = "Portfolio Tiers & Performance"
    description = "Initialize portfolios from YAML, calculate performance metrics"

    def execute(self) -> StepResult:
        from trading_cotrader.config.risk_config_loader import RiskConfigLoader
        from trading_cotrader.core.database.session import session_scope
        from trading_cotrader.services.portfolio_manager import PortfolioManager
        from trading_cotrader.services.performance_metrics_service import (
            PerformanceMetricsService,
        )

        tables: List[str] = []
        messages: List[str] = []

        # =====================================================================
        # Part 1: Load YAML config and validate
        # =====================================================================
        loader = RiskConfigLoader()
        risk_config = loader.load()
        pc = risk_config.portfolios

        if not pc.get_all():
            return self._fail_result("No portfolios defined in risk_config.yaml")

        total_alloc = pc.total_allocation_pct()
        valid = pc.validate_allocations()
        messages.append(
            f"YAML loaded: {len(pc.get_all())} portfolios, "
            f"total allocation {total_alloc:.0f}% "
            f"({'OK' if valid else 'OVER 100%!'})"
        )

        if not valid:
            return self._fail_result(
                f"Portfolio allocations sum to {total_alloc}% — must be <= 100%"
            )

        # Config summary table
        config_data = []
        for p in pc.get_all():
            config_data.append([
                p.display_name,
                f"{p.capital_allocation_pct:.0f}%",
                f"${p.initial_capital:,.0f}",
                f"{p.target_annual_return_pct:.0f}%",
                len(p.allowed_strategies),
                p.risk_limits.max_positions,
                p.exit_rule_profile,
            ])
        tables.append(rich_table(
            config_data,
            headers=["Portfolio", "Alloc%", "Capital", "Target", "Strategies", "Max Pos", "Exit Profile"],
            title="Portfolio Configuration (from YAML)",
        ))

        # =====================================================================
        # Part 2: Initialize portfolios in DB
        # =====================================================================
        with session_scope() as session:
            pm = PortfolioManager(session, config=pc)
            portfolios = pm.initialize_portfolios(
                total_capital=Decimal('250000')
            )

        messages.append(f"Initialized {len(portfolios)} portfolios in DB")

        # Portfolio DB table
        db_data = []
        for p in portfolios:
            db_data.append([
                p.name,
                p.account_id,
                f"${float(p.initial_capital):,.0f}",
                f"${float(p.total_equity):,.0f}",
                f"${float(p.cash_balance):,.0f}",
                f"{float(p.max_portfolio_delta):.0f}",
                p.id[:8] + "...",
            ])
        tables.append(rich_table(
            db_data,
            headers=["Name", "Account ID", "Initial", "Equity", "Cash", "Max Delta", "ID"],
            title="Portfolios in Database",
        ))

        # =====================================================================
        # Part 3: Calculate performance metrics for each portfolio
        # =====================================================================
        with session_scope() as session:
            metrics_svc = PerformanceMetricsService(session)

            all_metrics = []
            for p in portfolios:
                # Find matching config for initial capital
                p_config = pc.get_by_name(p.account_id)
                initial_cap = Decimal(str(p_config.initial_capital)) if p_config else p.initial_capital

                metrics = metrics_svc.calculate_portfolio_metrics(
                    portfolio_id=p.id,
                    label=p.name,
                    initial_capital=initial_cap,
                )
                all_metrics.append(metrics)

            # Metrics summary table
            metrics_data = []
            for m in all_metrics:
                metrics_data.append([
                    m.label,
                    m.total_trades,
                    f"{m.win_rate:.1f}%",
                    f"${float(m.total_pnl):,.2f}",
                    f"${float(m.avg_win):,.2f}" if m.winning_trades else "-",
                    f"${float(m.avg_loss):,.2f}" if m.losing_trades else "-",
                    f"{m.profit_factor:.2f}" if m.profit_factor else "-",
                    f"${float(m.expectancy):,.2f}" if m.total_trades else "-",
                    f"{m.max_drawdown_pct:.1f}%",
                    f"{m.sharpe_ratio:.2f}" if m.sharpe_ratio else "-",
                ])
            tables.append(rich_table(
                metrics_data,
                headers=[
                    "Portfolio", "Trades", "Win%", "Total P&L",
                    "Avg Win", "Avg Loss", "PF", "Expectancy",
                    "Max DD", "Sharpe",
                ],
                title="Performance Metrics",
            ))

            # =====================================================================
            # Part 4: Strategy breakdown for each portfolio with trades
            # =====================================================================
            for p in portfolios:
                breakdown = metrics_svc.calculate_strategy_breakdown(
                    portfolio_id=p.id,
                    label=p.name,
                )
                if breakdown.strategies:
                    strat_data = []
                    for stype, sm in sorted(breakdown.strategies.items()):
                        strat_data.append([
                            stype,
                            sm.total_trades,
                            f"{sm.win_rate:.1f}%",
                            f"${float(sm.total_pnl):,.2f}",
                            f"${float(sm.avg_win):,.2f}" if sm.winning_trades else "-",
                            f"${float(sm.avg_loss):,.2f}" if sm.losing_trades else "-",
                            f"{sm.profit_factor:.2f}" if sm.profit_factor else "-",
                        ])
                    tables.append(rich_table(
                        strat_data,
                        headers=["Strategy", "Trades", "Win%", "P&L", "Avg Win", "Avg Loss", "PF"],
                        title=f"Strategy Breakdown: {p.name}",
                    ))

            # =====================================================================
            # Part 5: Weekly P&L for portfolios with trade history
            # =====================================================================
            for p in portfolios:
                weekly = metrics_svc.calculate_weekly_performance(
                    portfolio_id=p.id,
                    weeks=12,
                )
                if weekly:
                    week_data = []
                    for w in weekly[-8:]:  # last 8 weeks
                        week_data.append([
                            w.week_start.strftime('%Y-%m-%d'),
                            w.trade_count,
                            f"${float(w.pnl):,.2f}",
                            f"${float(w.cumulative_pnl):,.2f}",
                        ])
                    tables.append(rich_table(
                        week_data,
                        headers=["Week Of", "Trades", "Weekly P&L", "Cumulative"],
                        title=f"Weekly P&L: {p.name}",
                    ))

        # =====================================================================
        # Part 6: Allowed strategies matrix
        # =====================================================================
        all_strategies = sorted(set(
            s for p_cfg in pc.get_all() for s in p_cfg.allowed_strategies
        ))
        strat_matrix = []
        for strat in all_strategies:
            row = [strat]
            for p_cfg in pc.get_all():
                row.append("Y" if strat in p_cfg.allowed_strategies else "-")
            strat_matrix.append(row)

        portfolio_names = [p.display_name[:12] for p in pc.get_all()]
        tables.append(rich_table(
            strat_matrix,
            headers=["Strategy"] + portfolio_names,
            title="Strategy Permissions Matrix",
        ))

        messages.append(f"Performance metrics calculated for {len(portfolios)} portfolios")

        # Store portfolios in context for subsequent steps
        self.context['managed_portfolios'] = portfolios

        return self._success_result(tables=tables, messages=messages)
