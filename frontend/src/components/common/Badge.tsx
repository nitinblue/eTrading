import { clsx } from 'clsx'

const variants: Record<string, string> = {
  open: 'bg-green-900/30 text-green-400 border-green-800',
  executed: 'bg-green-900/30 text-green-400 border-green-800',
  closed: 'bg-zinc-800/50 text-zinc-400 border-zinc-700',
  what_if: 'bg-blue-900/30 text-blue-400 border-blue-800',
  pending: 'bg-orange-900/30 text-orange-400 border-orange-800',
  rejected: 'bg-red-900/30 text-red-400 border-red-800',
  real: 'bg-emerald-900/30 text-emerald-400 border-emerald-800',
  paper: 'bg-purple-900/30 text-purple-400 border-purple-800',
  manual: 'bg-yellow-900/30 text-yellow-400 border-yellow-800',
  default: 'bg-zinc-800/50 text-zinc-400 border-zinc-700',
}

interface BadgeProps {
  variant?: string
  children: React.ReactNode
  className?: string
}

export function Badge({ variant = 'default', children, className }: BadgeProps) {
  const cls = variants[variant.toLowerCase()] || variants.default
  return (
    <span className={clsx('inline-flex items-center px-1.5 py-0.5 rounded text-2xs font-semibold border', cls, className)}>
      {children}
    </span>
  )
}
