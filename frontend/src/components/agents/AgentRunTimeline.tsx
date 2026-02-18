import { clsx } from 'clsx'
import type { AgentRun } from '../../api/types'

const statusColors: Record<string, string> = {
  completed: 'text-green-400',
  error: 'text-red-400',
  blocked: 'text-red-500',
  idle: 'text-text-muted',
  running: 'text-blue-400',
  waiting_for_human: 'text-amber-400',
}

const statusBg: Record<string, string> = {
  completed: 'bg-green-500/10',
  error: 'bg-red-500/10',
  blocked: 'bg-red-500/10',
  idle: 'bg-bg-tertiary',
  running: 'bg-blue-500/10',
  waiting_for_human: 'bg-amber-500/10',
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

interface AgentRunTimelineProps {
  runs: AgentRun[]
  maxItems?: number
}

export function AgentRunTimeline({ runs, maxItems = 20 }: AgentRunTimelineProps) {
  const items = runs.slice(0, maxItems)

  if (items.length === 0) {
    return (
      <div className="text-xs text-text-muted py-4 text-center">
        No runs recorded yet
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {items.map((run) => (
        <div
          key={run.id}
          className={clsx(
            'flex items-start gap-3 px-3 py-2 rounded text-xs',
            statusBg[run.status] || 'bg-bg-tertiary',
          )}
        >
          {/* Time */}
          <span className="text-text-muted font-mono w-[72px] shrink-0">
            {formatTime(run.started_at)}
          </span>

          {/* Status dot */}
          <div className="mt-1">
            <div
              className={clsx(
                'w-2 h-2 rounded-full',
                run.status === 'completed' ? 'bg-green-400' :
                run.status === 'error' ? 'bg-red-400' :
                run.status === 'blocked' ? 'bg-red-500' :
                run.status === 'running' ? 'bg-blue-400' :
                run.status === 'waiting_for_human' ? 'bg-amber-400' :
                'bg-gray-500',
              )}
            />
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className={clsx('font-medium', statusColors[run.status] || 'text-text-primary')}>
                {run.status}
              </span>
              {run.workflow_state && (
                <span className="text-text-muted">
                  in {run.workflow_state}
                </span>
              )}
              {run.duration_ms != null && (
                <span className="text-text-muted ml-auto">
                  {run.duration_ms}ms
                </span>
              )}
            </div>

            {/* Messages */}
            {run.messages.length > 0 && (
              <div className="mt-1 text-text-secondary">
                {run.messages.slice(0, 2).map((msg, i) => (
                  <div key={i} className="truncate">{msg}</div>
                ))}
                {run.messages.length > 2 && (
                  <div className="text-text-muted">+{run.messages.length - 2} more</div>
                )}
              </div>
            )}

            {/* Error */}
            {run.error_message && (
              <div className="mt-1 text-red-400 truncate">
                {run.error_message}
              </div>
            )}
          </div>

          {/* Cycle */}
          {run.cycle_id != null && (
            <span className="text-text-muted font-mono shrink-0">
              #{run.cycle_id}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}
