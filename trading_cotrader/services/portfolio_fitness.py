"""
Portfolio Fitness Checker — Validates whether a proposed trade fits
within portfolio risk limits.

Checks: margin, delta, concentration, VaR impact, position count.
Returns pass/fail with specific reasons and warnings.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FitnessResult:
    """Result of a portfolio fitness check."""
    fits: bool = True
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Impact numbers
    delta_after: float = 0.0
    var_after: float = 0.0
    margin_after_pct: float = 0.0
    concentration_after_pct: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'fits_portfolio': self.fits,
            'fitness_reasons': self.reasons,
            'fitness_warnings': self.warnings,
            'portfolio_delta_after': self.delta_after,
            'portfolio_var_after': self.var_after,
            'margin_used_pct_after': self.margin_after_pct,
            'concentration_after_pct': self.concentration_after_pct,
        }


class PortfolioFitnessChecker:
    """
    Check if a proposed trade fits the portfolio's risk constraints.

    Usage:
        checker = PortfolioFitnessChecker()
        result = checker.check_trade_fitness(portfolio_state, proposed_trade, risk_limits)
    """

    def check_trade_fitness(
        self,
        portfolio_state: Dict,
        proposed_trade: Dict,
        risk_limits: Dict,
    ) -> FitnessResult:
        """
        Check if a proposed trade fits the portfolio.

        Args:
            portfolio_state: {
                net_delta, total_equity, buying_power, margin_used,
                var_1d_95, open_positions, exposure_by_underlying
            }
            proposed_trade: {
                underlying, delta, margin_required, var_impact, legs
            }
            risk_limits: {
                max_delta, max_positions, max_var_pct, max_concentration_pct,
                min_cash_reserve_pct, max_margin_pct
            }

        Returns:
            FitnessResult with pass/fail and reasons
        """
        result = FitnessResult()
        reasons = []
        warnings = []

        equity = float(portfolio_state.get('total_equity', 0)) or 1
        current_delta = float(portfolio_state.get('net_delta', 0))
        buying_power = float(portfolio_state.get('buying_power', 0))
        margin_used = float(portfolio_state.get('margin_used', 0))
        current_var = float(portfolio_state.get('var_1d_95', 0))
        open_positions = int(portfolio_state.get('open_positions', 0))
        exposure = portfolio_state.get('exposure_by_underlying', {})

        trade_delta = float(proposed_trade.get('delta', 0))
        trade_margin = float(proposed_trade.get('margin_required', 0))
        trade_var = float(proposed_trade.get('var_impact', 0))
        trade_underlying = proposed_trade.get('underlying', '')

        # Limits
        max_delta = float(risk_limits.get('max_delta', 500))
        max_positions = int(risk_limits.get('max_positions', 50))
        max_var_pct = float(risk_limits.get('max_var_pct', 2.0))
        max_concentration_pct = float(risk_limits.get('max_concentration_pct', 20.0))
        max_margin_pct = float(risk_limits.get('max_margin_pct', 50.0))

        # 1. Delta check
        new_delta = current_delta + trade_delta
        result.delta_after = new_delta
        if abs(new_delta) <= max_delta:
            reasons.append(f"Delta {new_delta:+.0f} within limit ({max_delta})")
        else:
            result.fits = False
            reasons.append(f"FAIL: Delta {new_delta:+.0f} exceeds limit ({max_delta})")

        # 2. Margin check
        new_margin = margin_used + trade_margin
        new_margin_pct = (new_margin / equity * 100) if equity else 0
        result.margin_after_pct = new_margin_pct
        if trade_margin <= buying_power:
            reasons.append(f"Margin ${trade_margin:,.0f} available (BP: ${buying_power:,.0f})")
        else:
            result.fits = False
            reasons.append(f"FAIL: Margin ${trade_margin:,.0f} exceeds BP ${buying_power:,.0f}")
        if new_margin_pct > max_margin_pct:
            warnings.append(f"Margin at {new_margin_pct:.0f}% (limit {max_margin_pct:.0f}%)")

        # 3. VaR check
        new_var = current_var + trade_var
        result.var_after = new_var
        var_pct = (new_var / equity * 100) if equity else 0
        if var_pct <= max_var_pct:
            reasons.append(f"VaR {var_pct:.1f}% within limit ({max_var_pct}%)")
        else:
            warnings.append(f"VaR {var_pct:.1f}% exceeds {max_var_pct}% guideline")

        # 4. Concentration check
        current_exposure = float(exposure.get(trade_underlying, 0))
        # Use trade_margin as proxy for new exposure
        new_exposure = current_exposure + trade_margin
        concentration_pct = (new_exposure / equity * 100) if equity else 0
        result.concentration_after_pct = concentration_pct
        if concentration_pct > max_concentration_pct:
            warnings.append(
                f"{trade_underlying} concentration {concentration_pct:.0f}% "
                f"exceeds {max_concentration_pct:.0f}% guideline"
            )
        else:
            reasons.append(f"{trade_underlying} concentration {concentration_pct:.0f}% OK")

        # 5. Position count
        new_count = open_positions + 1
        if new_count <= max_positions:
            reasons.append(f"Position count {new_count}/{max_positions}")
        else:
            warnings.append(f"Position count {new_count} at limit ({max_positions})")

        result.reasons = reasons
        result.warnings = warnings
        return result
