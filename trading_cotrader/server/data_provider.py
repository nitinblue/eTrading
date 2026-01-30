"""
Market Data Provider - Refresh-based implementation

Fetches data from TastyTrade and builds MarketSnapshot.
Designed to be swappable with streaming implementation later.
"""

from typing import Dict, List, Optional, Protocol
from decimal import Decimal
from datetime import datetime, date
from dataclasses import dataclass
import asyncio
import logging

from contracts import (
    MarketSnapshot, MarketContext, Quote, IndexQuote, RateQuote,
    FuturesQuote, VolatilityQuote, FXQuote, PositionWithMarket,
    PositionGreeks, RiskBucket, RiskLimit, LimitBreach,
    HedgeRecommendation, HedgeInstrument, ScenarioMatrix, ScenarioResult,
    MarketRegime, VolRegime, CurveRegime,
    create_empty_snapshot, create_default_limits
)

logger = logging.getLogger(__name__)


# ============================================================================
# PROTOCOL - Interface for data providers
# ============================================================================

class DataProvider(Protocol):
    """Interface for market data providers"""
    
    async def get_snapshot(self) -> MarketSnapshot:
        """Return complete market snapshot"""
        ...
    
    async def refresh(self) -> None:
        """Force refresh of underlying data"""
        ...


# ============================================================================
# RISK AGGREGATION ENGINE
# ============================================================================

class RiskAggregator:
    """
    Aggregates position-level Greeks into risk buckets
    
    This is where institutional thinking happens:
    - Not "I have an iron condor" but "I have -150 SPY delta"
    """
    
    def aggregate_positions(
        self, 
        positions: List[PositionWithMarket],
        underlying_prices: Dict[str, Decimal]
    ) -> Dict[str, RiskBucket]:
        """
        Aggregate positions into risk buckets by underlying
        
        Returns dict: underlying -> RiskBucket
        """
        buckets: Dict[str, RiskBucket] = {}
        
        for pos in positions:
            underlying = pos.symbol
            
            if underlying not in buckets:
                buckets[underlying] = RiskBucket(underlying=underlying)
            
            bucket = buckets[underlying]
            
            # Aggregate Greeks
            bucket.delta += pos.greeks.delta
            bucket.gamma += pos.greeks.gamma
            bucket.theta += pos.greeks.theta
            bucket.vega += pos.greeks.vega
            
            # Position counts
            bucket.position_count += 1
            if pos.is_long:
                bucket.long_count += 1
            else:
                bucket.short_count += 1
            
            # Exposure
            pos_value = abs(pos.market_value)
            bucket.gross_exposure += pos_value
            if pos.is_long:
                bucket.net_exposure += pos_value
            else:
                bucket.net_exposure -= pos_value
            
            # By expiry (for options)
            if pos.expiry:
                expiry = pos.expiry
                bucket.delta_by_expiry[expiry] = bucket.delta_by_expiry.get(expiry, Decimal('0')) + pos.greeks.delta
                bucket.theta_by_expiry[expiry] = bucket.theta_by_expiry.get(expiry, Decimal('0')) + pos.greeks.theta
                bucket.vega_by_expiry[expiry] = bucket.vega_by_expiry.get(expiry, Decimal('0')) + pos.greeks.vega
        
        # Calculate dollar values
        for underlying, bucket in buckets.items():
            if underlying in underlying_prices:
                spot = underlying_prices[underlying]
                bucket.delta_dollars = bucket.delta * spot * Decimal('100')  # Options are 100 multiplier
                # Gamma dollars: P&L from 1% move due to gamma
                bucket.gamma_dollars = Decimal('0.5') * bucket.gamma * (spot * Decimal('0.01')) ** 2 * Decimal('100')
        
        return buckets
    
    def aggregate_portfolio(self, buckets: Dict[str, RiskBucket]) -> RiskBucket:
        """Create portfolio-level risk bucket from underlying buckets"""
        portfolio = RiskBucket(underlying="PORTFOLIO")
        
        for bucket in buckets.values():
            portfolio.delta += bucket.delta
            portfolio.delta_dollars += bucket.delta_dollars
            portfolio.gamma += bucket.gamma
            portfolio.gamma_dollars += bucket.gamma_dollars
            portfolio.theta += bucket.theta
            portfolio.vega += bucket.vega
            portfolio.position_count += bucket.position_count
            portfolio.long_count += bucket.long_count
            portfolio.short_count += bucket.short_count
            portfolio.gross_exposure += bucket.gross_exposure
            portfolio.net_exposure += bucket.net_exposure
        
        return portfolio
    
    def check_limits(
        self, 
        limits: List[RiskLimit],
        risk_by_underlying: Dict[str, RiskBucket],
        portfolio_risk: RiskBucket
    ) -> List[LimitBreach]:
        """Check all limits and return breaches"""
        breaches = []
        
        for limit in limits:
            # Get the relevant risk bucket
            if limit.underlying == "PORTFOLIO":
                bucket = portfolio_risk
            elif limit.underlying in risk_by_underlying:
                bucket = risk_by_underlying[limit.underlying]
            else:
                continue
            
            # Get the metric value
            current_value = getattr(bucket, limit.metric, None)
            if current_value is None:
                continue
            
            # Check breach
            if limit.is_breached(current_value):
                breach_amount = limit.breach_amount(current_value)
                
                # Determine severity
                abs_breach = abs(breach_amount)
                if limit.max_value:
                    limit_size = abs(limit.max_value - (limit.min_value or Decimal('0')))
                else:
                    limit_size = abs(limit.min_value or Decimal('100'))
                
                breach_pct = abs_breach / limit_size if limit_size else Decimal('0')
                
                if breach_pct > Decimal('0.5'):
                    severity = "critical"
                elif breach_pct > Decimal('0.2'):
                    severity = "breach"
                else:
                    severity = "warning"
                
                # Suggested action
                if breach_amount > 0:
                    action = f"Reduce {limit.underlying} {limit.metric} by {abs(breach_amount):.0f}"
                else:
                    action = f"Increase {limit.underlying} {limit.metric} by {abs(breach_amount):.0f}"
                
                breaches.append(LimitBreach(
                    limit=limit,
                    current_value=current_value,
                    breach_amount=breach_amount,
                    severity=severity,
                    suggested_action=action
                ))
        
        return breaches


# ============================================================================
# HEDGE CALCULATOR
# ============================================================================

class HedgeCalculator:
    """
    Calculates hedge recommendations to neutralize risk
    """
    
    def calculate_hedges(
        self,
        breaches: List[LimitBreach],
        risk_by_underlying: Dict[str, RiskBucket],
        underlying_prices: Dict[str, Decimal]
    ) -> List[HedgeRecommendation]:
        """
        For each breach, suggest a hedge
        """
        recommendations = []
        
        for breach in breaches:
            if breach.limit.metric == "delta":
                rec = self._hedge_delta(
                    breach, 
                    risk_by_underlying.get(breach.limit.underlying),
                    underlying_prices.get(breach.limit.underlying, Decimal('0'))
                )
                if rec:
                    recommendations.append(rec)
            
            elif breach.limit.metric == "gamma":
                rec = self._hedge_gamma(breach, risk_by_underlying.get(breach.limit.underlying))
                if rec:
                    recommendations.append(rec)
        
        return recommendations
    
    def _hedge_delta(
        self, 
        breach: LimitBreach,
        bucket: Optional[RiskBucket],
        spot_price: Decimal
    ) -> Optional[HedgeRecommendation]:
        """Hedge delta with stock"""
        if not bucket or not spot_price:
            return None
        
        # How much delta to offset
        target_delta = Decimal('0')  # Aim for neutral
        current_delta = bucket.delta
        delta_to_hedge = target_delta - current_delta
        
        # Stock has delta = 1 per share
        shares_needed = int(delta_to_hedge * 100)  # Convert from option delta to shares
        
        if shares_needed == 0:
            return None
        
        action = "buy" if shares_needed > 0 else "sell"
        
        return HedgeRecommendation(
            underlying=breach.limit.underlying,
            instrument=HedgeInstrument.STOCK,
            action=action,
            quantity=abs(shares_needed),
            estimated_price=spot_price,
            estimated_cost=spot_price * abs(shares_needed),
            delta_impact=Decimal(str(shares_needed)) / 100,  # Convert back to option delta
            resulting_delta=Decimal('0'),
            rationale=f"Neutralize {breach.limit.underlying} delta"
        )
    
    def _hedge_gamma(
        self, 
        breach: LimitBreach,
        bucket: Optional[RiskBucket]
    ) -> Optional[HedgeRecommendation]:
        """Hedge gamma with straddles (adds positive gamma)"""
        if not bucket:
            return None
        
        current_gamma = bucket.gamma
        
        # ATM straddle typically has gamma ~0.05-0.10 per contract
        # This is approximate - real implementation would price actual options
        gamma_per_straddle = Decimal('0.08')
        straddles_needed = int(abs(current_gamma) / gamma_per_straddle)
        
        if straddles_needed == 0:
            return None
        
        return HedgeRecommendation(
            underlying=breach.limit.underlying,
            instrument=HedgeInstrument.ATM_STRADDLE,
            action="buy" if current_gamma < 0 else "sell",
            quantity=straddles_needed,
            estimated_price=Decimal('10.00'),  # Placeholder
            estimated_cost=Decimal('10.00') * straddles_needed * 100,
            gamma_impact=gamma_per_straddle * straddles_needed * (-1 if current_gamma > 0 else 1),
            rationale=f"Neutralize {breach.limit.underlying} gamma with straddles"
        )


# ============================================================================
# SCENARIO ENGINE
# ============================================================================

class ScenarioEngine:
    """
    Calculates P&L under various market scenarios
    """
    
    def calculate_scenario_matrix(
        self,
        positions: List[PositionWithMarket],
        underlying: str,
        spot_price: Decimal,
        spot_moves: List[Decimal] = None,  # [-0.02, -0.01, 0, 0.01, 0.02]
        vol_moves: List[Decimal] = None    # [-2, -1, 0, 1, 2] (IV points)
    ) -> ScenarioMatrix:
        """
        Build a P&L matrix for spot vs vol scenarios
        """
        if spot_moves is None:
            spot_moves = [Decimal('-0.02'), Decimal('-0.01'), Decimal('0'), Decimal('0.01'), Decimal('0.02')]
        if vol_moves is None:
            vol_moves = [Decimal('-2'), Decimal('-1'), Decimal('0'), Decimal('1'), Decimal('2')]
        
        # Filter positions for this underlying
        relevant_positions = [p for p in positions if p.symbol == underlying]
        
        # Build matrix
        pnl_matrix = []
        
        for spot_move in spot_moves:
            row = []
            for vol_move in vol_moves:
                pnl = self._calculate_scenario_pnl(
                    relevant_positions, 
                    spot_price, 
                    spot_move, 
                    vol_move
                )
                row.append(pnl)
            pnl_matrix.append(row)
        
        return ScenarioMatrix(
            underlying=underlying,
            spot_scenarios=spot_moves,
            vol_scenarios=vol_moves,
            pnl_matrix=pnl_matrix
        )
    
    def _calculate_scenario_pnl(
        self,
        positions: List[PositionWithMarket],
        spot_price: Decimal,
        spot_move_pct: Decimal,
        vol_move_pts: Decimal
    ) -> Decimal:
        """
        Calculate P&L for a given scenario using Taylor expansion
        
        P&L ≈ Δ * dS + ½Γ * dS² + V * dσ + Θ * dt
        
        (Simplified - real implementation would reprice options)
        """
        total_pnl = Decimal('0')
        
        dS = spot_price * spot_move_pct  # Absolute price change
        dS_squared = dS * dS
        d_sigma = vol_move_pts / Decimal('100')  # Convert to decimal
        
        for pos in positions:
            # Delta P&L
            delta_pnl = pos.greeks.delta * dS * Decimal('100')  # 100 multiplier
            
            # Gamma P&L (convexity)
            gamma_pnl = Decimal('0.5') * pos.greeks.gamma * dS_squared * Decimal('100')
            
            # Vega P&L
            vega_pnl = pos.greeks.vega * vol_move_pts
            
            total_pnl += delta_pnl + gamma_pnl + vega_pnl
        
        return total_pnl


# ============================================================================
# MARKET CONTEXT BUILDER
# ============================================================================

class MarketContextBuilder:
    """
    Builds MarketContext from various data sources
    
    For now, uses mock data. Replace with real API calls.
    """
    
    def build_context(self, index_quotes: Dict[str, Quote] = None) -> MarketContext:
        """
        Build market context
        
        In production, this would fetch from:
        - TastyTrade for VIX, indices
        - Treasury API for rates
        - Commodities from futures quotes
        """
        now = datetime.utcnow()
        
        # For now, create with available data + defaults
        # This will be enhanced when we add more data sources
        
        indices = {}
        if index_quotes:
            for symbol, quote in index_quotes.items():
                indices[symbol] = IndexQuote(
                    symbol=quote.symbol,
                    bid=quote.bid,
                    ask=quote.ask,
                    last=quote.last,
                    change=quote.change,
                    change_pct=quote.change_pct,
                    volume=quote.volume
                )
        
        # Default VIX (will be replaced with real data)
        vix = VolatilityQuote(
            symbol="VIX",
            value=Decimal('14.50'),
            change=Decimal('-0.30'),
            change_pct=Decimal('-2.03'),
            term_structure="contango"
        )
        
        # Determine regimes based on available data
        vol_regime = self._classify_vol_regime(vix.value)
        market_regime = self._classify_market_regime(indices, vix.value)
        
        return MarketContext(
            timestamp=now,
            indices=indices,
            rates={},  # TODO: Add when we have rate data source
            curve_2s10s=Decimal('-35'),  # Placeholder
            move_index=Decimal('98.5'),  # Placeholder
            commodities={},  # TODO: Add when we have futures data
            vix=vix,
            vvix=VolatilityQuote(symbol="VVIX", value=Decimal('82.4'), change=Decimal('1.2'), change_pct=Decimal('1.5')),
            skew=VolatilityQuote(symbol="SKEW", value=Decimal('142'), change=Decimal('-2'), change_pct=Decimal('-1.4')),
            dxy=Decimal('103.4'),
            market_regime=market_regime,
            vol_regime=vol_regime,
            curve_regime=CurveRegime.INVERTED,
        )
    
    def _classify_vol_regime(self, vix: Decimal) -> VolRegime:
        """Classify volatility regime based on VIX level"""
        if vix < 15:
            return VolRegime.LOW_STABLE
        elif vix < 20:
            return VolRegime.LOW_RISING
        elif vix < 25:
            return VolRegime.ELEVATED
        elif vix < 35:
            return VolRegime.HIGH
        else:
            return VolRegime.CRISIS
    
    def _classify_market_regime(self, indices: Dict[str, IndexQuote], vix: Decimal) -> MarketRegime:
        """Classify market regime based on index performance and VIX"""
        if not indices:
            return MarketRegime.NEUTRAL
        
        # Simple heuristic: if most indices up and VIX down = risk on
        up_count = sum(1 for q in indices.values() if q.change_pct > 0)
        
        if up_count > len(indices) / 2 and vix < 18:
            return MarketRegime.RISK_ON
        elif up_count < len(indices) / 2 and vix > 22:
            return MarketRegime.RISK_OFF
        else:
            return MarketRegime.NEUTRAL


# ============================================================================
# REFRESH-BASED DATA PROVIDER
# ============================================================================

class RefreshBasedProvider:
    """
    Fetches fresh data from TastyTrade on each request
    
    This is the initial implementation. Can be swapped with
    StreamingProvider later without changing the UI.
    """
    
    def __init__(self, tastytrade_adapter):
        """
        Args:
            tastytrade_adapter: Instance of TastytradeAdapter
        """
        self.adapter = tastytrade_adapter
        self.risk_aggregator = RiskAggregator()
        self.hedge_calculator = HedgeCalculator()
        self.scenario_engine = ScenarioEngine()
        self.context_builder = MarketContextBuilder()
        
        self.limits = create_default_limits()
        self.refresh_count = 0
        self._last_snapshot: Optional[MarketSnapshot] = None
    
    async def get_snapshot(self) -> MarketSnapshot:
        """
        Fetch everything and build complete snapshot
        """
        try:
            # Increment refresh count
            self.refresh_count += 1
            logger.info(f"Refresh #{self.refresh_count} - Fetching data from TastyTrade...")
            
            # 1. Get positions from broker
            positions_raw = await asyncio.to_thread(self.adapter.get_positions)
            
            # 2. Get account balance
            balance = await asyncio.to_thread(self.adapter.get_account_balance)
            
            # 3. Build underlying price map
            underlying_prices = self._extract_underlying_prices(positions_raw)
            
            # 4. Convert to PositionWithMarket
            positions = self._convert_positions(positions_raw)
            
            # 5. Build market context
            index_quotes = self._build_index_quotes(underlying_prices)
            market_context = self.context_builder.build_context(index_quotes)
            
            # 6. Aggregate risk
            risk_by_underlying = self.risk_aggregator.aggregate_positions(positions, underlying_prices)
            portfolio_risk = self.risk_aggregator.aggregate_portfolio(risk_by_underlying)
            
            # 7. Check limits
            breaches = self.risk_aggregator.check_limits(self.limits, risk_by_underlying, portfolio_risk)
            
            # 8. Calculate hedges if needed
            hedge_recommendations = []
            if breaches:
                hedge_recommendations = self.hedge_calculator.calculate_hedges(
                    breaches, risk_by_underlying, underlying_prices
                )
            
            # 9. Build scenario matrices for each underlying
            scenarios = {}
            for underlying, price in underlying_prices.items():
                scenarios[underlying] = self.scenario_engine.calculate_scenario_matrix(
                    positions, underlying, price
                )
            
            # 10. Build final snapshot
            snapshot = MarketSnapshot(
                timestamp=datetime.utcnow(),
                market=market_context,
                positions=positions,
                risk_by_underlying=risk_by_underlying,
                portfolio_risk=portfolio_risk,
                limits=self.limits,
                breaches=breaches,
                hedge_recommendations=hedge_recommendations,
                scenarios=scenarios,
                account_value=balance.get('net_liquidating_value', Decimal('0')),
                buying_power=balance.get('derivative_buying_power', Decimal('0')),
                margin_used=balance.get('maintenance_excess', Decimal('0')),
                data_source="tastytrade",
                is_live=False,
                refresh_count=self.refresh_count
            )
            
            self._last_snapshot = snapshot
            logger.info(f"Refresh #{self.refresh_count} complete: {len(positions)} positions, {len(breaches)} breaches")
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error fetching snapshot: {e}")
            # Return last known snapshot or empty
            if self._last_snapshot:
                return self._last_snapshot
            return create_empty_snapshot()
    
    async def refresh(self) -> None:
        """Force refresh - just calls get_snapshot"""
        await self.get_snapshot()
    
    def _extract_underlying_prices(self, positions) -> Dict[str, Decimal]:
        """Extract underlying prices from positions"""
        prices = {}
        for pos in positions:
            ticker = pos.symbol.ticker
            if ticker not in prices:
                # Use current price as proxy for underlying
                # In production, would fetch actual underlying quotes
                if pos.symbol.asset_type.value == 'option':
                    # For options, we need to get underlying price separately
                    # For now, use a placeholder based on strike
                    prices[ticker] = pos.symbol.strike or Decimal('100')
                else:
                    prices[ticker] = pos.current_price
        return prices
    
    def _convert_positions(self, positions_raw) -> List[PositionWithMarket]:
        """Convert domain Position objects to PositionWithMarket"""
        positions = []
        
        for pos in positions_raw:
            symbol = pos.symbol
            
            # Calculate DTE if option
            dte = None
            if symbol.expiration:
                dte = (symbol.expiration.date() - date.today()).days
            
            # Build Greeks
            greeks = PositionGreeks()
            if pos.greeks:
                greeks = PositionGreeks(
                    delta=pos.greeks.delta or Decimal('0'),
                    gamma=pos.greeks.gamma or Decimal('0'),
                    theta=pos.greeks.theta or Decimal('0'),
                    vega=pos.greeks.vega or Decimal('0'),
                    rho=pos.greeks.rho or Decimal('0')
                )
            
            # Calculate P&L
            entry_value = pos.entry_price * abs(pos.quantity) * symbol.multiplier
            market_value = pos.current_price * abs(pos.quantity) * symbol.multiplier
            
            # For short positions, P&L is inverted
            if pos.quantity < 0:
                unrealized_pnl = entry_value - market_value
            else:
                unrealized_pnl = market_value - entry_value
            
            unrealized_pnl_pct = (unrealized_pnl / entry_value * 100) if entry_value else Decimal('0')
            
            pwm = PositionWithMarket(
                position_id=pos.broker_position_id or str(id(pos)),
                symbol=symbol.ticker,
                option_type=symbol.option_type.value if symbol.option_type else None,
                strike=symbol.strike,
                expiry=symbol.expiration.strftime('%Y-%m-%d') if symbol.expiration else None,
                dte=dte,
                quantity=pos.quantity,
                entry_price=pos.entry_price,
                bid=pos.current_price * Decimal('0.98'),  # Estimate - would come from quote
                ask=pos.current_price * Decimal('1.02'),  # Estimate
                last=pos.current_price,
                mark=pos.current_price,
                greeks=greeks,
                iv=Decimal('0.20'),  # Placeholder - would come from Greeks stream
                entry_value=entry_value,
                market_value=market_value,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_pct=unrealized_pnl_pct
            )
            
            positions.append(pwm)
        
        return positions
    
    def _build_index_quotes(self, underlying_prices: Dict[str, Decimal]) -> Dict[str, Quote]:
        """Build quote objects for underlyings we have positions in"""
        quotes = {}
        for symbol, price in underlying_prices.items():
            quotes[symbol] = Quote(
                symbol=symbol,
                bid=price * Decimal('0.999'),
                ask=price * Decimal('1.001'),
                last=price,
                change=Decimal('0'),  # Would need prior close
                change_pct=Decimal('0')
            )
        return quotes
    
    def set_limits(self, limits: List[RiskLimit]) -> None:
        """Update risk limits"""
        self.limits = limits


# ============================================================================
# MOCK PROVIDER (for testing without broker)
# ============================================================================

class MockDataProvider:
    """
    Returns mock data - useful for UI development
    """
    
    def __init__(self):
        self.risk_aggregator = RiskAggregator()
        self.hedge_calculator = HedgeCalculator()
        self.scenario_engine = ScenarioEngine()
        self.context_builder = MarketContextBuilder()
        self.limits = create_default_limits()
        self.refresh_count = 0
    
    async def get_snapshot(self) -> MarketSnapshot:
        """Return mock snapshot"""
        self.refresh_count += 1
        
        # Mock positions
        positions = self._create_mock_positions()
        
        # Mock underlying prices
        underlying_prices = {
            'SPY': Decimal('588.25'),
            'QQQ': Decimal('508.20'),
            'IWM': Decimal('221.50')
        }
        
        # Build index quotes
        index_quotes = {
            'SPY': Quote(symbol='SPY', bid=Decimal('588.24'), ask=Decimal('588.26'), 
                        last=Decimal('588.25'), change=Decimal('2.75'), change_pct=Decimal('0.47')),
            'QQQ': Quote(symbol='QQQ', bid=Decimal('508.18'), ask=Decimal('508.22'),
                        last=Decimal('508.20'), change=Decimal('3.12'), change_pct=Decimal('0.62')),
        }
        
        # Build market context
        market_context = self.context_builder.build_context(index_quotes)
        
        # Aggregate risk
        risk_by_underlying = self.risk_aggregator.aggregate_positions(positions, underlying_prices)
        portfolio_risk = self.risk_aggregator.aggregate_portfolio(risk_by_underlying)
        
        # Check limits
        breaches = self.risk_aggregator.check_limits(self.limits, risk_by_underlying, portfolio_risk)
        
        # Hedges
        hedge_recommendations = []
        if breaches:
            hedge_recommendations = self.hedge_calculator.calculate_hedges(
                breaches, risk_by_underlying, underlying_prices
            )
        
        # Scenarios
        scenarios = {}
        for underlying, price in underlying_prices.items():
            if underlying in risk_by_underlying:
                scenarios[underlying] = self.scenario_engine.calculate_scenario_matrix(
                    positions, underlying, price
                )
        
        return MarketSnapshot(
            timestamp=datetime.utcnow(),
            market=market_context,
            positions=positions,
            risk_by_underlying=risk_by_underlying,
            portfolio_risk=portfolio_risk,
            limits=self.limits,
            breaches=breaches,
            hedge_recommendations=hedge_recommendations,
            scenarios=scenarios,
            account_value=Decimal('125000'),
            buying_power=Decimal('85000'),
            margin_used=Decimal('15000'),
            data_source="mock",
            is_live=False,
            refresh_count=self.refresh_count
        )
    
    async def refresh(self) -> None:
        pass
    
    def _create_mock_positions(self) -> List[PositionWithMarket]:
        """Create mock positions representing a typical portfolio"""
        return [
            # SPY Iron Condor
            PositionWithMarket(
                position_id="1", symbol="SPY", option_type="CALL", strike=Decimal('600'),
                expiry="2026-01-31", dte=5, quantity=-1,
                entry_price=Decimal('0.85'), bid=Decimal('0.41'), ask=Decimal('0.43'),
                last=Decimal('0.42'), mark=Decimal('0.42'),
                greeks=PositionGreeks(delta=Decimal('-8'), gamma=Decimal('-1'), theta=Decimal('4'), vega=Decimal('-6')),
                iv=Decimal('0.16'),
                entry_value=Decimal('85'), market_value=Decimal('42'),
                unrealized_pnl=Decimal('43'), unrealized_pnl_pct=Decimal('50.59')
            ),
            PositionWithMarket(
                position_id="2", symbol="SPY", option_type="CALL", strike=Decimal('605'),
                expiry="2026-01-31", dte=5, quantity=1,
                entry_price=Decimal('0.45'), bid=Decimal('0.17'), ask=Decimal('0.19'),
                last=Decimal('0.18'), mark=Decimal('0.18'),
                greeks=PositionGreeks(delta=Decimal('3'), gamma=Decimal('0.5'), theta=Decimal('-2'), vega=Decimal('3')),
                iv=Decimal('0.15'),
                entry_value=Decimal('45'), market_value=Decimal('18'),
                unrealized_pnl=Decimal('-27'), unrealized_pnl_pct=Decimal('-60')
            ),
            PositionWithMarket(
                position_id="3", symbol="SPY", option_type="PUT", strike=Decimal('570'),
                expiry="2026-01-31", dte=5, quantity=-1,
                entry_price=Decimal('0.95'), bid=Decimal('0.54'), ask=Decimal('0.56'),
                last=Decimal('0.55'), mark=Decimal('0.55'),
                greeks=PositionGreeks(delta=Decimal('6'), gamma=Decimal('-1'), theta=Decimal('5'), vega=Decimal('-7')),
                iv=Decimal('0.17'),
                entry_value=Decimal('95'), market_value=Decimal('55'),
                unrealized_pnl=Decimal('40'), unrealized_pnl_pct=Decimal('42.11')
            ),
            PositionWithMarket(
                position_id="4", symbol="SPY", option_type="PUT", strike=Decimal('565'),
                expiry="2026-01-31", dte=5, quantity=1,
                entry_price=Decimal('0.60'), bid=Decimal('0.29'), ask=Decimal('0.31'),
                last=Decimal('0.30'), mark=Decimal('0.30'),
                greeks=PositionGreeks(delta=Decimal('-2'), gamma=Decimal('0.4'), theta=Decimal('-2'), vega=Decimal('3')),
                iv=Decimal('0.16'),
                entry_value=Decimal('60'), market_value=Decimal('30'),
                unrealized_pnl=Decimal('-30'), unrealized_pnl_pct=Decimal('-50')
            ),
            # QQQ Put Spread
            PositionWithMarket(
                position_id="5", symbol="QQQ", option_type="PUT", strike=Decimal('495'),
                expiry="2026-01-31", dte=5, quantity=-1,
                entry_price=Decimal('1.80'), bid=Decimal('0.94'), ask=Decimal('0.96'),
                last=Decimal('0.95'), mark=Decimal('0.95'),
                greeks=PositionGreeks(delta=Decimal('10'), gamma=Decimal('-1'), theta=Decimal('6'), vega=Decimal('-9')),
                iv=Decimal('0.18'),
                entry_value=Decimal('180'), market_value=Decimal('95'),
                unrealized_pnl=Decimal('85'), unrealized_pnl_pct=Decimal('47.22')
            ),
            PositionWithMarket(
                position_id="6", symbol="QQQ", option_type="PUT", strike=Decimal('490'),
                expiry="2026-01-31", dte=5, quantity=1,
                entry_price=Decimal('0.30'), bid=Decimal('0.09'), ask=Decimal('0.11'),
                last=Decimal('0.10'), mark=Decimal('0.10'),
                greeks=PositionGreeks(delta=Decimal('-2'), gamma=Decimal('0.3'), theta=Decimal('-1'), vega=Decimal('2')),
                iv=Decimal('0.17'),
                entry_value=Decimal('30'), market_value=Decimal('10'),
                unrealized_pnl=Decimal('-20'), unrealized_pnl_pct=Decimal('-66.67')
            ),
        ]
