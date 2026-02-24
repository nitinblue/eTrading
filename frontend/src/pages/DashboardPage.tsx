import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'
import { usePortfolios } from '../hooks/usePortfolios'
import { useWorkflowStatus } from '../hooks/useWorkflowStatus'
import { useCapitalData } from '../hooks/useCapital'
import { useRecommendations } from '../hooks/useRecommendations'
import { AgentBadge } from '../components/common/AgentBadge'
import { useWeeklyPnL } from '../hooks/usePerformance'
import { useAgentBrief, useAgentStatus, useAgentChat } from '../hooks/useAgentBrain'
import { Spinner } from '../components/common/Spinner'
import { clsx } from 'clsx'

const DONUT_COLORS = ['#3b82f6', '#1e293b']

export function DashboardPage() {
  const { data: portfolios, isLoading: loadingPf } = usePortfolios()
  const { data: wfStatus } = useWorkflowStatus()
  const { data: capitalData } = useCapitalData()
  const { data: pendingRecs } = useRecommendations({ status: 'pending' })
  const { data: weeklyPnl } = useWeeklyPnL('all', 12)
  const { data: agentBrief, isLoading: loadingBrief, refetch: refetchBrief } = useAgentBrief()
  const { data: agentStatus } = useAgentStatus()

  const agg = useMemo(() => {
    if (!portfolios) return null
    const real = portfolios.filter(
      (p) => p.portfolio_type === 'real' && !p.name.startsWith('research_'),
    )
    return {
      totalEquity: real.reduce((s, p) => s + p.total_equity, 0),
      dailyPnl: real.reduce((s, p) => s + p.daily_pnl, 0),
      theta: real.reduce((s, p) => s + p.portfolio_theta, 0),
      delta: real.reduce((s, p) => s + p.portfolio_delta, 0),
      openTrades: real.reduce((s, p) => s + p.open_trade_count, 0),
    }
  }, [portfolios])

  const capitalAgg = useMemo(() => {
    if (!capitalData || capitalData.length === 0) return null
    const deployed = capitalData.reduce((s, c) => s + (c.total_equity - c.idle_capital), 0)
    const idle = capitalData.reduce((s, c) => s + c.idle_capital, 0)
    return { deployed, idle }
  }, [capitalData])

  return (
    <div className="space-y-3">
      {/* Agent ownership */}
      <div className="flex items-center gap-1.5">
        <AgentBadge agent="sentinel" />
      </div>
      {/* Row 1: KPI strip + Workflow status side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="lg:col-span-2 card">
          <div className="card-body py-2">
            {loadingPf ? (
              <div className="flex items-center gap-6 flex-wrap">
                <KPI label="Total Equity" value={undefined} />
                <KPI label="Daily P&L" value={undefined} />
                <KPI label="Theta/day" value={undefined} />
                <KPI label="Net Delta" value={undefined} />
                <KPI label="Open Trades" value={undefined} />
                <KPI label="Pending Recs" value={undefined} />
                <KPI label="VIX" value={undefined} />
              </div>
            ) : (
              <div className="flex items-center gap-6 flex-wrap">
                <KPI label="Total Equity" value={fmtCurrency(agg?.totalEquity)} />
                <KPI
                  label="Daily P&L"
                  value={fmtPnl(agg?.dailyPnl)}
                  color={pnlColor(agg?.dailyPnl)}
                />
                <KPI label="Theta/day" value={agg ? `${agg.theta >= 0 ? '+' : ''}$${Math.abs(agg.theta).toFixed(0)}` : '--'} color="text-accent-green" />
                <KPI
                  label="Net Delta"
                  value={agg ? `${agg.delta >= 0 ? '+' : ''}${agg.delta.toFixed(1)}` : '--'}
                  color={pnlColor(agg?.delta)}
                />
                <KPI label="Open Trades" value={agg?.openTrades?.toString() ?? '--'} />
                <KPI
                  label="Pending Recs"
                  value={pendingRecs?.length?.toString() ?? '0'}
                  color={pendingRecs && pendingRecs.length > 0 ? 'text-accent-orange' : undefined}
                />
                <KPI
                  label="VIX"
                  value={wfStatus?.vix != null ? wfStatus.vix.toFixed(1) : '--'}
                  color={
                    wfStatus?.vix != null
                      ? wfStatus.vix > 30 ? 'text-accent-red' : wfStatus.vix > 20 ? 'text-accent-yellow' : 'text-accent-green'
                      : undefined
                  }
                />
              </div>
            )}
          </div>
        </div>
        <WorkflowSummaryCard status={wfStatus ?? null} />
      </div>

      {/* Row 2: Agent Brief + Capital side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="lg:col-span-2">
          <AgentBriefCard
            brief={agentBrief}
            loading={loadingBrief}
            status={agentStatus}
            onRefresh={() => refetchBrief()}
          />
        </div>
        <div className="card">
          <div className="card-header py-1.5">
            <h2 className="text-2xs font-semibold text-text-secondary uppercase tracking-wider">
              Capital Deployment
            </h2>
          </div>
          <div className="card-body flex items-center justify-center py-2" style={{ height: 140 }}>
            {capitalAgg ? (
              <div className="flex items-center gap-4">
                <ResponsiveContainer width={100} height={100}>
                  <PieChart>
                    <Pie
                      data={[
                        { name: 'Deployed', value: capitalAgg.deployed },
                        { name: 'Idle', value: capitalAgg.idle },
                      ]}
                      cx="50%"
                      cy="50%"
                      innerRadius={30}
                      outerRadius={45}
                      dataKey="value"
                      strokeWidth={0}
                    >
                      {DONUT_COLORS.map((color, i) => (
                        <Cell key={i} fill={color} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-1.5 text-2xs">
                  <div className="flex items-center gap-1.5">
                    <div className="w-2 h-2 rounded bg-accent-blue" />
                    <span className="text-text-secondary">Deployed</span>
                    <span className="font-mono font-semibold text-text-primary">
                      {fmtCurrency(capitalAgg.deployed)}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-2 h-2 rounded bg-bg-tertiary" />
                    <span className="text-text-secondary">Idle</span>
                    <span className="font-mono font-semibold text-text-primary">
                      {fmtCurrency(capitalAgg.idle)}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-text-muted text-2xs">No capital data</div>
            )}
          </div>
        </div>
      </div>

      {/* Row 3: Weekly P&L chart + Pending Recs + Agent Chat */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {/* Weekly P&L */}
        <div className="card">
          <div className="card-header py-1.5">
            <h2 className="text-2xs font-semibold text-text-secondary uppercase tracking-wider">
              Weekly P&L
            </h2>
          </div>
          <div className="card-body py-1" style={{ height: 160 }}>
            {weeklyPnl && weeklyPnl.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={weeklyPnl}>
                  <XAxis
                    dataKey="week_start"
                    tick={{ fontSize: 9, fill: '#555568' }}
                    tickFormatter={(v) => new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  />
                  <YAxis tick={{ fontSize: 9, fill: '#555568' }} tickFormatter={(v) => `$${v}`} width={45} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #2a2a3e', fontSize: 10 }}
                    labelFormatter={(v) => `Week of ${new Date(v).toLocaleDateString()}`}
                    formatter={(v: number) => [`$${v.toFixed(2)}`, 'Cumulative P&L']}
                  />
                  <Area
                    type="monotone"
                    dataKey="cumulative_pnl"
                    stroke="#3b82f6"
                    fill="#3b82f620"
                    strokeWidth={1.5}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-text-muted text-2xs">
                No weekly P&L data yet
              </div>
            )}
          </div>
        </div>

        {/* Pending Recs */}
        <PendingRecsCard recs={pendingRecs ?? []} />

        {/* Agent Chat */}
        <AgentChatCard />
      </div>
    </div>
  )
}

// --- Agent Brief Card ---

function AgentBriefCard({
  brief,
  loading,
  status,
  onRefresh,
}: {
  brief?: { available: boolean; brief: string; generated_at?: string; data_summary?: { positions: number; transactions: number; pending_recs: number; has_market_metrics: boolean } }
  loading: boolean
  status?: { llm_available: boolean; broker_connected: boolean }
  onRefresh: () => void
}) {
  const isConfigured = status?.llm_available ?? false
  const isBrokerConnected = status?.broker_connected ?? false

  return (
    <div className="card border-l-4 border-l-accent-blue">
      <div className="card-header py-1.5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={clsx(
            'w-2 h-2 rounded-full',
            isConfigured && isBrokerConnected ? 'bg-accent-green animate-pulse' : 'bg-accent-red',
          )} />
          <h2 className="text-2xs font-semibold text-accent-blue uppercase tracking-wider">
            Agent Intelligence
          </h2>
          {brief?.data_summary && (
            <span className="text-2xs text-text-muted">
              {brief.data_summary.positions} positions | {brief.data_summary.pending_recs} pending recs
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {brief?.generated_at && (
            <span className="text-2xs text-text-muted">
              {new Date(brief.generated_at).toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={onRefresh}
            disabled={loading}
            className="text-2xs text-accent-blue hover:underline disabled:opacity-50"
          >
            {loading ? 'Thinking...' : 'Refresh'}
          </button>
        </div>
      </div>
      <div className="card-body py-2">
        {loading ? (
          <div className="flex items-center gap-2 py-2">
            <Spinner size="sm" />
            <span className="text-2xs text-text-muted">Agent is analyzing your portfolio...</span>
          </div>
        ) : !isConfigured ? (
          <div className="py-2">
            <p className="text-2xs text-accent-orange">
              Agent brain not configured. Add <code className="bg-bg-tertiary px-1 rounded">ANTHROPIC_API_KEY</code> to .env to enable.
            </p>
          </div>
        ) : (
          <div className="text-2xs text-text-secondary leading-relaxed whitespace-pre-wrap max-h-[120px] overflow-auto">
            {brief?.brief || 'No analysis available. Click Refresh to generate.'}
          </div>
        )}
      </div>
    </div>
  )
}

// --- Agent Chat Card ---

function AgentChatCard() {
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<{ role: 'user' | 'agent'; text: string }[]>([])
  const chatMutation = useAgentChat()

  const handleSend = () => {
    if (!input.trim()) return
    const userMsg = input.trim()
    setMessages((prev) => [...prev, { role: 'user', text: userMsg }])
    setInput('')

    chatMutation.mutate(userMsg, {
      onSuccess: (data) => {
        setMessages((prev) => [...prev, { role: 'agent', text: data.response }])
      },
      onError: (err) => {
        setMessages((prev) => [...prev, { role: 'agent', text: `Error: ${err.message}` }])
      },
    })
  }

  return (
    <div className="card flex flex-col" style={{ minHeight: 160 }}>
      <div className="card-header py-1.5">
        <h2 className="text-2xs font-semibold text-text-secondary uppercase tracking-wider">
          Ask Agent
        </h2>
      </div>
      <div className="card-body flex-1 overflow-auto space-y-1.5 py-1" style={{ maxHeight: 120 }}>
        {messages.length === 0 ? (
          <p className="text-2xs text-text-muted py-1">
            Ask about portfolio, positions, risk, strategy...
          </p>
        ) : (
          messages.map((m, i) => (
            <div
              key={i}
              className={clsx(
                'text-2xs p-1.5 rounded max-w-[90%]',
                m.role === 'user'
                  ? 'bg-accent-blue/20 text-text-primary ml-auto'
                  : 'bg-bg-tertiary text-text-secondary',
              )}
            >
              {m.text}
            </div>
          ))
        )}
        {chatMutation.isPending && (
          <div className="flex items-center gap-1 text-2xs text-text-muted">
            <Spinner size="sm" /> Thinking...
          </div>
        )}
      </div>
      <div className="border-t border-border-secondary p-1.5 flex gap-1.5">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="What's my delta exposure?"
          className="flex-1 bg-bg-tertiary text-text-primary text-2xs rounded px-2 py-1 outline-none focus:ring-1 focus:ring-accent-blue"
        />
        <button
          onClick={handleSend}
          disabled={chatMutation.isPending || !input.trim()}
          className="bg-accent-blue text-white text-2xs px-2 py-1 rounded hover:bg-accent-blue/80 disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  )
}

// --- Sub-components ---

function KPI({ label, value, color }: { label: string; value: string | undefined; color?: string }) {
  return (
    <div>
      <div className="text-2xs text-text-muted uppercase">{label}</div>
      <span className={clsx('text-sm font-mono font-semibold', color || 'text-text-primary')}>
        {value ?? '--'}
      </span>
    </div>
  )
}

function PendingRecsCard({ recs }: { recs: { id: string; underlying: string; strategy_type: string; recommendation_type: string; confidence: number; created_at: string }[] }) {
  const navigate = useNavigate()
  return (
    <div className="card">
      <div className="card-header py-1.5 flex items-center justify-between">
        <h2 className="text-2xs font-semibold text-text-secondary uppercase tracking-wider">
          Pending Recommendations ({recs.length})
        </h2>
        {recs.length > 0 && (
          <button onClick={() => navigate('/recommendations')} className="text-2xs text-accent-blue hover:underline">
            View all
          </button>
        )}
      </div>
      <div className="card-body py-1">
        {recs.length === 0 ? (
          <p className="text-2xs text-text-muted py-3 text-center">No pending recommendations</p>
        ) : (
          <table className="w-full text-2xs">
            <thead>
              <tr className="text-text-muted text-left border-b border-border-secondary">
                <th className="py-1 pr-2">Type</th>
                <th className="py-1 pr-2">Underlying</th>
                <th className="py-1 pr-2">Strategy</th>
                <th className="py-1 text-right">Conf</th>
              </tr>
            </thead>
            <tbody>
              {recs.slice(0, 5).map((r) => (
                <tr
                  key={r.id}
                  className="text-text-secondary border-b border-border-secondary/50 hover:bg-bg-hover cursor-pointer"
                  onClick={() => navigate('/recommendations')}
                >
                  <td className="py-1 pr-2">
                    <span className={clsx(
                      'px-1 py-0.5 rounded text-2xs font-semibold border',
                      r.recommendation_type === 'entry' ? 'bg-green-900/30 text-green-400 border-green-800' : 'bg-red-900/30 text-red-400 border-red-800',
                    )}>
                      {r.recommendation_type.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-1 pr-2 font-mono font-medium">{r.underlying}</td>
                  <td className="py-1 pr-2">{r.strategy_type}</td>
                  <td className="py-1 text-right font-mono">{(r.confidence * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function WorkflowSummaryCard({ status }: { status: WorkflowStatusLocal | null }) {
  const stateColors: Record<string, string> = {
    idle: 'text-text-muted',
    boot: 'text-accent-yellow',
    macro_check: 'text-accent-cyan',
    screening: 'text-accent-blue',
    recommendation_review: 'text-accent-orange',
    execution: 'text-accent-green',
    monitoring: 'text-accent-blue',
    trade_management: 'text-accent-purple',
    trade_review: 'text-accent-orange',
    reporting: 'text-accent-cyan',
  }

  const stateLabel = status?.current_state?.replace(/_/g, ' ').toUpperCase() || 'OFFLINE'
  const stateColor = stateColors[status?.current_state || ''] || 'text-text-muted'

  return (
    <div className="card">
      <div className="card-header py-1.5">
        <h2 className="text-2xs font-semibold text-text-secondary uppercase tracking-wider">
          Workflow
        </h2>
      </div>
      <div className="card-body py-2">
        <div className="grid grid-cols-2 gap-2">
          <div>
            <div className="text-2xs text-text-muted uppercase">State</div>
            <span className={clsx('text-xs font-mono font-semibold', stateColor)}>
              {stateLabel}
            </span>
          </div>
          <div>
            <div className="text-2xs text-text-muted uppercase">Cycle</div>
            <span className="text-xs font-mono font-semibold text-text-primary">
              #{status?.cycle_count ?? 0}
            </span>
          </div>
          <div>
            <div className="text-2xs text-text-muted uppercase">Trades Today</div>
            <span className="text-xs font-mono font-semibold text-text-primary">
              {status?.trades_today ?? 0}
            </span>
          </div>
          <div>
            <div className="text-2xs text-text-muted uppercase">Halted</div>
            <span className={clsx(
              'text-xs font-mono font-semibold',
              status?.halted ? 'text-accent-red' : 'text-accent-green',
            )}>
              {status?.halted ? 'YES' : 'NO'}
            </span>
          </div>
        </div>
        {status?.halt_reason && (
          <div className="mt-1.5 text-2xs text-accent-red bg-red-900/20 rounded p-1.5">
            {status.halt_reason}
          </div>
        )}
      </div>
    </div>
  )
}

// Helpers
type WorkflowStatusLocal = {
  current_state: string
  cycle_count: number
  halted: boolean
  halt_reason: string | null
  trades_today: number
  vix: number | null
}

function fmtCurrency(v?: number | null): string {
  if (v == null) return '--'
  return `$${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}

function fmtPnl(v?: number | null): string {
  if (v == null) return '--'
  const sign = v >= 0 ? '+' : ''
  return `${sign}$${Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function pnlColor(v?: number | null): string | undefined {
  if (v == null) return undefined
  return v > 0 ? 'text-pnl-profit' : v < 0 ? 'text-pnl-loss' : undefined
}
