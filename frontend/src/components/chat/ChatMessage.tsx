import { clsx } from 'clsx'

interface ChatMessageProps {
  role: 'user' | 'system'
  text: string
  timestamp?: string
}

export function ChatMessage({ role, text, timestamp }: ChatMessageProps) {
  const isUser = role === 'user'

  // Simple markdown-like rendering for bold text
  const rendered = text.split('\n').map((line, i) => {
    const parts = line.split(/(\*\*.*?\*\*)/g)
    return (
      <div key={i} className={i > 0 ? 'mt-0.5' : ''}>
        {parts.map((part, j) => {
          if (part.startsWith('**') && part.endsWith('**')) {
            return <strong key={j} className="font-semibold text-text-primary">{part.slice(2, -2)}</strong>
          }
          return <span key={j}>{part}</span>
        })}
      </div>
    )
  })

  return (
    <div className={clsx('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={clsx(
          'max-w-[85%] rounded-lg px-3 py-2 text-xs',
          isUser
            ? 'bg-accent-blue/20 border border-accent-blue/30 text-text-primary'
            : 'bg-bg-tertiary border border-border-secondary text-text-secondary',
        )}
      >
        <div className="whitespace-pre-wrap">{rendered}</div>
        {timestamp && (
          <div className="text-2xs text-text-muted mt-1 text-right">{timestamp}</div>
        )}
      </div>
    </div>
  )
}
