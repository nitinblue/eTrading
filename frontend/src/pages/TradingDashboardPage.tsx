import { useState, useMemo } from 'react'
import { clsx } from 'clsx'
import { usePortfolios } from '../hooks/usePortfolios'
import {
  useTradingDashboard,
  useRefreshDashboard,
  useEvaluateTemplate,
  useBookTrade,
} from '../hooks/useTradingDashboard'
import { Spinner } from '../components/common/Spinner'
import { AgentBadge } from '../components/common/AgentBadge'
import type {
  TradingDashboardPortfolio,
  TradingDashboardStrategy,
  TradingDashboardPosition,
  TradingDashboardRiskFactor,
  TemplateEvaluationResult,
  EvaluatedSymbol,
} from '../api/types'

// ---------------------------------------------------------------------------
// Formatters — compact, no wasted space
// ---------------------------------------------------------------------------
const n = (v: number | null | undefined, d = 2) =>
  v == null ? '—' : v.toFixed(d)
const n$ = (v: number | null | undefined) =>
  v == null ? '—' : v < 0
    ? `-$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
    : `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
const pct = (v: number | null | undefined, d = 1) =>
  v == null ? '—' : `${v.toFixed(d)}%`
const g = (v: number | null | undefined, d = 2) =>
  v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(d)}`
const clr = (v: number | null | undefined) =>
  !v ? 'text-text-muted' : v > 0 ? 'text-accent-green' : 'text-accent-red'

// Common cell/header classes
const HC = 'py-[3px] px-1.5 text-[10px] font-semibold text-text-muted whitespace-nowrap'
const GH = 'py-[2px] px-1.5 text-[9px] font-bold uppercase tracking-wider text-text-muted bg-bg-tertiary border-b border-border-secondary'
const DC = 'py-[3px] px-1.5 text-[11px] font-mono whitespace-nowrap'
const ROW = 'border-b border-border-secondary/40 hover:bg-bg-hover/50'

// ---------------------------------------------------------------------------
// KPI Pill — tiny inline metric
// ---------------------------------------------------------------------------
function KPI({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="text-[10px] text-text-muted">{label}</span>
      <span className={clsx('text-[11px] font-mono font-semibold', color || 'text-text-primary')}>{value}</span>
    </span>
  )
}

// ---------------------------------------------------------------------------
// Portfolio Summary Strip — 2 dense rows
// ---------------------------------------------------------------------------
function SummaryStrip({ p }: { p: TradingDashboardPortfolio }) {
  return (
    <div className="border border-border-secondary rounded px-3 py-1.5 bg-bg-secondary space-y-0.5">
      {/* Row 1: Capital */}
      <div className="flex items-center gap-4 flex-wrap">
        <KPI label="Equity" value={n$(p.total_equity)} />
        <KPI label="Cash" value={n$(p.cash_balance)} />
        <KPI label="BP" value={n$(p.buying_power)} />
        <KPI label="Deployed" value={pct(p.capital_deployed_pct)} color={p.capital_deployed_pct > 60 ? 'text-accent-yellow' : undefined} />
        <KPI label="Margin" value={pct(p.margin_used_pct)} color={p.margin_used_pct > 40 ? 'text-accent-yellow' : undefined} />
        <span className="text-border-secondary">|</span>
        <KPI label="Δ" value={g(p.net_delta, 1)} color={clr(p.net_delta)} />
        <KPI label="Θ/d" value={`$${n(p.net_theta, 0)}`} color="text-accent-green" />
        <KPI label="Γ" value={n(p.net_gamma, 4)} />
        <KPI label="ν" value={g(p.net_vega, 1)} color={clr(-Math.abs(p.net_vega))} />
        <span className="text-border-secondary">|</span>
        <KPI label="VaR" value={n$(p.var_1d_95)} color={p.var_1d_95 > p.total_equity * 0.02 ? 'text-accent-red' : undefined} />
        <KPI label="Θ/VaR" value={p.theta_var_ratio ? pct(p.theta_var_ratio * 100) : '—'} color="text-accent-cyan" />
        <KPI label="Δ util" value={pct(p.delta_utilization_pct)} color={p.delta_utilization_pct > 70 ? 'text-accent-red' : undefined} />
      </div>
      {/* Row 2: Counts + WhatIf overlay */}
      <div className="flex items-center gap-4 flex-wrap text-[10px]">
        <span className="text-text-muted">Strategies: <span className="text-text-primary font-mono">{p.open_strategies}</span></span>
        <span className="text-text-muted">Positions: <span className="text-text-primary font-mono">{p.open_positions}</span></span>
        <span className="text-text-muted">WhatIf: <span className="text-accent-blue font-mono">{p.whatif_count}</span></span>
        {p.whatif_count > 0 && (
          <>
            <span className="text-border-secondary">|</span>
            <span className="text-text-muted">w/ WI Δ: <span className="font-mono text-accent-blue">{g(p.net_delta_with_whatif, 1)}</span></span>
            <span className="text-text-muted">w/ WI Θ: <span className="font-mono text-accent-blue">${n(p.net_theta_with_whatif, 0)}</span></span>
          </>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Table 1: Strategies
// ---------------------------------------------------------------------------
function StrategiesTable({ strategies }: { strategies: TradingDashboardStrategy[] }) {
  if (!strategies.length) {
    return (
      <div className="text-[11px] text-text-muted text-center py-2 border border-border-secondary/40 rounded">
        No open strategies
      </div>
    )
  }
  return (
    <div className="border border-border-secondary rounded overflow-hidden">
      <div className="bg-bg-tertiary px-2 py-[3px] text-[10px] font-bold uppercase tracking-wider text-text-muted border-b border-border-secondary">
        Strategies ({strategies.length})
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-border-secondary bg-bg-secondary">
              <th className={clsx(HC, 'text-left')}>UDL</th>
              <th className={clsx(HC, 'text-left')}>Type</th>
              <th className={clsx(HC, 'text-left')}>Legs</th>
              <th className={clsx(HC, 'text-right')}>DTE</th>
              <th className={clsx(HC, 'text-right')}>Qty</th>
              <th className={clsx(HC, 'text-right')}>Entry$</th>
              <th className={clsx(HC, 'text-right')}>Margin</th>
              <th className={clsx(HC, 'text-right')}>Mrg%</th>
              <th className={clsx(HC, 'text-right')}>MaxRisk</th>
              <th className={clsx(HC, 'text-right')}>MR/Mrg</th>
              <th className={clsx(HC, 'text-right')}>MR/BP</th>
              <th className={clsx(HC, 'text-right')}>Δ</th>
              <th className={clsx(HC, 'text-right')}>Θ</th>
              <th className={clsx(HC, 'text-right')}>P&L</th>
              <th className={clsx(HC, 'text-right')}>P&L%</th>
            </tr>
          </thead>
          <tbody>
            {strategies.map((s) => (
              <tr key={s.trade_id} className={ROW}>
                <td className={clsx(DC, 'text-left font-semibold text-text-primary')}>{s.underlying}</td>
                <td className={clsx(DC, 'text-left text-text-secondary')}>{s.strategy_type}</td>
                <td className={clsx(DC, 'text-left text-text-secondary text-[10px]')} title={s.legs_summary}>{s.legs_summary}</td>
                <td className={clsx(DC, 'text-right', s.dte != null && s.dte <= 7 ? 'text-accent-red' : '')}>{s.dte ?? '—'}</td>
                <td className={clsx(DC, 'text-right')}>{s.quantity}</td>
                <td className={clsx(DC, 'text-right')}>{n(s.entry_cost)}</td>
                <td className={clsx(DC, 'text-right')}>{n$(s.margin_used)}</td>
                <td className={clsx(DC, 'text-right')}>{pct(s.margin_pct_of_capital)}</td>
                <td className={clsx(DC, 'text-right text-accent-red')}>{n$(s.max_risk)}</td>
                <td className={clsx(DC, 'text-right')}>{pct(s.max_risk_pct_margin)}</td>
                <td className={clsx(DC, 'text-right')}>{pct(s.max_risk_pct_total_bp)}</td>
                <td className={clsx(DC, 'text-right', clr(s.net_delta))}>{g(s.net_delta, 2)}</td>
                <td className={clsx(DC, 'text-right', clr(s.net_theta))}>{g(s.net_theta, 2)}</td>
                <td className={clsx(DC, 'text-right', clr(s.total_pnl))}>{n$(s.total_pnl)}</td>
                <td className={clsx(DC, 'text-right', clr(s.pnl_pct))}>{pct(s.pnl_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Table 2: Positions — entry/current Greeks + P&L attribution
// ---------------------------------------------------------------------------
function PositionsTable({ positions }: { positions: TradingDashboardPosition[] }) {
  if (!positions.length) {
    return (
      <div className="text-[11px] text-text-muted text-center py-2 border border-border-secondary/40 rounded">
        No broker positions synced
      </div>
    )
  }
  return (
    <div className="border border-border-secondary rounded overflow-hidden">
      <div className="bg-bg-tertiary px-2 py-[3px] text-[10px] font-bold uppercase tracking-wider text-text-muted border-b border-border-secondary">
        Positions ({positions.length})
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          {/* Group headers */}
          <thead>
            <tr className="bg-bg-secondary">
              <th colSpan={5} className={clsx(GH, 'text-left border-r border-border-secondary')}>Trade</th>
              <th colSpan={6} className={clsx(GH, 'text-center border-r border-border-secondary')}>Entry Greeks</th>
              <th colSpan={6} className={clsx(GH, 'text-center border-r border-border-secondary')}>Current</th>
              <th colSpan={5} className={clsx(GH, 'text-center border-r border-border-secondary')}>P&L Attribution</th>
              <th colSpan={3} className={clsx(GH, 'text-center')}>Total</th>
            </tr>
            <tr className="border-b border-border-secondary bg-bg-secondary">
              {/* Trade */}
              <th className={clsx(HC, 'text-left')}>UDL</th>
              <th className={clsx(HC, 'text-center')}>Tp</th>
              <th className={clsx(HC, 'text-right')}>K</th>
              <th className={clsx(HC, 'text-right')}>DTE</th>
              <th className={clsx(HC, 'text-right border-r border-border-secondary/60')}>Qty</th>
              {/* Entry Greeks */}
              <th className={clsx(HC, 'text-right')}>Pr</th>
              <th className={clsx(HC, 'text-right')}>Δ</th>
              <th className={clsx(HC, 'text-right')}>Γ</th>
              <th className={clsx(HC, 'text-right')}>Θ</th>
              <th className={clsx(HC, 'text-right')}>ν</th>
              <th className={clsx(HC, 'text-right border-r border-border-secondary/60')}>IV</th>
              {/* Current */}
              <th className={clsx(HC, 'text-right')}>Pr</th>
              <th className={clsx(HC, 'text-right')}>Δ</th>
              <th className={clsx(HC, 'text-right')}>Γ</th>
              <th className={clsx(HC, 'text-right')}>Θ</th>
              <th className={clsx(HC, 'text-right')}>ν</th>
              <th className={clsx(HC, 'text-right border-r border-border-secondary/60')}>IV</th>
              {/* P&L Attribution */}
              <th className={clsx(HC, 'text-right')}>Δ</th>
              <th className={clsx(HC, 'text-right')}>Γ</th>
              <th className={clsx(HC, 'text-right')}>Θ</th>
              <th className={clsx(HC, 'text-right')}>ν</th>
              <th className={clsx(HC, 'text-right border-r border-border-secondary/60')}>Ux</th>
              {/* Total */}
              <th className={clsx(HC, 'text-right')}>P&L</th>
              <th className={clsx(HC, 'text-right')}>Bkr</th>
              <th className={clsx(HC, 'text-right')}>%</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr key={p.id} className={ROW}>
                {/* Trade */}
                <td className={clsx(DC, 'text-left font-semibold text-text-primary')}>{p.underlying || p.symbol}</td>
                <td className={clsx(DC, 'text-center')}>
                  <span className={clsx('text-[9px] px-0.5 rounded',
                    p.option_type === 'put' ? 'bg-accent-red/20 text-accent-red'
                    : p.option_type === 'call' ? 'bg-accent-green/20 text-accent-green'
                    : 'bg-accent-blue/20 text-accent-blue'
                  )}>
                    {p.option_type?.charAt(0).toUpperCase() || 'E'}
                  </span>
                </td>
                <td className={clsx(DC, 'text-right')}>{p.strike ? n(p.strike, 1) : '—'}</td>
                <td className={clsx(DC, 'text-right', p.dte != null && p.dte <= 7 ? 'text-accent-red font-semibold' : '')}>{p.dte ?? '—'}</td>
                <td className={clsx(DC, 'text-right border-r border-border-secondary/30', p.quantity < 0 ? 'text-accent-red' : 'text-accent-green')}>{p.quantity}</td>
                {/* Entry Greeks */}
                <td className={clsx(DC, 'text-right text-text-secondary')}>{n(p.entry_price)}</td>
                <td className={clsx(DC, 'text-right text-text-secondary')}>{n(p.entry_delta)}</td>
                <td className={clsx(DC, 'text-right text-text-secondary')}>{n(p.entry_gamma, 4)}</td>
                <td className={clsx(DC, 'text-right text-text-secondary')}>{n(p.entry_theta)}</td>
                <td className={clsx(DC, 'text-right text-text-secondary')}>{n(p.entry_vega)}</td>
                <td className={clsx(DC, 'text-right text-text-secondary border-r border-border-secondary/30')}>{n(p.entry_iv, 1)}</td>
                {/* Current */}
                <td className={clsx(DC, 'text-right')}>{n(p.current_price)}</td>
                <td className={clsx(DC, 'text-right', clr(p.delta))}>{g(p.delta)}</td>
                <td className={clsx(DC, 'text-right')}>{n(p.gamma, 4)}</td>
                <td className={clsx(DC, 'text-right', clr(p.theta))}>{g(p.theta)}</td>
                <td className={clsx(DC, 'text-right')}>{n(p.vega)}</td>
                <td className={clsx(DC, 'text-right border-r border-border-secondary/30')}>{n(p.iv, 1)}</td>
                {/* P&L Attribution */}
                <td className={clsx(DC, 'text-right', clr(p.pnl_delta))}>{n(p.pnl_delta)}</td>
                <td className={clsx(DC, 'text-right', clr(p.pnl_gamma))}>{n(p.pnl_gamma)}</td>
                <td className={clsx(DC, 'text-right', clr(p.pnl_theta))}>{n(p.pnl_theta)}</td>
                <td className={clsx(DC, 'text-right', clr(p.pnl_vega))}>{n(p.pnl_vega)}</td>
                <td className={clsx(DC, 'text-right border-r border-border-secondary/30', clr(p.pnl_unexplained))}>{n(p.pnl_unexplained)}</td>
                {/* Total */}
                <td className={clsx(DC, 'text-right font-semibold', clr(p.total_pnl))}>{n(p.total_pnl)}</td>
                <td className={clsx(DC, 'text-right', clr(p.broker_pnl))}>{n(p.broker_pnl)}</td>
                <td className={clsx(DC, 'text-right', clr(p.pnl_pct))}>{pct(p.pnl_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Table 3: Risk Factors
// ---------------------------------------------------------------------------
function RiskFactorsTable({ factors }: { factors: TradingDashboardRiskFactor[] }) {
  if (!factors.length) return null
  return (
    <div className="border border-border-secondary rounded overflow-hidden">
      <div className="bg-bg-tertiary px-2 py-[3px] text-[10px] font-bold uppercase tracking-wider text-text-muted border-b border-border-secondary">
        Risk Factors
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-border-secondary bg-bg-secondary">
              <th className={clsx(HC, 'text-left')}>UDL</th>
              <th className={clsx(HC, 'text-right')}>Spot</th>
              <th className={clsx(HC, 'text-right')}>Δ</th>
              <th className={clsx(HC, 'text-right')}>Γ</th>
              <th className={clsx(HC, 'text-right')}>Θ</th>
              <th className={clsx(HC, 'text-right')}>ν</th>
              <th className={clsx(HC, 'text-right')}>Δ$</th>
              <th className={clsx(HC, 'text-right')}>Conc%</th>
              <th className={clsx(HC, 'text-right')}>#Pos</th>
              <th className={clsx(HC, 'text-right')}>P&L</th>
            </tr>
          </thead>
          <tbody>
            {factors.map((f) => (
              <tr key={f.underlying} className={ROW}>
                <td className={clsx(DC, 'text-left font-semibold text-text-primary')}>{f.underlying}</td>
                <td className={clsx(DC, 'text-right')}>{n$(f.spot)}</td>
                <td className={clsx(DC, 'text-right', clr(f.delta))}>{g(f.delta)}</td>
                <td className={clsx(DC, 'text-right')}>{n(f.gamma, 4)}</td>
                <td className={clsx(DC, 'text-right', clr(f.theta))}>{g(f.theta)}</td>
                <td className={clsx(DC, 'text-right')}>{n(f.vega)}</td>
                <td className={clsx(DC, 'text-right', clr(f.delta_dollars))}>{n$(f.delta_dollars)}</td>
                <td className={clsx(DC, 'text-right',
                  f.concentration_pct > 30 ? 'text-accent-red' : f.concentration_pct > 20 ? 'text-accent-yellow' : ''
                )}>{pct(f.concentration_pct)}</td>
                <td className={clsx(DC, 'text-right text-text-secondary')}>{f.count}</td>
                <td className={clsx(DC, 'text-right', clr(f.pnl))}>{n(f.pnl)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// WhatIf Trades Section (compact)
// ---------------------------------------------------------------------------
function WhatIfSection({ trades, onBook }: { trades: TradingDashboardStrategy[]; onBook: (id: string) => void }) {
  if (!trades.length) return null
  return (
    <div className="border border-accent-blue/30 rounded overflow-hidden">
      <div className="bg-accent-blue/10 px-2 py-[3px] text-[10px] font-bold uppercase tracking-wider text-accent-blue border-b border-accent-blue/30 flex items-center justify-between">
        <span>WhatIf Trades ({trades.length})</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-border-secondary bg-bg-secondary">
              <th className={clsx(HC, 'text-left')}>UDL</th>
              <th className={clsx(HC, 'text-left')}>Type</th>
              <th className={clsx(HC, 'text-left')}>Legs</th>
              <th className={clsx(HC, 'text-right')}>DTE</th>
              <th className={clsx(HC, 'text-right')}>Δ</th>
              <th className={clsx(HC, 'text-right')}>Θ</th>
              <th className={clsx(HC, 'text-right')}>Margin</th>
              <th className={clsx(HC, 'text-right')}>MaxRisk</th>
              <th className={clsx(HC, 'text-right')}>P&L</th>
              <th className={clsx(HC, 'text-center')}>Action</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t) => (
              <tr key={t.trade_id} className={clsx(ROW, 'bg-accent-blue/5')}>
                <td className={clsx(DC, 'text-left font-semibold text-accent-blue')}>{t.underlying}</td>
                <td className={clsx(DC, 'text-left text-text-secondary')}>{t.strategy_type}</td>
                <td className={clsx(DC, 'text-left text-text-secondary text-[10px]')}>{t.legs_summary}</td>
                <td className={clsx(DC, 'text-right')}>{t.dte ?? '—'}</td>
                <td className={clsx(DC, 'text-right', clr(t.net_delta))}>{g(t.net_delta, 2)}</td>
                <td className={clsx(DC, 'text-right', clr(t.net_theta))}>{g(t.net_theta, 2)}</td>
                <td className={clsx(DC, 'text-right')}>{n$(t.margin_used)}</td>
                <td className={clsx(DC, 'text-right text-accent-red')}>{n$(t.max_risk)}</td>
                <td className={clsx(DC, 'text-right', clr(t.total_pnl))}>{n$(t.total_pnl)}</td>
                <td className={clsx(DC, 'text-center')}>
                  <button
                    onClick={() => onBook(t.trade_id)}
                    className="text-[9px] px-1.5 py-[1px] rounded bg-accent-blue/20 text-accent-blue hover:bg-accent-blue/30"
                  >
                    Book
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Template Evaluation
// ---------------------------------------------------------------------------
const TEMPLATES = [
  { name: 'correction_premium_sell', label: 'Correction Premium' },
  { name: 'earnings_iv_crush', label: 'Earnings IV Crush' },
  { name: 'black_swan_hedge', label: 'Black Swan Hedge' },
  { name: 'vol_arbitrage_calendar', label: 'Vol Arb Calendar' },
  { name: 'ma_crossover_rsi', label: 'MA Crossover RSI' },
  { name: 'bollinger_bounce', label: 'Bollinger Bounce' },
  { name: 'high_iv_iron_condor', label: 'High IV Iron Condor' },
]

function TemplateToolbar({
  evalTemplate,
  setEvalTemplate,
  onEvaluate,
  isPending,
  error,
}: {
  evalTemplate: string
  setEvalTemplate: (v: string) => void
  onEvaluate: () => void
  isPending: boolean
  error: Error | null
}) {
  return (
    <div className="flex items-center gap-2 border border-border-secondary rounded px-2 py-1 bg-bg-secondary">
      <span className="text-[10px] font-semibold text-text-muted uppercase">Evaluate Template:</span>
      <select
        value={evalTemplate}
        onChange={(e) => setEvalTemplate(e.target.value)}
        className="bg-bg-tertiary text-text-primary text-[11px] rounded px-1.5 py-[2px] border border-border-primary"
      >
        {TEMPLATES.map((t) => (
          <option key={t.name} value={t.name}>{t.label}</option>
        ))}
      </select>
      <button
        onClick={onEvaluate}
        disabled={isPending}
        className="px-2 py-[2px] rounded text-[10px] font-semibold bg-accent-blue text-white hover:bg-accent-blue/80 disabled:opacity-50"
      >
        {isPending ? 'Running...' : 'Run'}
      </button>
      {error && <span className="text-[10px] text-accent-red">{error.message}</span>}
    </div>
  )
}

function EvalResults({ result }: { result: TemplateEvaluationResult | null }) {
  if (!result) return null
  return (
    <div className="border border-border-secondary rounded overflow-hidden">
      <div className="bg-bg-tertiary px-2 py-[3px] text-[10px] font-bold uppercase tracking-wider text-text-muted border-b border-border-secondary flex items-center gap-3">
        <span>Template: {result.template.display_name}</span>
        <span className="text-text-secondary font-normal normal-case">{result.summary}</span>
      </div>
      <div className="divide-y divide-border-secondary/40">
        {result.evaluated_symbols.map((ev) => (
          <EvalSymbolRow key={ev.symbol} ev={ev} />
        ))}
      </div>
    </div>
  )
}

function EvalSymbolRow({ ev }: { ev: EvaluatedSymbol }) {
  const [open, setOpen] = useState(false)
  return (
    <div className={clsx('px-2 py-1', ev.triggered ? 'bg-accent-green/5' : '')}>
      <div className="flex items-center gap-3 cursor-pointer" onClick={() => setOpen(!open)}>
        <span className={clsx('text-[9px] font-bold px-1 rounded',
          ev.triggered ? 'bg-accent-green/20 text-accent-green' : 'bg-accent-red/20 text-accent-red'
        )}>
          {ev.triggered ? 'HIT' : 'MISS'}
        </span>
        <span className="text-[11px] font-mono font-semibold text-text-primary">{ev.symbol}</span>
        {ev.snapshot && <span className="text-[10px] text-text-muted font-mono">${n(ev.snapshot.price, 2)}</span>}
        {ev.proposed_trade && (
          <span className="text-[10px] font-mono text-text-secondary">
            {ev.proposed_trade.strategy_type}
            {ev.proposed_trade.pop != null && <> POP:{(ev.proposed_trade.pop * 100).toFixed(0)}%</>}
            {ev.proposed_trade.expected_value != null && (
              <span className={clr(ev.proposed_trade.expected_value)}> EV:${ev.proposed_trade.expected_value >= 0 ? '+' : ''}{ev.proposed_trade.expected_value.toFixed(0)}</span>
            )}
          </span>
        )}
      </div>
      {open && (
        <div className="ml-6 mt-1 text-[10px] space-y-1">
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(ev.conditions).map(([ind, c]) => (
              <span key={ind} className={clsx('px-1 py-[1px] rounded',
                c.passed ? 'bg-accent-green/20 text-accent-green' : 'bg-accent-red/20 text-accent-red'
              )}>
                {ind}: {c.actual != null ? (typeof c.actual === 'number' ? c.actual.toFixed(2) : String(c.actual)) : 'N/A'} {c.operator} {c.target != null ? String(c.target) : ''}
              </span>
            ))}
          </div>
          {ev.proposed_trade?.legs && (
            <div className="text-text-muted">
              {ev.proposed_trade.legs.map((l, i) => (
                <span key={i} className="mr-2">{l.side.toUpperCase()} {l.quantity} {l.option_type?.toUpperCase()} ${l.strike}</span>
              ))}
              {ev.proposed_trade.fits_portfolio != null && (
                <span className={clsx('ml-2 px-1 rounded',
                  ev.proposed_trade.fits_portfolio ? 'bg-accent-green/20 text-accent-green' : 'bg-accent-red/20 text-accent-red'
                )}>
                  {ev.proposed_trade.fits_portfolio ? 'FITS' : 'NO FIT'}
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------
export function TradingDashboardPage() {
  const { data: portfolios, isLoading: loadingPf } = usePortfolios()
  const [selectedPortfolio, setSelectedPortfolio] = useState('Tastytrade 5WZ78765')
  const [snapshotEnabled, setSnapshotEnabled] = useState(false)
  const [evalResult, setEvalResult] = useState<TemplateEvaluationResult | null>(null)
  const [evalTemplate, setEvalTemplate] = useState(TEMPLATES[0].name)

  const { data, isLoading, error } = useTradingDashboard(selectedPortfolio)
  const refreshMutation = useRefreshDashboard(selectedPortfolio)
  const evaluateMutation = useEvaluateTemplate(selectedPortfolio)
  const bookMutation = useBookTrade(selectedPortfolio)

  const realPortfolios = useMemo(
    () => portfolios?.filter((p) => p.portfolio_type === 'real') ?? [],
    [portfolios],
  )

  const handleRefresh = () => refreshMutation.mutate(snapshotEnabled)
  const handleEvaluate = async () => {
    try {
      const result = await evaluateMutation.mutateAsync(evalTemplate)
      setEvalResult(result)
    } catch { /* mutation handles error */ }
  }
  const handleBook = async (tradeId: string) => {
    try { await bookMutation.mutateAsync(tradeId) } catch { /* handled */ }
  }

  if (loadingPf) {
    return <div className="flex items-center justify-center h-full"><Spinner size="lg" /></div>
  }

  return (
    <div className="space-y-1.5 pb-4">
      {/* Agent ownership */}
      <div className="flex items-center gap-1.5">
        <AgentBadge agent="scout" />
        <AgentBadge agent="sentinel" />
      </div>
      {/* Toolbar: portfolio tabs + refresh */}
      <div className="flex items-center gap-2 flex-wrap">
        {realPortfolios.map((p) => (
          <button
            key={p.name}
            onClick={() => setSelectedPortfolio(p.name)}
            className={clsx(
              'px-2 py-[3px] rounded text-[11px] font-mono',
              selectedPortfolio === p.name
                ? 'bg-accent-blue text-white'
                : 'bg-bg-tertiary text-text-secondary hover:bg-bg-hover',
            )}
          >
            {p.name}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          {/* Snapshot toggle */}
          <label className="flex items-center gap-1 cursor-pointer">
            <span className="text-[10px] text-text-muted">Snapshot</span>
            <input
              type="checkbox"
              checked={snapshotEnabled}
              onChange={(e) => setSnapshotEnabled(e.target.checked)}
              className="w-3 h-3 accent-accent-blue"
            />
          </label>
          {/* Refresh button */}
          <button
            onClick={handleRefresh}
            disabled={refreshMutation.isPending}
            className={clsx(
              'px-2 py-[3px] rounded text-[10px] font-semibold',
              refreshMutation.isPending
                ? 'bg-bg-tertiary text-text-muted animate-pulse'
                : 'bg-accent-cyan/20 text-accent-cyan hover:bg-accent-cyan/30',
            )}
          >
            {refreshMutation.isPending ? 'Syncing...' : 'Refresh'}
          </button>
          {refreshMutation.isSuccess && (
            <span className="text-[9px] text-accent-green">
              {refreshMutation.data.broker_synced ? 'Synced' : 'Refreshed'}
              {refreshMutation.data.snapshot_captured ? ' + Snap' : ''}
            </span>
          )}
        </div>
      </div>

      {isLoading && <div className="flex items-center justify-center py-8"><Spinner size="md" /></div>}
      {error && <div className="text-[11px] text-accent-red border border-accent-red/30 rounded px-2 py-1">Error: {(error as Error).message}</div>}

      {data && (
        <>
          {/* Portfolio Summary */}
          <SummaryStrip p={data.portfolio} />

          {/* Strategies (Table 1) + Risk Factors (Table 3) side by side */}
          <div className="grid grid-cols-[3fr_2fr] gap-1.5">
            <StrategiesTable strategies={data.strategies} />
            <RiskFactorsTable factors={data.risk_factors} />
          </div>

          {/* Table 2: Positions (full width — many columns) */}
          <PositionsTable positions={data.positions} />

          {/* WhatIf Trades */}
          <WhatIfSection trades={data.whatif_trades} onBook={handleBook} />

          {/* Template Evaluation */}
          <TemplateToolbar
            evalTemplate={evalTemplate}
            setEvalTemplate={setEvalTemplate}
            onEvaluate={handleEvaluate}
            isPending={evaluateMutation.isPending}
            error={evaluateMutation.error}
          />
          <EvalResults result={evalResult} />
        </>
      )}
    </div>
  )
}
