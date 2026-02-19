import { useState, useMemo } from 'react'
import { useWorkflowStatus } from '../hooks/useWorkflowStatus'
import { useHaltWorkflow, useResumeWorkflow, useAgentTimeline } from '../hooks/useWorkflow'
import { Spinner } from '../components/common/Spinner'
import { showToast } from '../components/common/Toast'
import { clsx } from 'clsx'
import { Pause, Play, AlertTriangle } from 'lucide-react'

const STATES = [
  'idle', 'boot', 'macro_check', 'screening', 'recommendation_review',
  'execution', 'monitoring', 'trade_management', 'trade_review', 'reporting',
]

const stateColors: Record<string, string> = {
  idle: 'border-zinc-600 bg-zinc-800/40',
  boot: 'border-yellow-600 bg-yellow-900/30',
  macro_check: 'border-cyan-600 bg-cyan-900/30',
  screening: 'border-blue-600 bg-blue-900/30',
  recommendation_review: 'border-orange-600 bg-orange-900/30',
  execution: 'border-green-600 bg-green-900/30',
  monitoring: 'border-blue-600 bg-blue-900/30',
  trade_management: 'border-purple-600 bg-purple-900/30',
  trade_review: 'border-orange-600 bg-orange-900/30',
  reporting: 'border-cyan-600 bg-cyan-900/30',
}

const stateActiveColors: Record<string, string> = {
  idle: 'border-zinc-400 bg-zinc-700 ring-2 ring-zinc-500/50',
  boot: 'border-yellow-400 bg-yellow-800 ring-2 ring-yellow-500/50',
  macro_check: 'border-cyan-400 bg-cyan-800 ring-2 ring-cyan-500/50',
  screening: 'border-blue-400 bg-blue-800 ring-2 ring-blue-500/50',
  recommendation_review: 'border-orange-400 bg-orange-800 ring-2 ring-orange-500/50',
  execution: 'border-green-400 bg-green-800 ring-2 ring-green-500/50',
  monitoring: 'border-blue-400 bg-blue-800 ring-2 ring-blue-500/50',
  trade_management: 'border-purple-400 bg-purple-800 ring-2 ring-purple-500/50',
  trade_review: 'border-orange-400 bg-orange-800 ring-2 ring-orange-500/50',
  reporting: 'border-cyan-400 bg-cyan-800 ring-2 ring-cyan-500/50',
}

export function WorkflowPage() {
  const { data: status, isLoading } = useWorkflowStatus()
  const { data: timeline } = useAgentTimeline(3)
  const haltMut = useHaltWorkflow()
  const resumeMut = useResumeWorkflow()
  const [showResumeModal, setShowResumeModal] = useState(false)
  const [rationale, setRationale] = useState('')

  const handleHalt = () => {
    if (!confirm('Are you sure you want to halt the workflow?')) return
    haltMut.mutate(undefined, {
      onSuccess: () => showToast('success', 'Workflow halted'),
      onError: () => showToast('error', 'Failed to halt workflow'),
    })
  }

  const handleResume = () => {
    resumeMut.mutate(rationale, {
      onSuccess: () => {
        showToast('success', 'Workflow resumed')
        setShowResumeModal(false)
        setRationale('')
      },
      onError: () => showToast('error', 'Failed to resume workflow'),
    })
  }

  // Flatten timeline for display
  const timelineEntries = useMemo(() => {
    if (!timeline) return []
    const entries: { cycle: string; agent: string; status: string; state: string; duration: number; error: string | null }[] = []
    for (const [cycle, runs] of Object.entries(timeline)) {
      for (const run of (runs as Array<{ agent_name: string; status: string; workflow_state: string | null; duration_ms: number | null; error_message: string | null }>)) {
        entries.push({
          cycle,
          agent: run.agent_name,
          status: run.status,
          state: run.workflow_state || '',
          duration: run.duration_ms || 0,
          error: run.error_message,
        })
      }
    }
    return entries.slice(0, 50)
  }, [timeline])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    )
  }

  const currentState = status?.current_state || 'idle'

  return (
    <div className="space-y-3">
      {/* State machine pipeline */}
      <div className="card">
        <div className="card-header">
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Workflow State Machine
          </h2>
        </div>
        <div className="card-body">
          <div className="flex items-center gap-1 overflow-x-auto pb-2">
            {STATES.map((state, i) => {
              const isActive = state === currentState
              const isPast = STATES.indexOf(currentState) > i
              return (
                <div key={state} className="flex items-center">
                  <div
                    className={clsx(
                      'px-2.5 py-1.5 rounded border text-2xs font-mono font-semibold whitespace-nowrap transition-all',
                      isActive
                        ? stateActiveColors[state]
                        : isPast
                          ? 'border-border-secondary bg-bg-tertiary text-text-muted'
                          : stateColors[state],
                      isActive ? 'text-white animate-pulse' : isPast ? 'text-text-muted' : 'text-text-secondary',
                    )}
                  >
                    {state.replace(/_/g, ' ').toUpperCase()}
                  </div>
                  {i < STATES.length - 1 && (
                    <div className={clsx(
                      'w-4 h-0.5 mx-0.5',
                      isPast ? 'bg-accent-blue' : 'bg-border-secondary',
                    )} />
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Controls + Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Controls */}
        <div className="card">
          <div className="card-header">
            <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
              Controls
            </h2>
          </div>
          <div className="card-body space-y-3">
            <div className="flex items-center gap-3">
              <button
                onClick={handleHalt}
                disabled={status?.halted || haltMut.isPending}
                className="flex items-center gap-1.5 px-4 py-2 rounded text-xs font-semibold bg-red-900/40 text-red-400 border border-red-800 hover:bg-red-900/60 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Pause size={14} /> HALT
              </button>
              <button
                onClick={() => setShowResumeModal(true)}
                disabled={!status?.halted}
                className="flex items-center gap-1.5 px-4 py-2 rounded text-xs font-semibold bg-green-900/40 text-green-400 border border-green-800 hover:bg-green-900/60 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Play size={14} /> RESUME
              </button>
            </div>

            {status?.halted && status?.halt_reason && (
              <div className="flex items-start gap-2 text-xs text-accent-red bg-red-900/20 rounded p-2">
                <AlertTriangle size={14} className="shrink-0 mt-0.5" />
                <span>{status.halt_reason}</span>
              </div>
            )}
          </div>
        </div>

        {/* Stats */}
        <div className="card">
          <div className="card-header">
            <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
              Cycle Stats
            </h2>
          </div>
          <div className="card-body">
            <div className="grid grid-cols-2 gap-3">
              <Stat label="Cycle #" value={status?.cycle_count?.toString() ?? '0'} />
              <Stat label="Trades Today" value={status?.trades_today?.toString() ?? '0'} />
              <Stat label="Pending Recs" value={status?.pending_recommendations?.toString() ?? '0'} />
              <Stat
                label="Halted"
                value={status?.halted ? 'YES' : 'NO'}
                color={status?.halted ? 'text-accent-red' : 'text-accent-green'}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Agent timeline */}
      <div className="card">
        <div className="card-header">
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Agent Timeline (Last 3 Cycles)
          </h2>
        </div>
        <div className="card-body">
          {timelineEntries.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-text-muted text-left border-b border-border-secondary">
                    <th className="py-1.5 pr-3">Cycle</th>
                    <th className="py-1.5 pr-3">Agent</th>
                    <th className="py-1.5 pr-3">State</th>
                    <th className="py-1.5 pr-3">Status</th>
                    <th className="py-1.5 pr-3 text-right">Duration</th>
                    <th className="py-1.5">Error</th>
                  </tr>
                </thead>
                <tbody>
                  {timelineEntries.map((e, i) => (
                    <tr key={i} className="text-text-secondary border-b border-border-secondary/50">
                      <td className="py-1 pr-3 font-mono text-text-muted">{e.cycle}</td>
                      <td className="py-1 pr-3 font-medium">{e.agent}</td>
                      <td className="py-1 pr-3 text-text-muted">{e.state.replace(/_/g, ' ')}</td>
                      <td className="py-1 pr-3">
                        <span className={clsx(
                          'px-1.5 py-0.5 rounded text-2xs font-semibold border',
                          e.status === 'success' ? 'bg-green-900/30 text-green-400 border-green-800' :
                          e.status === 'error' ? 'bg-red-900/30 text-red-400 border-red-800' :
                          'bg-zinc-800/50 text-zinc-400 border-zinc-700',
                        )}>
                          {e.status.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-1 pr-3 text-right font-mono">{e.duration > 0 ? `${e.duration}ms` : '--'}</td>
                      <td className="py-1 text-accent-red truncate max-w-[200px]">{e.error || ''}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-text-muted py-4 text-center">No timeline data. Run workflow cycles to see agent activity.</p>
          )}
        </div>
      </div>

      {/* Resume modal */}
      {showResumeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setShowResumeModal(false)}>
          <div className="bg-bg-primary border border-border-primary rounded-lg shadow-xl w-full max-w-md p-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-sm font-semibold text-text-primary mb-3">Resume Workflow</h3>
            <div className="mb-3">
              <label className="text-2xs text-text-muted block mb-1">Rationale (required)</label>
              <textarea
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                rows={3}
                placeholder="Why are you resuming the workflow?"
                className="w-full px-2 py-1.5 rounded text-xs bg-bg-secondary border border-border-primary text-text-primary focus:border-accent-blue focus:outline-none resize-none"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleResume}
                disabled={!rationale.trim() || resumeMut.isPending}
                className="px-3 py-1.5 rounded text-xs font-medium bg-green-700 text-white hover:bg-green-600 disabled:opacity-40"
              >
                {resumeMut.isPending ? 'Resuming...' : 'Resume'}
              </button>
              <button
                onClick={() => setShowResumeModal(false)}
                className="px-3 py-1.5 rounded text-xs text-text-muted hover:text-text-primary"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div className="text-2xs text-text-muted uppercase">{label}</div>
      <span className={clsx('text-lg font-mono font-semibold', color || 'text-text-primary')}>
        {value}
      </span>
    </div>
  )
}
