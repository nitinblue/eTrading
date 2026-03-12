import { useState, useMemo, useCallback, useRef, useEffect } from 'react'
import { clsx } from 'clsx'
import { Columns3 } from 'lucide-react'
import { AgGridReact } from 'ag-grid-react'
import type { ColDef, ColGroupDef, GridReadyEvent, GridApi, ValueFormatterParams, ICellRendererParams, RowClassParams } from 'ag-grid-community'
import { usePortfolios } from '../hooks/usePortfolios'
import { useTradingDashboard } from '../hooks/useTradingDashboard'
import { Spinner } from '../components/common/Spinner'
import { TerminalPanel } from '../components/terminal/TerminalPanel'
import type {
  TradingDashboardStrategy,
  TradingDashboardPosition,
  TradingDashboardRiskFactor,
  TradingDashboardPortfolio,
} from '../api/types'

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------
const n = (v: number | null | undefined, d = 2) => v == null ? '--' : v.toFixed(d)
const n$ = (v: number | null | undefined) =>
  v == null ? '--' : v < 0
    ? `-$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
    : `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
const pct = (v: number | null | undefined, d = 1) => v == null ? '--' : `${v.toFixed(d)}%`
const g = (v: number | null | undefined, d = 2) => v == null ? '--' : `${v >= 0 ? '+' : ''}${v.toFixed(d)}`
const clr = (v: number | null | undefined) => !v ? 'text-text-muted' : v > 0 ? 'text-accent-green' : 'text-accent-red'

// ---------------------------------------------------------------------------
// KPI Pill
// ---------------------------------------------------------------------------
function KPI({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="text-[10px] text-text-muted">{label}</span>
      <span className={clsx('text-[11px] font-mono font-semibold', color || 'text-text-primary')}>{value}</span>
    </span>
  )
}

// ---------------------------------------------------------------------------
// Summary Strip
// ---------------------------------------------------------------------------
function SummaryStrip({ p, showWhatIf }: { p: TradingDashboardPortfolio; showWhatIf?: boolean }) {
  return (
    <div className="flex items-center gap-4 flex-wrap px-2 py-1 bg-bg-secondary border-b border-border-secondary">
      <KPI label="Equity" value={n$(p.total_equity)} />
      <KPI label="Cash" value={n$(p.cash_balance)} />
      <KPI label="BP" value={n$(p.buying_power)} />
      <KPI label="Deployed" value={pct(p.capital_deployed_pct)} color={p.capital_deployed_pct > 60 ? 'text-accent-yellow' : undefined} />
      <span className="text-border-secondary">|</span>
      {showWhatIf ? (
        <>
          <KPI label={'\u0394+WI'} value={g(p.net_delta_with_whatif, 1)} color={clr(p.net_delta_with_whatif)} />
          <KPI label={'\u0398+WI'} value={`$${n(p.net_theta_with_whatif, 0)}`} color="text-accent-green" />
        </>
      ) : (
        <>
          <KPI label={'\u0394'} value={g(p.net_delta, 1)} color={clr(p.net_delta)} />
          <KPI label={'\u0398/d'} value={`$${n(p.net_theta, 0)}`} color="text-accent-green" />
        </>
      )}
      <KPI label={'\u0393'} value={n(p.net_gamma, 4)} />
      <KPI label={'\u03BD'} value={g(p.net_vega, 1)} color={clr(-Math.abs(p.net_vega))} />
      <span className="text-border-secondary">|</span>
      <KPI label="VaR" value={n$(p.var_1d_95)} />
      <KPI label={'\u0394 util'} value={pct(p.delta_utilization_pct)} color={p.delta_utilization_pct > 70 ? 'text-accent-red' : undefined} />
      <span className="text-text-muted text-[10px]">Pos:{p.open_positions} Strat:{p.open_strategies}</span>
      {showWhatIf && p.whatif_count > 0 && (
        <span className="text-accent-blue text-[10px] font-semibold">+{p.whatif_count} WhatIf</span>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// AG Grid Cell Renderers (inline, terminal-grade)
// ---------------------------------------------------------------------------
function PnlCell({ value }: ICellRendererParams) {
  if (value == null) return <span className="text-zinc-500">--</span>
  const v = Number(value)
  const color = v > 0 ? '#22c55e' : v < 0 ? '#ef4444' : '#555568'
  const sign = v > 0 ? '+' : ''
  // Background intensity for heat-map effect
  const absV = Math.abs(v)
  const intensity = Math.min(absV / 2000, 0.15) // cap at 15% opacity
  const bgColor = v > 0 ? `rgba(34,197,94,${intensity})` : v < 0 ? `rgba(239,68,68,${intensity})` : 'transparent'
  return (
    <span style={{ color, fontWeight: 500, backgroundColor: bgColor, padding: '0 3px', borderRadius: '2px' }}>
      {sign}${Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
    </span>
  )
}

function PnlPctCell({ value }: ICellRendererParams) {
  if (value == null) return <span className="text-zinc-500">--</span>
  const v = Number(value)
  const color = v > 0 ? '#22c55e' : v < 0 ? '#ef4444' : '#555568'
  return <span style={{ color }}>{v >= 0 ? '+' : ''}{v.toFixed(1)}%</span>
}

function DteCell({ value }: ICellRendererParams) {
  if (value == null) return <span className="text-zinc-500">--</span>
  const dte = Number(value)
  const color = dte === 0 ? '#ef4444' : dte <= 3 ? '#ef4444' : dte <= 7 ? '#f97316' : dte <= 14 ? '#eab308' : '#a1a1aa'
  const bold = dte <= 3
  return <span style={{ color, fontWeight: bold ? 700 : 400 }}>{dte}d</span>
}

function GreekCell({ value }: ICellRendererParams) {
  if (value == null) return <span className="text-zinc-500">--</span>
  const v = Number(value)
  const color = v > 0 ? '#22c55e' : v < 0 ? '#ef4444' : '#71717a'
  return <span style={{ color }}>{v >= 0 ? '+' : ''}{v.toFixed(2)}</span>
}

function CurrencyCell({ value }: ICellRendererParams) {
  if (value == null) return <span className="text-zinc-500">--</span>
  const v = Number(value)
  if (v === 0) return <span className="text-zinc-500">$0</span>
  const color = v < 0 ? '#ef4444' : '#a1a1aa'
  return <span style={{ color }}>${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
}

function MarginPctCell({ value }: ICellRendererParams) {
  if (value == null) return <span className="text-zinc-500">--</span>
  const v = Number(value)
  const color = v >= 15 ? '#ef4444' : v >= 10 ? '#f97316' : '#71717a'
  return <span style={{ color }}>{v.toFixed(1)}%</span>
}

function OptionTypeCell({ value }: ICellRendererParams) {
  if (!value) return <span className="text-zinc-500">E</span>
  const v = String(value).toLowerCase()
  const label = v.charAt(0).toUpperCase()
  const cls = v === 'put' ? 'bg-red-900/30 text-red-400' : v === 'call' ? 'bg-green-900/30 text-green-400' : 'bg-blue-900/30 text-blue-400'
  return <span className={clsx('text-[9px] px-1 py-[1px] rounded font-semibold', cls)}>{label}</span>
}

function TradeTypeCell({ data }: ICellRendererParams) {
  const isWI = data?.trade_type === 'what_if' || data?._isWhatIf
  if (!isWI) return null
  return <span className="text-[8px] px-1 py-[0px] rounded bg-blue-900/30 text-blue-400 font-semibold">WI</span>
}

function RiskPctBpCell({ value }: ICellRendererParams) {
  if (value == null) return <span className="text-zinc-500">--</span>
  const v = Number(value)
  const color = v >= 5 ? '#ef4444' : v >= 2 ? '#f97316' : '#71717a'
  return <span style={{ color }}>{v.toFixed(1)}%</span>
}

// ---------------------------------------------------------------------------
// Column presets for Strategies grid
// ---------------------------------------------------------------------------
type StrategyPreset = 'default' | 'greeks' | 'risk' | 'pnl' | 'full'

const GRID_STYLE = {
  fontSize: '11px',
  fontFamily: "'JetBrains Mono', monospace",
}

const CELL_R: ColDef = {
  cellStyle: { ...GRID_STYLE, display: 'flex', alignItems: 'center', justifyContent: 'flex-end' },
}
const CELL_L: ColDef = {
  cellStyle: { ...GRID_STYLE, display: 'flex', alignItems: 'center' },
}

// All possible strategy columns
function getStrategyColumnDefs(preset: StrategyPreset): (ColDef | ColGroupDef)[] {
  const colUnderlying: ColDef = {
    field: 'underlying', headerName: 'UDL', width: 70, pinned: 'left', ...CELL_L,
    cellStyle: (params) => ({
      ...GRID_STYLE, display: 'flex', alignItems: 'center', fontWeight: 600,
      color: params.data?.trade_type === 'what_if' ? '#60a5fa' : '#e4e4e7',
    }),
  }
  const colType: ColDef = { field: 'strategy_type', headerName: 'Strategy', width: 100, ...CELL_L }
  const colLegs: ColDef = { field: 'legs_summary', headerName: 'Legs', width: 140, ...CELL_L, cellStyle: { ...GRID_STYLE, display: 'flex', alignItems: 'center', fontSize: '10px', color: '#a1a1aa' } }
  const colDte: ColDef = { field: 'dte', headerName: 'DTE', width: 55, ...CELL_R, cellRenderer: DteCell }
  const colQty: ColDef = { field: 'quantity', headerName: 'Qty', width: 45, ...CELL_R }
  const colWI: ColDef = { field: 'trade_type', headerName: '', width: 30, cellRenderer: TradeTypeCell, ...CELL_L, suppressSizeToFit: true }

  // P&L
  const colPnl: ColDef = { field: 'total_pnl', headerName: 'P&L', width: 75, cellRenderer: PnlCell, ...CELL_R, sort: 'desc' }
  const colPnlPct: ColDef = { field: 'pnl_pct', headerName: 'P&L%', width: 60, cellRenderer: PnlPctCell, ...CELL_R }
  const colEntry: ColDef = { field: 'entry_cost', headerName: 'Entry', width: 65, cellRenderer: CurrencyCell, ...CELL_R }

  // Greeks
  const colDelta: ColDef = { field: 'net_delta', headerName: '\u0394', width: 55, cellRenderer: GreekCell, ...CELL_R }
  const colGamma: ColDef = { field: 'net_gamma', headerName: '\u0393', width: 55, ...CELL_R, valueFormatter: (p: ValueFormatterParams) => p.value != null ? Number(p.value).toFixed(4) : '--' }
  const colTheta: ColDef = { field: 'net_theta', headerName: '\u0398', width: 60, cellRenderer: GreekCell, ...CELL_R }
  const colVega: ColDef = { field: 'net_vega', headerName: '\u03BD', width: 55, cellRenderer: GreekCell, ...CELL_R }

  // Risk
  const colMaxRisk: ColDef = { field: 'max_risk', headerName: 'MaxRisk', width: 70, cellRenderer: CurrencyCell, ...CELL_R }
  const colMargin: ColDef = { field: 'margin_used', headerName: 'Margin', width: 70, cellRenderer: CurrencyCell, ...CELL_R }
  const colMarginPct: ColDef = { field: 'margin_pct_of_capital', headerName: 'Mrg%', width: 55, cellRenderer: MarginPctCell, ...CELL_R }
  const colRiskPctBP: ColDef = { field: 'max_risk_pct_total_bp', headerName: 'Risk%BP', width: 60, cellRenderer: RiskPctBpCell, ...CELL_R }
  const colRiskPctMargin: ColDef = { field: 'max_risk_pct_margin', headerName: 'Risk%M', width: 60, cellRenderer: RiskPctBpCell, ...CELL_R }

  // Meta
  const colSource: ColDef = { field: 'trade_source', headerName: 'Src', width: 50, ...CELL_L, cellStyle: { ...GRID_STYLE, display: 'flex', alignItems: 'center', fontSize: '10px', color: '#71717a' } }
  const colOpened: ColDef = {
    field: 'opened_at', headerName: 'Opened', width: 70, ...CELL_L,
    valueFormatter: (p: ValueFormatterParams) => {
      if (!p.value) return '--'
      const d = new Date(p.value)
      return `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
    },
    cellStyle: { ...GRID_STYLE, display: 'flex', alignItems: 'center', fontSize: '10px', color: '#71717a' },
  }

  switch (preset) {
    case 'greeks':
      return [colUnderlying, colWI, colType, colLegs, colDte, colQty,
        { headerName: 'Greeks', children: [colDelta, colGamma, colTheta, colVega] },
        colPnl, colPnlPct]
    case 'risk':
      return [colUnderlying, colWI, colType, colDte, colQty,
        { headerName: 'Risk', children: [colMaxRisk, colMargin, colMarginPct, colRiskPctBP, colRiskPctMargin] },
        colDelta, colTheta, colPnl]
    case 'pnl':
      return [colUnderlying, colWI, colType, colLegs, colDte, colQty,
        { headerName: 'P&L', children: [colEntry, colPnl, colPnlPct] },
        colMaxRisk, colDelta, colTheta]
    case 'full':
      return [colUnderlying, colWI, colType, colLegs, colDte, colQty,
        colEntry, colMargin, colMarginPct, colMaxRisk, colRiskPctBP,
        { headerName: 'Greeks', children: [colDelta, colGamma, colTheta, colVega] },
        colPnl, colPnlPct, colSource, colOpened]
    case 'default':
    default:
      return [colUnderlying, colWI, colType, colLegs, colDte, colQty,
        colMargin, colMaxRisk, colDelta, colTheta, colPnl, colPnlPct]
  }
}

// ---------------------------------------------------------------------------
// All possible position columns
// ---------------------------------------------------------------------------
type PositionPreset = 'default' | 'greeks' | 'pnl_attr' | 'full'

function getPositionColumnDefs(preset: PositionPreset): (ColDef | ColGroupDef)[] {
  const colUdl: ColDef = {
    field: 'underlying', headerName: 'UDL', width: 65, pinned: 'left', ...CELL_L,
    valueGetter: (p) => p.data?.underlying || p.data?.symbol,
    cellStyle: (params) => ({
      ...GRID_STYLE, display: 'flex', alignItems: 'center', fontWeight: 600,
      color: params.data?.trade_type === 'what_if' ? '#60a5fa' : '#e4e4e7',
    }),
  }
  const colWI: ColDef = { field: 'trade_type', headerName: '', width: 30, cellRenderer: TradeTypeCell, ...CELL_L }
  const colOptType: ColDef = { field: 'option_type', headerName: 'Tp', width: 35, cellRenderer: OptionTypeCell, cellStyle: { ...GRID_STYLE, display: 'flex', alignItems: 'center', justifyContent: 'center' } }
  const colStrike: ColDef = { field: 'strike', headerName: 'K', width: 55, ...CELL_R, valueFormatter: (p: ValueFormatterParams) => p.value != null ? Number(p.value).toFixed(0) : '--' }
  const colDte: ColDef = { field: 'dte', headerName: 'DTE', width: 50, ...CELL_R, cellRenderer: DteCell }
  const colQty: ColDef = {
    field: 'quantity', headerName: 'Qty', width: 45, ...CELL_R,
    cellStyle: (params) => ({
      ...GRID_STYLE, display: 'flex', alignItems: 'center', justifyContent: 'flex-end',
      color: (params.value || 0) < 0 ? '#ef4444' : '#22c55e',
    }),
  }
  const colSide: ColDef = { field: 'side', headerName: 'Side', width: 45, ...CELL_L, cellStyle: { ...GRID_STYLE, display: 'flex', alignItems: 'center', fontSize: '10px', color: '#71717a' } }

  // Pricing
  const colEntry: ColDef = { field: 'entry_price', headerName: 'Entry', width: 55, ...CELL_R, valueFormatter: (p: ValueFormatterParams) => p.value != null ? Number(p.value).toFixed(2) : '--', cellStyle: { ...GRID_STYLE, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', color: '#a1a1aa' } }
  const colMark: ColDef = { field: 'current_price', headerName: 'Mark', width: 55, ...CELL_R, valueFormatter: (p: ValueFormatterParams) => p.value != null ? Number(p.value).toFixed(2) : '--' }
  const colIV: ColDef = { field: 'iv', headerName: 'IV', width: 50, ...CELL_R, valueFormatter: (p: ValueFormatterParams) => p.value != null ? `${(Number(p.value) * 100).toFixed(0)}%` : '--' }

  // Greeks
  const colDelta: ColDef = { field: 'delta', headerName: '\u0394', width: 55, ...CELL_R, cellRenderer: GreekCell }
  const colGamma: ColDef = { field: 'gamma', headerName: '\u0393', width: 55, ...CELL_R, valueFormatter: (p: ValueFormatterParams) => p.value != null ? Number(p.value).toFixed(4) : '--' }
  const colTheta: ColDef = { field: 'theta', headerName: '\u0398', width: 55, ...CELL_R, cellRenderer: GreekCell }
  const colVega: ColDef = { field: 'vega', headerName: '\u03BD', width: 55, ...CELL_R, cellRenderer: GreekCell }

  // Entry Greeks
  const colEntryDelta: ColDef = { field: 'entry_delta', headerName: '\u0394\u2080', width: 55, ...CELL_R, cellRenderer: GreekCell }
  const colEntryTheta: ColDef = { field: 'entry_theta', headerName: '\u0398\u2080', width: 55, ...CELL_R, cellRenderer: GreekCell }

  // P&L
  const colPnl: ColDef = { field: 'total_pnl', headerName: 'P&L', width: 65, ...CELL_R, cellRenderer: PnlCell }
  const colPnlPct: ColDef = { field: 'pnl_pct', headerName: '%', width: 50, ...CELL_R, cellRenderer: PnlPctCell }
  const colBrokerPnl: ColDef = { field: 'broker_pnl', headerName: 'Bkr P&L', width: 65, ...CELL_R, cellRenderer: PnlCell }

  // P&L Attribution
  const colPnlDelta: ColDef = { field: 'pnl_delta', headerName: '\u0394 P&L', width: 60, ...CELL_R, cellRenderer: PnlCell }
  const colPnlGamma: ColDef = { field: 'pnl_gamma', headerName: '\u0393 P&L', width: 60, ...CELL_R, cellRenderer: PnlCell }
  const colPnlTheta: ColDef = { field: 'pnl_theta', headerName: '\u0398 P&L', width: 60, ...CELL_R, cellRenderer: PnlCell }
  const colPnlVega: ColDef = { field: 'pnl_vega', headerName: '\u03BD P&L', width: 60, ...CELL_R, cellRenderer: PnlCell }
  const colPnlUnexp: ColDef = { field: 'pnl_unexplained', headerName: 'Unexp', width: 55, ...CELL_R, cellRenderer: PnlCell }

  switch (preset) {
    case 'greeks':
      return [colUdl, colWI, colOptType, colStrike, colDte, colQty,
        { headerName: 'Current Greeks', children: [colDelta, colGamma, colTheta, colVega] },
        { headerName: 'Entry Greeks', children: [colEntryDelta, colEntryTheta] },
        colIV, colPnl]
    case 'pnl_attr':
      return [colUdl, colWI, colOptType, colStrike, colDte, colQty,
        colEntry, colMark,
        { headerName: 'P&L Attribution', children: [colPnl, colPnlDelta, colPnlGamma, colPnlTheta, colPnlVega, colPnlUnexp] },
        colBrokerPnl, colPnlPct]
    case 'full':
      return [colUdl, colWI, colOptType, colStrike, colDte, colQty, colSide,
        colEntry, colMark, colIV,
        { headerName: 'Greeks', children: [colDelta, colGamma, colTheta, colVega] },
        { headerName: 'P&L', children: [colPnl, colPnlPct, colBrokerPnl] },
        { headerName: 'Attribution', children: [colPnlDelta, colPnlTheta, colPnlVega] }]
    case 'default':
    default:
      return [colUdl, colWI, colOptType, colStrike, colDte, colQty,
        colEntry, colMark, colDelta, colTheta, colPnl, colPnlPct]
  }
}

// ---------------------------------------------------------------------------
// Risk Factors Table (compact HTML — small dataset, no grid needed)
// ---------------------------------------------------------------------------
const HC = 'py-[3px] px-1.5 text-[10px] font-semibold text-text-muted whitespace-nowrap'
const DC = 'py-[3px] px-1.5 text-[11px] font-mono whitespace-nowrap'
const ROW = 'border-b border-border-secondary/40 hover:bg-bg-hover/50'

function RiskFactorsTable({ factors }: { factors: TradingDashboardRiskFactor[] }) {
  if (!factors.length) return null
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b border-border-secondary bg-bg-secondary">
            <th className={clsx(HC, 'text-left')}>UDL</th>
            <th className={clsx(HC, 'text-right')}>Spot</th>
            <th className={clsx(HC, 'text-right')}>{'\u0394'}</th>
            <th className={clsx(HC, 'text-right')}>{'\u0398'}</th>
            <th className={clsx(HC, 'text-right')}>{'\u0394$'}</th>
            <th className={clsx(HC, 'text-right')}>Conc%</th>
            <th className={clsx(HC, 'text-right')}>P&L</th>
          </tr>
        </thead>
        <tbody>
          {factors.map((f) => (
            <tr key={f.underlying + (f.trade_type || '')} className={ROW}>
              <td className={clsx(DC, 'text-left font-semibold', f.trade_type === 'what_if' ? 'text-accent-blue' : 'text-text-primary')}>{f.underlying}</td>
              <td className={clsx(DC, 'text-right')}>{n$(f.spot)}</td>
              <td className={clsx(DC, 'text-right', clr(f.delta))}>{g(f.delta)}</td>
              <td className={clsx(DC, 'text-right', clr(f.theta))}>{g(f.theta)}</td>
              <td className={clsx(DC, 'text-right', clr(f.delta_dollars))}>{n$(f.delta_dollars)}</td>
              <td className={clsx(DC, 'text-right', f.concentration_pct > 30 ? 'text-accent-red' : '')}>{pct(f.concentration_pct)}</td>
              <td className={clsx(DC, 'text-right', clr(f.pnl))}>{n(f.pnl)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Preset selector button row
// ---------------------------------------------------------------------------
function PresetBar<T extends string>({ presets, active, onChange }: {
  presets: { key: T; label: string }[]
  active: T
  onChange: (key: T) => void
}) {
  return (
    <div className="flex items-center gap-0.5">
      <Columns3 size={10} className="text-text-muted mr-1" />
      {presets.map(({ key, label }) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={clsx(
            'px-1.5 py-[1px] rounded text-[9px] font-mono',
            active === key
              ? 'bg-accent-blue/20 text-accent-blue'
              : 'text-text-muted hover:text-text-primary hover:bg-bg-hover',
          )}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

const STRATEGY_PRESETS: { key: StrategyPreset; label: string }[] = [
  { key: 'default', label: 'Def' },
  { key: 'greeks', label: 'Greeks' },
  { key: 'risk', label: 'Risk' },
  { key: 'pnl', label: 'P&L' },
  { key: 'full', label: 'Full' },
]

const POSITION_PRESETS: { key: PositionPreset; label: string }[] = [
  { key: 'default', label: 'Def' },
  { key: 'greeks', label: 'Greeks' },
  { key: 'pnl_attr', label: 'Attr' },
  { key: 'full', label: 'Full' },
]

// ---------------------------------------------------------------------------
// AG Grid defaults
// ---------------------------------------------------------------------------
const GRID_OPTIONS = {
  headerHeight: 24,
  rowHeight: 22,
  animateRows: false,
  suppressCellFocus: true,
  enableCellTextSelection: true,
  enableCellChangeFlash: true,
  suppressMovableColumns: false,
  domLayout: 'autoHeight' as const,
}

// ---------------------------------------------------------------------------
// Trades Frame (portfolio + blotter view)
// ---------------------------------------------------------------------------
type ViewMode = 'portfolio' | 'blotter'

function TradesFrame() {
  const { data: portfolios, isLoading: loadingPf } = usePortfolios()
  const [selectedPortfolio, setSelectedPortfolio] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('portfolio')
  const [stratPreset, setStratPreset] = useState<StrategyPreset>('default')
  const [posPreset, setPosPreset] = useState<PositionPreset>('default')

  const realPortfolios = useMemo(
    () => portfolios?.filter((p) => p.portfolio_type === 'real') ?? [],
    [portfolios],
  )

  const activePf = selectedPortfolio || realPortfolios[0]?.name || ''
  const { data, isLoading, isError, error } = useTradingDashboard(activePf)

  const showWhatIf = viewMode === 'blotter'

  // Merge strategies
  const strategyRows = useMemo(() => {
    if (!data || (data as any).status) return []
    const real = data.strategies || []
    if (!showWhatIf) return real
    const wi = (data.whatif_trades || []).map(s => ({ ...s, _isWhatIf: true }))
    return [...real, ...wi]
  }, [data, showWhatIf])

  // Merge positions
  const positionRows = useMemo(() => {
    if (!data || (data as any).status) return []
    const real = data.positions || []
    if (!showWhatIf) return real
    const wi = (data.whatif_positions || []).map(p => ({ ...p, _isWhatIf: true }))
    return [...real, ...wi]
  }, [data, showWhatIf])

  // Risk factors
  const riskFactors = useMemo(() => {
    if (!data || (data as any).status) return []
    const real = data.risk_factors || []
    if (!showWhatIf) return real
    return [...real, ...(data.whatif_risk_factors || [])]
  }, [data, showWhatIf])

  // Strategy totals (pinned bottom)
  const strategyTotals = useMemo(() => {
    if (!strategyRows.length) return []
    return [{
      underlying: 'TOTAL',
      strategy_type: '',
      legs_summary: `${strategyRows.length} strategies`,
      dte: null,
      quantity: null,
      margin_used: strategyRows.reduce((s, r) => s + (r.margin_used || 0), 0),
      max_risk: strategyRows.reduce((s, r) => s + (r.max_risk || 0), 0),
      net_delta: strategyRows.reduce((s, r) => s + (r.net_delta || 0), 0),
      net_theta: strategyRows.reduce((s, r) => s + (r.net_theta || 0), 0),
      net_gamma: strategyRows.reduce((s, r) => s + (r.net_gamma || 0), 0),
      net_vega: strategyRows.reduce((s, r) => s + (r.net_vega || 0), 0),
      total_pnl: strategyRows.reduce((s, r) => s + (r.total_pnl || 0), 0),
      pnl_pct: null,
      margin_pct_of_capital: null,
      max_risk_pct_total_bp: null,
      max_risk_pct_margin: null,
      entry_cost: null,
      trade_source: '',
      trade_type: '',
    }]
  }, [strategyRows])

  const stratColDefs = useMemo(() => getStrategyColumnDefs(stratPreset), [stratPreset])
  const posColDefs = useMemo(() => getPositionColumnDefs(posPreset), [posPreset])

  // Row class for WhatIf rows
  const getRowClass = useCallback((params: RowClassParams) => {
    if (params.data?.trade_type === 'what_if' || params.data?._isWhatIf) {
      return 'ag-row-whatif'
    }
    return ''
  }, [])

  return (
    <div className="h-full overflow-y-auto">
      {/* Portfolio tabs + view mode */}
      <div className="flex items-center gap-1.5 px-2 py-1 bg-bg-secondary border-b border-border-secondary flex-wrap">
        {loadingPf ? (
          <span className="text-[10px] text-text-muted">Loading...</span>
        ) : (
          <>
            {realPortfolios.map((p) => (
              <button
                key={p.name}
                onClick={() => setSelectedPortfolio(p.name)}
                className={clsx(
                  'px-2 py-[2px] rounded text-[10px] font-mono',
                  activePf === p.name
                    ? 'bg-accent-blue text-white'
                    : 'bg-bg-tertiary text-text-secondary hover:bg-bg-hover',
                )}
              >
                {p.name}
              </button>
            ))}
            <span className="text-border-secondary text-[10px]">|</span>
            <button
              onClick={() => setViewMode(viewMode === 'portfolio' ? 'blotter' : 'portfolio')}
              className={clsx(
                'px-2 py-[2px] rounded text-[10px] font-mono',
                viewMode === 'blotter'
                  ? 'bg-accent-blue/20 text-accent-blue border border-accent-blue/30'
                  : 'bg-bg-tertiary text-text-muted hover:bg-bg-hover',
              )}
              title="Toggle blotter: Portfolio + WhatIf"
            >
              {viewMode === 'blotter' ? 'Blotter (P+WI)' : 'Blotter'}
            </button>
          </>
        )}
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-3">
          <Spinner size="sm" />
          <span className="text-[10px] text-text-muted ml-2">Loading...</span>
        </div>
      )}

      {isError && (
        <div className="flex items-center gap-2 px-2 py-1.5 border-b border-border-secondary bg-bg-secondary">
          <span className="text-[10px] text-text-muted">No live data</span>
          <span className="text-2xs text-text-muted/60">({(error as Error)?.message?.includes('timeout') ? 'timeout' : 'offline'})</span>
        </div>
      )}

      {data && (data as any).status === 'waiting' && (
        <div className="flex items-center gap-2 px-2 py-1.5 border-b border-border-secondary bg-bg-secondary">
          <Spinner size="sm" />
          <span className="text-[10px] text-text-muted">Engine booting...</span>
        </div>
      )}

      {data && !(data as any).status && (
        <div>
          <SummaryStrip p={data.portfolio} showWhatIf={showWhatIf} />

          {/* Strategies + Risk side by side */}
          <div className="grid grid-cols-[1fr_auto] border-b border-border-secondary">
            {/* Strategies grid */}
            <div className="border-r border-border-secondary min-w-0">
              <div className="flex items-center justify-between px-1.5 py-[2px] bg-bg-tertiary border-b border-border-secondary">
                <span className="text-[9px] font-bold uppercase tracking-wider text-text-muted">
                  Strategies ({strategyRows.length})
                </span>
                <PresetBar presets={STRATEGY_PRESETS} active={stratPreset} onChange={setStratPreset} />
              </div>
              <div className="ag-theme-alpine-dark w-full">
                <style>{`.ag-row-whatif { background-color: rgba(59,130,246,0.04) !important; }`}</style>
                <AgGridReact
                  {...GRID_OPTIONS}
                  columnDefs={stratColDefs}
                  rowData={strategyRows}
                  pinnedBottomRowData={strategyTotals}
                  getRowClass={getRowClass}
                  getRowId={(params) => params.data.trade_id || params.data.underlying}
                />
              </div>
            </div>

            {/* Risk factors */}
            <div className="min-w-[280px]">
              <div className="px-1.5 py-[2px] text-[9px] font-bold uppercase tracking-wider text-text-muted bg-bg-tertiary border-b border-border-secondary">
                Risk Factors ({riskFactors.length})
              </div>
              <RiskFactorsTable factors={riskFactors} />
            </div>
          </div>

          {/* Positions grid */}
          <div>
            <div className="flex items-center justify-between px-1.5 py-[2px] bg-bg-tertiary border-b border-border-secondary">
              <span className="text-[9px] font-bold uppercase tracking-wider text-text-muted">
                Positions ({positionRows.length})
              </span>
              <PresetBar presets={POSITION_PRESETS} active={posPreset} onChange={setPosPreset} />
            </div>
            <div className="ag-theme-alpine-dark w-full">
              <AgGridReact
                {...GRID_OPTIONS}
                columnDefs={posColDefs}
                rowData={positionRows}
                getRowClass={getRowClass}
                getRowId={(params) => params.data.id}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Draggable split pane hook
// ---------------------------------------------------------------------------
function useSplitPane(defaultTopPct = 50) {
  const [topPct, setTopPct] = useState(defaultTopPct)
  const dragging = useRef(false)
  const containerRef = useRef<HTMLDivElement>(null)

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragging.current = true
    const onMouseMove = (ev: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const newPct = ((ev.clientY - rect.top) / rect.height) * 100
      setTopPct(Math.min(Math.max(newPct, 15), 85))
    }
    const onMouseUp = () => {
      dragging.current = false
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }, [])

  return { topPct, onMouseDown, containerRef }
}

// ---------------------------------------------------------------------------
// Command Reference (permanent right sidebar)
// ---------------------------------------------------------------------------
const CMD_SECTIONS = [
  {
    title: 'Trading Workflow',
    cmds: [
      ['plan', 'Daily plan (fast, all desks)'],
      ['scan', 'Full scan (Scout + gates)'],
      ['propose', 'Trade proposals'],
      ['deploy', 'Book to desk'],
      ['mark', 'Mark-to-market'],
      ['exits', 'Check exit rules'],
      ['close <id>', 'Close trade'],
      ['close auto', 'Auto-close triggered'],
    ],
  },
  {
    title: 'Execution',
    cmds: [
      ['golive <id>', 'Preview live order'],
      ['golive <id> --confirm', 'Place on broker'],
      ['orders', 'Order status'],
    ],
  },
  {
    title: 'Analytics',
    cmds: [
      ['perf [desk]', 'Performance'],
      ['learn [days]', 'ML/RL analysis'],
      ['setup-desks', 'Create desks'],
    ],
  },
  {
    title: 'Reports',
    cmds: [
      ['status', 'Workflow state'],
      ['positions', 'Trades + Greeks'],
      ['portfolios', 'All portfolios'],
      ['greeks', 'Greeks vs limits'],
      ['capital', 'Capital util'],
      ['trades', "Today's trades"],
      ['risk', 'VaR + breakers'],
    ],
  },
  {
    title: 'Actions',
    cmds: [
      ['approve/reject <id>', 'Approve or reject'],
      ['halt / resume', 'Trading control'],
    ],
  },
  {
    title: 'Booking',
    cmds: [
      ['templates', 'List templates'],
      ['book <#>', 'Book by index'],
    ],
  },
]

function CommandReference() {
  return (
    <div className="h-full overflow-y-auto bg-bg-primary border-l border-border-secondary">
      <div className="px-2 py-1.5 bg-bg-secondary border-b border-border-secondary sticky top-0">
        <span className="text-[10px] font-bold uppercase tracking-wider text-text-muted">Commands</span>
      </div>
      <div className="px-2 py-1 space-y-1.5">
        {CMD_SECTIONS.map((section) => (
          <div key={section.title}>
            <div className="text-[9px] font-bold uppercase tracking-wider text-accent-blue mt-1 mb-0.5">{section.title}</div>
            {section.cmds.map(([cmd, desc]) => (
              <div key={cmd} className="flex gap-1.5 py-[1px]">
                <code className="text-[10px] font-mono text-accent-green whitespace-nowrap min-w-[130px]">{cmd}</code>
                <span className="text-[9px] text-text-muted">{desc}</span>
              </div>
            ))}
          </div>
        ))}
        <div className="border-t border-border-secondary/40 pt-1 mt-1">
          <div className="text-[9px] text-text-muted">
            <span className="font-semibold">Desks:</span> 0dte ($10K) &middot; medium ($10K) &middot; leaps ($20K)
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Page — 2-column: Left (Plan + Trades + Terminal) | Right (Commands)
// ---------------------------------------------------------------------------
export function TradingTerminal() {
  const { topPct, onMouseDown, containerRef } = useSplitPane(45)

  return (
    <div className="flex h-full overflow-hidden -m-3">
      {/* Left: Trades + Terminal */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <div ref={containerRef} className="flex flex-col flex-1 min-h-0 overflow-hidden">
          <div className="overflow-auto" style={{ height: `${topPct}%` }}>
            <TradesFrame />
          </div>
          <div
            className="h-1 bg-border-primary hover:bg-accent-blue cursor-row-resize flex-shrink-0"
            onMouseDown={onMouseDown}
          />
          <div className="overflow-hidden flex-1" style={{ height: `${100 - topPct}%` }}>
            <TerminalPanel />
          </div>
        </div>
      </div>

      {/* Right: Permanent command reference */}
      <div className="w-[240px] flex-shrink-0">
        <CommandReference />
      </div>
    </div>
  )
}
