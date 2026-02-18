import { AgGridReact } from 'ag-grid-react'
import { ColDef } from 'ag-grid-community'
import { defaultGridOptions, numericColDef } from './gridTheme'
import { PnLRenderer, CurrencyRenderer, PercentRenderer } from './cellRenderers'
import type { Portfolio } from '../../api/types'

interface PortfolioGridProps {
  portfolios: Portfolio[]
  onPortfolioClick?: (name: string) => void
}

const columnDefs: ColDef[] = [
  {
    field: 'name',
    headerName: 'Portfolio',
    width: 160,
    cellStyle: { fontWeight: 600 },
  },
  {
    field: 'portfolio_type',
    headerName: 'Type',
    width: 80,
    cellRenderer: ({ value }: { value: string }) => (
      <span className={`px-1 py-0.5 rounded text-2xs font-semibold ${
        value === 'what_if' ? 'bg-blue-900/30 text-blue-400' :
        value === 'real' ? 'bg-green-900/30 text-green-400' :
        'bg-zinc-800/50 text-zinc-400'
      }`}>
        {value?.toUpperCase()}
      </span>
    ),
  },
  {
    field: 'broker',
    headerName: 'Broker',
    width: 100,
    cellStyle: { color: '#8888a0', fontSize: '11px' },
  },
  {
    field: 'total_equity',
    headerName: 'Equity',
    width: 110,
    ...numericColDef,
    cellRenderer: CurrencyRenderer,
  },
  {
    field: 'daily_pnl',
    headerName: 'Daily P&L',
    width: 100,
    ...numericColDef,
    cellRenderer: PnLRenderer,
  },
  {
    field: 'total_pnl',
    headerName: 'Total P&L',
    width: 100,
    ...numericColDef,
    cellRenderer: PnLRenderer,
  },
  {
    field: 'portfolio_delta',
    headerName: '\u0394 Delta',
    width: 85,
    ...numericColDef,
    valueFormatter: ({ value }) => value != null ? (value >= 0 ? '+' : '') + Number(value).toFixed(1) : '--',
  },
  {
    field: 'portfolio_theta',
    headerName: '\u0398 Theta',
    width: 85,
    ...numericColDef,
    valueFormatter: ({ value }) => value != null ? (value >= 0 ? '+' : '') + Number(value).toFixed(1) : '--',
  },
  {
    field: 'portfolio_vega',
    headerName: '\u03BD Vega',
    width: 85,
    ...numericColDef,
    valueFormatter: ({ value }) => value != null ? (value >= 0 ? '+' : '') + Number(value).toFixed(1) : '--',
  },
  {
    field: 'deployed_pct',
    headerName: 'Deployed',
    width: 85,
    ...numericColDef,
    cellRenderer: PercentRenderer,
  },
  {
    field: 'var_1d_95',
    headerName: 'VaR 95%',
    width: 90,
    ...numericColDef,
    cellRenderer: CurrencyRenderer,
  },
  {
    field: 'open_trade_count',
    headerName: 'Open',
    width: 60,
    ...numericColDef,
  },
]

export function PortfolioGrid({ portfolios, onPortfolioClick }: PortfolioGridProps) {
  return (
    <div className="ag-theme-alpine-dark w-full" style={{ height: Math.min(portfolios.length * 28 + 36, 350) }}>
      <AgGridReact
        {...defaultGridOptions}
        rowData={portfolios}
        columnDefs={columnDefs}
        onRowClicked={(e) => onPortfolioClick?.(e.data?.name)}
        rowStyle={{ cursor: 'pointer' }}
        getRowId={(params) => params.data.id}
      />
    </div>
  )
}
