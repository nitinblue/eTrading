# PROJECT STATUS - January 26, 2026

## Session Summary: WhatIf Integration

### What Was Done This Session

┌─────────────────────────────────────────────────────────┐
│                    BROWSER (React)                       │
│  ┌───────────────────────────────────────────────── ┐    │
│  │              AG Grid / Custom Grid               │    │
│  │  ┌─────────┬─────────┬─────────┬─────────┐       │    │
│  │  │ Cell A1 │ Cell B1 │ Cell C1 │ Cell D1 │       │    │
│  │  │ [Trade] │ [Value] │ [Computed]│[WhatIf]│      │    │
│  │  └─────────┴─────────┴─────────┴─────────┘       │    │
│  │  Cells hold OBJECT REFERENCES, not just values   │    │
│  └───────────────────────────────────────────────── ┘    │
│                          │                               │
│                   WebSocket + REST                       │
└──────────────────────────┼──────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────-┐
│                    FastAPI Backend                       │
│  ┌─────────────────────────────────────────────────┐     │
│  │              Object Store (In-Memory)            │    │
│  │  portfolios: Dict[str, Portfolio]                │    │
│  │  trades: Dict[str, Trade]                        │    │
│  │  positions: Dict[str, Position]                  │    │
│  │  whatifs: Dict[str, WhatIfScenario]              │    │
│  └─────────────────────────────────────────────────┘     │
│                          │                               │
│  ┌─────────────────────────────────────────────────┐     │
│  │              Object Operations                   │    │
│  │  POST /trades/{id}/execute  → trade.mark_executed()   │
│  │  POST /trades/{id}/close    → trade.mark_closed()     │
│  │  GET  /trades/{id}/pnl      → trade.get_pnl_attribution()
│  │  POST /whatif/evaluate      → engine.evaluate()       │
│  └─────────────────────────────────────────────────┘     │
│                          │                               │
│                    SQLite (Persistence)                  │
└─────────────────────────────────────────────────────────┘

UI Design Decision
What Makes Trading Software Compelling (Commercializable)
FeatureThinkorswim/TastyTradeYour VisionMost Trading AppsObjects in UI❌ Values only✅ First-class objects❌ Values onlyWhat-If as Object❌ Separate tool✅ Same as real trade❌ Separate/noneP&L Attribution❌ Basic✅ By Greek❌ NoneCustom Risk Limits⚠️ Limited✅ Per-portfolio❌ FixedWorkspace vs Dashboard❌ Fixed widgets✅ Grid workspace❌ Fixed

Your differentiator: Objects that behave, not just values that display.

100. Claude reflects.
   Key Insight: Objects Live in Backend, UI Holds References
   The grid cell doesn't hold the Trade object - it holds a reference (trade_id) and the rendered view. When you click, it calls the backend to get the full object and its methods.
   typescript// Frontend Cell
   interface GridCell {
   objectType: 'trade' | 'position' | 'whatif' | 'computed';
   objectId: string;
   displayValue: string;  // What you see
   // When clicked → fetch full object from backend
   }
   python# Backend API
   @app.post("/trades/{trade_id}/execute")
   async def execute_trade(trade_id: str, fill_price: Decimal):
      trade = trade_store.get(trade_id)  # Get the OBJECT
      trade.mark_executed(fill_price=fill_price)  # Call its METHOD
      trade_repo.update_from_domain(trade)  # Persist
      return trade.to_dict()  # Return updated state
   What I Should Build

   FastAPI Backend with:

   Object store (in-memory + DB persistence)
   WebSocket for real-time updates
   REST endpoints that expose object methods


   React Frontend with:

   AG Grid (professional, cell editing, object binding)
   Cells that hold object references
   Actions that call backend methods


   The "Aha" Feature:

   Drag a WhatIf into a cell
   Change strike price in cell
   Watch P&L, Greeks, Risk auto-recompute
   Click "Execute" → becomes real trade



   Before I Build - One Question
   What's your MVP interaction?
   A) View portfolios/trades, click to see details, click buttons to close/roll
   B) Actually edit values in cells (like strike price) and see recomputation
   C) Create WhatIf scenarios visually and compare them side-by-side
   This determines whether I start with:

   (A) → Simple grid + detail panel
   (B) → AG Grid with cell editing + WebSocket
   (C) → WhatIf workspace with comparison

   Which resonates most with how you'd actually use this?

100. Nitin Responds
   a, b, c are not necessarily different approaches, but to anwer yes i need cell editing so that i can make decision if current trade should be rolled, adjusted.. For each trade i am planning to throw extra columns to roll the expiry or strike so in one like you will get to see the strategies.. ..So i would say lets commit to AG Grid with cell edition and websocket


1. **Created Enhanced Domain Objects** (`domain_enhanced.py` → `domain.py`)
   - Added `PortfolioType` enum (real, paper, what_if, backtest)
   - Added `TradeType.WHAT_IF` 
   - Added `TradeStatus` with full lifecycle (INTENT → EVALUATED → PENDING → EXECUTED → CLOSED/ROLLED)
   - Added `PnLAttribution` class for P&L breakdown by Greek
   - Added `Portfolio.create_what_if()` and `Trade.create_what_if()` factory methods
   - Added entry/current/exit state tracking on Trade, Leg, Position
   - Added `is_open` as property (not field) on Trade

2. **Created Enhanced Schema** (`schema_enhanced.py` → `schema.py`)
   - Added `portfolio_type`, per-portfolio risk limits to PortfolioORM
   - Added entry state columns (entry_price, entry_greeks, entry_iv, etc.)
   - Added P&L attribution columns
   - Added new tables: `PositionGreeksSnapshotORM`, `PositionPnLSnapshotORM`

3. **Updated `debug_autotrader.py`**
   - Added WhatIf test steps (9-12)
   - Added `--mode what-if` for testing WhatIf features only
   - Added `--skip-sync` to skip broker connection

4. **Updated `repositories/trade.py`**
   - Fixed `opened_at` → `created_at` mapping
   - Fixed `RiskCategory` enum → string conversion
   - Removed `planned_exit` (not in enhanced schema)
   - Fixed `is_open` property vs field issue

### Current State

| Component | Status |
|-----------|--------|
| Enhanced domain.py | ✅ Installed |
| Enhanced schema.py | ✅ Installed |
| Database recreated | ✅ Done |
| trade.py repository | ⚠️ Needs latest fix (is_open) |
| debug_autotrader.py | ✅ Updated |
| Steps 1-4 | ✅ Passing |
| Step 5 (Event Logging) | ❌ Failing (is_open issue) |
| Steps 6-13 | ⏳ Not tested yet |

### Files to Download

From `/mnt/user-data/outputs/`:
1. `trade.py` - **Download latest version** (has is_open fix)
2. `debug_autotrader.py` - Already have this

### Next Session Priority

1. **Fix remaining trade.py issues** - Apply the is_open fix and test
2. **Run full debug_autotrader** - Get all 13 steps passing
3. **Test WhatIf workflow end-to-end**:
   - Create what-if portfolio
   - Create what-if trade
   - Run through lifecycle (intent → evaluate → execute → close)
   - Test P&L attribution

### Key Architecture Decisions Made

1. **WhatIf = Trade** - Same object model, just `trade_type=WHAT_IF`
2. **Opening vs Current State** - Every position/trade captures entry state for P&L attribution
3. **Portfolio-level risk limits** - Each what-if portfolio can have different limits
4. **`is_open` is a property** - Computed from `trade_status`, not stored

### Commands to Run

```bash
# After applying trade.py fix
python -m runners.debug_autotrader --skip-sync

# Test WhatIf features only (no broker needed)
python -m runners.debug_autotrader --mode what-if

# Full test with broker sync
python -m runners.debug_autotrader
```

### Domain Model Quick Reference

```python
# Create what-if portfolio
portfolio = Portfolio.create_what_if(
    name="0DTE Strategies",
    capital=10000,
    risk_limits={'max_delta': 50}
)

# Create what-if trade
trade = Trade.create_what_if(
    underlying="SPY",
    strategy_type=StrategyType.IRON_CONDOR,
    legs=[...],
    portfolio_id=portfolio.id
)

# Trade lifecycle
trade.mark_evaluated()
trade.mark_executed(fill_price=Decimal('2.50'), underlying_price=Decimal('590'))
trade.mark_closed(exit_price=Decimal('0.50'), reason="Profit target")

# P&L Attribution
attribution = position.get_pnl_attribution()
print(f"Delta P&L: ${attribution.delta_pnl}")
print(f"Theta P&L: ${attribution.theta_pnl}")
print(f"Unexplained: ${attribution.unexplained_pnl}")
```

### Files Changed This Session

| File | Action |
|------|--------|
| `core/models/domain.py` | Replaced with enhanced version |
| `core/database/schema.py` | Replaced with enhanced version |
| `repositories/trade.py` | Updated for enhanced domain |
| `runners/debug_autotrader.py` | Updated with WhatIf tests |
| `trading_cotrader.db` | Recreated with new schema |
