import { clsx } from 'clsx'

interface PnLDisplayProps {
  value: number | null | undefined
  size?: 'sm' | 'md' | 'lg'
  showSign?: boolean
  currency?: string
  className?: string
}

export function PnLDisplay({ value, size = 'sm', showSign = true, currency = '$', className }: PnLDisplayProps) {
  if (value == null) return <span className="text-text-muted">--</span>

  const color = value > 0 ? 'text-pnl-profit' : value < 0 ? 'text-pnl-loss' : 'text-pnl-zero'
  const sign = showSign && value > 0 ? '+' : ''
  const sizeClass = size === 'lg' ? 'text-lg' : size === 'md' ? 'text-sm' : 'text-xs'

  return (
    <span className={clsx('font-mono-num font-medium', color, sizeClass, className)}>
      {sign}{currency}{Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
    </span>
  )
}
