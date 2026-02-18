import type { ICellRendererParams } from 'ag-grid-community'

export function PnLRenderer({ value }: ICellRendererParams) {
  if (value == null) return <span className="text-text-muted">--</span>
  const num = Number(value)
  const color = num > 0 ? 'text-pnl-profit' : num < 0 ? 'text-pnl-loss' : 'text-pnl-zero'
  const sign = num > 0 ? '+' : ''
  return (
    <span className={`font-mono-num font-medium ${color}`}>
      {sign}${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
    </span>
  )
}

export function PercentRenderer({ value }: ICellRendererParams) {
  if (value == null) return <span className="text-text-muted">--</span>
  const num = Number(value)
  const color = num > 0 ? 'text-pnl-profit' : num < 0 ? 'text-pnl-loss' : 'text-pnl-zero'
  const sign = num > 0 ? '+' : ''
  return (
    <span className={`font-mono-num ${color}`}>
      {sign}{num.toFixed(1)}%
    </span>
  )
}

export function StatusBadgeRenderer({ value }: ICellRendererParams) {
  const statusColors: Record<string, string> = {
    executed: 'bg-green-900/30 text-green-400 border-green-800',
    open: 'bg-green-900/30 text-green-400 border-green-800',
    closed: 'bg-zinc-800/50 text-zinc-400 border-zinc-700',
    what_if: 'bg-blue-900/30 text-blue-400 border-blue-800',
    pending: 'bg-orange-900/30 text-orange-400 border-orange-800',
    rejected: 'bg-red-900/30 text-red-400 border-red-800',
    intent: 'bg-purple-900/30 text-purple-400 border-purple-800',
    rolled: 'bg-cyan-900/30 text-cyan-400 border-cyan-800',
  }
  const cls = statusColors[value?.toLowerCase()] || 'bg-zinc-800/50 text-zinc-400 border-zinc-700'
  return (
    <span className={`px-1.5 py-0.5 rounded text-2xs font-semibold border ${cls}`}>
      {(value || '').toUpperCase()}
    </span>
  )
}

export function DTERenderer({ value }: ICellRendererParams) {
  if (value == null) return <span className="text-text-muted">--</span>
  const dte = Number(value)
  const color =
    dte <= 3 ? 'text-accent-red' :
    dte <= 7 ? 'text-accent-orange' :
    dte <= 14 ? 'text-accent-yellow' :
    'text-text-primary'
  return <span className={`font-mono-num ${color}`}>{dte}d</span>
}

export function GreeksRenderer({ value }: ICellRendererParams) {
  if (value == null) return <span className="text-text-muted">--</span>
  const num = Number(value)
  return (
    <span className="font-mono-num text-text-secondary">
      {num >= 0 ? '+' : ''}{num.toFixed(2)}
    </span>
  )
}

export function CurrencyRenderer({ value }: ICellRendererParams) {
  if (value == null) return <span className="text-text-muted">--</span>
  const num = Number(value)
  return (
    <span className="font-mono-num text-text-primary">
      ${num.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
    </span>
  )
}

export function TradeTypeRenderer({ value, data }: ICellRendererParams) {
  const isWhatIf = data?.trade_type === 'what_if' || data?.portfolio_type === 'what_if'
  if (isWhatIf) {
    return (
      <span className="px-1.5 py-0.5 rounded text-2xs font-semibold bg-blue-900/20 text-blue-400 border border-blue-800">
        WHATIF
      </span>
    )
  }
  return <span className="text-text-secondary text-2xs">{(value || 'real').toUpperCase()}</span>
}
