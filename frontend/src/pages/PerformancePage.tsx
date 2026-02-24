import { useState, useMemo } from 'react'
import { AgGridReact } from 'ag-grid-react'
import { ColDef } from 'ag-grid-community'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  Line, ComposedChart, Cell,
} from 'recharts'
import { defaultGridOptions, numericColDef } from '../components/grids/gridTheme'
import { AgentBadge } from '../components/common/AgentBadge'
import { PnLRenderer } from '../components/grids/cellRenderers'
import { usePerformanceMetrics, useWeeklyPnL, useStrategyBreakdown, useSourceAttribution } from '../hooks/usePerformance'
import { usePortfolios } from '../hooks/usePortfolios'
import { Spinner } from '../components/common/Spinner'
import { EmptyState } from '../components/common/EmptyState'
import { clsx } from 'clsx'

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

export function PerformancePage() {
  const { data: portfolios, isLoading: loadingPf } = usePortfolios()
  const [selectedPortfolio, setSelectedPortfolio] = useState('all')

  const { data: metrics } = usePerformanceMetrics(selectedPortfolio === 'all' ? undefined : selectedPortfolio)
  const { data: weeklyPnl } = useWeeklyPnL(selectedPortfolio === 'all' ? 'all' : selectedPortfolio)
  const { data: strategyData } = useStrategyBreakdown(selectedPortfolio === 'all' ? 'all' : selectedPortfolio)
  const { data: sourceData } = useSourceAttribution(selectedPortfolio === 'all' ? 'all' : selectedPortfolio)

  const realPortfolios = useMemo(() => {
    if (!portfolios) return []
    return portfolios.filter((p) => p.portfolio_type === 'real' && !p.name.startsWith('research_'))
  }, [portfolios])

  // Aggregate metrics
  const agg = useMemo(() => {
    if (!metrics || metrics.length === 0) return null
    // Sum across all returned metrics
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

  if (loadingPf) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    )
  }

  const hasData = agg && agg.totalTrades > 0

  return (
    <div className="space-y-3">
      {/* Agent ownership */}
      <div className="flex items-center gap-1.5">
        <AgentBadge agent="atlas" />
        <AgentBadge agent="maverick" />
      </div>
      {/* Portfolio tabs */}
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
    </div>
  )
}

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
