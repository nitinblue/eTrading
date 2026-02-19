import { useMemo } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { useCapitalData } from '../hooks/useCapital'
import { Spinner } from '../components/common/Spinner'
import { EmptyState } from '../components/common/EmptyState'
import { clsx } from 'clsx'

const severityColors: Record<string, { bg: string; text: string; border: string }> = {
  ok: { bg: 'bg-green-900/30', text: 'text-green-400', border: 'border-green-800' },
  info: { bg: 'bg-blue-900/30', text: 'text-blue-400', border: 'border-blue-800' },
  warning: { bg: 'bg-yellow-900/30', text: 'text-yellow-400', border: 'border-yellow-800' },
  critical: { bg: 'bg-red-900/30', text: 'text-red-400', border: 'border-red-800' },
}

export function CapitalPage() {
  const { data: capitalData, isLoading } = useCapitalData()

  const totals = useMemo(() => {
    if (!capitalData || capitalData.length === 0) return null
    return {
      total: capitalData.reduce((s, c) => s + c.initial_capital, 0),
      equity: capitalData.reduce((s, c) => s + c.total_equity, 0),
      deployed: capitalData.reduce((s, c) => s + (c.total_equity - c.idle_capital), 0),
      idle: capitalData.reduce((s, c) => s + c.idle_capital, 0),
    }
  }, [capitalData])

  const chartData = useMemo(() => {
    if (!capitalData) return []
    return capitalData.map((c) => ({
      name: c.name,
      Deployed: Math.max(c.total_equity - c.idle_capital, 0),
      Idle: c.idle_capital,
    }))
  }, [capitalData])

  // Sort by severity for alert table
  const sortedBySeverity = useMemo(() => {
    if (!capitalData) return []
    const order: Record<string, number> = { critical: 0, warning: 1, info: 2, ok: 3 }
    return [...capitalData].sort(
      (a, b) => (order[a.severity] ?? 4) - (order[b.severity] ?? 4),
    )
  }, [capitalData])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    )
  }

  if (!capitalData || capitalData.length === 0) {
    return (
      <div className="card">
        <EmptyState message="No capital data available. Start the workflow engine to populate capital metrics." />
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* KPI strip */}
      {totals && (
        <div className="card">
          <div className="card-body">
            <div className="flex items-center gap-6 flex-wrap">
              <KPI label="Total Capital" value={fmtCurrency(totals.total)} />
              <KPI label="Total Equity" value={fmtCurrency(totals.equity)} />
              <KPI label="Deployed" value={fmtCurrency(totals.deployed)} color="text-accent-blue" />
              <KPI label="Idle" value={fmtCurrency(totals.idle)} color={totals.idle > totals.total * 0.3 ? 'text-accent-yellow' : 'text-text-primary'} />
              <KPI
                label="Deploy %"
                value={totals.equity > 0 ? `${((totals.deployed / totals.equity) * 100).toFixed(1)}%` : '0%'}
              />
            </div>
          </div>
        </div>
      )}

      {/* Portfolio capital cards */}
      <div className="card">
        <div className="card-header">
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Per-Portfolio Capital
          </h2>
        </div>
        <div className="card-body">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            {capitalData.map((c) => {
              const sev = severityColors[c.severity] || severityColors.ok
              return (
                <div
                  key={c.name}
                  className={clsx(
                    'rounded-lg border p-3 transition-colors',
                    sev.border, sev.bg,
                  )}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-text-primary truncate">{c.name}</span>
                    <span className={clsx('px-1.5 py-0.5 rounded text-2xs font-semibold border', sev.bg, sev.text, sev.border)}>
                      {c.severity.toUpperCase()}
                    </span>
                  </div>
                  <div className="space-y-1 text-2xs">
                    <div className="flex justify-between">
                      <span className="text-text-muted">Equity</span>
                      <span className="font-mono text-text-primary">{fmtCurrency(c.total_equity)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-text-muted">Deployed</span>
                      <span className="font-mono text-accent-blue">{c.deployed_pct.toFixed(1)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-text-muted">Idle</span>
                      <span className="font-mono text-text-secondary">{fmtCurrency(c.idle_capital)}</span>
                    </div>
                    {c.opp_cost_daily != null && c.opp_cost_daily > 0 && (
                      <div className="flex justify-between">
                        <span className="text-text-muted">Opp Cost/day</span>
                        <span className="font-mono text-accent-orange">${c.opp_cost_daily.toFixed(2)}</span>
                      </div>
                    )}
                  </div>
                  {/* Utilization bar */}
                  <div className="mt-2 h-1.5 bg-bg-tertiary rounded overflow-hidden">
                    <div
                      className="h-full bg-accent-blue rounded"
                      style={{ width: `${Math.min(c.deployed_pct, 100)}%` }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Stacked bar chart */}
      <div className="card">
        <div className="card-header">
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Deployed vs Idle by Portfolio
          </h2>
        </div>
        <div className="card-body" style={{ height: 250 }}>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#555568' }} angle={-30} textAnchor="end" height={60} />
                <YAxis tick={{ fontSize: 10, fill: '#555568' }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #2a2a3e', fontSize: 11 }}
                  formatter={(v: number) => `$${v.toLocaleString()}`}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="Deployed" stackId="a" fill="#3b82f6" />
                <Bar dataKey="Idle" stackId="a" fill="#1e293b" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-full text-text-muted text-xs">No chart data</div>
          )}
        </div>
      </div>

      {/* Idle capital alerts */}
      <div className="card">
        <div className="card-header">
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Idle Capital Alerts
          </h2>
        </div>
        <div className="card-body">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-text-muted text-left border-b border-border-secondary">
                <th className="py-1.5 pr-3">Portfolio</th>
                <th className="py-1.5 pr-3">Severity</th>
                <th className="py-1.5 pr-3 text-right">Idle Capital</th>
                <th className="py-1.5 pr-3 text-right">Deployed %</th>
                <th className="py-1.5 text-right">Opp Cost/day</th>
              </tr>
            </thead>
            <tbody>
              {sortedBySeverity.map((c) => {
                const sev = severityColors[c.severity] || severityColors.ok
                return (
                  <tr key={c.name} className="border-b border-border-secondary/50">
                    <td className="py-1.5 pr-3 font-medium text-text-primary">{c.name}</td>
                    <td className="py-1.5 pr-3">
                      <span className={clsx('px-1.5 py-0.5 rounded text-2xs font-semibold border', sev.bg, sev.text, sev.border)}>
                        {c.severity.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-1.5 pr-3 text-right font-mono text-text-secondary">{fmtCurrency(c.idle_capital)}</td>
                    <td className="py-1.5 pr-3 text-right font-mono text-accent-blue">{c.deployed_pct.toFixed(1)}%</td>
                    <td className="py-1.5 text-right font-mono text-accent-orange">
                      {c.opp_cost_daily != null ? `$${c.opp_cost_daily.toFixed(2)}` : '--'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function KPI({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <div className="text-2xs text-text-muted uppercase">{label}</div>
      <span className={clsx('text-sm font-mono font-semibold', color || 'text-text-primary')}>
        {value}
      </span>
    </div>
  )
}

function fmtCurrency(v?: number | null): string {
  if (v == null) return '--'
  return `$${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}
