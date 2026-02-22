import { useState } from 'react'
import { clsx } from 'clsx'
import { Beaker, BookOpen, Brain, AlertCircle, Clock, Award, Activity } from 'lucide-react'
import { useAgents, useAgentSummary, useMLStatus, useAgentTimeline } from '../hooks/useAgents'
import { AgentCard } from '../components/agents/AgentCard'
import { CATEGORY_CONFIG, AGENT_ICONS, type AgentCategory } from '../config/agentConfig'
import type { AgentInfo, AgentTimelineCycle } from '../api/types'

type TabId = 'active' | 'research' | 'knowledge' | 'ml'

const CategoryIcon = CATEGORY_CONFIG.safety.icon // Shield — used for tab

const tabs: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: 'active', label: 'Active Agents', icon: CategoryIcon },
  { id: 'research', label: 'Quant Research', icon: Beaker },
  { id: 'knowledge', label: 'Knowledge Base', icon: BookOpen },
  { id: 'ml', label: 'ML/RL Status', icon: Brain },
]

const categoryOrder = ['safety', 'perception', 'analysis', 'execution', 'learning'] as const

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
// ML Status Tab
// ---------------------------------------------------------------------------

function MLStatusTab() {
  const { data: ml, isLoading } = useMLStatus()

  if (isLoading) {
    return <div className="text-xs text-text-muted py-8 text-center">Loading ML status...</div>
  }

  if (!ml) {
    return <div className="text-xs text-text-muted py-8 text-center">ML pipeline not initialized</div>
  }

  const supervPct = ml.supervised_trades_needed > 0
    ? Math.round(((100 - ml.supervised_trades_needed) / 100) * 100)
    : 100
  const rlPct = ml.rl_trades_needed > 0
    ? Math.round(((500 - ml.rl_trades_needed) / 500) * 100)
    : 100

  return (
    <div className="space-y-6">
      {/* Data Pipeline */}
      <div className="bg-bg-secondary rounded-lg border border-border-primary p-4">
        <h3 className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-3">
          Data Pipeline
        </h3>
        <div className="grid grid-cols-4 gap-4">
          <Stat label="Daily Snapshots" value={ml.snapshots} />
          <Stat label="Trade Events" value={ml.events} />
          <Stat label="Events w/ Outcomes" value={ml.events_with_outcomes} />
          <Stat label="Closed Trades" value={ml.closed_trades} />
        </div>
      </div>

      {/* Readiness Indicators */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-bg-secondary rounded-lg border border-border-primary p-4">
          <h3 className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-3">
            Supervised Learning
          </h3>
          <ReadinessBar pct={supervPct} ready={ml.supervised_learning_ready} />
          <p className="text-xs text-text-muted mt-2">
            {ml.supervised_learning_ready
              ? 'Ready for training (100+ closed trades)'
              : `Need ${ml.supervised_trades_needed} more closed trades`}
          </p>
        </div>
        <div className="bg-bg-secondary rounded-lg border border-border-primary p-4">
          <h3 className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-3">
            Reinforcement Learning
          </h3>
          <ReadinessBar pct={rlPct} ready={ml.rl_ready} />
          <p className="text-xs text-text-muted mt-2">
            {ml.rl_ready
              ? 'Ready for RL training (500+ closed trades)'
              : `Need ${ml.rl_trades_needed} more closed trades`}
          </p>
        </div>
      </div>

      {/* Feature Extraction */}
      <div className="bg-bg-secondary rounded-lg border border-border-primary p-4">
        <h3 className="text-xs font-medium text-text-secondary uppercase tracking-wider mb-3">
          Feature Extraction ({ml.features_defined} features)
        </h3>
        <div className="grid grid-cols-3 gap-4">
          <FeatureGroup label="Market Features" count={ml.feature_groups.market} total={ml.features_defined} />
          <FeatureGroup label="Position Features" count={ml.feature_groups.position} total={ml.features_defined} />
          <FeatureGroup label="Portfolio Features" count={ml.feature_groups.portfolio} total={ml.features_defined} />
        </div>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-lg font-bold text-text-primary font-mono">{value.toLocaleString()}</div>
      <div className="text-[10px] text-text-muted">{label}</div>
    </div>
  )
}

function ReadinessBar({ pct, ready }: { pct: number; ready: boolean }) {
  return (
    <div className="w-full h-2 bg-bg-tertiary rounded-full overflow-hidden">
      <div
        className={clsx(
          'h-full rounded-full transition-all',
          ready ? 'bg-green-500' : 'bg-accent-blue',
        )}
        style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
      />
    </div>
  )
}

function FeatureGroup({ label, count, total }: { label: string; count: number; total: number }) {
  const pct = Math.round((count / total) * 100)
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-text-secondary">{label}</span>
        <span className="text-xs font-mono text-text-primary">{count}</span>
      </div>
      <div className="w-full h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
        <div className="h-full rounded-full bg-purple-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function AgentsPage() {
  const [activeTab, setActiveTab] = useState<TabId>('active')

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
