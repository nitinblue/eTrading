import { useState, useCallback, useMemo } from 'react'
import { AgGridReact } from 'ag-grid-react'
import { ColDef, RowClickedEvent } from 'ag-grid-community'
import { defaultGridOptions, numericColDef } from './gridTheme'
import {
  PnLRenderer,
  StatusBadgeRenderer,
  DTERenderer,
  GreeksRenderer,
  TradeTypeRenderer,
} from './cellRenderers'
import type { Trade } from '../../api/types'
import { TradeDetailModal } from '../modals/TradeDetailModal'

interface PositionGridProps {
  trades: Trade[]
}

const columnDefs: ColDef[] = [
  {
    field: 'underlying_symbol',
    headerName: 'Underlying',
    width: 90,
    cellStyle: { fontWeight: 600 },
    pinned: 'left',
  },
  {
    field: 'strategy_type',
    headerName: 'Strategy',
    width: 140,
    valueFormatter: ({ value }) => value?.replace(/_/g, ' ') || '--',
    cellStyle: { color: '#8888a0' },
  },
  {
    field: 'trade_status',
    headerName: 'Status',
    width: 90,
    cellRenderer: StatusBadgeRenderer,
  },
  {
    field: 'trade_type',
    headerName: 'Type',
    width: 70,
    cellRenderer: TradeTypeRenderer,
  },
  {
    field: 'entry_price',
    headerName: 'Entry',
    width: 80,
    ...numericColDef,
    valueFormatter: ({ value }) => value ? `$${Number(value).toFixed(2)}` : '--',
  },
  {
    field: 'current_price',
    headerName: 'Current',
    width: 80,
    ...numericColDef,
    valueFormatter: ({ value }) => value ? `$${Number(value).toFixed(2)}` : '--',
  },
  {
    field: 'total_pnl',
    headerName: 'P&L',
    width: 95,
    ...numericColDef,
    cellRenderer: PnLRenderer,
    sort: 'desc',
  },
  {
    field: 'current_delta',
    headerName: '\u0394',
    width: 70,
    ...numericColDef,
    cellRenderer: GreeksRenderer,
  },
  {
    field: 'current_theta',
    headerName: '\u0398',
    width: 70,
    ...numericColDef,
    cellRenderer: GreeksRenderer,
  },
  {
    field: 'current_vega',
    headerName: '\u03BD',
    width: 70,
    ...numericColDef,
    cellRenderer: GreeksRenderer,
  },
  {
    field: 'dte',
    headerName: 'DTE',
    width: 65,
    ...numericColDef,
    cellRenderer: DTERenderer,
  },
  {
    field: 'trade_source',
    headerName: 'Source',
    width: 95,
    cellStyle: { color: '#555568', fontSize: '11px' },
    valueFormatter: ({ value }) => value?.replace('screener_', '') || '--',
  },
  {
    field: 'opened_at',
    headerName: 'Opened',
    width: 90,
    valueFormatter: ({ value }) => value ? new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '--',
    cellStyle: { color: '#555568' },
  },
  {
    headerName: 'Legs',
    width: 50,
    ...numericColDef,
    valueGetter: ({ data }) => data?.legs?.length || 0,
  },
]

export function PositionGrid({ trades }: PositionGridProps) {
  const [selectedTrade, setSelectedTrade] = useState<Trade | null>(null)

  const onRowClicked = useCallback((event: RowClickedEvent) => {
    setSelectedTrade(event.data as Trade)
  }, [])

  const gridHeight = useMemo(() => {
    return Math.max(Math.min(trades.length * 28 + 36, 600), 200)
  }, [trades.length])

  return (
    <>
      <div className="ag-theme-alpine-dark w-full" style={{ height: gridHeight }}>
        <AgGridReact
          {...defaultGridOptions}
          rowData={trades}
          columnDefs={columnDefs}
          onRowClicked={onRowClicked}
          rowStyle={{ cursor: 'pointer' }}
          getRowId={(params) => params.data.id}
          rowClassRules={{
            'opacity-60': (params) => params.data?.trade_type === 'what_if',
          }}
        />
      </div>

      {selectedTrade && (
        <TradeDetailModal
          trade={selectedTrade}
          onClose={() => setSelectedTrade(null)}
        />
      )}
    </>
  )
}
