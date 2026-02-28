import { useState } from 'react'
import { clsx } from 'clsx'
import { usePlan } from '../../hooks/usePlan'
import { Spinner } from '../common/Spinner'
import type { PlanTrade, DailyTradingPlan } from '../../api/types'

const VERDICT_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  trade: { bg: 'bg-green-900/30', text: 'text-green-400', label: 'TRADE' },
  trade_light: { bg: 'bg-amber-900/30', text: 'text-amber-400', label: 'TRADE LIGHT' },
  avoid: { bg: 'bg-red-900/30', text: 'text-red-400', label: 'AVOID' },
  no_trade: { bg: 'bg-red-900/50', text: 'text-red-300', label: 'NO TRADE' },
}

const HORIZON_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  '0dte': { bg: 'bg-red-900/20', text: 'text-red-400', label: '0DTE' },
  weekly: { bg: 'bg-amber-900/20', text: 'text-amber-400', label: 'WEEKLY' },
  monthly: { bg: 'bg-blue-900/20', text: 'text-blue-400', label: 'MONTHLY' },
  leap: { bg: 'bg-purple-900/20', text: 'text-purple-400', label: 'LEAP' },
}

const TRADE_VERDICT: Record<string, { bg: string; text: string }> = {
  go: { bg: 'bg-green-900/30', text: 'text-green-400' },
  caution: { bg: 'bg-amber-900/30', text: 'text-amber-400' },
  no_go: { bg: 'bg-red-900/30', text: 'text-red-400' },
}

const DIR_CLR: Record<string, string> = {
  bullish: 'text-green-400',
  bearish: 'text-red-400',
  neutral: 'text-accent-cyan',
}

function TradeRow({ t }: { t: PlanTrade }) {
  const tv = TRADE_VERDICT[t.verdict.toLowerCase()] || TRADE_VERDICT.no_go
  const hs = HORIZON_STYLE[t.horizon] || HORIZON_STYLE.monthly
  return (
    <tr className="border-b border-border-secondary/40 hover:bg-bg-hover/50">
      <td className="py-0.5 px-1.5 text-2xs font-mono text-text-muted text-center">{t.rank}</td>
      <td className="py-0.5 px-1.5 text-xs font-mono font-bold text-accent-blue">{t.ticker}</td>
      <td className="py-0.5 px-1.5">
        <span className={clsx('px-1 py-0.5 rounded text-2xs font-semibold', hs.bg, hs.text)}>{hs.label}</span>
      </td>
      <td className="py-0.5 px-1.5 text-2xs text-text-secondary">{t.strategy_type.replace(/_/g, ' ')}</td>
      <td className="py-0.5 px-1.5">
        <span className={clsx('px-1 py-0.5 rounded text-2xs font-semibold uppercase', tv.bg, tv.text)}>
          {t.verdict === 'no_go' ? 'NO' : t.verdict}
        </span>
      </td>
      <td className="py-0.5 px-1.5">
        <div className="flex items-center gap-1">
          <div className="w-10 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
            <div
              className={clsx('h-full rounded-full', t.composite_score >= 0.7 ? 'bg-green-500' : t.composite_score >= 0.45 ? 'bg-amber-500' : 'bg-red-500')}
              style={{ width: `${Math.round(t.composite_score * 100)}%` }}
            />
          </div>
          <span className="text-2xs font-mono text-text-muted">{Math.round(t.composite_score * 100)}</span>
        </div>
      </td>
      <td className="py-0.5 px-1.5">
        <span className={clsx('text-2xs font-mono', DIR_CLR[t.direction] || 'text-text-muted')}>
          {t.direction === 'bullish' ? '\u25B2' : t.direction === 'bearish' ? '\u25BC' : '\u25C6'} {t.direction}
        </span>
      </td>
      <td className="py-0.5 px-1.5 text-2xs text-text-secondary">
        {t.trade_spec ? t.trade_spec.leg_codes.slice(0, 2).join(' | ') + (t.trade_spec.leg_codes.length > 2 ? ' ...' : '') : '--'}
      </td>
      <td className="py-0.5 px-1.5 text-2xs text-text-secondary max-w-[200px] truncate" title={t.rationale}>
        {t.rationale}
      </td>
    </tr>
  )
}

function HorizonSection({ horizon, trades }: { horizon: string; trades: PlanTrade[] }) {
  const hs = HORIZON_STYLE[horizon] || HORIZON_STYLE.monthly
  if (!trades.length) return null
  return (
    <div>
      <div className={clsx('flex items-center gap-2 px-1.5 py-0.5 border-b border-border-secondary/60', hs.bg)}>
        <span className={clsx('text-2xs font-bold uppercase tracking-wider', hs.text)}>{hs.label}</span>
        <span className="text-2xs text-text-muted">{trades.length} trade{trades.length !== 1 ? 's' : ''}</span>
      </div>
      <table className="w-full text-xs">
        <tbody>
          {trades.map(t => <TradeRow key={`${t.ticker}-${t.strategy_type}`} t={t} />)}
        </tbody>
      </table>
    </div>
  )
}

export function PlanPanel({ tickers }: { tickers: string[] }) {
  const { data, isLoading, isError, error } = usePlan(tickers)
  const [expanded, setExpanded] = useState(true)

  if (isLoading) {
    return (
      <div className="card">
        <div className="card-body flex items-center justify-center py-3">
          <Spinner size="sm" />
          <span className="text-xs text-text-muted ml-2">Generating daily plan...</span>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="card">
        <div className="card-body text-xs text-accent-red py-1.5 px-2">
          Plan error: {(error as Error)?.message || 'Unknown'}
        </div>
      </div>
    )
  }

  if (!data) return null

  const vs = VERDICT_STYLE[data.day_verdict] || VERDICT_STYLE.avoid
  const horizons = ['0dte', 'weekly', 'monthly', 'leap'] as const

  return (
    <div className="card">
      <div className="card-header py-1 px-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-xs font-bold text-text-primary uppercase tracking-wider">Daily Plan</h2>
          <span className={clsx('px-1.5 py-0.5 rounded text-2xs font-bold uppercase', vs.bg, vs.text)}>{vs.label}</span>
          <span className="text-2xs text-text-muted">{data.plan_for_date}</span>
          {data.total_trades > 0 && (
            <span className="text-2xs text-text-muted">{data.total_trades} trades</span>
          )}
        </div>
        <div className="flex items-center gap-3 text-2xs text-text-muted">
          <span>Max pos: <span className="text-text-primary font-mono">{data.risk_budget.max_new_positions}</span></span>
          <span>Risk $: <span className="text-text-primary font-mono">${data.risk_budget.max_daily_risk_dollars.toLocaleString()}</span></span>
          <span>Size: <span className="text-text-primary font-mono">{(data.risk_budget.position_size_factor * 100).toFixed(0)}%</span></span>
          <button onClick={() => setExpanded(v => !v)} className="text-accent-blue hover:underline ml-1">
            {expanded ? 'Hide' : 'Show'}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="card-body p-0">
          {/* Verdict reasons */}
          {data.day_verdict_reasons.length > 0 && (
            <div className="px-2 py-1 border-b border-border-secondary/40 text-2xs text-text-secondary">
              {data.day_verdict_reasons.map((r, i) => <span key={i} className="mr-3">{r}</span>)}
            </div>
          )}

          {/* Expiry events */}
          {data.expiry_events.length > 0 && (
            <div className="px-2 py-1 border-b border-border-secondary/40 flex items-center gap-2">
              <span className="text-2xs text-amber-400 font-semibold">EXPIRY TODAY:</span>
              {data.expiry_events.map((e, i) => (
                <span key={i} className="text-2xs text-text-secondary">
                  {e.label} ({e.tickers.join(', ')})
                </span>
              ))}
            </div>
          )}

          {/* Trades by horizon */}
          {data.total_trades > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-text-muted text-2xs uppercase tracking-wider border-b border-border-secondary">
                    <th className="py-0.5 px-1.5 text-center w-6">#</th>
                    <th className="py-0.5 px-1.5">Ticker</th>
                    <th className="py-0.5 px-1.5">Horizon</th>
                    <th className="py-0.5 px-1.5">Strategy</th>
                    <th className="py-0.5 px-1.5">Verdict</th>
                    <th className="py-0.5 px-1.5">Score</th>
                    <th className="py-0.5 px-1.5">Direction</th>
                    <th className="py-0.5 px-1.5">Legs</th>
                    <th className="py-0.5 px-1.5">Rationale</th>
                  </tr>
                </thead>
              </table>
              {horizons.map(h => {
                const trades = data.trades_by_horizon[h]
                return trades && trades.length > 0
                  ? <HorizonSection key={h} horizon={h} trades={trades} />
                  : null
              })}
            </div>
          ) : (
            <div className="px-2 py-2 text-2xs text-text-muted text-center">
              {data.day_verdict === 'no_trade' || data.day_verdict === 'avoid'
                ? 'No trades today — see verdict above'
                : 'No actionable trades found'}
            </div>
          )}

          {/* Summary */}
          {data.summary && (
            <div className="px-2 py-1 border-t border-border-secondary text-2xs text-text-muted">
              {data.summary}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
