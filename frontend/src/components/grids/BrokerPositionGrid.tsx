import { useMemo } from 'react'
import { AgGridReact } from 'ag-grid-react'
import { ColDef } from 'ag-grid-community'
import { defaultGridOptions, numericColDef } from './gridTheme'
import { PnLRenderer, DTERenderer, GreeksRenderer } from './cellRenderers'
import type { BrokerPosition } from '../../api/types'

interface BrokerPositionGridProps {
  positions: BrokerPosition[]
}

const columnDefs: ColDef[] = [
  {
    field: 'account',
    headerName: 'Account',
    width: 110,
    cellStyle: { color: '#8888a0', fontSize: '11px' },
    pinned: 'left',
  },
  {
    field: 'underlying',
    headerName: 'Underlying',
    width: 85,
    cellStyle: { fontWeight: 600 },
    pinned: 'left',
  },
  {
    field: 'symbol',
    headerName: 'Symbol',
    width: 180,
    cellStyle: { color: '#8888a0', fontSize: '11px' },
  },
  {
    field: 'type',
    headerName: 'Type',
    width: 60,
    cellStyle: { fontSize: '11px' },
  },
  {
    field: 'strike',
    headerName: 'Strike',
    width: 70,
    ...numericColDef,
    valueFormatter: ({ value }) => value ? Number(value).toFixed(0) : '--',
  },
  {
    field: 'expiry',
    headerName: 'Expiry',
    width: 85,
    valueFormatter: ({ value }) => {
      if (!value) return '--'
      const d = new Date(value)
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' })
    },
    cellStyle: { color: '#555568' },
  },
  {
    field: 'dte',
    headerName: 'DTE',
    width: 55,
    ...numericColDef,
    cellRenderer: DTERenderer,
  },
  {
    field: 'qty',
    headerName: 'Qty',
    width: 50,
    ...numericColDef,
    cellStyle: (params) => ({
      ...numericColDef.cellStyle,
      color: (params.value ?? 0) > 0 ? '#22c55e' : (params.value ?? 0) < 0 ? '#ef4444' : '#8888a0',
    }),
  },
  {
    field: 'entry',
    headerName: 'Entry',
    width: 75,
    ...numericColDef,
    valueFormatter: ({ value }) => value ? Number(value).toFixed(2) : '--',
  },
  {
    field: 'mark',
    headerName: 'Mark',
    width: 75,
    ...numericColDef,
    valueFormatter: ({ value }) => value ? Number(value).toFixed(2) : '--',
  },
  {
    field: 'pnl',
    headerName: 'P&L',
    width: 90,
    ...numericColDef,
    cellRenderer: PnLRenderer,
    sort: 'desc',
  },
  {
    field: 'pnl_pct',
    headerName: 'P&L %',
    width: 70,
    ...numericColDef,
    valueFormatter: ({ value }) => value != null ? `${Number(value).toFixed(1)}%` : '--',
    cellStyle: (params) => ({
      ...numericColDef.cellStyle,
      color: (params.value ?? 0) > 0 ? '#22c55e' : (params.value ?? 0) < 0 ? '#ef4444' : '#8888a0',
    }),
  },
  {
    field: 'delta',
    headerName: 'Delta',
    width: 65,
    ...numericColDef,
    cellRenderer: GreeksRenderer,
  },
  {
    field: 'gamma',
    headerName: 'Gamma',
    width: 65,
    ...numericColDef,
    cellRenderer: GreeksRenderer,
  },
  {
    field: 'theta',
    headerName: 'Theta',
    width: 65,
    ...numericColDef,
    cellRenderer: GreeksRenderer,
  },
  {
    field: 'vega',
    headerName: 'Vega',
    width: 65,
    ...numericColDef,
    cellRenderer: GreeksRenderer,
  },
  {
    field: 'iv',
    headerName: 'IV',
    width: 60,
    ...numericColDef,
    valueFormatter: ({ value }) => value != null ? `${Number(value).toFixed(0)}%` : '--',
  },
]

export function BrokerPositionGrid({ positions }: BrokerPositionGridProps) {
  const gridHeight = useMemo(() => {
    // +1 row for pinned bottom totals
    return Math.max(Math.min((positions.length + 1) * 28 + 36, 600), 150)
  }, [positions.length])

  const pinnedBottomRowData = useMemo(() => {
    if (positions.length === 0) return []
    return [{
      id: '__totals__',
      account: '',
      underlying: 'TOTAL',
      symbol: '',
      type: '',
      strike: null,
      expiry: null,
      dte: null,
      qty: null,
      entry: null,
      mark: null,
      pnl: positions.reduce((sum, p) => sum + (p.pnl ?? 0), 0),
      pnl_pct: null,
      delta: null,
      gamma: null,
      theta: positions.reduce((sum, p) => sum + (p.theta ?? 0), 0),
      vega: null,
      iv: null,
    }]
  }, [positions])

  return (
    <div className="ag-theme-alpine-dark w-full" style={{ height: gridHeight }}>
      <AgGridReact
        {...defaultGridOptions}
        rowData={positions}
        columnDefs={columnDefs}
        getRowId={(params) => params.data.id}
        pinnedBottomRowData={pinnedBottomRowData}
        getRowStyle={(params) => {
          if (params.node.rowPinned === 'bottom') {
            return { fontWeight: '700', background: 'rgba(255,255,255,0.04)', borderTop: '2px solid #333' }
          }
          return undefined
        }}
      />
    </div>
  )
}
