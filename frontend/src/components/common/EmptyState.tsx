import { Inbox } from 'lucide-react'

interface EmptyStateProps {
  message?: string
  icon?: React.ReactNode
}

export function EmptyState({ message = 'No data', icon }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-text-muted">
      {icon || <Inbox size={32} className="mb-2 opacity-50" />}
      <p className="text-sm">{message}</p>
    </div>
  )
}
