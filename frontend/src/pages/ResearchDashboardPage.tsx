import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { clsx } from 'clsx'
import { RefreshCw, Plus, X, Settings, ChevronDown } from 'lucide-react'
import { useResearch, useRefreshResearch, useWatchlist, useAddWatchlistTicker, useRemoveWatchlistTicker } from '../hooks/useResearch'
import { Spinner } from '../components/common/Spinner'
import { AgentBadge } from '../components/common/AgentBadge'
import type { ResearchEntry, ResearchMacroContext, MacroEvent } from '../api/types'

// ---------------------------------------------------------------------------
// Regime Colors
// ---------------------------------------------------------------------------

const RC: Record<number, { color: string; bg: string; border: string; label: string }> = {
  1: { color: 'text-green-400', bg: 'bg-green-900/30', border: 'border-green-700', label: 'Low Vol MR' },
  2: { color: 'text-amber-400', bg: 'bg-amber-900/30', border: 'border-amber-700', label: 'High Vol MR' },
  3: { color: 'text-blue-400', bg: 'bg-blue-900/30', border: 'border-blue-700', label: 'Low Vol Trend' },
  4: { color: 'text-red-400', bg: 'bg-red-900/30', border: 'border-red-700', label: 'High Vol Trend' },
}
function getRC(r: number | null) {
  return RC[r ?? 0] || { color: 'text-text-muted', bg: 'bg-bg-tertiary', border: 'border-border-secondary', label: '?' }
}

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

function fmt(v: number | null, d = 2): string { return v == null ? '--' : v.toFixed(d) }
function fmtPct(v: number | null): string { return v == null ? '--' : `${(v * 100).toFixed(1)}%` }
function fmtBigNum(v: number | null): string {
  if (v == null) return '--'
  if (Math.abs(v) >= 1e12) return `${(v / 1e12).toFixed(1)}T`
  if (Math.abs(v) >= 1e9) return `${(v / 1e9).toFixed(1)}B`
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  return v.toLocaleString()
}

function TrendArrow({ direction }: { direction: string | null }) {
  if (!direction) return <span className="text-text-muted">--</span>
  if (direction === 'bullish' || direction === 'up') return <span className="text-green-400">&#9650;</span>
  if (direction === 'bearish' || direction === 'down') return <span className="text-red-400">&#9660;</span>
  return <span className="text-text-muted">&#9654;</span>
}

function RsiCell({ value, ob, os }: { value: number | null; ob: boolean; os: boolean }) {
  if (value == null) return <span className="text-text-muted">--</span>
  return (
    <div className="flex items-center gap-1">
      <span className={clsx('font-mono', ob ? 'text-red-400 font-bold' : os ? 'text-green-400 font-bold' : 'text-text-primary')}>
        {value.toFixed(1)}
      </span>
      <div className="w-8 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
        <div
          className={clsx('h-full rounded-full', value > 70 ? 'bg-red-500' : value < 30 ? 'bg-green-500' : 'bg-accent-blue')}
          style={{ width: `${Math.min(value, 100)}%` }}
        />
      </div>
    </div>
  )
}

function MacdCell({ hist, bullCross, bearCross }: { hist: number | null; bullCross: boolean; bearCross: boolean }) {
  if (hist == null) return <span className="text-text-muted">--</span>
  return (
    <div className="flex items-center gap-1">
      <span className={clsx('font-mono', hist > 0 ? 'text-green-400' : 'text-red-400')}>
        {hist > 0 ? '+' : ''}{hist.toFixed(3)}
      </span>
      {bullCross && <span className="text-green-400 text-2xs font-bold">BX</span>}
      {bearCross && <span className="text-red-400 text-2xs font-bold">SX</span>}
    </div>
  )
}

function ConfBar({ value }: { value: number | null }) {
  if (value == null) return <span className="text-text-muted">--</span>
  const pct = Math.round(value * 100)
  const c = pct >= 80 ? 'bg-green-500' : pct >= 50 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-1">
      <div className="w-10 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full', c)} style={{ width: `${pct}%` }} />
      </div>
      <span className={clsx('font-mono text-2xs', pct >= 80 ? 'text-green-400' : pct >= 50 ? 'text-amber-400' : 'text-red-400')}>
        {pct}%
      </span>
    </div>
  )
}

const VERDICT_STYLE: Record<string, { bg: string; text: string; border: string }> = {
  go: { bg: 'bg-green-900/30', text: 'text-green-400', border: 'border-green-700' },
  caution: { bg: 'bg-amber-900/30', text: 'text-amber-400', border: 'border-amber-700' },
  no_go: { bg: 'bg-red-900/30', text: 'text-red-400', border: 'border-red-700' },
}

function VerdictBadge({ verdict, strategy, confidence }: { verdict: string | null; strategy: string | null; confidence: number | null }) {
  if (!verdict) return <span className="text-text-muted text-2xs">--</span>
  const v = verdict.toLowerCase()
  const s = VERDICT_STYLE[v] || VERDICT_STYLE.no_go
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center gap-1">
        <span className={clsx('px-1 py-0.5 rounded text-2xs font-semibold border uppercase', s.bg, s.text, s.border)}>
          {v === 'no_go' ? 'NO' : v}
        </span>
        {confidence != null && (
          <div className="w-6 h-1 bg-bg-tertiary rounded-full overflow-hidden">
            <div className={clsx('h-full rounded-full', v === 'go' ? 'bg-green-500' : v === 'caution' ? 'bg-amber-500' : 'bg-red-500')} style={{ width: `${Math.round(confidence * 100)}%` }} />
          </div>
        )}
      </div>
      {strategy && <span className="text-text-muted text-2xs truncate max-w-[80px]" title={strategy}>{strategy}</span>}
    </div>
  )
}

function SmScoreBar({ value }: { value: number | null }) {
  if (value == null) return <span className="text-text-muted text-2xs">--</span>
  const pct = Math.round(value * 100)
  const c = pct >= 60 ? 'bg-green-500' : pct >= 30 ? 'bg-amber-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-1">
      <div className="w-10 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full', c)} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-2xs text-text-secondary">{pct}%</span>
    </div>
  )
}

function PctCell({ value }: { value: number | null }) {
  if (value == null) return <span className="text-text-muted">--</span>
  const v = value > 1 || value < -1 ? value : value * 100  // handle both 0.05 and 5.0 formats
  return (
    <span className={clsx('font-mono', v > 0 ? 'text-green-400' : v < 0 ? 'text-red-400' : 'text-text-muted')}>
      {v > 0 ? '+' : ''}{v.toFixed(1)}%
    </span>
  )
}

// ---------------------------------------------------------------------------
// Impact Badge
// ---------------------------------------------------------------------------
const IMPACT_STYLE: Record<string, { bg: string; text: string }> = {
  high: { bg: 'bg-red-900/30', text: 'text-red-400' },
  medium: { bg: 'bg-amber-900/30', text: 'text-amber-400' },
  low: { bg: 'bg-green-900/30', text: 'text-green-400' },
}
function ImpactBadge({ impact }: { impact: string }) {
  const s = IMPACT_STYLE[impact] || IMPACT_STYLE.low
  return <span className={clsx('px-1.5 py-0.5 rounded text-2xs font-semibold uppercase', s.bg, s.text)}>{impact}</span>
}

function daysFromNow(dateStr: string): number {
  return Math.ceil((new Date(dateStr).getTime() - Date.now()) / 86400000)
}

// ---------------------------------------------------------------------------
// Column groups for toggling
// ---------------------------------------------------------------------------

type ColGroup = 'core' | 'regime' | 'phase' | 'technicals' | 'fundamentals' | 'momentum' | 'vcp' | 'opportunities' | 'smartmoney' | 'levels'

const COL_GROUPS: { key: ColGroup; label: string }[] = [
  { key: 'core', label: 'Core' },
  { key: 'regime', label: 'Regime' },
  { key: 'phase', label: 'Phase' },
  { key: 'opportunities', label: 'Opportunities' },
  { key: 'smartmoney', label: 'Smart Money' },
  { key: 'levels', label: 'Levels' },
  { key: 'technicals', label: 'Technicals' },
  { key: 'momentum', label: 'Momentum' },
  { key: 'vcp', label: 'VCP' },
  { key: 'fundamentals', label: 'Fundamentals' },
]

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export function ResearchDashboardPage() {
  const { data: res, isLoading, isError, error } = useResearch()
  const refreshMutation = useRefreshResearch()
  const navigate = useNavigate()
  const [activeGroups, setActiveGroups] = useState<Set<ColGroup>>(new Set(['core', 'regime', 'technicals']))
  const [showWatchlistManager, setShowWatchlistManager] = useState(false)

  const toggle = (g: ColGroup) => {
    setActiveGroups(prev => {
      const next = new Set(prev)
      if (next.has(g)) next.delete(g); else next.add(g)
      return next
    })
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-accent-red text-sm">Failed to load research: {(error as Error)?.message}</div>
      </div>
    )
  }

  const data = res?.data || []
  const macro = res?.macro

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h1 className="text-sm font-semibold text-text-primary">Market Analysis</h1>
          <AgentBadge agent="quant_research" />
        </div>
        <div className="flex items-center gap-3">
          {/* Column group toggles */}
          <div className="flex gap-1">
            {COL_GROUPS.map(g => (
              <button
                key={g.key}
                onClick={() => toggle(g.key)}
                className={clsx(
                  'px-2 py-0.5 rounded text-2xs font-medium transition-colors',
                  activeGroups.has(g.key) ? 'bg-accent-blue/20 text-accent-blue border border-accent-blue/30' : 'bg-bg-tertiary text-text-muted hover:text-text-secondary',
                )}
              >
                {g.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => setShowWatchlistManager(v => !v)}
            className={clsx(
              'flex items-center gap-1 px-2 py-1 rounded text-xs hover:bg-bg-hover',
              showWatchlistManager ? 'text-accent-blue bg-accent-blue/10' : 'text-text-secondary',
            )}
          >
            <Settings size={12} />
            Watchlist
          </button>
          <button
            onClick={() => refreshMutation.mutate(undefined)}
            disabled={refreshMutation.isPending}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs text-accent-blue hover:bg-bg-hover disabled:opacity-50"
          >
            <RefreshCw size={12} className={clsx(refreshMutation.isPending && 'animate-spin')} />
            Refresh
          </button>
          <span className="text-2xs text-text-muted">
            {isLoading ? 'Loading...' : `${data.length} symbols`}
          </span>
          {res?.from_db && !refreshMutation.isPending && (
            <span className="text-2xs text-amber-400">Cached</span>
          )}
        </div>
      </div>

      {/* Watchlist manager */}
      {showWatchlistManager && <WatchlistManager onClose={() => setShowWatchlistManager(false)} />}

      {/* Macro strip */}
      {macro && <MacroStrip macro={macro} />}

      {/* Main table */}
      {isLoading ? (
        <div className="card card-body flex items-center justify-center py-8">
          <Spinner size="sm" />
          <span className="text-xs text-text-muted ml-2">Loading research data...</span>
        </div>
      ) : data.length === 0 ? (
        <div className="card card-body text-center py-6 text-text-muted text-xs">
          No watchlist configured. Add tickers to config/market_watchlist.yaml
        </div>
      ) : (
        <div className="card">
          <div className="card-body p-0 overflow-x-auto">
            <table className="w-full text-xs whitespace-nowrap">
              <thead>
                <tr className="text-text-muted text-left border-b border-border-secondary text-2xs uppercase tracking-wider">
                  {/* Core — always visible */}
                  <th className="py-1.5 px-2 sticky left-0 bg-bg-primary z-10">Ticker</th>
                  {activeGroups.has('core') && <>
                    <th className="py-1.5 px-2 text-right">Price</th>
                    <th className="py-1.5 px-2">Sector</th>
                    <th className="py-1.5 px-2 text-right">MCap</th>
                  </>}
                  {activeGroups.has('regime') && <>
                    <th className="py-1.5 px-2">Regime</th>
                    <th className="py-1.5 px-2">Conf</th>
                    <th className="py-1.5 px-2 text-center">Trend</th>
                    <th className="py-1.5 px-2">Strategy</th>
                  </>}
                  {activeGroups.has('phase') && <>
                    <th className="py-1.5 px-2">Phase</th>
                    <th className="py-1.5 px-2">Conf</th>
                    <th className="py-1.5 px-2 text-right">Age</th>
                    <th className="py-1.5 px-2 text-right">Cycle</th>
                    <th className="py-1.5 px-2">Structure</th>
                    <th className="py-1.5 px-2">Strategy</th>
                  </>}
                  {activeGroups.has('opportunities') && <>
                    <th className="py-1.5 px-2">0DTE</th>
                    <th className="py-1.5 px-2">LEAP</th>
                    <th className="py-1.5 px-2">Breakout</th>
                    <th className="py-1.5 px-2">Momentum</th>
                  </>}
                  {activeGroups.has('smartmoney') && <>
                    <th className="py-1.5 px-2">SM Score</th>
                    <th className="py-1.5 px-2 text-right">OBs</th>
                    <th className="py-1.5 px-2 text-right">FVGs</th>
                  </>}
                  {activeGroups.has('levels') && <>
                    <th className="py-1.5 px-2">Dir</th>
                    <th className="py-1.5 px-2 text-right">Stop</th>
                    <th className="py-1.5 px-2 text-right">Target</th>
                    <th className="py-1.5 px-2 text-right">S1</th>
                    <th className="py-1.5 px-2 text-right">S2</th>
                    <th className="py-1.5 px-2 text-right">R1</th>
                    <th className="py-1.5 px-2 text-right">R2</th>
                    <th className="py-1.5 px-2">Summary</th>
                  </>}
                  {activeGroups.has('technicals') && <>
                    <th className="py-1.5 px-2">RSI</th>
                    <th className="py-1.5 px-2">MACD</th>
                    <th className="py-1.5 px-2 text-right">%B</th>
                    <th className="py-1.5 px-2 text-right">ATR%</th>
                    <th className="py-1.5 px-2 text-right">Supp</th>
                    <th className="py-1.5 px-2 text-right">Res</th>
                  </>}
                  {activeGroups.has('momentum') && <>
                    <th className="py-1.5 px-2 text-right">vs SMA20</th>
                    <th className="py-1.5 px-2 text-right">vs SMA50</th>
                    <th className="py-1.5 px-2 text-right">vs SMA200</th>
                    <th className="py-1.5 px-2 text-right">Stoch %K</th>
                  </>}
                  {activeGroups.has('vcp') && <>
                    <th className="py-1.5 px-2">Stage</th>
                    <th className="py-1.5 px-2 text-right">Score</th>
                    <th className="py-1.5 px-2 text-right">Pivot</th>
                    <th className="py-1.5 px-2 text-right">Dist%</th>
                    <th className="py-1.5 px-2 text-right">Base</th>
                    <th className="py-1.5 px-2 text-right">Comp</th>
                  </>}
                  {activeGroups.has('fundamentals') && <>
                    <th className="py-1.5 px-2 text-right">P/E</th>
                    <th className="py-1.5 px-2 text-right">Fwd PE</th>
                    <th className="py-1.5 px-2 text-right">PEG</th>
                    <th className="py-1.5 px-2 text-right">Earn Gr</th>
                    <th className="py-1.5 px-2 text-right">Div Yld</th>
                    <th className="py-1.5 px-2 text-right">Beta</th>
                    <th className="py-1.5 px-2 text-right">52w Hi</th>
                    <th className="py-1.5 px-2">Earnings</th>
                  </>}
                  <th className="py-1.5 px-2">Signals</th>
                </tr>
              </thead>
              <tbody>
                {data.map((r: ResearchEntry) => (
                  <ResearchRow
                    key={r.symbol}
                    entry={r}
                    activeGroups={activeGroups}
                    onClick={() => navigate(`/market/${r.symbol}`)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Watchlist Manager
// ---------------------------------------------------------------------------

const ASSET_CLASSES = ['equity', 'equity_index', 'commodity', 'currency', 'tech', 'copper_mining', 'etf', 'crypto']

function WatchlistManager({ onClose }: { onClose: () => void }) {
  const { data: wl, isLoading } = useWatchlist()
  const addMutation = useAddWatchlistTicker()
  const removeMutation = useRemoveWatchlistTicker()
  const [ticker, setTicker] = useState('')
  const [name, setName] = useState('')
  const [assetClass, setAssetClass] = useState('equity')
  const [addError, setAddError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleAdd = () => {
    const t = ticker.trim().toUpperCase()
    if (!t) return
    setAddError(null)
    addMutation.mutate(
      { ticker: t, name: name.trim() || t, asset_class: assetClass },
      {
        onSuccess: () => {
          setTicker('')
          setName('')
          setAssetClass('equity')
          inputRef.current?.focus()
        },
        onError: (err: unknown) => {
          const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to add ticker'
          setAddError(msg)
        },
      },
    )
  }

  const handleRemove = (t: string) => {
    removeMutation.mutate(t)
  }

  const items = wl?.watchlist || []

  return (
    <div className="card">
      <div className="card-body py-2 px-3 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-text-primary">Manage Watchlist</span>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary">
            <X size={14} />
          </button>
        </div>

        {/* Add form */}
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={ticker}
            onChange={e => { setTicker(e.target.value.toUpperCase()); setAddError(null) }}
            onKeyDown={e => e.key === 'Enter' && handleAdd()}
            placeholder="TICKER"
            className="w-20 px-2 py-1 rounded bg-bg-tertiary border border-border-secondary text-xs text-text-primary font-mono uppercase placeholder:text-text-muted focus:outline-none focus:border-accent-blue"
          />
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleAdd()}
            placeholder="Display name (optional)"
            className="flex-1 min-w-0 px-2 py-1 rounded bg-bg-tertiary border border-border-secondary text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-blue"
          />
          <select
            value={assetClass}
            onChange={e => setAssetClass(e.target.value)}
            className="px-2 py-1 rounded bg-bg-tertiary border border-border-secondary text-xs text-text-primary focus:outline-none focus:border-accent-blue"
          >
            {ASSET_CLASSES.map(ac => (
              <option key={ac} value={ac}>{ac}</option>
            ))}
          </select>
          <button
            onClick={handleAdd}
            disabled={!ticker.trim() || addMutation.isPending}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs bg-accent-blue/20 text-accent-blue hover:bg-accent-blue/30 disabled:opacity-50"
          >
            <Plus size={12} />
            Add
          </button>
        </div>
        {addError && <span className="text-2xs text-accent-red">{addError}</span>}

        {/* Current watchlist */}
        {isLoading ? (
          <div className="flex items-center gap-1 py-1">
            <Spinner size="sm" />
            <span className="text-2xs text-text-muted">Loading...</span>
          </div>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {items.map(item => (
              <div
                key={item.ticker}
                className="group flex items-center gap-1 px-2 py-0.5 rounded bg-bg-tertiary border border-border-secondary text-xs"
              >
                <span className="font-mono font-bold text-accent-blue">{item.ticker}</span>
                <span className="text-text-muted text-2xs">{item.name}</span>
                <span className="text-text-muted text-2xs">({item.asset_class})</span>
                <button
                  onClick={() => handleRemove(item.ticker)}
                  disabled={removeMutation.isPending}
                  className="opacity-0 group-hover:opacity-100 text-text-muted hover:text-accent-red transition-opacity ml-0.5"
                  title={`Remove ${item.ticker}`}
                >
                  <X size={10} />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="text-2xs text-text-muted">{items.length} tickers in watchlist</div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Table Row
// ---------------------------------------------------------------------------

function ResearchRow({ entry: r, activeGroups, onClick }: {
  entry: ResearchEntry
  activeGroups: Set<ColGroup>
  onClick: () => void
}) {
  const rc = getRC(r.hmm_regime_id)

  return (
    <tr className="border-b border-border-secondary/50 hover:bg-bg-hover cursor-pointer transition-colors" onClick={onClick}>
      {/* Ticker — always visible, sticky */}
      <td className="py-1.5 px-2 sticky left-0 bg-bg-primary z-10">
        <span className="font-mono font-bold text-accent-blue">{r.symbol}</span>
        <span className="text-text-muted text-2xs ml-1">{r.name}</span>
      </td>

      {/* Core */}
      {activeGroups.has('core') && <>
        <td className="py-1.5 px-2 text-right font-mono text-text-primary">{r.current_price != null ? `$${r.current_price.toFixed(2)}` : '--'}</td>
        <td className="py-1.5 px-2 text-text-secondary text-2xs">{r.sector || '--'}</td>
        <td className="py-1.5 px-2 text-right font-mono text-text-secondary text-2xs">{fmtBigNum(r.market_cap)}</td>
      </>}

      {/* Regime */}
      {activeGroups.has('regime') && <>
        <td className="py-1.5 px-2">
          {r.hmm_regime_id != null ? (
            <>
              <span className={clsx('px-1 py-0.5 rounded text-2xs font-semibold border', rc.bg, rc.color, rc.border)}>R{r.hmm_regime_id}</span>
              <span className={clsx('ml-1 text-2xs', rc.color)}>{rc.label}</span>
            </>
          ) : <span className="text-text-muted text-2xs">--</span>}
        </td>
        <td className="py-1.5 px-2"><ConfBar value={r.hmm_confidence} /></td>
        <td className="py-1.5 px-2 text-center"><TrendArrow direction={r.hmm_trend_direction} /></td>
        <td className="py-1.5 px-2 text-text-secondary text-2xs max-w-[200px] truncate">{r.hmm_strategy_comment || '--'}</td>
      </>}

      {/* Phase (enhanced) */}
      {activeGroups.has('phase') && <>
        <td className="py-1.5 px-2">
          {r.phase_name ? (
            <span className={clsx('px-1 py-0.5 rounded text-2xs font-semibold border',
              r.phase_name === 'markup' ? 'bg-green-900/30 text-green-400 border-green-700' :
              r.phase_name === 'accumulation' ? 'bg-blue-900/30 text-blue-400 border-blue-700' :
              r.phase_name === 'distribution' ? 'bg-amber-900/30 text-amber-400 border-amber-700' :
              r.phase_name === 'markdown' ? 'bg-red-900/30 text-red-400 border-red-700' :
              'bg-bg-tertiary text-text-muted border-border-secondary',
            )}>
              {r.phase_name.charAt(0).toUpperCase() + r.phase_name.slice(1)}
            </span>
          ) : <span className="text-text-muted text-2xs">--</span>}
        </td>
        <td className="py-1.5 px-2"><ConfBar value={r.phase_confidence} /></td>
        <td className="py-1.5 px-2 text-right font-mono text-text-secondary text-2xs">
          {r.phase_age_days != null ? `${r.phase_age_days}d` : '--'}
        </td>
        <td className="py-1.5 px-2 text-right">
          {r.phase_cycle_completion != null ? (
            <div className="flex items-center gap-1">
              <div className="w-8 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                <div className="h-full rounded-full bg-accent-blue" style={{ width: `${Math.round(r.phase_cycle_completion * 100)}%` }} />
              </div>
              <span className="font-mono text-2xs text-text-muted">{Math.round(r.phase_cycle_completion * 100)}%</span>
            </div>
          ) : <span className="text-text-muted text-2xs">--</span>}
        </td>
        <td className="py-1.5 px-2">
          <div className="flex gap-0.5 text-2xs font-mono">
            {r.phase_higher_highs && <span className="text-green-400" title="Higher Highs">HH</span>}
            {r.phase_higher_lows && <span className="text-green-400" title="Higher Lows">HL</span>}
            {r.phase_lower_highs && <span className="text-red-400" title="Lower Highs">LH</span>}
            {r.phase_lower_lows && <span className="text-red-400" title="Lower Lows">LL</span>}
            {!r.phase_higher_highs && !r.phase_higher_lows && !r.phase_lower_highs && !r.phase_lower_lows && <span className="text-text-muted">--</span>}
          </div>
        </td>
        <td className="py-1.5 px-2 text-text-secondary text-2xs max-w-[150px] truncate" title={r.phase_strategy_comment || ''}>
          {r.phase_strategy_comment || '--'}
        </td>
      </>}

      {/* Opportunities */}
      {activeGroups.has('opportunities') && <>
        <td className="py-1.5 px-2">
          <VerdictBadge verdict={r.opp_zero_dte_verdict} strategy={r.opp_zero_dte_strategy} confidence={r.opp_zero_dte_confidence} />
        </td>
        <td className="py-1.5 px-2">
          <VerdictBadge verdict={r.opp_leap_verdict} strategy={r.opp_leap_strategy} confidence={r.opp_leap_confidence} />
        </td>
        <td className="py-1.5 px-2">
          <div className="flex flex-col gap-0.5">
            <VerdictBadge verdict={r.opp_breakout_verdict} strategy={r.opp_breakout_strategy} confidence={r.opp_breakout_confidence} />
            {r.opp_breakout_type && (
              <span className={clsx('text-2xs', r.opp_breakout_type === 'BULLISH' ? 'text-green-400' : 'text-red-400')}>
                {r.opp_breakout_type === 'BULLISH' ? '\u25B2' : '\u25BC'} {r.opp_breakout_pivot != null ? `$${r.opp_breakout_pivot.toFixed(0)}` : ''}
              </span>
            )}
          </div>
        </td>
        <td className="py-1.5 px-2">
          <div className="flex flex-col gap-0.5">
            <VerdictBadge verdict={r.opp_momentum_verdict} strategy={r.opp_momentum_strategy} confidence={r.opp_momentum_confidence} />
            {r.opp_momentum_direction && (
              <span className={clsx('text-2xs', r.opp_momentum_direction === 'BULLISH' ? 'text-green-400' : 'text-red-400')}>
                {r.opp_momentum_direction === 'BULLISH' ? '\u25B2' : '\u25BC'}
              </span>
            )}
          </div>
        </td>
      </>}

      {/* Smart Money */}
      {activeGroups.has('smartmoney') && <>
        <td className="py-1.5 px-2"><SmScoreBar value={r.smart_money_score} /></td>
        <td className="py-1.5 px-2 text-right font-mono text-text-secondary text-2xs">
          {r.active_ob_count != null ? r.active_ob_count : '--'}
        </td>
        <td className="py-1.5 px-2 text-right font-mono text-text-secondary text-2xs">
          {r.unfilled_fvg_count != null ? r.unfilled_fvg_count : '--'}
        </td>
      </>}

      {/* Levels */}
      {activeGroups.has('levels') && <>
        <td className="py-1.5 px-2">
          {r.levels_direction ? (
            <span className={clsx('font-mono font-bold text-2xs', r.levels_direction === 'long' ? 'text-green-400' : 'text-red-400')}>
              {r.levels_direction === 'long' ? '\u25B2 LONG' : '\u25BC SHORT'}
            </span>
          ) : <span className="text-text-muted text-2xs">--</span>}
        </td>
        <td className="py-1.5 px-2 text-right">
          {r.levels_stop_price != null ? (
            <div className="flex flex-col items-end">
              <span className="font-mono text-red-400">${r.levels_stop_price.toFixed(2)}</span>
              {r.levels_stop_distance_pct != null && <span className="text-2xs text-red-400/70">({r.levels_stop_distance_pct.toFixed(1)}%)</span>}
            </div>
          ) : <span className="text-text-muted">--</span>}
        </td>
        <td className="py-1.5 px-2 text-right">
          {r.levels_best_target_price != null ? (
            <div className="flex flex-col items-end">
              <span className="font-mono text-green-400">${r.levels_best_target_price.toFixed(2)}</span>
              {r.levels_best_target_rr != null && <span className="text-2xs text-green-400/70">R:R={r.levels_best_target_rr.toFixed(1)}</span>}
            </div>
          ) : <span className="text-text-muted">--</span>}
        </td>
        <td className="py-1.5 px-2 text-right">
          {r.levels_s1_price != null ? (
            <div className="flex flex-col items-end">
              <span className="font-mono text-text-secondary">${r.levels_s1_price.toFixed(2)}</span>
              {r.levels_s1_sources && <span className="text-2xs text-text-muted truncate max-w-[60px]" title={r.levels_s1_sources}>{r.levels_s1_sources}</span>}
            </div>
          ) : <span className="text-text-muted">--</span>}
        </td>
        <td className="py-1.5 px-2 text-right">
          {r.levels_s2_price != null ? (
            <div className="flex flex-col items-end">
              <span className="font-mono text-text-secondary">${r.levels_s2_price.toFixed(2)}</span>
              {r.levels_s2_sources && <span className="text-2xs text-text-muted truncate max-w-[60px]" title={r.levels_s2_sources}>{r.levels_s2_sources}</span>}
            </div>
          ) : <span className="text-text-muted">--</span>}
        </td>
        <td className="py-1.5 px-2 text-right">
          {r.levels_r1_price != null ? (
            <div className="flex flex-col items-end">
              <span className="font-mono text-text-secondary">${r.levels_r1_price.toFixed(2)}</span>
              {r.levels_r1_sources && <span className="text-2xs text-text-muted truncate max-w-[60px]" title={r.levels_r1_sources}>{r.levels_r1_sources}</span>}
            </div>
          ) : <span className="text-text-muted">--</span>}
        </td>
        <td className="py-1.5 px-2 text-right">
          {r.levels_r2_price != null ? (
            <div className="flex flex-col items-end">
              <span className="font-mono text-text-secondary">${r.levels_r2_price.toFixed(2)}</span>
              {r.levels_r2_sources && <span className="text-2xs text-text-muted truncate max-w-[60px]" title={r.levels_r2_sources}>{r.levels_r2_sources}</span>}
            </div>
          ) : <span className="text-text-muted">--</span>}
        </td>
        <td className="py-1.5 px-2 text-text-secondary text-2xs max-w-[250px] truncate" title={r.levels_summary || ''}>
          {r.levels_summary || '--'}
        </td>
      </>}

      {/* Technicals */}
      {activeGroups.has('technicals') && <>
        <td className="py-1.5 px-2"><RsiCell value={r.rsi_14} ob={r.rsi_overbought} os={r.rsi_oversold} /></td>
        <td className="py-1.5 px-2"><MacdCell hist={r.macd_histogram} bullCross={r.macd_bullish_cross} bearCross={r.macd_bearish_cross} /></td>
        <td className="py-1.5 px-2 text-right">
          {r.bollinger_pct_b != null ? (
            <span className={clsx('font-mono', r.bollinger_pct_b > 1 ? 'text-red-400' : r.bollinger_pct_b < 0 ? 'text-green-400' : 'text-text-primary')}>
              {r.bollinger_pct_b.toFixed(2)}
            </span>
          ) : <span className="text-text-muted">--</span>}
        </td>
        <td className="py-1.5 px-2 text-right font-mono text-text-secondary">{r.atr_pct != null ? `${r.atr_pct.toFixed(1)}%` : '--'}</td>
        <td className="py-1.5 px-2 text-right font-mono text-text-secondary">{r.support != null ? `$${r.support.toFixed(0)}` : '--'}</td>
        <td className="py-1.5 px-2 text-right font-mono text-text-secondary">{r.resistance != null ? `$${r.resistance.toFixed(0)}` : '--'}</td>
      </>}

      {/* Momentum */}
      {activeGroups.has('momentum') && <>
        <td className="py-1.5 px-2 text-right"><PctCell value={r.price_vs_sma_20_pct} /></td>
        <td className="py-1.5 px-2 text-right"><PctCell value={r.price_vs_sma_50_pct} /></td>
        <td className="py-1.5 px-2 text-right"><PctCell value={r.price_vs_sma_200_pct} /></td>
        <td className="py-1.5 px-2 text-right">
          {r.stochastic_k != null ? (
            <span className={clsx('font-mono', r.stochastic_overbought ? 'text-red-400' : r.stochastic_oversold ? 'text-green-400' : 'text-text-primary')}>
              {r.stochastic_k.toFixed(1)}
            </span>
          ) : <span className="text-text-muted">--</span>}
        </td>
      </>}

      {/* VCP */}
      {activeGroups.has('vcp') && <>
        <td className="py-1.5 px-2">
          {r.vcp_stage && r.vcp_stage !== 'none' ? (
            <span className={clsx('px-1 py-0.5 rounded text-2xs font-semibold border',
              r.vcp_stage === 'breakout' ? 'bg-green-900/30 text-green-400 border-green-700' :
              r.vcp_stage === 'ready' ? 'bg-emerald-900/30 text-emerald-400 border-emerald-700' :
              r.vcp_stage === 'maturing' ? 'bg-amber-900/30 text-amber-400 border-amber-700' :
              r.vcp_stage === 'forming' ? 'bg-blue-900/30 text-blue-400 border-blue-700' :
              'bg-bg-tertiary text-text-muted border-border-secondary',
            )}>
              {r.vcp_stage.charAt(0).toUpperCase() + r.vcp_stage.slice(1)}
            </span>
          ) : <span className="text-text-muted text-2xs">--</span>}
        </td>
        <td className="py-1.5 px-2 text-right">
          {r.vcp_score != null ? (
            <span className={clsx('font-mono', r.vcp_score >= 7 ? 'text-green-400 font-bold' : r.vcp_score >= 4 ? 'text-amber-400' : 'text-text-muted')}>
              {r.vcp_score.toFixed(1)}
            </span>
          ) : <span className="text-text-muted">--</span>}
        </td>
        <td className="py-1.5 px-2 text-right font-mono text-text-secondary">
          {r.vcp_pivot_price != null ? `$${r.vcp_pivot_price.toFixed(2)}` : '--'}
        </td>
        <td className="py-1.5 px-2 text-right">
          {r.vcp_pivot_distance_pct != null ? <PctCell value={r.vcp_pivot_distance_pct / 100} /> : <span className="text-text-muted">--</span>}
        </td>
        <td className="py-1.5 px-2 text-right font-mono text-text-secondary">
          {r.vcp_days_in_base != null ? `${r.vcp_days_in_base}d` : '--'}
        </td>
        <td className="py-1.5 px-2 text-right">
          {r.vcp_range_compression != null ? (
            <span className={clsx('font-mono text-2xs', r.vcp_range_compression > 0.5 ? 'text-green-400' : 'text-text-muted')}>
              {(r.vcp_range_compression * 100).toFixed(0)}%
            </span>
          ) : <span className="text-text-muted">--</span>}
        </td>
      </>}

      {/* Fundamentals */}
      {activeGroups.has('fundamentals') && <>
        <td className="py-1.5 px-2 text-right font-mono text-text-secondary">{fmt(r.pe_ratio, 1)}</td>
        <td className="py-1.5 px-2 text-right font-mono text-text-secondary">{fmt(r.forward_pe, 1)}</td>
        <td className="py-1.5 px-2 text-right font-mono text-text-secondary">{fmt(r.peg_ratio, 1)}</td>
        <td className="py-1.5 px-2 text-right">{r.earnings_growth != null ? <PctCell value={r.earnings_growth} /> : <span className="text-text-muted">--</span>}</td>
        <td className="py-1.5 px-2 text-right font-mono text-text-secondary">{r.dividend_yield != null ? fmtPct(r.dividend_yield) : '--'}</td>
        <td className="py-1.5 px-2 text-right font-mono text-text-secondary">{fmt(r.beta, 2)}</td>
        <td className="py-1.5 px-2 text-right">{r.pct_from_52w_high != null ? <PctCell value={r.pct_from_52w_high / 100} /> : <span className="text-text-muted">--</span>}</td>
        <td className="py-1.5 px-2">
          {r.next_earnings_date ? (
            <span className="text-2xs">
              <span className="font-mono text-amber-400">{r.next_earnings_date}</span>
              {r.days_to_earnings != null && <span className="text-text-muted ml-1">({r.days_to_earnings}d)</span>}
            </span>
          ) : <span className="text-text-muted text-2xs">--</span>}
        </td>
      </>}

      {/* Signals */}
      <td className="py-1.5 px-2">
        {r.signals && r.signals.length > 0 ? (
          <div className="flex gap-0.5 flex-wrap max-w-[200px]">
            {r.signals.slice(0, 3).map((sig, i) => (
              <span
                key={i}
                className={clsx(
                  'px-1 py-0.5 rounded text-2xs font-medium',
                  sig.direction === 'bullish' ? 'bg-green-900/30 text-green-400' :
                  sig.direction === 'bearish' ? 'bg-red-900/30 text-red-400' :
                  'bg-bg-tertiary text-text-muted',
                )}
                title={sig.description}
              >
                {sig.name}
              </span>
            ))}
            {r.signals.length > 3 && <span className="text-2xs text-text-muted">+{r.signals.length - 3}</span>}
          </div>
        ) : <span className="text-text-muted text-2xs">--</span>}
      </td>
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Macro Strip
// ---------------------------------------------------------------------------

function MacroStrip({ macro }: { macro: ResearchMacroContext }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="card">
      <div className="card-body py-1.5 px-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Next event */}
            {macro.next_event_name ? (
              <div className="flex items-center gap-2 text-xs">
                <span className="text-text-muted">Next:</span>
                <span className="font-medium text-text-primary">{macro.next_event_name}</span>
                {macro.next_event_impact && <ImpactBadge impact={macro.next_event_impact} />}
                <span className="text-text-muted font-mono">{macro.next_event_date}</span>
                {macro.days_to_next_event != null && (
                  <span className={clsx('font-mono', macro.days_to_next_event <= 3 ? 'text-red-400 font-bold' : 'text-text-muted')}>
                    ({macro.days_to_next_event}d)
                  </span>
                )}
              </div>
            ) : <span className="text-xs text-text-muted">No upcoming macro events</span>}

            {/* FOMC */}
            {macro.next_fomc_date && macro.next_fomc_date !== macro.next_event_date && (
              <div className="text-xs">
                <span className="text-text-muted">FOMC:</span>
                <span className="text-amber-400 font-mono ml-1">{macro.next_fomc_date}</span>
                {macro.days_to_fomc != null && <span className="text-text-muted font-mono ml-1">({macro.days_to_fomc}d)</span>}
              </div>
            )}
          </div>

          {macro.events_30d.length > 0 && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-2xs text-accent-blue hover:underline"
            >
              {expanded ? 'Hide' : `${macro.events_30d.length} events`}
            </button>
          )}
        </div>

        {/* Expanded events list */}
        {expanded && macro.events_30d.length > 0 && (
          <div className="mt-2 border-t border-border-secondary pt-1">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-muted text-2xs uppercase">
                  <th className="py-0.5 px-1 text-left">Date</th>
                  <th className="py-0.5 px-1 text-left">Days</th>
                  <th className="py-0.5 px-1 text-left">Event</th>
                  <th className="py-0.5 px-1 text-center">Impact</th>
                  <th className="py-0.5 px-1 text-left">Options Impact</th>
                </tr>
              </thead>
              <tbody>
                {macro.events_30d.map((evt: MacroEvent, i: number) => {
                  const days = daysFromNow(evt.date)
                  return (
                    <tr key={i} className={clsx('border-b border-border-secondary/30', days <= 3 && 'bg-red-900/10')}>
                      <td className="py-0.5 px-1 font-mono text-text-primary">{evt.date}</td>
                      <td className={clsx('py-0.5 px-1 font-mono', days <= 3 ? 'text-red-400 font-bold' : 'text-text-secondary')}>{days}d</td>
                      <td className="py-0.5 px-1 text-text-primary">{evt.name}</td>
                      <td className="py-0.5 px-1 text-center"><ImpactBadge impact={evt.impact} /></td>
                      <td className="py-0.5 px-1 text-text-secondary truncate max-w-[300px]">{evt.options_impact}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
