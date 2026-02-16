# AI/ML Capability Assessment — Trading CoTrader

**Last Updated:** February 16, 2026
**Module:** `trading_cotrader/ai_cotrader/` (2,438 lines, 8 files)

---

## 1. What Exists Today

### Data Pipeline (`data_pipeline.py`)

```
Workflow Engine → SnapshotService → DailyPerformanceORM + GreeksHistoryORM
                                          ↓
                                   MLDataPipeline.accumulate_training_data()
                                          ↓
                                   Check: enough samples? → Report status
```

| Component | Status | Description |
|-----------|--------|-------------|
| Daily portfolio snapshots | WIRED (session 16) | Captures equity, P&L, Greeks, VaR, position count for every portfolio every day |
| Position Greeks history | WIRED (session 16) | Delta, gamma, theta, vega per position per day |
| Trade events (decisions) | WORKING | Every trade open/close/adjust/roll logged with market context |
| ML status dashboard | WORKING | `pipeline.get_ml_status()` reports readiness |
| Feature building | WORKING | 55 features extracted from events (market + position + portfolio) |
| Model training | NOT WIRED | Training code exists but is never called |
| Model inference | NOT WIRED | `TradingAdvisor.recommend()` exists but is never invoked |

### Feature Engineering (`feature_engineering/feature_extractor.py`)

55-dimensional feature vector, well-designed:

| Category | # Features | Examples |
|----------|-----------|----------|
| Market (21) | Price vs MAs, IV rank, VIX, RSI, regime flags, day-of-week, DTE |
| Position (19) | P&L %, DTE, Greeks (delta/gamma/theta/vega), risk-reward, strategy type flags |
| Portfolio (15) | Delta/theta per $10K, concentration, buying power %, drawdown, weekly P&L |

### Supervised Learning (`learning/supervised.py`)

| Component | What It Does | Honest Assessment |
|-----------|-------------|-------------------|
| SimpleDecisionTree | CART decision tree from scratch (no sklearn) | Works but slow. Max depth 5. |
| PatternRecognizer | Wraps tree for action prediction + confidence | Never trained on real data. |
| Action labels | HOLD, CLOSE, CLOSE_HALF, ROLL, ADJUST | Good action space. |

**How it would work (when wired):**
1. Every closed trade becomes a labeled example: features at entry → action taken → P&L outcome
2. PatternRecognizer trains on these examples
3. For new positions, it predicts: "Based on 200 similar trades, CLOSE_HALF had 72% win rate"

### Reinforcement Learning (`learning/reinforcement.py`)

| Component | What It Does | Honest Assessment |
|-----------|-------------|-------------------|
| QLearningAgent | Tabular Q-learning with state discretization | Works for small state spaces. 55 dims = explodes. |
| DQNAgent | Deep Q-Network (3-layer numpy net) | **Backprop is a stub.** Forward pass only. |
| ReplayBuffer | Experience replay for DQN | Standard, works correctly. |
| RewardFunction | Multi-component: P&L + risk penalty + time efficiency + rule compliance | Well-designed, untested on real data. |

**How it would work (when wired):**
1. Each day is a "step": state = portfolio features, action = hold/close/adjust
2. Reward = P&L delta + risk-keeping-bonus - rule-violation-penalty
3. Agent learns which (state, action) pairs maximize long-term reward
4. Over 500+ trades, learns patterns like: "When VIX > 25 and delta > threshold, CLOSE is optimal"

### Trading Advisor (`learning/reinforcement.py`)

Ensemble voting:
```
Supervised (PatternRecognizer)  → 40% weight
Reinforcement (QLearning)       → 40% weight
Rules Engine (existing rules)   → 20% weight
                                  ↓
                          Final recommendation
```

---

## 2. Does AI/ML Capture Market Moves and Portfolio Behavior?

### What It WILL Capture (Once Data Flows)

| Data Point | Source | Frequency | ML Use |
|------------|--------|-----------|--------|
| Portfolio equity curve | DailyPerformanceORM | Daily | Track drawdowns, identify winning patterns |
| Greeks evolution | GreeksHistoryORM | Daily | How delta/theta change as market moves |
| VIX at trade entry | TradeEventORM.market_context | Per trade | Learn VIX regime → optimal strategy |
| RSI, price vs MAs | market_context features | Per trade | Technical pattern recognition |
| Trade P&L outcome | TradeEventORM.outcome | Per close | Label: was this trade profitable? |
| Action taken | TradeEventORM.event_type | Per event | Label: what did you actually do? |
| Time held | DTE features | Per trade | Learn optimal holding periods |
| Risk metrics | VaR, delta, concentration | Daily | Learn risk-reward patterns |

### What It Will Learn

1. **Entry patterns**: "Iron condors opened when VIX 15-20 and RSI 45-55 had 75% win rate"
2. **Exit timing**: "Closing at 50% profit is better than holding to expiration for credit spreads"
3. **Adjustment triggers**: "When delta exceeds 0.40 on short puts, rolling down saved 60% of trades"
4. **Portfolio behavior**: "Portfolio drawdowns > 3% in a week always followed by 2-week recovery"
5. **Market regime responses**: "High VIX entries outperformed low VIX entries by 15% annualized"

### What It Will NOT Capture (Today's Gaps)

| Gap | Impact | Fix Required |
|-----|--------|--------------|
| No intraday data | Can't learn from intraday moves | Capture snapshots during monitoring cycles too |
| No earnings/FOMC calendar | Can't learn event-driven behavior | Wire calendar data into features |
| No order flow | Can't see market microstructure | Not critical for options |
| No cross-asset correlations | Can't learn SPY-QQQ relationships | Add correlation features |
| No live market data features | Market features are mock/stale | Wire TechnicalAnalysisService into features |

---

## 3. Will It Generate Recommendations?

### Current State: NO

The `TradingAdvisor.recommend()` method exists but is never called. The workflow engine uses rule-based screeners (VIX regime, IV rank, LEAPS) and rule-based exit evaluation (RulesEngine with profit/loss/DTE/delta thresholds).

### Planned Architecture

```
TODAY (Rules Only):
  Screener → Rule-based recommendations → User approves → Execute

FUTURE (Rules + AI/ML):
  Screener → Rule-based recommendations ─────────────┐
  TradingAdvisor → ML-based recommendations ──────────┤
                                                       ↓
                                              Merged ranked list
                                                       ↓
                                              User approves → Execute
                                                       ↓
                                              Outcome logged → ML retrains
```

ML recommendations would look like:

```
AI/ML RECOMMENDATIONS (confidence: 0.78, based on 245 similar trades)
┌─────────┬──────────────┬────────────┬───────────┬──────────────────────────────┐
│ Action  │ Position     │ Confidence │ Win Rate  │ Rationale                    │
├─────────┼──────────────┼────────────┼───────────┼──────────────────────────────┤
│ CLOSE   │ SPY IC -450  │ 82%        │ 71%       │ Similar setups: 41/58 profit │
│ HOLD    │ QQQ VS -510  │ 74%        │ 65%       │ Theta decay favorable, 22DTE │
│ ROLL    │ IWM IC -220  │ 68%        │ 58%       │ Delta breach + 8 DTE         │
└─────────┴──────────────┴────────────┴───────────┴──────────────────────────────┘
```

---

## 4. Honest Evaluation

### Strengths

| Area | Rating | Why |
|------|--------|-----|
| Feature design | A | 55 features cover market, position, and portfolio comprehensively |
| Algorithm choice | B+ | Decision tree + Q-learning + ensemble is appropriate for this data scale |
| Reward shaping | A | Multi-component reward (P&L + risk + time + compliance) is sophisticated |
| Code quality | B+ | Clean, well-documented, consistent patterns |
| Data model | A | Snapshot tables + event tables provide rich training data |

### Weaknesses

| Area | Rating | Why |
|------|--------|-----|
| Integration | F | Nothing is wired into the trading workflow |
| Training | F | No training loop exists. Models are never fit on real data |
| DQN implementation | D | Backprop is a stub. Forward pass only. |
| Dependencies | C | No sklearn, no PyTorch. Custom decision tree is OK but limiting |
| Testing | F | Zero tests for ML components |
| State discretization | D | 55 dims with 10 bins = 10^55 states. Q-learning can't handle this |
| Data labeling | C | Naive event-type-to-action mapping. No outcome weighting |

### Overall Grade: C+

**Good specification, zero execution.** The architecture is thoughtful but the system has never learned anything. It's a well-drawn blueprint for a house that hasn't been built yet.

---

## 5. What Needs to Happen — Priority Order

### Phase 1: Data Collection (NOW — already started with session 16)

- [x] Wire `SnapshotService` into workflow engine (DONE)
- [x] Wire `MLDataPipeline` into workflow engine (DONE)
- [ ] Book 50+ WhatIf trades to seed the data
- [ ] Ensure trade close events have P&L outcomes populated

**After Phase 1:** You'll have daily snapshots and trade events accumulating. Run `pipeline.get_ml_status()` to track progress.

### Phase 2: First Model (After 100+ closed trades)

- [ ] Add `scikit-learn` to requirements (RandomForest replaces custom tree)
- [ ] Build `train_model.py` CLI: reads events → trains PatternRecognizer → saves .pkl
- [ ] Add evaluation: accuracy, confusion matrix, feature importance
- [ ] Print "what would ML have recommended?" alongside rule-based recommendations

**After Phase 2:** ML produces suggestions but doesn't control execution. Compare ML vs rules for 1-3 months.

### Phase 3: RL Training (After 500+ closed trades)

- [ ] Replace numpy DQN with `stable-baselines3` PPO
- [ ] Create proper RL environment wrapping portfolio state
- [ ] Train offline on historical transitions
- [ ] Compare RL policy to rule-based exits

**After Phase 3:** RL agent can recommend hold/close/adjust based on learned Q-values.

### Phase 4: Live Integration

- [ ] Load models on workflow boot
- [ ] Call `TradingAdvisor.recommend()` during exit evaluation
- [ ] Show ML recommendations alongside rule-based in CLI
- [ ] Track ML accuracy vs actual outcomes
- [ ] Retrain monthly on accumulated data

---

## 6. Data Requirements

| Metric | Threshold | Current | Ready? |
|--------|-----------|---------|--------|
| Daily snapshots | 30+ days | 0 | Start booking trades |
| Closed trades with outcomes | 100+ | 0 | Need WhatIf trading |
| Unique strategies | 3+ | 0 | Book diverse strategies |
| Supervised training | 100 samples | 0 | ~2-3 months of active trading |
| RL training | 500 samples | 0 | ~6-12 months of active trading |

---

## 7. Key Files

| File | Lines | Purpose |
|------|-------|---------|
| `ai_cotrader/data_pipeline.py` | 391 | Data accumulation + dataset building |
| `ai_cotrader/feature_engineering/feature_extractor.py` | 580 | 55 features + RLState vector |
| `ai_cotrader/learning/supervised.py` | 480 | Decision tree + PatternRecognizer |
| `ai_cotrader/learning/reinforcement.py` | 803 | Q-learning + DQN + RewardFunction + TradingAdvisor |
| `services/snapshot_service.py` | 490 | Daily snapshot capture (feeds ML) |
| `core/database/schema.py` | — | DailyPerformanceORM, GreeksHistoryORM, TradeEventORM |
