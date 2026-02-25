import { clsx } from 'clsx'
import { useRanking } from '../../hooks/useRanking'
import { Spinner } from '../common/Spinner'
import type { RankedEntry } from '../../api/types'

const VERDICT_CLR: Record<string, { bg: string; text: string }> = {
  go: { bg: 'bg-green-900/30', text: 'text-green-400' },
  caution: { bg: 'bg-amber-900/30', text: 'text-amber-400' },
  no_go: { bg: 'bg-red-900/30', text: 'text-red-400' },
}

const DIR_CLR: Record<string, string> = {
  bullish: 'text-green-400',
  bearish: 'text-red-400',
  neutral: 'text-accent-cyan',
}

const STRAT_CLR: Record<string, string> = {
  zero_dte: 'bg-red-900/20 text-red-400 border-red-800',
  leap: 'bg-blue-900/20 text-blue-400 border-blue-800',
  breakout: 'bg-green-900/20 text-green-400 border-green-800',
  momentum: 'bg-amber-900/20 text-amber-400 border-amber-800',
}

function ScoreBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const c = pct >= 70 ? 'bg-green-500' : pct >= 45 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-1">
      <div className="w-12 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full', c)} style={{ width: `${pct}%` }} />
      </div>
      <span className={clsx('text-2xs font-mono', pct >= 70 ? 'text-green-400' : pct >= 45 ? 'text-amber-400' : 'text-red-400')}>
        {pct}
      </span>
    </div>
  )
}

function RankRow({ entry: e }: { entry: RankedEntry }) {
  const vc = VERDICT_CLR[e.verdict.toLowerCase()] || VERDICT_CLR.no_go
  return (
    <tr className="border-b border-border-secondary/40 hover:bg-bg-hover/50 transition-colors">
      <td className="py-1 px-2 text-xs font-mono text-text-muted text-center">{e.rank}</td>
      <td className="py-1 px-2">
        <span className="text-xs font-mono font-bold text-accent-blue">{e.ticker}</span>
      </td>
      <td className="py-1 px-2">
        <span className={clsx('px-1.5 py-0.5 rounded text-2xs font-semibold border', STRAT_CLR[e.strategy_type] || 'bg-bg-tertiary text-text-muted border-border-secondary')}>
          {e.strategy_type === 'zero_dte' ? '0DTE' : e.strategy_type.toUpperCase()}
        </span>
      </td>
      <td className="py-1 px-2">
        <span className={clsx('px-1 py-0.5 rounded text-2xs font-semibold uppercase', vc.bg, vc.text)}>
          {e.verdict === 'no_go' ? 'NO' : e.verdict}
        </span>
      </td>
      <td className="py-1 px-2"><ScoreBar value={e.composite_score} /></td>
      <td className="py-1 px-2">
        <span className={clsx('text-xs font-mono', DIR_CLR[e.direction] || 'text-text-muted')}>
          {e.direction === 'bullish' ? '\u25B2' : e.direction === 'bearish' ? '\u25BC' : '\u25C6'} {e.direction}
        </span>
      </td>
      <td className="py-1 px-2">
        <span className="text-2xs text-text-secondary">{e.strategy_name}</span>
      </td>
      <td className="py-1 px-2 text-2xs text-text-secondary max-w-[250px] truncate" title={e.rationale}>
        {e.rationale}
      </td>
    </tr>
  )
}

export function RankingPanel({ tickers }: { tickers: string[] }) {
  const { data, isLoading, isError, error } = useRanking(tickers)

  if (isLoading) {
    return (
      <div className="card">
        <div className="card-body flex items-center justify-center py-4">
          <Spinner size="sm" />
          <span className="text-xs text-text-muted ml-2">Ranking {tickers.length} tickers across 4 strategies...</span>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="card">
        <div className="card-body text-xs text-accent-red py-2 px-3">
          Ranking error: {(error as Error)?.message || 'Unknown'}
        </div>
      </div>
    )
  }

  if (!data || !data.top_trades.length) {
    return (
      <div className="card">
        <div className="card-body text-xs text-text-muted text-center py-3">
          No ranked trades available
        </div>
      </div>
    )
  }

  // Filter to actionable entries (GO or CAUTION)
  const actionable = data.top_trades.filter(e => e.verdict.toLowerCase() !== 'no_go')
  const display = actionable.length > 0 ? actionable : data.top_trades.slice(0, 10)

  return (
    <div className="card">
      <div className="card-header py-1 px-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-xs font-bold text-text-primary uppercase tracking-wider">Trade Ranking</h2>
          <span className="text-2xs text-text-muted">{data.as_of_date}</span>
          {data.black_swan_gate && (
            <span className="text-2xs font-bold text-red-400 bg-red-900/30 px-1.5 py-0.5 rounded animate-pulse">
              BLACK SWAN HALT
            </span>
          )}
          {!data.black_swan_gate && data.black_swan_level && data.black_swan_level !== 'NORMAL' && (
            <span className="text-2xs font-bold text-amber-400 bg-amber-900/30 px-1.5 py-0.5 rounded">
              {data.black_swan_level}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-2xs text-text-muted">
          <span>Assessed: <span className="text-text-primary font-mono">{data.total_assessed}</span></span>
          <span>Actionable: <span className="text-accent-green font-mono">{data.total_actionable}</span></span>
        </div>
      </div>
      <div className="card-body p-0 overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-text-muted text-left border-b border-border-secondary text-2xs uppercase tracking-wider">
              <th className="py-1 px-2 text-center w-8">#</th>
              <th className="py-1 px-2">Ticker</th>
              <th className="py-1 px-2">Strategy</th>
              <th className="py-1 px-2">Verdict</th>
              <th className="py-1 px-2">Score</th>
              <th className="py-1 px-2">Direction</th>
              <th className="py-1 px-2">Name</th>
              <th className="py-1 px-2">Rationale</th>
            </tr>
          </thead>
          <tbody>
            {display.map((e) => (
              <RankRow key={`${e.ticker}-${e.strategy_type}`} entry={e} />
            ))}
          </tbody>
        </table>
      </div>
      {data.summary && (
        <div className="px-2 py-1 border-t border-border-secondary text-2xs text-text-muted">
          {data.summary}
        </div>
      )}
    </div>
  )
}
