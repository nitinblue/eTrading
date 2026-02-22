import { useState, useMemo, useCallback } from 'react'
import { AgGridReact } from 'ag-grid-react'
import { ColDef, RowClickedEvent, ICellRendererParams } from 'ag-grid-community'
import { defaultGridOptions, numericColDef } from '../components/grids/gridTheme'
import {
  PnLRenderer,
  GreeksRenderer,
  DTERenderer,
} from '../components/grids/cellRenderers'
import { useRiskFactors, useBrokerPositions } from '../hooks/useRisk'
import { AgentBadge } from '../components/common/AgentBadge'
import { Spinner } from '../components/common/Spinner'
import { EmptyState } from '../components/common/EmptyState'
import { clsx } from 'clsx'
import type { RiskFactor, BrokerPosition } from '../api/types'

// --- Custom cell renderers ---

function RiskStatusRenderer({ value }: ICellRendererParams) {
  const colors: Record<string, string> = {
    OK: 'bg-green-900/30 text-green-400 border-green-800',
    WARNING: 'bg-yellow-900/30 text-yellow-400 border-yellow-800',
    BREACH: 'bg-red-900/30 text-red-400 border-red-800',
  }
  const cls = colors[value] || colors.OK
  return (
    <span className={`px-1.5 py-0.5 rounded text-2xs font-semibold border ${cls}`}>
      {value}
    </span>
  )
}

function DeltaDollarRenderer({ value }: ICellRendererParams) {
  if (value == null) return <span className="text-text-muted">--</span>
  const num = Number(value)
  const color = num > 0 ? 'text-pnl-profit' : num < 0 ? 'text-pnl-loss' : 'text-text-secondary'
  const sign = num > 0 ? '+' : ''
  return (
    <span className={`font-mono-num font-medium ${color}`}>
      {sign}${Math.abs(num).toLocaleString('en-US', { maximumFractionDigits: 0 })}
    </span>
  )
}

function SpotChangeRenderer({ value }: ICellRendererParams) {
  if (value == null) return <span className="text-text-muted">--</span>
  const num = Number(value)
  const color = num > 0 ? 'text-pnl-profit' : num < 0 ? 'text-pnl-loss' : 'text-pnl-zero'
  const sign = num > 0 ? '+' : ''
  return (
    <span className={`font-mono-num ${color}`}>
      {sign}{num.toFixed(2)}%
    </span>
  )
}

function LimitUsedRenderer({ value }: ICellRendererParams) {
  if (value == null) return <span className="text-text-muted">--</span>
  const pct = Math.min(Number(value), 100)
  const color =
    pct > 100 ? 'bg-red-500' :
    pct > 80 ? 'bg-yellow-500' :
    'bg-accent-blue'
  return (
    <div className="flex items-center gap-1.5 w-full">
      <div className="flex-1 h-2 bg-bg-tertiary rounded overflow-hidden">
        <div className={`h-full ${color} rounded`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className="font-mono-num text-text-secondary text-2xs w-8 text-right">
        {pct.toFixed(0)}%
      </span>
    </div>
  )
}

function PositionTypeRenderer({ value }: ICellRendererParams) {
  const colors: Record<string, string> = {
    CALL: 'bg-green-900/30 text-green-400 border-green-800',
    PUT: 'bg-red-900/30 text-red-400 border-red-800',
    STOCK: 'bg-blue-900/30 text-blue-400 border-blue-800',
  }
  const cls = colors[value] || 'bg-zinc-800/50 text-zinc-400 border-zinc-700'
  return (
    <span className={`px-1.5 py-0.5 rounded text-2xs font-semibold border ${cls}`}>
      {value}
    </span>
  )
}

// --- Column definitions ---

const riskFactorCols: ColDef[] = [
  {
    field: 'underlying',
    headerName: 'Underlying',
    width: 100,
    pinned: 'left',
    cellStyle: { fontWeight: 600 },
  },
  {
    field: 'spot',
    headerName: 'Spot',
    width: 90,
    ...numericColDef,
    valueFormatter: ({ value }) => value ? `$${Number(value).toFixed(2)}` : '--',
  },
  {
    field: 'spot_chg',
    headerName: 'Chg%',
    width: 75,
    ...numericColDef,
    cellRenderer: SpotChangeRenderer,
  },
  {
    field: 'delta',
    headerName: '\u0394',
    width: 80,
    ...numericColDef,
    cellRenderer: GreeksRenderer,
  },
  {
    field: 'gamma',
    headerName: '\u0393',
    width: 80,
    ...numericColDef,
    cellRenderer: GreeksRenderer,
  },
  {
    field: 'theta',
    headerName: '\u0398',
    width: 80,
    ...numericColDef,
    cellStyle: { ...numericColDef.cellStyle, color: '#22c55e' },
    valueFormatter: ({ value }) => value != null ? `${Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(2)}` : '--',
  },
  {
    field: 'vega',
    headerName: '\u03BD',
    width: 80,
    ...numericColDef,
    cellRenderer: GreeksRenderer,
  },
  {
    field: 'delta_$',
    headerName: 'Delta $',
    width: 100,
    ...numericColDef,
    cellRenderer: DeltaDollarRenderer,
  },
  {
    field: 'positions',
    headerName: 'Pos',
    width: 60,
    ...numericColDef,
  },
  {
    field: 'long',
    headerName: 'Long',
    width: 55,
    ...numericColDef,
    cellStyle: { ...numericColDef.cellStyle, color: '#22c55e' },
  },
  {
    field: 'short',
    headerName: 'Short',
    width: 55,
    ...numericColDef,
    cellStyle: { ...numericColDef.cellStyle, color: '#ef4444' },
  },
  {
    field: 'pnl',
    headerName: 'P&L',
    width: 100,
    ...numericColDef,
    cellRenderer: PnLRenderer,
    sort: 'desc',
  },
  {
    field: 'limit_used',
    headerName: 'Limit Used',
    width: 110,
    cellRenderer: LimitUsedRenderer,
  },
  {
    field: 'status',
    headerName: 'Status',
    width: 85,
    cellRenderer: RiskStatusRenderer,
  },
]

const brokerPositionCols: ColDef[] = [
  {
    field: 'symbol',
    headerName: 'Symbol',
    width: 220,
    pinned: 'left',
    cellStyle: { fontWeight: 500 },
  },
  {
    field: 'underlying',
    headerName: 'UL',
    width: 75,
  },
  {
    field: 'type',
    headerName: 'Type',
    width: 65,
    cellRenderer: PositionTypeRenderer,
  },
  {
    field: 'strike',
    headerName: 'Strike',
    width: 80,
    ...numericColDef,
    valueFormatter: ({ value }) => value != null ? `$${Number(value).toFixed(0)}` : '--',
  },
  {
    field: 'expiry',
    headerName: 'Expiry',
    width: 100,
    valueFormatter: ({ value }) =>
      value ? new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' }) : '--',
    cellStyle: { color: '#8888a0' },
  },
  {
    field: 'dte',
    headerName: 'DTE',
    width: 60,
    ...numericColDef,
    cellRenderer: DTERenderer,
  },
  {
    field: 'qty',
    headerName: 'Qty',
    width: 60,
    ...numericColDef,
    cellStyle: (params) => ({
      ...numericColDef.cellStyle,
      color: params.value > 0 ? '#22c55e' : params.value < 0 ? '#ef4444' : '#8888a0',
      fontWeight: 600,
    }),
  },
  {
    field: 'entry',
    headerName: 'Entry',
    width: 80,
    ...numericColDef,
    valueFormatter: ({ value }) => value ? `$${Number(value).toFixed(2)}` : '--',
  },
  {
    field: 'mark',
    headerName: 'Mark',
    width: 80,
    ...numericColDef,
    valueFormatter: ({ value }) => value ? `$${Number(value).toFixed(2)}` : '--',
  },
  {
    field: 'delta',
    headerName: '\u0394',
    width: 75,
    ...numericColDef,
    cellRenderer: GreeksRenderer,
  },
  {
    field: 'gamma',
    headerName: '\u0393',
    width: 75,
    ...numericColDef,
    cellRenderer: GreeksRenderer,
  },
  {
    field: 'theta',
    headerName: '\u0398',
    width: 75,
    ...numericColDef,
    cellStyle: { ...numericColDef.cellStyle, color: '#22c55e' },
    valueFormatter: ({ value }) => value != null ? `${Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(2)}` : '--',
  },
  {
    field: 'vega',
    headerName: '\u03BD',
    width: 75,
    ...numericColDef,
    cellRenderer: GreeksRenderer,
  },
  {
    field: 'iv',
    headerName: 'IV',
    width: 60,
    ...numericColDef,
    valueFormatter: ({ value }) => value != null ? `${Number(value).toFixed(0)}%` : '--',
    cellStyle: { ...numericColDef.cellStyle, color: '#c084fc' },
  },
  {
    field: 'pnl',
    headerName: 'P&L',
    width: 100,
    ...numericColDef,
    cellRenderer: PnLRenderer,
    sort: 'desc',
  },
  {
    field: 'pnl_pct',
    headerName: 'P&L %',
    width: 80,
    ...numericColDef,
    cellStyle: (params) => ({
      ...numericColDef.cellStyle,
      color: params.value > 0 ? '#22c55e' : params.value < 0 ? '#ef4444' : '#555568',
    }),
    valueFormatter: ({ value }) => value != null ? `${Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(1)}%` : '--',
  },
]

// --- Page component ---

export function RiskPage() {
  const { data: riskFactors, isLoading: loadingFactors } = useRiskFactors()
  const { data: brokerPositions, isLoading: loadingPositions } = useBrokerPositions()
  const [selectedUnderlying, setSelectedUnderlying] = useState<string | null>(null)

  const onRiskFactorRowClicked = useCallback((event: RowClickedEvent) => {
    const row = event.data as RiskFactor
    setSelectedUnderlying((prev) => prev === row.underlying ? null : row.underlying)
  }, [])

  const filteredPositions = useMemo(() => {
    if (!brokerPositions) return []
    if (!selectedUnderlying) return brokerPositions
    return brokerPositions.filter((p) => p.underlying === selectedUnderlying)
  }, [brokerPositions, selectedUnderlying])

  // Aggregate totals
  const totals = useMemo(() => {
    if (!riskFactors || riskFactors.length === 0) return null
    return {
      delta: riskFactors.reduce((s, r) => s + r.delta, 0),
      gamma: riskFactors.reduce((s, r) => s + r.gamma, 0),
      theta: riskFactors.reduce((s, r) => s + r.theta, 0),
      vega: riskFactors.reduce((s, r) => s + r.vega, 0),
      pnl: riskFactors.reduce((s, r) => s + r.pnl, 0),
      positions: riskFactors.reduce((s, r) => s + r.positions, 0),
      underlyings: riskFactors.length,
    }
  }, [riskFactors])

  const riskGridHeight = useMemo(() => {
    const count = riskFactors?.length || 0
    return Math.max(Math.min(count * 28 + 36, 350), 150)
  }, [riskFactors?.length])

  const posGridHeight = useMemo(() => {
    const count = filteredPositions.length
    return Math.max(Math.min(count * 28 + 36, 500), 200)
  }, [filteredPositions.length])

  if (loadingFactors && loadingPositions) {
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
        <AgentBadge agent="risk" />
        <AgentBadge agent="circuit_breaker" />
      </div>
      {/* Summary header */}
      {totals && (
        <div className="card">
          <div className="card-body">
            <div className="flex items-center gap-6">
              <div>
                <div className="text-2xs text-text-muted uppercase">Net Delta</div>
                <span className={clsx(
                  'text-lg font-mono font-bold',
                  totals.delta > 0 ? 'text-pnl-profit' : totals.delta < 0 ? 'text-pnl-loss' : 'text-text-primary',
                )}>
                  {totals.delta >= 0 ? '+' : ''}{totals.delta.toFixed(1)}
                </span>
              </div>
              <div>
                <div className="text-2xs text-text-muted uppercase">Net Gamma</div>
                <span className="text-sm font-mono text-text-primary">
                  {totals.gamma >= 0 ? '+' : ''}{totals.gamma.toFixed(2)}
                </span>
              </div>
              <div>
                <div className="text-2xs text-text-muted uppercase">Net Theta</div>
                <span className="text-sm font-mono text-accent-green">
                  {totals.theta >= 0 ? '+' : ''}{totals.theta.toFixed(1)}/day
                </span>
              </div>
              <div>
                <div className="text-2xs text-text-muted uppercase">Net Vega</div>
                <span className="text-sm font-mono text-text-primary">
                  {totals.vega >= 0 ? '+' : ''}{totals.vega.toFixed(1)}
                </span>
              </div>
              <div>
                <div className="text-2xs text-text-muted uppercase">Unrealized P&L</div>
                <span className={clsx(
                  'text-sm font-mono font-medium',
                  totals.pnl > 0 ? 'text-pnl-profit' : totals.pnl < 0 ? 'text-pnl-loss' : 'text-pnl-zero',
                )}>
                  {totals.pnl >= 0 ? '+' : ''}${Math.abs(totals.pnl).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </span>
              </div>
              <div>
                <div className="text-2xs text-text-muted uppercase">Underlyings</div>
                <span className="text-sm font-mono text-text-primary">{totals.underlyings}</span>
              </div>
              <div>
                <div className="text-2xs text-text-muted uppercase">Positions</div>
                <span className="text-sm font-mono text-text-primary">{totals.positions}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Risk Factors grid */}
      <div className="card">
        <div className="card-header flex items-center justify-between">
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Risk Factors by Underlying
            {riskFactors && ` (${riskFactors.length})`}
          </h2>
          {selectedUnderlying && (
            <button
              onClick={() => setSelectedUnderlying(null)}
              className="text-2xs text-accent-blue hover:underline"
            >
              Clear filter ({selectedUnderlying})
            </button>
          )}
        </div>
        {loadingFactors ? (
          <div className="card-body flex justify-center py-8">
            <Spinner />
          </div>
        ) : riskFactors && riskFactors.length > 0 ? (
          <div className="ag-theme-alpine-dark w-full" style={{ height: riskGridHeight }}>
            <AgGridReact
              {...defaultGridOptions}
              rowData={riskFactors}
              columnDefs={riskFactorCols}
              onRowClicked={onRiskFactorRowClicked}
              rowStyle={{ cursor: 'pointer' }}
              getRowId={(params) => params.data.id}
              rowClassRules={{
                'bg-bg-active': (params) => params.data?.underlying === selectedUnderlying,
              }}
            />
          </div>
        ) : (
          <EmptyState message="No risk factors available. Start the workflow engine to populate containers." />
        )}
      </div>

      {/* Broker Positions grid */}
      <div className="card">
        <div className="card-header flex items-center justify-between">
          <h2 className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            {selectedUnderlying
              ? `${selectedUnderlying} Positions`
              : 'All Broker Positions'}
            {` (${filteredPositions.length})`}
          </h2>
        </div>
        {loadingPositions ? (
          <div className="card-body flex justify-center py-8">
            <Spinner />
          </div>
        ) : filteredPositions.length > 0 ? (
          <div className="ag-theme-alpine-dark w-full" style={{ height: posGridHeight }}>
            <AgGridReact
              {...defaultGridOptions}
              rowData={filteredPositions}
              columnDefs={brokerPositionCols}
              getRowId={(params) => params.data.id}
            />
          </div>
        ) : (
          <EmptyState
            message={
              selectedUnderlying
                ? `No positions for ${selectedUnderlying}`
                : 'No broker positions synced. Run a workflow cycle to sync positions from your broker.'
            }
          />
        )}
      </div>
    </div>
  )
}
