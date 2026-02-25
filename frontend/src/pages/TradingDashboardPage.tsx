import { useState, useMemo, useCallback, useRef } from 'react'
import { clsx } from 'clsx'
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
// Compact formatters
// ---------------------------------------------------------------------------
const n = (v: number | null | undefined, d = 2) => v == null ? '--' : v.toFixed(d)
const n$ = (v: number | null | undefined) =>
  v == null ? '--' : v < 0
    ? `-$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
    : `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
const pct = (v: number | null | undefined, d = 1) => v == null ? '--' : `${v.toFixed(d)}%`
const g = (v: number | null | undefined, d = 2) => v == null ? '--' : `${v >= 0 ? '+' : ''}${v.toFixed(d)}`
const clr = (v: number | null | undefined) => !v ? 'text-text-muted' : v > 0 ? 'text-accent-green' : 'text-accent-red'

const HC = 'py-[3px] px-1.5 text-[10px] font-semibold text-text-muted whitespace-nowrap'
const DC = 'py-[3px] px-1.5 text-[11px] font-mono whitespace-nowrap'
const ROW = 'border-b border-border-secondary/40 hover:bg-bg-hover/50'

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
function SummaryStrip({ p }: { p: TradingDashboardPortfolio }) {
  return (
    <div className="flex items-center gap-4 flex-wrap px-2 py-1 bg-bg-secondary border-b border-border-secondary">
      <KPI label="Equity" value={n$(p.total_equity)} />
      <KPI label="Cash" value={n$(p.cash_balance)} />
      <KPI label="BP" value={n$(p.buying_power)} />
      <KPI label="Deployed" value={pct(p.capital_deployed_pct)} color={p.capital_deployed_pct > 60 ? 'text-accent-yellow' : undefined} />
      <span className="text-border-secondary">|</span>
      <KPI label="\u0394" value={g(p.net_delta, 1)} color={clr(p.net_delta)} />
      <KPI label="\u0398/d" value={`$${n(p.net_theta, 0)}`} color="text-accent-green" />
      <KPI label="\u0393" value={n(p.net_gamma, 4)} />
      <KPI label="\u03BD" value={g(p.net_vega, 1)} color={clr(-Math.abs(p.net_vega))} />
      <span className="text-border-secondary">|</span>
      <KPI label="VaR" value={n$(p.var_1d_95)} />
      <KPI label="\u0394 util" value={pct(p.delta_utilization_pct)} color={p.delta_utilization_pct > 70 ? 'text-accent-red' : undefined} />
      <span className="text-text-muted text-[10px]">Pos:{p.open_positions} Strat:{p.open_strategies}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Strategies Table (compact)
// ---------------------------------------------------------------------------
function StrategiesTable({ strategies }: { strategies: TradingDashboardStrategy[] }) {
  if (!strategies.length) return <div className="text-[10px] text-text-muted px-2 py-1">No open strategies</div>
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b border-border-secondary bg-bg-secondary">
            <th className={clsx(HC, 'text-left')}>UDL</th>
            <th className={clsx(HC, 'text-left')}>Type</th>
            <th className={clsx(HC, 'text-left')}>Legs</th>
            <th className={clsx(HC, 'text-right')}>DTE</th>
            <th className={clsx(HC, 'text-right')}>Qty</th>
            <th className={clsx(HC, 'text-right')}>Margin</th>
            <th className={clsx(HC, 'text-right')}>MaxRisk</th>
            <th className={clsx(HC, 'text-right')}>{'\u0394'}</th>
            <th className={clsx(HC, 'text-right')}>{'\u0398'}</th>
            <th className={clsx(HC, 'text-right')}>P&L</th>
            <th className={clsx(HC, 'text-right')}>P&L%</th>
          </tr>
        </thead>
        <tbody>
          {strategies.map((s) => (
            <tr key={s.trade_id} className={ROW}>
              <td className={clsx(DC, 'text-left font-semibold text-text-primary')}>{s.underlying}</td>
              <td className={clsx(DC, 'text-left text-text-secondary')}>{s.strategy_type}</td>
              <td className={clsx(DC, 'text-left text-text-secondary text-[10px]')} title={s.legs_summary}>{s.legs_summary}</td>
              <td className={clsx(DC, 'text-right', s.dte != null && s.dte <= 7 ? 'text-accent-red' : '')}>{s.dte ?? '--'}</td>
              <td className={clsx(DC, 'text-right')}>{s.quantity}</td>
              <td className={clsx(DC, 'text-right')}>{n$(s.margin_used)}</td>
              <td className={clsx(DC, 'text-right text-accent-red')}>{n$(s.max_risk)}</td>
              <td className={clsx(DC, 'text-right', clr(s.net_delta))}>{g(s.net_delta, 2)}</td>
              <td className={clsx(DC, 'text-right', clr(s.net_theta))}>{g(s.net_theta, 2)}</td>
              <td className={clsx(DC, 'text-right', clr(s.total_pnl))}>{n$(s.total_pnl)}</td>
              <td className={clsx(DC, 'text-right', clr(s.pnl_pct))}>{pct(s.pnl_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Positions Table (compact)
// ---------------------------------------------------------------------------
function PositionsTable({ positions }: { positions: TradingDashboardPosition[] }) {
  if (!positions.length) return <div className="text-[10px] text-text-muted px-2 py-1">No positions synced</div>
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="border-b border-border-secondary bg-bg-secondary">
            <th className={clsx(HC, 'text-left')}>UDL</th>
            <th className={clsx(HC, 'text-center')}>Tp</th>
            <th className={clsx(HC, 'text-right')}>K</th>
            <th className={clsx(HC, 'text-right')}>DTE</th>
            <th className={clsx(HC, 'text-right')}>Qty</th>
            <th className={clsx(HC, 'text-right')}>Entry</th>
            <th className={clsx(HC, 'text-right')}>Mark</th>
            <th className={clsx(HC, 'text-right')}>{'\u0394'}</th>
            <th className={clsx(HC, 'text-right')}>{'\u0398'}</th>
            <th className={clsx(HC, 'text-right')}>P&L</th>
            <th className={clsx(HC, 'text-right')}>%</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => (
            <tr key={p.id} className={ROW}>
              <td className={clsx(DC, 'text-left font-semibold text-text-primary')}>{p.underlying || p.symbol}</td>
              <td className={clsx(DC, 'text-center')}>
                <span className={clsx('text-[9px] px-0.5 rounded',
                  p.option_type === 'put' ? 'bg-accent-red/20 text-accent-red'
                  : p.option_type === 'call' ? 'bg-accent-green/20 text-accent-green'
                  : 'bg-accent-blue/20 text-accent-blue'
                )}>
                  {p.option_type?.charAt(0).toUpperCase() || 'E'}
                </span>
              </td>
              <td className={clsx(DC, 'text-right')}>{p.strike ? n(p.strike, 1) : '--'}</td>
              <td className={clsx(DC, 'text-right', p.dte != null && p.dte <= 7 ? 'text-accent-red font-semibold' : '')}>{p.dte ?? '--'}</td>
              <td className={clsx(DC, 'text-right', p.quantity < 0 ? 'text-accent-red' : 'text-accent-green')}>{p.quantity}</td>
              <td className={clsx(DC, 'text-right text-text-secondary')}>{n(p.entry_price)}</td>
              <td className={clsx(DC, 'text-right')}>{n(p.current_price)}</td>
              <td className={clsx(DC, 'text-right', clr(p.delta))}>{g(p.delta)}</td>
              <td className={clsx(DC, 'text-right', clr(p.theta))}>{g(p.theta)}</td>
              <td className={clsx(DC, 'text-right font-semibold', clr(p.total_pnl))}>{n(p.total_pnl)}</td>
              <td className={clsx(DC, 'text-right', clr(p.pnl_pct))}>{pct(p.pnl_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Risk Factors (compact)
// ---------------------------------------------------------------------------
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
            <tr key={f.underlying} className={ROW}>
              <td className={clsx(DC, 'text-left font-semibold text-text-primary')}>{f.underlying}</td>
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
// Trades Frame (top pane)
// ---------------------------------------------------------------------------
function TradesFrame() {
  const { data: portfolios, isLoading: loadingPf } = usePortfolios()
  const [selectedPortfolio, setSelectedPortfolio] = useState<string | null>(null)

  const realPortfolios = useMemo(
    () => portfolios?.filter((p) => p.portfolio_type === 'real') ?? [],
    [portfolios],
  )

  // Auto-select first real portfolio
  const activePf = selectedPortfolio || realPortfolios[0]?.name || ''
  const { data, isLoading, isError, error } = useTradingDashboard(activePf)

  return (
    <div className="h-full overflow-y-auto">
      {/* Portfolio tabs */}
      <div className="flex items-center gap-1.5 px-2 py-1 bg-bg-secondary border-b border-border-secondary flex-wrap">
        {loadingPf ? (
          <span className="text-[10px] text-text-muted">Loading portfolios...</span>
        ) : (
          realPortfolios.map((p) => (
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
          ))
        )}
      </div>

      {/* Content */}
      {isLoading && (
        <div className="flex items-center justify-center py-4">
          <Spinner size="sm" />
          <span className="text-[10px] text-text-muted ml-2">Loading trades...</span>
        </div>
      )}

      {isError && (
        <div className="flex items-center gap-2 px-2 py-1.5 border-b border-border-secondary bg-bg-secondary">
          <span className="text-[10px] text-text-muted">No live data</span>
          <span className="text-2xs text-text-muted/60">({(error as Error)?.message?.includes('timeout') ? 'backend timeout' : 'backend offline'})</span>
        </div>
      )}

      {data && (data as any).status === 'waiting' && (
        <div className="flex items-center gap-2 px-2 py-1.5 border-b border-border-secondary bg-bg-secondary">
          <Spinner size="sm" />
          <span className="text-[10px] text-text-muted">Engine booting — containers populating...</span>
        </div>
      )}

      {data && !(data as any).status && (
        <div>
          {/* Summary strip */}
          <SummaryStrip p={data.portfolio} />

          {/* Strategies + Risk side by side */}
          <div className="grid grid-cols-[3fr_2fr] border-b border-border-secondary">
            <div className="border-r border-border-secondary">
              <div className="px-1.5 py-[2px] text-[9px] font-bold uppercase tracking-wider text-text-muted bg-bg-tertiary border-b border-border-secondary">
                Strategies ({data.strategies.length})
              </div>
              <StrategiesTable strategies={data.strategies} />
            </div>
            <div>
              <div className="px-1.5 py-[2px] text-[9px] font-bold uppercase tracking-wider text-text-muted bg-bg-tertiary border-b border-border-secondary">
                Risk Factors
              </div>
              <RiskFactorsTable factors={data.risk_factors} />
            </div>
          </div>

          {/* Positions */}
          <div>
            <div className="px-1.5 py-[2px] text-[9px] font-bold uppercase tracking-wider text-text-muted bg-bg-tertiary border-b border-border-secondary">
              Positions ({data.positions.length})
            </div>
            <PositionsTable positions={data.positions} />
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
// Main Page — split layout: trades (top) + terminal (bottom)
// ---------------------------------------------------------------------------
export function TradingDashboardPage() {
  const { topPct, onMouseDown, containerRef } = useSplitPane(50)

  return (
    <div ref={containerRef} className="flex flex-col h-full overflow-hidden -m-3">
      {/* Top: Trades */}
      <div className="overflow-hidden" style={{ height: `${topPct}%` }}>
        <TradesFrame />
      </div>

      {/* Draggable divider */}
      <div
        className="h-1 bg-border-primary hover:bg-accent-blue cursor-row-resize flex-shrink-0"
        onMouseDown={onMouseDown}
      />

      {/* Bottom: Terminal */}
      <div className="overflow-hidden flex-1" style={{ height: `${100 - topPct}%` }}>
        <TerminalPanel />
      </div>
    </div>
  )
}
