import { clsx } from 'clsx'

interface CurrencyDisplayProps {
  value: number | null | undefined
  currency?: 'USD' | 'INR'
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const symbols: Record<string, string> = {
  USD: '$',
  INR: '\u20B9',
}

export function CurrencyDisplay({ value, currency = 'USD', size = 'sm', className }: CurrencyDisplayProps) {
  if (value == null) return <span className="text-text-muted">--</span>

  const symbol = symbols[currency] || '$'
  const sizeClass = size === 'lg' ? 'text-lg' : size === 'md' ? 'text-sm' : 'text-xs'

  return (
    <span className={clsx('font-mono-num text-text-primary', sizeClass, className)}>
      {symbol}{value.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
    </span>
  )
}
