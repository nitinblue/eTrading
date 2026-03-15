import { useState } from 'react'
import { clsx } from 'clsx'
import {
  Eye, BarChart3, TrendingUp, Shield, Target, Activity,
  Brain, Zap, Clock, AlertTriangle, CheckCircle2, XCircle,
  ArrowDown, ChevronDown, ChevronUp, Lock, Crosshair,
  Gauge, GitBranch, Layers, Radio, BookOpen
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Step Component
// ---------------------------------------------------------------------------
interface StepData {
  id: number
  phase: string
  phaseColor: string
  title: string
  icon: React.ElementType
  iconColor: string
  headline: string
  visual: React.ReactNode
  whatHappens: string[]
  whatCanGoWrong: string[]
  exampleOutput?: string
  maServices?: string[]
}

function StepCard({ step, isOpen, onToggle }: { step: StepData; isOpen: boolean; onToggle: () => void }) {
  return (
    <div className="relative">
      {/* Connector line */}
      {step.id > 1 && (
        <div className="absolute left-6 -top-6 w-px h-6 bg-gradient-to-b from-transparent to-border-secondary" />
      )}

      <div className={clsx(
        'border rounded-xl overflow-hidden transition-all',
        isOpen ? 'border-accent-blue/30 bg-bg-secondary/50' : 'border-border-secondary bg-bg-secondary/20 hover:border-border-primary',
      )}>
        {/* Header — always visible */}
        <button onClick={onToggle} className="w-full flex items-center gap-3 px-4 py-3 text-left">
          {/* Step number + icon */}
          <div className={clsx(
            'w-10 h-10 rounded-xl flex items-center justify-center border shrink-0',
            step.iconColor.replace('text-', 'border-').replace('400', '700'),
            step.iconColor.replace('text-', 'bg-').replace('400', '950/40'),
          )}>
            <step.icon size={18} className={step.iconColor} />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className={clsx('text-[9px] font-semibold uppercase tracking-wider', step.phaseColor)}>{step.phase}</span>
              <span className="text-[9px] text-text-muted">Step {step.id}</span>
            </div>
            <h3 className="text-sm font-semibold text-text-primary truncate">{step.title}</h3>
            <p className="text-[10px] text-text-muted truncate">{step.headline}</p>
          </div>

          {isOpen ? <ChevronUp size={16} className="text-text-muted" /> : <ChevronDown size={16} className="text-text-muted" />}
        </button>

        {/* Expanded content */}
        {isOpen && (
          <div className="px-4 pb-4 space-y-4 border-t border-border-secondary/50 pt-3">
            {/* Visual */}
            <div className="bg-bg-tertiary rounded-lg p-4 border border-border-secondary">
              {step.visual}
            </div>

            {/* Two columns */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* What happens */}
              <div>
                <h4 className="text-[10px] font-semibold text-green-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                  <CheckCircle2 size={10} /> What Happens
                </h4>
                <ul className="space-y-1">
                  {step.whatHappens.map((item, i) => (
                    <li key={i} className="text-[10px] text-text-secondary flex items-start gap-1.5">
                      <span className="text-green-500 mt-0.5 shrink-0">›</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* What can go wrong */}
              <div>
                <h4 className="text-[10px] font-semibold text-red-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                  <XCircle size={10} /> What Can Stop It
                </h4>
                <ul className="space-y-1">
                  {step.whatCanGoWrong.map((item, i) => (
                    <li key={i} className="text-[10px] text-text-secondary flex items-start gap-1.5">
                      <span className="text-red-400 mt-0.5 shrink-0">›</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* MA Services used */}
            {step.maServices && (
              <div className="flex flex-wrap gap-1.5 pt-2 border-t border-border-secondary/50">
                <span className="text-[9px] text-text-muted mr-1">Intelligence:</span>
                {step.maServices.map((svc) => (
                  <span key={svc} className="text-[8px] px-1.5 py-0.5 rounded bg-purple-900/20 text-purple-400 border border-purple-800/30 font-mono">{svc}</span>
                ))}
              </div>
            )}

            {/* Example output */}
            {step.exampleOutput && (
              <div className="bg-bg-primary rounded border border-border-secondary p-3">
                <p className="text-[9px] text-text-muted mb-1">Example Output:</p>
                <pre className="text-[10px] text-green-400 font-mono whitespace-pre-wrap">{step.exampleOutput}</pre>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Arrow down to next step */}
      {step.id < 16 && (
        <div className="flex justify-center py-1">
          <ArrowDown size={14} className="text-text-muted/30" />
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Visual builders for each step
// ---------------------------------------------------------------------------
function FlowBox({ label, sub, color }: { label: string; sub: string; color: string }) {
  return (
    <div className={clsx('border rounded px-3 py-1.5 text-center', color)}>
      <p className="text-[10px] font-semibold">{label}</p>
      <p className="text-[8px] opacity-70">{sub}</p>
    </div>
  )
}

function Arrow() { return <ArrowDown size={12} className="text-text-muted mx-auto" /> }

function GateCheck({ name, value, pass: p }: { name: string; value: string; pass: boolean }) {
  return (
    <div className="flex items-center gap-2 text-[10px]">
      {p ? <CheckCircle2 size={11} className="text-green-500 shrink-0" /> : <XCircle size={11} className="text-red-500 shrink-0" />}
      <span className="text-text-muted w-24">{name}</span>
      <span className={clsx('font-mono', p ? 'text-green-400' : 'text-red-400')}>{value}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// All 15 Steps
// ---------------------------------------------------------------------------
const STEPS: StepData[] = [
  {
    id: 1, phase: 'WAKE UP', phaseColor: 'text-blue-400',
    title: 'Market Context Check',
    icon: Eye, iconColor: 'text-blue-400',
    headline: 'Is it safe to trade today? Check the world before anything else.',
    visual: (
      <div className="space-y-2">
        <div className="grid grid-cols-3 gap-2">
          <FlowBox label="Black Swan" sub="VIX spike? Credit stress?" color="border-red-700 text-red-400" />
          <FlowBox label="Macro Calendar" sub="FOMC? CPI? NFP today?" color="border-amber-700 text-amber-400" />
          <FlowBox label="Environment" sub="R1 calm? R4 crisis?" color="border-blue-700 text-blue-400" />
        </div>
        <Arrow />
        <FlowBox label="Day Verdict" sub="TRADE / TRADE_LIGHT / AVOID / NO_TRADE" color="border-green-700 text-green-400" />
      </div>
    ),
    whatHappens: [
      'System calls ma.context.assess() — checks VIX, credit spreads, intermarket signals',
      'Black swan monitor scans for tail risk (VIX > 30, TLT crash, credit blow-out)',
      'Macro calendar checked — FOMC days, quad witching, CPI release = reduced sizing',
      'Day verdict determines: how many positions allowed, position size factor',
    ],
    whatCanGoWrong: [
      'BLACK SWAN CRITICAL → system halts. Zero trades today.',
      'FOMC day → TRADE_LIGHT: only 1 new position, 50% size',
      'Quad witching → AVOID: no new trades, monitor only',
    ],
    maServices: ['context.assess()', 'black_swan.alert()', 'macro.calendar()'],
    exampleOutput: `Day Verdict: TRADE
Environment: Risk-on, low volatility
Black Swan: NORMAL (VIX 16.2)
Risk Budget: max 5 positions, $2,000 daily risk, sizing 100%`,
  },
  {
    id: 2, phase: 'WAKE UP', phaseColor: 'text-blue-400',
    title: 'Account & Capital Check',
    icon: Lock, iconColor: 'text-blue-400',
    headline: 'How much money do we have to work with?',
    visual: (
      <div className="grid grid-cols-2 gap-3">
        <div className="border border-border-secondary rounded p-3">
          <p className="text-[10px] text-text-muted">Account Balance</p>
          <p className="text-lg font-bold font-mono text-text-primary">$50,240</p>
          <p className="text-[9px] text-text-muted">Net Liquidating Value</p>
        </div>
        <div className="border border-border-secondary rounded p-3">
          <p className="text-[10px] text-text-muted">Buying Power</p>
          <p className="text-lg font-bold font-mono text-green-400">$38,100</p>
          <p className="text-[9px] text-text-muted">Available for new trades</p>
        </div>
      </div>
    ),
    whatHappens: [
      'System reads account balance from broker (via MA account_provider)',
      'Buying power determines what trades are affordable (Gate 3b)',
      'Each desk has allocated capital: 0DTE $10K, Medium $15K, LEAPs $20K',
      'Capital deployed % tracked per desk — won\'t over-allocate',
    ],
    whatCanGoWrong: [
      'Low buying power → expensive trades rejected at Gate 3b',
      'Desk fully deployed → no new trades for that desk until exits',
    ],
    maServices: ['account_provider.get_balance()'],
  },
  {
    id: 3, phase: 'SCAN', phaseColor: 'text-green-400',
    title: 'Watchlist Resolution',
    icon: BookOpen, iconColor: 'text-green-400',
    headline: 'Which tickers are we looking at today?',
    visual: (
      <div className="space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <FlowBox label="TastyTrade Watchlist" sub="MA-Income (25 tickers)" color="border-green-700 text-green-400" />
          <FlowBox label="YAML Fallback" sub="market_watchlist.yaml" color="border-zinc-700 text-zinc-400" />
        </div>
        <Arrow />
        <div className="flex flex-wrap gap-1">
          {['SPY','QQQ','IWM','GLD','TLT','AAPL','MSFT','NVDA','AMD','META','GOOGL','AMZN','JPM','XLE','XLF'].map(t => (
            <span key={t} className="text-[9px] px-1.5 py-0.5 rounded bg-bg-primary border border-border-secondary text-text-primary font-mono">{t}</span>
          ))}
          <span className="text-[9px] text-text-muted">+10 more</span>
        </div>
      </div>
    ),
    whatHappens: [
      'System checks TastyTrade for MA-Income watchlist (broker-synced)',
      'If available, merges with MA-Sectors for sector exposure',
      'Falls back to YAML config if no broker watchlist',
      'Typically 25-40 tickers covering ETFs, mega-caps, sectors',
    ],
    whatCanGoWrong: [
      'Broker disconnected → falls back to YAML (smaller universe)',
      'Watchlist empty → system has nothing to scan',
    ],
    maServices: ['watchlist_provider.get_watchlist()'],
  },
  {
    id: 4, phase: 'SCAN', phaseColor: 'text-green-400',
    title: 'Phase 1: Fast Screen',
    icon: Eye, iconColor: 'text-green-400',
    headline: '25 tickers screened in 60 seconds. Only candidates with score >= 0.4 advance.',
    visual: (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-[10px]">
          <span className="text-text-muted">25 tickers →</span>
          <div className="flex-1 h-2 bg-bg-primary rounded-full overflow-hidden">
            <div className="h-full bg-green-500 rounded-full" style={{ width: '40%' }} />
          </div>
          <span className="text-green-400 font-mono">10 candidates</span>
        </div>
        <p className="text-[9px] text-text-muted">
          Screen checks: regime, technicals, phase, IV rank, liquidity, earnings proximity, correlation filter
        </p>
      </div>
    ),
    whatHappens: [
      'ma.screening.scan() evaluates each ticker quickly',
      'Checks: is there a tradeable setup? Any of 11 strategy types?',
      'Filters: ATR < 0.3% → too illiquid. Correlated with already-selected → deduped',
      'Result: ~10 candidates from 25 tickers (60% filtered out)',
    ],
    whatCanGoWrong: [
      'Zero candidates → market is quiet, no setups. Stand down.',
      'All NO_GO → strong regime mismatch (R4 for income strategies)',
    ],
    maServices: ['screening.scan()', 'regime.detect()', 'technicals.snapshot()'],
  },
  {
    id: 5, phase: 'SCAN', phaseColor: 'text-green-400',
    title: 'Phase 2: Deep Rank',
    icon: BarChart3, iconColor: 'text-green-400',
    headline: '10 candidates ranked by 10+ factors. Each scored 0-1. Best trades rise to top.',
    visual: (
      <div className="space-y-1.5">
        <div className="grid grid-cols-8 gap-1 text-[8px] text-text-muted text-center">
          <span>#</span><span>Ticker</span><span>Strategy</span><span>Score</span>
          <span>Regime</span><span>IV Rank</span><span>Phase</span><span>Verdict</span>
        </div>
        {[
          { r: 1, t: 'GLD', s: 'Iron Condor', sc: '0.82', rg: 'R1', iv: '45', ph: 'Accum', v: 'GO' },
          { r: 2, t: 'SPY', s: 'Credit Spread', sc: '0.71', rg: 'R1', iv: '38', ph: 'Markup', v: 'GO' },
          { r: 3, t: 'QQQ', s: 'Iron Condor', sc: '0.65', rg: 'R2', iv: '52', ph: 'Distrib', v: 'CAUTION' },
          { r: 4, t: 'AAPL', s: 'Calendar', sc: '0.58', rg: 'R1', iv: '32', ph: 'Markup', v: 'GO' },
          { r: 5, t: 'TLT', s: 'Iron Condor', sc: '0.41', rg: 'R3', iv: '28', ph: 'Markdown', v: 'NO_GO' },
        ].map((row) => (
          <div key={row.r} className={clsx('grid grid-cols-8 gap-1 text-[9px] font-mono text-center py-0.5 rounded',
            row.v === 'GO' ? 'text-green-400' : row.v === 'CAUTION' ? 'text-amber-400' : 'text-red-400 opacity-50')}>
            <span>{row.r}</span><span>{row.t}</span><span className="text-left">{row.s}</span>
            <span className="font-bold">{row.sc}</span><span>{row.rg}</span><span>{row.iv}</span><span>{row.ph}</span>
            <span className="font-bold">{row.v}</span>
          </div>
        ))}
      </div>
    ),
    whatHappens: [
      'ma.ranking.rank() evaluates each candidate across 11 strategy types',
      'Score breakdown: regime alignment, risk/reward, technical quality, phase, confidence',
      'Thompson Sampling bandits influence which strategies are tried (ML-E2)',
      'IV rank map passed for per-assessor hard stops (IC needs IV > 15)',
      'Ranked list passed to Maverick with trade specs + legs',
    ],
    whatCanGoWrong: [
      'All scores < 0.35 → none pass Gate 2',
      'All NO_GO verdicts → regime says don\'t trade this strategy here',
    ],
    maServices: ['ranking.rank()', 'select_strategies()', 'Thompson Sampling', 'IV rank map'],
  },
  {
    id: 6, phase: 'ANALYZE', phaseColor: 'text-amber-400',
    title: 'Per-Trade Analytics',
    icon: Crosshair, iconColor: 'text-amber-400',
    headline: 'For the #1 candidate (GLD Iron Condor): compute POP, EV, breakevens, yield, liquidity.',
    visual: (
      <div className="grid grid-cols-3 gap-3">
        <div className="border border-border-secondary rounded p-2 text-center">
          <p className="text-[9px] text-text-muted">Probability of Profit</p>
          <p className="text-xl font-bold font-mono text-green-400">68%</p>
          <p className="text-[8px] text-text-muted">Regime-adjusted, not BS</p>
        </div>
        <div className="border border-border-secondary rounded p-2 text-center">
          <p className="text-[9px] text-text-muted">Expected Value</p>
          <p className="text-xl font-bold font-mono text-green-400">$32</p>
          <p className="text-[8px] text-text-muted">Per spread</p>
        </div>
        <div className="border border-border-secondary rounded p-2 text-center">
          <p className="text-[9px] text-text-muted">Return on Capital</p>
          <p className="text-xl font-bold font-mono text-amber-400">16.8%</p>
          <p className="text-[8px] text-text-muted">Annualized: 204%</p>
        </div>
      </div>
    ),
    whatHappens: [
      'POP: regime-adjusted probability (not Black-Scholes). R1 calm = higher POP.',
      'EV: POP × max_profit - (1-POP) × max_loss. Must be positive.',
      'Breakevens: exact prices where trade goes from profit to loss',
      'Income yield: credit/width ratio, ROC, annualized return',
      'Income entry check: is IV rank in sweet spot? RSI neutral? Regime friendly?',
      'Execution quality: bid-ask spread, open interest, volume per leg',
    ],
    whatCanGoWrong: [
      'POP < 45% → Gate 7 rejects',
      'EV negative → Gate 8 rejects (odds don\'t pay)',
      'Income entry not confirmed → wrong time to sell premium',
      'Wide bid-ask spread → Gate 11 rejects (illiquid, bad fills)',
    ],
    maServices: ['estimate_pop()', 'compute_income_yield()', 'compute_breakevens()', 'check_income_entry()', 'validate_execution_quality()'],
    exampleOutput: `GLD Iron Condor — 35 DTE
Legs: STO P455 | BTO P450 | STO C480 | BTO C485
POP: 68% (R1 regime, ATR 0.8%)  EV: +$32.40
Breakevens: $452.28 - $482.72
Yield: credit $0.72, width $5, ROC 16.8%
Entry: CONFIRMED (score 0.92, IV 45, RSI 48)
Liquidity: GO (spread 0.8%, OI 2,400)`,
  },
  {
    id: 7, phase: 'GATES', phaseColor: 'text-amber-400',
    title: 'The 11 Gates',
    icon: Shield, iconColor: 'text-amber-400',
    headline: 'Every single gate must pass. One failure = trade rejected. No exceptions. No overrides.',
    visual: (
      <div className="grid grid-cols-2 gap-x-4 gap-y-0.5">
        <GateCheck name="1. Verdict" value="GO" pass={true} />
        <GateCheck name="2. Score" value="0.82 >= 0.35" pass={true} />
        <GateCheck name="3. Trade spec" value="4 legs" pass={true} />
        <GateCheck name="3b. Buying power" value="$500 <= $38K" pass={true} />
        <GateCheck name="4. No duplicates" value="unique" pass={true} />
        <GateCheck name="5. Position limit" value="2/10" pass={true} />
        <GateCheck name="6. ML pattern" value="0.12" pass={true} />
        <GateCheck name="6b. Drift check" value="stable" pass={true} />
        <GateCheck name="7. POP" value="68% >= 45%" pass={true} />
        <GateCheck name="8. EV" value="+$32 > $0" pass={true} />
        <GateCheck name="9. Income entry" value="confirmed" pass={true} />
        <GateCheck name="10. Time window" value="10:15 AM" pass={true} />
        <GateCheck name="11. Liquidity" value="GO" pass={true} />
      </div>
    ),
    whatHappens: [
      'Gates run sequentially — first failure stops evaluation',
      'Drift check (ML-E1): is this strategy degrading in current regime?',
      'ML pattern (Gate 6): historical Q-learning says this pattern wins/loses',
      'Buying power (Gate 3b): wing_width × 100 must fit available BP',
      'Time window (Gate 10): 0DTE only 9:45-14:00. Monthly 10:00-15:00',
      'ALL PASS → trade is "proposed" and ready to book',
    ],
    whatCanGoWrong: [
      'Any single gate fails → entire trade rejected',
      'DRIFT CRITICAL → strategy suspended until performance recovers',
      'Already have GLD IC open → Gate 4 duplicate check blocks',
      'After 2pm → Gate 10 blocks 0DTE entries',
    ],
    maServices: ['estimate_pop()', 'check_income_entry()', 'validate_execution_quality()', 'detect_drift()'],
  },
  {
    id: 8, phase: 'SIZE', phaseColor: 'text-purple-400',
    title: 'Position Sizing',
    icon: Layers, iconColor: 'text-purple-400',
    headline: 'How many contracts? 2% of desk capital per trade. Never more.',
    visual: (
      <div className="space-y-2 text-[10px]">
        <div className="flex items-center justify-between">
          <span className="text-text-muted">Desk capital</span>
          <span className="font-mono text-text-primary">$15,000</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-text-muted">Risk per trade (2%)</span>
          <span className="font-mono text-text-primary">$300</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-text-muted">Max risk per spread</span>
          <span className="font-mono text-text-primary">$500 (wing $5)</span>
        </div>
        <div className="h-px bg-border-secondary" />
        <div className="flex items-center justify-between">
          <span className="text-text-muted font-semibold">Contracts</span>
          <span className="font-mono text-green-400 font-bold">1 contract</span>
        </div>
        <p className="text-[9px] text-text-muted">floor($300 / $500) = 0 → minimum 1. Capital preserved.</p>
      </div>
    ),
    whatHappens: [
      'MA\'s spec.position_size(capital, risk_pct=0.02) computes contracts',
      'For defined risk: max_loss = wing_width × 100 per spread',
      'For undefined risk: margin estimate from strategy service',
      'Minimum 1 contract, maximum 10. Conservative by default.',
    ],
    whatCanGoWrong: [
      'Wing too wide → 0 contracts at 2% → bumped to minimum 1',
      'Very small account → max 1 contract on everything',
    ],
    maServices: ['spec.position_size()'],
  },
  {
    id: 9, phase: 'BOOK', phaseColor: 'text-purple-400',
    title: 'Book to WhatIf Portfolio',
    icon: Target, iconColor: 'text-purple-400',
    headline: 'Trade booked to desk_medium WhatIf. Not real money. Proving the system works.',
    visual: (
      <div className="space-y-2">
        <div className="grid grid-cols-4 gap-1.5 text-[9px] font-mono">
          <div className="bg-red-950/30 border border-red-800/50 rounded p-1.5 text-center text-red-400">
            <p className="font-bold">STO</p><p>P455 4/17</p>
          </div>
          <div className="bg-green-950/30 border border-green-800/50 rounded p-1.5 text-center text-green-400">
            <p className="font-bold">BTO</p><p>P450 4/17</p>
          </div>
          <div className="bg-red-950/30 border border-red-800/50 rounded p-1.5 text-center text-red-400">
            <p className="font-bold">STO</p><p>C480 4/17</p>
          </div>
          <div className="bg-green-950/30 border border-green-800/50 rounded p-1.5 text-center text-green-400">
            <p className="font-bold">BTO</p><p>C485 4/17</p>
          </div>
        </div>
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-text-muted">Credit received</span>
          <span className="text-green-400 font-mono font-bold">$0.72 ($72/spread)</span>
        </div>
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-text-muted">Max loss</span>
          <span className="text-red-400 font-mono">$428 (defined by wings)</span>
        </div>
      </div>
    ),
    whatHappens: [
      'TradeBookingService creates TradeORM + 4 LegORMs in DB',
      'Entry Greeks fetched from broker (delta, theta, gamma, vega)',
      'ExitPlan serialized: TP 50%, SL 2x credit, close <= 21 DTE',
      'Breakevens computed and stored: $452.28 - $482.72',
      'POP, EV, regime, IV rank, composite score all stored',
      'Decision lineage logged: every gate result + market context',
      'Trade routed to desk_medium (35 DTE → medium desk)',
    ],
    whatCanGoWrong: [
      'No broker quotes → booking uses zero prices (WhatIf still works)',
      'Booking fails → logged, trade not created',
    ],
    maServices: ['from_dxlink_symbols()', 'compute_breakevens()', 'ExitPlan'],
  },
  {
    id: 10, phase: 'DEPLOY', phaseColor: 'text-amber-400',
    title: 'Promote to Real (User Action)',
    icon: Shield, iconColor: 'text-amber-400',
    headline: 'The ONLY step that requires human action. System proposes in WhatIf — you decide what goes live.',
    visual: (
      <div className="space-y-3">
        {/* Three types of promotions */}
        <div className="grid grid-cols-3 gap-2">
          <div className="border border-green-700 bg-green-950/20 rounded-lg p-2.5 text-center">
            <Target size={16} className="text-green-400 mx-auto mb-1" />
            <p className="text-[10px] text-green-400 font-semibold">New Trade</p>
            <p className="text-[8px] text-text-muted mt-1">System books to WhatIf. You review, then promote entry order to broker.</p>
          </div>
          <div className="border border-red-700 bg-red-950/20 rounded-lg p-2.5 text-center">
            <AlertTriangle size={16} className="text-red-400 mx-auto mb-1" />
            <p className="text-[10px] text-red-400 font-semibold">Exit / Close</p>
            <p className="text-[8px] text-text-muted mt-1">System signals exit in WhatIf. You review, then place closing order on broker.</p>
          </div>
          <div className="border border-amber-700 bg-amber-950/20 rounded-lg p-2.5 text-center">
            <Activity size={16} className="text-amber-400 mx-auto mb-1" />
            <p className="text-[10px] text-amber-400 font-semibold">Adjustment / Roll</p>
            <p className="text-[8px] text-text-muted mt-1">System recommends roll/adjust in WhatIf. You review legs, then execute on broker.</p>
          </div>
        </div>

        {/* WhatIf vs Live */}
        <div className="grid grid-cols-2 gap-3">
          <div className="border border-blue-700 bg-blue-950/20 rounded-lg p-2.5">
            <p className="text-[10px] text-blue-400 font-semibold text-center">WhatIf (System)</p>
            <ul className="text-[8px] text-text-muted mt-1 space-y-0.5">
              <li>• Scans, gates, books automatically</li>
              <li>• Monitors health, signals exits</li>
              <li>• Recommends adjustments with exact legs</li>
              <li>• Tracks full P&L + decision lineage</li>
              <li>• Zero real money at risk</li>
            </ul>
          </div>
          <div className="border border-green-700 bg-green-950/20 rounded-lg p-2.5">
            <p className="text-[10px] text-green-400 font-semibold text-center">Real (User Promotes)</p>
            <ul className="text-[8px] text-text-muted mt-1 space-y-0.5">
              <li>• User reviews WhatIf track record</li>
              <li>• Confirms each action on broker</li>
              <li>• Entry: <code className="text-green-400">execute &lt;id&gt; --confirm</code></li>
              <li>• Exit: <code className="text-red-400">close &lt;id&gt; --confirm</code></li>
              <li>• Adjust: place new legs manually</li>
            </ul>
          </div>
        </div>

        <div className="bg-bg-primary rounded border border-border-secondary p-2 text-center">
          <p className="text-[9px] text-text-muted">System decides WHAT and WHEN. Human decides WHETHER. Capital at risk = human responsibility.</p>
        </div>
      </div>
    ),
    whatHappens: [
      'ENTRY: System books to WhatIf → user reviews → execute <id> --confirm → real order placed',
      'EXIT: System signals close in WhatIf → user reviews → close <id> --confirm → closing order placed',
      'ADJUST: System recommends roll with exact legs → user reviews → places multi-leg order on broker',
      'All three follow same pattern: WhatIf first, human promotes second',
      'Two safety rails: TRADE_EXECUTION_ENABLED env var + adapter read_only mode',
      'Configurable: auto-promote mode (future) for users who trust the system fully',
    ],
    whatCanGoWrong: [
      'User ignores exit signal → position stays open past optimal close point',
      'Market moves between WhatIf signal and real execution → slippage',
      'User promotes without reviewing → defeats the purpose of WhatIf',
      'TRADE_EXECUTION_ENABLED=false → all promotions blocked (safety default)',
    ],
    maServices: ['TradeSpec.order_data', 'validate_execution_quality()', 'recommend_action()'],
    exampleOutput: `ENTRY:
> execute abc123 --confirm
  ORDER PLACED: SPY Iron Condor, 4 legs, filled at $0.70

EXIT:
> close abc123 --confirm
  CLOSING ORDER: SPY IC, buy back at $0.35, P&L +$35

ADJUSTMENT:
> health
  GLD: TESTED — recommend ROLL_AWAY
  Close legs: BTC P455, STO P450
  New legs: STO P445, BTO P440
  → Place this manually on broker`,
  },
  {
    id: 11, phase: 'MONITOR', phaseColor: 'text-purple-400',
    title: 'Mark-to-Market (every 30 min)',
    icon: Activity, iconColor: 'text-purple-400',
    headline: 'Live prices and Greeks update. System knows exactly where every position stands.',
    visual: (
      <div className="space-y-1 text-[10px] font-mono">
        <div className="grid grid-cols-7 gap-1 text-[8px] text-text-muted text-center">
          <span>UDL</span><span>Entry</span><span>Current</span><span>P&L</span><span>Health</span><span>DTE</span><span>\u0398/day</span>
        </div>
        <div className="grid grid-cols-7 gap-1 text-[9px] text-center py-0.5">
          <span className="text-text-primary font-bold">GLD</span>
          <span>$0.72</span><span>$0.38</span>
          <span className="text-green-400">+$34</span>
          <span className="text-[8px] px-1 rounded bg-green-900/30 text-green-400">OK</span>
          <span>28d</span><span className="text-green-400">$2.10</span>
        </div>
      </div>
    ),
    whatHappens: [
      'Broker DXLink streams bid/ask for every leg → mid price computed',
      'Greeks refreshed: delta, gamma, theta, vega per leg',
      'Trade-level P&L recalculated from leg prices',
      'Health check runs: MA\'s check_trade_health() per position',
      'Health status updated: healthy → tested → breached → exit_triggered',
    ],
    whatCanGoWrong: [
      'Broker disconnected → stale prices (last known used)',
      'Greeks unavailable → position risk unmeasured',
    ],
    maServices: ['check_trade_health()', 'regime.detect()', 'technicals.snapshot()'],
  },
  {
    id: 12, phase: 'MONITOR', phaseColor: 'text-purple-400',
    title: 'Health Check & Adjustment',
    icon: Gauge, iconColor: 'text-purple-400',
    headline: 'Is GLD still safe? Price near short strike? System decides: HOLD, ADJUST, or CLOSE.',
    visual: (
      <div className="space-y-2">
        <div className="grid grid-cols-4 gap-2">
          {[
            { s: 'SAFE', c: 'border-green-700 bg-green-950/30 text-green-400', d: 'Price > 1 ATR from strikes' },
            { s: 'TESTED', c: 'border-yellow-700 bg-yellow-950/30 text-yellow-400', d: 'Price within 1 ATR' },
            { s: 'BREACHED', c: 'border-red-700 bg-red-950/30 text-red-400', d: 'Price past short strike' },
            { s: 'MAX LOSS', c: 'border-red-600 bg-red-950/50 text-red-300', d: 'At wing. Close now.' },
          ].map(h => (
            <div key={h.s} className={clsx('border rounded p-2 text-center', h.c)}>
              <p className="text-[10px] font-bold">{h.s}</p>
              <p className="text-[8px] opacity-70">{h.d}</p>
            </div>
          ))}
        </div>
        <div className="text-[9px] text-text-muted text-center">
          <strong>Decision tree:</strong> BREACHED + R4 → CLOSE &nbsp;|&nbsp; TESTED + R3 → ROLL &nbsp;|&nbsp; SAFE → HOLD
        </div>
      </div>
    ),
    whatHappens: [
      'MA\'s recommend_action() returns ONE deterministic action (no menu)',
      'SAFE + R1/R2 → DO_NOTHING (hold)',
      'TESTED + R4 → CLOSE_FULL (crisis + tested = get out)',
      'BREACHED + R1 → ROLL_AWAY (calm market, roll the tested side)',
      'Adjustment history logged on TradeORM',
    ],
    whatCanGoWrong: [
      'IMMEDIATE adjustments auto-close the trade',
      'ROLL adjustments queued for human execution (new order needed)',
    ],
    maServices: ['recommend_action()', 'AdjustmentDecision'],
  },
  {
    id: 13, phase: 'EXIT', phaseColor: 'text-red-400',
    title: 'Exit Signal Detection',
    icon: AlertTriangle, iconColor: 'text-red-400',
    headline: 'Day 15: GLD spread at $0.36. That\'s 50% of credit. PROFIT TARGET HIT.',
    visual: (
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <div className="flex-1">
            <div className="flex items-center justify-between text-[10px] mb-1">
              <span className="text-text-muted">P&L Progress</span>
              <span className="text-green-400 font-mono">50% → TP hit</span>
            </div>
            <div className="h-3 bg-bg-primary rounded-full overflow-hidden">
              <div className="h-full bg-gradient-to-r from-green-600 to-green-400 rounded-full" style={{ width: '50%' }} />
            </div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 text-[9px]">
          <div className="flex items-center gap-1.5"><CheckCircle2 size={10} className="text-green-500" /><span>Profit target: 50% of $72 = $36 → <strong className="text-green-400">HIT</strong></span></div>
          <div className="flex items-center gap-1.5"><XCircle size={10} className="text-zinc-600" /><span className="text-text-muted">Stop loss: 2x credit = $144 → not hit</span></div>
          <div className="flex items-center gap-1.5"><XCircle size={10} className="text-zinc-600" /><span className="text-text-muted">DTE exit: 21 days → 28 remaining</span></div>
          <div className="flex items-center gap-1.5"><XCircle size={10} className="text-zinc-600" /><span className="text-text-muted">Regime change: still R1 → no change</span></div>
        </div>
      </div>
    ),
    whatHappens: [
      'MA\'s monitor_exit_conditions() checks all rules against current price',
      'Profit target: entry $0.72, current $0.36 → 50% profit → CLOSE signal',
      'Time-of-day awareness: near 3:30pm + tested = IMMEDIATE urgency',
      'Regime drift: if R1 at entry, now R4 → income strategy invalidated → CLOSE',
      'Signal mapped to severity: URGENT → auto-close, WARNING → alert, INFO → monitor',
    ],
    whatCanGoWrong: [
      'Stop loss hit → URGENT → auto-close at loss',
      'DTE < 21 → gamma acceleration risk → close early',
      'Regime changed R1→R4 → close all income positions',
    ],
    maServices: ['monitor_exit_conditions()', 'time_of_day', 'regime change detection'],
  },
  {
    id: 14, phase: 'EXIT', phaseColor: 'text-red-400',
    title: 'Auto-Close',
    icon: Zap, iconColor: 'text-red-400',
    headline: 'System closes the GLD iron condor. $36 profit. 15 days held. No human involved.',
    visual: (
      <div className="border border-green-700 bg-green-950/20 rounded-lg p-4 text-center">
        <p className="text-[10px] text-green-400 font-semibold">TRADE CLOSED — PROFIT TARGET</p>
        <p className="text-2xl font-bold font-mono text-green-400 mt-1">+$36.00</p>
        <div className="flex items-center justify-center gap-4 mt-2 text-[9px] text-text-muted">
          <span>Entry: $0.72</span>
          <span>Exit: $0.36</span>
          <span>Held: 15 days</span>
          <span>ROC: 8.4%</span>
        </div>
      </div>
    ),
    whatHappens: [
      'TradeLifecycleService closes the trade in DB',
      'Exit price, exit reason, close timestamp recorded',
      'P&L attribution: how much from delta, theta, vega, unexplained',
      'TradeEventORM created with full outcome for ML learning',
      'Containers refreshed for UI',
    ],
    whatCanGoWrong: [
      'In WhatIf mode: nothing to execute on broker (just DB update)',
      'In real mode: closing order must be placed and filled',
    ],
    maServices: ['TradeLifecycleService'],
  },
  {
    id: 15, phase: 'LEARN', phaseColor: 'text-cyan-400',
    title: 'ML Learning Loop',
    icon: Brain, iconColor: 'text-cyan-400',
    headline: 'This win feeds the machine. GLD IC in R1 → bandit updated. System gets smarter.',
    visual: (
      <div className="space-y-2">
        <div className="grid grid-cols-3 gap-2 text-[9px]">
          <div className="border border-cyan-800/50 bg-cyan-950/20 rounded p-2">
            <p className="text-cyan-400 font-semibold">Drift Detection</p>
            <p className="text-text-muted">IC in R1: win rate 72% → stable. No alert.</p>
          </div>
          <div className="border border-purple-800/50 bg-purple-950/20 rounded p-2">
            <p className="text-purple-400 font-semibold">Bandit Update</p>
            <p className="text-text-muted">R1_iron_condor: Beta(12,4) → 75% expected. +1 win.</p>
          </div>
          <div className="border border-amber-800/50 bg-amber-950/20 rounded p-2">
            <p className="text-amber-400 font-semibold">Threshold Tune</p>
            <p className="text-text-muted">IC IV rank min: 15 → holding. POP min: 50% → holding.</p>
          </div>
        </div>
        <p className="text-[9px] text-text-muted text-center">
          Next time R1 is detected, iron condor will rank even higher. Proven winner gets more allocation.
        </p>
      </div>
    ),
    whatHappens: [
      'TradeOutcome built from closed trade data',
      'Bandit updated: Beta(alpha+1, beta) for win → higher sampling probability',
      'Drift detection: checks if this (regime, strategy) cell is still performing',
      'Threshold optimization: adjusts gate cutoffs based on real outcomes',
      'POP calibration: corrects probability estimates per regime',
      'Weight calibration: adjusts scoring factors from performance',
    ],
    whatCanGoWrong: [
      'Not enough data (< 10 trades) → ML learning deferred',
      'Drift CRITICAL → strategy suspended until performance recovers',
    ],
    maServices: ['update_bandit()', 'detect_drift()', 'optimize_thresholds()', 'calibrate_pop_factors()'],
  },
  {
    id: 16, phase: 'LEARN', phaseColor: 'text-cyan-400',
    title: 'Decision Lineage',
    icon: GitBranch, iconColor: 'text-cyan-400',
    headline: '"Why this trade?" Full audit trail. Every gate, every number, every reason. Always.',
    visual: (
      <div className="space-y-1 text-[9px] font-mono">
        <p className="text-purple-400">{'>'} explain trade-ic-001</p>
        <p className="text-text-muted">GLD Iron Condor — desk_medium</p>
        <p className="text-text-muted">Entry: POP=68% | EV=$32 | Regime=R1 | IV=45 | ROC=16.8%</p>
        <p className="text-text-muted">Gates: 11/11 passed</p>
        <p className="text-text-muted">Commentary:</p>
        <p className="text-cyan-400/70 pl-2">[regime] HMM fitted on 252 days. R1 prob=0.82. Low vol, mean-reverting.</p>
        <p className="text-cyan-400/70 pl-2">[technicals] RSI 48 neutral. ATR 0.8% calm. Above SMA-20.</p>
        <p className="text-cyan-400/70 pl-2">[ranking] Score 0.82. Regime alignment 95%. Risk/reward strong.</p>
        <p className="text-green-400">Exit: profit_target at 50%. P&L +$36. Held 15 days.</p>
      </div>
    ),
    whatHappens: [
      'Full decision tree stored in TradeORM.decision_lineage JSON',
      'Every gate result with value and threshold',
      'Market context snapshot at entry time',
      'MA commentary from debug=True — step-by-step reasoning',
      'Data gaps flagged — where analysis was uncertain',
      'Available via API: GET /trades/{id}/explain',
      'CLI: explain <trade_id>',
    ],
    whatCanGoWrong: [
      'Nothing — this is the accountability layer. It always works.',
    ],
    maServices: ['debug=True', 'commentary', 'data_gaps', 'decision_lineage'],
  },
]

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function TradeJourneyPage() {
  const [openSteps, setOpenSteps] = useState<Set<number>>(new Set([1]))

  const toggle = (id: number) => {
    setOpenSteps(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const expandAll = () => setOpenSteps(new Set(STEPS.map(s => s.id)))
  const collapseAll = () => setOpenSteps(new Set())

  return (
    <div className="h-full overflow-y-auto bg-bg-primary">
      {/* Header */}
      <div className="border-b border-border-primary bg-gradient-to-r from-bg-primary via-bg-secondary to-bg-primary px-6 py-6">
        <div className="max-w-3xl mx-auto">
          <p className="text-[10px] text-accent-blue font-semibold tracking-widest uppercase mb-1">Trader Onboarding</p>
          <h1 className="text-xl font-bold text-text-primary">Anatomy of a Trade</h1>
          <p className="text-xs text-text-secondary mt-1">
            Follow one trade from market open to close. Every step, every decision, every number.
            This is exactly what the system does — no shortcuts, no guessing.
          </p>
          <div className="flex items-center gap-3 mt-3">
            <button onClick={expandAll} className="text-[10px] text-accent-blue hover:underline">Expand all</button>
            <button onClick={collapseAll} className="text-[10px] text-text-muted hover:underline">Collapse all</button>
            <span className="text-[9px] text-text-muted">|</span>
            <span className="text-[9px] text-text-muted">{STEPS.length} steps · 6 phases · Click any step to explore</span>
          </div>

          {/* Phase legend */}
          <div className="flex items-center gap-3 mt-3 flex-wrap">
            {[
              { phase: 'WAKE UP', color: 'text-blue-400' },
              { phase: 'SCAN', color: 'text-green-400' },
              { phase: 'ANALYZE + GATES', color: 'text-amber-400' },
              { phase: 'SIZE + BOOK', color: 'text-purple-400' },
              { phase: 'MONITOR', color: 'text-purple-400' },
              { phase: 'EXIT + LEARN', color: 'text-red-400' },
            ].map(p => (
              <span key={p.phase} className={clsx('text-[9px] font-semibold', p.color)}>{p.phase}</span>
            ))}
          </div>
        </div>
      </div>

      {/* Steps */}
      <div className="max-w-3xl mx-auto px-6 py-6 space-y-2">
        {STEPS.map(step => (
          <StepCard
            key={step.id}
            step={step}
            isOpen={openSteps.has(step.id)}
            onToggle={() => toggle(step.id)}
          />
        ))}

        {/* Footer */}
        <div className="border border-border-secondary rounded-xl p-5 bg-bg-secondary/30 mt-4 text-center">
          <p className="text-xs text-text-primary font-semibold">That's one trade. The system does this for every candidate, every day, automatically.</p>
          <p className="text-[10px] text-text-muted mt-1">
            16 steps. 11 gates. 20+ MA services. 3 ML systems. Full audit trail. One human decision.
            Zero human decisions during the trading day.
          </p>
        </div>
      </div>
    </div>
  )
}
