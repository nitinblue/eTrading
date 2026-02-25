import { clsx } from 'clsx'
import { useMarketWatchlist, useMacroCalendar } from '../hooks/useRegime'
import { Spinner } from '../components/common/Spinner'
import type { MacroEvent } from '../api/types'

// Regime color + label + definition mapping
const REGIME_CONFIG: Record<number, { color: string; bg: string; border: string; label: string; strategy: string; definition: string }> = {
  1: { color: 'text-green-400', bg: 'bg-green-900/30', border: 'border-green-700', label: 'Low Vol MR', strategy: 'Iron condors, strangles, theta', definition: 'Low volatility, mean-reverting price action. Markets oscillate in a range. Ideal for premium selling — iron condors, strangles, and theta harvesting.' },
  2: { color: 'text-amber-400', bg: 'bg-amber-900/30', border: 'border-amber-700', label: 'High Vol MR', strategy: 'Wide wings, defined risk', definition: 'Elevated volatility but still mean-reverting. Sharp swings that revert. Use wider wings and defined-risk strategies to capture rich premium.' },
  3: { color: 'text-blue-400', bg: 'bg-blue-900/30', border: 'border-blue-700', label: 'Low Vol Trend', strategy: 'Directional spreads', definition: 'Low volatility with sustained directional momentum. Steady grind up or down. Favor directional spreads aligned with trend, debit spreads.' },
  4: { color: 'text-red-400', bg: 'bg-red-900/30', border: 'border-red-700', label: 'High Vol Trend', strategy: 'Risk-defined directional', definition: 'High volatility with trending behavior. Fast, violent moves. Use risk-defined directional plays, consider long vega. Tighten stops.' },
}

function getRC(regime: number) {
  return REGIME_CONFIG[regime] || { color: 'text-text-muted', bg: 'bg-bg-tertiary', border: 'border-border-secondary', label: 'Unknown', strategy: '--' }
}

function TrendArrow({ direction }: { direction: string | null }) {
  if (!direction) return <span className="text-text-muted text-xs">--</span>
  if (direction === 'bullish' || direction === 'up') return <span className="text-green-400 text-xs">&#9650;</span>
  if (direction === 'bearish' || direction === 'down') return <span className="text-red-400 text-xs">&#9660;</span>
  return <span className="text-text-muted text-xs">&#9654;</span>
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const barColor = pct >= 80 ? 'bg-green-500' : pct >= 50 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-14 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full', barColor)} style={{ width: `${pct}%` }} />
      </div>
      <span className={clsx(
        'text-xs font-mono',
        pct >= 80 ? 'text-green-400' : pct >= 50 ? 'text-amber-400' : 'text-red-400'
      )}>
        {pct}%
      </span>
    </div>
  )
}

const IMPACT_STYLE: Record<string, { bg: string; text: string }> = {
  high: { bg: 'bg-red-900/30', text: 'text-red-400' },
  medium: { bg: 'bg-amber-900/30', text: 'text-amber-400' },
  low: { bg: 'bg-green-900/30', text: 'text-green-400' },
}

function ImpactBadge({ impact }: { impact: string }) {
  const s = IMPACT_STYLE[impact] || IMPACT_STYLE.low
  return <span className={clsx('px-1.5 py-0.5 rounded text-2xs font-semibold uppercase', s.bg, s.text)}>{impact}</span>
}

function daysFromNow(dateStr: string): number {
  const d = new Date(dateStr)
  const now = new Date()
  return Math.ceil((d.getTime() - now.getTime()) / 86400000)
}

export function MarketDashboardPage() {
  const { data: watchlist, isLoading, isError, error } = useMarketWatchlist()
  const { data: macro, isLoading: macroLoading } = useMacroCalendar()


  if (isError) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-accent-red text-sm">
          Failed to load market data: {(error as Error)?.message || 'Unknown error'}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold text-text-primary">Market Regime Dashboard</h1>
        <span className="text-xs text-text-muted">
          HMM Detection | 5m refresh
          {isLoading && <span className="ml-2 text-accent-blue">Loading...</span>}
        </span>
      </div>

      {/* Macro Events — upcoming economic calendar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-2">
        {/* Next Event highlight */}
        <div className="card">
          <div className="card-header py-1"><h2 className="text-xs font-semibold text-text-secondary uppercase">Next Event</h2></div>
          <div className="card-body py-2">
            {macroLoading ? <Spinner size="sm" /> : macro?.next_event ? (
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-text-primary">{macro.next_event.name}</span>
                  <ImpactBadge impact={macro.next_event.impact} />
                </div>
                <div className="text-xs text-text-muted">{macro.next_event.date} ({macro.days_to_next}d away)</div>
                <div className="text-xs text-text-secondary">{macro.next_event.options_impact}</div>
                {macro.next_fomc && macro.next_fomc.date !== macro.next_event.date && (
                  <div className="text-xs text-amber-400 mt-1">Next FOMC: {macro.next_fomc.date} ({macro.days_to_next_fomc}d)</div>
                )}
              </div>
            ) : <span className="text-xs text-text-muted">No upcoming events</span>}
          </div>
        </div>

        {/* 7-day events */}
        <div className="lg:col-span-2 card">
          <div className="card-header py-1"><h2 className="text-xs font-semibold text-text-secondary uppercase">Upcoming Events (30d)</h2></div>
          <div className="card-body p-0">
            {macroLoading ? (
              <div className="py-4 flex justify-center"><Spinner size="sm" /></div>
            ) : macro?.events_next_30_days && macro.events_next_30_days.length > 0 ? (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-text-muted border-b border-border-secondary text-2xs uppercase">
                    <th className="py-1 px-2 text-left">Date</th>
                    <th className="py-1 px-2 text-left">Days</th>
                    <th className="py-1 px-2 text-left">Event</th>
                    <th className="py-1 px-2 text-center">Impact</th>
                    <th className="py-1 px-2 text-left">Options Impact</th>
                  </tr>
                </thead>
                <tbody>
                  {macro.events_next_30_days.map((evt: MacroEvent, i: number) => {
                    const days = daysFromNow(evt.date)
                    return (
                      <tr key={i} className={clsx('border-b border-border-secondary/50', days <= 3 && 'bg-red-900/10')}>
                        <td className="py-1 px-2 font-mono text-text-primary">{evt.date}</td>
                        <td className={clsx('py-1 px-2 font-mono', days <= 3 ? 'text-red-400 font-bold' : 'text-text-secondary')}>{days}d</td>
                        <td className="py-1 px-2 font-medium text-text-primary">{evt.name}</td>
                        <td className="py-1 px-2 text-center"><ImpactBadge impact={evt.impact} /></td>
                        <td className="py-1 px-2 text-text-secondary truncate max-w-[300px]">{evt.options_impact}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            ) : <div className="py-3 text-center text-xs text-text-muted">No events in next 30 days</div>}
          </div>
        </div>
      </div>

      {/* State Definitions — always visible immediately */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        {([1, 2, 3, 4] as const).map((r) => {
          const rc = getRC(r)
          return (
            <div key={r} className={clsx('rounded border px-2.5 py-2', rc.border, rc.bg)}>
              <div className={clsx('text-xs font-bold font-mono', rc.color)}>R{r} {rc.label}</div>
              <div className="text-2xs text-text-secondary leading-snug mt-0.5">{rc.definition}</div>
              <div className="text-2xs text-text-muted mt-1">Strategy: {rc.strategy}</div>
            </div>
          )
        })}
      </div>

      {/* Regime table — loaded async */}
      {isLoading ? (
        <div className="card">
          <div className="card-body flex items-center justify-center py-8">
            <Spinner size="sm" />
            <span className="text-xs text-text-muted ml-2">Detecting regimes...</span>
          </div>
        </div>
      ) : !watchlist || watchlist.length === 0 ? (
        <div className="card">
          <div className="card-body text-center py-6 text-text-muted text-xs">
            No watchlist configured. Add tickers to config/market_watchlist.yaml
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="card-body p-0">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-muted text-left border-b border-border-secondary text-2xs uppercase tracking-wider">
                  <th className="py-1.5 px-2">Ticker</th>
                  <th className="py-1.5 px-2">Asset</th>
                  <th className="py-1.5 px-2">Regime</th>
                  <th className="py-1.5 px-2">Confidence</th>
                  <th className="py-1.5 px-2 text-center">Trend</th>
                  <th className="py-1.5 px-2">Strategy</th>
                </tr>
              </thead>
              <tbody>
                {watchlist.map((item) => {
                  const rc = getRC(item.regime)
                  return (
                    <tr
                      key={item.ticker}
                      className="border-b border-border-secondary/50 hover:bg-bg-hover transition-colors"
                    >
                      <td className="py-1.5 px-2">
                        <span className="font-mono font-bold text-accent-blue">{item.ticker}</span>
                        <span className="text-text-muted text-2xs ml-1.5">{item.name}</span>
                      </td>
                      <td className="py-1.5 px-2 text-text-secondary text-2xs capitalize">{item.asset_class.replace('_', ' ')}</td>
                      <td className="py-1.5 px-2">
                        <span className={clsx('px-1.5 py-0.5 rounded text-2xs font-semibold border', rc.bg, rc.color, rc.border)}>
                          R{item.regime}
                        </span>
                        <span className={clsx('ml-1.5 text-2xs', rc.color)}>{rc.label}</span>
                      </td>
                      <td className="py-1.5 px-2">
                        <ConfidenceBar value={item.confidence} />
                      </td>
                      <td className="py-1.5 px-2 text-center">
                        <TrendArrow direction={item.trend_direction} />
                      </td>
                      <td className="py-1.5 px-2 text-xs text-text-secondary max-w-[300px] truncate">
                        {item.strategy_comment || rc.strategy}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
