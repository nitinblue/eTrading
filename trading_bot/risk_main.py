# trading_bot/risk.py
from decimal import Decimal
from typing import List, Dict
from trading_bot.positions import Position
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

    def assess_position(self, position: Position, capital: float) -> Dict:
        allocation = abs(Decimal(position.quantity) * Decimal(position.current_price) * 100) / Decimal(capital) if Decimal(capital) > 0 else 0
        pnl = position.calculate_pnl()
        pnl_driver = self._determine_pnl_driver(position)
        is_undefined_risk = 'undefined' in position.strategy.lower()
        buying_power_used = Decimal(allocation) * Decimal(capital)

        violations = []
        if allocation > self.max_allocation:
            violations.append(f"Allocation {allocation:.2%} > {self.max_allocation:.2%}")
        if pnl < -self.max_loss * capital:
            violations.append(f"Max loss ${-pnl:.2f} > {self.max_loss * capital:.2f}")

        return {
            'trade_id': getattr(position, 'trade_id', 'N/A'),
            'leg_id': getattr(position, 'leg_id', 'N/A'),
            'strategy': position.strategy,
            'symbol': position.symbol,
            'quantity': position.quantity,
            'entry_price': position.entry_price,
            'current_price': position.current_price,
            'pnl': pnl,
            'pnl_driver': pnl_driver,
            'allocation': allocation,
            'buying_power_used': buying_power_used,
            'is_undefined_risk': is_undefined_risk,
            'violations': violations,
            # New
            'volume': position.volume,
            'open_interest': position.open_interest,
            'stop_loss': position.stop_loss,
            'take_profit': position.take_profit,
            'stop_hit': position.is_stop_hit(position.current_price),
            'tp_hit': position.is_tp_hit(position.current_price),
        }

    def list_positions_api(self, positions: List[Position], capital: float) -> List[Dict]:
        """Return detailed position risk data for reporting."""
        return [self.assess_position(p, capital) for p in positions]

    def assess(self, positions: List[Position], capital: float):
        """Portfolio-level risk check — called by Portfolio.update()."""
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

    # Helper methods (unchanged)
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
        # net = {'delta': 0.0, 'gamma': 0.0, 'theta': 0.0, 'vega': 0.0, 'rho': 0.0}
        # for p in positions:
        #     for greek in net:
        #         net[greek] += Decimal(p.greeks.get(greek, 0.0)) * Decimal(p.quantity)
        # return net
        net = {g: 0.0 for g in ['delta', 'gamma', 'theta', 'vega', 'rho']}
    
        for p in positions:
         qty = float(p.quantity)
        for greek in net:
            val = p.greeks.get(greek, 0.0) or 0.0
            net[greek] += float(val) * qty
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
            conc[strat] = conc.get(strat, 0) + Decimal(r['buying_power_used']) / Decimal(capital) if Decimal(capital) > 0 else 0
        return conc