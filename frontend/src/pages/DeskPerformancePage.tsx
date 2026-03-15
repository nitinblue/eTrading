import { useState, useMemo } from 'react'
import { clsx } from 'clsx'
import { useQuery } from '@tanstack/react-query'
import {
  Zap, TrendingUp, BarChart3, Shield, Activity, Brain,
  CheckCircle2, XCircle, Clock, Target, AlertTriangle,
  ChevronDown, ChevronUp, Play, RefreshCw, Eye, Radio
} from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AgGridReact } from 'ag-grid-react'
import type { ColDef, ICellRendererParams } from 'ag-grid-community'

const API = '/api/v2'

// Currency-aware formatter
function nCur(v: number, currency: string = 'USD') {
  const sym = currency === 'INR' ? '\u20B9' : '$'
  const abs = Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })
  return v < 0 ? `-${sym}${abs}` : `${sym}${abs}`
}

// Market status (open/closed)
function isMarketOpen(market: string): boolean {
  const now = new Date()
  if (market === 'US') {
    // Rough check: Mon-Fri, 9:30-16:00 ET (UTC-4 or UTC-5)
    const utcH = now.getUTCHours()
    const day = now.getUTCDay()
    if (day === 0 || day === 6) return false
    return utcH >= 13 && utcH < 21 // ~9:30 ET = 13:30 UTC, ~16:00 ET = 20:00 UTC
  }
  if (market === 'INDIA') {
    // Mon-Fri, 9:15-15:30 IST (UTC+5:30)
    const utcH = now.getUTCHours()
    const day = now.getUTCDay()
    if (day === 0 || day === 6) return false
    return utcH >= 3 && utcH < 10 // ~9:15 IST = 3:45 UTC, ~15:30 IST = 10:00 UTC
  }
  return false
}

const MARKET_META: Record<string, { flag: string; label: string; tz: string }> = {
  US: { flag: '\uD83C\uDDFA\uD83C\uDDF8', label: 'United States', tz: 'ET' },
  INDIA: { flag: '\uD83C\uDDEE\uD83C\uDDF3', label: 'India', tz: 'IST' },
}

// Legacy alias
const n$ = (v: number) => nCur(v, 'USD')

// ---------------------------------------------------------------------------
// API hooks
// ---------------------------------------------------------------------------
interface DeskData {
  name: string; display_name: string; description: string; capital: number
  currency: string; market: string; timezone: string; broker: string
  open_positions: number; closed_trades: number; total_pnl: number
  realized_pnl: number; unrealized_pnl: number; win_rate: number
  wins: number; losses: number; daily_theta: number; deployed_pct: number
  health: Record<string, number>; target_return_pct: number
  allowed_strategies: string[]; tags: string[]; portfolio_exists: boolean
  has_overnight_risk?: boolean; last_health_check?: string
}

function useDesks() {
  return useQuery<DeskData[]>({ queryKey: ['desks'], queryFn: () => fetch(`${API}/desks`).then(r => r.json()), refetchInterval: 30000 })
}

function useDeskTrades(desk: string, status: string) {
  return useQuery({ queryKey: ['desk-trades', desk, status], queryFn: () => fetch(`${API}/desks/${desk}/trades?status=${status}`).then(r => r.json()), enabled: !!desk })
}

function useDeskPerformance() {
  return useQuery<Record<string, any>>({ queryKey: ['desk-performance'], queryFn: () => fetch(`${API}/desks/performance`).then(r => r.json()), refetchInterval: 60000 })
}

function useDailyReport() {
  return useQuery<Record<string, any>>({ queryKey: ['daily-report'], queryFn: () => fetch(`${API}/report/daily`).then(r => r.json()), refetchInterval: 60000 })
}

function useSystemEvents() {
  return useQuery<any[]>({ queryKey: ['system-events'], queryFn: () => fetch(`${API}/system/events?limit=10`).then(r => r.json()), refetchInterval: 30000 })
}

// ---------------------------------------------------------------------------
// Action Buttons
// ---------------------------------------------------------------------------
function ActionButtons() {
  const qc = useQueryClient()
  const scanMutation = useMutation({
    mutationFn: () => fetch(`${API}/desks/scan`, { method: 'POST' }).then(r => r.json()),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['desks'] }),
  })
  const deployMutation = useMutation({
    mutationFn: () => fetch(`${API}/desks/deploy`, { method: 'POST' }).then(r => r.json()),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['desks'] }),
  })
  const markMutation = useMutation({
    mutationFn: () => fetch(`${API}/desks/mark`, { method: 'POST' }).then(r => r.json()),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['desks'] }),
  })

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-3 gap-2">
        <button
          onClick={() => scanMutation.mutate()}
          disabled={scanMutation.isPending}
          className={clsx(
            'flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border text-[10px] font-semibold transition-all',
            scanMutation.isPending ? 'opacity-50' : 'hover:bg-green-950/30',
            'border-green-800/50 text-green-400',
          )}
        >
          <Play size={12} />
          {scanMutation.isPending ? 'Scanning...' : 'Scan'}
        </button>
        <button
          onClick={() => deployMutation.mutate()}
          disabled={deployMutation.isPending}
          className={clsx(
            'flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border text-[10px] font-semibold transition-all',
            deployMutation.isPending ? 'opacity-50' : 'hover:bg-purple-950/30',
            'border-purple-800/50 text-purple-400',
          )}
        >
          <Target size={12} />
          {deployMutation.isPending ? 'Deploying...' : 'Deploy'}
        </button>
        <button
          onClick={() => markMutation.mutate()}
          disabled={markMutation.isPending}
          className={clsx(
            'flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg border text-[10px] font-semibold transition-all',
            markMutation.isPending ? 'opacity-50' : 'hover:bg-blue-950/30',
            'border-blue-800/50 text-blue-400',
          )}
        >
          <RefreshCw size={12} />
          {markMutation.isPending ? 'Marking...' : 'Mark'}
        </button>
      </div>
      {/* Results */}
      {scanMutation.data && (
        <p className="text-[9px] text-green-400">
          Scan: {scanMutation.data.proposals} proposals, {scanMutation.data.rejected} rejected, {scanMutation.data.ranking} ranked
        </p>
      )}
      {deployMutation.data && (
        <p className="text-[9px] text-purple-400">
          Deploy: {deployMutation.data.booked} trades booked
        </p>
      )}
      {markMutation.data && (
        <p className="text-[9px] text-blue-400">
          Mark: {markMutation.data.marked} trades, P&L ${markMutation.data.total_pnl?.toFixed(0)}
        </p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Maverick Identity
// ---------------------------------------------------------------------------
function MaverickCard({ desks }: { desks: DeskData[] }) {
  // Group by market — never mix currencies
  const markets = new Map<string, DeskData[]>()
  for (const d of desks) {
    const m = d.market || 'US'
    if (!markets.has(m)) markets.set(m, [])
    markets.get(m)!.push(d)
  }

  const totalOpen = desks.reduce((s, d) => s + d.open_positions, 0)
  const totalClosed = desks.reduce((s, d) => s + d.closed_trades, 0)
  const totalWins = desks.reduce((s, d) => s + d.wins, 0)
  const totalLosses = desks.reduce((s, d) => s + d.losses, 0)
  const winRate = (totalWins + totalLosses) > 0 ? (totalWins / (totalWins + totalLosses) * 100) : 0

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
              "I trade {desks.length} desks across {markets.size} market{markets.size > 1 ? 's' : ''} with 11 gates."
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          {Array.from(markets.keys()).map(m => {
            const meta = MARKET_META[m] || { flag: '', label: m, tz: '' }
            const open = isMarketOpen(m)
            return (
              <span key={m} className={clsx(
                'px-2 py-0.5 rounded-full text-[9px] font-semibold border flex items-center gap-1',
                open ? 'bg-green-900/30 text-green-400 border-green-800' : 'bg-zinc-800 text-zinc-400 border-zinc-700',
              )}>
                <span>{meta.flag}</span>
                <span>{m}</span>
                <span className={clsx('w-1.5 h-1.5 rounded-full', open ? 'bg-green-400' : 'bg-zinc-600')} />
              </span>
            )
          })}
          <span className="px-2 py-0.5 rounded-full bg-purple-900/30 text-purple-400 text-[9px] font-mono border border-purple-800">11 gates</span>
        </div>
      </div>

      {/* Per-Market Aggregates — never mix currencies */}
      <div className="mt-4 pt-4 border-t border-border-secondary space-y-3">
        {Array.from(markets.entries()).map(([market, mDesks]) => {
          const meta = MARKET_META[market] || { flag: '', label: market, tz: '' }
          const cur = mDesks[0]?.currency || 'USD'
          const mPnl = mDesks.reduce((s, d) => s + d.total_pnl, 0)
          const mCapital = mDesks.reduce((s, d) => s + d.capital, 0)
          const mTheta = mDesks.reduce((s, d) => s + d.daily_theta, 0)
          const mOpen = mDesks.reduce((s, d) => s + d.open_positions, 0)

          return (
            <div key={market} className="flex items-center gap-6">
              <span className="text-sm">{meta.flag}</span>
              <Metric label={`Capital (${cur})`} value={nCur(mCapital, cur)} />
              <Metric label={`P&L (${cur})`} value={nCur(mPnl, cur)} color={mPnl >= 0 ? 'text-green-400' : 'text-red-400'} />
              <Metric label={`\u0398/day (${cur})`} value={mTheta !== 0 ? nCur(mTheta, cur) : '--'} color="text-green-400" />
              <Metric label="Open" value={`${mOpen}`} />
              <Metric label="Desks" value={`${mDesks.length}`} />
            </div>
          )
        })}

        {/* Cross-market stats (counts only, no currency) */}
        <div className="flex items-center gap-6 pt-2 border-t border-border-secondary/50">
          <Metric label="Total Open" value={`${totalOpen}`} />
          <Metric label="Total Closed" value={`${totalClosed}`} />
          <Metric label="Win Rate" value={winRate > 0 ? `${winRate.toFixed(0)}%` : '--'} color={winRate >= 60 ? 'text-green-400' : winRate > 0 ? 'text-amber-400' : undefined} />
          <Metric label="W / L" value={`${totalWins} / ${totalLosses}`} />
        </div>
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
  const cur = desk.currency || 'USD'
  const market = desk.market || 'US'
  const meta = MARKET_META[market] || { flag: '', label: market, tz: '' }
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
            <div className="flex items-center gap-1.5">
              <h3 className="text-sm font-bold text-text-primary">{desk.display_name}</h3>
              <span className="text-[10px]">{meta.flag}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[9px] text-text-muted font-mono">{desk.name}</span>
              <span className="text-[8px] text-text-muted">|</span>
              <span className="text-[8px] text-text-muted">{desk.broker}</span>
              <span className="text-[8px] text-text-muted">|</span>
              <span className="text-[8px] text-text-muted">{cur}</span>
            </div>
          </div>
        </div>
        <span className="text-base font-bold font-mono text-text-primary">{nCur(desk.capital, cur)}</span>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-3 gap-y-2 text-[10px] mb-3">
        <KV label="P&L" value={nCur(desk.total_pnl, cur)} color={pnlColor} />
        <KV label="Win Rate" value={desk.win_rate > 0 ? `${desk.win_rate.toFixed(0)}%` : '--'} color={desk.win_rate >= 60 ? 'text-green-400' : undefined} />
        <KV label="Open" value={`${desk.open_positions}`} />
        <KV label="Realized" value={nCur(desk.realized_pnl, cur)} color={desk.realized_pnl >= 0 ? 'text-green-400' : 'text-red-400'} />
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

function HealthCellR({ value, data }: ICellRendererParams) {
  const [detail, setDetail] = useState<any>(null)
  const colors: Record<string, { bg: string; text: string; label: string }> = {
    healthy: { bg: 'bg-green-900/30', text: 'text-green-400', label: 'OK' },
    tested: { bg: 'bg-yellow-900/30', text: 'text-yellow-400', label: 'TST' },
    breached: { bg: 'bg-red-900/30', text: 'text-red-400', label: 'BRK' },
    exit_triggered: { bg: 'bg-red-900/50', text: 'text-red-300', label: 'EXIT' },
  }
  const c = colors[value] || { bg: 'bg-zinc-800', text: 'text-zinc-400', label: value || '--' }

  const fetchDetail = async () => {
    if (!data?.id) return
    try {
      const res = await fetch(`${API}/trades/${data.id}/health`)
      if (res.ok) setDetail(await res.json())
    } catch { /* ignore */ }
  }

  if (detail) {
    return (
      <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={() => setDetail(null)}>
        <div className="bg-bg-primary border border-border-primary rounded-xl max-w-lg w-full max-h-[70vh] overflow-y-auto p-4" onClick={e => e.stopPropagation()}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-text-primary">{detail.ticker} — Health Detail</h3>
            <button onClick={() => setDetail(null)} className="text-text-muted text-xs">Close</button>
          </div>

          {/* Status */}
          <div className="grid grid-cols-3 gap-2 mb-3 text-[10px]">
            <div className="bg-bg-tertiary rounded p-2">
              <p className="text-text-muted">Health</p>
              <p className={clsx('font-bold', colors[detail.health_status]?.text || 'text-text-primary')}>
                {detail.health_status?.toUpperCase() || '--'}
              </p>
            </div>
            <div className="bg-bg-tertiary rounded p-2">
              <p className="text-text-muted">P&L</p>
              <p className={clsx('font-bold', (detail.total_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400')}>
                {nCur(detail.total_pnl || 0, data?.currency || 'USD')}
              </p>
            </div>
            <div className="bg-bg-tertiary rounded p-2">
              <p className="text-text-muted">Regime</p>
              <p className="font-bold text-blue-400">{detail.regime_at_entry || '--'}</p>
            </div>
          </div>

          {/* Breakevens */}
          {(detail.breakeven_low || detail.breakeven_high) && (
            <div className="mb-3">
              <p className="text-[10px] font-semibold text-text-muted mb-1">Breakevens</p>
              <div className="flex items-center gap-2 text-[10px]">
                <span className="text-red-400">${detail.breakeven_low?.toFixed(2) || '?'}</span>
                <div className="flex-1 h-1 bg-bg-tertiary rounded-full overflow-hidden relative">
                  <div className="absolute inset-0 bg-gradient-to-r from-red-500 via-green-500 to-red-500 opacity-30 rounded-full" />
                </div>
                <span className="text-red-400">${detail.breakeven_high?.toFixed(2) || '?'}</span>
              </div>
            </div>
          )}

          {/* Exit Plan */}
          {detail.exit_plan && (
            <div className="mb-3">
              <p className="text-[10px] font-semibold text-text-muted mb-1">Exit Plan</p>
              <div className="grid grid-cols-2 gap-1 text-[9px]">
                {detail.exit_plan.profit_targets?.map((t: any, i: number) => (
                  <div key={i} className="flex items-center gap-1 text-green-400">
                    <span>TP{i+1}: {t.pct_from_entry ? `${(t.pct_from_entry*100).toFixed(0)}%` : t.price}</span>
                    <span className="text-text-muted">— {t.action || 'close'}</span>
                  </div>
                ))}
                {detail.exit_plan.stop_loss && (
                  <div className="flex items-center gap-1 text-red-400">
                    <span>SL: {detail.exit_plan.stop_loss.pct_from_entry ? `${(detail.exit_plan.stop_loss.pct_from_entry*100).toFixed(0)}%` : detail.exit_plan.stop_loss.price}</span>
                  </div>
                )}
                {detail.exit_plan.dte_exit_threshold && (
                  <div className="text-amber-400">DTE exit: {detail.exit_plan.dte_exit_threshold}d</div>
                )}
                {detail.exit_plan.regime_change_action && (
                  <div className="text-purple-400">Regime change: {detail.exit_plan.regime_change_action}</div>
                )}
              </div>
            </div>
          )}

          {/* Adjustment History */}
          {detail.adjustment_history?.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-text-muted mb-1">Adjustment History</p>
              {detail.adjustment_history.map((adj: any, i: number) => (
                <div key={i} className="text-[9px] text-text-secondary py-0.5 border-b border-border-secondary/30">
                  <span className="text-amber-400">{adj.type || adj.action}</span> — {adj.rationale}
                </div>
              ))}
            </div>
          )}

          {/* Last checked */}
          {detail.health_checked_at && (
            <p className="text-[8px] text-text-muted mt-2">
              Last checked: {new Date(detail.health_checked_at).toLocaleString()}
            </p>
          )}
        </div>
      </div>
    )
  }

  return (
    <button onClick={fetchDetail} className={clsx('text-[9px] px-1.5 py-[1px] rounded font-semibold cursor-pointer hover:opacity-80', c.bg, c.text)}>
      {c.label}
    </button>
  )
}

const GRID_STYLE = { fontSize: '11px', fontFamily: "'JetBrains Mono', monospace" }
const CELL_R: ColDef = { cellStyle: { ...GRID_STYLE, display: 'flex', alignItems: 'center', justifyContent: 'flex-end' } }
const CELL_L: ColDef = { cellStyle: { ...GRID_STYLE, display: 'flex', alignItems: 'center' } }

// B: Explain button cell renderer
function ExplainCell({ data }: ICellRendererParams) {
  const [explanation, setExplanation] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const fetchExplain = async () => {
    if (!data?.id) return
    setLoading(true)
    try {
      const res = await fetch(`${API}/trades/${data.id}/explain`)
      if (res.ok) {
        setExplanation(await res.json())
      }
    } catch { /* ignore */ }
    setLoading(false)
  }

  if (explanation) {
    return (
      <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={() => setExplanation(null)}>
        <div className="bg-bg-primary border border-border-primary rounded-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto p-5" onClick={e => e.stopPropagation()}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-text-primary">
              {explanation.ticker} {explanation.strategy_type} — Decision Lineage
            </h3>
            <button onClick={() => setExplanation(null)} className="text-text-muted hover:text-text-primary text-xs">Close</button>
          </div>

          {/* Entry Analytics */}
          <div className="grid grid-cols-4 gap-2 mb-3 text-[10px]">
            {explanation.pop_at_entry != null && <div className="bg-bg-tertiary rounded p-2 text-center"><p className="text-text-muted">POP</p><p className="font-bold text-green-400">{(explanation.pop_at_entry * 100).toFixed(0)}%</p></div>}
            {explanation.ev_at_entry != null && <div className="bg-bg-tertiary rounded p-2 text-center"><p className="text-text-muted">EV</p><p className="font-bold text-green-400">${explanation.ev_at_entry.toFixed(0)}</p></div>}
            {explanation.regime_at_entry && <div className="bg-bg-tertiary rounded p-2 text-center"><p className="text-text-muted">Regime</p><p className="font-bold text-blue-400">{explanation.regime_at_entry}</p></div>}
            {explanation.income_yield_roc != null && <div className="bg-bg-tertiary rounded p-2 text-center"><p className="text-text-muted">ROC</p><p className="font-bold text-amber-400">{(explanation.income_yield_roc * 100).toFixed(1)}%</p></div>}
          </div>

          {/* Gates */}
          {explanation.gates?.length > 0 && (
            <div className="mb-3">
              <p className="text-[10px] font-semibold text-text-muted mb-1">GATES</p>
              <div className="grid grid-cols-2 gap-1">
                {explanation.gates.map((g: any, i: number) => (
                  <div key={i} className="flex items-center gap-1.5 text-[9px]">
                    <span className={g.passed ? 'text-green-400' : 'text-red-400'}>{g.passed ? '\u2713' : '\u2717'}</span>
                    <span className="text-text-muted w-20">{g.name}</span>
                    <span className="text-text-primary font-mono">{String(g.value).slice(0, 15)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Commentary */}
          {explanation.commentary && Object.keys(explanation.commentary).length > 0 && (
            <div className="mb-3">
              <p className="text-[10px] font-semibold text-text-muted mb-1">COMMENTARY</p>
              {Object.entries(explanation.commentary).map(([source, comments]: [string, any]) => (
                <div key={source} className="mb-1">
                  <p className="text-[9px] text-cyan-400">[{source}]</p>
                  {(Array.isArray(comments) ? comments : [comments]).map((c: string, i: number) => (
                    <p key={i} className="text-[9px] text-text-muted pl-2">{c}</p>
                  ))}
                </div>
              ))}
            </div>
          )}

          {/* Data Gaps */}
          {explanation.data_gaps?.length > 0 && (
            <div className="mb-3">
              <p className="text-[10px] font-semibold text-amber-400 mb-1">DATA GAPS</p>
              {explanation.data_gaps.map((gap: any, i: number) => (
                <p key={i} className="text-[9px] text-text-muted">{gap.field}: {gap.reason} (impact: {gap.impact})</p>
              ))}
            </div>
          )}

          {/* Exit info */}
          {explanation.status !== 'open' && (
            <div className="border-t border-border-secondary pt-2">
              <p className="text-[10px] text-text-muted">
                Exit: {explanation.exit_reason} | P&L: ${explanation.total_pnl?.toFixed(2)} | Held: {explanation.days_held}d
              </p>
            </div>
          )}

          {/* Adjustments */}
          {explanation.adjustment_history?.length > 0 && (
            <div className="border-t border-border-secondary pt-2 mt-2">
              <p className="text-[10px] font-semibold text-text-muted mb-1">ADJUSTMENTS</p>
              {explanation.adjustment_history.map((adj: any, i: number) => (
                <p key={i} className="text-[9px] text-text-muted">{adj.type} — {adj.rationale}</p>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <button
      onClick={fetchExplain}
      disabled={loading}
      className="text-[9px] text-accent-blue hover:underline"
    >
      {loading ? '...' : 'explain'}
    </button>
  )
}

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
  { field: 'income_yield_roc', headerName: 'ROC', width: 50, ...CELL_R, valueFormatter: (p: any) => p.value != null ? `${(Number(p.value) * 100).toFixed(0)}%` : '--' },
  { headerName: '', width: 50, cellRenderer: ExplainCell, ...CELL_L },
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
  { headerName: '', width: 50, cellRenderer: ExplainCell, ...CELL_L },
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
  const { data: perfData } = useDeskPerformance()
  const { data: reportData } = useDailyReport()
  const { data: sysEvents } = useSystemEvents()

  if (isLoading) {
    return <div className="flex items-center justify-center h-full text-text-muted text-sm">Loading desks...</div>
  }

  return (
    <div className="h-full overflow-y-auto bg-bg-primary">
      <div className="max-w-6xl mx-auto px-6 py-6 space-y-6">

        {/* Maverick Identity */}
        <MaverickCard desks={deskList} />

        {/* Philosophy + Actions */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Philosophy */}
          <div className="border border-border-secondary rounded-xl p-4 bg-bg-secondary/30">
            <h3 className="text-xs font-semibold text-text-primary mb-3">Trading Philosophy</h3>
            <div className="grid grid-cols-2 gap-2">
              {[
                { icon: Shield, color: 'text-red-400', title: 'Capital First', desc: 'Defined risk only. 2% max per trade. 11 gates.' },
                { icon: Radio, color: 'text-green-400', title: 'Trade Small, Trade Frequent', desc: 'Mathematical edge over many trades. Sample size > single bets.' },
                { icon: Brain, color: 'text-purple-400', title: 'Every Event Is Data', desc: 'ML learns from every close. System gets smarter over time.' },
                { icon: Eye, color: 'text-blue-400', title: 'Full Transparency', desc: '"Why this trade?" has a complete answer. Always.' },
              ].map(p => (
                <div key={p.title} className="flex items-start gap-2 p-2 rounded bg-bg-tertiary/50">
                  <p.icon size={14} className={clsx(p.color, 'mt-0.5 shrink-0')} />
                  <div>
                    <p className="text-[10px] font-semibold text-text-primary">{p.title}</p>
                    <p className="text-[9px] text-text-muted leading-snug">{p.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Actions + Workflow */}
          <div className="border border-border-secondary rounded-xl p-4 bg-bg-secondary/30">
            <h3 className="text-xs font-semibold text-text-primary mb-3">Actions & Monitoring</h3>
            <ActionButtons />
            <div className="mt-3 pt-3 border-t border-border-secondary">
              <p className="text-[9px] text-text-muted mb-2 font-semibold">Automatic Schedule:</p>
              <div className="grid grid-cols-2 gap-1 text-[9px]">
                <div className="flex items-center gap-1.5 text-text-muted">
                  <Clock size={10} className="text-blue-400" />
                  <span>Pre-market: Context + Scan</span>
                </div>
                <div className="flex items-center gap-1.5 text-text-muted">
                  <RefreshCw size={10} className="text-purple-400" />
                  <span>Every 30 min: Mark + Health</span>
                </div>
                <div className="flex items-center gap-1.5 text-text-muted">
                  <Zap size={10} className="text-red-400" />
                  <span>Every 2 min: 0DTE fast cycle</span>
                </div>
                <div className="flex items-center gap-1.5 text-text-muted">
                  <AlertTriangle size={10} className="text-amber-400" />
                  <span>3:30 PM: Overnight risk</span>
                </div>
                <div className="flex items-center gap-1.5 text-text-muted">
                  <Brain size={10} className="text-cyan-400" />
                  <span>Every 10 cycles: ML learning</span>
                </div>
                <div className="flex items-center gap-1.5 text-text-muted">
                  <Target size={10} className="text-green-400" />
                  <span>On exit: Auto-close + bandit update</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Desk Cards — grouped by market */}
        {(() => {
          const byMarket = new Map<string, DeskData[]>()
          for (const d of deskList) {
            const m = d.market || 'US'
            if (!byMarket.has(m)) byMarket.set(m, [])
            byMarket.get(m)!.push(d)
          }
          return Array.from(byMarket.entries()).map(([market, mDesks]) => {
            const meta = MARKET_META[market] || { flag: '', label: market, tz: '' }
            const open = isMarketOpen(market)
            return (
              <div key={market} className="space-y-2">
                {/* Market header */}
                <div className="flex items-center gap-2 px-1">
                  <span className="text-sm">{meta.flag}</span>
                  <span className="text-xs font-semibold text-text-primary">{meta.label}</span>
                  <span className={clsx('text-[9px] px-1.5 py-0.5 rounded-full font-semibold',
                    open ? 'bg-green-900/30 text-green-400 border border-green-800' : 'bg-zinc-800 text-zinc-500 border border-zinc-700'
                  )}>{open ? `Open (${meta.tz})` : `Closed (${meta.tz})`}</span>
                  <span className="text-[9px] text-text-muted">{mDesks[0]?.currency}</span>
                  <div className="flex-1 h-px bg-border-secondary" />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {mDesks.map(desk => (
                    <DeskCard
                      key={desk.name}
                      desk={desk}
                      selected={desk.name === selectedDesk}
                      onClick={() => setSelectedDesk(desk.name)}
                    />
                  ))}
                </div>
              </div>
            )
          })
        })()}

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

        {/* Performance Analytics + System Health (Tier 1 gaps A, E, F, H) */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* A: Desk Performance — Sharpe/Drawdown */}
          {perfData?.desks && Object.keys(perfData.desks).length > 0 && (
            <div className="border border-border-secondary rounded-xl p-4 bg-bg-secondary/30">
              <h3 className="text-xs font-semibold text-text-primary mb-3 flex items-center gap-2">
                <BarChart3 size={14} className="text-cyan-400" /> Performance Analytics
              </h3>
              <div className="space-y-2 text-[10px]">
                <div className="grid grid-cols-6 gap-1 text-text-muted font-semibold">
                  <span>Desk</span><span className="text-right">Sharpe</span><span className="text-right">Sortino</span>
                  <span className="text-right">MaxDD</span><span className="text-right">Win%</span><span className="text-right">Avg P&L</span>
                </div>
                {Object.entries(perfData.desks).map(([name, d]: [string, any]) => (
                  <div key={name} className="grid grid-cols-6 gap-1 font-mono">
                    <span className="text-text-primary">{name.replace('desk_', '')}</span>
                    <span className={clsx('text-right', (d.sharpe || 0) > 1 ? 'text-green-400' : (d.sharpe || 0) > 0 ? 'text-amber-400' : 'text-red-400')}>
                      {d.sharpe != null ? d.sharpe.toFixed(2) : '--'}
                    </span>
                    <span className="text-right text-text-muted">{d.sortino != null ? d.sortino.toFixed(2) : '--'}</span>
                    <span className="text-right text-red-400">{d.max_drawdown_pct != null ? `${d.max_drawdown_pct.toFixed(1)}%` : '--'}</span>
                    <span className="text-right">{d.win_rate != null ? `${d.win_rate}%` : '--'}</span>
                    <span className={clsx('text-right', (d.avg_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400')}>
                      {d.avg_pnl != null ? `$${d.avg_pnl.toFixed(0)}` : '--'}
                    </span>
                  </div>
                ))}
              </div>
              {perfData.recommendation && (
                <p className="text-[9px] text-cyan-400 mt-2 pt-2 border-t border-border-secondary">{perfData.recommendation}</p>
              )}
            </div>
          )}

          {/* E: Daily Report Summary */}
          {reportData?.messages && (
            <div className="border border-border-secondary rounded-xl p-4 bg-bg-secondary/30">
              <h3 className="text-xs font-semibold text-text-primary mb-3 flex items-center gap-2">
                <Activity size={14} className="text-green-400" /> Daily Report
              </h3>
              <div className="space-y-1 text-[10px]">
                {reportData.messages.map((msg: string, i: number) => (
                  <p key={i} className={clsx('text-text-secondary', msg.includes('AT RISK') ? 'text-red-400 font-semibold' : '')}>
                    {msg}
                  </p>
                ))}
              </div>
              {reportData.positions_at_risk?.length > 0 && (
                <div className="mt-2 pt-2 border-t border-border-secondary">
                  <p className="text-[9px] text-red-400 font-semibold mb-1">Positions at Risk:</p>
                  {reportData.positions_at_risk.map((p: any, i: number) => (
                    <p key={i} className="text-[9px] text-text-muted">
                      {p.ticker} ({p.desk}) — {p.health} — P&L ${p.pnl >= 0 ? '+' : ''}{p.pnl.toFixed(0)}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* F: System Alerts */}
        {sysEvents && sysEvents.length > 0 && (
          <div className="border border-border-secondary rounded-xl p-4 bg-bg-secondary/30">
            <h3 className="text-xs font-semibold text-text-primary mb-3 flex items-center gap-2">
              <AlertTriangle size={14} className="text-amber-400" /> System Alerts
              <span className="text-[9px] text-text-muted ml-auto">{sysEvents.length} recent</span>
            </h3>
            <div className="space-y-1 text-[10px]">
              {sysEvents.slice(0, 5).map((e: any) => (
                <div key={e.id} className="flex items-center gap-2">
                  <span className={clsx('px-1 py-0.5 rounded text-[8px] font-mono font-bold',
                    e.severity === 'HIGH' ? 'bg-red-900/30 text-red-400' :
                    e.severity === 'WARNING' ? 'bg-amber-900/30 text-amber-400' :
                    'bg-blue-900/30 text-blue-400'
                  )}>{e.severity}</span>
                  <span className="text-text-muted">{e.source}</span>
                  <span className="text-text-secondary flex-1 truncate">{e.message}</span>
                  <span className="text-text-muted text-[8px]">
                    {e.timestamp ? new Date(e.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : ''}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
