import { useParams, Link } from 'react-router-dom'
import { useState } from 'react'
import { clsx } from 'clsx'
import { ChevronLeft, ChevronDown, ChevronRight, Database, ShieldOff } from 'lucide-react'
import { useAgentDetail } from '../hooks/useAgents'
import { AgentRunTimeline } from '../components/agents/AgentRunTimeline'
import { ObjectiveGradeChart } from '../components/agents/ObjectiveGradeChart'
import { AGENT_ICONS, CATEGORY_CONFIG, type AgentCategory } from '../config/agentConfig'
import type { AgentRun } from '../api/types'

// ---------------------------------------------------------------------------
// Expandable JSON viewer
// ---------------------------------------------------------------------------

function JsonViewer({ data, label }: { data: Record<string, unknown>; label: string }) {
  const [open, setOpen] = useState(false)
  const keys = Object.keys(data)
  if (keys.length === 0) return null

  return (
    <div className="border border-border-primary rounded">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-2 text-xs text-text-secondary hover:text-text-primary w-full text-left"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <span>{label}</span>
        <span className="text-text-muted ml-auto">{keys.length} keys</span>
      </button>
      {open && (
        <pre className="px-3 pb-2 text-[10px] text-text-secondary font-mono overflow-x-auto max-h-48 overflow-y-auto">
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Run detail row (expandable)
// ---------------------------------------------------------------------------

function RunRow({ run }: { run: AgentRun }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border-b border-border-secondary/50">
      <div
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-3 px-3 py-2 text-xs cursor-pointer hover:bg-bg-hover"
      >
        <span className="font-mono text-text-muted w-16 shrink-0">
          {run.cycle_id != null ? `#${run.cycle_id}` : '--'}
        </span>
        <span className="text-text-secondary w-24 shrink-0">{run.workflow_state || '--'}</span>
        <span
          className={clsx(
            'w-16 shrink-0',
            run.status === 'completed' ? 'text-green-400' :
            run.status === 'error' ? 'text-red-400' :
            'text-text-secondary',
          )}
        >
          {run.status}
        </span>
        <span className="font-mono text-text-muted w-14 text-right shrink-0">
          {run.duration_ms != null ? `${run.duration_ms}ms` : '--'}
        </span>
        <span className="text-text-secondary truncate flex-1">
          {run.messages[0] || ''}
        </span>
        <span className="text-text-muted font-mono w-[72px] shrink-0 text-right">
          {new Date(run.started_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}
        </span>
        {expanded ? <ChevronDown size={12} className="text-text-muted" /> : <ChevronRight size={12} className="text-text-muted" />}
      </div>
      {expanded && (
        <div className="px-3 pb-3 space-y-2 bg-bg-tertiary/30">
          {/* Messages */}
          {run.messages.length > 0 && (
            <div className="text-[10px] text-text-secondary space-y-0.5">
              {run.messages.map((msg, i) => (
                <div key={i} className="font-mono">{msg}</div>
              ))}
            </div>
          )}
          {/* Data and Metrics */}
          <div className="flex gap-2">
            {Object.keys(run.data).length > 0 && (
              <div className="flex-1">
                <JsonViewer data={run.data} label="Data" />
              </div>
            )}
            {Object.keys(run.metrics).length > 0 && (
              <div className="flex-1">
                <JsonViewer data={run.metrics} label="Metrics" />
              </div>
            )}
          </div>
          {/* Error */}
          {run.error_message && (
            <div className="text-[10px] text-red-400 font-mono">{run.error_message}</div>
          )}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function AgentDetailPage() {
  const { name } = useParams<{ name: string }>()
  const { data: agent, isLoading, error } = useAgentDetail(name || '')

  if (isLoading) {
    return <div className="p-4 text-xs text-text-muted">Loading agent...</div>
  }

  if (error || !agent) {
    return (
      <div className="p-4">
        <Link to="/agents" className="flex items-center gap-1 text-xs text-accent-blue mb-4 hover:underline">
          <ChevronLeft size={14} /> Back to Agents
        </Link>
        <div className="text-xs text-red-400">Agent not found</div>
      </div>
    )
  }

  const todayObj = agent.objectives.find((o) => o.date === new Date().toISOString().slice(0, 10))

  return (
    <div className="p-4 space-y-4">
      {/* Back link */}
      <Link to="/agents" className="flex items-center gap-1 text-xs text-accent-blue hover:underline">
        <ChevronLeft size={14} /> Back to Agents
      </Link>

      {/* Header */}
      {(() => {
        const cat = CATEGORY_CONFIG[agent.category as AgentCategory]
        const AgentIcon = AGENT_ICONS[agent.name]
        return (
          <div className={clsx('bg-bg-secondary rounded-lg border overflow-hidden', cat?.border || 'border-border-primary')}>
            {/* Colored top accent */}
            <div className={clsx('h-1', cat?.dot || 'bg-gray-500')} />
            <div className="p-4">
              <div className="flex items-center gap-3 mb-2">
                {AgentIcon && (
                  <div className={clsx('w-10 h-10 rounded-lg flex items-center justify-center', cat?.bg)}>
                    <AgentIcon size={22} className={cat?.color} />
                  </div>
                )}
                <div>
                  <div className="flex items-center gap-2">
                    <h1 className="text-lg font-bold text-text-primary">{agent.display_name}</h1>
                    <span className={clsx('text-[10px] px-1.5 py-0.5 rounded border', cat?.bg, cat?.color, cat?.border)}>
                      {agent.category}
                    </span>
                  </div>
                  <span className={clsx('text-xs font-medium', cat?.color)}>{agent.role}</span>
                </div>
              </div>

              {/* Intro — self-description */}
              {agent.intro && (
                <p className="text-xs text-text-secondary leading-relaxed mt-2 mb-3 italic border-l-2 pl-3" style={{ borderColor: 'var(--border-secondary)' }}>
                  "{agent.intro}"
                </p>
              )}

              <p className="text-xs text-text-secondary mb-3">{agent.description}</p>

              {/* Responsibilities */}
              <div className="mb-3">
                <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1 font-semibold">Responsibilities</div>
                <div className="flex flex-wrap gap-1">
                  {agent.responsibilities.map((r) => (
                    <span key={r} className={clsx('text-[10px] px-1.5 py-0.5 rounded', cat?.bg, cat?.color)}>
                      {r}
                    </span>
                  ))}
                </div>
              </div>

              {/* Datasources + Boundaries side by side */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-3">
                {agent.datasources && agent.datasources.length > 0 && (
                  <div>
                    <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1 font-semibold flex items-center gap-1">
                      <Database size={10} /> Data Sources
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {agent.datasources.map((d) => (
                        <span key={d} className="text-[10px] px-1.5 py-0.5 rounded bg-bg-tertiary text-text-secondary">{d}</span>
                      ))}
                    </div>
                  </div>
                )}
                {agent.boundaries && agent.boundaries.length > 0 && (
                  <div>
                    <div className="text-[10px] text-text-muted uppercase tracking-wider mb-1 font-semibold flex items-center gap-1">
                      <ShieldOff size={10} /> Boundaries
                    </div>
                    <ul className="text-[10px] text-text-muted space-y-0.5">
                      {agent.boundaries.map((b) => (
                        <li key={b} className="flex items-start gap-1">
                          <span className="text-red-400 mt-0.5 text-[8px]">&#x2717;</span>
                          <span>{b}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              {/* Stats */}
              <div className="flex items-center gap-6 text-xs">
                <div>
                  <span className="text-text-muted">Total Runs: </span>
                  <span className="font-mono text-text-primary">{agent.stats.total_runs}</span>
                </div>
                <div>
                  <span className="text-text-muted">Avg Duration: </span>
                  <span className="font-mono text-text-primary">{Math.round(agent.stats.avg_duration_ms)}ms</span>
                </div>
                <div>
                  <span className="text-text-muted">Errors: </span>
                  <span className={clsx('font-mono', agent.stats.error_count > 0 ? 'text-red-400' : 'text-text-primary')}>
                    {agent.stats.error_count}
                  </span>
                </div>
                <div>
                  <span className="text-text-muted">Runs During: </span>
                  <span className="text-text-secondary">{agent.runs_during.join(', ')}</span>
                </div>
              </div>

              {/* Capabilities */}
              <div className="mt-3 flex flex-wrap gap-1">
                {agent.capabilities_implemented.map((cap) => (
                  <span key={cap} className="text-[9px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-400">
                    {cap}
                  </span>
                ))}
                {agent.capabilities_planned.map((cap) => (
                  <span key={cap} className="text-[9px] px-1.5 py-0.5 rounded bg-gray-500/10 text-text-muted">
                    {cap} (planned)
                  </span>
                ))}
              </div>
            </div>
          </div>
        )
      })()}

      {/* Today's Objective */}
      {todayObj && (
        <div className="bg-bg-secondary rounded-lg border border-border-primary p-4">
          <h3 className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-2">
            Today's Objective
          </h3>
          <div className="flex items-start gap-4">
            <div className="flex-1">
              <p className="text-xs text-text-primary">{todayObj.objective}</p>
              {todayObj.target_metric && (
                <p className="text-[10px] text-text-muted mt-1">
                  Target: {todayObj.target_metric} = {todayObj.target_value}
                  {todayObj.actual_value != null && ` | Actual: ${todayObj.actual_value}`}
                </p>
              )}
              {todayObj.gap_analysis && (
                <p className="text-[10px] text-amber-400 mt-1">{todayObj.gap_analysis}</p>
              )}
            </div>
            {todayObj.grade && (
              <div
                className={clsx(
                  'text-2xl font-bold',
                  todayObj.grade === 'A' ? 'text-green-400' :
                  todayObj.grade === 'B' ? 'text-blue-400' :
                  todayObj.grade === 'C' ? 'text-amber-400' :
                  todayObj.grade === 'F' ? 'text-red-400' :
                  'text-text-muted',
                )}
              >
                {todayObj.grade}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Grade History Chart */}
      {agent.objectives.length > 0 && (
        <div className="bg-bg-secondary rounded-lg border border-border-primary p-4">
          <h3 className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-2">
            Grade History (30 days)
          </h3>
          <ObjectiveGradeChart objectives={agent.objectives} />
        </div>
      )}

      {/* Run History */}
      <div className="bg-bg-secondary rounded-lg border border-border-primary">
        <div className="px-4 py-3 border-b border-border-secondary">
          <h3 className="text-xs font-medium text-text-secondary uppercase tracking-wider">
            Run History (Recent 20)
          </h3>
        </div>
        {/* Table header */}
        <div className="flex items-center gap-3 px-3 py-1.5 text-[10px] text-text-muted border-b border-border-secondary bg-bg-tertiary/30">
          <span className="w-16 shrink-0">Cycle</span>
          <span className="w-24 shrink-0">State</span>
          <span className="w-16 shrink-0">Status</span>
          <span className="w-14 text-right shrink-0">Duration</span>
          <span className="flex-1">Message</span>
          <span className="w-[72px] text-right shrink-0">Time</span>
          <span className="w-3" />
        </div>
        {agent.recent_runs.length === 0 ? (
          <div className="text-xs text-text-muted py-4 text-center">No runs recorded</div>
        ) : (
          agent.recent_runs.map((run) => <RunRow key={run.id} run={run} />)
        )}
      </div>
    </div>
  )
}
