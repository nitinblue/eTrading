# trading_bot/risk.py
from typing import List, Dict
from .positions import Position
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, config: Dict):
        self.config = config.get('risk', {})
        self.max_allocation = self.config.get('max_allocation_per_position', 0.05)
        self.max_loss = self.config.get('max_loss_per_trade', 0.002)
        self.max_undefined_risk = self.config.get('max_undefined_risk_allocation', 0.20)
        self.reserved_margin = self.config.get('reserved_margin_fraction', 0.20)
        self.stop_loss_level = self.config.get('stop_loss_level', -0.01)
        self.take_profit_level = self.config.get('take_profit_level', 0.02)
        self.max_strategy_concentration = self.config.get('max_strategy_concentration', 0.25)
        self.greek_targets = self.config.get('greek_targets', {})
        self.multiplier = 100  # Standard for options

    def assess_position(self, position: Position, capital: float) -> Dict:
        """Assess risk for a single position, including Greek PNL attribution."""
        allocation = abs(position.quantity * position.current_price * self.multiplier) / capital if capital > 0 else 0
        actual_pnl = position.calculate_pnl()
        pnl_driver = self._determine_pnl_driver(position)

        # Greek PNL attribution
        change_underlying = position.current_underlying_price - position.opening_underlying_price
        days_passed = (datetime.now() - position.opening_time).days
        change_iv = position.current_iv - position.opening_iv
        change_rate = position.current_rate - position.opening_rate

        opening_greeks = position.opening_greeks
        current_greeks = position.greeks

        delta_pnl = opening_greeks.get('delta', 0) * change_underlying * self.multiplier
        gamma_pnl = 0.5 * opening_greeks.get('gamma', 0) * (change_underlying ** 2) * self.multiplier
        theta_pnl = opening_greeks.get('theta', 0) * days_passed * self.multiplier
        vega_pnl = opening_greeks.get('vega', 0) * change_iv * self.multiplier / 100
        rho_pnl = opening_greeks.get('rho', 0) * change_rate * self.multiplier / 100

        greek_pnl = delta_pnl + gamma_pnl + theta_pnl + vega_pnl + rho_pnl
        unexplained_pnl = actual_pnl - greek_pnl

        is_undefined_risk = 'undefined' in position.strategy.lower()
        buying_power_used = allocation * capital

        violations = []
        if allocation > self.max_allocation:
            violations.append(f"Allocation {allocation:.2%} > {self.max_allocation:.2%}")
        if actual_pnl < -self.max_loss * capital:
            violations.append(f"Max loss ${-actual_pnl:.2f} > {self.max_loss * capital:.2f}")

        return {
            'trade_id': position.trade_id,
            'leg_id': position.leg_id,
            'strategy': position.strategy,
            'allocation': allocation,
            'actual_pnl': actual_pnl,
            'pnl_driver': pnl_driver,
            'stop_loss': position.entry_price * (1 + self.stop_loss_level),
            'take_profit': position.entry_price * (1 + self.take_profit_level),
            'buying_power_used': buying_power_used,
            'is_undefined_risk': is_undefined_risk,
            'opening_greeks': opening_greeks,
            'current_greeks': current_greeks,
            'delta_pnl': delta_pnl,
            'gamma_pnl': gamma_pnl,
            'theta_pnl': theta_pnl,
            'vega_pnl': vega_pnl,
            'rho_pnl': rho_pnl,
            'unexplained_pnl': unexplained_pnl,
            'violations': violations
        }

    def list_positions_api(self, positions: List[Position], capital: float) -> List[Dict]:
        """Enhanced API to list all positions with Greek PNL attribution."""
        return [self.assess_position(p, capital) for p in positions]

    # ... (keep assess_portfolio and other methods as before)

    def assess(self, positions: List[Position], capital: float) -> Dict:
        """Main portfolio-level risk assessment (called by Portfolio.update())."""
        position_risks = self.list_positions_api(positions, capital)
        total_undefined = sum(r['buying_power_used'] for r in position_risks if r['is_undefined_risk']) / capital if capital > 0 else 0
        strategy_concentration = self._calculate_strategy_concentration(position_risks, capital)
        net_greeks = self._aggregate_greeks(positions)
        greek_violations = self._check_greek_targets(net_greeks)

        violations = []
        if total_undefined > self.max_undefined_risk:
            violations.append(f"Undefined risk {total_undefined:.2%} > {self.max_undefined_risk:.2%}")
        violations.extend(greek_violations)
        for conc in strategy_concentration.values():
            if conc > self.max_strategy_concentration:
                violations.append(f"Strategy concentration {conc:.2%} > {self.max_strategy_concentration:.2%}")

        if violations:
            raise ValueError("Portfolio risk violations: " + "; ".join(violations))

        available_margin = capital * (1 - self.reserved_margin) - sum(r['buying_power_used'] for r in position_risks)

        return {
            'position_risks': position_risks,
            'net_greeks': net_greeks,
            'total_undefined_risk': total_undefined,
            'strategy_concentration': strategy_concentration,
            'available_margin': available_margin,
            'violations': violations
        }

    def _determine_pnl_driver(self, position: Position) -> str:
        greeks = position.greeks
        drivers = []
        if abs(greeks.get('delta', 0)) > 0.5:
            drivers.append('delta')
        if abs(greeks.get('theta', 0)) > 0.1:
            drivers.append('theta')
        if abs(greeks.get('vega', 0)) > 10:
            drivers.append('short vega' if greeks['vega'] < 0 else 'vega')
        return ", ".join(drivers) or "unknown"

    def _aggregate_greeks(self, positions: List[Position]) -> Dict:
        net = {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0, 'rho': 0.0}
        for p in positions:
            for greek in net:
                net[greek] += p.greeks.get(greek, 0.0) * p.quantity
        return net

    def _check_greek_targets(self, net_greeks: Dict) -> List[str]:
        violations = []
        targets = self.greek_targets
        delta = net_greeks['delta']
        if 'delta_min' in targets and delta < targets['delta_min']:
            violations.append(f"Delta below min ({delta:.2f} < {targets['delta_min']})")
        if 'delta_max' in targets and delta > targets['delta_max']:
            violations.append(f"Delta above max ({delta:.2f} > {targets['delta_max']})")
        return violations

    def _calculate_strategy_concentration(self, risks: List[Dict], capital: float) -> Dict[str, float]:
        conc = {}
        for r in risks:
            strat = r['strategy']
            conc[strat] = conc.get(strat, 0) + r['buying_power_used'] / capital if capital > 0 else 0
        return conc