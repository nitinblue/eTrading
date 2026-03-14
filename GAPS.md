# Money-Making Machine — Standing Gap Analysis
# Last Updated: 2026-03-14 (Session 41)
# SINGLE SOURCE OF TRUTH: Review every session. Update after changes.

## THE MISSION
Deploy $250K systematically. Generate cash flow through options trading.
Zero human decisions during the trading day. MA is the brain, eTrading is the hands.
Agents own their desk WhatIf P&L — fully, no excuses.

---

## MASTER GAP TABLE (MA Integration + Platform)

| # | Gap | Phase | Priority | Status | Implementation |
|---|-----|-------|----------|--------|----------------|
| **G1** | TradeSpec Bridge | P1 | CRITICAL | **DONE** | `services/tradespec_bridge.py` — trade_to_tradespec(), trade_to_dxlink_symbols(), trade_to_monitor_params(). 17 tests. |
| **G2** | Schema: Analytics Fields | P1 | CRITICAL | **DONE** | 13 columns on TradeORM: exit_plan_json, health_status, health_checked_at, pop_at_entry, ev_at_entry, breakeven_low/high, wing_width, income_yield_roc, regime_at_entry, adjustment_history, decision_lineage |
| **G3** | Exit Monitor → MA | P2 | CRITICAL | **DONE** | exit_monitor.py rewritten: _check_trade_via_ma() calls MA monitor_exit_conditions(), maps signals. Local fallback. time_of_day passed (G21). |
| **G4** | Health Status Tracking | P2 | CRITICAL | **DONE** | _run_health_checks() in mark_to_market.py. Calls check_trade_health() per trade. Stores health_status + health_checked_at. |
| **G5** | ExitPlan Storage | P2 | HIGH | **DONE** | maverick._store_exit_rules() serializes full ExitPlan to exit_plan_json. Flat fields kept for backward compat. |
| **G6** | POP/EV Gates | P3 | HIGH | **DONE** | _ma_analytics_gates(): Gate 7 POP>=45%, Gate 8 EV>$0, Gate 9 income_entry confirmed. POP/EV stored at entry. |
| **G7** | Account Filtering | P3 | HIGH | **DONE** | Gate 3b: per-trade BP check. _get_available_buying_power() reads portfolio or MA account_provider. |
| **G8** | Position Sizing → MA | P3 | MEDIUM | **DONE** | _compute_position_size() tries MA spec.position_size() first, falls back to local. |
| **G9** | Adjustment Pipeline | P4 | HIGH | **DONE** | `services/trade_health_service.py`. check_all_positions() → recommend_action(). Engine step 8b: IMMEDIATE→auto-close, ADJUST→queued. |
| **G10** | Watchlist-Driven Scanning | P5 | MEDIUM | **DONE** | Engine 4-tuple providers. Scout._resolve_tickers() tries MA-Income+MA-Sectors, YAML fallback. |
| **G11** | Two-Phase Scan | P5 | MEDIUM | **DONE** | Scout: screen→rank screened candidates only. skip_intraday=True. |
| **G12** | Auto-Book (No Human Review) | P5 | HIGH | **DONE** | Engine step 7b auto-books. 11 gates are the filter. run_once() auto-advances past RECOMMENDATION_REVIEW. |
| **G13** | Intraday Fast Cycle (0DTE) | P6 | MEDIUM | **DONE** | `services/intraday_monitor.py`. Engine.run_intraday_cycle() every 2min. IMMEDIATE→auto-close. Scheduler wired. |
| **G14** | Decision Lineage / Learning Mode | P7 | MEDIUM | **DONE** | `services/decision_lineage.py`. explain_trade() + build_lineage_at_entry(). Maverick stores at booking. |
| **G15** | Frontend: Health/Adjustments | P8 | LOW | **DONE** | API: health/POP/BE/regime/exit_plan in trade serialization. GET /trades/{id}/explain. HealthCell/PopCell/RegimeCell in grid. |
| **G16** | Breakeven Tracking | P2 | MEDIUM | **DONE** | compute_breakevens() at entry. Stored in breakeven_low/high. POP, EV, income_yield_roc also stored. |
| **G17** | Greeks from MA | P8 | LOW | DEFERRED | Broker Greeks work fine. aggregate_greeks() can validate later. Not blocking. |
| **G18** | Regime Change Detection | P2 | HIGH | **DONE** | regime_at_entry stored at booking. entry_regime_id passed to monitor_exit_conditions(). |
| **G19** | Execution Quality Gate | P3 | HIGH | **DONE** | Gate 11: validate_execution_quality() with broker leg quotes. Rejects WIDE_SPREAD/ILLIQUID. |
| **G20** | Entry Time Window | P5 | MEDIUM | **DONE** | Gate 10: checks entry_window_start/end from TradeSpec vs current time. |
| **G21** | Time-of-Day Exit Urgency | P2 | HIGH | **DONE** | time_of_day passed in exit monitor _check_trade_via_ma(). Wired in G3. |
| **G22** | Overnight Risk Assessment | P4 | HIGH | **DONE** | trade_health_service.assess_overnight_risk(). CLOSE_BEFORE_CLOSE flagged. |
| **G23** | Deterministic Adjustment | P4 | CRITICAL | **DONE** | recommend_action() exclusively. BREACHED+R4→CLOSE, TESTED+R3→ROLL, SAFE→HOLD. Zero decisions. |
| **G24** | Performance Feedback Loop | P7 | MEDIUM | **DONE** | build_trade_outcomes() exports closed trades for MA calibrate_weights(). |
| **G25** | Commentary / Debug Mode | P7 | HIGH | **DONE** | decision_lineage stores commentary. explain_trade() returns it. debug=True wiring ready. |
| **G26** | Data Gap Self-ID | P7 | MEDIUM | **DONE** | decision_lineage stores data_gaps. explain_trade() returns them. |
| **G27** | Market Data → MA Only | — | MEDIUM | DEFERRED | Refactoring: route all market data through MA, not direct DXLink. Multi-broker enabler. Not blocking systematic flow. |

---

## PHASE SUMMARY

| Phase | Name | Gaps | Status |
|-------|------|------|--------|
| **P1** | Foundation | G1, G2 | **DONE** |
| **P2** | Exit Intelligence | G3, G4, G5, G16, G18, G21 | **DONE** |
| **P3** | Entry Intelligence | G6, G7, G8, G19 | **DONE** |
| **P4** | Adjustment Pipeline | G9, G22, G23 | **DONE** |
| **P5** | Autonomous Entry | G10, G11, G12, G20 | **DONE** |
| **P6** | 0DTE Fast Cycle | G13 | **DONE** |
| **P7** | Learning Mode | G14, G24, G25, G26 | **DONE** |
| **P8** | Frontend & Polish | G15 | **DONE** |

**25 of 27 gaps closed. G17 + G27 deferred (not blocking).**

---

## SYSTEM BOUNDARY

```
MA  = pure functions. Takes inputs, returns decisions. NEVER fetches, polls, or schedules.
eT  = orchestrator. Fetches data from broker, decides WHEN to call MA, executes results.
```

| Responsibility | Owner |
|---|---|
| Market data (quotes, Greeks, chains, metrics) | MA (via providers from eTrading) |
| Analysis (regime, technicals, ranking, POP, exits) | MA |
| Portfolio state (positions, orders, fills) | eTrading |
| Order execution (place, cancel, retry) | eTrading |
| Risk limits (concentration, slots, margin) | eTrading |
| Polling/scheduling (when to call MA) | eTrading |

---

## MAVERICK GATES (11 total, s41)

| # | Gate | Source | Threshold |
|---|------|--------|-----------|
| 1 | Verdict | Existing | not no_go |
| 2 | Score | Existing | >= 0.35 |
| 3 | Trade spec has legs | Existing | legs exist |
| 3b | Buying power | G7 | wing_width×100 <= available BP |
| 4 | Duplicate prevention | Existing | unique ticker:strategy |
| 5 | Position limit | Existing | under max_positions |
| 6 | ML score | Existing | > -0.5 |
| 7 | POP | G6 | >= 45% |
| 8 | EV | G6 | > $0 |
| 9 | Income entry | G6 | confirmed (score >= 0.60) |
| 10 | Entry time window | G20 | within start-end |
| 11 | Execution quality | G19 | GO (not WIDE_SPREAD/ILLIQUID) |

---

## FULLY SYSTEMATIC TRADING DAY

### Morning — ZERO decisions
1. Engine boots → pulls tickers from TastyTrade watchlists (G10)
2. Two-phase scan: screen → rank → account filter (G11, G7)
3. Per-candidate: POP, EV, income_entry, breakevens from MA (G6)
4. 11 gates filter — only high-confidence pass (G12)
5. Auto-book to WhatIf desks (G12)
6. Decision lineage logged (G14)

### Market Hours — ZERO decisions
7. Every 30 min: mark-to-market + health check (G4)
8. MA decides: HOLD / CLOSE / ADJUST (G3)
9. Auto-close on exit signals (G3, G18)
10. Adjustments: IMMEDIATE→auto-close, ADJUST→queued (G9)
11. 0DTE desk: 2-min fast cycle (G13)
12. Overnight risk before close (G22)

### End of Day — ZERO decisions
13. P&L report
14. ML learning on closed trades
15. Full decision lineage logged (G14)

### Human touches ONLY
- Place broker orders (WhatIf → real promotion)
- Execute queued adjustments (new multi-leg orders)
- Periodic desk P&L review (weekly)

---

## VALIDATION NEEDED

| # | What | Why | How |
|---|------|-----|-----|
| V1 | End-to-end with live broker | Prove full pipeline works with real market data | Connect broker, `scan`, verify proposals, `deploy`, `mark`, `exits` |
| V2 | Track WhatIf 5+ trading days | Agent desk P&L is the product | Book trades, run daily, measure win rate + Sharpe |
| V3 | 0DTE fast cycle test | Verify 2-min signals fire correctly | Open 0DTE position, watch intraday signals |

---

## PRODUCT QUALITY (not blocking systematic flow)

| Item | Status | Notes |
|------|--------|-------|
| Trade execution rail guard | TODO | Env var gate + read-only adapter mode. Defense in depth. |
| Daily P&L report | TODO | Morning: overnight changes, theta earned, exits, cash flow |
| Notifications | TODO | Slack/email: exit signal, trade booked, black swan, P&L |
| Trade journal / decision analysis | **DONE** (G14) | Decision lineage + explain endpoint |
| Confidence framework | **DONE** (G25, G26) | Commentary + data_gaps from MA |

---

## SAAS (future)

| Item | Status |
|------|--------|
| User model + auth (OAuth/SSO) | Not started |
| Multi-tenancy (scoped queries) | Not started |
| Desk onboarding UI | CLI only |
| Broker account linking | Single-user |
| PostgreSQL | Not started |
| Cloud deployment (Docker/K8s) | Not started |
| Multi-broker routing | G27 deferred |

---

## MA DEPENDENCY STATUS

| MA Gap | What | Status |
|--------|------|--------|
| MA-G01 | recommend_action() — deterministic adjustment | **DONE** |
| MA-G02 | validate_execution_quality() — liquidity check | **DONE** |
| MA-G03 | entry_window on TradeSpec | **DONE** |
| MA-G04 | time_of_day on monitor | **DONE** |
| MA-G05 | assess_overnight_risk() | **DONE** |
| MA-G06 | auto_select on scan() | **DONE** |
| MA-G07 | TradeOutcome + calibrate_weights() | **DONE** |
| MA-G08 | commentary + debug=True | **DONE** |
| MA-G09 | data_gaps on outputs | **DONE** |
| MA-SQ1-SQ10 | IV rank integration, HMM staleness, POP calibration, assessor overhauls | **DONE** |
| MA-TA1-TA6 | Fibonacci, ADX, Donchian, Keltner, Pivots, VWAP | **DONE** |
| MA-ML1 | Drift detection — flags degrading strategies | **DONE** |
| MA-ML2 | Thompson Sampling — learns strategy selection per regime | **DONE** |
| MA-ML3 | Threshold optimization — self-tunes gate cutoffs | **DONE** |

### ML Integration (eTrading side)

| # | What | MA API | eTrading Action | Status |
|---|------|--------|-----------------|--------|
| ML-E1 | Drift detection | `detect_drift(outcomes)` → `list[DriftAlert]` | `ml_learning_service.run_drift_detection()`. CRITICAL → Gate 6b rejects. Engine step 9b runs every 10 cycles. | **DONE** |
| ML-E2 | Strategy bandits | `build_bandits()`, `update_bandit()`, `select_strategies()` | `ml_learning_service.update_bandits()` + `select_strategies_for_regime()`. Stored in MLStateORM. | **DONE** |
| ML-E3 | Threshold optimization | `optimize_thresholds(outcomes)` → `ThresholdConfig` | `ml_learning_service.optimize_gate_thresholds()`. Stored in MLStateORM. | **DONE** |
| ML-E4 | POP calibration | `calibrate_pop_factors(outcomes)` → regime factor map | `ml_learning_service.calibrate_pop()`. Stored in MLStateORM. | **DONE** |
| ML-E5 | IV rank threading | `rank(tickers, iv_rank_map=...)` | `ml_learning_service.build_iv_rank_map()`. Ready for Scout integration. | **DONE** |

**All ML + signal quality items wired. Additional wiring completed:**
- Scout passes `min_score=0.4, top_n=20` to `scan()` (G06)
- Scout passes `debug=True` to `context.assess()` and `regime.detect()` (G08)
- Scout builds `iv_rank_map` from broker, passes to `rank(iv_rank_map=...)` (SQ9/ML-E5)
- Scout passes bandit-selected strategies to `rank(strategies=...)` (ML-E2/E6)
- Scout checks `regime.model_age_days` for staleness (SQ2)
- Maverick passes `iv_rank` to `estimate_pop()` (SQ3)
- Maverick stores `iv_rank_at_entry`, `dte_at_entry`, `composite_score` at booking (Fix 7)
- Commentary from `debug=True` stored in context for decision lineage (G25)

**MA total: 1241 tests passing. 43 gaps closed. eTrading: 185 tests. All wiring complete.**

---

## WEEKLY SCORECARD

| Metric | Target | Current |
|--------|--------|---------|
| Trades proposed / week | 5-10 | TBD (validate V1) |
| WhatIf P&L this week | Track | TBD |
| Exit signals acted on | 100% | TBD |
| Win rate (closed) | >60% | TBD |
| Avg days held | 15-30 | TBD |
| Capital utilization | 50-80% | TBD |
| Theta earned / day | >0 | TBD |

---

## SESSION LOG

| Session | Date | Key Outcome |
|---------|------|-------------|
| **s41** | Mar 14 | **MA Integration complete.** 25/27 gaps closed (G17, G27 deferred). P1-P8 all done. 4 new services created. 11 Maverick gates. Fully systematic trading day. 185 tests. |
| s40 | Mar 11 | Fixed plan timeout. CLAUDE.md refocused. Rail guard added to GAPS. |
| s39 | Mar 11 | Fixed ranking bug. CLAUDE.md rewritten. MA REQ-1→5. 168 tests. |
| s38 | Mar 10 | Stallion deletion. UI consolidation. SaaS credentials. Daily plan. |
| s37b | Mar 9 | Trading desks. Full lifecycle. 3 desks. 170 tests. |
| s37 | Mar 9 | Full trading workflow. Maverick 6 gates. 163 tests. |
