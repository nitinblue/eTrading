"""
Event Logging CLI

Thin wrapper around EventLogger service.
Just handles CLI argument parsing and display.
"""

import click
from core.database.session import session_scope
from services.event_logger import EventLogger


@click.group()
def event_cli():
    """Log trading events for AI learning"""
    pass


@event_cli.command('open-trade')
@click.option('--underlying', required=True, help='Underlying symbol (e.g. IWM)')
@click.option('--strategy', required=True, help='Strategy name (e.g. iron_condor)')
@click.option('--rationale', required=True, help='Why this trade?')
@click.option('--outlook', type=click.Choice(['bullish', 'bearish', 'neutral', 'uncertain']), 
              default='neutral', help='Market outlook')
@click.option('--confidence', type=int, default=5, help='Confidence 1-10')
@click.option('--risk', type=float, required=True, help='Max risk in dollars')
def open_trade(underlying, strategy, rationale, outlook, confidence, risk):
    """Log a trade opening event"""
    
    print("=" * 80)
    print(f"LOGGING: Trade Open - {underlying}")
    print("=" * 80)
    print()
    
    with session_scope() as session:
        event_logger = EventLogger(session)
        
        result = event_logger.log_trade_opened(
            underlying=underlying,
            strategy=strategy,
            rationale=rationale,
            outlook=outlook,
            confidence=confidence,
            max_risk=risk
        )
        
        if result.success:
            print(f"✓ Intent trade created: {result.trade_id}")
            print(f"✓ Event logged: {result.event_id}")
            print(f"\nStatus: INTENT (not yet executed)")
            print(f"Max Risk: ${risk:.2f}")
            print(f"Rationale: {rationale}")
            print(f"Outlook: {outlook}")
            print(f"Confidence: {confidence}/10")
            print("\nNext: Execute on broker, then sync to match")
        else:
            print(f"\n❌ Failed: {result.error}")


if __name__ == '__main__':
    event_cli()