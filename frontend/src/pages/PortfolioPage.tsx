import { useState, useMemo } from 'react'
import { AgGridReact } from 'ag-grid-react'
import { ColDef } from 'ag-grid-community'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  Line, ComposedChart, Cell, Legend,
} from 'recharts'
import { defaultGridOptions, numericColDef } from '../components/grids/gridTheme'
import { PnLRenderer } from '../components/grids/cellRenderers'
import { usePortfolios } from '../hooks/usePortfolios'
import { useBrokerPositions } from '../hooks/useBrokerPositions'
import { useRiskFactors } from '../hooks/useRisk'
import { useLiveOrders } from '../hooks/useLiveOrders'
import { usePerformanceMetrics, useWeeklyPnL, useStrategyBreakdown, useSourceAttribution } from '../hooks/usePerformance'
import { useCapitalData } from '../hooks/useCapital'
import { PortfolioGrid } from '../components/grids/PortfolioGrid'
import { BrokerPositionGrid } from '../components/grids/BrokerPositionGrid'
import { PnLDisplay } from '../components/common/PnLDisplay'
import { GreeksBar } from '../components/common/GreeksBar'
import { AgentBadge } from '../components/common/AgentBadge'
import { Spinner } from '../components/common/Spinner'
import { EmptyState } from '../components/common/EmptyState'
import { clsx } from 'clsx'

type ViewMode = 'real' | 'whatif' | 'all'
type TabId = 'positions' | 'performance' | 'capital'

const tabDefs: { id: TabId; label: string }[] = [
  { id: 'positions', label: 'Positions' },
  { id: 'performance', label: 'Performance' },
  { id: 'capital', label: 'Capital' },
]

// ---------------------------------------------------------------------------
// Performance tab column definitions
// ---------------------------------------------------------------------------

const breakdownCols: ColDef[] = [
  { field: 'label', headerName: 'Strategy', width: 160, cellStyle: { fontWeight: 600 } },
  { field: 'total_trades', headerName: 'Trades', width: 80, ...numericColDef },
  {
    field: 'win_rate',
    headerName: 'Win %',
    width: 80,
    ...numericColDef,
    valueFormatter: ({ value }) => value != null ? `${(Number(value) * 100).toFixed(0)}%` : '--',
  },
  { field: 'total_pnl', headerName: 'Total P&L', width: 110, ...numericColDef, cellRenderer: PnLRenderer },
  {
    field: 'avg_win',
    headerName: 'Avg Win',
    width: 90,
    ...numericColDef,
    valueFormatter: ({ value }) => value != null ? `$${Number(value).toFixed(0)}` : '--',
    cellStyle: { ...numericColDef.cellStyle, color: '#22c55e' },
  },
  {
    field: 'avg_loss',
    headerName: 'Avg Loss',
    width: 90,
    ...numericColDef,
    valueFormatter: ({ value }) => value != null ? `-$${Math.abs(Number(value)).toFixed(0)}` : '--',
    cellStyle: { ...numericColDef.cellStyle, color: '#ef4444' },
  },
  {
    field: 'profit_factor',
    headerName: 'PF',
    width: 70,
    ...numericColDef,
    valueFormatter: ({ value }) => value != null ? Number(value).toFixed(2) : '--',
  },
  {
    field: 'sharpe_ratio',
    headerName: 'Sharpe',
    width: 80,
    ...numericColDef,
    valueFormatter: ({ value }) => value != null ? Number(value).toFixed(2) : '--',
  },
]

const sourceCols: ColDef[] = [
  { field: 'label', headerName: 'Source', width: 160, cellStyle: { fontWeight: 600 } },
  { field: 'total_trades', headerName: 'Trades', width: 80, ...numericColDef },
  {
    field: 'win_rate',
    headerName: 'Win %',
    width: 80,
    ...numericColDef,
    valueFormatter: ({ value }) => value != null ? `${(Number(value) * 100).toFixed(0)}%` : '--',
  },
  { field: 'total_pnl', headerName: 'Total P&L', width: 110, ...numericColDef, cellRenderer: PnLRenderer },
  {
    field: 'biggest_win',
    headerName: 'Best',
    width: 90,
    ...numericColDef,
    valueFormatter: ({ value }) => value != null ? `$${Number(value).toFixed(0)}` : '--',
    cellStyle: { ...numericColDef.cellStyle, color: '#22c55e' },
  },
  {
    field: 'biggest_loss',
    headerName: 'Worst',
    width: 90,
    ...numericColDef,
    valueFormatter: ({ value }) => value != null ? `-$${Math.abs(Number(value)).toFixed(0)}` : '--',
    cellStyle: { ...numericColDef.cellStyle, color: '#ef4444' },
  },
]

// ---------------------------------------------------------------------------
// Capital tab helpers
// ---------------------------------------------------------------------------

const severityColors: Record<string, { bg: string; text: string; border: string }> = {
  ok: { bg: 'bg-green-900/30', text: 'text-green-400', border: 'border-green-800' },
  info: { bg: 'bg-blue-900/30', text: 'text-blue-400', border: 'border-blue-800' },
  warning: { bg: 'bg-yellow-900/30', text: 'text-yellow-400', border: 'border-yellow-800' },
  critical: { bg: 'bg-red-900/30', text: 'text-red-400', border: 'border-red-800' },
}

function fmtCurrency(v?: number | null): string {
  if (v == null) return '--'
  return `$${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}

// ---------------------------------------------------------------------------
// Small reusable components
// ---------------------------------------------------------------------------

function MetricCard({ label, value, subtext }: { label: string; value: string; subtext?: string }) {
  return (
    <div className="card">
      <div className="card-body text-center">
        <div className="text-2xs text-text-muted uppercase mb-1">{label}</div>
        <div className="text-2xl font-mono font-bold text-text-primary">{value}</div>
        {subtext && <div className="text-2xs text-text-muted mt-0.5">{subtext}</div>}
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

// ---------------------------------------------------------------------------
// Positions Tab
// ---------------------------------------------------------------------------

function PositionsTab({
  filteredPortfolios,
  selectedPortfolio,
  setSelectedPortfolio,
  selected,
  brokerPositions,
  loadingBrokerPositions,
  riskFactors,
  liveOrders,
}: {
  filteredPortfolios: any[]
  selectedPortfolio: string | null
  setSelectedPortfolio: (v: string | null) => void
  selected: any | undefined
  brokerPositions: any[] | undefined
  loadingBrokerPositions: boolean
  riskFactors: any[] | undefined
  liveOrders: any[] | undefined
}) {
  return (
    <>
      {/* Portfolio grid */}
      <div className="card">
        <div className="card-header flex items-center justify-between">
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Portfolios ({filteredPortfolios.length})
          </h2>
          {selectedPortfolio && (
            <button
              onClick={() => setSelectedPortfolio(null)}
              className="text-2xs text-accent-blue hover:underline"
            >
              Show all positions
            </button>
          )}
        </div>
        <PortfolioGrid
          portfolios={filteredPortfolios}
          onPortfolioClick={setSelectedPortfolio}
        />
      </div>

      {/* Selected portfolio detail */}
      {selected && (
        <div className="card">
          <div className="card-header flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-xs font-semibold text-text-primary">
                {selected.name}
              </h2>
              <span className="text-2xs text-text-muted">{selected.broker}</span>
            </div>
            <PnLDisplay value={selected.total_pnl} size="sm" />
          </div>
          <div className="card-body">
            <div className="grid grid-cols-4 gap-2 mb-3">
              <GreeksBar label="Delta" value={selected.portfolio_delta} limit={selected.max_portfolio_delta} />
              <GreeksBar label="Gamma" value={selected.portfolio_gamma} limit={selected.max_portfolio_gamma} />
              <GreeksBar label="Theta" value={selected.portfolio_theta} limit={selected.min_portfolio_theta} />
              <GreeksBar label="Vega" value={selected.portfolio_vega} limit={selected.max_portfolio_vega} />
            </div>
          </div>
        </div>
      )}

      {/* Broker Positions */}
      <div className="card">
        <div className="card-header">
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Live Positions
            {brokerPositions && ` (${brokerPositions.length})`}
          </h2>
        </div>
        {loadingBrokerPositions ? (
          <div className="card-body flex justify-center py-8">
            <Spinner />
          </div>
        ) : brokerPositions && brokerPositions.length > 0 ? (
          <BrokerPositionGrid positions={brokerPositions} />
        ) : (
          <EmptyState message="No broker positions synced" />
        )}
      </div>

      {/* Risk Factors */}
      {riskFactors && riskFactors.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
              Risk Factors ({riskFactors.length})
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-border-primary text-text-muted text-left">
                  <th className="px-3 py-2">Account</th>
                  <th className="px-3 py-2">Underlying</th>
                  <th className="px-3 py-2 text-right">Spot</th>
                  <th className="px-3 py-2 text-right">Delta</th>
                  <th className="px-3 py-2 text-right">Gamma</th>
                  <th className="px-3 py-2 text-right">Theta</th>
                  <th className="px-3 py-2 text-right">Vega</th>
                  <th className="px-3 py-2 text-right">Delta $</th>
                  <th className="px-3 py-2 text-right">Gamma $</th>
                  <th className="px-3 py-2 text-right">P&L</th>
                  <th className="px-3 py-2 text-right">Positions</th>
                </tr>
              </thead>
              <tbody>
                {riskFactors.map((rf) => (
                  <tr key={`${rf.account}-${rf.underlying}`} className="border-b border-border-primary hover:bg-bg-secondary">
                    <td className="px-3 py-2 text-text-muted">{rf.account ?? '-'}</td>
                    <td className="px-3 py-2 font-semibold text-text-primary">{rf.underlying}</td>
                    <td className="px-3 py-2 text-right">{rf.spot?.toFixed(2) ?? '-'}</td>
                    <td className="px-3 py-2 text-right">{rf.delta?.toFixed(2) ?? '-'}</td>
                    <td className="px-3 py-2 text-right">{rf.gamma?.toFixed(4) ?? '-'}</td>
                    <td className="px-3 py-2 text-right">{rf.theta?.toFixed(2) ?? '-'}</td>
                    <td className="px-3 py-2 text-right">{rf.vega?.toFixed(2) ?? '-'}</td>
                    <td className="px-3 py-2 text-right">{rf['delta_$']?.toLocaleString('en-US', { maximumFractionDigits: 0 }) ?? '-'}</td>
                    <td className="px-3 py-2 text-right">{rf['gamma_$']?.toLocaleString('en-US', { maximumFractionDigits: 0 }) ?? '-'}</td>
                    <td className={`px-3 py-2 text-right ${(rf.pnl ?? 0) > 0 ? 'text-pnl-profit' : (rf.pnl ?? 0) < 0 ? 'text-pnl-loss' : 'text-text-muted'}`}>
                      {rf.pnl?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? '-'}
                    </td>
                    <td className="px-3 py-2 text-right">{rf.positions}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                {(() => {
                  const totDelta$ = riskFactors.reduce((s, r) => s + (r['delta_$'] ?? 0), 0)
                  const totGamma$ = riskFactors.reduce((s, r) => s + (r['gamma_$'] ?? 0), 0)
                  const totPnl = riskFactors.reduce((s, r) => s + (r.pnl ?? 0), 0)
                  const totPositions = riskFactors.reduce((s, r) => s + (r.positions ?? 0), 0)
                  return (
                    <tr className="border-t-2 border-border-primary bg-bg-tertiary font-bold">
                      <td className="px-3 py-2"></td>
                      <td className="px-3 py-2 text-text-primary">TOTAL</td>
                      <td className="px-3 py-2"></td>
                      <td className="px-3 py-2"></td>
                      <td className="px-3 py-2"></td>
                      <td className="px-3 py-2"></td>
                      <td className="px-3 py-2"></td>
                      <td className="px-3 py-2 text-right">{totDelta$.toLocaleString('en-US', { maximumFractionDigits: 0 })}</td>
                      <td className="px-3 py-2 text-right">{totGamma$.toLocaleString('en-US', { maximumFractionDigits: 0 })}</td>
                      <td className={`px-3 py-2 text-right ${totPnl > 0 ? 'text-pnl-profit' : totPnl < 0 ? 'text-pnl-loss' : 'text-text-muted'}`}>
                        {totPnl.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </td>
                      <td className="px-3 py-2 text-right">{totPositions}</td>
                    </tr>
                  )
                })()}
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {/* Pending Orders */}
      {liveOrders && liveOrders.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
              Pending Orders ({liveOrders.length})
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="border-b border-border-primary text-text-muted text-left">
                  <th className="px-3 py-2">Broker</th>
                  <th className="px-3 py-2">Underlying</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Legs</th>
                  <th className="px-3 py-2 text-right">Price</th>
                  <th className="px-3 py-2 text-right">Filled</th>
                  <th className="px-3 py-2">Received</th>
                </tr>
              </thead>
              <tbody>
                {liveOrders.map((order) => (
                  <tr key={order.order_id} className="border-b border-border-primary hover:bg-bg-secondary">
                    <td className="px-3 py-2 text-text-muted">{order.broker}</td>
                    <td className="px-3 py-2 font-semibold text-text-primary">{order.underlying}</td>
                    <td className="px-3 py-2">
                      <span className="px-1.5 py-0.5 rounded text-2xs font-semibold bg-orange-900/30 text-orange-400 border border-orange-800">
                        {order.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-text-secondary">
                      {order.legs.map((leg: any, i: number) => (
                        <div key={i}>
                          {leg.action} {leg.quantity} {leg.symbol}
                        </div>
                      ))}
                    </td>
                    <td className="px-3 py-2 text-right">{order.price?.toFixed(2) ?? '-'}</td>
                    <td className="px-3 py-2 text-right">{order.filled_quantity}</td>
                    <td className="px-3 py-2 text-text-muted">
                      {order.received_at ? new Date(order.received_at).toLocaleString() : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Performance Tab
// ---------------------------------------------------------------------------

function PerformanceTab() {
  const { data: portfolios } = usePortfolios()
  const [selectedPortfolio, setSelectedPortfolio] = useState('all')

  const { data: metrics } = usePerformanceMetrics(selectedPortfolio === 'all' ? undefined : selectedPortfolio)
  const { data: weeklyPnl } = useWeeklyPnL(selectedPortfolio === 'all' ? 'all' : selectedPortfolio)
  const { data: strategyData } = useStrategyBreakdown(selectedPortfolio === 'all' ? 'all' : selectedPortfolio)
  const { data: sourceData } = useSourceAttribution(selectedPortfolio === 'all' ? 'all' : selectedPortfolio)

  const realPortfolios = useMemo(() => {
    if (!portfolios) return []
    return portfolios.filter((p) => p.portfolio_type === 'real' && !p.name.startsWith('research_'))
  }, [portfolios])

  const agg = useMemo(() => {
    if (!metrics || metrics.length === 0) return null
    const totalTrades = metrics.reduce((s, m) => s + m.total_trades, 0)
    const winningTrades = metrics.reduce((s, m) => s + m.winning_trades, 0)
    return {
      winRate: totalTrades > 0 ? winningTrades / totalTrades : 0,
      sharpe: metrics[0]?.sharpe_ratio ?? 0,
      profitFactor: metrics[0]?.profit_factor ?? 0,
      totalPnl: metrics.reduce((s, m) => s + m.total_pnl, 0),
      totalTrades,
    }
  }, [metrics])

  const strategyGridHeight = useMemo(() => {
    const count = strategyData?.length || 0
    return Math.max(Math.min(count * 28 + 36, 300), 120)
  }, [strategyData?.length])

  const sourceGridHeight = useMemo(() => {
    const count = sourceData?.length || 0
    return Math.max(Math.min(count * 28 + 36, 300), 120)
  }, [sourceData?.length])

  const hasData = agg && agg.totalTrades > 0

  return (
    <>
      {/* Portfolio selector tabs */}
      <div className="card">
        <div className="card-body">
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setSelectedPortfolio('all')}
              className={clsx(
                'px-2.5 py-1 rounded text-xs font-medium',
                selectedPortfolio === 'all' ? 'bg-accent-blue text-white' : 'bg-bg-tertiary text-text-secondary hover:bg-bg-hover',
              )}
            >
              All
            </button>
            {realPortfolios.map((p) => (
              <button
                key={p.name}
                onClick={() => setSelectedPortfolio(p.name)}
                className={clsx(
                  'px-2.5 py-1 rounded text-xs font-medium',
                  selectedPortfolio === p.name ? 'bg-accent-blue text-white' : 'bg-bg-tertiary text-text-secondary hover:bg-bg-hover',
                )}
              >
                {p.name}
              </button>
            ))}
          </div>
        </div>
      </div>

      {!hasData ? (
        <div className="card">
          <EmptyState message="No closed trades yet. Performance metrics will appear after trades are closed. Research portfolios will generate data automatically." />
        </div>
      ) : (
        <>
          {/* KPI row */}
          <div className="grid grid-cols-3 gap-3">
            <MetricCard
              label="Win Rate"
              value={`${(agg.winRate * 100).toFixed(0)}%`}
              subtext={`${agg.totalTrades} trades`}
            />
            <MetricCard
              label="Sharpe Ratio"
              value={agg.sharpe.toFixed(2)}
            />
            <MetricCard
              label="Profit Factor"
              value={agg.profitFactor.toFixed(2)}
            />
          </div>

          {/* Weekly P&L chart */}
          <div className="card">
            <div className="card-header">
              <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Weekly P&L</h2>
            </div>
            <div className="card-body" style={{ height: 250 }}>
              {weeklyPnl && weeklyPnl.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={weeklyPnl}>
                    <XAxis
                      dataKey="week_start"
                      tick={{ fontSize: 10, fill: '#555568' }}
                      tickFormatter={(v) => new Date(v).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    />
                    <YAxis yAxisId="left" tick={{ fontSize: 10, fill: '#555568' }} tickFormatter={(v) => `$${v}`} />
                    <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: '#555568' }} tickFormatter={(v) => `$${v}`} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1a1a2e', border: '1px solid #2a2a3e', fontSize: 11 }}
                    />
                    <Bar yAxisId="left" dataKey="pnl" name="Weekly P&L">
                      {weeklyPnl.map((entry, i) => (
                        <Cell key={i} fill={entry.pnl >= 0 ? '#22c55e' : '#ef4444'} />
                      ))}
                    </Bar>
                    <Line
                      yAxisId="right"
                      type="monotone"
                      dataKey="cumulative_pnl"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={false}
                      name="Cumulative"
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-text-muted text-xs">
                  No weekly P&L data
                </div>
              )}
            </div>
          </div>

          {/* Strategy + Source grids */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <div className="card">
              <div className="card-header">
                <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
                  Strategy Breakdown
                </h2>
              </div>
              {strategyData && strategyData.length > 0 ? (
                <div className="ag-theme-alpine-dark w-full" style={{ height: strategyGridHeight }}>
                  <AgGridReact
                    {...defaultGridOptions}
                    rowData={strategyData}
                    columnDefs={breakdownCols}
                    getRowId={(params) => params.data.label}
                  />
                </div>
              ) : (
                <EmptyState message="No strategy data" />
              )}
            </div>

            <div className="card">
              <div className="card-header">
                <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
                  Source Attribution
                </h2>
              </div>
              {sourceData && sourceData.length > 0 ? (
                <div className="ag-theme-alpine-dark w-full" style={{ height: sourceGridHeight }}>
                  <AgGridReact
                    {...defaultGridOptions}
                    rowData={sourceData}
                    columnDefs={sourceCols}
                    getRowId={(params) => params.data.label}
                  />
                </div>
              ) : (
                <EmptyState message="No source data" />
              )}
            </div>
          </div>
        </>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Capital Tab
// ---------------------------------------------------------------------------

function CapitalTab() {
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

  const sortedBySeverity = useMemo(() => {
    if (!capitalData) return []
    const order: Record<string, number> = { critical: 0, warning: 1, info: 2, ok: 3 }
    return [...capitalData].sort(
      (a, b) => (order[a.severity] ?? 4) - (order[b.severity] ?? 4),
    )
  }, [capitalData])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
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
    <>
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
    </>
  )
}

// ---------------------------------------------------------------------------
// Main PortfolioPage
// ---------------------------------------------------------------------------

export function PortfolioPage() {
  const { data: portfolios, isLoading: loadingPortfolios } = usePortfolios()
  const [selectedPortfolio, setSelectedPortfolio] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('real')
  const [activeTab, setActiveTab] = useState<TabId>('positions')

  const { data: brokerPositions, isLoading: loadingBrokerPositions } = useBrokerPositions(
    selectedPortfolio || undefined,
  )
  const { data: riskFactors } = useRiskFactors(selectedPortfolio || undefined)
  const { data: liveOrders } = useLiveOrders()

  const filteredPortfolios = useMemo(() => {
    if (!portfolios) return []
    const base = portfolios.filter((p) => !p.name.startsWith('research_'))
    if (viewMode === 'real') return base.filter((p) => p.portfolio_type === 'real')
    if (viewMode === 'whatif') return base.filter((p) => p.portfolio_type === 'what_if')
    return base
  }, [portfolios, viewMode])

  const selected = useMemo(
    () => portfolios?.find((p) => p.name === selectedPortfolio),
    [portfolios, selectedPortfolio],
  )

  // Aggregate totals — real USD portfolios only
  const totals = useMemo(() => {
    if (!portfolios) return null
    const real = portfolios.filter((p) => p.portfolio_type === 'real')
    return {
      equity: real.reduce((sum, p) => sum + p.total_equity, 0),
      dailyPnl: real.reduce((sum, p) => sum + p.daily_pnl, 0),
      totalPnl: real.reduce((sum, p) => sum + p.total_pnl, 0),
      delta: real.reduce((sum, p) => sum + p.portfolio_delta, 0),
      theta: real.reduce((sum, p) => sum + p.portfolio_theta, 0),
      openTrades: real.reduce((sum, p) => sum + (p.open_trade_count || 0), 0),
    }
  }, [portfolios])

  if (loadingPortfolios) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Agent ownership */}
      <div className="flex items-center gap-1.5">
        <AgentBadge agent="steward" />
      </div>

      {/* Summary header — visible across all tabs */}
      {totals && (
        <div className="card">
          <div className="card-body">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-6">
                <div>
                  <div className="text-2xs text-text-muted uppercase">Total Equity (Real)</div>
                  <div className="text-lg font-mono font-bold text-text-primary">
                    ${totals.equity.toLocaleString('en-US', { maximumFractionDigits: 0 })}
                  </div>
                </div>
                <div>
                  <div className="text-2xs text-text-muted uppercase">Daily P&L</div>
                  <PnLDisplay value={totals.dailyPnl} size="md" />
                </div>
                <div>
                  <div className="text-2xs text-text-muted uppercase">Total P&L</div>
                  <PnLDisplay value={totals.totalPnl} size="md" />
                </div>
                <div>
                  <div className="text-2xs text-text-muted uppercase">Net Delta</div>
                  <span className="text-sm font-mono text-text-primary">
                    {totals.delta >= 0 ? '+' : ''}{totals.delta.toFixed(1)}
                  </span>
                </div>
                <div>
                  <div className="text-2xs text-text-muted uppercase">Net Theta</div>
                  <span className="text-sm font-mono text-accent-green">
                    {totals.theta >= 0 ? '+' : ''}{totals.theta.toFixed(1)}/day
                  </span>
                </div>
                <div>
                  <div className="text-2xs text-text-muted uppercase">Open Trades</div>
                  <span className="text-sm font-mono text-text-primary">{totals.openTrades}</span>
                </div>
              </div>

              {/* View mode toggle */}
              <div className="flex items-center gap-1 bg-bg-tertiary rounded p-0.5">
                {(['real', 'whatif', 'all'] as ViewMode[]).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setViewMode(mode)}
                    className={clsx(
                      'px-2 py-1 rounded text-2xs font-semibold transition-colors',
                      viewMode === mode
                        ? 'bg-bg-active text-text-primary'
                        : 'text-text-muted hover:text-text-secondary',
                    )}
                  >
                    {mode === 'whatif' ? 'WhatIf' : mode.charAt(0).toUpperCase() + mode.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab bar */}
      <div className="flex items-center gap-1 border-b border-border-primary">
        {tabDefs.map(({ id, label }) => (
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
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'positions' && (
        <PositionsTab
          filteredPortfolios={filteredPortfolios}
          selectedPortfolio={selectedPortfolio}
          setSelectedPortfolio={setSelectedPortfolio}
          selected={selected}
          brokerPositions={brokerPositions}
          loadingBrokerPositions={loadingBrokerPositions}
          riskFactors={riskFactors}
          liveOrders={liveOrders}
        />
      )}
      {activeTab === 'performance' && <PerformanceTab />}
      {activeTab === 'capital' && <CapitalTab />}
    </div>
  )
}
