import { clsx } from 'clsx'

interface GreeksBarProps {
  label: string
  value: number
  limit: number
  unit?: string
}

export function GreeksBar({ label, value, limit, unit = '' }: GreeksBarProps) {
  const absValue = Math.abs(value)
  const absLimit = Math.abs(limit)
  const pct = absLimit > 0 ? Math.min((absValue / absLimit) * 100, 100) : 0

  const barColor =
    pct > 80 ? 'bg-accent-red' :
    pct > 60 ? 'bg-accent-yellow' :
    'bg-accent-blue'

  return (
    <div className="flex items-center gap-2">
      <span className="text-2xs text-text-muted w-8 text-right">{label}</span>
      <div className="flex-1 h-2 bg-bg-tertiary rounded-full overflow-hidden">
        <div
          className={clsx('h-full rounded-full transition-all duration-300', barColor)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-2xs font-mono text-text-secondary w-16 text-right">
        {value >= 0 ? '+' : ''}{value.toFixed(1)}{unit}/{absLimit.toFixed(0)}
      </span>
    </div>
  )
}
