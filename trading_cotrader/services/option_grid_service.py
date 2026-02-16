"""
Option Grid Service - Grid-based option strategy builder

Design:
- Grid of strikes (rows) x expiries (columns) for a given underlying
- Each cell contains: bid, ask, mid, delta, gamma, theta, vega
- Strategy templates select multiple cells to form a position
- User can expand grid (more strikes, more expiries)

Grid Structure:
- Rows: 5 strikes above ATM, ATM, 5 strikes below ATM
- Columns: Standard expiries (5D, 7D, 30D, 45D, 1Y or nearest available)
- Separate grids for CALLS and PUTS

Flow:
1. User selects underlying from watchlist
2. Grid is populated with option data
3. User selects strategy template (vertical, iron condor, etc.)
4. Template highlights required cells
5. User can adjust by clicking cells
6. Submit creates what-if trade
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from datetime import datetime, date, timedelta
import logging

import trading_cotrader.core.models.domain as dm

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class OptionCell:
    """Single cell in the option grid"""
    underlying: str
    strike: Decimal
    expiry: date
    option_type: str  # 'C' or 'P'
    dte: int

    # Pricing
    bid: Decimal = Decimal('0')
    ask: Decimal = Decimal('0')
    mid: Decimal = Decimal('0')

    # Greeks (per contract)
    delta: Decimal = Decimal('0')
    gamma: Decimal = Decimal('0')
    theta: Decimal = Decimal('0')
    vega: Decimal = Decimal('0')
    iv: Decimal = Decimal('0')

    # Selection state
    selected: bool = False
    quantity: int = 0  # Positive = buy, Negative = sell

    @property
    def cell_id(self) -> str:
        """Unique ID for this cell"""
        return f"{self.underlying}_{self.expiry}_{self.strike}_{self.option_type}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'cell_id': self.cell_id,
            'underlying': self.underlying,
            'strike': float(self.strike),
            'expiry': self.expiry.strftime('%Y-%m-%d'),
            'option_type': self.option_type,
            'dte': self.dte,
            'bid': float(self.bid),
            'ask': float(self.ask),
            'mid': float(self.mid),
            'delta': float(self.delta),
            'gamma': float(self.gamma),
            'theta': float(self.theta),
            'vega': float(self.vega),
            'iv': float(self.iv),
            'selected': self.selected,
            'quantity': self.quantity,
        }


@dataclass
class OptionGrid:
    """Grid of options for a single underlying"""
    underlying: str
    underlying_price: Decimal
    atm_strike: Decimal

    # Grid dimensions
    strikes: List[Decimal] = field(default_factory=list)  # Sorted low to high
    expiries: List[date] = field(default_factory=list)    # Sorted near to far

    # Cells indexed by (strike, expiry, type)
    calls: Dict[Tuple[Decimal, date], OptionCell] = field(default_factory=dict)
    puts: Dict[Tuple[Decimal, date], OptionCell] = field(default_factory=dict)

    def get_cell(self, strike: Decimal, expiry: date, option_type: str) -> Optional[OptionCell]:
        """Get a cell from the grid"""
        key = (strike, expiry)
        if option_type == 'C':
            return self.calls.get(key)
        else:
            return self.puts.get(key)

    def select_cell(self, strike: Decimal, expiry: date, option_type: str, quantity: int):
        """Select/deselect a cell with quantity"""
        cell = self.get_cell(strike, expiry, option_type)
        if cell:
            cell.selected = quantity != 0
            cell.quantity = quantity

    def clear_selection(self):
        """Clear all selections"""
        for cell in self.calls.values():
            cell.selected = False
            cell.quantity = 0
        for cell in self.puts.values():
            cell.selected = False
            cell.quantity = 0

    def get_selected_cells(self) -> List[OptionCell]:
        """Get all selected cells"""
        selected = []
        for cell in self.calls.values():
            if cell.selected:
                selected.append(cell)
        for cell in self.puts.values():
            if cell.selected:
                selected.append(cell)
        return selected

    def to_dict(self) -> Dict[str, Any]:
        """Convert grid to dict for JSON serialization"""
        return {
            'underlying': self.underlying,
            'underlying_price': float(self.underlying_price),
            'atm_strike': float(self.atm_strike),
            'strikes': [float(s) for s in self.strikes],
            'expiries': [e.strftime('%Y-%m-%d') for e in self.expiries],
            'calls': [[self.calls.get((s, e)).to_dict() if self.calls.get((s, e)) else None
                       for e in self.expiries] for s in self.strikes],
            'puts': [[self.puts.get((s, e)).to_dict() if self.puts.get((s, e)) else None
                      for e in self.expiries] for s in self.strikes],
        }


# ============================================================================
# Strategy Templates
# ============================================================================

@dataclass
class StrategyLeg:
    """A leg in a strategy template"""
    option_type: str  # 'C' or 'P'
    strike_offset: int  # Relative to ATM: -2 = 2 strikes below, +1 = 1 strike above
    quantity: int  # Positive = buy, Negative = sell


@dataclass
class StrategyTemplate:
    """Template for building option strategies"""
    name: str
    strategy_type: str
    description: str
    legs: List[StrategyLeg]
    risk_category: str = 'defined'  # defined, undefined

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'strategy_type': self.strategy_type,
            'description': self.description,
            'risk_category': self.risk_category,
            'leg_count': len(self.legs),
        }


# Standard strategy templates
STRATEGY_TEMPLATES = {
    'bull_put_spread': StrategyTemplate(
        name='Bull Put Spread',
        strategy_type='vertical',
        description='Sell higher strike put, buy lower strike put',
        legs=[
            StrategyLeg(option_type='P', strike_offset=0, quantity=-1),   # Sell ATM put
            StrategyLeg(option_type='P', strike_offset=-1, quantity=1),   # Buy 1 strike below
        ],
        risk_category='defined',
    ),
    'bear_call_spread': StrategyTemplate(
        name='Bear Call Spread',
        strategy_type='vertical',
        description='Sell lower strike call, buy higher strike call',
        legs=[
            StrategyLeg(option_type='C', strike_offset=0, quantity=-1),   # Sell ATM call
            StrategyLeg(option_type='C', strike_offset=1, quantity=1),    # Buy 1 strike above
        ],
        risk_category='defined',
    ),
    'iron_condor': StrategyTemplate(
        name='Iron Condor',
        strategy_type='iron_condor',
        description='Bull put spread + bear call spread',
        legs=[
            StrategyLeg(option_type='P', strike_offset=-1, quantity=-1),  # Sell OTM put
            StrategyLeg(option_type='P', strike_offset=-2, quantity=1),   # Buy lower put
            StrategyLeg(option_type='C', strike_offset=1, quantity=-1),   # Sell OTM call
            StrategyLeg(option_type='C', strike_offset=2, quantity=1),    # Buy higher call
        ],
        risk_category='defined',
    ),
    'straddle': StrategyTemplate(
        name='Short Straddle',
        strategy_type='straddle',
        description='Sell ATM call and put',
        legs=[
            StrategyLeg(option_type='C', strike_offset=0, quantity=-1),
            StrategyLeg(option_type='P', strike_offset=0, quantity=-1),
        ],
        risk_category='undefined',
    ),
    'strangle': StrategyTemplate(
        name='Short Strangle',
        strategy_type='strangle',
        description='Sell OTM call and put',
        legs=[
            StrategyLeg(option_type='C', strike_offset=2, quantity=-1),
            StrategyLeg(option_type='P', strike_offset=-2, quantity=-1),
        ],
        risk_category='undefined',
    ),
    'call_credit_spread': StrategyTemplate(
        name='Call Credit Spread',
        strategy_type='vertical',
        description='Sell lower call, buy higher call',
        legs=[
            StrategyLeg(option_type='C', strike_offset=1, quantity=-1),
            StrategyLeg(option_type='C', strike_offset=2, quantity=1),
        ],
        risk_category='defined',
    ),
    'put_credit_spread': StrategyTemplate(
        name='Put Credit Spread',
        strategy_type='vertical',
        description='Sell higher put, buy lower put',
        legs=[
            StrategyLeg(option_type='P', strike_offset=-1, quantity=-1),
            StrategyLeg(option_type='P', strike_offset=-2, quantity=1),
        ],
        risk_category='defined',
    ),
}


# ============================================================================
# Option Grid Service
# ============================================================================

class OptionGridService:
    """
    Service for building option grids and strategies.

    Separated from TastytradeAdapter for clean architecture.
    Uses adapter's session for API calls but owns the grid logic.
    """

    def __init__(self, broker_adapter=None):
        """
        Initialize with optional broker adapter.

        Args:
            broker_adapter: TastytradeAdapter instance for API calls
        """
        self.broker = broker_adapter
        self.current_grid: Optional[OptionGrid] = None

        # Default grid configuration
        self.strikes_above_atm = 5
        self.strikes_below_atm = 5
        self.target_dtes = [5, 7, 30, 45, 365]  # Target DTEs for expiries

    def set_broker(self, broker_adapter):
        """Set or update the broker adapter"""
        self.broker = broker_adapter

    def get_strategy_templates(self) -> List[Dict[str, Any]]:
        """Get available strategy templates"""
        return [t.to_dict() for t in STRATEGY_TEMPLATES.values()]

    def build_grid(self, underlying: str,
                   underlying_price: float = None,
                   strikes_above: int = None,
                   strikes_below: int = None) -> Optional[OptionGrid]:
        """
        Build an option grid for an underlying.

        Args:
            underlying: Ticker symbol (e.g., 'SPY')
            underlying_price: Current price (if known)
            strikes_above: Number of strikes above ATM
            strikes_below: Number of strikes below ATM

        Returns:
            OptionGrid or None if failed
        """
        if not self.broker or not self.broker.session:
            logger.error("No broker session available")
            return None

        strikes_above = strikes_above or self.strikes_above_atm
        strikes_below = strikes_below or self.strikes_below_atm

        try:
            # Get option chain via broker adapter
            logger.info(f"Fetching option chain for {underlying}...")
            chain = self.broker.get_option_chain(underlying)

            if not chain:
                logger.warning(f"No options found for {underlying}")
                return None

            logger.info(f"Found {len(chain)} options for {underlying}")

            # Find ATM strike and available strikes/expiries
            all_strikes = set()
            all_expiries = set()

            # Build lookup: (strike, expiry, type) -> option with greeks
            option_lookup = {}

            for opt in chain:
                strike = Decimal(str(opt.strike_price))
                expiry = opt.expiration_date
                opt_type = opt.option_type  # 'C' or 'P'

                all_strikes.add(strike)
                all_expiries.add(expiry)

                # Store option data with Greeks if available
                key = (strike, expiry, opt_type)
                option_lookup[key] = opt

            sorted_strikes = sorted(all_strikes)
            sorted_expiries = sorted(all_expiries)

            # Determine ATM strike
            if underlying_price:
                atm_price = Decimal(str(underlying_price))
            else:
                # Use middle strike as approximation
                atm_price = sorted_strikes[len(sorted_strikes) // 2]

            # Find closest strike to ATM
            atm_strike = min(sorted_strikes, key=lambda s: abs(s - atm_price))
            atm_idx = sorted_strikes.index(atm_strike)

            # Select strikes around ATM
            start_idx = max(0, atm_idx - strikes_below)
            end_idx = min(len(sorted_strikes), atm_idx + strikes_above + 1)
            grid_strikes = sorted_strikes[start_idx:end_idx]

            # Select expiries closest to target DTEs
            today = date.today()
            grid_expiries = []
            for target_dte in self.target_dtes:
                target_date = today + timedelta(days=target_dte)
                closest = min(sorted_expiries, key=lambda e: abs((e - target_date).days))
                if closest not in grid_expiries:
                    grid_expiries.append(closest)
            grid_expiries = sorted(grid_expiries)

            # Build grid
            grid = OptionGrid(
                underlying=underlying,
                underlying_price=atm_price,
                atm_strike=atm_strike,
                strikes=grid_strikes,
                expiries=grid_expiries,
            )

            # Populate cells from option_lookup
            for strike in grid_strikes:
                for expiry in grid_expiries:
                    dte = (expiry - today).days

                    # Create PUT cell
                    put_key = (strike, expiry, 'P')
                    put_opt = option_lookup.get(put_key)
                    put_cell = OptionCell(
                        underlying=underlying,
                        strike=strike,
                        expiry=expiry,
                        option_type='P',
                        dte=dte,
                    )
                    # Populate Greeks if available from chain
                    if put_opt and hasattr(put_opt, 'greeks') and put_opt.greeks:
                        put_cell.delta = Decimal(str(put_opt.greeks.delta or 0))
                        put_cell.gamma = Decimal(str(put_opt.greeks.gamma or 0))
                        put_cell.theta = Decimal(str(put_opt.greeks.theta or 0))
                        put_cell.vega = Decimal(str(put_opt.greeks.vega or 0))
                    grid.puts[(strike, expiry)] = put_cell

                    # Create CALL cell
                    call_key = (strike, expiry, 'C')
                    call_opt = option_lookup.get(call_key)
                    call_cell = OptionCell(
                        underlying=underlying,
                        strike=strike,
                        expiry=expiry,
                        option_type='C',
                        dte=dte,
                    )
                    # Populate Greeks if available from chain
                    if call_opt and hasattr(call_opt, 'greeks') and call_opt.greeks:
                        call_cell.delta = Decimal(str(call_opt.greeks.delta or 0))
                        call_cell.gamma = Decimal(str(call_opt.greeks.gamma or 0))
                        call_cell.theta = Decimal(str(call_opt.greeks.theta or 0))
                        call_cell.vega = Decimal(str(call_opt.greeks.vega or 0))
                    grid.calls[(strike, expiry)] = call_cell

            self.current_grid = grid
            logger.info(f"Built grid: {len(grid_strikes)} strikes x {len(grid_expiries)} expiries")

            return grid

        except Exception as e:
            logger.error(f"Failed to build grid for {underlying}: {e}")
            logger.exception("Full trace:")
            return None

    def populate_greeks(self, grid: OptionGrid = None) -> bool:
        """
        Populate Greeks for all cells in the grid using DXLink streaming.

        Returns True if successful.
        """
        grid = grid or self.current_grid
        if not grid:
            logger.error("No grid to populate")
            return False

        if not self.broker:
            logger.error("No broker available")
            return False

        try:
            # Build streamer symbols for all cells
            symbols_to_cells = {}

            for (strike, expiry), cell in grid.calls.items():
                streamer_sym = self._build_streamer_symbol(
                    grid.underlying, expiry, strike, 'C'
                )
                symbols_to_cells[streamer_sym] = cell

            for (strike, expiry), cell in grid.puts.items():
                streamer_sym = self._build_streamer_symbol(
                    grid.underlying, expiry, strike, 'P'
                )
                symbols_to_cells[streamer_sym] = cell

            if not symbols_to_cells:
                return True

            # Fetch Greeks via DXLink
            logger.info(f"Fetching Greeks for {len(symbols_to_cells)} options...")
            greeks_map = self.broker._run_async(
                self.broker._fetch_greeks_via_dxlink(list(symbols_to_cells.keys()))
            )

            # Populate cells
            for sym, greeks in greeks_map.items():
                cell = symbols_to_cells.get(sym)
                if cell:
                    cell.delta = greeks.delta
                    cell.gamma = greeks.gamma
                    cell.theta = greeks.theta
                    cell.vega = greeks.vega

            logger.info(f"Populated Greeks for {len(greeks_map)} cells")
            return True

        except Exception as e:
            logger.error(f"Failed to populate Greeks: {e}")
            return False

    def _build_streamer_symbol(self, underlying: str, expiry: date,
                                strike: Decimal, opt_type: str) -> str:
        """Build DXLink streamer symbol"""
        exp_str = expiry.strftime('%y%m%d')
        strike_int = int(strike)
        return f".{underlying}{exp_str}{opt_type}{strike_int}"

    def apply_strategy(self, strategy_key: str, expiry_idx: int = 0) -> List[OptionCell]:
        """
        Apply a strategy template to the current grid.

        Args:
            strategy_key: Key from STRATEGY_TEMPLATES
            expiry_idx: Which expiry column to use (0 = nearest)

        Returns:
            List of selected cells
        """
        if not self.current_grid:
            logger.error("No grid available")
            return []

        template = STRATEGY_TEMPLATES.get(strategy_key)
        if not template:
            logger.error(f"Unknown strategy: {strategy_key}")
            return []

        grid = self.current_grid
        grid.clear_selection()

        # Find ATM index in strikes
        atm_idx = grid.strikes.index(grid.atm_strike) if grid.atm_strike in grid.strikes else len(grid.strikes) // 2

        # Get target expiry
        if expiry_idx >= len(grid.expiries):
            expiry_idx = 0
        target_expiry = grid.expiries[expiry_idx]

        # Apply each leg
        selected = []
        for leg in template.legs:
            strike_idx = atm_idx + leg.strike_offset
            if 0 <= strike_idx < len(grid.strikes):
                strike = grid.strikes[strike_idx]
                grid.select_cell(strike, target_expiry, leg.option_type, leg.quantity)
                cell = grid.get_cell(strike, target_expiry, leg.option_type)
                if cell:
                    selected.append(cell)

        logger.info(f"Applied {template.name}: {len(selected)} legs selected")
        return selected

    def get_position_summary(self) -> Dict[str, Any]:
        """Get summary of currently selected position"""
        if not self.current_grid:
            return {'error': 'No grid available'}

        selected = self.current_grid.get_selected_cells()
        if not selected:
            return {'legs': 0, 'delta': 0, 'gamma': 0, 'theta': 0, 'vega': 0, 'credit': 0}

        total_delta = Decimal('0')
        total_gamma = Decimal('0')
        total_theta = Decimal('0')
        total_vega = Decimal('0')
        total_credit = Decimal('0')

        for cell in selected:
            qty = cell.quantity
            multiplier = 100  # Options multiplier

            # Position-level Greeks
            total_delta += cell.delta * qty * multiplier
            total_gamma += cell.gamma * abs(qty) * multiplier
            total_theta += cell.theta * qty * multiplier
            total_vega += cell.vega * abs(qty) * multiplier

            # Credit/debit (selling = credit)
            if qty < 0:
                total_credit += cell.mid * abs(qty) * multiplier
            else:
                total_credit -= cell.mid * abs(qty) * multiplier

        return {
            'legs': len(selected),
            'delta': float(total_delta),
            'gamma': float(total_gamma),
            'theta': float(total_theta),
            'vega': float(total_vega),
            'credit': float(total_credit),
            'cells': [c.to_dict() for c in selected],
        }

    def expand_grid(self, direction: str, count: int = 2) -> bool:
        """
        Expand the grid in a direction.

        Args:
            direction: 'strikes_up', 'strikes_down', 'expiry_near', 'expiry_far'
            count: Number of strikes/expiries to add

        Returns:
            True if successful
        """
        # TODO: Implement grid expansion
        logger.info(f"Expanding grid: {direction} by {count}")
        return False
