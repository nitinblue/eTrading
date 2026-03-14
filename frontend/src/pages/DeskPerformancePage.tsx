import { useState, useMemo } from 'react'
import { clsx } from 'clsx'
import { useQuery } from '@tanstack/react-query'
import {
  Zap, TrendingUp, BarChart3, Shield, Activity, Brain,
  CheckCircle2, XCircle, Clock, Target, AlertTriangle,
  ChevronDown, ChevronUp
} from 'lucide-react'
import { AgGridReact } from 'ag-grid-react'
import type { ColDef, ICellRendererParams } from 'ag-grid-community'

const API = '/api/v2'
const n$ = (v: number) => v < 0 ? `-$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`

// ---------------------------------------------------------------------------
// API hooks
// ---------------------------------------------------------------------------
interface DeskData {
  name: string; display_name: string; description: string; capital: number
  open_positions: number; closed_trades: number; total_pnl: number
  realized_pnl: number; unrealized_pnl: number; win_rate: number
  wins: number; losses: number; daily_theta: number; deployed_pct: number
  health: Record<string, number>; target_return_pct: number
  allowed_strategies: string[]; tags: string[]; portfolio_exists: boolean
}

function useDesks() {
  return useQuery<DeskData[]>({ queryKey: ['desks'], queryFn: () => fetch(`${API}/desks`).then(r => r.json()), refetchInterval: 30000 })
}

function useDeskTrades(desk: string, status: string) {
  return useQuery({ queryKey: ['desk-trades', desk, status], queryFn: () => fetch(`${API}/desks/${desk}/trades?status=${status}`).then(r => r.json()), enabled: !!desk })
}

// ---------------------------------------------------------------------------
// Maverick Identity
// ---------------------------------------------------------------------------
function MaverickCard({ desks }: { desks: DeskData[] }) {
  const totalPnl = desks.reduce((s, d) => s + d.total_pnl, 0)
  const totalOpen = desks.reduce((s, d) => s + d.open_positions, 0)
  const totalClosed = desks.reduce((s, d) => s + d.closed_trades, 0)
  const totalWins = desks.reduce((s, d) => s + d.wins, 0)
  const totalLosses = desks.reduce((s, d) => s + d.losses, 0)
  const winRate = (totalWins + totalLosses) > 0 ? (totalWins / (totalWins + totalLosses) * 100) : 0
  const totalTheta = desks.reduce((s, d) => s + d.daily_theta, 0)
  const totalCapital = desks.reduce((s, d) => s + d.capital, 0)

  return (
    <div className="border border-border-primary bg-gradient-to-r from-purple-950/30 via-bg-secondary to-blue-950/20 rounded-xl p-5">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-purple-900/40 border border-purple-700 flex items-center justify-center">
            <Brain size={24} className="text-purple-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-text-primary">Maverick</h2>
            <p className="text-[11px] text-text-muted">Trader Agent — Systematic Options Trading</p>
            <p className="text-[10px] text-purple-400 mt-0.5">
              "I trade {desks.length} desks with 11 gates. Every trade has a reason. Every loss is data."
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="px-2 py-0.5 rounded-full bg-green-900/30 text-green-400 text-[9px] font-semibold border border-green-800">ACTIVE</span>
          <span className="px-2 py-0.5 rounded-full bg-purple-900/30 text-purple-400 text-[9px] font-mono border border-purple-800">11 gates</span>
        </div>
      </div>

      {/* Aggregate Metrics */}
      <div className="flex items-center gap-6 mt-4 pt-4 border-t border-border-secondary">
        <Metric label="Total Capital" value={n$(totalCapital)} />
        <Metric label="Total P&L" value={n$(totalPnl)} color={totalPnl >= 0 ? 'text-green-400' : 'text-red-400'} />
        <Metric label="Win Rate" value={winRate > 0 ? `${winRate.toFixed(0)}%` : '--'} color={winRate >= 60 ? 'text-green-400' : winRate > 0 ? 'text-amber-400' : undefined} />
        <Metric label="Open" value={`${totalOpen}`} />
        <Metric label="Closed" value={`${totalClosed}`} />
        <Metric label="Daily \u0398" value={totalTheta !== 0 ? `$${totalTheta.toFixed(0)}` : '--'} color="text-green-400" />
        <Metric label="W / L" value={`${totalWins} / ${totalLosses}`} />
      </div>
    </div>
  )
}

function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[9px] text-text-muted uppercase tracking-wider">{label}</span>
      <span className={clsx('text-sm font-bold font-mono', color || 'text-text-primary')}>{value}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Desk Card
// ---------------------------------------------------------------------------
const DESK_ICONS: Record<string, { icon: React.ElementType; color: string; gradient: string }> = {
  desk_0dte:   { icon: Zap, color: 'text-red-400', gradient: 'from-red-950/40 to-bg-secondary border-red-800/40' },
  desk_medium: { icon: TrendingUp, color: 'text-amber-400', gradient: 'from-amber-950/30 to-bg-secondary border-amber-800/40' },
  desk_leaps:  { icon: BarChart3, color: 'text-blue-400', gradient: 'from-blue-950/30 to-bg-secondary border-blue-800/40' },
}

function DeskCard({ desk, selected, onClick }: { desk: DeskData; selected: boolean; onClick: () => void }) {
  const cfg = DESK_ICONS[desk.name] || DESK_ICONS.desk_medium
  const Icon = cfg.icon
  const pnlColor = desk.total_pnl > 0 ? 'text-green-400' : desk.total_pnl < 0 ? 'text-red-400' : 'text-text-muted'

  // Generate Maverick's voice
  const voice = generateVoice(desk)

  return (
    <button
      onClick={onClick}
      className={clsx(
        'border rounded-xl p-4 text-left transition-all w-full bg-gradient-to-b',
        cfg.gradient,
        selected ? 'ring-2 ring-accent-blue/50 border-accent-blue/30' : 'hover:border-border-primary',
      )}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon size={18} className={cfg.color} />
          <div>
            <h3 className="text-sm font-bold text-text-primary">{desk.display_name}</h3>
            <span className="text-[9px] text-text-muted font-mono">{desk.name}</span>
          </div>
        </div>
        <span className="text-base font-bold font-mono text-text-primary">${desk.capital.toLocaleString()}</span>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-3 gap-y-2 text-[10px] mb-3">
        <KV label="P&L" value={n$(desk.total_pnl)} color={pnlColor} />
        <KV label="Win Rate" value={desk.win_rate > 0 ? `${desk.win_rate.toFixed(0)}%` : '--'} color={desk.win_rate >= 60 ? 'text-green-400' : undefined} />
        <KV label="Open" value={`${desk.open_positions}`} />
        <KV label="Realized" value={n$(desk.realized_pnl)} color={desk.realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'} />
        <KV label="W / L" value={`${desk.wins}/${desk.losses}`} />
        <KV label="Deployed" value={`${desk.deployed_pct.toFixed(0)}%`} color={desk.deployed_pct > 60 ? 'text-amber-400' : undefined} />
      </div>

      {/* Health dots */}
      <div className="flex items-center gap-1.5 mb-2">
        {Object.entries(desk.health).map(([status, count]) => (
          <HealthDot key={status} status={status} count={count} />
        ))}
        {Object.keys(desk.health).length === 0 && <span className="text-[9px] text-text-muted">No positions</span>}
      </div>

      {/* Maverick's voice */}
      <p className="text-[9px] text-purple-400/80 italic leading-snug border-t border-border-secondary pt-2 mt-1">
        "{voice}"
      </p>
    </button>
  )
}

function KV({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <span className="text-text-muted">{label} </span>
      <span className={clsx('font-mono font-semibold', color || 'text-text-primary')}>{value}</span>
    </div>
  )
}

function HealthDot({ status, count }: { status: string; count: number }) {
  const colors: Record<string, string> = {
    healthy: 'bg-green-500', tested: 'bg-yellow-500', breached: 'bg-red-500',
    exit_triggered: 'bg-red-600', unknown: 'bg-zinc-600',
  }
  return (
    <span className="flex items-center gap-0.5 text-[9px] text-text-muted">
      <span className={clsx('w-2 h-2 rounded-full', colors[status] || 'bg-zinc-600')} />
      {count}
    </span>
  )
}

function generateVoice(desk: DeskData): string {
  if (desk.open_positions === 0 && desk.closed_trades === 0) {
    return `No trades yet. Waiting for opportunities that pass all 11 gates.`
  }
  if (desk.open_positions === 0) {
    return `${desk.closed_trades} trades closed. Win rate ${desk.win_rate.toFixed(0)}%. Scanning for next opportunity.`
  }
  const healthStr = desk.health.healthy ? `${desk.health.healthy} healthy` : ''
  const testedStr = desk.health.tested ? `, ${desk.health.tested} tested` : ''
  return `${desk.open_positions} open position${desk.open_positions > 1 ? 's' : ''} (${healthStr}${testedStr}). P&L ${n$(desk.total_pnl)}.`
}

// ---------------------------------------------------------------------------
// Trade Grid
// ---------------------------------------------------------------------------
function PnlCell({ value }: ICellRendererParams) {
  if (value == null) return <span className="text-zinc-500">--</span>
  const v = Number(value)
  const color = v > 0 ? '#22c55e' : v < 0 ? '#ef4444' : '#555'
  return <span style={{ color, fontWeight: 500 }}>{v >= 0 ? '+' : ''}${Math.abs(v).toFixed(0)}</span>
}

function HealthCellR({ value }: ICellRendererParams) {
  const colors: Record<string, { bg: string; text: string; label: string }> = {
    healthy: { bg: 'bg-green-900/30', text: 'text-green-400', label: 'OK' },
    tested: { bg: 'bg-yellow-900/30', text: 'text-yellow-400', label: 'TST' },
    breached: { bg: 'bg-red-900/30', text: 'text-red-400', label: 'BRK' },
    exit_triggered: { bg: 'bg-red-900/50', text: 'text-red-300', label: 'EXIT' },
  }
  const c = colors[value] || { bg: 'bg-zinc-800', text: 'text-zinc-400', label: value || '--' }
  return <span className={clsx('text-[9px] px-1.5 py-[1px] rounded font-semibold', c.bg, c.text)}>{c.label}</span>
}

const GRID_STYLE = { fontSize: '11px', fontFamily: "'JetBrains Mono', monospace" }
const CELL_R: ColDef = { cellStyle: { ...GRID_STYLE, display: 'flex', alignItems: 'center', justifyContent: 'flex-end' } }
const CELL_L: ColDef = { cellStyle: { ...GRID_STYLE, display: 'flex', alignItems: 'center' } }

const openColDefs: ColDef[] = [
  { field: 'underlying_symbol', headerName: 'UDL', width: 70, pinned: 'left', ...CELL_L,
    cellStyle: { ...GRID_STYLE, display: 'flex', alignItems: 'center', fontWeight: 600 } },
  { field: 'health_status', headerName: 'Health', width: 55, cellRenderer: HealthCellR, ...CELL_L },
  { field: 'strategy_type', headerName: 'Strategy', width: 120, ...CELL_L,
    valueGetter: (p: any) => p.data?.strategy_type || p.data?.legs?.[0]?.option_type || '?' },
  { field: 'dte', headerName: 'DTE', width: 50, ...CELL_R },
  { field: 'entry_price', headerName: 'Entry', width: 65, ...CELL_R, valueFormatter: (p: any) => p.value != null ? `$${Number(p.value).toFixed(2)}` : '--' },
  { field: 'current_price', headerName: 'Current', width: 65, ...CELL_R, valueFormatter: (p: any) => p.value != null ? `$${Number(p.value).toFixed(2)}` : '--' },
  { field: 'total_pnl', headerName: 'P&L', width: 70, cellRenderer: PnlCell, ...CELL_R, sort: 'desc' },
  { field: 'pop_at_entry', headerName: 'POP', width: 50, ...CELL_R, valueFormatter: (p: any) => p.value != null ? `${(Number(p.value) * 100).toFixed(0)}%` : '--' },
  { field: 'regime_at_entry', headerName: 'Rgm', width: 40, ...CELL_L },
  { field: 'max_risk', headerName: 'Risk', width: 60, ...CELL_R, valueFormatter: (p: any) => p.value != null ? `$${Number(p.value).toFixed(0)}` : '--' },
]

const closedColDefs: ColDef[] = [
  { field: 'underlying_symbol', headerName: 'UDL', width: 70, ...CELL_L, cellStyle: { ...GRID_STYLE, display: 'flex', alignItems: 'center', fontWeight: 600 } },
  { field: 'strategy_type', headerName: 'Strategy', width: 120, ...CELL_L,
    valueGetter: (p: any) => p.data?.strategy_type || '?' },
  { field: 'total_pnl', headerName: 'P&L', width: 70, cellRenderer: PnlCell, ...CELL_R, sort: 'desc' },
  { field: 'exit_reason', headerName: 'Exit', width: 100, ...CELL_L },
  { field: 'closed_at', headerName: 'Closed', width: 80, ...CELL_L, valueFormatter: (p: any) => {
    if (!p.value) return '--'
    return new Date(p.value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }},
  { field: 'entry_price', headerName: 'Entry', width: 60, ...CELL_R, valueFormatter: (p: any) => p.value != null ? `$${Number(p.value).toFixed(2)}` : '--' },
  { field: 'exit_price', headerName: 'Exit$', width: 60, ...CELL_R, valueFormatter: (p: any) => p.value != null ? `$${Number(p.value).toFixed(2)}` : '--' },
  { field: 'pop_at_entry', headerName: 'POP', width: 50, ...CELL_R, valueFormatter: (p: any) => p.value != null ? `${(Number(p.value) * 100).toFixed(0)}%` : '--' },
]

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function DeskPerformancePage() {
  const { data: desks, isLoading } = useDesks()
  const [selectedDesk, setSelectedDesk] = useState<string>('desk_0dte')
  const [tradeView, setTradeView] = useState<'open' | 'closed'>('open')

  const { data: trades } = useDeskTrades(selectedDesk, tradeView)

  const deskList = desks || []
  const selectedDeskData = deskList.find(d => d.name === selectedDesk)

  if (isLoading) {
    return <div className="flex items-center justify-center h-full text-text-muted text-sm">Loading desks...</div>
  }

  return (
    <div className="h-full overflow-y-auto bg-bg-primary">
      <div className="max-w-6xl mx-auto px-6 py-6 space-y-6">

        {/* Maverick Identity */}
        <MaverickCard desks={deskList} />

        {/* Desk Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {deskList.map(desk => (
            <DeskCard
              key={desk.name}
              desk={desk}
              selected={desk.name === selectedDesk}
              onClick={() => setSelectedDesk(desk.name)}
            />
          ))}
        </div>

        {/* Trade Grid */}
        {selectedDeskData && (
          <div className="border border-border-secondary rounded-xl overflow-hidden bg-bg-secondary/30">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2 bg-bg-tertiary border-b border-border-secondary">
              <div className="flex items-center gap-2">
                <h3 className="text-xs font-semibold text-text-primary">
                  {selectedDeskData.display_name} — Trades
                </h3>
                <span className="text-[9px] text-text-muted font-mono">
                  ({tradeView === 'open' ? selectedDeskData.open_positions : selectedDeskData.closed_trades} trades)
                </span>
              </div>
              <div className="flex gap-1">
                {(['open', 'closed'] as const).map(v => (
                  <button
                    key={v}
                    onClick={() => setTradeView(v)}
                    className={clsx(
                      'px-2.5 py-1 rounded text-[10px] font-mono',
                      tradeView === v
                        ? 'bg-accent-blue text-white'
                        : 'bg-bg-tertiary text-text-muted hover:bg-bg-hover',
                    )}
                  >
                    {v === 'open' ? 'Open' : 'Closed'}
                  </button>
                ))}
              </div>
            </div>

            {/* Grid */}
            <div className="ag-theme-alpine-dark" style={{ width: '100%' }}>
              <AgGridReact
                columnDefs={tradeView === 'open' ? openColDefs : closedColDefs}
                rowData={trades || []}
                domLayout="autoHeight"
                headerHeight={24}
                rowHeight={24}
                animateRows={false}
                suppressCellFocus={true}
                enableCellTextSelection={true}
                defaultColDef={{ sortable: true, resizable: true }}
              />
            </div>

            {/* Empty state */}
            {trades && trades.length === 0 && (
              <div className="py-8 text-center text-text-muted text-xs">
                <Target size={24} className="mx-auto mb-2 opacity-30" />
                <p>No {tradeView} trades in {selectedDeskData.display_name}.</p>
                <p className="text-[10px] mt-1">Run <code className="text-amber-400">scan</code> to find opportunities.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
