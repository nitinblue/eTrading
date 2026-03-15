import { useState } from 'react'
import { clsx } from 'clsx'
import {
  BookOpen, Target, Shield, Brain, Activity, Zap, Eye,
  BarChart3, Clock, AlertTriangle, CheckCircle2, Lock,
  TrendingUp, Settings, Terminal, ChevronDown, ChevronUp,
  HelpCircle, Layers, Radio, GitBranch
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Accordion Section
// ---------------------------------------------------------------------------
function Section({ id, title, icon: Icon, iconColor, children, isOpen, onToggle }: {
  id: string; title: string; icon: React.ElementType; iconColor: string;
  children: React.ReactNode; isOpen: boolean; onToggle: () => void;
}) {
  return (
    <div className="border border-border-secondary rounded-lg overflow-hidden">
      <button onClick={onToggle} className="w-full flex items-center gap-3 px-4 py-3 bg-bg-secondary/50 hover:bg-bg-secondary text-left">
        <Icon size={16} className={iconColor} />
        <span className="text-sm font-semibold text-text-primary flex-1">{title}</span>
        {isOpen ? <ChevronUp size={14} className="text-text-muted" /> : <ChevronDown size={14} className="text-text-muted" />}
      </button>
      {isOpen && <div className="px-4 py-4 space-y-4">{children}</div>}
    </div>
  )
}

function SubHead({ children }: { children: string }) {
  return <h4 className="text-xs font-bold text-text-primary mt-2 mb-1">{children}</h4>
}

function P({ children }: { children: React.ReactNode }) {
  return <p className="text-[11px] text-text-secondary leading-relaxed">{children}</p>
}

function Cmd({ cmd, desc }: { cmd: string; desc: string }) {
  return (
    <div className="flex gap-3 text-[10px] py-0.5">
      <code className="text-amber-400 font-mono w-28 shrink-0">{cmd}</code>
      <span className="text-text-muted">{desc}</span>
    </div>
  )
}

function Tip({ children }: { children: string }) {
  return (
    <div className="flex items-start gap-2 bg-blue-950/20 border border-blue-900/30 rounded p-2 text-[10px] text-blue-300">
      <HelpCircle size={12} className="shrink-0 mt-0.5" />
      <span>{children}</span>
    </div>
  )
}

function Warning({ children }: { children: string }) {
  return (
    <div className="flex items-start gap-2 bg-red-950/20 border border-red-900/30 rounded p-2 text-[10px] text-red-300">
      <AlertTriangle size={12} className="shrink-0 mt-0.5" />
      <span>{children}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Table of Contents
// ---------------------------------------------------------------------------
const TOC = [
  { id: 'getting-started', title: 'Getting Started', icon: BookOpen, color: 'text-blue-400' },
  { id: 'philosophy', title: 'Trading Philosophy', icon: Shield, color: 'text-red-400' },
  { id: 'desks', title: 'Trading Desks', icon: Target, color: 'text-green-400' },
  { id: 'pipeline', title: 'The Trading Pipeline', icon: Activity, color: 'text-purple-400' },
  { id: 'gates', title: 'The 11 Gates', icon: Lock, color: 'text-amber-400' },
  { id: 'monitoring', title: 'Position Monitoring', icon: Eye, color: 'text-purple-400' },
  { id: 'exits', title: 'Exit Rules & Adjustments', icon: AlertTriangle, color: 'text-red-400' },
  { id: 'agents', title: 'The Five Agents', icon: Brain, color: 'text-purple-400' },
  { id: 'ml', title: 'Machine Learning', icon: GitBranch, color: 'text-cyan-400' },
  { id: 'capabilities', title: 'Intelligence Capabilities', icon: Brain, color: 'text-purple-400' },
  { id: 'cli', title: 'CLI Reference', icon: Terminal, color: 'text-green-400' },
  { id: 'ui', title: 'UI Guide', icon: Layers, color: 'text-blue-400' },
  { id: 'config', title: 'Configuration', icon: Settings, color: 'text-zinc-400' },
  { id: 'faq', title: 'FAQ', icon: HelpCircle, color: 'text-amber-400' },
]

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function UserManualPage() {
  const [openSections, setOpenSections] = useState<Set<string>>(new Set(['getting-started']))

  const toggle = (id: string) => {
    setOpenSections(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const expandAll = () => setOpenSections(new Set(TOC.map(t => t.id)))
  const collapseAll = () => setOpenSections(new Set())

  return (
    <div className="h-full overflow-y-auto bg-bg-primary">
      {/* Header */}
      <div className="border-b border-border-primary bg-gradient-to-r from-bg-primary via-bg-secondary to-bg-primary px-6 py-6">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center gap-3 mb-2">
            <BookOpen size={24} className="text-accent-blue" />
            <div>
              <h1 className="text-xl font-bold text-text-primary">CoTrader User Manual</h1>
              <p className="text-xs text-text-muted">Everything you need to know to use the system</p>
            </div>
          </div>

          {/* TOC */}
          <div className="flex items-center gap-2 mt-4 flex-wrap">
            <button onClick={expandAll} className="text-[9px] text-accent-blue hover:underline">Expand all</button>
            <button onClick={collapseAll} className="text-[9px] text-text-muted hover:underline">Collapse all</button>
            <span className="text-[9px] text-text-muted">|</span>
            {TOC.map(t => (
              <button
                key={t.id}
                onClick={() => { setOpenSections(new Set([t.id])) }}
                className={clsx('text-[9px] hover:underline', t.color)}
              >
                {t.title}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Sections */}
      <div className="max-w-4xl mx-auto px-6 py-6 space-y-3">

        <Section id="getting-started" title="Getting Started" icon={BookOpen} iconColor="text-blue-400"
          isOpen={openSections.has('getting-started')} onToggle={() => toggle('getting-started')}>
          <SubHead>What is CoTrader?</SubHead>
          <P>CoTrader is a fully systematic options trading system. It scans markets, identifies opportunities, applies 11 quality gates, books trades, monitors positions, and exits automatically. Zero human decisions during the trading day.</P>

          <SubHead>Quick Start</SubHead>
          <div className="bg-bg-tertiary rounded p-3 font-mono text-[10px] space-y-1">
            <p className="text-text-muted"># Start with broker connection + web dashboard</p>
            <p className="text-green-400">python -m trading_cotrader.runners.run_workflow --paper --web</p>
            <p className="text-text-muted mt-2"># Open dashboard</p>
            <p className="text-green-400">http://localhost:8080</p>
            <p className="text-text-muted mt-2"># Run systematic trading day (dry-run)</p>
            <p className="text-green-400">python -m trading_cotrader.agents.workflow.the_trader</p>
          </div>

          <SubHead>First Steps</SubHead>
          <P>1. Start the server with <code className="text-amber-400">--paper --web</code> to connect to your TastyTrade paper account.</P>
          <P>2. Navigate to <strong>Desks</strong> — you'll see 3 trading desks (0DTE $10K, Medium $15K, LEAPs $20K).</P>
          <P>3. Click <strong>Scan</strong> to screen the market. The system finds opportunities and applies 11 gates.</P>
          <P>4. Click <strong>Deploy</strong> to book passing trades to WhatIf portfolios.</P>
          <P>5. Click <strong>Mark</strong> to update prices and health status.</P>
          <P>6. Monitor positions — the system auto-closes on profit targets and stop losses.</P>

          <Tip>The system auto-runs scans every 30 minutes and 0DTE checks every 2 minutes. You don't need to click anything after initial setup.</Tip>
        </Section>

        <Section id="philosophy" title="Trading Philosophy" icon={Shield} iconColor="text-red-400"
          isOpen={openSections.has('philosophy')} onToggle={() => toggle('philosophy')}>
          <div className="grid grid-cols-2 gap-3">
            {[
              { icon: Shield, color: 'text-red-400', title: 'Capital Preservation First',
                desc: 'Every trade has defined max loss. 2% risk per trade. 11 gates ensure only high-confidence trades execute. We would rather miss a trade than take a bad one.' },
              { icon: Radio, color: 'text-green-400', title: 'Trade Small, Trade Frequent',
                desc: 'Our edge is mathematical, not heroic. Small positions, many trades, consistent execution. Sample size matters more than any single bet. Law of large numbers is our friend.' },
              { icon: Brain, color: 'text-purple-400', title: 'Every Event Is Data',
                desc: 'Every trade outcome feeds the ML engine. Drift detection catches degrading strategies. Thompson Sampling learns which strategies work in which regimes. The system gets smarter with every close.' },
              { icon: Eye, color: 'text-blue-400', title: 'Full Transparency',
                desc: 'Every trade has a complete decision audit trail. Ask "why this trade?" and get the full reasoning: regime, POP, EV, breakevens, gate results, commentary. No black boxes.' },
            ].map(p => (
              <div key={p.title} className="border border-border-secondary rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <p.icon size={14} className={p.color} />
                  <span className="text-[11px] font-bold text-text-primary">{p.title}</span>
                </div>
                <p className="text-[10px] text-text-secondary leading-relaxed">{p.desc}</p>
              </div>
            ))}
          </div>
          <Warning>Never book a bogus trade. Every trade must come from the full pipeline with real market data. Never take action for the sake of action — 90%+ confidence required.</Warning>
        </Section>

        <Section id="desks" title="Trading Desks" icon={Target} iconColor="text-green-400"
          isOpen={openSections.has('desks')} onToggle={() => toggle('desks')}>
          <P>Capital is allocated across 3 virtual desks. Each desk has its own strategy universe, exit rules, and monitoring cadence.</P>

          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead><tr className="border-b border-border-secondary text-text-muted">
                <th className="text-left py-2 px-2">Desk</th><th className="text-left py-2 px-2">Capital</th>
                <th className="text-left py-2 px-2">DTE</th><th className="text-left py-2 px-2">Tickers</th>
                <th className="text-left py-2 px-2">Profit Target</th><th className="text-left py-2 px-2">Stop Loss</th>
                <th className="text-left py-2 px-2">Monitor</th>
              </tr></thead>
              <tbody className="text-text-secondary">
                <tr className="border-b border-border-secondary/30"><td className="py-1.5 px-2 font-mono text-red-400">desk_0dte</td><td>$10,000</td><td>0 days</td><td>SPY, QQQ, IWM</td><td className="text-green-400">90%</td><td>None (defined risk)</td><td className="text-purple-400">Every 2 min</td></tr>
                <tr className="border-b border-border-secondary/30"><td className="py-1.5 px-2 font-mono text-amber-400">desk_medium</td><td>$15,000</td><td>30-60 days</td><td>Top 10 underlyings</td><td className="text-green-400">50%</td><td>2x credit</td><td>Every 30 min</td></tr>
                <tr><td className="py-1.5 px-2 font-mono text-blue-400">desk_leaps</td><td>$20,000</td><td>180+ days</td><td>Blue chips</td><td className="text-green-400">100%</td><td>50% loss</td><td>Every 30 min</td></tr>
              </tbody>
            </table>
          </div>

          <SubHead>How Trades Route to Desks</SubHead>
          <P>Maverick (the trader agent) automatically routes trades by DTE: 0-1 days → desk_0dte, 2-179 days → desk_medium, 180+ days → desk_leaps. You never manually assign a desk.</P>

          <SubHead>Desk Actions (UI Buttons)</SubHead>
          <div className="grid grid-cols-3 gap-2">
            <div className="border border-green-800/50 rounded p-2 text-center"><Zap size={14} className="text-green-400 mx-auto mb-1" /><p className="text-[10px] font-semibold text-green-400">Scan</p><p className="text-[9px] text-text-muted">Screen market + rank + apply gates</p></div>
            <div className="border border-purple-800/50 rounded p-2 text-center"><Target size={14} className="text-purple-400 mx-auto mb-1" /><p className="text-[10px] font-semibold text-purple-400">Deploy</p><p className="text-[9px] text-text-muted">Book passing trades to desks</p></div>
            <div className="border border-blue-800/50 rounded p-2 text-center"><Activity size={14} className="text-blue-400 mx-auto mb-1" /><p className="text-[10px] font-semibold text-blue-400">Mark</p><p className="text-[9px] text-text-muted">Update prices + health checks</p></div>
          </div>

          <Tip>These actions also run automatically on schedule. Scan every 30 min, Mark every 30 min, 0DTE check every 2 min.</Tip>
        </Section>

        <Section id="pipeline" title="The Trading Pipeline" icon={Activity} iconColor="text-purple-400"
          isOpen={openSections.has('pipeline')} onToggle={() => toggle('pipeline')}>
          <P>Every trading day follows this pipeline. Each step must complete before the next begins.</P>
          <div className="space-y-1 text-[10px]">
            {[
              { n: '1', l: 'Context Check', d: 'Is it safe to trade? Black swan? Macro events? VIX level?', c: 'text-blue-400' },
              { n: '2', l: 'Account Check', d: 'Buying power available? Capital per desk?', c: 'text-blue-400' },
              { n: '3', l: 'Watchlist', d: 'Pull tickers from TastyTrade MA-Income watchlist (25-40 tickers)', c: 'text-green-400' },
              { n: '4', l: 'Phase 1: Screen', d: 'Fast screen — filter universe to candidates (score >= 0.4)', c: 'text-green-400' },
              { n: '5', l: 'Phase 2: Rank', d: 'Deep rank — score candidates by 10+ factors, IV rank, bandits', c: 'text-green-400' },
              { n: '6', l: 'Analytics', d: 'POP, EV, breakevens, income yield, entry timing, liquidity per trade', c: 'text-amber-400' },
              { n: '7', l: '11 Gates', d: 'Every gate must pass. One failure = rejected. No exceptions.', c: 'text-amber-400' },
              { n: '8', l: 'Position Size', d: '2% risk per trade. MA computes contracts from capital + wing width.', c: 'text-purple-400' },
              { n: '9', l: 'Book', d: 'Trade booked to WhatIf desk. Legs, Greeks, ExitPlan, lineage stored.', c: 'text-purple-400' },
              { n: '10', l: 'Monitor', d: 'Mark-to-market every 30 min. Health check: healthy/tested/breached.', c: 'text-purple-400' },
              { n: '11', l: 'Exit', d: 'Profit target, stop loss, DTE, regime change → auto-close.', c: 'text-red-400' },
              { n: '12', l: 'Adjust', d: 'Tested/breached → MA recommends: hold, roll, or close. Deterministic.', c: 'text-red-400' },
              { n: '13', l: 'Learn', d: 'Every close feeds ML: drift detection, bandit update, threshold tune.', c: 'text-cyan-400' },
            ].map(s => (
              <div key={s.n} className="flex items-start gap-2">
                <span className={clsx('font-mono font-bold w-5 shrink-0', s.c)}>{s.n}</span>
                <span className="font-semibold text-text-primary w-28 shrink-0">{s.l}</span>
                <span className="text-text-muted">{s.d}</span>
              </div>
            ))}
          </div>
        </Section>

        <Section id="gates" title="The 11 Gates" icon={Lock} iconColor="text-amber-400"
          isOpen={openSections.has('gates')} onToggle={() => toggle('gates')}>
          <P>Every trade proposal must pass ALL 11 gates. This is the quality filter that makes auto-booking safe. No human review needed — the gates ARE the review.</P>
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead><tr className="border-b border-border-secondary text-text-muted">
                <th className="text-left py-1 px-2">#</th><th className="text-left py-1 px-2">Gate</th>
                <th className="text-left py-1 px-2">Threshold</th><th className="text-left py-1 px-2">Why</th><th className="text-left py-1 px-2">ML?</th>
              </tr></thead>
              <tbody className="text-text-secondary">
                {[
                  ['1', 'Verdict', 'not NO_GO', 'MA overall assessment', ''],
                  ['2', 'Score', '>= 0.35', '10-factor composite ranking', ''],
                  ['3', 'Trade spec', 'legs exist', 'Valid option legs', ''],
                  ['3b', 'Buying power', 'affordable', 'Wing × 100 fits BP', ''],
                  ['4', 'No duplicates', 'unique', 'No open same ticker:strategy', ''],
                  ['5', 'Position limit', 'under max', 'Desk has room', ''],
                  ['6', 'ML pattern', '> -0.5', 'Q-learning doesn\'t flag', 'ML'],
                  ['6b', 'Drift check', 'not CRITICAL', 'Strategy not degrading', 'ML'],
                  ['7', 'POP', '>= 45%', 'Probability of profit', 'ML'],
                  ['8', 'EV', '> $0', 'Positive expected value', 'ML'],
                  ['9', 'Income entry', 'confirmed', 'IV/RSI/regime sweet spot', ''],
                  ['10', 'Time window', 'in hours', '0DTE: 9:45-14:00', ''],
                  ['11', 'Liquidity', 'GO', 'Spread, OI, volume OK', ''],
                ].map(([n, name, threshold, why, ml]) => (
                  <tr key={n} className="border-b border-border-secondary/20">
                    <td className="py-1 px-2 font-mono text-accent-blue">{n}</td>
                    <td className="py-1 px-2 font-semibold text-text-primary">{name}</td>
                    <td className="py-1 px-2 text-amber-400 font-mono">{threshold}</td>
                    <td className="py-1 px-2">{why}</td>
                    <td className="py-1 px-2">{ml && <span className="text-[8px] px-1 rounded bg-purple-900/30 text-purple-400">ML</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>

        <Section id="monitoring" title="Position Monitoring" icon={Eye} iconColor="text-purple-400"
          isOpen={openSections.has('monitoring')} onToggle={() => toggle('monitoring')}>
          <SubHead>Health Status</SubHead>
          <P>Every open position is continuously monitored. Status determines the system's response:</P>
          <div className="grid grid-cols-4 gap-2 text-[9px]">
            {[
              { s: 'OK', c: 'bg-green-900/30 text-green-400 border-green-700', d: 'Within limits. Hold.' },
              { s: 'TST', c: 'bg-yellow-900/30 text-yellow-400 border-yellow-700', d: 'Price near strike. Watching.' },
              { s: 'BRK', c: 'bg-red-900/30 text-red-400 border-red-700', d: 'Past strike. Adjust or close.' },
              { s: 'EXIT', c: 'bg-red-900/50 text-red-300 border-red-600', d: 'Target hit. Auto-closing.' },
            ].map(h => (
              <div key={h.s} className={clsx('border rounded p-2 text-center', h.c)}>
                <p className="font-bold font-mono">{h.s}</p><p className="opacity-70 mt-0.5">{h.d}</p>
              </div>
            ))}
          </div>

          <SubHead>Monitoring Schedule</SubHead>
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <div className="flex items-center gap-2"><Clock size={12} className="text-purple-400" /><span className="text-text-muted">Every 30 min: mark-to-market + health check (all desks)</span></div>
            <div className="flex items-center gap-2"><Zap size={12} className="text-red-400" /><span className="text-text-muted">Every 2 min: 0DTE intraday signals (desk_0dte only)</span></div>
            <div className="flex items-center gap-2"><AlertTriangle size={12} className="text-amber-400" /><span className="text-text-muted">3:30 PM: overnight risk assessment (all positions)</span></div>
            <div className="flex items-center gap-2"><Brain size={12} className="text-cyan-400" /><span className="text-text-muted">Every 10 cycles: ML learning (drift, bandits, thresholds)</span></div>
          </div>
        </Section>

        <Section id="exits" title="Exit Rules & Adjustments" icon={AlertTriangle} iconColor="text-red-400"
          isOpen={openSections.has('exits')} onToggle={() => toggle('exits')}>
          <SubHead>Exit Rules by Desk</SubHead>
          <div className="overflow-x-auto">
            <table className="w-full text-[10px]">
              <thead><tr className="border-b border-border-secondary text-text-muted">
                <th className="text-left py-1 px-2">Desk</th><th className="text-left py-1 px-2">Profit Target</th>
                <th className="text-left py-1 px-2">Stop Loss</th><th className="text-left py-1 px-2">DTE Exit</th><th className="text-left py-1 px-2">Special</th>
              </tr></thead>
              <tbody className="text-text-secondary">
                <tr className="border-b border-border-secondary/20"><td className="py-1 px-2 font-mono text-red-400">0DTE</td><td>90% of credit</td><td>None (defined risk)</td><td>Expiry</td><td>Force close at 3:00 PM</td></tr>
                <tr className="border-b border-border-secondary/20"><td className="py-1 px-2 font-mono text-amber-400">Medium</td><td>50% of credit</td><td>2x credit</td><td>21 DTE</td><td>Regime change R1→R4 = close</td></tr>
                <tr><td className="py-1 px-2 font-mono text-blue-400">LEAPs</td><td>100% return</td><td>50% loss</td><td>90 DTE (roll)</td><td>—</td></tr>
              </tbody>
            </table>
          </div>

          <SubHead>Adjustment Decision Tree</SubHead>
          <P>When a position is TESTED or BREACHED, MA's deterministic decision tree fires:</P>
          <div className="grid grid-cols-2 gap-1 text-[9px] bg-bg-tertiary rounded p-3">
            <span className="text-text-muted">Breached + R4 regime</span><span className="text-red-400 font-bold">→ CLOSE</span>
            <span className="text-text-muted">Breached + R1/R2 regime</span><span className="text-amber-400 font-bold">→ ROLL AWAY</span>
            <span className="text-text-muted">Tested + R4 regime</span><span className="text-red-400 font-bold">→ CLOSE</span>
            <span className="text-text-muted">Tested + R3 regime</span><span className="text-amber-400 font-bold">→ ROLL AWAY</span>
            <span className="text-text-muted">Tested + R1/R2 regime</span><span className="text-green-400 font-bold">→ HOLD</span>
            <span className="text-text-muted">Safe (any regime)</span><span className="text-green-400 font-bold">→ HOLD</span>
          </div>
        </Section>

        <Section id="agents" title="The Five Agents" icon={Brain} iconColor="text-purple-400"
          isOpen={openSections.has('agents')} onToggle={() => toggle('agents')}>
          {[
            { emoji: '🔭', name: 'Chanakya (Scout)', role: 'Market Intelligence',
              desc: 'Scans markets using 20+ services. Ranks opportunities via Thompson Sampling. Sole interface to MarketAnalyzer.',
              kpi: 'Score ↔ P&L correlation', ml: 'Thompson Sampling, IV rank, POP calibration' },
            { emoji: '⚖️', name: 'Kubera (Steward)', role: 'Treasury & Performance',
              desc: 'Guards the treasury. Tracks P&L by desk, Greek attribution, capital utilization. Decides capital allocation.',
              kpi: 'Portfolio Sharpe ratio', ml: 'Weight calibration, capital optimization' },
            { emoji: '🛡️', name: 'Bhishma (Sentinel)', role: 'Risk Enforcement',
              desc: '5 circuit breakers, 8 trading constraints. When Bhishma halts, everything stops. Unbreakable vows.',
              kpi: 'Max drawdown vs limit', ml: 'Rules-based (by design)' },
            { emoji: '🎯', name: 'Arjuna (Maverick)', role: 'Trader',
              desc: '11 gates, 3 desks, position sizing, booking, exits, adjustments. "I see only the eye of the fish."',
              kpi: 'Win rate × average P&L', ml: 'Q-learning, drift detection, threshold optimization' },
            { emoji: '🔧', name: 'Vishwakarma (Atlas)', role: 'Infrastructure & Analytics',
              desc: 'Watches the watchers. Broker health, price freshness, ML staleness, cross-desk risk, system errors.',
              kpi: 'System uptime × ML freshness', ml: 'Anomaly detection, meta-ML' },
          ].map(a => (
            <div key={a.name} className="flex items-start gap-3 py-2 border-b border-border-secondary/30 last:border-0">
              <span className="text-xl">{a.emoji}</span>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold text-text-primary">{a.name}</span>
                  <span className="text-[9px] text-text-muted">— {a.role}</span>
                </div>
                <p className="text-[10px] text-text-secondary mt-0.5">{a.desc}</p>
                <div className="flex gap-4 mt-1 text-[9px]">
                  <span className="text-text-muted">KPI: <span className="text-amber-400">{a.kpi}</span></span>
                  <span className="text-text-muted">ML: <span className="text-purple-400">{a.ml}</span></span>
                </div>
              </div>
            </div>
          ))}
        </Section>

        <Section id="ml" title="Machine Learning" icon={GitBranch} iconColor="text-cyan-400"
          isOpen={openSections.has('ml')} onToggle={() => toggle('ml')}>
          <P>The system uses 5 ML systems that learn from every closed trade. No hardcoded rules — the system adapts.</P>
          <div className="space-y-2">
            {[
              { name: 'Drift Detection', desc: 'Monitors win rate per (regime, strategy) cell. If a strategy\'s recent win rate drops 25%+ from baseline → CRITICAL: strategy suspended. 15%+ → WARNING: position size halved.',
                trigger: 'Daily (or every 5 closes)', effect: 'Gate 6b blocks degrading strategies' },
              { name: 'Thompson Sampling', desc: 'Each (regime, strategy) cell has a Beta distribution. System samples from distributions to balance exploitation (proven winners) with exploration (undersampled strategies).',
                trigger: 'Every close updates bandit', effect: 'Scout selects strategies for ranking' },
              { name: 'Threshold Optimization', desc: 'Learns optimal gate cutoffs from real outcomes. Analyzes: did trades above/below each threshold win more? Adjusts by ±20% max per iteration.',
                trigger: 'Monthly (or every 50 closes)', effect: 'Gates 7-11 thresholds self-tune' },
              { name: 'POP Calibration', desc: 'Corrects probability estimates from actual win rates per regime. If regime R1 trades win 72% but POP predicts 60% → calibration factor adjusts.',
                trigger: 'Weekly', effect: 'Gate 7 POP estimate more accurate' },
              { name: 'Q-Learning Patterns', desc: 'Learns from regime:iv:strategy:dte:side patterns. Builds a reward table from closed trade outcomes.',
                trigger: 'Every 10 cycles', effect: 'Gate 6 ML score' },
            ].map(ml => (
              <div key={ml.name} className="border border-border-secondary rounded p-3">
                <p className="text-[11px] font-bold text-cyan-400">{ml.name}</p>
                <p className="text-[10px] text-text-secondary mt-1">{ml.desc}</p>
                <div className="flex gap-4 mt-1.5 text-[9px]">
                  <span className="text-text-muted">Trigger: <span className="text-amber-400">{ml.trigger}</span></span>
                  <span className="text-text-muted">Effect: <span className="text-green-400">{ml.effect}</span></span>
                </div>
              </div>
            ))}
          </div>
          <Tip>Run 'ml' in CLI to see current ML state. Run 'ml run' to trigger a full learning cycle manually.</Tip>
        </Section>

        <Section id="capabilities" title="Intelligence Capabilities" icon={Brain} iconColor="text-purple-400"
          isOpen={openSections.has('capabilities')} onToggle={() => toggle('capabilities')}>
          <P>All intelligence comes from MarketAnalyzer (MA) — a stateless library with 1,241 tests. CoTrader passes data in, MA returns decisions. Here's every capability by category:</P>

          <SubHead>Market Regime & Environment</SubHead>
          <div className="grid grid-cols-2 gap-1 text-[9px]">
            {[
              ['HMM Regime Detection', 'R1-R4 classification with confidence. Drives strategy selection.'],
              ['Wyckoff Phase Analysis', 'Accumulation / Markup / Distribution / Markdown cycle.'],
              ['Black Swan Monitor', 'VIX spike, credit stress, TLT crash, correlation breakdown.'],
              ['Market Context', 'Environment label, trading allowed flag, position size factor.'],
              ['Macro Calendar', 'FOMC, CPI, NFP, quad witching. Day verdict: TRADE/AVOID/NO_TRADE.'],
              ['Intermarket Dashboard', 'Cross-asset regime comparison (SPY, TLT, GLD, HYG).'],
            ].map(([name, desc]) => (
              <div key={name} className="flex items-start gap-1.5 py-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-1 shrink-0" />
                <div><span className="font-semibold text-text-primary">{name}</span> — <span className="text-text-muted">{desc}</span></div>
              </div>
            ))}
          </div>

          <SubHead>Technical Analysis (12 indicators)</SubHead>
          <div className="grid grid-cols-3 gap-1 text-[9px]">
            {['RSI (14)', 'MACD + Signal', 'Bollinger Bands', 'Stochastic K/D', 'Moving Averages (SMA 20/50/200, EMA 9/21)',
              'Fibonacci Retracements', 'ADX Trend Strength', 'Donchian Channels', 'Keltner Channels',
              'Pivot Points (PP, S1-S3, R1-R3)', 'VWAP (20-day)', 'Smart Money (Order Blocks, FVGs)'].map(t => (
              <span key={t} className="flex items-center gap-1 text-text-muted"><span className="w-1.5 h-1.5 rounded-full bg-green-500" />{t}</span>
            ))}
          </div>

          <SubHead>Trade Assessment (11 strategy assessors)</SubHead>
          <div className="grid grid-cols-2 gap-1 text-[9px]">
            {[
              ['Iron Condor', 'IV rank > 15, R1/R2 regime, defined risk'],
              ['Iron Butterfly', 'IV rank > 20, high premium environment'],
              ['Credit Spread', 'Directional bias with defined risk'],
              ['Calendar / Diagonal', 'IV differential, dual-expiry structures'],
              ['Ratio Spread', 'Advanced: partial hedge + extra premium'],
              ['0DTE', 'Same-day expiry, SPY/QQQ/IWM only'],
              ['LEAPs', 'IV rank < 70, 6+ month options'],
              ['Breakout', 'Donchian breakout + Keltner squeeze confirmation'],
              ['Momentum', 'ADX > 15, Fibonacci pullback quality'],
              ['Mean Reversion', 'ADX < 35, Fibonacci target, VWAP deviation'],
              ['Earnings', 'Implied move analysis, IV rank > 25'],
            ].map(([name, desc]) => (
              <div key={name} className="flex items-start gap-1.5 py-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-1 shrink-0" />
                <div><span className="font-semibold text-text-primary">{name}</span> — <span className="text-text-muted">{desc}</span></div>
              </div>
            ))}
          </div>

          <SubHead>Trade Analytics (pure functions)</SubHead>
          <div className="grid grid-cols-2 gap-1 text-[9px]">
            {[
              ['Probability of Profit (POP)', 'Regime-adjusted, not Black-Scholes. Calibrated from outcomes.'],
              ['Expected Value (EV)', 'POP × max_profit - (1-POP) × max_loss.'],
              ['Breakevens', 'Exact prices where trade goes from profit to loss.'],
              ['Income Yield', 'ROC, annualized return, credit-to-width ratio.'],
              ['Income Entry Check', 'Is IV/RSI/regime in sweet spot for premium selling?'],
              ['Execution Quality', 'Bid-ask spread, open interest, volume per leg.'],
              ['Position Sizing', 'Capital-based contract count (2% risk, max 10).'],
              ['Greeks Aggregation', 'Net delta/gamma/theta/vega across all legs.'],
              ['Strike Alignment', 'Snap strikes to support/resistance levels.'],
              ['Account Filtering', 'Remove trades exceeding buying power or max risk.'],
            ].map(([name, desc]) => (
              <div key={name} className="flex items-start gap-1.5 py-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-500 mt-1 shrink-0" />
                <div><span className="font-semibold text-text-primary">{name}</span> — <span className="text-text-muted">{desc}</span></div>
              </div>
            ))}
          </div>

          <SubHead>Position Management</SubHead>
          <div className="grid grid-cols-2 gap-1 text-[9px]">
            {[
              ['Exit Monitor', '5 exit rules: profit target, stop loss, DTE, regime change, time-of-day.'],
              ['Trade Health Check', 'Combined exit + adjustment analysis. Status: healthy/tested/breached.'],
              ['Deterministic Adjustments', 'recommend_action(): single action, no menu. Decision tree.'],
              ['Overnight Risk', 'Gap risk assessment. 0DTE → close. R4+tested → close before close.'],
              ['Intraday Signals', '10 signal types for 0DTE: gamma risk, strike breach, momentum shift.'],
            ].map(([name, desc]) => (
              <div key={name} className="flex items-start gap-1.5 py-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 mt-1 shrink-0" />
                <div><span className="font-semibold text-text-primary">{name}</span> — <span className="text-text-muted">{desc}</span></div>
              </div>
            ))}
          </div>

          <SubHead>Machine Learning (5 systems)</SubHead>
          <div className="grid grid-cols-1 gap-1 text-[9px]">
            {[
              ['Drift Detection', 'Flags degrading strategies. CRITICAL → suspend. WARNING → halve size.'],
              ['Thompson Sampling', 'Beta distributions per (regime, strategy). Balances exploration/exploitation.'],
              ['Threshold Optimization', 'Learns optimal gate cutoffs from outcomes. Clamped ±20% per iteration.'],
              ['POP Calibration', 'Corrects probability estimates from actual win rates per regime.'],
              ['Weight Calibration', 'Adjusts strategy scoring weights from performance data.'],
            ].map(([name, desc]) => (
              <div key={name} className="flex items-start gap-1.5 py-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 mt-1 shrink-0" />
                <div><span className="font-semibold text-text-primary">{name}</span> — <span className="text-text-muted">{desc}</span></div>
              </div>
            ))}
          </div>

          <SubHead>Transparency & Lineage</SubHead>
          <div className="grid grid-cols-2 gap-1 text-[9px]">
            {[
              ['Commentary (debug=True)', 'Step-by-step reasoning from every MA service.'],
              ['Data Gaps', 'Each assessor flags where analysis is weak or data missing.'],
              ['Decision Lineage', 'Full gate-by-gate audit trail stored on every trade.'],
              ['Performance Reports', 'Per-strategy, per-regime breakdowns with POP accuracy.'],
            ].map(([name, desc]) => (
              <div key={name} className="flex items-start gap-1.5 py-0.5">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 mt-1 shrink-0" />
                <div><span className="font-semibold text-text-primary">{name}</span> — <span className="text-text-muted">{desc}</span></div>
              </div>
            ))}
          </div>

          <Tip>All capabilities are from MarketAnalyzer (1,241 tests). CoTrader never computes — it only passes data to MA and executes the returned decisions.</Tip>
        </Section>

        <Section id="cli" title="CLI Reference" icon={Terminal} iconColor="text-green-400"
          isOpen={openSections.has('cli')} onToggle={() => toggle('cli')}>
          <SubHead>Trading Workflow</SubHead>
          <Cmd cmd="scan" desc="Screen watchlist + rank + apply 11 gates → proposals" />
          <Cmd cmd="propose" desc="Show current proposals with POP, EV, regime, liquidity" />
          <Cmd cmd="deploy" desc="Book proposed trades to their routed desks" />
          <Cmd cmd="mark" desc="Mark-to-market + health check all open positions" />
          <Cmd cmd="exits" desc="Check exit conditions via MA (profit target, stop loss, DTE)" />
          <Cmd cmd="close auto" desc="Auto-close URGENT signals + profit targets" />
          <Cmd cmd="close <id>" desc="Manual close with reason" />

          <SubHead>Analysis & Monitoring</SubHead>
          <Cmd cmd="health" desc="Position health + adjustment recommendations for all trades" />
          <Cmd cmd="explain <id>" desc="Full decision lineage — gates, commentary, data gaps" />
          <Cmd cmd="report" desc="Daily P&L report — per desk, positions at risk, exits today" />
          <Cmd cmd="syscheck" desc="System health — broker, prices, ML models, cross-desk risk" />
          <Cmd cmd="ml" desc="ML learning status — drift alerts, bandits, thresholds, POP factors" />
          <Cmd cmd="ml run" desc="Trigger full ML learning cycle now" />

          <SubHead>Portfolio & Performance</SubHead>
          <Cmd cmd="perf [desk]" desc="Win rate, Sharpe, P&L by desk" />
          <Cmd cmd="positions" desc="All open positions with Greeks" />
          <Cmd cmd="portfolios" desc="Portfolio summaries" />
          <Cmd cmd="capital" desc="Capital allocation across desks" />
          <Cmd cmd="greeks" desc="Portfolio-level Greeks" />
          <Cmd cmd="risk" desc="Risk metrics — VaR, concentration, delta utilization" />

          <SubHead>System</SubHead>
          <Cmd cmd="status" desc="Workflow engine state, cycle count, cadences" />
          <Cmd cmd="learn [days]" desc="Run ML Q-learning from closed trade history" />
          <Cmd cmd="setup-desks" desc="Create/recreate the 3 trading desks in DB" />
          <Cmd cmd="help" desc="Show all available commands" />
        </Section>

        <Section id="ui" title="UI Guide" icon={Layers} iconColor="text-blue-400"
          isOpen={openSections.has('ui')} onToggle={() => toggle('ui')}>
          <P>The sidebar has 12 pages. Here's what each does:</P>
          {[
            { icon: '🏠', page: 'Overview', desc: 'System philosophy, pipeline visualization, 11 gates, desks, health status legend, ML learning loop.' },
            { icon: '🎯', page: 'Desks', desc: 'Maverick\'s accountability page. 3 desk cards with P&L, win rate, health. Scan/Deploy/Mark buttons. Trade grid.' },
            { icon: '📖', page: 'Trade Journey', desc: '15-step interactive walkthrough of booking one trade. From context check to ML learning.' },
            { icon: '📊', page: 'Research', desc: 'Market research dashboard. Regime, technicals, opportunities per ticker. Watchlist management.' },
            { icon: '💻', page: 'Trading', desc: 'Trading terminal. AG Grid blotter with positions, Greeks, P&L. Real + WhatIf merged view.' },
            { icon: '💼', page: 'Portfolio', desc: 'Portfolio page. Positions, performance charts, capital allocation tabs.' },
            { icon: '🛡️', page: 'Risk', desc: 'Risk dashboard. VaR, concentration, delta utilization, circuit breaker status.' },
            { icon: '🤖', page: 'Agents', desc: 'Agent monitor. Character introductions, run history, ML/RL status, workflow state.' },
            { icon: '📋', page: 'Reports', desc: 'Reports page. Daily P&L, performance reports.' },
            { icon: '🗄️', page: 'Data Explorer', desc: 'Raw DB access. Query tables, inspect data.' },
            { icon: '⚙️', page: 'Config', desc: 'Configuration. Desks, risk limits, strategies, workflow settings.' },
            { icon: '❓', page: 'Manual', desc: 'This page. Complete user guide.' },
          ].map(p => (
            <div key={p.page} className="flex items-start gap-2 py-1 text-[10px]">
              <span>{p.icon}</span>
              <span className="font-semibold text-text-primary w-24 shrink-0">{p.page}</span>
              <span className="text-text-muted">{p.desc}</span>
            </div>
          ))}
        </Section>

        <Section id="config" title="Configuration" icon={Settings} iconColor="text-zinc-400"
          isOpen={openSections.has('config')} onToggle={() => toggle('config')}>
          <SubHead>Key Config Files</SubHead>
          <Cmd cmd="risk_config.yaml" desc="Desk definitions, capital, strategies, risk limits, exit rules" />
          <Cmd cmd="workflow_rules.yaml" desc="Circuit breakers, trading constraints, halt thresholds" />
          <Cmd cmd="market_watchlist.yaml" desc="Fallback ticker list (used when broker watchlist unavailable)" />
          <Cmd cmd=".env" desc="Broker credentials, API keys, environment flags" />

          <SubHead>Environment Variables</SubHead>
          <Cmd cmd="TASTYTRADE_USERNAME" desc="TastyTrade login" />
          <Cmd cmd="TASTYTRADE_PASSWORD" desc="TastyTrade password" />
          <Cmd cmd="TRADE_EXECUTION_ENABLED" desc="Set to 'true' to allow real order placement (default: false)" />

          <Warning>TRADE_EXECUTION_ENABLED must be explicitly set to 'true' to place real orders. Default is false — WhatIf only. This is the primary safety rail.</Warning>
        </Section>

        <Section id="faq" title="FAQ" icon={HelpCircle} iconColor="text-amber-400"
          isOpen={openSections.has('faq')} onToggle={() => toggle('faq')}>
          {[
            { q: 'Can the system place real orders?', a: 'Not by default. TRADE_EXECUTION_ENABLED must be explicitly set to true. Even then, Claude (AI assistant) has market data access only — never order execution.' },
            { q: 'What happens if the broker disconnects?', a: 'System falls back to yfinance for basic data. Prices become less accurate. Atlas (Vishwakarma) flags the disconnection. Trading continues with WhatIf using last known prices.' },
            { q: 'How many trades per day?', a: 'Depends on market conditions. Typically 2-5 proposals per scan, 0-3 pass all gates. Trade Small, Trade Frequent — many small positions, not few large ones.' },
            { q: 'What if all gates reject everything?', a: 'Good. The system is being disciplined. If there are no high-confidence trades, it sits on hands. "I would rather take no action than compulsions."' },
            { q: 'Can I override a rejection?', a: 'No. Gates are non-negotiable. If a trade doesn\'t pass all 11, it doesn\'t get booked. The ML systems will self-correct thresholds over time if they\'re too tight.' },
            { q: 'How does the system handle a crash (2008, COVID)?', a: 'Bhishma (Sentinel) triggers circuit breakers: VIX spike → HALT, daily loss > threshold → HALT, consecutive losses → HALT. Trading stops entirely until conditions normalize.' },
            { q: 'How long before the ML is useful?', a: 'Thompson Sampling starts learning after ~10 closed trades. Threshold optimization needs ~50. Drift detection needs ~20 per cell. The system is conservative until data accumulates.' },
            { q: 'Is this a black box?', a: 'No. Every trade has full decision lineage. Run "explain <trade_id>" to see every gate, every number, every reason. Commentary from MA\'s debug mode provides step-by-step reasoning.' },
          ].map((faq, i) => (
            <div key={i} className="py-2 border-b border-border-secondary/30 last:border-0">
              <p className="text-[11px] font-semibold text-text-primary">{faq.q}</p>
              <p className="text-[10px] text-text-secondary mt-0.5">{faq.a}</p>
            </div>
          ))}
        </Section>

      </div>
    </div>
  )
}
