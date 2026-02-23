import { useState, useMemo, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { clsx } from 'clsx'
import { Check, Trash2, Plus } from 'lucide-react'
import { useRegimeResearch, useRegimeChart, useTechnicals, useFundamentals } from '../hooks/useRegime'
import { useResearchTicker, useStrategies, useWatchlist } from '../hooks/useResearch'
import { usePortfolios } from '../hooks/usePortfolios'
import {
  useTradingDashboard,
  useRefreshDashboard,
  useEvaluateTemplate,
  useBookTrade,
  useDeleteWhatIf,
  useAddWhatIf,
} from '../hooks/useTradingDashboard'
import { Spinner } from '../components/common/Spinner'
import type {
  FeatureZScore,
  TransitionRow,
  RegimeDistributionEntry,
  RegimeHistoryDay,
  StateMeansRow,
  TechnicalSignal,
  ResearchEntry as ResearchEntryType,
  StrategyProposal,
  TradingDashboardPortfolio,
  TradingDashboardStrategy,
  TradingDashboardPosition,
  TradingDashboardRiskFactor,
  TemplateEvaluationResult,
  EvaluatedSymbol,
} from '../api/types'

// ---------------------------------------------------------------------------
// Formatters (from TradingDashboardPage pattern)
// ---------------------------------------------------------------------------
const n = (v: number | null | undefined, d = 2) =>
  v == null ? '\u2014' : v.toFixed(d)
const n$ = (v: number | null | undefined) =>
  v == null ? '\u2014' : v < 0
    ? `-$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
    : `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
const pct = (v: number | null | undefined, d = 1) =>
  v == null ? '\u2014' : `${v.toFixed(d)}%`
const g = (v: number | null | undefined, d = 2) =>
  v == null ? '\u2014' : `${v >= 0 ? '+' : ''}${v.toFixed(d)}`
const clr = (v: number | null | undefined) =>
  !v ? 'text-text-muted' : v > 0 ? 'text-accent-green' : 'text-accent-red'

const HC = 'py-[3px] px-1.5 text-[10px] font-semibold text-text-muted whitespace-nowrap'
const GH = 'py-[2px] px-1.5 text-[9px] font-bold uppercase tracking-wider text-text-muted bg-bg-tertiary border-b border-border-secondary'
const DC = 'py-[3px] px-1.5 text-[11px] font-mono whitespace-nowrap'
const ROW = 'border-b border-border-secondary/40 hover:bg-bg-hover/50'

// Analysis tab formatters
function fmtNum(v: number | null | undefined, decimals = 2): string {
  if (v == null) return '--'
  return v.toFixed(decimals)
}
function fmtPct(v: number | null | undefined): string {
  if (v == null) return '--'
  return `${(v * 100).toFixed(1)}%`
}
function fmtBigNum(v: number | null | undefined): string {
  if (v == null) return '--'
  if (Math.abs(v) >= 1e12) return `${(v / 1e12).toFixed(1)}T`
  if (Math.abs(v) >= 1e9) return `${(v / 1e9).toFixed(1)}B`
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  return v.toLocaleString()
}

// Regime color config (for analysis tab)
const RC: Record<number, { color: string; bg: string; border: string; label: string }> = {
  1: { color: 'text-green-400', bg: 'bg-green-900/30', border: 'border-green-700', label: 'Low Vol MR' },
  2: { color: 'text-amber-400', bg: 'bg-amber-900/30', border: 'border-amber-700', label: 'High Vol MR' },
  3: { color: 'text-blue-400', bg: 'bg-blue-900/30', border: 'border-blue-700', label: 'Low Vol Trend' },
  4: { color: 'text-red-400', bg: 'bg-red-900/30', border: 'border-red-700', label: 'High Vol Trend' },
}
function getRC(r: number) { return RC[r] || { color: 'text-text-muted', bg: 'bg-bg-tertiary', border: 'border-border-secondary', label: '?' } }

// ---------------------------------------------------------------------------
// KPI Pill
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
// Portfolio Summary Strip
// ---------------------------------------------------------------------------
function SummaryStrip({ p }: { p: TradingDashboardPortfolio }) {
  return (
    <div className="border border-border-secondary rounded px-3 py-1.5 bg-bg-secondary space-y-0.5">
      <div className="flex items-center gap-4 flex-wrap">
        <KPI label="Equity" value={n$(p.total_equity)} />
        <KPI label="Cash" value={n$(p.cash_balance)} />
        <KPI label="BP" value={n$(p.buying_power)} />
        <KPI label="Deployed" value={pct(p.capital_deployed_pct)} color={p.capital_deployed_pct > 60 ? 'text-accent-yellow' : undefined} />
        <span className="text-border-secondary">|</span>
        <KPI label="\u0394" value={g(p.net_delta, 1)} color={clr(p.net_delta)} />
        <KPI label="\u0398/d" value={`$${n(p.net_theta, 0)}`} color="text-accent-green" />
        <KPI label="\u0393" value={n(p.net_gamma, 4)} />
        <KPI label="\u03BD" value={g(p.net_vega, 1)} color={clr(-Math.abs(p.net_vega))} />
        <span className="text-border-secondary">|</span>
        <KPI label="VaR" value={n$(p.var_1d_95)} color={p.var_1d_95 > p.total_equity * 0.02 ? 'text-accent-red' : undefined} />
        <KPI label="\u0398/VaR" value={p.theta_var_ratio ? pct(p.theta_var_ratio * 100) : '\u2014'} color="text-accent-cyan" />
        <KPI label="\u0394 util" value={pct(p.delta_utilization_pct)} color={p.delta_utilization_pct > 70 ? 'text-accent-red' : undefined} />
      </div>
      <div className="flex items-center gap-4 flex-wrap text-[10px]">
        <span className="text-text-muted">Strategies: <span className="text-text-primary font-mono">{p.open_strategies}</span></span>
        <span className="text-text-muted">Positions: <span className="text-text-primary font-mono">{p.open_positions}</span></span>
        <span className="text-text-muted">WhatIf: <span className="text-accent-blue font-mono">{p.whatif_count}</span></span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Strategies Table — merged real + WhatIf, checkbox only on WhatIf rows
// ---------------------------------------------------------------------------
function StrategiesTable({
  strategies,
  whatifTrades,
  portfolioName,
  checkedIds,
  onToggle,
  onBook,
  onDelete,
  bookPending,
  deletePending,
}: {
  strategies: TradingDashboardStrategy[]
  whatifTrades: TradingDashboardStrategy[]
  portfolioName: string
  checkedIds: Set<string>
  onToggle: (id: string) => void
  onBook: (id: string) => void
  onDelete: (id: string) => void
  bookPending: boolean
  deletePending: boolean
}) {
  const allRows = useMemo(() => {
    const real = strategies.map(s => ({ ...s, _isWhatIf: false, _portfolio: portfolioName }))
    const wi = whatifTrades.map(s => ({ ...s, _isWhatIf: true, _portfolio: 'WhatIf' }))
    return [...real, ...wi]
  }, [strategies, whatifTrades, portfolioName])

  // Checked WhatIf summary
  const checkedSummary = useMemo(() => {
    let delta = 0, theta = 0, gamma = 0, vega = 0, maxRisk = 0, count = 0
    for (const t of whatifTrades) {
      if (checkedIds.has(t.trade_id)) {
        delta += t.net_delta; theta += t.net_theta; gamma += t.net_gamma
        vega += t.net_vega; maxRisk += t.max_risk; count++
      }
    }
    return { delta, theta, gamma, vega, maxRisk, count }
  }, [whatifTrades, checkedIds])

  if (!allRows.length) {
    return <div className="text-[11px] text-text-muted text-center py-2 border border-border-secondary/40 rounded">No open strategies</div>
  }
  return (
    <div className="border border-border-secondary rounded overflow-hidden">
      <div className="bg-bg-tertiary px-2 py-[3px] text-[10px] font-bold uppercase tracking-wider text-text-muted border-b border-border-secondary">
        Strategies ({strategies.length} real{whatifTrades.length > 0 ? ` + ${whatifTrades.length} whatif` : ''})
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-border-secondary bg-bg-secondary">
              <th className={clsx(HC, 'w-6')}></th>
              <th className={clsx(HC, 'text-left')}>Port</th>
              <th className={clsx(HC, 'text-left')}>UDL</th>
              <th className={clsx(HC, 'text-left')}>Type</th>
              <th className={clsx(HC, 'text-left')}>Legs</th>
              <th className={clsx(HC, 'text-right')}>DTE</th>
              <th className={clsx(HC, 'text-right')}>Qty</th>
              <th className={clsx(HC, 'text-right')}>Entry$</th>
              <th className={clsx(HC, 'text-right')}>MaxRisk</th>
              <th className={clsx(HC, 'text-right')}>MR/BP</th>
              <th className={clsx(HC, 'text-right')}>{'\u0394'}</th>
              <th className={clsx(HC, 'text-right')}>{'\u0398'}</th>
              <th className={clsx(HC, 'text-right')}>P&L</th>
              <th className={clsx(HC, 'text-right')}>P&L%</th>
              <th className={clsx(HC, 'text-center')}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {allRows.map((s) => (
              <tr key={s.trade_id} className={clsx(ROW, s._isWhatIf && checkedIds.has(s.trade_id) && 'bg-accent-blue/5')}>
                <td className={clsx(DC, 'text-center')}>
                  {s._isWhatIf ? (
                    <button
                      onClick={() => onToggle(s.trade_id)}
                      className={clsx(
                        'w-4 h-4 rounded border flex items-center justify-center',
                        checkedIds.has(s.trade_id)
                          ? 'bg-accent-blue border-accent-blue text-white'
                          : 'border-border-secondary',
                      )}
                    >
                      {checkedIds.has(s.trade_id) && <Check size={10} />}
                    </button>
                  ) : null}
                </td>
                <td className={clsx(DC, 'text-left')}>
                  <span className={clsx('text-[9px] px-1 rounded font-semibold',
                    s._isWhatIf ? 'bg-accent-blue/20 text-accent-blue' : 'bg-bg-tertiary text-text-secondary'
                  )}>{s._isWhatIf ? 'WI' : 'Real'}</span>
                </td>
                <td className={clsx(DC, 'text-left font-semibold', s._isWhatIf ? 'text-accent-blue' : 'text-text-primary')}>{s.underlying}</td>
                <td className={clsx(DC, 'text-left text-text-secondary')}>{s.strategy_type}</td>
                <td className={clsx(DC, 'text-left text-text-secondary text-[10px]')} title={s.legs_summary}>{s.legs_summary}</td>
                <td className={clsx(DC, 'text-right', s.dte != null && s.dte <= 7 ? 'text-accent-red' : '')}>{s.dte ?? '\u2014'}</td>
                <td className={clsx(DC, 'text-right')}>{s.quantity}</td>
                <td className={clsx(DC, 'text-right')}>{n(s.entry_cost)}</td>
                <td className={clsx(DC, 'text-right text-accent-red')}>{n$(s.max_risk)}</td>
                <td className={clsx(DC, 'text-right')}>{pct(s.max_risk_pct_total_bp)}</td>
                <td className={clsx(DC, 'text-right', clr(s.net_delta))}>{g(s.net_delta, 2)}</td>
                <td className={clsx(DC, 'text-right', clr(s.net_theta))}>{g(s.net_theta, 2)}</td>
                <td className={clsx(DC, 'text-right', clr(s.total_pnl))}>{n$(s.total_pnl)}</td>
                <td className={clsx(DC, 'text-right', clr(s.pnl_pct))}>{pct(s.pnl_pct)}</td>
                <td className={clsx(DC, 'text-center')}>
                  {s._isWhatIf ? (
                    <div className="flex items-center justify-center gap-1">
                      <button onClick={() => onBook(s.trade_id)} disabled={bookPending}
                        className="text-[9px] px-1.5 py-[1px] rounded bg-accent-blue/20 text-accent-blue hover:bg-accent-blue/30 disabled:opacity-50">
                        Book
                      </button>
                      <button onClick={() => onDelete(s.trade_id)} disabled={deletePending}
                        className="text-[9px] px-1 py-[1px] rounded bg-accent-red/20 text-accent-red hover:bg-accent-red/30 disabled:opacity-50">
                        <Trash2 size={10} />
                      </button>
                    </div>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {/* Checked WhatIf summary */}
      {checkedSummary.count > 0 && (
        <div className="flex items-center gap-4 px-2 py-1 bg-accent-blue/5 border-t border-accent-blue/20 text-[10px]">
          <span className="font-semibold text-accent-blue">Checked ({checkedSummary.count}):</span>
          <KPI label={'\u0394'} value={g(checkedSummary.delta, 2)} color={clr(checkedSummary.delta)} />
          <KPI label={'\u0398/d'} value={`$${n(checkedSummary.theta, 0)}`} color={clr(checkedSummary.theta)} />
          <KPI label={'\u0393'} value={n(checkedSummary.gamma, 4)} />
          <KPI label={'\u03BD'} value={g(checkedSummary.vega, 2)} />
          <KPI label="MaxRisk" value={n$(checkedSummary.maxRisk)} color="text-accent-red" />
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Positions Table — merged real + WhatIf, checkbox only on WhatIf rows
// ---------------------------------------------------------------------------
function PositionsTable({
  positions, whatifPositions, checkedIds, onToggle,
}: {
  positions: TradingDashboardPosition[]
  whatifPositions: TradingDashboardPosition[]
  checkedIds: Set<string>
  onToggle: (id: string) => void
}) {
  const allRows = useMemo(() => {
    const real = positions.map(p => ({ ...p, _isWhatIf: false }))
    const wi = whatifPositions.map(p => ({ ...p, _isWhatIf: true }))
    return [...real, ...wi]
  }, [positions, whatifPositions])

  if (!allRows.length) {
    return <div className="text-[11px] text-text-muted text-center py-2 border border-border-secondary/40 rounded">No positions</div>
  }
  return (
    <div className="border border-border-secondary rounded overflow-hidden">
      <div className="bg-bg-tertiary px-2 py-[3px] text-[10px] font-bold uppercase tracking-wider text-text-muted border-b border-border-secondary">
        Positions ({positions.length} real{whatifPositions.length > 0 ? ` + ${whatifPositions.length} whatif` : ''})
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-bg-secondary">
              <th className={clsx(GH, 'w-6')}></th>
              <th className={clsx(GH, 'text-left')}>Port</th>
              <th colSpan={5} className={clsx(GH, 'text-left border-r border-border-secondary')}>Trade</th>
              <th colSpan={6} className={clsx(GH, 'text-center border-r border-border-secondary')}>Entry Greeks</th>
              <th colSpan={6} className={clsx(GH, 'text-center border-r border-border-secondary')}>Current</th>
              <th colSpan={5} className={clsx(GH, 'text-center border-r border-border-secondary')}>P&L Attribution</th>
              <th colSpan={3} className={clsx(GH, 'text-center')}>Total</th>
            </tr>
            <tr className="border-b border-border-secondary bg-bg-secondary">
              <th className={clsx(HC, 'w-6')}></th>
              <th className={clsx(HC, 'text-left')}>Port</th>
              <th className={clsx(HC, 'text-left')}>UDL</th>
              <th className={clsx(HC, 'text-center')}>Tp</th>
              <th className={clsx(HC, 'text-right')}>K</th>
              <th className={clsx(HC, 'text-right')}>DTE</th>
              <th className={clsx(HC, 'text-right border-r border-border-secondary/60')}>Qty</th>
              <th className={clsx(HC, 'text-right')}>Pr</th>
              <th className={clsx(HC, 'text-right')}>{'\u0394'}</th>
              <th className={clsx(HC, 'text-right')}>{'\u0393'}</th>
              <th className={clsx(HC, 'text-right')}>{'\u0398'}</th>
              <th className={clsx(HC, 'text-right')}>{'\u03BD'}</th>
              <th className={clsx(HC, 'text-right border-r border-border-secondary/60')}>IV</th>
              <th className={clsx(HC, 'text-right')}>Pr</th>
              <th className={clsx(HC, 'text-right')}>{'\u0394'}</th>
              <th className={clsx(HC, 'text-right')}>{'\u0393'}</th>
              <th className={clsx(HC, 'text-right')}>{'\u0398'}</th>
              <th className={clsx(HC, 'text-right')}>{'\u03BD'}</th>
              <th className={clsx(HC, 'text-right border-r border-border-secondary/60')}>IV</th>
              <th className={clsx(HC, 'text-right')}>{'\u0394'}</th>
              <th className={clsx(HC, 'text-right')}>{'\u0393'}</th>
              <th className={clsx(HC, 'text-right')}>{'\u0398'}</th>
              <th className={clsx(HC, 'text-right')}>{'\u03BD'}</th>
              <th className={clsx(HC, 'text-right border-r border-border-secondary/60')}>Ux</th>
              <th className={clsx(HC, 'text-right')}>P&L</th>
              <th className={clsx(HC, 'text-right')}>Bkr</th>
              <th className={clsx(HC, 'text-right')}>%</th>
            </tr>
          </thead>
          <tbody>
            {allRows.map((p) => {
              const wiChecked = p._isWhatIf && p.trade_id && checkedIds.has(p.trade_id)
              return (
                <tr key={p.id} className={clsx(ROW, wiChecked && 'bg-accent-blue/5')}>
                  <td className={clsx(DC, 'text-center')}>
                    {p._isWhatIf && p.trade_id ? (
                      <button
                        onClick={() => onToggle(p.trade_id!)}
                        className={clsx(
                          'w-4 h-4 rounded border flex items-center justify-center',
                          wiChecked ? 'bg-accent-blue border-accent-blue text-white' : 'border-border-secondary',
                        )}
                      >
                        {wiChecked && <Check size={10} />}
                      </button>
                    ) : null}
                  </td>
                  <td className={clsx(DC, 'text-left')}>
                    <span className={clsx('text-[9px] px-1 rounded font-semibold',
                      p._isWhatIf ? 'bg-accent-blue/20 text-accent-blue' : 'bg-bg-tertiary text-text-secondary'
                    )}>{p._isWhatIf ? 'WI' : 'Real'}</span>
                  </td>
                  <td className={clsx(DC, 'text-left font-semibold', p._isWhatIf ? 'text-accent-blue' : 'text-text-primary')}>{p.underlying || p.symbol}</td>
                  <td className={clsx(DC, 'text-center')}>
                    <span className={clsx('text-[9px] px-0.5 rounded',
                      p.option_type === 'put' ? 'bg-accent-red/20 text-accent-red'
                      : p.option_type === 'call' ? 'bg-accent-green/20 text-accent-green'
                      : 'bg-accent-blue/20 text-accent-blue'
                    )}>
                      {p.option_type?.charAt(0).toUpperCase() || 'E'}
                    </span>
                  </td>
                  <td className={clsx(DC, 'text-right')}>{p.strike ? n(p.strike, 1) : '\u2014'}</td>
                  <td className={clsx(DC, 'text-right', p.dte != null && p.dte <= 7 ? 'text-accent-red font-semibold' : '')}>{p.dte ?? '\u2014'}</td>
                  <td className={clsx(DC, 'text-right border-r border-border-secondary/30', p.quantity < 0 ? 'text-accent-red' : 'text-accent-green')}>{p.quantity}</td>
                  <td className={clsx(DC, 'text-right text-text-secondary')}>{n(p.entry_price)}</td>
                  <td className={clsx(DC, 'text-right text-text-secondary')}>{n(p.entry_delta)}</td>
                  <td className={clsx(DC, 'text-right text-text-secondary')}>{n(p.entry_gamma, 4)}</td>
                  <td className={clsx(DC, 'text-right text-text-secondary')}>{n(p.entry_theta)}</td>
                  <td className={clsx(DC, 'text-right text-text-secondary')}>{n(p.entry_vega)}</td>
                  <td className={clsx(DC, 'text-right text-text-secondary border-r border-border-secondary/30')}>{n(p.entry_iv, 1)}</td>
                  <td className={clsx(DC, 'text-right')}>{n(p.current_price)}</td>
                  <td className={clsx(DC, 'text-right', clr(p.delta))}>{g(p.delta)}</td>
                  <td className={clsx(DC, 'text-right')}>{n(p.gamma, 4)}</td>
                  <td className={clsx(DC, 'text-right', clr(p.theta))}>{g(p.theta)}</td>
                  <td className={clsx(DC, 'text-right')}>{n(p.vega)}</td>
                  <td className={clsx(DC, 'text-right border-r border-border-secondary/30')}>{n(p.iv, 1)}</td>
                  <td className={clsx(DC, 'text-right', clr(p.pnl_delta))}>{n(p.pnl_delta)}</td>
                  <td className={clsx(DC, 'text-right', clr(p.pnl_gamma))}>{n(p.pnl_gamma)}</td>
                  <td className={clsx(DC, 'text-right', clr(p.pnl_theta))}>{n(p.pnl_theta)}</td>
                  <td className={clsx(DC, 'text-right', clr(p.pnl_vega))}>{n(p.pnl_vega)}</td>
                  <td className={clsx(DC, 'text-right border-r border-border-secondary/30', clr(p.pnl_unexplained))}>{n(p.pnl_unexplained)}</td>
                  <td className={clsx(DC, 'text-right font-semibold', clr(p.total_pnl))}>{n(p.total_pnl)}</td>
                  <td className={clsx(DC, 'text-right', clr(p.broker_pnl))}>{n(p.broker_pnl)}</td>
                  <td className={clsx(DC, 'text-right', clr(p.pnl_pct))}>{pct(p.pnl_pct)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Risk Factors Table — merged real + WhatIf, checkbox only on WhatIf rows
// ---------------------------------------------------------------------------
function RiskFactorsTable({
  factors, whatifFactors, checkedIds, onToggle,
}: {
  factors: TradingDashboardRiskFactor[]
  whatifFactors: TradingDashboardRiskFactor[]
  checkedIds: Set<string>
  onToggle: (id: string) => void
}) {
  const allRows = useMemo(() => {
    const real = factors.map(f => ({ ...f, _isWhatIf: false }))
    const wi = whatifFactors.map(f => ({ ...f, _isWhatIf: true }))
    return [...real, ...wi]
  }, [factors, whatifFactors])

  if (!allRows.length) return null
  return (
    <div className="border border-border-secondary rounded overflow-hidden">
      <div className="bg-bg-tertiary px-2 py-[3px] text-[10px] font-bold uppercase tracking-wider text-text-muted border-b border-border-secondary">
        Risk Factors ({factors.length} real{whatifFactors.length > 0 ? ` + ${whatifFactors.length} whatif` : ''})
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="border-b border-border-secondary bg-bg-secondary">
              <th className={clsx(HC, 'w-6')}></th>
              <th className={clsx(HC, 'text-left')}>Port</th>
              <th className={clsx(HC, 'text-left')}>UDL</th>
              <th className={clsx(HC, 'text-right')}>Spot</th>
              <th className={clsx(HC, 'text-right')}>{'\u0394'}</th>
              <th className={clsx(HC, 'text-right')}>{'\u0393'}</th>
              <th className={clsx(HC, 'text-right')}>{'\u0398'}</th>
              <th className={clsx(HC, 'text-right')}>{'\u03BD'}</th>
              <th className={clsx(HC, 'text-right')}>{'\u0394'}$</th>
              <th className={clsx(HC, 'text-right')}>Conc%</th>
              <th className={clsx(HC, 'text-right')}>#</th>
              <th className={clsx(HC, 'text-right')}>P&L</th>
            </tr>
          </thead>
          <tbody>
            {allRows.map((f) => {
              const wiKey = f._isWhatIf ? `wi_rf_${f.underlying}` : ''
              const wiChecked = f._isWhatIf && checkedIds.has(wiKey)
              return (
                <tr key={f._isWhatIf ? `wi-${f.underlying}` : f.underlying} className={clsx(ROW, wiChecked && 'bg-accent-blue/5')}>
                  <td className={clsx(DC, 'text-center')}>
                    {f._isWhatIf ? (
                      <button
                        onClick={() => onToggle(wiKey)}
                        className={clsx(
                          'w-4 h-4 rounded border flex items-center justify-center',
                          wiChecked ? 'bg-accent-blue border-accent-blue text-white' : 'border-border-secondary',
                        )}
                      >
                        {wiChecked && <Check size={10} />}
                      </button>
                    ) : null}
                  </td>
                  <td className={clsx(DC, 'text-left')}>
                    <span className={clsx('text-[9px] px-1 rounded font-semibold',
                      f._isWhatIf ? 'bg-accent-blue/20 text-accent-blue' : 'bg-bg-tertiary text-text-secondary'
                    )}>{f._isWhatIf ? 'WI' : 'Real'}</span>
                  </td>
                  <td className={clsx(DC, 'text-left font-semibold', f._isWhatIf ? 'text-accent-blue' : 'text-text-primary')}>{f.underlying}</td>
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
              )
            })}
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
  evalTemplate, setEvalTemplate, onEvaluate, isPending, error,
}: {
  evalTemplate: string; setEvalTemplate: (v: string) => void
  onEvaluate: () => void; isPending: boolean; error: Error | null
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
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ===========================================================================
// MAIN PAGE — Trade Blotter
// ===========================================================================

export function TradeBlotterPage() {
  const { ticker: urlTicker } = useParams<{ ticker: string }>()

  // State
  const [selectedUnderlying, setSelectedUnderlying] = useState(urlTicker?.toUpperCase() || '')
  const [selectedPortfolio, setSelectedPortfolio] = useState('Tastytrade 5WZ78765')
  const [activeTab, setActiveTab] = useState<'blotter' | 'analysis'>('blotter')
  const [checkedWhatIfs, setCheckedWhatIfs] = useState<Set<string>>(new Set())
  const [evalResult, setEvalResult] = useState<TemplateEvaluationResult | null>(null)
  const [evalTemplate, setEvalTemplate] = useState(TEMPLATES[0].name)
  const [snapshotEnabled, setSnapshotEnabled] = useState(false)

  // WhatIf portfolio: derive from real portfolio name
  const whatifPortfolio = useMemo(() => {
    // Real portfolios have display names like "Tastytrade 5WZ78765"
    // WhatIf portfolios are named e.g. "Tastytrade (WhatIf)"
    // We hardcode to the known whatif portfolio name for now
    return 'Tastytrade (WhatIf)'
  }, [])

  // Data fetching
  const { data: watchlistData } = useWatchlist()
  const { data: portfolios } = usePortfolios()
  const { data: dashData, isLoading: dashLoading, error: dashError } = useTradingDashboard(selectedPortfolio)
  const { data: whatifDashData } = useTradingDashboard(whatifPortfolio)
  const refreshMutation = useRefreshDashboard(selectedPortfolio)
  const evaluateMutation = useEvaluateTemplate(selectedPortfolio)
  const bookMutation = useBookTrade(whatifPortfolio)
  const deleteMutation = useDeleteWhatIf(whatifPortfolio)
  const addWhatIf = useAddWhatIf(whatifPortfolio)

  // Analysis tab data
  const { data: researchEntry } = useResearchTicker(selectedUnderlying || null)
  const { data: strategiesData, isLoading: strategiesLoading } = useStrategies(
    selectedUnderlying || null, selectedPortfolio,
  )

  // Real portfolios for selector
  const realPortfolios = useMemo(
    () => portfolios?.filter((p) => p.portfolio_type === 'real') ?? [],
    [portfolios],
  )

  // Watchlist items for underlying dropdown (fallback: derive from dashboard data)
  const watchlistItems = useMemo(() => {
    if (watchlistData?.watchlist?.length) return watchlistData.watchlist
    // Fallback: derive tickers from dashboard strategies
    if (dashData?.strategies) {
      const seen = new Set<string>()
      const items: { ticker: string; name: string; asset_class: string }[] = []
      for (const s of dashData.strategies) {
        if (s.underlying && !seen.has(s.underlying)) {
          seen.add(s.underlying)
          items.push({ ticker: s.underlying, name: s.underlying, asset_class: 'equity' })
        }
      }
      return items
    }
    return []
  }, [watchlistData, dashData])

  // All WhatIf trades (from whatif portfolio, NOT filtered by underlying)
  const whatifTrades = useMemo(
    () => whatifDashData?.whatif_trades ?? [],
    [whatifDashData],
  )

  // Toggle checkbox
  const toggleWhatIf = useCallback((tradeId: string) => {
    setCheckedWhatIfs(prev => {
      const next = new Set(prev)
      if (next.has(tradeId)) next.delete(tradeId)
      else next.add(tradeId)
      return next
    })
  }, [])

  // Handlers
  const handleRefresh = () => refreshMutation.mutate(snapshotEnabled)
  const handleEvaluate = async () => {
    try {
      const result = await evaluateMutation.mutateAsync(evalTemplate)
      setEvalResult(result)
    } catch { /* mutation handles error */ }
  }
  const handleBook = async (tradeId: string) => {
    try {
      await bookMutation.mutateAsync(tradeId)
      checkedWhatIfs.delete(tradeId)
      setCheckedWhatIfs(new Set(checkedWhatIfs))
    } catch { /* handled */ }
  }
  const handleDelete = async (tradeId: string) => {
    try {
      await deleteMutation.mutateAsync(tradeId)
      checkedWhatIfs.delete(tradeId)
      setCheckedWhatIfs(new Set(checkedWhatIfs))
    } catch { /* handled */ }
  }
  const handleAddStrategy = useCallback((proposal: StrategyProposal) => {
    addWhatIf.mutate({
      underlying: selectedUnderlying,
      strategy_type: proposal.strategy_type,
      legs: proposal.legs.map(l => ({
        option_type: l.option_type,
        strike: l.strike,
        quantity: l.quantity,
        side: l.side,
        expiration: l.expiration,
      })),
      notes: `${proposal.display_name} (Score: ${proposal.score}) from blotter`,
    }, {
      onSuccess: (result: { trade_id: string }) => {
        setCheckedWhatIfs(prev => new Set(prev).add(result.trade_id))
      },
    })
  }, [selectedUnderlying, addWhatIf])

  return (
    <div className="space-y-1.5 pb-4">
      {/* Header: Title + Underlying Dropdown + Portfolio Selector */}
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-sm font-bold text-text-primary">Trade Blotter</h1>

        {/* Underlying dropdown */}
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-text-muted">Underlying:</span>
          <select
            value={selectedUnderlying}
            onChange={(e) => setSelectedUnderlying(e.target.value)}
            className="bg-bg-tertiary text-text-primary text-[11px] rounded px-1.5 py-[2px] border border-border-primary font-mono"
          >
            <option value="">All</option>
            {watchlistItems.map((w) => (
              <option key={w.ticker} value={w.ticker}>{w.ticker}</option>
            ))}
          </select>
        </div>

        {/* Portfolio tabs */}
        <div className="flex items-center gap-1 ml-auto">
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
          <label className="flex items-center gap-1 cursor-pointer ml-2">
            <span className="text-[10px] text-text-muted">Snap</span>
            <input
              type="checkbox"
              checked={snapshotEnabled}
              onChange={(e) => setSnapshotEnabled(e.target.checked)}
              className="w-3 h-3 accent-accent-blue"
            />
          </label>
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
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex items-center gap-1 border-b border-border-secondary">
        {(['blotter', 'analysis'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={clsx(
              'px-3 py-1.5 text-xs font-semibold uppercase tracking-wider border-b-2 -mb-px transition-colors',
              activeTab === tab
                ? 'border-accent-blue text-accent-blue'
                : 'border-transparent text-text-muted hover:text-text-secondary',
            )}
          >
            {tab === 'blotter' ? 'Blotter' : 'Analysis'}
          </button>
        ))}
        {activeTab === 'analysis' && selectedUnderlying && strategiesData && (
          <div className="ml-auto flex items-center gap-2 text-xs text-text-muted pb-1">
            <span>Spot: <span className="font-mono text-text-primary">${fmtNum(strategiesData.spot)}</span></span>
            <span>IV: <span className="font-mono text-text-primary">{fmtPct(strategiesData.iv)}</span></span>
            {strategiesData.regime && <span>Regime: <span className="font-mono text-text-primary">{strategiesData.regime}</span></span>}
          </div>
        )}
      </div>

      {/* BLOTTER TAB */}
      {activeTab === 'blotter' && (
        <>
          {dashLoading && <div className="flex items-center justify-center py-8"><Spinner size="md" /></div>}
          {dashError && <div className="text-[11px] text-accent-red border border-accent-red/30 rounded px-2 py-1">Error: {(dashError as Error).message}</div>}

          {dashData && (
            <>
              <SummaryStrip p={dashData.portfolio} />

              {/* Strategies (real + WhatIf merged) + Risk Factors side by side */}
              <div className="grid grid-cols-[3fr_2fr] gap-1.5">
                <StrategiesTable
                  strategies={dashData.strategies}
                  whatifTrades={whatifTrades}
                  portfolioName={selectedPortfolio}
                  checkedIds={checkedWhatIfs}
                  onToggle={toggleWhatIf}
                  onBook={handleBook}
                  onDelete={handleDelete}
                  bookPending={bookMutation.isPending}
                  deletePending={deleteMutation.isPending}
                />
                <RiskFactorsTable
                  factors={dashData.risk_factors}
                  whatifFactors={whatifDashData?.whatif_risk_factors ?? []}
                  checkedIds={checkedWhatIfs}
                  onToggle={toggleWhatIf}
                />
              </div>

              {/* Positions */}
              <PositionsTable
                positions={dashData.positions}
                whatifPositions={whatifDashData?.whatif_positions ?? []}
                checkedIds={checkedWhatIfs}
                onToggle={toggleWhatIf}
              />

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
        </>
      )}

      {/* ANALYSIS TAB */}
      {activeTab === 'analysis' && (
        <>
          {!selectedUnderlying ? (
            <div className="text-[11px] text-text-muted text-center py-8 border border-border-secondary/40 rounded">
              Select an underlying from the dropdown to view analysis.
            </div>
          ) : (
            <div className="space-y-2">
              {/* Strategies sub-section */}
              <StrategiesTab
                ticker={selectedUnderlying}
                strategiesData={strategiesData}
                strategiesLoading={strategiesLoading}
                onAddStrategy={handleAddStrategy}
                addingInProgress={addWhatIf.isPending}
              />

              {/* Analysis: Phase, Levels, Opportunities, Smart Money */}
              <AnalysisTab ticker={selectedUnderlying} researchEntry={researchEntry} />
            </div>
          )}
        </>
      )}
    </div>
  )
}

// Keep the old name as alias for backward compat with /market/:ticker route
export { TradeBlotterPage as ResearchPage }

// ===========================================================================
// ANALYSIS TAB — Research deep-dive on selected underlying
// ===========================================================================

function AnalysisTab({ ticker, researchEntry }: { ticker: string; researchEntry?: ResearchEntryType | null }) {
  return (
    <div className="space-y-2">
      <FundamentalsSection ticker={ticker} />
      {researchEntry && <ResearchDataSection entry={researchEntry} />}
      <SectionLabel>Technical Analysis</SectionLabel>
      <TechnicalsSection ticker={ticker} />
      <SectionLabel>Market Regime</SectionLabel>
      <RegimeSection ticker={ticker} />
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 pt-1">
      <h2 className="text-xs font-bold text-text-secondary uppercase tracking-wider">{children}</h2>
      <div className="flex-1 h-px bg-border-secondary" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Strategies Tab (for Analysis tab)
// ---------------------------------------------------------------------------

function StrategiesTab({
  ticker, strategiesData, strategiesLoading, onAddStrategy, addingInProgress,
}: {
  ticker: string
  strategiesData?: import('../api/types').StrategyProposalsResponse | null
  strategiesLoading: boolean
  onAddStrategy: (p: StrategyProposal) => void
  addingInProgress: boolean
}) {
  if (strategiesLoading) {
    return <div className="flex items-center gap-2 py-4"><Spinner size="sm" /><span className="text-xs text-text-muted">Computing strategy proposals...</span></div>
  }
  if (!strategiesData || strategiesData.strategies.length === 0) {
    const diag = strategiesData?.diagnostics ?? []
    return (
      <div className="card card-body text-text-muted text-xs py-4 space-y-2">
        <div>No strategy proposals for {ticker}.</div>
        {diag.length > 0 && (
          <div className="space-y-0.5">
            <div className="text-[10px] font-semibold text-text-secondary uppercase">Diagnostics Trace:</div>
            <div className="bg-bg-tertiary rounded p-2 border border-border-secondary/40 max-h-64 overflow-y-auto">
              {diag.map((line, i) => (
                <div key={i} className={clsx(
                  'text-[10px] font-mono py-[1px]',
                  line.startsWith('!!') ? 'text-accent-red font-semibold' :
                  line.startsWith('>>') ? 'text-accent-cyan' :
                  line.startsWith('--') ? 'text-text-muted' :
                  'text-text-secondary',
                )}>{line}</div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }
  return (
    <div className="space-y-2">
      <SectionLabel>Strategy Proposals ({strategiesData.strategy_count})</SectionLabel>
      {strategiesData.strategies.map(proposal => (
        <StrategyCard key={`${proposal.rank}-${proposal.strategy_type}`} proposal={proposal} onAdd={onAddStrategy} addingInProgress={addingInProgress} />
      ))}
    </div>
  )
}

function StrategyCard({ proposal, onAdd, addingInProgress }: {
  proposal: StrategyProposal; onAdd: (p: StrategyProposal) => void; addingInProgress: boolean
}) {
  const { payoff, levels, fitness } = proposal
  const fits = fitness.fits_portfolio
  return (
    <div className={clsx('card border-l-4', fits ? 'border-green-700' : 'border-amber-700')}>
      <div className="card-body py-2 space-y-1.5">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-bold text-text-primary bg-bg-tertiary px-1.5 py-0.5 rounded">#{proposal.rank}</span>
          <span className="text-sm font-semibold text-text-primary">{proposal.display_name}</span>
          <span className="text-xs text-text-muted">({proposal.source})</span>
          <span className="text-xs font-mono text-text-muted">DTE: {proposal.dte}</span>
          <span className={clsx(
            'ml-auto text-xs font-bold px-2 py-0.5 rounded',
            proposal.score >= 60 ? 'bg-green-900/30 text-green-400' :
            proposal.score >= 40 ? 'bg-amber-900/30 text-amber-400' :
            'bg-bg-tertiary text-text-muted',
          )}>Score: {proposal.score}</span>
          <button
            onClick={() => onAdd(proposal)}
            disabled={addingInProgress}
            className="flex items-center gap-1 px-2 py-0.5 rounded bg-accent-blue text-white text-xs font-semibold hover:bg-accent-blue/80 disabled:opacity-50"
          >
            <Plus size={12} /> Add WhatIf
          </button>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-text-muted">Legs:</span>
          {proposal.legs.map((leg, i) => (
            <span key={i} className="font-mono text-text-secondary">
              {leg.quantity > 0 ? '+' : ''}{leg.quantity}{leg.option_type[0].toUpperCase()}{leg.strike}
              {i < proposal.legs.length - 1 && ' /'}
            </span>
          ))}
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs">
            <span className="text-text-muted">POP: <span className={clsx('font-mono font-semibold', payoff.pop >= 0.65 ? 'text-green-400' : payoff.pop >= 0.50 ? 'text-amber-400' : 'text-red-400')}>{(payoff.pop * 100).toFixed(0)}%</span></span>
            <span className="text-text-muted">EV: <span className={clsx('font-mono font-semibold', payoff.ev >= 0 ? 'text-green-400' : 'text-red-400')}>${payoff.ev.toFixed(0)}</span></span>
            <span className="text-text-muted">Max P: <span className="font-mono text-green-400">{payoff.max_profit != null ? `$${payoff.max_profit.toFixed(0)}` : 'Inf'}</span></span>
            <span className="text-text-muted">Max L: <span className="font-mono text-red-400">{payoff.max_loss != null ? `$${payoff.max_loss.toFixed(0)}` : 'Undef'}</span></span>
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs">
            {payoff.breakevens.length > 0 && (
              <span className="text-text-muted">BE: {payoff.breakevens.map((b, i) => (
                <span key={i} className="font-mono text-text-secondary">{i > 0 ? ', ' : ''}${b.toFixed(0)}</span>
              ))}</span>
            )}
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs">
            {levels.stop_price && <span className="text-text-muted">Stop: <span className="font-mono text-red-400">${fmtNum(levels.stop_price)}</span></span>}
            {levels.best_target_price && <span className="text-text-muted">Target: <span className="font-mono text-green-400">${fmtNum(levels.best_target_price)}</span></span>}
            {levels.best_target_rr != null && <span className="text-text-muted">R:R: <span className="font-mono font-semibold text-text-primary">{levels.best_target_rr.toFixed(1)}</span></span>}
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className={clsx('font-semibold', fits ? 'text-green-400' : 'text-amber-400')}>
              {fits ? 'Fits' : 'Warnings'}
            </span>
            {fitness.fitness_warnings.length > 0 && (
              <span className="text-amber-400 text-2xs">{fitness.fitness_warnings[0]}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Research Data Section (Phase, Levels, Opportunities, Smart Money)
// ---------------------------------------------------------------------------

function ResearchDataSection({ entry }: { entry: ResearchEntryType }) {
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        {/* Phase */}
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Phase (Wyckoff)</h3></div>
          <div className="card-body py-1.5 space-y-0.5">
            <div className="text-sm font-semibold text-text-primary capitalize">{entry.phase_name || '--'}</div>
            {entry.phase_confidence != null && <div className="text-xs text-text-muted">Confidence: <span className="font-mono">{(entry.phase_confidence * 100).toFixed(0)}%</span></div>}
            {entry.phase_age_days != null && <div className="text-xs text-text-muted">Age: {entry.phase_age_days}d</div>}
            {entry.phase_cycle_completion != null && <div className="text-xs text-text-muted">Cycle: {(entry.phase_cycle_completion * 100).toFixed(0)}%</div>}
            {entry.phase_strategy_comment && <div className="text-xs text-accent-blue mt-1">{entry.phase_strategy_comment}</div>}
          </div>
        </div>
        {/* Levels */}
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Levels</h3></div>
          <div className="card-body py-1.5 space-y-0.5">
            <div className="flex justify-between text-xs">
              <span className="text-text-muted">Direction</span>
              <span className={clsx('font-semibold', entry.levels_direction === 'long' ? 'text-green-400' : entry.levels_direction === 'short' ? 'text-red-400' : 'text-text-muted')}>{entry.levels_direction || '--'}</span>
            </div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">Stop</span><span className="font-mono text-red-400">{entry.levels_stop_price ? `$${fmtNum(entry.levels_stop_price)}` : '--'}</span></div>
            {entry.levels_stop_distance_pct != null && <div className="flex justify-between text-xs"><span className="text-text-muted">Stop Dist</span><span className="font-mono text-text-secondary">{entry.levels_stop_distance_pct.toFixed(1)}%</span></div>}
            <div className="flex justify-between text-xs"><span className="text-text-muted">Target</span><span className="font-mono text-green-400">{entry.levels_best_target_price ? `$${fmtNum(entry.levels_best_target_price)}` : '--'}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">R:R</span><span className="font-mono font-semibold text-text-primary">{entry.levels_best_target_rr ? entry.levels_best_target_rr.toFixed(1) : '--'}</span></div>
          </div>
        </div>
        {/* Opportunities */}
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Opportunities</h3></div>
          <div className="card-body py-1.5 space-y-1">
            {[
              { label: '0DTE', verdict: entry.opp_zero_dte_verdict, confidence: entry.opp_zero_dte_confidence },
              { label: 'LEAP', verdict: entry.opp_leap_verdict, confidence: entry.opp_leap_confidence },
              { label: 'Breakout', verdict: entry.opp_breakout_verdict, confidence: entry.opp_breakout_confidence },
              { label: 'Momentum', verdict: entry.opp_momentum_verdict, confidence: entry.opp_momentum_confidence },
            ].map(opp => (
              <div key={opp.label} className="flex items-center justify-between text-xs">
                <span className="text-text-muted">{opp.label}</span>
                <div className="flex items-center gap-1">
                  <VerdictBadge verdict={opp.verdict} />
                  {opp.confidence != null && <span className="font-mono text-text-secondary text-2xs">{(opp.confidence * 100).toFixed(0)}%</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
        {/* Smart Money */}
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Smart Money</h3></div>
          <div className="card-body py-1.5 space-y-0.5">
            <div className="flex justify-between text-xs"><span className="text-text-muted">Score</span><span className="font-mono text-text-primary">{entry.smart_money_score != null ? (entry.smart_money_score * 100).toFixed(0) + '%' : '--'}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">FVGs</span><span className="font-mono text-text-primary">{entry.unfilled_fvg_count ?? '--'}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">Order Blocks</span><span className="font-mono text-text-primary">{entry.active_ob_count ?? '--'}</span></div>
            {entry.smart_money_description && <div className="text-xs text-text-secondary mt-1">{entry.smart_money_description}</div>}
          </div>
        </div>
      </div>

      {/* Support / Resistance Levels Table */}
      {(entry.levels_s1_price || entry.levels_r1_price) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
          <div className="card">
            <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Support Levels</h3></div>
            <div className="card-body p-0">
              <table className="w-full text-xs">
                <thead><tr className="text-text-muted border-b border-border-secondary"><th className="py-0.5 px-2 text-left">Level</th><th className="py-0.5 px-2 text-right">Price</th><th className="py-0.5 px-2 text-right">Strength</th><th className="py-0.5 px-2 text-left">Sources</th></tr></thead>
                <tbody>
                  {[
                    { label: 'S1', price: entry.levels_s1_price, strength: entry.levels_s1_strength, sources: entry.levels_s1_sources },
                    { label: 'S2', price: entry.levels_s2_price, strength: entry.levels_s2_strength, sources: entry.levels_s2_sources },
                    { label: 'S3', price: entry.levels_s3_price, strength: entry.levels_s3_strength, sources: entry.levels_s3_sources },
                  ].filter(l => l.price != null).map(l => (
                    <tr key={l.label} className="border-b border-border-secondary/50">
                      <td className="py-0.5 px-2 font-semibold text-green-400">{l.label}</td>
                      <td className="py-0.5 px-2 text-right font-mono text-text-primary">${fmtNum(l.price)}</td>
                      <td className="py-0.5 px-2 text-right font-mono text-text-secondary">{l.strength != null ? (l.strength * 100).toFixed(0) + '%' : '--'}</td>
                      <td className="py-0.5 px-2 text-text-muted">{l.sources || '--'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="card">
            <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Resistance Levels</h3></div>
            <div className="card-body p-0">
              <table className="w-full text-xs">
                <thead><tr className="text-text-muted border-b border-border-secondary"><th className="py-0.5 px-2 text-left">Level</th><th className="py-0.5 px-2 text-right">Price</th><th className="py-0.5 px-2 text-right">Strength</th><th className="py-0.5 px-2 text-left">Sources</th></tr></thead>
                <tbody>
                  {[
                    { label: 'R1', price: entry.levels_r1_price, strength: entry.levels_r1_strength, sources: entry.levels_r1_sources },
                    { label: 'R2', price: entry.levels_r2_price, strength: entry.levels_r2_strength, sources: entry.levels_r2_sources },
                    { label: 'R3', price: entry.levels_r3_price, strength: entry.levels_r3_strength, sources: entry.levels_r3_sources },
                  ].filter(l => l.price != null).map(l => (
                    <tr key={l.label} className="border-b border-border-secondary/50">
                      <td className="py-0.5 px-2 font-semibold text-red-400">{l.label}</td>
                      <td className="py-0.5 px-2 text-right font-mono text-text-primary">${fmtNum(l.price)}</td>
                      <td className="py-0.5 px-2 text-right font-mono text-text-secondary">{l.strength != null ? (l.strength * 100).toFixed(0) + '%' : '--'}</td>
                      <td className="py-0.5 px-2 text-text-muted">{l.sources || '--'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function VerdictBadge({ verdict }: { verdict: string | null }) {
  if (!verdict) return <span className="text-text-muted text-xs">--</span>
  const v = verdict.toUpperCase()
  if (v === 'GO') return <span className="px-1.5 py-0.5 rounded text-xs font-bold bg-green-900/40 text-green-400 border border-green-700">GO</span>
  if (v === 'CAUTION') return <span className="px-1.5 py-0.5 rounded text-xs font-bold bg-amber-900/40 text-amber-400 border border-amber-700">CAUTION</span>
  return <span className="px-1.5 py-0.5 rounded text-xs font-bold bg-red-900/40 text-red-400 border border-red-700">NO GO</span>
}

// ---------------------------------------------------------------------------
// Fundamentals Section
// ---------------------------------------------------------------------------

function FundamentalsSection({ ticker }: { ticker: string }) {
  const { data: fund, isLoading, isError, error } = useFundamentals(ticker || null)
  if (isLoading) return <div className="flex items-center gap-2 py-2"><Spinner size="sm" /><span className="text-xs text-text-muted">Loading fundamentals...</span></div>
  if (isError) return <div className="card card-body text-red-400 text-xs py-2">Fundamentals failed: {(error as Error)?.message}</div>
  if (!fund) return <div className="card card-body text-text-muted text-xs py-2">No fundamental data for {ticker}</div>

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        <div className="card">
          <div className="card-body py-2 space-y-1">
            <div className="text-lg font-bold text-text-primary">{fund.business.long_name || ticker}</div>
            <div className="text-xs text-text-muted">{fund.business.sector} / {fund.business.industry}</div>
            <div className="flex gap-3 text-xs">
              <span className="text-text-muted">Beta: <span className="font-mono text-text-primary">{fmtNum(fund.business.beta)}</span></span>
              <span className="text-text-muted">MCap: <span className="font-mono text-text-primary">{fmtBigNum(fund.revenue.market_cap)}</span></span>
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Valuation</h3></div>
          <div className="card-body py-1.5 space-y-0.5">
            {[
              { label: 'P/E (TTM)', val: fmtNum(fund.valuation.trailing_pe) },
              { label: 'P/E (Fwd)', val: fmtNum(fund.valuation.forward_pe) },
              { label: 'PEG', val: fmtNum(fund.valuation.peg_ratio) },
              { label: 'P/B', val: fmtNum(fund.valuation.price_to_book) },
              { label: 'P/S', val: fmtNum(fund.valuation.price_to_sales) },
            ].map(r => (
              <div key={r.label} className="flex justify-between text-xs">
                <span className="text-text-muted">{r.label}</span>
                <span className="font-mono text-text-primary">{r.val}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">52-Week Range</h3></div>
          <div className="card-body py-1.5 space-y-1">
            <div className="flex justify-between text-xs"><span className="text-text-muted">High</span><span className="font-mono text-text-primary">${fmtNum(fund.fifty_two_week.high)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">Low</span><span className="font-mono text-text-primary">${fmtNum(fund.fifty_two_week.low)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">From High</span><span className={clsx('font-mono', (fund.fifty_two_week.pct_from_high ?? 0) < 0 ? 'text-red-400' : 'text-green-400')}>{fmtPct(fund.fifty_two_week.pct_from_high != null ? fund.fifty_two_week.pct_from_high / 100 : null)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">From Low</span><span className={clsx('font-mono', (fund.fifty_two_week.pct_from_low ?? 0) > 0 ? 'text-green-400' : 'text-red-400')}>{fmtPct(fund.fifty_two_week.pct_from_low != null ? fund.fifty_two_week.pct_from_low / 100 : null)}</span></div>
          </div>
        </div>
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Events</h3></div>
          <div className="card-body py-1.5 space-y-1.5">
            {fund.upcoming_events.next_earnings_date ? (
              <div>
                <div className="text-xs text-text-muted">Next Earnings</div>
                <div className="text-sm font-mono font-bold text-amber-400">{fund.upcoming_events.next_earnings_date}</div>
                {fund.upcoming_events.days_to_earnings != null && <div className="text-xs text-text-muted">{fund.upcoming_events.days_to_earnings}d away</div>}
              </div>
            ) : <div className="text-xs text-text-muted">No earnings date</div>}
            {fund.dividends.dividend_yield != null && fund.dividends.dividend_yield > 0 && (
              <div className="flex justify-between text-xs"><span className="text-text-muted">Div Yield</span><span className="font-mono text-green-400">{fmtPct(fund.dividends.dividend_yield)}</span></div>
            )}
            {fund.upcoming_events.ex_dividend_date && (
              <div className="flex justify-between text-xs"><span className="text-text-muted">Ex-Div</span><span className="font-mono text-text-primary">{fund.upcoming_events.ex_dividend_date}</span></div>
            )}
          </div>
        </div>
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Earnings</h3></div>
          <div className="card-body py-1.5 space-y-0.5">
            <div className="flex justify-between text-xs"><span className="text-text-muted">EPS (TTM)</span><span className="font-mono text-text-primary">{fmtNum(fund.earnings.trailing_eps)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">EPS (Fwd)</span><span className="font-mono text-text-primary">{fmtNum(fund.earnings.forward_eps)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">Growth</span><span className={clsx('font-mono', (fund.earnings.earnings_growth ?? 0) > 0 ? 'text-green-400' : 'text-red-400')}>{fmtPct(fund.earnings.earnings_growth)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">Revenue</span><span className="font-mono text-text-primary">{fmtBigNum(fund.revenue.total_revenue)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">Rev Growth</span><span className={clsx('font-mono', (fund.revenue.revenue_growth ?? 0) > 0 ? 'text-green-400' : 'text-red-400')}>{fmtPct(fund.revenue.revenue_growth)}</span></div>
          </div>
        </div>
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Margins</h3></div>
          <div className="card-body py-1.5 space-y-0.5">
            {[
              { label: 'Gross', val: fund.margins.gross_margins },
              { label: 'Operating', val: fund.margins.operating_margins },
              { label: 'Profit', val: fund.margins.profit_margins },
              { label: 'EBITDA', val: fund.margins.ebitda_margins },
            ].map(r => (
              <div key={r.label} className="flex justify-between text-xs"><span className="text-text-muted">{r.label}</span><span className="font-mono text-text-primary">{fmtPct(r.val)}</span></div>
            ))}
          </div>
        </div>
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Returns</h3></div>
          <div className="card-body py-1.5 space-y-0.5">
            <div className="flex justify-between text-xs"><span className="text-text-muted">ROE</span><span className="font-mono text-text-primary">{fmtPct(fund.returns.return_on_equity)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">ROA</span><span className="font-mono text-text-primary">{fmtPct(fund.returns.return_on_assets)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">FCF</span><span className="font-mono text-text-primary">{fmtBigNum(fund.cash.free_cashflow)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">Op CF</span><span className="font-mono text-text-primary">{fmtBigNum(fund.cash.operating_cashflow)}</span></div>
          </div>
        </div>
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Balance Sheet</h3></div>
          <div className="card-body py-1.5 space-y-0.5">
            <div className="flex justify-between text-xs"><span className="text-text-muted">Total Cash</span><span className="font-mono text-text-primary">{fmtBigNum(fund.cash.total_cash)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">Total Debt</span><span className="font-mono text-text-primary">{fmtBigNum(fund.debt.total_debt)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">D/E</span><span className="font-mono text-text-primary">{fmtNum(fund.debt.debt_to_equity)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">Current Ratio</span><span className="font-mono text-text-primary">{fmtNum(fund.debt.current_ratio)}</span></div>
          </div>
        </div>
      </div>
      {fund.recent_earnings.length > 0 && (
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Recent Earnings ({fund.recent_earnings.length})</h3></div>
          <div className="card-body p-0">
            <table className="w-full text-xs">
              <thead><tr className="text-text-muted border-b border-border-secondary text-2xs uppercase"><th className="py-1 px-2 text-left">Date</th><th className="py-1 px-2 text-right">Estimate</th><th className="py-1 px-2 text-right">Actual</th><th className="py-1 px-2 text-right">Surprise</th></tr></thead>
              <tbody>
                {fund.recent_earnings.map((e, i) => (
                  <tr key={i} className="border-b border-border-secondary/50">
                    <td className="py-0.5 px-2 font-mono text-text-primary">{e.date}</td>
                    <td className="py-0.5 px-2 text-right font-mono text-text-secondary">{e.eps_estimate?.toFixed(2) ?? '--'}</td>
                    <td className="py-0.5 px-2 text-right font-mono text-text-primary">{e.eps_actual?.toFixed(2) ?? '--'}</td>
                    <td className={clsx('py-0.5 px-2 text-right font-mono font-semibold', (e.surprise_pct ?? 0) > 0 ? 'text-green-400' : (e.surprise_pct ?? 0) < 0 ? 'text-red-400' : 'text-text-muted')}>
                      {e.surprise_pct != null ? `${e.surprise_pct > 0 ? '+' : ''}${e.surprise_pct.toFixed(1)}%` : '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Technicals Section
// ---------------------------------------------------------------------------

function TechnicalsSection({ ticker }: { ticker: string }) {
  const { data: tech, isLoading, isError, error } = useTechnicals(ticker || null)
  if (isLoading) return <div className="flex items-center gap-2 py-2"><Spinner size="sm" /><span className="text-xs text-text-muted">Loading technicals...</span></div>
  if (isError) return <div className="card card-body text-red-400 text-xs py-2">Technicals failed: {(error as Error)?.message}</div>
  if (!tech) return <div className="card card-body text-text-muted text-xs py-2">No technical data for {ticker}</div>

  const ma = tech.moving_averages
  const bb = tech.bollinger
  const macd = tech.macd
  const stoch = tech.stochastic
  const sr = tech.support_resistance

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        <div className="card">
          <div className="card-body py-2 space-y-1">
            <div className="text-xs text-text-muted uppercase font-semibold">Price</div>
            <div className="text-lg font-mono font-bold text-text-primary">${tech.current_price.toFixed(2)}</div>
            <div className="flex gap-3 text-xs">
              <span className="text-text-muted">ATR: <span className="text-text-primary font-mono">{tech.atr.toFixed(2)}</span></span>
              <span className="text-text-muted">ATR%: <span className="text-text-primary font-mono">{tech.atr_pct.toFixed(2)}%</span></span>
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-body py-2 space-y-1">
            <div className="text-xs text-text-muted uppercase font-semibold">RSI (14)</div>
            <div className={clsx('text-lg font-mono font-bold', tech.rsi.is_overbought ? 'text-red-400' : tech.rsi.is_oversold ? 'text-green-400' : 'text-text-primary')}>{tech.rsi.value.toFixed(1)}</div>
            <div className="w-full h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
              <div className={clsx('h-full rounded-full', tech.rsi.value > 70 ? 'bg-red-500' : tech.rsi.value < 30 ? 'bg-green-500' : 'bg-accent-blue')} style={{ width: `${tech.rsi.value}%` }} />
            </div>
            <div className="text-xs">{tech.rsi.is_overbought ? <span className="text-red-400 font-semibold">Overbought</span> : tech.rsi.is_oversold ? <span className="text-green-400 font-semibold">Oversold</span> : <span className="text-text-muted">Neutral</span>}</div>
          </div>
        </div>
        <div className="card">
          <div className="card-body py-2 space-y-1">
            <div className="text-xs text-text-muted uppercase font-semibold">MACD</div>
            <div className="flex items-baseline gap-2">
              <span className="text-sm font-mono font-bold text-text-primary">{macd.macd_line.toFixed(3)}</span>
              <span className="text-xs text-text-muted">sig: {macd.signal_line.toFixed(3)}</span>
            </div>
            <div className={clsx('text-xs font-mono font-semibold', macd.histogram > 0 ? 'text-green-400' : 'text-red-400')}>Hist: {macd.histogram > 0 ? '+' : ''}{macd.histogram.toFixed(3)}</div>
            <div className="text-xs">{macd.is_bullish_crossover ? <span className="text-green-400 font-semibold">Bullish Cross</span> : macd.is_bearish_crossover ? <span className="text-red-400 font-semibold">Bearish Cross</span> : <span className="text-text-muted">No crossover</span>}</div>
          </div>
        </div>
        <div className="card">
          <div className="card-body py-2 space-y-1">
            <div className="text-xs text-text-muted uppercase font-semibold">Stochastic</div>
            <div className="flex items-baseline gap-2">
              <span className={clsx('text-sm font-mono font-bold', stoch.is_overbought ? 'text-red-400' : stoch.is_oversold ? 'text-green-400' : 'text-text-primary')}>%K {stoch.k.toFixed(1)}</span>
              <span className="text-xs text-text-muted font-mono">%D {stoch.d.toFixed(1)}</span>
            </div>
            <div className="text-xs">{stoch.is_overbought ? <span className="text-red-400 font-semibold">Overbought</span> : stoch.is_oversold ? <span className="text-green-400 font-semibold">Oversold</span> : <span className="text-text-muted">Neutral</span>}</div>
          </div>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-2">
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Moving Averages</h3></div>
          <div className="card-body p-0">
            <table className="w-full text-xs">
              <thead><tr className="text-text-muted border-b border-border-secondary"><th className="py-1 px-2 text-left">MA</th><th className="py-1 px-2 text-right">Value</th><th className="py-1 px-2 text-right">vs Price</th></tr></thead>
              <tbody>
                {[
                  { name: 'EMA 9', val: ma.ema_9, pct: null as number | null },
                  { name: 'SMA 20', val: ma.sma_20, pct: ma.price_vs_sma_20_pct },
                  { name: 'EMA 21', val: ma.ema_21, pct: null as number | null },
                  { name: 'SMA 50', val: ma.sma_50, pct: ma.price_vs_sma_50_pct },
                  { name: 'SMA 200', val: ma.sma_200, pct: ma.price_vs_sma_200_pct },
                ].map((row) => (
                  <tr key={row.name} className="border-b border-border-secondary/50">
                    <td className="py-0.5 px-2 text-text-primary">{row.name}</td>
                    <td className="py-0.5 px-2 text-right font-mono">${row.val.toFixed(2)}</td>
                    <td className={clsx('py-0.5 px-2 text-right font-mono', row.pct != null ? (row.pct > 0 ? 'text-green-400' : 'text-red-400') : 'text-text-muted')}>{row.pct != null ? `${row.pct > 0 ? '+' : ''}${row.pct.toFixed(1)}%` : '--'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Bollinger Bands</h3></div>
          <div className="card-body py-2 space-y-1">
            {[{ label: 'Upper', val: bb.upper }, { label: 'Middle', val: bb.middle }, { label: 'Lower', val: bb.lower }].map(r => (
              <div key={r.label} className="flex justify-between text-xs"><span className="text-text-muted">{r.label}</span><span className="font-mono text-text-primary">${r.val.toFixed(2)}</span></div>
            ))}
            <div className="flex justify-between text-xs"><span className="text-text-muted">BW</span><span className="font-mono text-text-primary">{bb.bandwidth.toFixed(2)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">%B</span><span className={clsx('font-mono font-semibold', bb.percent_b > 1 ? 'text-red-400' : bb.percent_b < 0 ? 'text-green-400' : 'text-text-primary')}>{bb.percent_b.toFixed(3)}</span></div>
            <div className="relative h-2 bg-bg-tertiary rounded-full mt-1">
              <div className="absolute left-0 top-0 h-full w-px bg-text-muted/30" /><div className="absolute top-0 h-full w-px bg-text-muted/30" style={{ left: '50%' }} /><div className="absolute right-0 top-0 h-full w-px bg-text-muted/30" />
              <div className="absolute top-0 w-2 h-2 rounded-full bg-accent-blue border border-white" style={{ left: `${Math.max(0, Math.min(100, bb.percent_b * 100))}%`, transform: 'translateX(-50%)' }} />
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Support / Resistance</h3></div>
          <div className="card-body py-2 space-y-2">
            <div className="flex justify-between items-baseline"><span className="text-xs text-text-muted">Resistance</span><div className="flex items-baseline gap-1"><span className="text-sm font-mono font-bold text-red-400">${sr.resistance?.toFixed(2) ?? '--'}</span>{sr.price_vs_resistance_pct != null && <span className="text-xs font-mono text-text-muted">({sr.price_vs_resistance_pct.toFixed(1)}%)</span>}</div></div>
            <div className="flex justify-between items-baseline"><span className="text-xs text-text-muted">Current</span><span className="text-sm font-mono font-bold text-text-primary">${tech.current_price.toFixed(2)}</span></div>
            <div className="flex justify-between items-baseline"><span className="text-xs text-text-muted">Support</span><div className="flex items-baseline gap-1"><span className="text-sm font-mono font-bold text-green-400">${sr.support?.toFixed(2) ?? '--'}</span>{sr.price_vs_support_pct != null && <span className="text-xs font-mono text-text-muted">({sr.price_vs_support_pct.toFixed(1)}%)</span>}</div></div>
          </div>
        </div>
      </div>
      {tech.signals && tech.signals.length > 0 && (
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Signals</h3></div>
          <div className="card-body p-0">
            <table className="w-full text-xs">
              <thead><tr className="text-text-muted border-b border-border-secondary"><th className="py-1 px-2 text-left">Signal</th><th className="py-1 px-2 text-center">Direction</th><th className="py-1 px-2 text-center">Strength</th><th className="py-1 px-2 text-left">Description</th></tr></thead>
              <tbody>
                {tech.signals.map((sig: TechnicalSignal, i: number) => (
                  <tr key={i} className="border-b border-border-secondary/50">
                    <td className="py-0.5 px-2 font-medium text-text-primary">{sig.name}</td>
                    <td className="py-0.5 px-2 text-center"><span className={clsx('px-1.5 py-0.5 rounded font-semibold text-xs', sig.direction === 'bullish' ? 'bg-green-900/30 text-green-400' : sig.direction === 'bearish' ? 'bg-red-900/30 text-red-400' : 'bg-bg-tertiary text-text-muted')}>{sig.direction}</span></td>
                    <td className="py-0.5 px-2 text-center"><span className={clsx('font-mono', sig.strength === 'strong' ? 'text-text-primary font-bold' : sig.strength === 'moderate' ? 'text-text-secondary' : 'text-text-muted')}>{sig.strength}</span></td>
                    <td className="py-0.5 px-2 text-text-secondary">{sig.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Regime Section
// ---------------------------------------------------------------------------

function TrendBadge({ direction }: { direction: string | null }) {
  if (!direction) return <span className="text-xs text-text-muted">--</span>
  if (direction === 'bullish' || direction === 'up') return <span className="text-xs text-green-400 font-semibold">&#9650; Bullish</span>
  if (direction === 'bearish' || direction === 'down') return <span className="text-xs text-red-400 font-semibold">&#9660; Bearish</span>
  return <span className="text-xs text-text-muted">&#9654; {direction}</span>
}

function TrendArrowSmall({ direction }: { direction: string | null }) {
  if (!direction) return <span className="text-text-muted text-xs">--</span>
  if (direction === 'bullish' || direction === 'up') return <span className="text-green-400 text-xs">&#9650;</span>
  if (direction === 'bearish' || direction === 'down') return <span className="text-red-400 text-xs">&#9660;</span>
  return <span className="text-text-muted text-xs">&#9654;</span>
}

function RegimeSection({ ticker }: { ticker: string }) {
  const { data: research, isLoading, isError, error } = useRegimeResearch(ticker || null)
  const { data: chartData, isLoading: chartLoading } = useRegimeChart(ticker || null)

  if (isLoading) return <div className="flex justify-center py-4"><Spinner size="sm" /></div>
  if (isError || !research) return <div className="text-red-400 text-xs py-2 card card-body">Regime failed: {(error as Error)?.message || 'Unknown error'}</div>

  const rr = research.regime_result
  const rc = getRC(rr.regime)

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
        <div className="space-y-2">
          <div className={clsx('card border-l-4', rc.border)}>
            <div className="card-body py-2 space-y-1.5">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={clsx('px-2 py-0.5 rounded text-xs font-bold border', rc.bg, rc.color, rc.border)}>R{rr.regime} {rc.label}</span>
                <span className={clsx('font-mono text-xs font-semibold', rr.confidence >= 0.8 ? 'text-green-400' : rr.confidence >= 0.5 ? 'text-amber-400' : 'text-red-400')}>{(rr.confidence * 100).toFixed(0)}%</span>
                <TrendBadge direction={rr.trend_direction} />
              </div>
              {research.strategy_comment && <p className="text-xs text-accent-blue font-medium">{research.strategy_comment}</p>}
              {research.explanation_text && (
                <div className="text-xs text-text-secondary leading-snug max-h-[60px] overflow-auto">
                  {research.explanation_text.split('\n').filter((l: string) => l.trim() && !l.trim().startsWith('---') && !l.trim().match(/Feature\s+Z-Score/)).slice(0, 3).map((l: string, i: number) => <p key={i}>{l}</p>)}
                </div>
              )}
            </div>
          </div>
          <div className="card">
            <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Features (Z-Scores)</h3></div>
            <div className="card-body p-0"><FeatureTable features={research.current_features} /></div>
          </div>
        </div>
        <div className="card flex items-center justify-center">
          <div className="card-body py-2 flex items-center justify-center w-full">
            {chartLoading ? <Spinner size="sm" /> : chartData?.chart_base64 ? (
              <img src={`data:image/png;base64,${chartData.chart_base64}`} alt={`${ticker} regime`} className="rounded object-contain w-full" style={{ maxHeight: 320 }} />
            ) : <span className="text-xs text-text-muted">No chart available</span>}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-2">
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Transition Matrix</h3></div>
          <div className="card-body p-0"><TransitionTable matrix={research.transition_matrix} currentRegime={rr.regime} /></div>
        </div>
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Distribution</h3></div>
          <div className="card-body py-1"><DistributionBars distribution={research.regime_distribution} /></div>
        </div>
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">State Means</h3></div>
          <div className="card-body p-0"><StateMeansTable means={research.state_means} /></div>
        </div>
      </div>

      <div className="card">
        <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Recent History (20d)</h3></div>
        <div className="card-body p-0"><HistoryTable history={research.recent_history} /></div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Regime Sub-Components
// ---------------------------------------------------------------------------

function FeatureTable({ features }: { features: FeatureZScore[] }) {
  if (!features?.length) return <div className="p-2 text-xs text-text-muted">No data</div>
  const maxAbsZ = Math.max(...features.map(f => Math.abs(f.z_score)), 0.01)
  return (
    <table className="w-full text-xs">
      <thead><tr className="text-text-muted border-b border-border-secondary"><th className="py-1 px-2 text-left">Feature</th><th className="py-1 px-2 text-right w-12">Z</th><th className="py-1 px-2 w-16">Bar</th><th className="py-1 px-2">Note</th></tr></thead>
      <tbody>
        {features.map((f) => {
          const absZ = Math.abs(f.z_score)
          const zColor = absZ <= 1 ? 'text-green-400' : absZ <= 2 ? 'text-amber-400' : 'text-red-400'
          const barColor = absZ <= 1 ? 'bg-green-500' : absZ <= 2 ? 'bg-amber-500' : 'bg-red-500'
          const barPct = Math.min((absZ / Math.max(maxAbsZ, 3)) * 100, 100)
          return (
            <tr key={f.feature} className="border-b border-border-secondary/50">
              <td className="py-0.5 px-2 font-mono text-text-primary">{f.feature}</td>
              <td className={clsx('py-0.5 px-2 text-right font-mono font-bold', zColor)}>{f.z_score >= 0 ? '+' : ''}{f.z_score.toFixed(2)}</td>
              <td className="py-0.5 px-2">
                <div className="w-full h-1.5 bg-bg-tertiary rounded-full relative overflow-hidden">
                  {f.z_score < 0 ? <div className={clsx('absolute h-full rounded-full', barColor)} style={{ right: '50%', width: `${barPct / 2}%` }} /> : <div className={clsx('absolute h-full rounded-full', barColor)} style={{ left: '50%', width: `${barPct / 2}%` }} />}
                  <div className="absolute left-1/2 top-0 h-full w-px bg-text-muted/50" />
                </div>
              </td>
              <td className="py-0.5 px-2 text-text-secondary truncate max-w-[120px]">{f.comment}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function TransitionTable({ matrix, currentRegime }: { matrix: TransitionRow[]; currentRegime: number }) {
  if (!matrix?.length) return <div className="p-2 text-xs text-text-muted">No data</div>
  return (
    <table className="w-full text-xs">
      <thead><tr className="text-text-muted border-b border-border-secondary"><th className="py-1 px-1.5 text-left">From</th>{[1,2,3,4].map(r=><th key={r} className="py-1 px-1 text-center"><span className={getRC(r).color}>R{r}</span></th>)}<th className="py-1 px-1 text-center">Sticky</th></tr></thead>
      <tbody>
        {matrix.map((row) => (
          <tr key={row.from_regime} className={clsx('border-b border-border-secondary/50', row.from_regime === currentRegime && 'bg-accent-blue/10')}>
            <td className={clsx('py-0.5 px-1.5 font-mono font-semibold', getRC(row.from_regime).color)}>R{row.from_regime}{row.from_regime === currentRegime && '*'}</td>
            {[1,2,3,4].map(toR => {
              const p = row.to_probabilities[String(toR)] ?? 0
              return <td key={toR} className={clsx('py-0.5 px-1 text-center font-mono', row.from_regime === toR ? 'font-bold text-text-primary' : 'text-text-secondary', p >= 0.7 && 'bg-green-900/20')}>{(p*100).toFixed(0)}%</td>
            })}
            <td className="py-0.5 px-1 text-center text-text-secondary">{row.stability}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function DistributionBars({ distribution }: { distribution: RegimeDistributionEntry[] }) {
  if (!distribution?.length) return <div className="text-xs text-text-muted">No data</div>
  const maxPct = Math.max(...distribution.map(d => d.percentage), 1)
  return (
    <div className="space-y-1">
      {distribution.map((d) => {
        const rc = getRC(d.regime)
        return (
          <div key={d.regime} className="flex items-center gap-1.5">
            <div className={clsx('w-8 text-xs font-mono font-semibold shrink-0', rc.color)}>R{d.regime}</div>
            <div className="flex-1 h-3.5 bg-bg-tertiary rounded overflow-hidden relative">
              <div className={clsx('h-full rounded', rc.bg)} style={{ width: `${(d.percentage / maxPct) * 100}%`, opacity: 0.7 }} />
              <span className="absolute inset-0 flex items-center px-1 text-xs font-mono text-text-primary">{d.percentage.toFixed(0)}% ({d.days}d)</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function HistoryTable({ history }: { history: RegimeHistoryDay[] }) {
  if (!history?.length) return <div className="p-2 text-xs text-text-muted">No data</div>
  return (
    <div className="max-h-[180px] overflow-auto">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-bg-secondary"><tr className="text-text-muted border-b border-border-secondary"><th className="py-1 px-2 text-left">Date</th><th className="py-1 px-2">Regime</th><th className="py-1 px-2 text-right">Conf</th><th className="py-1 px-2 text-center">Trend</th><th className="py-1 px-2">Change</th></tr></thead>
        <tbody>
          {history.map((d) => {
            const rc = getRC(d.regime)
            return (
              <tr key={d.date} className={clsx('border-b border-border-secondary/50', d.changed_from != null && 'bg-amber-900/10')}>
                <td className="py-0.5 px-2 font-mono text-text-primary">{d.date}</td>
                <td className="py-0.5 px-2"><span className={clsx('px-1 py-0.5 rounded font-semibold border', rc.bg, rc.color, rc.border)}>R{d.regime}</span></td>
                <td className="py-0.5 px-2 text-right font-mono text-text-secondary">{(d.confidence*100).toFixed(0)}%</td>
                <td className="py-0.5 px-2 text-center"><TrendArrowSmall direction={d.trend_direction} /></td>
                <td className="py-0.5 px-2">{d.changed_from != null ? <span className="text-amber-400 font-mono font-semibold">R{d.changed_from}&#8594;R{d.regime}</span> : <span className="text-text-muted">--</span>}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function StateMeansTable({ means }: { means: StateMeansRow[] }) {
  if (!means?.length) return <div className="p-2 text-xs text-text-muted">No data</div>
  const featureNames = Array.from(new Set(means.flatMap(m => Object.keys(m.feature_means))))
  return (
    <div className="overflow-auto">
      <table className="w-full text-xs">
        <thead><tr className="text-text-muted border-b border-border-secondary"><th className="py-1 px-2 text-left">R</th><th className="py-1 px-2">Vol</th><th className="py-1 px-2">Trend</th>{featureNames.map(f=><th key={f} className="py-1 px-1.5 text-right font-mono">{f}</th>)}</tr></thead>
        <tbody>
          {means.map(m => {
            const rc = getRC(m.regime)
            return (
              <tr key={m.regime} className="border-b border-border-secondary/50">
                <td className={clsx('py-0.5 px-2 font-mono font-semibold', rc.color)}>R{m.regime}</td>
                <td className="py-0.5 px-2 text-text-secondary">{m.vol_character}</td>
                <td className="py-0.5 px-2 text-text-secondary">{m.trend_character}</td>
                {featureNames.map(f=><td key={f} className="py-0.5 px-1.5 text-right font-mono text-text-secondary">{m.feature_means[f]?.toFixed(3) ?? '--'}</td>)}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
