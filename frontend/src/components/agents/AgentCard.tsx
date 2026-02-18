import { useNavigate } from 'react-router-dom'
import { clsx } from 'clsx'
import type { AgentInfo } from '../../api/types'

const categoryColors: Record<string, string> = {
  safety: 'bg-red-500/20 text-red-400',
  perception: 'bg-blue-500/20 text-blue-400',
  analysis: 'bg-purple-500/20 text-purple-400',
  execution: 'bg-green-500/20 text-green-400',
  learning: 'bg-amber-500/20 text-amber-400',
}

const gradeColors: Record<string, string> = {
  A: 'text-green-400',
  B: 'text-blue-400',
  C: 'text-amber-400',
  F: 'text-red-400',
  'N/A': 'text-text-muted',
}

const statusDot: Record<string, string> = {
  completed: 'bg-green-400',
  idle: 'bg-gray-500',
  running: 'bg-blue-400 animate-pulse',
  error: 'bg-red-400',
  blocked: 'bg-red-500',
  waiting_for_human: 'bg-amber-400 animate-pulse',
}

function timeAgo(iso: string | null): string {
  if (!iso) return 'Never'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

interface AgentCardProps {
  agent: AgentInfo
}

export function AgentCard({ agent }: AgentCardProps) {
  const navigate = useNavigate()

  return (
    <div
      onClick={() => navigate(`/agents/${agent.name}`)}
      className="bg-bg-secondary border border-border-primary rounded-lg p-3 cursor-pointer hover:border-accent-blue/50 transition-colors"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <div className={clsx('w-2 h-2 rounded-full', statusDot[agent.status] || 'bg-gray-500')} />
          <span className="text-sm font-medium text-text-primary">{agent.display_name}</span>
        </div>
        {agent.today_grade && (
          <span className={clsx('text-lg font-bold', gradeColors[agent.today_grade] || 'text-text-muted')}>
            {agent.today_grade}
          </span>
        )}
      </div>

      {/* Category badge */}
      <div className="mb-2">
        <span className={clsx('text-[10px] px-1.5 py-0.5 rounded', categoryColors[agent.category] || 'bg-gray-500/20 text-gray-400')}>
          {agent.category}
        </span>
      </div>

      {/* Role */}
      <p className="text-xs text-text-secondary mb-3 line-clamp-2">{agent.role}</p>

      {/* Stats row */}
      <div className="flex items-center justify-between text-[10px] text-text-muted">
        <span>{agent.run_count} runs</span>
        <span>{agent.last_duration_ms != null ? `${agent.last_duration_ms}ms` : '--'}</span>
        <span>{timeAgo(agent.last_run_at)}</span>
      </div>

      {/* Error indicator */}
      {agent.last_error && (
        <div className="mt-2 text-[10px] text-red-400 truncate">
          {agent.last_error}
        </div>
      )}

      {/* Capabilities */}
      <div className="mt-2 flex flex-wrap gap-1">
        {agent.capabilities_implemented.slice(0, 3).map((cap) => (
          <span key={cap} className="text-[9px] px-1 py-0.5 rounded bg-green-500/10 text-green-400">
            {cap}
          </span>
        ))}
        {agent.capabilities_planned.length > 0 && (
          <span className="text-[9px] px-1 py-0.5 rounded bg-gray-500/10 text-text-muted">
            +{agent.capabilities_planned.length} planned
          </span>
        )}
      </div>
    </div>
  )
}
