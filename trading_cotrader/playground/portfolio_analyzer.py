"""
COMPLETE ARCHITECTURE - Integration Guide
==========================================

This document shows how all pieces fit together:

1. Volatility Surface (term structure data)
2. Greeks Engine (Black-Scholes calculations)
3. Functional Portfolio Engine (DAG computation)
4. Foundation for Recommendations

This is professional-grade infrastructure.
"""

from typing import List
from decimal import Decimal
from datetime import datetime, date
from decimal import Decimal
import sys
import trading_cotrader.core.models.domain as dm
# Your imports
from trading_cotrader.repositories.position import PositionRepository
from trading_cotrader.repositories.portfolio import PortfolioRepository
from trading_cotrader.core.database.session import session_scope


# New components
from trading_cotrader.analytics.greeks.engine import GreeksEngine
from trading_cotrader.analytics.volatility_surface import VolatilitySurface, VolatilitySurfaceBuilder
from trading_cotrader.analytics.functional_portfolio import (
    PortfolioAnalyzer,
    ComputationContext,
    GreeksSource,
    MarketScenario
)


# ============================================================================
# WORKFLOW 1: Daily Portfolio Analysis
# ============================================================================

def daily_portfolio_analysis(portfolio_id: str):
    """
    Daily workflow: Analyze your portfolio with proper Greeks
    
    This is what you run every morning
    """
    
    print("="*80)
    print("DAILY PORTFOLIO ANALYSIS")
    print("="*80)
    
    # Step 1: Load positions from database
    print("\n1. Loading positions...")
    with session_scope() as session:
        position_repo = PositionRepository(session)
        positions = position_repo.get_by_portfolio(portfolio_id)
    
    print(f"   ✓ Loaded {len(positions)} positions")
    
    # Step 2: Build volatility surface from positions
    print("\n2. Building volatility surface...")
    greeks_engine = GreeksEngine()
    
    # Group by underlying
    by_underlying = {}
    for pos in positions:
        ticker = pos.symbol.ticker
        if ticker not in by_underlying:
            by_underlying[ticker] = []
        by_underlying[ticker].append(pos)
    
    surfaces = {}
    for ticker, ticker_positions in by_underlying.items():
        # Get current spot price (from equity position or first option)
        spot = None
        for pos in ticker_positions:
            if pos.symbol.asset_type == dm.AssetType.EQUITY:
                spot = pos.current_price
                break
        
        if not spot and ticker_positions:
            # Estimate from first option
            spot = ticker_positions[0].symbol.strike
        
        if spot:
            surface = VolatilitySurfaceBuilder.from_positions(
                underlying=ticker,
                spot_price=spot,
                positions=ticker_positions,
                greeks_engine=greeks_engine
            )
            surfaces[ticker] = surface
            print(f"   ✓ Built {ticker} surface: {surface.summary()}")
    
    # Step 3: Analyze current state (with broker Greeks)
    print("\n3. Current State (Broker Greeks)...")
    analyzer = PortfolioAnalyzer(positions, greeks_engine)
    current = analyzer.with_broker_greeks().compute()
    
    print(f"   Total P&L:     ${current.total_pnl:,.2f}")
    print(f"   Portfolio Δ:   {current.total_delta:.2f}")
    print(f"   Portfolio Θ:   ${current.total_theta:.2f}/day")
    print(f"   Portfolio V:   {current.total_vega:.2f}")
    
    # Step 4: Analyze with volatility surface (calculated Greeks)
    print("\n4. Surface-Based Greeks...")
    if surfaces:
        # Use first surface (expand later for multi-underlying)
        primary_ticker = list(surfaces.keys())[0]
        surface_result = (analyzer
            .with_surface_greeks(surfaces[primary_ticker])
            .compute())
        
        print(f"   Portfolio Δ:   {surface_result.total_delta:.2f}")
        print(f"   Portfolio Θ:   ${surface_result.total_theta:.2f}/day")
        
        # Compare
        delta_diff = abs(current.total_delta - surface_result.total_delta)
        if delta_diff > 5:
            print(f"\n   ⚠️  DELTA MISMATCH: {delta_diff:.2f}")
            print(f"      Broker thinks: {current.total_delta:.2f}")
            print(f"      Reality is:    {surface_result.total_delta:.2f}")
            print(f"      Hidden exposure!")
    
    # Step 5: What-if scenarios
    print("\n5. Scenario Analysis...")
    scenarios = {
        'Crash (-5%)': analyzer.scenario(spy_move=-5, iv_change=0.10).compute(),
        'Rally (+3%)': analyzer.scenario(spy_move=3, iv_change=-0.05).compute(),
        'Time (7d)': analyzer.scenario(days_forward=7).compute(),
    }
    
    print(f"\n   {'Scenario':<20} {'P&L':>12} {'Delta':>8} {'Theta':>10}")
    print(f"   {'-'*20} {'-'*12} {'-'*8} {'-'*10}")
    print(f"   {'Current':<20} ${current.total_pnl:>11,.2f} {current.total_delta:>7.2f} ${current.total_theta:>9.2f}")
    
    for name, result in scenarios.items():
        print(f"   {name:<20} ${result.total_pnl:>11,.2f} {result.total_delta:>7.2f} ${result.total_theta:>9.2f}")
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    
    return {
        'current': current,
        'scenarios': scenarios,
        'surfaces': surfaces
    }


# ============================================================================
# WORKFLOW 2: Pre-Trade Analysis
# ============================================================================

def analyze_proposed_trade(
    portfolio_id: str,
    proposed_position: 'dm.Position',
    spot_price: Decimal
):
    """
    Before entering a trade: analyze impact on portfolio
    
    Usage:
        proposed = dm.Position(
            symbol=dm.Symbol(ticker='IWM', strike=210, ...),
            quantity=-2,
            ...
        )
        
        analyze_proposed_trade(portfolio_id, proposed, Decimal('209.50'))
    """
    
    print("\n" + "="*80)
    print("PRE-TRADE ANALYSIS")
    print("="*80)
    
    # Load current positions
    with session_scope() as session:
        position_repo = PositionRepository(session)
        current_positions = position_repo.get_by_portfolio(portfolio_id)
    
    # Build surface
    greeks_engine = GreeksEngine()
    surface = VolatilitySurfaceBuilder.from_positions(
        underlying=proposed_position.symbol.ticker,
        spot_price=spot_price,
        positions=current_positions,
        greeks_engine=greeks_engine
    )
    
    # Current portfolio
    analyzer_current = PortfolioAnalyzer(current_positions, greeks_engine)
    current = analyzer_current.with_surface_greeks(surface).compute()
    
    # Portfolio with proposed trade
    new_positions = current_positions + [proposed_position]
    analyzer_new = PortfolioAnalyzer(new_positions, greeks_engine)
    with_trade = analyzer_new.with_surface_greeks(surface).compute()
    
    # Impact
    delta_impact = with_trade.total_delta - current.total_delta
    theta_impact = with_trade.total_theta - current.total_theta
    
    print(f"\nCurrent Portfolio:")
    print(f"  Delta: {current.total_delta:.2f}")
    print(f"  Theta: ${current.total_theta:.2f}/day")
    
    print(f"\nProposed Trade:")
    print(f"  {proposed_position.symbol.ticker} {proposed_position.quantity}x")
    print(f"  Strike: ${proposed_position.symbol.strike}")
    
    print(f"\nAfter Trade:")
    print(f"  Delta: {with_trade.total_delta:.2f} ({delta_impact:+.2f})")
    print(f"  Theta: ${with_trade.total_theta:.2f}/day ({theta_impact:+.2f})")
    
    # Test scenarios with new trade
    print(f"\nScenario Testing:")
    scenarios = {
        'Crash -5%': analyzer_new.scenario(spy_move=-5, iv_change=0.10).compute(),
        'Rally +3%': analyzer_new.scenario(spy_move=3, iv_change=-0.05).compute(),
    }
    
    for name, result in scenarios.items():
        print(f"  {name}: ${result.total_pnl:,.2f}")
    
    # Recommendation
    print(f"\nRECOMMENDATION:")
    if abs(with_trade.total_delta) > 50:
        print(f"  ⚠️  High directional risk (Δ={with_trade.total_delta:.2f})")
    elif abs(delta_impact) > 20:
        print(f"  ⚠️  Large delta change ({delta_impact:+.2f})")
    else:
        print(f"  ✓ Risk acceptable")
    
    print("="*80)
    
    return {
        'current': current,
        'with_trade': with_trade,
        'scenarios': scenarios
    }


# ============================================================================
# WORKFLOW 3: Arbitrage Detection
# ============================================================================

def detect_arbitrage_opportunities(portfolio_id: str):
    """
    Find arbitrage opportunities by comparing broker vs calculated Greeks
    
    This is your EDGE
    """
    
    print("\n" + "="*80)
    print("ARBITRAGE DETECTION")
    print("="*80)
    
    # Load positions
    with session_scope() as session:
        position_repo = PositionRepository(session)
        positions = position_repo.get_by_portfolio(portfolio_id)
    
    # Build surface
    greeks_engine = GreeksEngine()
    
    opportunities = []
    
    for pos in positions:
        if pos.symbol.asset_type != dm.AssetType.OPTION:
            continue
        
        # Compare broker Greeks vs calculated Greeks
        broker_greeks = pos.greeks
        
        if not broker_greeks:
            continue
        
        # Calculate from surface
        try:
            # Build mini-surface for this position
            surface = VolatilitySurfaceBuilder.from_positions(
                underlying=pos.symbol.ticker,
                spot_price=pos.current_price,  # Approximate
                positions=[pos],
                greeks_engine=greeks_engine
            )
            
            # Calculate Greeks
            analyzer = PortfolioAnalyzer([pos], greeks_engine)
            calc_result = analyzer.with_surface_greeks(surface).compute()
            
            if calc_result.positions:
                calc_greeks = calc_result.positions[0].greeks
                
                # Compare
                delta_diff = abs(broker_greeks.delta - calc_greeks.delta)
                theta_diff = abs(broker_greeks.theta - calc_greeks.theta)
                
                if delta_diff > 0.10 or theta_diff > 5:
                    opportunities.append({
                        'position': pos,
                        'broker_delta': float(broker_greeks.delta),
                        'calc_delta': float(calc_greeks.delta),
                        'broker_theta': float(broker_greeks.theta),
                        'calc_theta': float(calc_greeks.theta),
                        'delta_diff': float(delta_diff),
                        'theta_diff': float(theta_diff)
                    })
        
        except Exception as e:
            logger.debug(f"Could not calculate for {pos.symbol.ticker}: {e}")
            continue
    
    # Display opportunities
    if opportunities:
        print(f"\n⚠️  Found {len(opportunities)} potential arbitrage opportunities:")
        
        for opp in opportunities:
            print(f"\n{opp['position'].symbol.ticker} ${opp['position'].symbol.strike}")
            print(f"  Delta: Broker={opp['broker_delta']:.2f}, Calc={opp['calc_delta']:.2f}, Diff={opp['delta_diff']:.2f}")
            print(f"  Theta: Broker=${opp['broker_theta']:.2f}, Calc=${opp['calc_theta']:.2f}, Diff=${opp['theta_diff']:.2f}")
            
            if opp['delta_diff'] > 0.20:
                print(f"  🚨 SIGNIFICANT DELTA MISMATCH - Hidden risk!")
    else:
        print("\n✓ No arbitrage opportunities detected")
    
    print("="*80)
    
    return opportunities


# ============================================================================
# WORKFLOW 4: Hedge Recommendations
# ============================================================================

def recommend_hedges(portfolio_id: str, target_delta: float = 0):
    """
    Recommend hedges to achieve target portfolio delta
    
    Foundation for automated hedge recommendations
    """
    
    print("\n" + "="*80)
    print("HEDGE RECOMMENDATIONS")
    print("="*80)
    
    # Load positions
    with session_scope() as session:
        position_repo = PositionRepository(session)
        positions = position_repo.get_by_portfolio(portfolio_id)
    
    # Current state
    greeks_engine = GreeksEngine()
    analyzer = PortfolioAnalyzer(positions, greeks_engine)
    current = analyzer.with_broker_greeks().compute()
    
    print(f"\nCurrent Portfolio:")
    print(f"  Delta: {current.total_delta:.2f}")
    print(f"  Target: {target_delta:.2f}")
    
    delta_to_hedge = target_delta - current.total_delta
    
    print(f"\nDelta to Hedge: {delta_to_hedge:.2f}")
    
    if abs(delta_to_hedge) < 5:
        print("  ✓ Portfolio already balanced")
        return
    
    # Recommend hedges
    print(f"\nHedge Options:")
    
    # Option 1: SPY shares
    spy_shares = int(delta_to_hedge / Decimal("1")) # Each share = 1 delta
    print(f"  1. {'Buy' if spy_shares > 0 else 'Sell'} {abs(spy_shares)} SPY shares")
    
    # Option 2: SPY options
    # Assume 0.50 delta for ATM options
    spy_contracts = int(delta_to_hedge / 50)  # 100 shares * 0.50 delta
    print(f"  2. {'Buy' if spy_contracts > 0 else 'Sell'} {abs(spy_contracts)} SPY ATM {'calls' if spy_contracts > 0 else 'puts'}")
    
    # Option 3: Adjust existing positions
    print(f"  3. Close or reduce existing positions with high delta")
    
    print("="*80)


# ============================================================================
# MAIN: Run All Workflows
# ============================================================================

if __name__ == "__main__":

    
    # Your portfolio ID (from database)
    portfolio_id = 'b08f59f1-67ee-4ffe-a270-ce0e5f8a5660'
    
    # Run workflows
    try:
        # 1. Daily analysis
        results = daily_portfolio_analysis(portfolio_id)
        
        # 2. Arbitrage detection
        opportunities = detect_arbitrage_opportunities(portfolio_id)
        
        # 3. Hedge recommendations
        recommend_hedges(portfolio_id, target_delta=0)
        
        print("\n✅ All workflows completed successfully")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import logging
        logging.exception("Full trace:")
        sys.exit(1)