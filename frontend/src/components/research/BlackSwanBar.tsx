import { clsx } from 'clsx'
import { useBlackSwan } from '../../hooks/useBlackSwan'
import type { StressIndicator } from '../../api/types'

const LEVEL_STYLE: Record<string, { bg: string; text: string; border: string }> = {
  NORMAL: { bg: 'bg-green-900/20', text: 'text-green-400', border: 'border-green-800' },
  ELEVATED: { bg: 'bg-amber-900/20', text: 'text-amber-400', border: 'border-amber-800' },
  HIGH: { bg: 'bg-red-900/20', text: 'text-red-400', border: 'border-red-800' },
  CRITICAL: { bg: 'bg-red-900/40', text: 'text-red-300', border: 'border-red-600' },
}

const STATUS_DOT: Record<string, string> = {
  NORMAL: 'bg-green-500',
  WARNING: 'bg-amber-500',
  DANGER: 'bg-red-500',
  CRITICAL: 'bg-red-400 animate-pulse',
  UNAVAILABLE: 'bg-gray-600',
}

function IndicatorDot({ ind }: { ind: StressIndicator }) {
  return (
    <div className="flex items-center gap-1" title={`${ind.name}: ${ind.description} (score: ${(ind.score * 100).toFixed(0)}%)`}>
      <span className={clsx('w-1.5 h-1.5 rounded-full', STATUS_DOT[ind.status] || 'bg-gray-600')} />
      <span className="text-[10px] text-text-muted">{ind.name.replace(/ Level| Stress| Gap/g, '')}</span>
      {ind.value != null && (
        <span className={clsx('text-[10px] font-mono',
          ind.status === 'DANGER' || ind.status === 'CRITICAL' ? 'text-red-400' :
          ind.status === 'WARNING' ? 'text-amber-400' : 'text-text-secondary'
        )}>
          {ind.value.toFixed(1)}
        </span>
      )}
    </div>
  )
}

export function BlackSwanBar() {
  const { data, isLoading } = useBlackSwan()

  if (isLoading || !data) return null
  if (data.alert_level === 'NORMAL' && data.composite_score < 0.15) return null // hide when calm

  const ls = LEVEL_STYLE[data.alert_level] || LEVEL_STYLE.NORMAL
  const pct = Math.round(data.composite_score * 100)

  return (
    <div className={clsx('flex items-center gap-3 px-2 py-1 rounded border text-[10px]', ls.bg, ls.border)}>
      {/* Alert level badge */}
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <span className={clsx('font-bold uppercase text-[11px]', ls.text,
          data.alert_level === 'CRITICAL' && 'animate-pulse'
        )}>
          {data.alert_level === 'CRITICAL' ? 'BLACK SWAN' : data.alert_level}
        </span>
        {/* Score bar */}
        <div className="w-14 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
          <div
            className={clsx('h-full rounded-full', pct >= 60 ? 'bg-red-500' : pct >= 30 ? 'bg-amber-500' : 'bg-green-500')}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className={clsx('font-mono', ls.text)}>{pct}%</span>
      </div>

      <span className="text-border-secondary">|</span>

      {/* Stress indicators */}
      <div className="flex items-center gap-2 flex-wrap">
        {data.indicators.map((ind) => (
          <IndicatorDot key={ind.name} ind={ind} />
        ))}
      </div>

      {/* Breakers */}
      {data.triggered_breakers > 0 && (
        <>
          <span className="text-border-secondary">|</span>
          <span className="text-red-400 font-bold animate-pulse">
            {data.triggered_breakers} BREAKER{data.triggered_breakers > 1 ? 'S' : ''}
          </span>
        </>
      )}

      {/* Action */}
      <span className={clsx('ml-auto text-[10px] italic flex-shrink-0', ls.text)}>{data.action}</span>
    </div>
  )
}
