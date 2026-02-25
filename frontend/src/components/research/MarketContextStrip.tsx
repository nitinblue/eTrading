import { clsx } from 'clsx'
import { useMarketContext } from '../../hooks/useMarketContext'
import type { IntermarketEntry } from '../../api/types'

const ENV_STYLE: Record<string, { bg: string; text: string; icon: string }> = {
  'risk-on':    { bg: 'bg-green-900/20', text: 'text-green-400', icon: '\u2714' },
  'cautious':   { bg: 'bg-amber-900/20', text: 'text-amber-400', icon: '\u26A0' },
  'defensive':  { bg: 'bg-red-900/20',   text: 'text-red-400',   icon: '\u26D4' },
  'crisis':     { bg: 'bg-red-900/40',   text: 'text-red-300',   icon: '\u2622' },
}

const RC: Record<number, { color: string; label: string }> = {
  1: { color: 'text-green-400', label: 'R1' },
  2: { color: 'text-amber-400', label: 'R2' },
  3: { color: 'text-blue-400',  label: 'R3' },
  4: { color: 'text-red-400',   label: 'R4' },
}

function IntermarketPill({ e }: { e: IntermarketEntry }) {
  const rc = RC[e.regime_id ?? 0] || { color: 'text-text-muted', label: '?' }
  return (
    <span className="inline-flex items-center gap-0.5" title={`${e.ticker}: ${e.regime_label || 'unknown'} (${((e.confidence || 0) * 100).toFixed(0)}%)`}>
      <span className="text-[10px] text-text-muted font-mono">{e.ticker}</span>
      <span className={clsx('text-[10px] font-bold font-mono', rc.color)}>{rc.label}</span>
    </span>
  )
}

export function MarketContextStrip() {
  const { data, isLoading } = useMarketContext()

  if (isLoading || !data) return null

  const env = ENV_STYLE[data.environment_label] || ENV_STYLE.cautious
  const sizePct = Math.round(data.position_size_factor * 100)
  const im = data.intermarket

  return (
    <div className="flex items-center gap-3 px-2 py-1 bg-bg-secondary border border-border-secondary rounded text-[10px]">
      {/* Environment label */}
      <div className={clsx('flex items-center gap-1 px-1.5 py-0.5 rounded font-semibold uppercase', env.bg, env.text)}>
        <span>{env.icon}</span>
        <span>{data.environment_label}</span>
      </div>

      {/* Trading gate */}
      <div className="flex items-center gap-1">
        <span className={clsx('w-1.5 h-1.5 rounded-full', data.trading_allowed ? 'bg-green-500' : 'bg-red-500 animate-pulse')} />
        <span className={data.trading_allowed ? 'text-green-400' : 'text-red-400 font-bold'}>
          {data.trading_allowed ? 'TRADING ON' : 'TRADING HALTED'}
        </span>
      </div>

      {/* Position size factor */}
      <div className="flex items-center gap-1">
        <span className="text-text-muted">Size:</span>
        <div className="w-10 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
          <div className={clsx('h-full rounded-full', sizePct >= 80 ? 'bg-green-500' : sizePct >= 50 ? 'bg-amber-500' : 'bg-red-500')} style={{ width: `${sizePct}%` }} />
        </div>
        <span className={clsx('font-mono', sizePct >= 80 ? 'text-green-400' : sizePct >= 50 ? 'text-amber-400' : 'text-red-400')}>{sizePct}%</span>
      </div>

      <span className="text-border-secondary">|</span>

      {/* Intermarket regime alignment */}
      <div className="flex items-center gap-1.5">
        <span className="text-text-muted">Intermarket:</span>
        {im.entries.map(e => <IntermarketPill key={e.ticker} e={e} />)}
        {im.divergence && <span className="text-amber-400 font-bold">DIVERGENT</span>}
        <span className="text-text-muted">
          ({im.risk_on_count} on / {im.risk_off_count} off)
        </span>
      </div>

      {/* Market */}
      <span className="ml-auto text-text-muted font-mono">{data.market} {data.as_of_date}</span>
    </div>
  )
}
