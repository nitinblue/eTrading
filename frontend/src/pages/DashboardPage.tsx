import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from 'recharts'
import { usePortfolios } from '../hooks/usePortfolios'
import { useWorkflowStatus } from '../hooks/useWorkflowStatus'
import { useCapitalData } from '../hooks/useCapital'
import { useRecommendations } from '../hooks/useRecommendations'
import { useWeeklyPnL } from '../hooks/usePerformance'
import { Spinner } from '../components/common/Spinner'
import { clsx } from 'clsx'

const DONUT_COLORS = ['#3b82f6', '#1e293b']

export function DashboardPage() {
  const { data: portfolios, isLoading: loadingPf } = usePortfolios()
  const { data: wfStatus } = useWorkflowStatus()
  const { data: capitalData } = useCapitalData()
  const { data: pendingRecs } = useRecommendations({ status: 'pending' })
  const { data: weeklyPnl } = useWeeklyPnL('all', 12)

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

  if (loadingPf) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* KPI strip */}
      <div className="card">
        <div className="card-body">
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
        </div>
      </div>

      {/* Row 2: charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Equity curve / weekly P&L */}
        <div className="card">
          <div className="card-header">
            <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
              Weekly P&L
            </h2>
          </div>
          <div className="card-body" style={{ height: 220 }}>
            {weeklyPnl && weeklyPnl.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={weeklyPnl}>
                  <XAxis
                    dataKey="week_start"
                    tick={{ fontSize: 10, fill: '#555568' }}
                    tickFormatter={(v) => new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  />
                  <YAxis tick={{ fontSize: 10, fill: '#555568' }} tickFormatter={(v) => `$${v}`} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #2a2a3e', fontSize: 11 }}
                    labelFormatter={(v) => `Week of ${new Date(v).toLocaleDateString()}`}
                    formatter={(v: number) => [`$${v.toFixed(2)}`, 'Cumulative P&L']}
                  />
                  <Area
                    type="monotone"
                    dataKey="cumulative_pnl"
                    stroke="#3b82f6"
                    fill="#3b82f620"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-full text-text-muted text-xs">
                No weekly P&L data yet
              </div>
            )}
          </div>
        </div>

        {/* Capital donut */}
        <div className="card">
          <div className="card-header">
            <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
              Capital Deployment
            </h2>
          </div>
          <div className="card-body flex items-center justify-center" style={{ height: 220 }}>
            {capitalAgg ? (
              <div className="flex items-center gap-6">
                <ResponsiveContainer width={150} height={150}>
                  <PieChart>
                    <Pie
                      data={[
                        { name: 'Deployed', value: capitalAgg.deployed },
                        { name: 'Idle', value: capitalAgg.idle },
                      ]}
                      cx="50%"
                      cy="50%"
                      innerRadius={40}
                      outerRadius={65}
                      dataKey="value"
                      strokeWidth={0}
                    >
                      {DONUT_COLORS.map((color, i) => (
                        <Cell key={i} fill={color} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="space-y-2 text-xs">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded bg-accent-blue" />
                    <span className="text-text-secondary">Deployed</span>
                    <span className="font-mono font-semibold text-text-primary">
                      {fmtCurrency(capitalAgg.deployed)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded bg-bg-tertiary" />
                    <span className="text-text-secondary">Idle</span>
                    <span className="font-mono font-semibold text-text-primary">
                      {fmtCurrency(capitalAgg.idle)}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-text-muted text-xs">No capital data</div>
            )}
          </div>
        </div>
      </div>

      {/* Row 3: mini tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Pending recommendations */}
        <PendingRecsCard recs={pendingRecs ?? []} />

        {/* Workflow summary */}
        <WorkflowSummaryCard status={wfStatus ?? null} />
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
      <div className="card-header flex items-center justify-between">
        <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
          Pending Recommendations ({recs.length})
        </h2>
        {recs.length > 0 && (
          <button onClick={() => navigate('/recommendations')} className="text-2xs text-accent-blue hover:underline">
            View all
          </button>
        )}
      </div>
      <div className="card-body">
        {recs.length === 0 ? (
          <p className="text-xs text-text-muted py-4 text-center">No pending recommendations</p>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-text-muted text-left border-b border-border-secondary">
                <th className="py-1.5 pr-2">Type</th>
                <th className="py-1.5 pr-2">Underlying</th>
                <th className="py-1.5 pr-2">Strategy</th>
                <th className="py-1.5 text-right">Conf</th>
              </tr>
            </thead>
            <tbody>
              {recs.slice(0, 5).map((r) => (
                <tr
                  key={r.id}
                  className="text-text-secondary border-b border-border-secondary/50 hover:bg-bg-hover cursor-pointer"
                  onClick={() => navigate('/recommendations')}
                >
                  <td className="py-1.5 pr-2">
                    <span className={clsx(
                      'px-1.5 py-0.5 rounded text-2xs font-semibold border',
                      r.recommendation_type === 'entry' ? 'bg-green-900/30 text-green-400 border-green-800' : 'bg-red-900/30 text-red-400 border-red-800',
                    )}>
                      {r.recommendation_type.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-1.5 pr-2 font-mono font-medium">{r.underlying}</td>
                  <td className="py-1.5 pr-2">{r.strategy_type}</td>
                  <td className="py-1.5 text-right font-mono">{(r.confidence * 100).toFixed(0)}%</td>
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
      <div className="card-header">
        <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
          Workflow Status
        </h2>
      </div>
      <div className="card-body">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="text-2xs text-text-muted uppercase">State</div>
            <span className={clsx('text-sm font-mono font-semibold', stateColor)}>
              {stateLabel}
            </span>
          </div>
          <div>
            <div className="text-2xs text-text-muted uppercase">Cycle</div>
            <span className="text-sm font-mono font-semibold text-text-primary">
              #{status?.cycle_count ?? 0}
            </span>
          </div>
          <div>
            <div className="text-2xs text-text-muted uppercase">Trades Today</div>
            <span className="text-sm font-mono font-semibold text-text-primary">
              {status?.trades_today ?? 0}
            </span>
          </div>
          <div>
            <div className="text-2xs text-text-muted uppercase">Halted</div>
            <span className={clsx(
              'text-sm font-mono font-semibold',
              status?.halted ? 'text-accent-red' : 'text-accent-green',
            )}>
              {status?.halted ? 'YES' : 'NO'}
            </span>
          </div>
        </div>
        {status?.halt_reason && (
          <div className="mt-2 text-xs text-accent-red bg-red-900/20 rounded p-2">
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
