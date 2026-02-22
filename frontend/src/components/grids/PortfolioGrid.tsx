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
    width: 150,
    cellStyle: { fontWeight: 600 },
  },
  {
    field: 'portfolio_type',
    headerName: 'Type',
    width: 70,
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
    width: 90,
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
    field: 'initial_capital',
    headerName: 'Initial Cap',
    width: 110,
    ...numericColDef,
    cellRenderer: CurrencyRenderer,
  },
  {
    field: 'cash_balance',
    headerName: 'Cash',
    width: 100,
    ...numericColDef,
    cellRenderer: CurrencyRenderer,
  },
  {
    field: 'buying_power',
    headerName: 'Buying Power',
    width: 110,
    ...numericColDef,
    cellRenderer: CurrencyRenderer,
  },
  {
    field: 'margin_used',
    headerName: 'Margin Used',
    width: 110,
    ...numericColDef,
    cellRenderer: CurrencyRenderer,
  },
  {
    field: 'available_margin',
    headerName: 'Avail Margin',
    width: 110,
    ...numericColDef,
    cellRenderer: CurrencyRenderer,
  },
  {
    field: 'margin_utilization_pct',
    headerName: 'Margin %',
    width: 85,
    ...numericColDef,
    cellRenderer: ({ value }: { value: number | null }) => {
      if (value == null) return '--'
      const color = value >= 85 ? 'text-red-400' : value >= 70 ? 'text-amber-400' : 'text-green-400'
      return <span className={`font-mono ${color}`}>{value.toFixed(1)}%</span>
    },
  },
  {
    field: 'margin_buffer',
    headerName: 'Buffer Req',
    width: 110,
    ...numericColDef,
    headerTooltip: 'Required buffer = margin_used × buffer_multiplier (from risk_config.yaml)',
    cellRenderer: CurrencyRenderer,
  },
  {
    field: 'margin_buffer_remaining',
    headerName: 'Buffer Avail',
    width: 110,
    ...numericColDef,
    cellRenderer: ({ value }: { value: number | null }) => {
      if (value == null) return '--'
      const color = value < 0 ? 'text-red-400' : value < 1000 ? 'text-amber-400' : 'text-green-400'
      return <span className={`font-mono ${color}`}>{value.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })}</span>
    },
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
    field: 'risk_pct_of_margin',
    headerName: 'Risk/Margin',
    width: 95,
    ...numericColDef,
    headerTooltip: 'VaR as % of margin used',
    cellRenderer: ({ value }: { value: number | null }) => {
      if (value == null || value === 0) return <span className="text-text-muted">--</span>
      const color = value >= 50 ? 'text-red-400' : value >= 25 ? 'text-amber-400' : 'text-text-secondary'
      return <span className={`font-mono ${color}`}>{value.toFixed(1)}%</span>
    },
  },
  {
    field: 'total_pnl',
    headerName: 'Total P&L',
    width: 100,
    ...numericColDef,
    cellRenderer: PnLRenderer,
  },
  {
    field: 'daily_pnl',
    headerName: 'Daily P&L',
    width: 100,
    ...numericColDef,
    cellRenderer: PnLRenderer,
  },
  {
    field: 'currency',
    headerName: 'Ccy',
    width: 50,
    cellStyle: { color: '#8888a0', fontSize: '11px' },
  },
  {
    field: 'open_trade_count',
    headerName: 'Open',
    width: 55,
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
