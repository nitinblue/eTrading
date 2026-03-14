import {
  Shield, Brain, Clock, TrendingUp, AlertTriangle,
  ArrowRight, Zap, Eye, BarChart3, Target, Lock,
  Activity, CheckCircle2, XCircle, ArrowDownRight
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Visual Pipeline
// ---------------------------------------------------------------------------
function PipelineStep({ icon: Icon, label, sublabel, color, active }: {
  icon: React.ElementType; label: string; sublabel: string; color: string; active?: boolean
}) {
  return (
    <div className={`flex flex-col items-center gap-1 ${active ? 'opacity-100' : 'opacity-70'}`}>
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center border ${color}`}>
        <Icon size={20} />
      </div>
      <span className="text-[10px] font-semibold text-text-primary">{label}</span>
      <span className="text-[9px] text-text-muted text-center max-w-[70px] leading-tight">{sublabel}</span>
    </div>
  )
}

function Arrow() {
  return <ArrowRight size={14} className="text-text-muted mt-[-8px]" />
}

// ---------------------------------------------------------------------------
// Metric Ring (visual gauge)
// ---------------------------------------------------------------------------
function MetricRing({ value, label, color, suffix }: {
  value: number; label: string; color: string; suffix?: string
}) {
  const pct = Math.min(value, 100)
  const r = 28
  const circ = 2 * Math.PI * r
  const offset = circ - (pct / 100) * circ
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="68" height="68" viewBox="0 0 68 68">
        <circle cx="34" cy="34" r={r} fill="none" stroke="#27272a" strokeWidth="5" />
        <circle cx="34" cy="34" r={r} fill="none" stroke={color} strokeWidth="5"
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round" transform="rotate(-90 34 34)"
          className="transition-all duration-1000"
        />
        <text x="34" y="32" textAnchor="middle" className="fill-text-primary text-[13px] font-bold font-mono">
          {value}{suffix || ''}
        </text>
        <text x="34" y="44" textAnchor="middle" className="fill-text-muted text-[8px]">
          {label}
        </text>
      </svg>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Gate Visual
// ---------------------------------------------------------------------------
function GateVisual({ num, name, icon: Icon, color }: {
  num: string; name: string; icon: React.ElementType; color: string
}) {
  return (
    <div className="flex items-center gap-2 px-2 py-1.5 bg-bg-tertiary rounded border border-border-secondary">
      <span className={`text-[9px] font-mono font-bold w-4 ${color}`}>{num}</span>
      <Icon size={12} className={color} />
      <span className="text-[10px] text-text-primary">{name}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function SystemOverviewPage() {
  return (
    <div className="h-full overflow-y-auto bg-bg-primary">
      {/* Hero */}
      <div className="relative overflow-hidden border-b border-border-primary">
        <div className="absolute inset-0 bg-gradient-to-br from-blue-950/40 via-transparent to-emerald-950/20" />
        <div className="relative max-w-6xl mx-auto px-6 py-10">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[11px] text-accent-blue font-semibold tracking-widest uppercase mb-1">Systematic Options Trading</p>
              <h1 className="text-3xl font-bold text-text-primary">CoTrader</h1>
              <p className="text-sm text-text-secondary mt-2 max-w-lg">
                An AI-powered system that scans, analyzes, enters, monitors, adjusts, and exits
                options trades — with zero human decisions during the trading day.
              </p>
            </div>
            {/* Philosophy badges */}
            <div className="hidden md:flex flex-col gap-2">
              <div className="flex items-center gap-2 bg-red-950/30 border border-red-900/50 rounded-lg px-3 py-2">
                <Shield size={16} className="text-red-400" />
                <div>
                  <p className="text-[10px] font-bold text-red-400">Capital Preservation First</p>
                  <p className="text-[9px] text-red-400/70">11 gates. No trade without 90%+ confidence.</p>
                </div>
              </div>
              <div className="flex items-center gap-2 bg-amber-950/30 border border-amber-900/50 rounded-lg px-3 py-2">
                <Lock size={16} className="text-amber-400" />
                <div>
                  <p className="text-[10px] font-bold text-amber-400">Defined Risk Only</p>
                  <p className="text-[9px] text-amber-400/70">Every trade has a max loss. No naked positions.</p>
                </div>
              </div>
              <div className="flex items-center gap-2 bg-blue-950/30 border border-blue-900/50 rounded-lg px-3 py-2">
                <Brain size={16} className="text-blue-400" />
                <div>
                  <p className="text-[10px] font-bold text-blue-400">Every Event Is Data</p>
                  <p className="text-[9px] text-blue-400/70">System learns from every trade. Gets smarter over time.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-6 space-y-8">

        {/* Metrics At a Glance */}
        <div className="flex items-center justify-center gap-6 py-2">
          <MetricRing value={11} label="GATES" color="#3b82f6" />
          <MetricRing value={3} label="DESKS" color="#22c55e" />
          <MetricRing value={45} label="MIN POP" color="#eab308" suffix="%" />
          <MetricRing value={2} label="FAST" color="#a855f7" suffix="m" />
          <MetricRing value={5} label="EXITS" color="#ef4444" />
          <MetricRing value={11} label="STRATS" color="#06b6d4" />
        </div>

        {/* Visual Pipeline */}
        <section>
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-4 text-center">Trading Day Pipeline</h2>
          <div className="flex items-start justify-center gap-3 flex-wrap py-2">
            <PipelineStep icon={Eye} label="Context" sublabel="Safe to trade?" color="border-blue-600 bg-blue-950/40 text-blue-400" active />
            <Arrow />
            <PipelineStep icon={BarChart3} label="Screen" sublabel="40+ tickers in 2min" color="border-green-600 bg-green-950/40 text-green-400" active />
            <Arrow />
            <PipelineStep icon={TrendingUp} label="Rank" sublabel="Score + POP + EV" color="border-green-600 bg-green-950/40 text-green-400" active />
            <Arrow />
            <PipelineStep icon={Shield} label="11 Gates" sublabel="Zero compromises" color="border-amber-600 bg-amber-950/40 text-amber-400" active />
            <Arrow />
            <PipelineStep icon={Target} label="Book" sublabel="Auto to WhatIf" color="border-purple-600 bg-purple-950/40 text-purple-400" active />
            <Arrow />
            <PipelineStep icon={Activity} label="Monitor" sublabel="Health + Greeks" color="border-purple-600 bg-purple-950/40 text-purple-400" active />
            <Arrow />
            <PipelineStep icon={AlertTriangle} label="Exit" sublabel="TP / SL / DTE" color="border-red-600 bg-red-950/40 text-red-400" active />
            <Arrow />
            <PipelineStep icon={Brain} label="Learn" sublabel="ML feedback" color="border-cyan-600 bg-cyan-950/40 text-cyan-400" active />
          </div>
        </section>

        {/* Two Column: Gates + Health */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Gates */}
          <section className="border border-border-secondary rounded-xl p-5 bg-bg-secondary/50">
            <div className="flex items-center gap-2 mb-4">
              <Shield size={18} className="text-amber-400" />
              <h2 className="text-sm font-semibold text-text-primary">Quality Gates</h2>
              <span className="text-[9px] bg-amber-900/30 text-amber-400 px-2 py-0.5 rounded-full font-mono">11 gates</span>
            </div>
            <p className="text-[10px] text-text-muted mb-3">
              Every trade passes ALL gates. No exceptions. This is the quality filter that makes auto-booking safe.
            </p>
            <div className="grid grid-cols-2 gap-1.5">
              <GateVisual num="1" name="Verdict" icon={CheckCircle2} color="text-green-400" />
              <GateVisual num="2" name="Score >= 0.35" icon={BarChart3} color="text-green-400" />
              <GateVisual num="3" name="Valid legs" icon={CheckCircle2} color="text-green-400" />
              <GateVisual num="3b" name="Buying power" icon={Lock} color="text-amber-400" />
              <GateVisual num="4" name="No duplicates" icon={XCircle} color="text-red-400" />
              <GateVisual num="5" name="Position limit" icon={Shield} color="text-amber-400" />
              <GateVisual num="6" name="ML pattern" icon={Brain} color="text-purple-400" />
              <GateVisual num="7" name="POP >= 45%" icon={Target} color="text-blue-400" />
              <GateVisual num="8" name="EV > $0" icon={TrendingUp} color="text-green-400" />
              <GateVisual num="9" name="Entry timing" icon={Clock} color="text-cyan-400" />
              <GateVisual num="10" name="Time window" icon={Clock} color="text-amber-400" />
              <GateVisual num="11" name="Liquidity" icon={Activity} color="text-blue-400" />
            </div>
          </section>

          {/* Health Status */}
          <section className="border border-border-secondary rounded-xl p-5 bg-bg-secondary/50">
            <div className="flex items-center gap-2 mb-4">
              <Activity size={18} className="text-purple-400" />
              <h2 className="text-sm font-semibold text-text-primary">Position Health</h2>
            </div>
            <p className="text-[10px] text-text-muted mb-4">
              Every position is continuously monitored. The system detects problems and acts before you need to.
            </p>
            <div className="space-y-3">
              {[
                { status: 'Healthy', badge: 'OK', color: 'bg-green-500', barW: '100%', desc: 'All clear. Position within limits. Hold.' },
                { status: 'Tested', badge: 'TST', color: 'bg-yellow-500', barW: '65%', desc: 'Price approaching short strike. System watching closely.' },
                { status: 'Breached', badge: 'BRK', color: 'bg-red-500', barW: '35%', desc: 'Price past short strike. System recommends adjust or close.' },
                { status: 'Exit Triggered', badge: 'EXIT', color: 'bg-red-600', barW: '10%', desc: 'Profit target, stop loss, or DTE hit. Auto-closing.' },
              ].map((h) => (
                <div key={h.status} className="flex items-center gap-3">
                  <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${h.color} text-white w-10 text-center`}>{h.badge}</span>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-[11px] font-medium text-text-primary">{h.status}</span>
                    </div>
                    <div className="h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${h.color}`} style={{ width: h.barW }} />
                    </div>
                    <p className="text-[9px] text-text-muted mt-0.5">{h.desc}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Adjustment Decision Tree */}
            <div className="mt-5 pt-4 border-t border-border-secondary">
              <p className="text-[10px] font-semibold text-text-primary mb-2">Automatic Response</p>
              <div className="grid grid-cols-2 gap-2 text-[9px]">
                <div className="flex items-center gap-1.5 text-text-muted">
                  <ArrowDownRight size={10} className="text-red-400" />
                  <span>Breached + R4 regime</span>
                  <span className="text-red-400 font-bold ml-auto">CLOSE</span>
                </div>
                <div className="flex items-center gap-1.5 text-text-muted">
                  <ArrowDownRight size={10} className="text-amber-400" />
                  <span>Tested + R3 regime</span>
                  <span className="text-amber-400 font-bold ml-auto">ROLL</span>
                </div>
                <div className="flex items-center gap-1.5 text-text-muted">
                  <ArrowDownRight size={10} className="text-green-400" />
                  <span>Safe + R1/R2</span>
                  <span className="text-green-400 font-bold ml-auto">HOLD</span>
                </div>
                <div className="flex items-center gap-1.5 text-text-muted">
                  <ArrowDownRight size={10} className="text-red-400" />
                  <span>0DTE + 3:00pm</span>
                  <span className="text-red-400 font-bold ml-auto">CLOSE</span>
                </div>
              </div>
            </div>
          </section>
        </div>

        {/* Trading Desks — Visual */}
        <section>
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-4 text-center">Trading Desks</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { name: '0DTE', sub: 'Day Trades', capital: '$10K', dte: '0', tickers: 'SPY QQQ IWM',
                tp: '90%', sl: 'None', monitor: '2 min', color: 'from-red-950/60 to-bg-secondary border-red-800/50',
                icon: Zap, iconColor: 'text-red-400' },
              { name: 'Medium', sub: '~45 DTE Income', capital: '$10K', dte: '30-60', tickers: 'Top 10',
                tp: '50%', sl: '2x credit', monitor: '30 min', color: 'from-amber-950/40 to-bg-secondary border-amber-800/50',
                icon: TrendingUp, iconColor: 'text-amber-400' },
              { name: 'LEAPs', sub: 'Long-Term', capital: '$20K', dte: '180+', tickers: 'Blue chips',
                tp: '100%', sl: '50%', monitor: '30 min', color: 'from-blue-950/40 to-bg-secondary border-blue-800/50',
                icon: BarChart3, iconColor: 'text-blue-400' },
            ].map((d) => (
              <div key={d.name} className={`rounded-xl border p-5 bg-gradient-to-b ${d.color}`}>
                <div className="flex items-center gap-2 mb-3">
                  <d.icon size={20} className={d.iconColor} />
                  <div>
                    <h3 className="text-sm font-bold text-text-primary">{d.name}</h3>
                    <p className="text-[10px] text-text-muted">{d.sub}</p>
                  </div>
                  <span className="ml-auto text-sm font-bold font-mono text-text-primary">{d.capital}</span>
                </div>
                <div className="grid grid-cols-2 gap-y-2 text-[10px]">
                  <span className="text-text-muted">DTE</span><span className="text-text-primary text-right">{d.dte} days</span>
                  <span className="text-text-muted">Universe</span><span className="text-text-primary text-right">{d.tickers}</span>
                  <span className="text-text-muted">Profit Target</span><span className="text-green-400 text-right">{d.tp}</span>
                  <span className="text-text-muted">Stop Loss</span><span className="text-red-400 text-right">{d.sl}</span>
                  <span className="text-text-muted">Monitor</span><span className="text-purple-400 text-right">every {d.monitor}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Risk Philosophy */}
        <section className="border border-border-secondary rounded-xl p-6 bg-gradient-to-r from-red-950/20 via-bg-secondary to-amber-950/20">
          <h2 className="text-sm font-semibold text-text-primary mb-4 text-center">Risk Management Philosophy</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-red-900/30 border border-red-700 flex items-center justify-center mx-auto mb-2">
                <Shield size={22} className="text-red-400" />
              </div>
              <h3 className="text-xs font-bold text-text-primary mb-1">Capital Preservation First</h3>
              <p className="text-[10px] text-text-muted leading-relaxed">
                Every trade has defined max loss. 2% risk per trade.
                11 gates ensure only high-confidence trades execute.
                "I would rather take no action than compulsions."
              </p>
            </div>
            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-amber-900/30 border border-amber-700 flex items-center justify-center mx-auto mb-2">
                <Eye size={22} className="text-amber-400" />
              </div>
              <h3 className="text-xs font-bold text-text-primary mb-1">Full Transparency</h3>
              <p className="text-[10px] text-text-muted leading-relaxed">
                Every decision is logged with full lineage.
                Ask "why this trade?" and get the complete reasoning:
                regime, POP, EV, breakevens, gate results, commentary.
              </p>
            </div>
            <div className="text-center">
              <div className="w-12 h-12 rounded-full bg-blue-900/30 border border-blue-700 flex items-center justify-center mx-auto mb-2">
                <Brain size={22} className="text-blue-400" />
              </div>
              <h3 className="text-xs font-bold text-text-primary mb-1">Continuous Learning</h3>
              <p className="text-[10px] text-text-muted leading-relaxed">
                Every trade outcome feeds the ML engine.
                Strategy weights calibrate from real performance.
                The system gets smarter with every position it closes.
              </p>
            </div>
          </div>
        </section>

        {/* Market Intelligence */}
        <section>
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-1 text-center">Market Intelligence Engine</h2>
          <p className="text-[10px] text-text-muted text-center mb-4">
            Every decision is backed by quantitative analysis. The system uses 20+ services, 6 technical indicators, and 3 ML systems.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {/* Market Analysis */}
            <div className="border border-border-secondary rounded-lg p-3 bg-bg-secondary/30">
              <div className="flex items-center gap-1.5 mb-2">
                <Activity size={14} className="text-blue-400" />
                <h3 className="text-[11px] font-bold text-text-primary">Market Analysis</h3>
              </div>
              <ul className="space-y-1 text-[9px] text-text-muted">
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-blue-500" />HMM Regime Detection (R1-R4)</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-blue-500" />Wyckoff Phase Analysis</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-blue-500" />Black Swan / Tail Risk Monitor</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-blue-500" />Volatility Surface + Term Structure</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-blue-500" />Macro Calendar (FOMC, CPI, NFP)</li>
              </ul>
            </div>

            {/* Technicals */}
            <div className="border border-border-secondary rounded-lg p-3 bg-bg-secondary/30">
              <div className="flex items-center gap-1.5 mb-2">
                <BarChart3 size={14} className="text-green-400" />
                <h3 className="text-[11px] font-bold text-text-primary">Technical Analysis</h3>
              </div>
              <ul className="space-y-1 text-[9px] text-text-muted">
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-green-500" />RSI, MACD, Stochastic, Bollinger</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-green-500" />Fibonacci Retracements + Extensions</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-green-500" />ADX Trend Strength + Direction</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-green-500" />Donchian + Keltner Channels</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-green-500" />Pivot Points (S1-S3, R1-R3)</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-green-500" />VWAP + Smart Money (OB, FVG)</li>
              </ul>
            </div>

            {/* Trade Intelligence */}
            <div className="border border-border-secondary rounded-lg p-3 bg-bg-secondary/30">
              <div className="flex items-center gap-1.5 mb-2">
                <Target size={14} className="text-amber-400" />
                <h3 className="text-[11px] font-bold text-text-primary">Trade Intelligence</h3>
              </div>
              <ul className="space-y-1 text-[9px] text-text-muted">
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-amber-500" />11 Strategy Assessors (IC, Calendar, LEAP...)</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-amber-500" />POP: Regime-adjusted probability</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-amber-500" />Income Yield (ROC, annualized)</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-amber-500" />Execution Quality (spread, OI, volume)</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-amber-500" />S/R Strike Alignment</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-amber-500" />IV Rank Integration (per assessor)</li>
              </ul>
            </div>

            {/* Machine Learning */}
            <div className="border border-purple-900/50 rounded-lg p-3 bg-purple-950/10">
              <div className="flex items-center gap-1.5 mb-2">
                <Brain size={14} className="text-purple-400" />
                <h3 className="text-[11px] font-bold text-purple-300">Machine Learning</h3>
              </div>
              <ul className="space-y-1 text-[9px] text-text-muted">
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-purple-500" />Drift Detection — flags degrading strategies</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-purple-500" />Thompson Sampling — learns which strategies win in which regimes</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-purple-500" />Threshold Optimization — tunes gate cutoffs from real outcomes</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-purple-500" />POP Calibration — corrects probability from actual win rates</li>
                <li className="flex items-center gap-1.5"><span className="w-1.5 h-1.5 rounded-full bg-purple-500" />Weight Calibration — adjusts scoring from performance</li>
              </ul>
            </div>
          </div>

          {/* ML Visual: The Learning Loop */}
          <div className="mt-4 border border-purple-900/30 rounded-xl p-5 bg-gradient-to-r from-purple-950/20 via-bg-secondary to-cyan-950/10">
            <h3 className="text-xs font-bold text-purple-300 mb-3 text-center">The Learning Loop</h3>
            <div className="flex items-center justify-center gap-3 flex-wrap">
              {[
                { label: 'Trade Closes', sub: 'outcome recorded', color: 'border-green-700 text-green-400' },
                { label: 'Drift Check', sub: 'is strategy degrading?', color: 'border-red-700 text-red-400' },
                { label: 'Bandit Update', sub: 'Beta(alpha, beta) updated', color: 'border-purple-700 text-purple-400' },
                { label: 'Threshold Tune', sub: 'cutoffs optimized', color: 'border-amber-700 text-amber-400' },
                { label: 'Next Trade', sub: 'better decisions', color: 'border-cyan-700 text-cyan-400' },
              ].map((step, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className={`border rounded-lg px-3 py-2 bg-bg-tertiary text-center ${step.color}`}>
                    <p className="text-[10px] font-semibold">{step.label}</p>
                    <p className="text-[8px] text-text-muted">{step.sub}</p>
                  </div>
                  {i < 4 && <ArrowRight size={12} className="text-text-muted" />}
                </div>
              ))}
            </div>
            <p className="text-[9px] text-text-muted text-center mt-3">
              Every closed trade makes the system smarter. Drift detection catches degradation.
              Thompson Sampling explores undersampled strategies. Thresholds self-calibrate from reality.
            </p>
          </div>
        </section>

        {/* How Humans + System Interact */}
        <section className="pb-8">
          <h2 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-4 text-center">Human + System</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border border-green-900/50 bg-green-950/10 rounded-xl p-5">
              <h3 className="text-xs font-bold text-green-400 mb-3 flex items-center gap-2">
                <Brain size={14} /> System Decides
              </h3>
              <ul className="space-y-1.5 text-[10px] text-text-secondary">
                {[
                  'What to trade (screening, ranking, 11 gates)',
                  'When to enter (entry timing, regime, IV rank)',
                  'How much to trade (position sizing from MA)',
                  'When to exit (profit target, stop loss, DTE)',
                  'When to adjust (tested/breached detection)',
                  'How to adjust (roll, narrow, close — deterministic)',
                  'Overnight risk (close-before-close for dangerous holds)',
                ].map((s, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <CheckCircle2 size={11} className="text-green-500 mt-0.5 shrink-0" />{s}
                  </li>
                ))}
              </ul>
            </div>
            <div className="border border-blue-900/50 bg-blue-950/10 rounded-xl p-5">
              <h3 className="text-xs font-bold text-blue-400 mb-3 flex items-center gap-2">
                <Shield size={14} /> Human Controls
              </h3>
              <ul className="space-y-1.5 text-[10px] text-text-secondary">
                {[
                  'Promote WhatIf trades to real (place broker orders)',
                  'Execute queued adjustments (multi-leg orders)',
                  'Review desk P&L weekly',
                  'Kill switch (halt all trading)',
                  'Configure desks, capital allocation, risk limits',
                  'Set watchlists in TastyTrade (MA-Income, MA-Sectors)',
                ].map((s, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <Lock size={11} className="text-blue-500 mt-0.5 shrink-0" />{s}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
