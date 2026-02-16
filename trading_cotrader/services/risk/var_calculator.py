"""
Value at Risk (VaR) Calculator

Provides multiple methods for calculating portfolio VaR:
- Parametric (delta-normal): Fast, assumes normal returns, uses delta-equivalent exposures
- Historical simulation: Uses actual past returns, captures fat tails
- Incremental VaR: How much risk does adding a trade contribute?

VaR answers: "What's the maximum loss at X% confidence over Y days?"

For an options portfolio, positions are converted to delta-equivalent
stock exposures before VaR calculation. This is the standard
delta-normal approach used on institutional trading floors.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Tuple
import logging
import numpy as np

from trading_cotrader.services.risk.correlation import CorrelationAnalyzer, _fetch_returns

logger = logging.getLogger(__name__)


class VaRMethod(Enum):
    """VaR calculation methods"""
    PARAMETRIC = "parametric"          # Delta-normal (variance-covariance)
    HISTORICAL = "historical"          # Uses actual historical returns
    MONTE_CARLO = "monte_carlo"        # Simulates many scenarios


@dataclass
class VaRContribution:
    """How much each underlying contributes to portfolio VaR"""
    symbol: str
    delta_exposure: float          # Dollar delta exposure to this underlying
    standalone_var: Decimal         # VaR of this underlying alone
    percent_of_total: float         # % contribution to portfolio VaR
    marginal_var: Decimal           # How much VaR increases by adding this position


@dataclass
class VaRResult:
    """
    Result of VaR calculation

    VaR of $10,000 at 95% confidence means:
    "We are 95% confident the portfolio won't lose more than $10,000 in the given period"
    """
    # Core result
    var_amount: Decimal              # Absolute VaR in dollars
    var_percent: Decimal             # VaR as % of portfolio value

    # Parameters used
    confidence_level: float          # e.g., 0.95 for 95%
    horizon_days: int                # e.g., 1 for 1-day VaR
    method: VaRMethod

    # Breakdown
    contributions: List[VaRContribution] = field(default_factory=list)

    # Context
    portfolio_value: Decimal = Decimal('0')
    calculation_time: datetime = field(default_factory=datetime.utcnow)

    # Additional metrics
    expected_shortfall: Optional[Decimal] = None  # CVaR - average loss beyond VaR
    data_source: str = "yfinance"  # or "fallback_estimates"

    def __str__(self) -> str:
        return (
            f"VaR({self.method.value}): ${self.var_amount:,.2f} "
            f"({self.var_percent:.2f}%) at {self.confidence_level*100:.0f}% confidence, "
            f"{self.horizon_days}-day horizon"
        )


def _extract_exposures(positions: List) -> Dict[str, float]:
    """
    Extract delta-dollar exposures per underlying from positions.

    For options: exposure = per_contract_delta * quantity * multiplier * underlying_price
    For equity: exposure = quantity * current_price

    Returns:
        Dict of {ticker: total_delta_dollar_exposure}
    """
    exposures: Dict[str, float] = {}

    for pos in positions:
        symbol = getattr(pos, 'symbol', None)
        if not symbol:
            continue

        ticker = symbol.ticker
        quantity = getattr(pos, 'quantity', 0)
        if quantity == 0:
            continue

        if getattr(symbol, 'is_option', False):
            # Option position: delta-equivalent exposure
            greeks = getattr(pos, 'current_greeks', None)
            if not greeks:
                # Try greeks list (last entry)
                greeks_list = getattr(pos, 'greeks', [])
                greeks = greeks_list[-1] if greeks_list else None
            if not greeks:
                continue

            delta = float(getattr(greeks, 'delta', 0))
            multiplier = getattr(symbol, 'multiplier', 100)
            underlying_price = float(
                getattr(pos, 'current_underlying_price', 0) or
                getattr(pos, 'entry_underlying_price', 0) or 0
            )

            if underlying_price == 0:
                # Estimate from market value if available
                mv = float(getattr(pos, 'market_value', 0))
                if mv != 0 and abs(delta) > 0.01:
                    underlying_price = abs(mv) / (abs(delta) * abs(quantity) * multiplier)

            exposure = delta * quantity * multiplier * underlying_price
        else:
            # Equity position: full notional
            price = float(
                getattr(pos, 'current_price', 0) or
                getattr(pos, 'entry_price', 0) or 0
            )
            exposure = quantity * price

        exposures[ticker] = exposures.get(ticker, 0.0) + exposure

    return exposures


class VaRCalculator:
    """
    Calculate Value at Risk for a portfolio.

    Uses delta-normal approach for options:
    1. Convert all positions to delta-equivalent stock exposures
    2. Fetch historical returns from yfinance
    3. Compute covariance matrix
    4. Apply parametric or historical VaR formula

    Usage:
        calculator = VaRCalculator()

        # Parametric VaR (fastest, assumes normal distribution)
        result = calculator.calculate_parametric_var(positions, portfolio_value, confidence=0.95)

        # Historical VaR (uses actual past returns, captures fat tails)
        result = calculator.calculate_historical_var(positions, portfolio_value, lookback_days=252)

        # Incremental VaR (how much risk does a new trade add?)
        before, after, change = calculator.calculate_incremental_var(positions, new_trade, value)
    """

    def __init__(self, market_data_provider=None):
        self.market_data = market_data_provider
        self._correlation_analyzer = CorrelationAnalyzer(market_data_provider)

    def calculate_parametric_var(
        self,
        positions: List,
        portfolio_value: Decimal,
        confidence: float = 0.95,
        horizon_days: int = 1
    ) -> VaRResult:
        """
        Calculate VaR using parametric (delta-normal / variance-covariance) method.

        Steps:
        1. Extract delta-dollar exposures per underlying
        2. Fetch historical returns → covariance matrix
        3. Portfolio variance = w' * Σ * w
        4. VaR = z_score * sqrt(portfolio_variance) * sqrt(horizon_days)

        Args:
            positions: List of Position objects
            portfolio_value: Total portfolio value
            confidence: Confidence level (0.95 = 95%)
            horizon_days: Time horizon in days

        Returns:
            VaRResult with VaR amount and per-underlying breakdown
        """
        logger.info(f"Calculating parametric VaR for {len(positions)} positions")

        # Step 1: Extract delta-dollar exposures
        exposures = _extract_exposures(positions)

        if not exposures:
            return self._empty_result(portfolio_value, confidence, horizon_days, VaRMethod.PARAMETRIC)

        tickers = list(exposures.keys())
        exposure_vec = np.array([exposures[t] for t in tickers])

        # Step 2: Get correlation matrix (includes covariance + volatilities)
        corr_matrix = self._correlation_analyzer.calculate_correlation_matrix(tickers)
        data_source = "yfinance" if corr_matrix.covariance_matrix is not None else "fallback_estimates"

        # Step 3: Build daily covariance matrix
        if corr_matrix.covariance_matrix is not None and len(corr_matrix.symbols) == len(tickers):
            # Use real covariance from yfinance returns
            # Reorder to match our ticker order
            cov_daily = self._reorder_covariance(corr_matrix, tickers)
        else:
            # Build from volatilities + correlations
            cov_daily = self._build_covariance_from_vol_corr(tickers, corr_matrix)

        # Step 4: Portfolio variance = w' * Σ * w (where w is exposure vector)
        portfolio_variance = float(exposure_vec @ cov_daily @ exposure_vec)
        portfolio_std = np.sqrt(max(portfolio_variance, 0))

        # Step 5: Apply z-score and time scaling
        z = self._get_z_score(confidence)
        var_amount = portfolio_std * z * np.sqrt(horizon_days)

        # Step 6: Expected Shortfall (CVaR) — for normal distribution: ES = σ * φ(z) / (1-α)
        # where φ is standard normal PDF
        from scipy.stats import norm
        es_amount = portfolio_std * norm.pdf(z) / (1 - confidence) * np.sqrt(horizon_days)

        # Step 7: Per-underlying contributions
        contributions = self._calculate_contributions(
            tickers, exposure_vec, cov_daily, var_amount, z, horizon_days
        )

        var_decimal = Decimal(str(round(var_amount, 2)))
        pv = float(portfolio_value) if portfolio_value else 1
        var_pct = Decimal(str(round(var_amount / pv * 100, 4))) if pv > 0 else Decimal('0')

        return VaRResult(
            var_amount=var_decimal,
            var_percent=var_pct,
            confidence_level=confidence,
            horizon_days=horizon_days,
            method=VaRMethod.PARAMETRIC,
            contributions=contributions,
            portfolio_value=portfolio_value,
            expected_shortfall=Decimal(str(round(es_amount, 2))),
            data_source=data_source
        )

    def calculate_historical_var(
        self,
        positions: List,
        portfolio_value: Decimal,
        lookback_days: int = 252,
        confidence: float = 0.95,
        horizon_days: int = 1
    ) -> VaRResult:
        """
        Calculate VaR using historical simulation.

        Uses actual historical returns — no distribution assumption.
        Better for fat tails but needs good historical data.

        Steps:
        1. Extract delta-dollar exposures per underlying
        2. Fetch historical returns
        3. For each historical day, compute portfolio P&L
        4. Sort P&Ls, find the percentile = VaR

        Args:
            positions: List of Position objects
            portfolio_value: Total portfolio value
            lookback_days: Days of history to use
            confidence: Confidence level
            horizon_days: Time horizon

        Returns:
            VaRResult with VaR amount
        """
        logger.info(f"Calculating historical VaR using {lookback_days} days of history")

        exposures = _extract_exposures(positions)
        if not exposures:
            return self._empty_result(portfolio_value, confidence, horizon_days, VaRMethod.HISTORICAL)

        tickers = list(exposures.keys())
        exposure_vec = np.array([exposures[t] for t in tickers])

        # Fetch historical returns
        returns_data = _fetch_returns(tickers, lookback_days)
        if not returns_data:
            logger.warning("No historical data available, falling back to parametric VaR")
            return self.calculate_parametric_var(positions, portfolio_value, confidence, horizon_days)

        # Align returns to common dates
        valid_tickers = [t for t in tickers if t in returns_data]
        if not valid_tickers:
            return self._empty_result(portfolio_value, confidence, horizon_days, VaRMethod.HISTORICAL)

        min_len = min(len(returns_data[t]) for t in valid_tickers)
        aligned_returns = np.column_stack([returns_data[t][-min_len:] for t in valid_tickers])
        valid_exposures = np.array([exposures[t] for t in valid_tickers])

        # Compute historical portfolio P&Ls: each day's P&L = sum(exposure_i * return_i)
        daily_pnls = aligned_returns @ valid_exposures

        # Scale for horizon
        if horizon_days > 1:
            # Use overlapping windows for multi-day VaR
            if len(daily_pnls) >= horizon_days:
                multi_day_pnls = np.array([
                    np.sum(daily_pnls[i:i + horizon_days])
                    for i in range(len(daily_pnls) - horizon_days + 1)
                ])
            else:
                multi_day_pnls = daily_pnls * np.sqrt(horizon_days)
        else:
            multi_day_pnls = daily_pnls

        # VaR = negative of the percentile (losses are negative)
        percentile = (1 - confidence) * 100
        var_amount = -np.percentile(multi_day_pnls, percentile)
        var_amount = max(var_amount, 0)  # VaR is positive

        # Expected Shortfall = average of losses beyond VaR
        threshold = np.percentile(multi_day_pnls, percentile)
        tail_losses = multi_day_pnls[multi_day_pnls <= threshold]
        es_amount = -np.mean(tail_losses) if len(tail_losses) > 0 else var_amount

        var_decimal = Decimal(str(round(var_amount, 2)))
        pv = float(portfolio_value) if portfolio_value else 1
        var_pct = Decimal(str(round(var_amount / pv * 100, 4))) if pv > 0 else Decimal('0')

        return VaRResult(
            var_amount=var_decimal,
            var_percent=var_pct,
            confidence_level=confidence,
            horizon_days=horizon_days,
            method=VaRMethod.HISTORICAL,
            portfolio_value=portfolio_value,
            expected_shortfall=Decimal(str(round(es_amount, 2))),
            data_source="yfinance"
        )

    def calculate_incremental_var(
        self,
        current_positions: List,
        proposed_trade,
        portfolio_value: Decimal,
        confidence: float = 0.95,
        horizon_days: int = 1
    ) -> Tuple[VaRResult, VaRResult, Decimal]:
        """
        Calculate how a proposed trade affects portfolio VaR.

        Critical for pre-trade risk assessment:
        - VaR before the trade
        - VaR after adding the trade
        - Incremental VaR (the difference)

        The proposed_trade can be:
        - A Trade domain object (has legs with greeks)
        - A Position object (has symbol, quantity, greeks)
        - A list of Position objects

        Args:
            current_positions: Existing portfolio positions
            proposed_trade: Trade/Position being considered
            portfolio_value: Current portfolio value
            confidence: Confidence level
            horizon_days: Time horizon

        Returns:
            Tuple of (VaR_before, VaR_after, incremental_VaR)
        """
        # Calculate current VaR
        var_before = self.calculate_parametric_var(
            current_positions, portfolio_value, confidence, horizon_days
        )

        # Convert proposed trade to positions and combine
        new_positions = self._trade_to_positions(proposed_trade)
        combined_positions = list(current_positions) + new_positions

        # Estimate new portfolio value (rough: add/subtract trade market value)
        trade_value = sum(
            abs(getattr(p, 'market_value', Decimal('0')))
            for p in new_positions
        )
        new_portfolio_value = portfolio_value + trade_value

        var_after = self.calculate_parametric_var(
            combined_positions, new_portfolio_value, confidence, horizon_days
        )

        incremental = var_after.var_amount - var_before.var_amount

        return var_before, var_after, incremental

    def calculate_expected_shortfall(
        self,
        var_result: VaRResult,
        positions: List
    ) -> Decimal:
        """
        Calculate Expected Shortfall (CVaR) — average loss beyond VaR.

        If already computed during VaR calculation, returns that value.
        Otherwise recalculates using historical method.
        """
        if var_result.expected_shortfall is not None:
            return var_result.expected_shortfall

        # Recalculate using historical method
        hist_result = self.calculate_historical_var(
            positions,
            var_result.portfolio_value,
            lookback_days=252,
            confidence=var_result.confidence_level,
            horizon_days=var_result.horizon_days
        )
        return hist_result.expected_shortfall or var_result.var_amount

    # ========================================================================
    # Internal helpers
    # ========================================================================

    def _reorder_covariance(self, corr_matrix, tickers: List[str]) -> np.ndarray:
        """Reorder covariance matrix to match ticker order."""
        n = len(tickers)
        cov = np.zeros((n, n))
        for i, t1 in enumerate(tickers):
            for j, t2 in enumerate(tickers):
                c = corr_matrix.get_covariance(t1, t2)
                if c is not None:
                    cov[i, j] = c
                elif i == j:
                    # Diagonal: use volatility squared / 252
                    vol = corr_matrix.get_volatility(t1) or 0.25
                    cov[i, j] = (vol ** 2) / 252
                else:
                    # Cross-term: estimate from vols + correlation
                    vol_i = corr_matrix.get_volatility(t1) or 0.25
                    vol_j = corr_matrix.get_volatility(t2) or 0.25
                    rho = corr_matrix.get_correlation(t1, t2) or 0.5
                    cov[i, j] = rho * vol_i * vol_j / 252
        return cov

    def _build_covariance_from_vol_corr(
        self,
        tickers: List[str],
        corr_matrix
    ) -> np.ndarray:
        """Build covariance matrix from individual volatilities and correlations."""
        n = len(tickers)
        cov = np.zeros((n, n))
        for i, t1 in enumerate(tickers):
            vol_i = (corr_matrix.get_volatility(t1) or 0.25) / np.sqrt(252)  # Daily vol
            for j, t2 in enumerate(tickers):
                vol_j = (corr_matrix.get_volatility(t2) or 0.25) / np.sqrt(252)
                if i == j:
                    cov[i, j] = vol_i ** 2
                else:
                    rho = corr_matrix.get_correlation(t1, t2) or 0.5
                    cov[i, j] = rho * vol_i * vol_j
        return cov

    def _calculate_contributions(
        self,
        tickers: List[str],
        exposure_vec: np.ndarray,
        cov_daily: np.ndarray,
        total_var: float,
        z_score: float,
        horizon_days: int
    ) -> List[VaRContribution]:
        """Calculate per-underlying VaR contributions."""
        contributions = []
        portfolio_variance = float(exposure_vec @ cov_daily @ exposure_vec)
        portfolio_std = np.sqrt(max(portfolio_variance, 0))

        for i, ticker in enumerate(tickers):
            # Standalone VaR for this underlying
            standalone_var = abs(exposure_vec[i]) * np.sqrt(cov_daily[i, i]) * z_score * np.sqrt(horizon_days)

            # Component VaR: how much this position contributes to total portfolio VaR
            # Component VaR_i = (Σ * w)_i * w_i / portfolio_std * z * sqrt(t)
            if portfolio_std > 0:
                marginal = float(cov_daily[i, :] @ exposure_vec) * exposure_vec[i]
                component_var = marginal / portfolio_std * z_score * np.sqrt(horizon_days)
                pct = component_var / total_var * 100 if total_var > 0 else 0
            else:
                component_var = 0
                pct = 0

            contributions.append(VaRContribution(
                symbol=ticker,
                delta_exposure=float(exposure_vec[i]),
                standalone_var=Decimal(str(round(standalone_var, 2))),
                percent_of_total=round(pct, 2),
                marginal_var=Decimal(str(round(component_var, 2)))
            ))

        # Sort by contribution descending
        contributions.sort(key=lambda c: abs(float(c.marginal_var)), reverse=True)
        return contributions

    def _trade_to_positions(self, trade) -> List:
        """
        Convert a Trade object (or similar) to a list of position-like objects.

        Handles:
        - Trade with legs
        - A single Position
        - A list of Positions
        """
        if isinstance(trade, list):
            return trade

        # Check if it's a Position-like object (has symbol, quantity)
        if hasattr(trade, 'symbol') and hasattr(trade, 'quantity'):
            return [trade]

        # Check if it's a Trade with legs
        legs = getattr(trade, 'legs', None)
        if legs:
            return list(legs)

        return []

    def _empty_result(
        self,
        portfolio_value: Decimal,
        confidence: float,
        horizon_days: int,
        method: VaRMethod
    ) -> VaRResult:
        """Return zero VaR result when no positions."""
        return VaRResult(
            var_amount=Decimal('0'),
            var_percent=Decimal('0'),
            confidence_level=confidence,
            horizon_days=horizon_days,
            method=method,
            portfolio_value=portfolio_value,
            data_source="none"
        )

    def _get_z_score(self, confidence: float) -> float:
        """Get z-score for given confidence level."""
        z_scores = {
            0.90: 1.282,
            0.95: 1.645,
            0.99: 2.326,
        }
        if confidence in z_scores:
            return z_scores[confidence]
        # General case using scipy
        try:
            from scipy.stats import norm
            return float(norm.ppf(confidence))
        except ImportError:
            return 1.645  # Default to 95%
