import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { clsx } from 'clsx'
import { Database, ShieldOff, ChevronDown, ChevronUp } from 'lucide-react'
import type { AgentInfo } from '../../api/types'
import { AGENT_ICONS, CATEGORY_CONFIG, type AgentCategory } from '../../config/agentConfig'

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
  const [expanded, setExpanded] = useState(false)
  const cat = CATEGORY_CONFIG[agent.category as AgentCategory]
  const AgentIcon = AGENT_ICONS[agent.name]

  return (
    <div
      className={clsx(
        'bg-bg-secondary border rounded-lg overflow-hidden transition-all',
        cat?.border || 'border-border-primary',
        'hover:shadow-lg hover:shadow-black/20',
      )}
    >
      {/* Colored top accent bar */}
      <div className={clsx('h-0.5', cat?.dot || 'bg-gray-500')} />

      {/* Header — clickable to detail page */}
      <div
        onClick={() => navigate(`/agents/${agent.name}`)}
        className="p-3 cursor-pointer hover:bg-bg-hover transition-colors"
      >
        <div className="flex items-center justify-between mb-1.5">
          <div className="flex items-center gap-2">
            {/* Agent icon */}
            {AgentIcon && (
              <div className={clsx('w-7 h-7 rounded-lg flex items-center justify-center', cat?.bg)}>
                <AgentIcon size={16} className={cat?.color} />
              </div>
            )}
            <div>
              <div className="flex items-center gap-1.5">
                <div className={clsx('w-1.5 h-1.5 rounded-full', statusDot[agent.status] || 'bg-gray-500')} />
                <span className="text-sm font-semibold text-text-primary">{agent.display_name}</span>
              </div>
              <span className={clsx('text-[10px] font-medium', cat?.color)}>{agent.role}</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {agent.today_grade && (
              <span className={clsx('text-lg font-bold', gradeColors[agent.today_grade] || 'text-text-muted')}>
                {agent.today_grade}
              </span>
            )}
            <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border', cat?.bg, cat?.color, cat?.border)}>
              {agent.category}
            </span>
          </div>
        </div>

        {/* Intro — the agent's self-description */}
        {agent.intro && (
          <p className="text-[11px] text-text-secondary leading-relaxed mt-1 italic">
            "{agent.intro}"
          </p>
        )}
      </div>

      {/* Stats row */}
      <div className="px-3 pb-1.5 flex items-center justify-between text-[10px] text-text-muted">
        <span>{agent.run_count} runs</span>
        <span>{agent.last_duration_ms != null ? `${agent.last_duration_ms}ms` : '--'}</span>
        <span>{timeAgo(agent.last_run_at)}</span>
        <button
          onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}
          className="flex items-center gap-0.5 text-accent-blue hover:underline"
        >
          {expanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
          {expanded ? 'Less' : 'More'}
        </button>
      </div>

      {/* Error indicator */}
      {agent.last_error && (
        <div className="px-3 pb-1.5 text-[10px] text-red-400 truncate">
          {agent.last_error}
        </div>
      )}

      {/* Expandable details */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2 border-t border-border-secondary/50 pt-2">
          {/* Responsibilities */}
          <div>
            <div className="text-[9px] text-text-muted uppercase tracking-wider mb-0.5 font-semibold">Responsibilities</div>
            <div className="flex flex-wrap gap-1">
              {agent.responsibilities.map((r) => (
                <span key={r} className={clsx('text-[9px] px-1 py-0.5 rounded', cat?.bg, cat?.color)}>{r}</span>
              ))}
            </div>
          </div>

          {/* Datasources */}
          {agent.datasources && agent.datasources.length > 0 && (
            <div>
              <div className="text-[9px] text-text-muted uppercase tracking-wider mb-0.5 font-semibold flex items-center gap-1">
                <Database size={8} /> Data Sources
              </div>
              <div className="flex flex-wrap gap-1">
                {agent.datasources.map((d) => (
                  <span key={d} className="text-[9px] px-1 py-0.5 rounded bg-bg-tertiary text-text-secondary">{d}</span>
                ))}
              </div>
            </div>
          )}

          {/* Boundaries */}
          {agent.boundaries && agent.boundaries.length > 0 && (
            <div>
              <div className="text-[9px] text-text-muted uppercase tracking-wider mb-0.5 font-semibold flex items-center gap-1">
                <ShieldOff size={8} /> Boundaries
              </div>
              <ul className="text-[9px] text-text-muted space-y-0.5">
                {agent.boundaries.map((b) => (
                  <li key={b} className="flex items-start gap-1">
                    <span className="text-red-400 mt-0.5">x</span>
                    <span>{b}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Capabilities */}
          <div>
            <div className="text-[9px] text-text-muted uppercase tracking-wider mb-0.5 font-semibold">Capabilities</div>
            <div className="flex flex-wrap gap-1">
              {agent.capabilities_implemented.map((cap) => (
                <span key={cap} className="text-[9px] px-1 py-0.5 rounded bg-green-500/10 text-green-400">{cap}</span>
              ))}
              {agent.capabilities_planned.map((cap) => (
                <span key={cap} className="text-[9px] px-1 py-0.5 rounded bg-gray-500/10 text-text-muted">{cap}</span>
              ))}
            </div>
          </div>

          {/* Runs during */}
          <div className="text-[9px] text-text-muted">
            <span className="font-semibold">Active during:</span>{' '}
            {agent.runs_during.join(', ')}
          </div>
        </div>
      )}
    </div>
  )
}
