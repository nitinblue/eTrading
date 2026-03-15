import { useState, useMemo, useEffect } from 'react'
import { clsx } from 'clsx'
import { Beaker, BookOpen, Brain, AlertCircle, Clock, Award, Activity, Pause, Play, AlertTriangle, BarChart3, Globe } from 'lucide-react'
import { useAgents, useAgentSummary, useMLStatus, useAgentTimeline } from '../hooks/useAgents'
import { useClosedTrades, useRecentTrades, type RecentTrade } from '../hooks/useRecentTrades'
import { useWorkflowStatus } from '../hooks/useWorkflowStatus'
import { useHaltWorkflow, useResumeWorkflow } from '../hooks/useWorkflow'
import { AgentCard } from '../components/agents/AgentCard'
import { Spinner } from '../components/common/Spinner'
import { showToast } from '../components/common/Toast'
import { CATEGORY_CONFIG, AGENT_ICONS, type AgentCategory } from '../config/agentConfig'
import type { AgentInfo, AgentTimelineCycle } from '../api/types'

type TabId = 'workflow' | 'active' | 'research' | 'knowledge' | 'ml'

const CategoryIcon = CATEGORY_CONFIG.safety.icon // Shield — used for tab

const tabs: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: 'workflow', label: 'Workflow', icon: Activity },
  { id: 'active', label: 'Active Agents', icon: CategoryIcon },
  { id: 'research', label: 'Quant Research', icon: Beaker },
  { id: 'knowledge', label: 'Knowledge Base', icon: BookOpen },
  { id: 'ml', label: 'ML/RL Status', icon: Brain },
]

const categoryOrder = ['safety', 'perception', 'analysis', 'execution', 'learning'] as const

// ---------------------------------------------------------------------------
// Workflow Tab — state pipeline, KPIs, halt/resume, agent cards, timeline, trades
// ---------------------------------------------------------------------------

const STATES = ['idle', 'booting', 'monitoring']

const STATE_CLR: Record<string, { base: string; active: string }> = {
  idle:       { base: 'border-zinc-700 bg-zinc-800/40 text-zinc-400', active: 'border-zinc-400 bg-zinc-700 text-white ring-2 ring-zinc-500/50 animate-pulse' },
  booting:    { base: 'border-yellow-700 bg-yellow-900/30 text-yellow-500', active: 'border-yellow-400 bg-yellow-800 text-white ring-2 ring-yellow-500/50 animate-pulse' },
  monitoring: { base: 'border-blue-700 bg-blue-900/30 text-blue-400', active: 'border-blue-400 bg-blue-800 text-white ring-2 ring-blue-500/50 animate-pulse' },
}

function WorkflowKPI({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="text-center">
      <div className={clsx('text-sm font-mono font-bold', color || 'text-text-primary')}>{value}</div>
      <div className="text-[9px] text-text-muted uppercase tracking-wider">{label}</div>
    </div>
  )
}

const AGENT_CLR: Record<string, string> = {
  scout: 'text-blue-400 border-blue-800',
  steward: 'text-purple-400 border-purple-800',
  sentinel: 'text-red-400 border-red-800',
  maverick: 'text-green-400 border-green-800',
  atlas: 'text-zinc-400 border-zinc-700',
}

function WorkflowAgentStatusCard({ agent }: { agent: AgentInfo }) {
  const c = AGENT_CLR[agent.name] || 'text-text-muted border-border-secondary'
  const lastRun = agent.last_run_at ? new Date(agent.last_run_at) : null
  const timeStr = lastRun
    ? lastRun.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
    : '--'
  const durStr = agent.last_duration_ms != null ? `${agent.last_duration_ms}ms` : '--'

  return (
    <div className={clsx('rounded border px-2 py-1.5 bg-bg-secondary', c.split(' ')[1])}>
      <div className="flex items-center justify-between mb-1">
        <span className={clsx('text-[11px] font-bold uppercase', c.split(' ')[0])}>{agent.display_name}</span>
        <span className={clsx(
          'text-[9px] px-1 py-[1px] rounded font-semibold',
          agent.status === 'success' || agent.status === 'completed' ? 'bg-green-900/40 text-green-400' :
          agent.status === 'error' ? 'bg-red-900/40 text-red-400' :
          'bg-zinc-800 text-zinc-400',
        )}>
          {(agent.status || 'idle').toUpperCase()}
        </span>
      </div>
      <div className="flex items-center gap-3 text-[10px] text-text-muted">
        <span>Last: {timeStr}</span>
        <span>{durStr}</span>
        <span>Runs: {agent.run_count}</span>
      </div>
      {agent.last_error && (
        <div className="text-[10px] text-red-400 mt-1 truncate" title={agent.last_error}>
          {agent.last_error}
        </div>
      )}
    </div>
  )
}

function WorkflowTab() {
  const { data: status, isLoading, isError, error } = useWorkflowStatus()
  const { data: timelineData } = useAgentTimeline(5)
  const { data: agents } = useAgents()
  const { data: tradesData } = useRecentTrades(30)
  const haltMut = useHaltWorkflow()
  const resumeMut = useResumeWorkflow()
  const [showResumeModal, setShowResumeModal] = useState(false)
  const [rationale, setRationale] = useState('')

  const handleHalt = () => {
    if (!confirm('Halt the workflow?')) return
    haltMut.mutate(undefined, {
      onSuccess: () => showToast('success', 'Workflow halted'),
      onError: () => showToast('error', 'Failed to halt'),
    })
  }

  const handleResume = () => {
    resumeMut.mutate(rationale, {
      onSuccess: () => {
        showToast('success', 'Workflow resumed')
        setShowResumeModal(false)
        setRationale('')
      },
      onError: () => showToast('error', 'Failed to resume'),
    })
  }

  // Flatten timeline
  const timelineEntries = useMemo(() => {
    if (!timelineData?.cycles || typeof timelineData.cycles !== 'object') return []
    try {
      const entries: { cycle: string; agent: string; status: string; state: string; duration: number; error: string | null; started_at: string }[] = []
      for (const [cycle, runs] of Object.entries(timelineData.cycles)) {
        if (!Array.isArray(runs)) continue
        for (const run of runs) {
          entries.push({
            cycle,
            agent: run.agent_name ?? '?',
            status: run.status ?? 'unknown',
            state: run.workflow_state || '',
            duration: run.duration_ms || 0,
            error: run.error_message,
            started_at: run.started_at || '',
          })
        }
      }
      // Sort newest first
      entries.sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())
      return entries.slice(0, 50)
    } catch {
      return []
    }
  }, [timelineData])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    )
  }

  if (isError) {
    const msg = (error as Error)?.message || 'Unknown error'
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3">
        <AlertTriangle size={28} className="text-accent-yellow" />
        <div className="text-sm text-text-secondary">Workflow backend not reachable</div>
        <div className="text-2xs text-text-muted">{msg.includes('timeout') ? 'Backend timeout' : 'Backend offline — start with run_workflow'}</div>
      </div>
    )
  }

  const currentState = status?.current_state || 'idle'
  const sortedAgents = ['sentinel', 'scout', 'steward', 'maverick', 'atlas']
  const agentList = sortedAgents
    .map(name => agents?.find(a => a.name === name))
    .filter(Boolean) as AgentInfo[]

  return (
    <div className="space-y-2">
      {/* Row 1: Status strip — state pipeline + KPIs + controls */}
      <div className="card">
        <div className="card-body py-2 px-3">
          <div className="flex items-center gap-4 flex-wrap">
            {/* State pipeline */}
            <div className="flex items-center gap-1">
              {STATES.map((state, i) => {
                const isActive = state === currentState || (currentState === 'boot' && state === 'booting')
                const clrs = STATE_CLR[state] || STATE_CLR.idle
                return (
                  <div key={state} className="flex items-center">
                    <div className={clsx('px-2 py-1 rounded border text-[10px] font-mono font-bold', isActive ? clrs.active : clrs.base)}>
                      {state.toUpperCase()}
                    </div>
                    {i < STATES.length - 1 && <div className="w-3 h-0.5 bg-border-secondary mx-0.5" />}
                  </div>
                )
              })}
            </div>

            <div className="h-5 w-px bg-border-secondary" />

            {/* KPIs */}
            <WorkflowKPI label="Cycle" value={`#${status?.cycle_count ?? 0}`} />
            <WorkflowKPI label="Trades Today" value={String(status?.trades_today ?? 0)} color={status?.trades_today ? 'text-accent-green' : undefined} />
            <WorkflowKPI label="Pending" value={String(status?.pending_recommendations ?? 0)} color={status?.pending_recommendations ? 'text-accent-yellow' : undefined} />

            <div className="h-5 w-px bg-border-secondary" />

            {/* Controls */}
            <div className="flex items-center gap-1.5">
              {status?.halted ? (
                <>
                  <span className="text-[10px] text-red-400 font-bold uppercase">HALTED</span>
                  <button
                    onClick={() => setShowResumeModal(true)}
                    className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-semibold bg-green-900/40 text-green-400 border border-green-800 hover:bg-green-900/60"
                  >
                    <Play size={10} /> Resume
                  </button>
                </>
              ) : (
                <button
                  onClick={handleHalt}
                  disabled={haltMut.isPending}
                  className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-semibold bg-red-900/30 text-red-400 border border-red-800 hover:bg-red-900/50 disabled:opacity-40"
                >
                  <Pause size={10} /> Halt
                </button>
              )}
            </div>

            {status?.halted && status?.halt_reason && (
              <>
                <div className="h-5 w-px bg-border-secondary" />
                <div className="flex items-center gap-1 text-[10px] text-red-400">
                  <AlertTriangle size={11} />
                  <span className="truncate max-w-[200px]">{status.halt_reason}</span>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Row 2: Agent status cards */}
      <div className="grid grid-cols-5 gap-2">
        {agentList.map(agent => (
          <WorkflowAgentStatusCard key={agent.name} agent={agent} />
        ))}
        {agentList.length === 0 && (
          <div className="col-span-5 text-center text-[10px] text-text-muted py-2">
            No agent data — run a workflow cycle first
          </div>
        )}
      </div>

      {/* Row 3: Two columns — Agent Timeline | Recent Trades */}
      <div className="grid grid-cols-[3fr_2fr] gap-2 min-h-0" style={{ height: 'calc(100vh - 280px)' }}>
        {/* Left: Agent Timeline */}
        <div className="card overflow-hidden flex flex-col">
          <div className="card-header py-1.5 px-2 flex-shrink-0">
            <h2 className="text-[10px] font-bold text-text-muted uppercase tracking-wider">
              Agent Timeline (Last 5 Cycles)
            </h2>
          </div>
          <div className="overflow-y-auto flex-1">
            {timelineEntries.length > 0 ? (
              <table className="w-full text-[11px]">
                <thead className="sticky top-0 bg-bg-secondary">
                  <tr className="text-text-muted text-left border-b border-border-secondary text-[9px] uppercase tracking-wider">
                    <th className="py-1 px-2">Time</th>
                    <th className="py-1 px-2">Agent</th>
                    <th className="py-1 px-2">State</th>
                    <th className="py-1 px-2">Status</th>
                    <th className="py-1 px-2 text-right">Duration</th>
                    <th className="py-1 px-2 text-right">Cycle</th>
                    <th className="py-1 px-2">Error</th>
                  </tr>
                </thead>
                <tbody>
                  {timelineEntries.map((e, i) => {
                    const t = e.started_at ? new Date(e.started_at) : null
                    const timeStr = t
                      ? t.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
                      : '--'
                    return (
                      <tr key={i} className="border-b border-border-secondary/30 hover:bg-bg-hover/50">
                        <td className="py-[3px] px-2 font-mono text-text-muted">{timeStr}</td>
                        <td className="py-[3px] px-2">
                          <span className={clsx('font-semibold', AGENT_CLR[e.agent]?.split(' ')[0] || 'text-text-primary')}>
                            {e.agent}
                          </span>
                        </td>
                        <td className="py-[3px] px-2 text-text-muted">{e.state.replace(/_/g, ' ')}</td>
                        <td className="py-[3px] px-2">
                          <span className={clsx(
                            'px-1 py-[1px] rounded text-[9px] font-semibold',
                            e.status === 'success' || e.status === 'completed' ? 'bg-green-900/30 text-green-400' :
                            e.status === 'error' ? 'bg-red-900/30 text-red-400' :
                            'bg-zinc-800/50 text-zinc-400',
                          )}>
                            {e.status.toUpperCase()}
                          </span>
                        </td>
                        <td className="py-[3px] px-2 text-right font-mono text-text-muted">
                          {e.duration > 0 ? `${e.duration}ms` : '--'}
                        </td>
                        <td className="py-[3px] px-2 text-right font-mono text-text-muted">#{e.cycle}</td>
                        <td className="py-[3px] px-2 text-red-400 truncate max-w-[200px]" title={e.error || ''}>
                          {e.error || ''}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            ) : (
              <div className="text-[10px] text-text-muted py-6 text-center">
                No timeline data — run workflow cycles to see agent activity
              </div>
            )}
          </div>
        </div>

        {/* Right: Recent Trades */}
        <div className="card overflow-hidden flex flex-col">
          <div className="card-header py-1.5 px-2 flex-shrink-0">
            <h2 className="text-[10px] font-bold text-text-muted uppercase tracking-wider">
              Recent Trades
            </h2>
          </div>
          <div className="overflow-y-auto flex-1">
            {tradesData && tradesData.trades.length > 0 ? (
              <table className="w-full text-[11px]">
                <thead className="sticky top-0 bg-bg-secondary">
                  <tr className="text-text-muted text-left border-b border-border-secondary text-[9px] uppercase tracking-wider">
                    <th className="py-1 px-2">Time</th>
                    <th className="py-1 px-2">UDL</th>
                    <th className="py-1 px-2">Strategy</th>
                    <th className="py-1 px-2">Status</th>
                    <th className="py-1 px-2 text-right">Entry</th>
                    <th className="py-1 px-2 text-right">P&L</th>
                    <th className="py-1 px-2">Portfolio</th>
                  </tr>
                </thead>
                <tbody>
                  {tradesData.trades.map((t) => {
                    const created = t.created_at ? new Date(t.created_at) : null
                    const dateStr = created
                      ? `${(created.getMonth() + 1).toString().padStart(2, '0')}/${created.getDate().toString().padStart(2, '0')} ${created.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}`
                      : '--'
                    const pnl = t.total_pnl
                    const pnlStr = pnl != null ? `${pnl >= 0 ? '+' : ''}$${Math.abs(pnl).toFixed(0)}` : '--'
                    const statusLabel =
                      t.trade_status === 'intent' && t.trade_type === 'what_if' ? 'WHATIF' :
                      t.trade_status === 'closed' ? 'CLOSED' :
                      t.trade_status === 'executed' ? 'OPEN' :
                      t.trade_status?.toUpperCase() || '--'

                    return (
                      <tr key={t.id} className="border-b border-border-secondary/30 hover:bg-bg-hover/50">
                        <td className="py-[3px] px-2 font-mono text-text-muted whitespace-nowrap">{dateStr}</td>
                        <td className="py-[3px] px-2 font-semibold text-accent-blue">{t.underlying_symbol}</td>
                        <td className="py-[3px] px-2 text-text-secondary">{(t.strategy_type || '--').replace(/_/g, ' ')}</td>
                        <td className="py-[3px] px-2">
                          <span className={clsx(
                            'px-1 py-[1px] rounded text-[9px] font-semibold',
                            statusLabel === 'OPEN' ? 'bg-green-900/30 text-green-400' :
                            statusLabel === 'CLOSED' ? 'bg-zinc-800/50 text-zinc-400' :
                            statusLabel === 'WHATIF' ? 'bg-blue-900/30 text-blue-400' :
                            'bg-amber-900/30 text-amber-400',
                          )}>
                            {statusLabel}
                          </span>
                        </td>
                        <td className="py-[3px] px-2 text-right font-mono text-text-secondary">
                          {t.entry_price != null ? `$${Number(t.entry_price).toFixed(2)}` : '--'}
                        </td>
                        <td className={clsx(
                          'py-[3px] px-2 text-right font-mono font-semibold',
                          pnl == null ? 'text-text-muted' : pnl > 0 ? 'text-green-400' : pnl < 0 ? 'text-red-400' : 'text-text-muted',
                        )}>
                          {pnlStr}
                        </td>
                        <td className="py-[3px] px-2 text-text-muted text-[10px] truncate max-w-[100px]" title={t.portfolio_name || ''}>
                          {t.portfolio_name || '--'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            ) : (
              <div className="text-[10px] text-text-muted py-6 text-center">
                No trades yet — use terminal: scan &rarr; propose &rarr; deploy
              </div>
            )}
          </div>
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

// ---------------------------------------------------------------------------
// Summary bar
// ---------------------------------------------------------------------------

function SummaryBar() {
  const { data: summary } = useAgentSummary()
  if (!summary) return null

  const gradeA = summary.grade_distribution['A'] || 0
  const total = Object.values(summary.grade_distribution).reduce((a, b) => a + b, 0)

  return (
    <div className="flex items-center gap-4 mb-4 text-xs flex-wrap">
      <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-bg-secondary border border-border-primary">
        <Activity size={12} className="text-accent-blue" />
        <span className="text-text-primary font-medium">{summary.total_agents} Active</span>
      </div>
      {summary.today_errors > 0 && (
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-red-500/10 border border-red-500/20">
          <AlertCircle size={12} className="text-red-400" />
          <span className="text-red-400 font-medium">{summary.today_errors} Errors</span>
        </div>
      )}
      <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-bg-secondary border border-border-primary">
        <Clock size={12} className="text-text-muted" />
        <span className="text-text-secondary">Avg {Math.round(summary.avg_duration_ms)}ms</span>
      </div>
      {total > 0 && (
        <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-bg-secondary border border-border-primary">
          <Award size={12} className="text-green-400" />
          <span className="text-text-secondary">{gradeA}/{total} Grade A</span>
        </div>
      )}
      <div className="flex items-center gap-1.5 px-2 py-1 rounded bg-bg-secondary border border-border-primary">
        <Activity size={12} className="text-text-muted" />
        <span className="text-text-secondary">Cycle #{summary.cycle_count} &middot; {summary.current_state}</span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Active Agents Tab
// ---------------------------------------------------------------------------

function ActiveAgentsTab() {
  const { data: agents, isLoading } = useAgents()
  const { data: timeline } = useAgentTimeline(3)

  if (isLoading) {
    return <div className="text-xs text-text-muted py-8 text-center">Loading agents...</div>
  }

  if (!agents || agents.length === 0) {
    return <div className="text-xs text-text-muted py-8 text-center">No agent data available. Run a workflow cycle first.</div>
  }

  // Group by category
  const grouped = categoryOrder.reduce((acc, cat) => {
    acc[cat] = agents.filter((a) => a.category === cat)
    return acc
  }, {} as Record<string, AgentInfo[]>)

  // Recent activity from timeline
  const recentActivity: (AgentTimelineCycle & { cycle: string })[] = []
  if (timeline?.cycles) {
    for (const [cycleId, runs] of Object.entries(timeline.cycles)) {
      for (const run of runs) {
        recentActivity.push({ ...run, cycle: cycleId })
      }
    }
  }
  recentActivity.sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())

  return (
    <div>
      {/* Agent Character Introductions */}
      <div className="mb-6 grid grid-cols-1 md:grid-cols-5 gap-3">
        {[
          { name: 'Chanakya', role: 'Scout', icon: '🔭', color: 'border-blue-800 bg-blue-950/20',
            tagline: 'The Strategist', desc: 'Scans markets using 20+ services. Ranks opportunities. Selects strategies via Thompson Sampling. Every decision backed by regime, technicals, and fundamentals.',
            metric: 'Score↔P&L correlation', ml: true },
          { name: 'Kubera', role: 'Steward', icon: '⚖️', color: 'border-purple-800 bg-purple-950/20',
            tagline: 'The Treasurer', desc: 'Guards the treasury. Tracks P&L by desk, Greek attribution, capital utilization. Decides how capital flows between desks.',
            metric: 'Portfolio Sharpe ratio', ml: true },
          { name: 'Bhishma', role: 'Sentinel', icon: '🛡️', color: 'border-red-800 bg-red-950/20',
            tagline: 'The Guardian', desc: '5 circuit breakers. 8 trading constraints. When Bhishma says halt, everything stops. Unbreakable vows protect capital.',
            metric: 'Max drawdown vs limit', ml: false },
          { name: 'Arjuna', role: 'Maverick', icon: '🎯', color: 'border-green-800 bg-green-950/20',
            tagline: 'The Archer', desc: '11 gates — no trade without conviction. POP, EV, drift check, execution quality. Books to 3 desks. Monitors health. Auto-closes.',
            metric: 'Win rate × avg P&L', ml: true },
          { name: 'Vishwakarma', role: 'Atlas', icon: '🔧', color: 'border-amber-800 bg-amber-950/20',
            tagline: 'The Architect', desc: 'Watches the watchers. Broker health, price freshness, ML model staleness, cross-desk risk, Greek attribution. Sounds the alarm.',
            metric: 'System uptime × ML freshness', ml: true },
        ].map(a => (
          <div key={a.name} className={clsx('border rounded-xl p-3', a.color)}>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-lg">{a.icon}</span>
              <div>
                <p className="text-xs font-bold text-text-primary">{a.name}</p>
                <p className="text-[9px] text-text-muted">{a.tagline}</p>
              </div>
            </div>
            <p className="text-[9px] text-text-secondary leading-relaxed mb-2">{a.desc}</p>
            <div className="flex items-center justify-between">
              <span className="text-[8px] text-text-muted">KPI: {a.metric}</span>
              {a.ml && <span className="text-[7px] px-1 py-0.5 rounded bg-purple-900/30 text-purple-400 border border-purple-800/30">ML</span>}
            </div>
          </div>
        ))}
      </div>

      <SummaryBar />

      {/* Agent cards grouped by category with headers */}
      <div className="space-y-5 mb-6">
        {categoryOrder.map((cat) => {
          const agents = grouped[cat]
          if (!agents || agents.length === 0) return null
          const catConfig = CATEGORY_CONFIG[cat as AgentCategory]
          const CatIcon = catConfig.icon
          return (
            <div key={cat}>
              {/* Category header */}
              <div className="flex items-center gap-2 mb-2">
                <div className={clsx('w-5 h-5 rounded flex items-center justify-center', catConfig.bg)}>
                  <CatIcon size={12} className={catConfig.color} />
                </div>
                <h3 className={clsx('text-xs font-bold uppercase tracking-wider', catConfig.color)}>{catConfig.label}</h3>
                <div className="flex-1 h-px bg-border-secondary" />
                <span className="text-[10px] text-text-muted">{agents.length} agent{agents.length > 1 ? 's' : ''}</span>
              </div>
              {/* Cards row */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {agents.map((agent) => (
                  <AgentCard key={agent.name} agent={agent} />
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {/* Recent Activity */}
      {recentActivity.length > 0 && (
        <div>
          <h3 className="text-xs font-medium text-text-secondary mb-2 uppercase tracking-wider">
            Recent Activity
          </h3>
          <div className="bg-bg-secondary rounded-lg border border-border-primary overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border-secondary text-text-muted">
                  <th className="text-left px-3 py-2 font-medium">Time</th>
                  <th className="text-left px-3 py-2 font-medium">Agent</th>
                  <th className="text-left px-3 py-2 font-medium">State</th>
                  <th className="text-left px-3 py-2 font-medium">Status</th>
                  <th className="text-right px-3 py-2 font-medium">Duration</th>
                  <th className="text-left px-3 py-2 font-medium">Cycle</th>
                </tr>
              </thead>
              <tbody>
                {recentActivity.slice(0, 30).map((run, i) => {
                  const RunIcon = AGENT_ICONS[run.agent_name]
                  return (
                    <tr key={i} className="border-b border-border-secondary/50 hover:bg-bg-hover">
                      <td className="px-3 py-1.5 font-mono text-text-muted">
                        {new Date(run.started_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
                      </td>
                      <td className="px-3 py-1.5 text-text-primary">
                        <div className="flex items-center gap-1.5">
                          {RunIcon && <RunIcon size={12} className="text-text-muted" />}
                          {run.agent_name}
                        </div>
                      </td>
                      <td className="px-3 py-1.5 text-text-secondary">{run.workflow_state || '--'}</td>
                      <td className="px-3 py-1.5">
                        <span
                          className={clsx(
                            run.status === 'completed' ? 'text-green-400' :
                            run.status === 'error' ? 'text-red-400' :
                            'text-text-secondary',
                          )}
                        >
                          {run.status}
                        </span>
                      </td>
                      <td className="px-3 py-1.5 text-right font-mono text-text-muted">
                        {run.duration_ms != null ? `${run.duration_ms}ms` : '--'}
                      </td>
                      <td className="px-3 py-1.5 font-mono text-text-muted">#{run.cycle}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Placeholder tabs
// ---------------------------------------------------------------------------

function ComingSoonTab({ title, description, icon: Icon }: { title: string; description: string; icon: React.ElementType }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-16 h-16 rounded-full bg-bg-secondary border border-border-primary flex items-center justify-center mb-4">
        <Icon size={28} className="text-text-muted" />
      </div>
      <h3 className="text-sm font-medium text-text-primary mb-2">{title}</h3>
      <p className="text-xs text-text-secondary max-w-md leading-relaxed">{description}</p>
      <span className="mt-4 text-[10px] px-2 py-1 rounded bg-accent-blue/10 text-accent-blue">
        Coming Soon
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
function MLSystemCard({ title, icon, color, description, status, statusColor }: {
  title: string; icon: string; color: string; description: string; status: string; statusColor: string;
}) {
  return (
    <div className="border border-border-secondary rounded-lg p-3 bg-bg-secondary/30">
      <div className="flex items-center gap-2 mb-1">
        <span>{icon}</span>
        <span className={clsx('text-[11px] font-bold', color)}>{title}</span>
      </div>
      <p className="text-[9px] text-text-muted mb-2">{description}</p>
      <span className={clsx('text-[10px] font-mono font-semibold', statusColor)}>{status}</span>
    </div>
  )
}

function MacroCrossMarketPanel() {
  const [macro, setMacro] = useState<any>(null)
  const [cm, setCm] = useState<any>(null)

  useEffect(() => {
    fetch('/api/v2/macro').then(r => r.json()).then(d => { if (!d.message) setMacro(d) }).catch(() => {})
    fetch('/api/v2/cross-market').then(r => r.json()).then(d => { if (!d.message) setCm(d) }).catch(() => {})
  }, [])

  if (!macro && !cm) return null

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {macro && (
        <div className="border border-border-secondary rounded-lg p-3 bg-bg-secondary/30">
          <h4 className="text-[11px] font-bold text-text-primary mb-2 flex items-center gap-1">
            <BarChart3 size={12} className="text-amber-400" /> Macro Indicators
          </h4>
          <p className="text-[10px] text-text-muted mb-1">Risk: <span className={clsx('font-semibold',
            macro.overall_risk_level === 'low' ? 'text-green-400' : macro.overall_risk_level === 'high' ? 'text-red-400' : 'text-amber-400'
          )}>{macro.overall_risk_level?.toUpperCase()}</span></p>
          {macro.indicators && Object.entries(macro.indicators).slice(0, 4).map(([name, ind]: [string, any]) => (
            <div key={name} className="flex items-center justify-between text-[9px] py-0.5">
              <span className="text-text-muted">{name}</span>
              <span className="text-text-primary font-mono">{ind?.risk_level || ind?.level || '--'}</span>
            </div>
          ))}
        </div>
      )}
      {cm && (
        <div className="border border-border-secondary rounded-lg p-3 bg-bg-secondary/30">
          <h4 className="text-[11px] font-bold text-text-primary mb-2 flex items-center gap-1">
            <Globe size={12} className="text-blue-400" /> US-India Cross-Market
          </h4>
          <div className="space-y-1 text-[9px]">
            <div className="flex justify-between"><span className="text-text-muted">Correlation (20d)</span><span className="font-mono">{cm.correlation_20d?.toFixed(3)}</span></div>
            <div className="flex justify-between"><span className="text-text-muted">Predicted gap</span><span className={clsx('font-mono', (cm.predicted_india_gap_pct || 0) < 0 ? 'text-red-400' : 'text-green-400')}>{cm.predicted_india_gap_pct?.toFixed(2)}%</span></div>
            <div className="flex justify-between"><span className="text-text-muted">Sync</span><span className="font-mono">{cm.sync_status}</span></div>
            <div className="flex justify-between"><span className="text-text-muted">US regime</span><span className="font-mono">R{cm.source_regime}</span></div>
            <div className="flex justify-between"><span className="text-text-muted">India regime</span><span className="font-mono">R{cm.target_regime}</span></div>
          </div>
        </div>
      )}
    </div>
  )
}

// ML Status Tab
// ---------------------------------------------------------------------------

function MLStatusTab() {
  const { data: ml, isLoading: mlLoading } = useMLStatus()
  const { data: closedData, isLoading: tradesLoading } = useClosedTrades(100)

  if (mlLoading) {
    return <div className="text-xs text-text-muted py-8 text-center">Loading ML status...</div>
  }

  const trades = closedData?.trades || []
  const totalClosed = closedData?.total || 0

  // Summary stats from trades
  const wins = trades.filter(t => (t.total_pnl ?? 0) > 0).length
  const losses = trades.filter(t => (t.total_pnl ?? 0) < 0).length
  const totalPnl = trades.reduce((s, t) => s + (t.total_pnl ?? 0), 0)
  const avgPnl = trades.length > 0 ? totalPnl / trades.length : 0
  const winRate = trades.length > 0 ? (wins / trades.length * 100) : 0

  const supervPct = ml ? Math.min(100, Math.round((ml.closed_trades / 100) * 100)) : 0
  const rlPct = ml ? Math.min(100, Math.round((ml.closed_trades / 500) * 100)) : 0

  return (
    <div className="space-y-4">
      {/* Readiness strip */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2 px-3 py-2 bg-bg-secondary rounded border border-border-primary">
          <span className="text-[10px] text-text-muted uppercase">Supervised</span>
          <div className="w-20 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
            <div className={clsx('h-full rounded-full', supervPct >= 100 ? 'bg-green-500' : 'bg-accent-blue')} style={{ width: `${supervPct}%` }} />
          </div>
          <span className="text-xs font-mono text-text-primary">{ml?.closed_trades || 0}/100</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-2 bg-bg-secondary rounded border border-border-primary">
          <span className="text-[10px] text-text-muted uppercase">RL</span>
          <div className="w-20 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
            <div className={clsx('h-full rounded-full', rlPct >= 100 ? 'bg-green-500' : 'bg-accent-blue')} style={{ width: `${rlPct}%` }} />
          </div>
          <span className="text-xs font-mono text-text-primary">{ml?.closed_trades || 0}/500</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-2 bg-bg-secondary rounded border border-border-primary">
          <span className="text-[10px] text-text-muted uppercase">Events</span>
          <span className="text-xs font-mono text-text-primary">{ml?.events || 0}</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-2 bg-bg-secondary rounded border border-border-primary">
          <span className="text-[10px] text-text-muted uppercase">Snapshots</span>
          <span className="text-xs font-mono text-text-primary">{ml?.snapshots || 0}</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-2 bg-bg-secondary rounded border border-border-primary">
          <span className="text-[10px] text-text-muted uppercase">Win Rate</span>
          <span className="text-xs font-mono text-text-primary">{winRate.toFixed(0)}%</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-2 bg-bg-secondary rounded border border-border-primary">
          <span className="text-[10px] text-text-muted uppercase">Avg P&L</span>
          <span className={clsx('text-xs font-mono', avgPnl >= 0 ? 'text-green-400' : 'text-red-400')}>
            ${avgPnl.toFixed(2)}
          </span>
        </div>
      </div>

      {/* ML Intelligence Systems */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Drift Detection */}
        <MLSystemCard
          title="Drift Detection" icon="\u26A0" color="text-red-400"
          description="Monitors strategy degradation per regime"
          status={ml?.drift_alerts === 0 ? 'All stable' : `${ml?.drift_alerts || 0} alerts`}
          statusColor={ml?.drift_alerts ? 'text-red-400' : 'text-green-400'}
        />
        {/* Thompson Sampling */}
        <MLSystemCard
          title="Thompson Sampling" icon="\uD83C\uDFB0" color="text-purple-400"
          description="Learns which strategies win per regime"
          status={`${ml?.bandit_cells || 0} cells`}
          statusColor="text-purple-400"
        />
        {/* Threshold Optimization */}
        <MLSystemCard
          title="Thresholds" icon="\u2699" color="text-amber-400"
          description="Self-tunes gate cutoffs from outcomes"
          status={ml?.thresholds_optimized ? 'Optimized' : 'Default'}
          statusColor={ml?.thresholds_optimized ? 'text-green-400' : 'text-zinc-400'}
        />
        {/* POP Calibration */}
        <MLSystemCard
          title="POP Calibration" icon="\uD83C\uDFAF" color="text-cyan-400"
          description="Corrects probability from actual win rates"
          status={ml?.pop_calibrated ? 'Calibrated' : 'Uncalibrated'}
          statusColor={ml?.pop_calibrated ? 'text-green-400' : 'text-zinc-400'}
        />
      </div>

      {/* Macro + Cross-Market */}
      <MacroCrossMarketPanel />

      {/* Training Data — Closed Trades Table */}
      <div className="bg-bg-secondary rounded-lg border border-border-primary overflow-hidden">
        <div className="px-3 py-2 border-b border-border-secondary flex items-center justify-between">
          <h3 className="text-xs font-medium text-text-secondary uppercase tracking-wider">
            Training Data — Closed Trades ({totalClosed})
          </h3>
          <span className="text-[10px] text-text-muted">
            {wins}W / {losses}L &middot; Total P&L: <span className={clsx(totalPnl >= 0 ? 'text-green-400' : 'text-red-400')}>${totalPnl.toFixed(2)}</span>
          </span>
        </div>

        {tradesLoading ? (
          <div className="text-xs text-text-muted py-8 text-center">Loading trades...</div>
        ) : trades.length === 0 ? (
          <div className="text-xs text-text-muted py-8 text-center">
            No closed trades yet. Each closed trade becomes a training sample for ML/RL models.
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[calc(100vh-300px)]">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-bg-secondary">
                <tr className="border-b border-border-secondary text-text-muted">
                  <th className="text-left px-2 py-1.5 font-medium">Symbol</th>
                  <th className="text-left px-2 py-1.5 font-medium">Strategy</th>
                  <th className="text-left px-2 py-1.5 font-medium">Desk</th>
                  <th className="text-right px-2 py-1.5 font-medium">Entry</th>
                  <th className="text-right px-2 py-1.5 font-medium">Exit</th>
                  <th className="text-right px-2 py-1.5 font-medium">P&L</th>
                  <th className="text-right px-2 py-1.5 font-medium">Max Risk</th>
                  <th className="text-right px-2 py-1.5 font-medium">R:R</th>
                  <th className="text-right px-2 py-1.5 font-medium">Days</th>
                  <th className="text-left px-2 py-1.5 font-medium">Exit Reason</th>
                  <th className="text-left px-2 py-1.5 font-medium">Source</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => {
                  const rr = t.max_risk && t.max_risk !== 0 && t.total_pnl != null
                    ? (t.total_pnl / Math.abs(t.max_risk))
                    : null
                  return (
                    <tr key={t.id} className="border-b border-border-secondary/50 hover:bg-bg-hover">
                      <td className="px-2 py-1.5 font-mono text-text-primary font-medium">{t.underlying_symbol}</td>
                      <td className="px-2 py-1.5 text-text-secondary">{t.strategy_type || '--'}</td>
                      <td className="px-2 py-1.5 text-text-muted">{t.portfolio_name || '--'}</td>
                      <td className="px-2 py-1.5 text-right font-mono text-text-secondary">
                        {t.entry_price != null ? `$${t.entry_price.toFixed(2)}` : '--'}
                      </td>
                      <td className="px-2 py-1.5 text-right font-mono text-text-secondary">
                        {t.exit_price != null ? `$${t.exit_price.toFixed(2)}` : '--'}
                      </td>
                      <td className={clsx('px-2 py-1.5 text-right font-mono font-medium',
                        (t.total_pnl ?? 0) > 0 ? 'text-green-400' : (t.total_pnl ?? 0) < 0 ? 'text-red-400' : 'text-text-muted'
                      )}>
                        {t.total_pnl != null ? `$${t.total_pnl.toFixed(2)}` : '--'}
                      </td>
                      <td className="px-2 py-1.5 text-right font-mono text-text-muted">
                        {t.max_risk != null ? `$${Math.abs(t.max_risk).toFixed(0)}` : '--'}
                      </td>
                      <td className={clsx('px-2 py-1.5 text-right font-mono',
                        rr != null && rr > 0 ? 'text-green-400' : rr != null && rr < 0 ? 'text-red-400' : 'text-text-muted'
                      )}>
                        {rr != null ? `${rr.toFixed(2)}` : '--'}
                      </td>
                      <td className="px-2 py-1.5 text-right font-mono text-text-muted">
                        {t.duration_days ?? '--'}
                      </td>
                      <td className="px-2 py-1.5 text-text-secondary">{t.exit_reason || '--'}</td>
                      <td className="px-2 py-1.5 text-text-muted">{t.trade_source || '--'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function AgentsPage() {
  const [activeTab, setActiveTab] = useState<TabId>('workflow')

  return (
    <div className="p-4">
      {/* Tab bar */}
      <div className="flex items-center gap-1 mb-4 border-b border-border-primary">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-2 text-xs transition-colors border-b-2 -mb-px',
              activeTab === id
                ? 'border-accent-blue text-accent-blue'
                : 'border-transparent text-text-muted hover:text-text-secondary',
            )}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'workflow' && <WorkflowTab />}
      {activeTab === 'active' && <ActiveAgentsTab />}
      {activeTab === 'research' && (
        <ComingSoonTab
          title="Quant Research Engine"
          icon={Beaker}
          description="Autonomous research engine with 8 skills: Market Scan, Technical Analysis, Fundamental Analysis, Sentiment, Recovery Analysis, Backtesting, Correlation, and Black Swan Detection. Runs WhatIf portfolios, generates hypotheses, uses LLM for market reasoning."
        />
      )}
      {activeTab === 'knowledge' && (
        <ComingSoonTab
          title="Learning & Knowledge Base"
          icon={BookOpen}
          description="Agents will declare structured learnings, patterns, and improvement areas. Knowledge base tracks observations across all agents with confidence levels and validation status. Feeds continuous improvement loop."
        />
      )}
      {activeTab === 'ml' && <MLStatusTab />}
    </div>
  )
}
