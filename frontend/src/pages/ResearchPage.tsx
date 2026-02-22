import { useParams, useNavigate } from 'react-router-dom'
import { clsx } from 'clsx'
import { ArrowLeft } from 'lucide-react'
import { useRegimeResearch, useRegimeChart, useTechnicals, useFundamentals } from '../hooks/useRegime'
import { Spinner } from '../components/common/Spinner'
import type {
  FeatureZScore,
  TransitionRow,
  RegimeDistributionEntry,
  RegimeHistoryDay,
  StateMeansRow,
  TechnicalSignal,
  FundamentalsSnapshot,
} from '../api/types'

// ---------------------------------------------------------------------------
// Regime Color Config
// ---------------------------------------------------------------------------

const RC: Record<number, { color: string; bg: string; border: string; label: string }> = {
  1: { color: 'text-green-400', bg: 'bg-green-900/30', border: 'border-green-700', label: 'Low Vol MR' },
  2: { color: 'text-amber-400', bg: 'bg-amber-900/30', border: 'border-amber-700', label: 'High Vol MR' },
  3: { color: 'text-blue-400', bg: 'bg-blue-900/30', border: 'border-blue-700', label: 'Low Vol Trend' },
  4: { color: 'text-red-400', bg: 'bg-red-900/30', border: 'border-red-700', label: 'High Vol Trend' },
}
function getRC(r: number) { return RC[r] || { color: 'text-text-muted', bg: 'bg-bg-tertiary', border: 'border-border-secondary', label: '?' } }

function TrendBadge({ direction }: { direction: string | null }) {
  if (!direction) return <span className="text-xs text-text-muted">--</span>
  if (direction === 'bullish' || direction === 'up') return <span className="text-xs text-green-400 font-semibold">&#9650; Bullish</span>
  if (direction === 'bearish' || direction === 'down') return <span className="text-xs text-red-400 font-semibold">&#9660; Bearish</span>
  return <span className="text-xs text-text-muted">&#9654; {direction}</span>
}

function TrendArrowSmall({ direction }: { direction: string | null }) {
  if (!direction) return <span className="text-text-muted text-xs">--</span>
  if (direction === 'bullish' || direction === 'up') return <span className="text-green-400 text-xs">&#9650;</span>
  if (direction === 'bearish' || direction === 'down') return <span className="text-red-400 text-xs">&#9660;</span>
  return <span className="text-text-muted text-xs">&#9654;</span>
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 pt-1">
      <h2 className="text-xs font-bold text-text-secondary uppercase tracking-wider">{children}</h2>
      <div className="flex-1 h-px bg-border-secondary" />
    </div>
  )
}

function fmtNum(v: number | null, decimals = 2): string {
  if (v == null) return '--'
  return v.toFixed(decimals)
}

function fmtPct(v: number | null): string {
  if (v == null) return '--'
  return `${(v * 100).toFixed(1)}%`
}

function fmtBigNum(v: number | null): string {
  if (v == null) return '--'
  if (Math.abs(v) >= 1e12) return `${(v / 1e12).toFixed(1)}T`
  if (Math.abs(v) >= 1e9) return `${(v / 1e9).toFixed(1)}B`
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  return v.toLocaleString()
}

// ---------------------------------------------------------------------------
// Research Page — Fundamentals → Technicals → Market Regime
// ---------------------------------------------------------------------------

export function ResearchPage() {
  const { ticker } = useParams<{ ticker: string }>()
  const navigate = useNavigate()

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/')} className="flex items-center gap-1 text-xs text-accent-blue hover:underline">
          <ArrowLeft size={14} /> Back
        </button>
        <span className="text-text-muted">|</span>
        <h1 className="text-base font-bold font-mono text-text-primary">{ticker?.toUpperCase()} Research</h1>
      </div>

      <FundamentalsSection ticker={ticker || ''} />
      <SectionLabel>Technical Analysis</SectionLabel>
      <TechnicalsSection ticker={ticker || ''} />
      <SectionLabel>Market Regime</SectionLabel>
      <RegimeSection ticker={ticker || ''} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Fundamentals Section
// ---------------------------------------------------------------------------

function FundamentalsSection({ ticker }: { ticker: string }) {
  const { data: fund, isLoading, isError, error } = useFundamentals(ticker || null)

  if (isLoading) return <div className="flex items-center gap-2 py-2"><Spinner size="sm" /><span className="text-xs text-text-muted">Loading fundamentals...</span></div>
  if (isError) return <div className="card card-body text-red-400 text-xs py-2">Fundamentals failed: {(error as Error)?.message}</div>
  if (!fund) return <div className="card card-body text-text-muted text-xs py-2">No fundamental data for {ticker}</div>

  return (
    <div className="space-y-2">
      {/* Row 1: Business + Valuation + 52w + Upcoming Events */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        {/* Business Info */}
        <div className="card">
          <div className="card-body py-2 space-y-1">
            <div className="text-lg font-bold text-text-primary">{fund.business.long_name || ticker}</div>
            <div className="text-xs text-text-muted">{fund.business.sector} / {fund.business.industry}</div>
            <div className="flex gap-3 text-xs">
              <span className="text-text-muted">Beta: <span className="font-mono text-text-primary">{fmtNum(fund.business.beta)}</span></span>
              <span className="text-text-muted">MCap: <span className="font-mono text-text-primary">{fmtBigNum(fund.revenue.market_cap)}</span></span>
            </div>
          </div>
        </div>

        {/* Valuation */}
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Valuation</h3></div>
          <div className="card-body py-1.5 space-y-0.5">
            {[
              { label: 'P/E (TTM)', val: fmtNum(fund.valuation.trailing_pe) },
              { label: 'P/E (Fwd)', val: fmtNum(fund.valuation.forward_pe) },
              { label: 'PEG', val: fmtNum(fund.valuation.peg_ratio) },
              { label: 'P/B', val: fmtNum(fund.valuation.price_to_book) },
              { label: 'P/S', val: fmtNum(fund.valuation.price_to_sales) },
            ].map(r => (
              <div key={r.label} className="flex justify-between text-xs">
                <span className="text-text-muted">{r.label}</span>
                <span className="font-mono text-text-primary">{r.val}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 52-Week Range */}
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">52-Week Range</h3></div>
          <div className="card-body py-1.5 space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-text-muted">High</span>
              <span className="font-mono text-text-primary">${fmtNum(fund.fifty_two_week.high)}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-text-muted">Low</span>
              <span className="font-mono text-text-primary">${fmtNum(fund.fifty_two_week.low)}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-text-muted">From High</span>
              <span className={clsx('font-mono', (fund.fifty_two_week.pct_from_high ?? 0) < 0 ? 'text-red-400' : 'text-green-400')}>
                {fmtPct(fund.fifty_two_week.pct_from_high != null ? fund.fifty_two_week.pct_from_high / 100 : null)}
              </span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-text-muted">From Low</span>
              <span className={clsx('font-mono', (fund.fifty_two_week.pct_from_low ?? 0) > 0 ? 'text-green-400' : 'text-red-400')}>
                {fmtPct(fund.fifty_two_week.pct_from_low != null ? fund.fifty_two_week.pct_from_low / 100 : null)}
              </span>
            </div>
          </div>
        </div>

        {/* Upcoming Events */}
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Events</h3></div>
          <div className="card-body py-1.5 space-y-1.5">
            {fund.upcoming_events.next_earnings_date ? (
              <div>
                <div className="text-xs text-text-muted">Next Earnings</div>
                <div className="text-sm font-mono font-bold text-amber-400">{fund.upcoming_events.next_earnings_date}</div>
                {fund.upcoming_events.days_to_earnings != null && (
                  <div className="text-xs text-text-muted">{fund.upcoming_events.days_to_earnings}d away</div>
                )}
              </div>
            ) : <div className="text-xs text-text-muted">No earnings date</div>}
            {fund.dividends.dividend_yield != null && fund.dividends.dividend_yield > 0 && (
              <div className="flex justify-between text-xs">
                <span className="text-text-muted">Div Yield</span>
                <span className="font-mono text-green-400">{fmtPct(fund.dividends.dividend_yield)}</span>
              </div>
            )}
            {fund.upcoming_events.ex_dividend_date && (
              <div className="flex justify-between text-xs">
                <span className="text-text-muted">Ex-Div</span>
                <span className="font-mono text-text-primary">{fund.upcoming_events.ex_dividend_date}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Row 2: Earnings + Margins + Returns + Debt/Cash */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        {/* Earnings */}
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Earnings</h3></div>
          <div className="card-body py-1.5 space-y-0.5">
            <div className="flex justify-between text-xs"><span className="text-text-muted">EPS (TTM)</span><span className="font-mono text-text-primary">{fmtNum(fund.earnings.trailing_eps)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">EPS (Fwd)</span><span className="font-mono text-text-primary">{fmtNum(fund.earnings.forward_eps)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">Growth</span><span className={clsx('font-mono', (fund.earnings.earnings_growth ?? 0) > 0 ? 'text-green-400' : 'text-red-400')}>{fmtPct(fund.earnings.earnings_growth)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">Revenue</span><span className="font-mono text-text-primary">{fmtBigNum(fund.revenue.total_revenue)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">Rev Growth</span><span className={clsx('font-mono', (fund.revenue.revenue_growth ?? 0) > 0 ? 'text-green-400' : 'text-red-400')}>{fmtPct(fund.revenue.revenue_growth)}</span></div>
          </div>
        </div>

        {/* Margins */}
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Margins</h3></div>
          <div className="card-body py-1.5 space-y-0.5">
            {[
              { label: 'Gross', val: fund.margins.gross_margins },
              { label: 'Operating', val: fund.margins.operating_margins },
              { label: 'Profit', val: fund.margins.profit_margins },
              { label: 'EBITDA', val: fund.margins.ebitda_margins },
            ].map(r => (
              <div key={r.label} className="flex justify-between text-xs">
                <span className="text-text-muted">{r.label}</span>
                <span className="font-mono text-text-primary">{fmtPct(r.val)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Returns */}
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Returns</h3></div>
          <div className="card-body py-1.5 space-y-0.5">
            <div className="flex justify-between text-xs"><span className="text-text-muted">ROE</span><span className="font-mono text-text-primary">{fmtPct(fund.returns.return_on_equity)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">ROA</span><span className="font-mono text-text-primary">{fmtPct(fund.returns.return_on_assets)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">FCF</span><span className="font-mono text-text-primary">{fmtBigNum(fund.cash.free_cashflow)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">Op CF</span><span className="font-mono text-text-primary">{fmtBigNum(fund.cash.operating_cashflow)}</span></div>
          </div>
        </div>

        {/* Debt */}
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Balance Sheet</h3></div>
          <div className="card-body py-1.5 space-y-0.5">
            <div className="flex justify-between text-xs"><span className="text-text-muted">Total Cash</span><span className="font-mono text-text-primary">{fmtBigNum(fund.cash.total_cash)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">Total Debt</span><span className="font-mono text-text-primary">{fmtBigNum(fund.debt.total_debt)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">D/E</span><span className="font-mono text-text-primary">{fmtNum(fund.debt.debt_to_equity)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">Current Ratio</span><span className="font-mono text-text-primary">{fmtNum(fund.debt.current_ratio)}</span></div>
          </div>
        </div>
      </div>

      {/* Row 3: Recent Earnings History */}
      {fund.recent_earnings.length > 0 && (
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Recent Earnings ({fund.recent_earnings.length})</h3></div>
          <div className="card-body p-0">
            <table className="w-full text-xs">
              <thead><tr className="text-text-muted border-b border-border-secondary text-2xs uppercase"><th className="py-1 px-2 text-left">Date</th><th className="py-1 px-2 text-right">Estimate</th><th className="py-1 px-2 text-right">Actual</th><th className="py-1 px-2 text-right">Surprise</th></tr></thead>
              <tbody>
                {fund.recent_earnings.map((e, i) => (
                  <tr key={i} className="border-b border-border-secondary/50">
                    <td className="py-0.5 px-2 font-mono text-text-primary">{e.date}</td>
                    <td className="py-0.5 px-2 text-right font-mono text-text-secondary">{e.eps_estimate?.toFixed(2) ?? '--'}</td>
                    <td className="py-0.5 px-2 text-right font-mono text-text-primary">{e.eps_actual?.toFixed(2) ?? '--'}</td>
                    <td className={clsx('py-0.5 px-2 text-right font-mono font-semibold', (e.surprise_pct ?? 0) > 0 ? 'text-green-400' : (e.surprise_pct ?? 0) < 0 ? 'text-red-400' : 'text-text-muted')}>
                      {e.surprise_pct != null ? `${e.surprise_pct > 0 ? '+' : ''}${e.surprise_pct.toFixed(1)}%` : '--'}
                    </td>
                  </tr>
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
// Technicals Section (same as before)
// ---------------------------------------------------------------------------

function TechnicalsSection({ ticker }: { ticker: string }) {
  const { data: tech, isLoading, isError, error } = useTechnicals(ticker || null)

  if (isLoading) return <div className="flex items-center gap-2 py-2"><Spinner size="sm" /><span className="text-xs text-text-muted">Loading technicals...</span></div>
  if (isError) return <div className="card card-body text-red-400 text-xs py-2">Technicals failed: {(error as Error)?.message}</div>
  if (!tech) return <div className="card card-body text-text-muted text-xs py-2">No technical data for {ticker}</div>

  const ma = tech.moving_averages
  const bb = tech.bollinger
  const macd = tech.macd
  const stoch = tech.stochastic
  const sr = tech.support_resistance

  return (
    <div className="space-y-2">
      {/* Row 1: Price + RSI + MACD + Stochastic */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        <div className="card">
          <div className="card-body py-2 space-y-1">
            <div className="text-xs text-text-muted uppercase font-semibold">Price</div>
            <div className="text-lg font-mono font-bold text-text-primary">${tech.current_price.toFixed(2)}</div>
            <div className="flex gap-3 text-xs">
              <span className="text-text-muted">ATR: <span className="text-text-primary font-mono">{tech.atr.toFixed(2)}</span></span>
              <span className="text-text-muted">ATR%: <span className="text-text-primary font-mono">{tech.atr_pct.toFixed(2)}%</span></span>
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-body py-2 space-y-1">
            <div className="text-xs text-text-muted uppercase font-semibold">RSI (14)</div>
            <div className={clsx('text-lg font-mono font-bold', tech.rsi.is_overbought ? 'text-red-400' : tech.rsi.is_oversold ? 'text-green-400' : 'text-text-primary')}>{tech.rsi.value.toFixed(1)}</div>
            <div className="w-full h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
              <div className={clsx('h-full rounded-full', tech.rsi.value > 70 ? 'bg-red-500' : tech.rsi.value < 30 ? 'bg-green-500' : 'bg-accent-blue')} style={{ width: `${tech.rsi.value}%` }} />
            </div>
            <div className="text-xs">{tech.rsi.is_overbought ? <span className="text-red-400 font-semibold">Overbought</span> : tech.rsi.is_oversold ? <span className="text-green-400 font-semibold">Oversold</span> : <span className="text-text-muted">Neutral</span>}</div>
          </div>
        </div>
        <div className="card">
          <div className="card-body py-2 space-y-1">
            <div className="text-xs text-text-muted uppercase font-semibold">MACD</div>
            <div className="flex items-baseline gap-2">
              <span className="text-sm font-mono font-bold text-text-primary">{macd.macd_line.toFixed(3)}</span>
              <span className="text-xs text-text-muted">sig: {macd.signal_line.toFixed(3)}</span>
            </div>
            <div className={clsx('text-xs font-mono font-semibold', macd.histogram > 0 ? 'text-green-400' : 'text-red-400')}>Hist: {macd.histogram > 0 ? '+' : ''}{macd.histogram.toFixed(3)}</div>
            <div className="text-xs">{macd.is_bullish_crossover ? <span className="text-green-400 font-semibold">Bullish Cross</span> : macd.is_bearish_crossover ? <span className="text-red-400 font-semibold">Bearish Cross</span> : <span className="text-text-muted">No crossover</span>}</div>
          </div>
        </div>
        <div className="card">
          <div className="card-body py-2 space-y-1">
            <div className="text-xs text-text-muted uppercase font-semibold">Stochastic</div>
            <div className="flex items-baseline gap-2">
              <span className={clsx('text-sm font-mono font-bold', stoch.is_overbought ? 'text-red-400' : stoch.is_oversold ? 'text-green-400' : 'text-text-primary')}>%K {stoch.k.toFixed(1)}</span>
              <span className="text-xs text-text-muted font-mono">%D {stoch.d.toFixed(1)}</span>
            </div>
            <div className="text-xs">{stoch.is_overbought ? <span className="text-red-400 font-semibold">Overbought</span> : stoch.is_oversold ? <span className="text-green-400 font-semibold">Oversold</span> : <span className="text-text-muted">Neutral</span>}</div>
          </div>
        </div>
      </div>

      {/* Row 2: MAs + Bollinger + Support/Resistance */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-2">
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Moving Averages</h3></div>
          <div className="card-body p-0">
            <table className="w-full text-xs">
              <thead><tr className="text-text-muted border-b border-border-secondary"><th className="py-1 px-2 text-left">MA</th><th className="py-1 px-2 text-right">Value</th><th className="py-1 px-2 text-right">vs Price</th></tr></thead>
              <tbody>
                {[
                  { name: 'EMA 9', val: ma.ema_9, pct: null },
                  { name: 'SMA 20', val: ma.sma_20, pct: ma.price_vs_sma_20_pct },
                  { name: 'EMA 21', val: ma.ema_21, pct: null },
                  { name: 'SMA 50', val: ma.sma_50, pct: ma.price_vs_sma_50_pct },
                  { name: 'SMA 200', val: ma.sma_200, pct: ma.price_vs_sma_200_pct },
                ].map((row) => (
                  <tr key={row.name} className="border-b border-border-secondary/50">
                    <td className="py-0.5 px-2 text-text-primary">{row.name}</td>
                    <td className="py-0.5 px-2 text-right font-mono">${row.val.toFixed(2)}</td>
                    <td className={clsx('py-0.5 px-2 text-right font-mono', row.pct != null ? (row.pct > 0 ? 'text-green-400' : 'text-red-400') : 'text-text-muted')}>{row.pct != null ? `${row.pct > 0 ? '+' : ''}${row.pct.toFixed(1)}%` : '--'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Bollinger Bands</h3></div>
          <div className="card-body py-2 space-y-1">
            {[{ label: 'Upper', val: bb.upper }, { label: 'Middle', val: bb.middle }, { label: 'Lower', val: bb.lower }].map(r => (
              <div key={r.label} className="flex justify-between text-xs"><span className="text-text-muted">{r.label}</span><span className="font-mono text-text-primary">${r.val.toFixed(2)}</span></div>
            ))}
            <div className="flex justify-between text-xs"><span className="text-text-muted">BW</span><span className="font-mono text-text-primary">{bb.bandwidth.toFixed(2)}</span></div>
            <div className="flex justify-between text-xs"><span className="text-text-muted">%B</span><span className={clsx('font-mono font-semibold', bb.percent_b > 1 ? 'text-red-400' : bb.percent_b < 0 ? 'text-green-400' : 'text-text-primary')}>{bb.percent_b.toFixed(3)}</span></div>
            <div className="relative h-2 bg-bg-tertiary rounded-full mt-1">
              <div className="absolute left-0 top-0 h-full w-px bg-text-muted/30" /><div className="absolute top-0 h-full w-px bg-text-muted/30" style={{ left: '50%' }} /><div className="absolute right-0 top-0 h-full w-px bg-text-muted/30" />
              <div className="absolute top-0 w-2 h-2 rounded-full bg-accent-blue border border-white" style={{ left: `${Math.max(0, Math.min(100, bb.percent_b * 100))}%`, transform: 'translateX(-50%)' }} />
            </div>
          </div>
        </div>
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Support / Resistance</h3></div>
          <div className="card-body py-2 space-y-2">
            <div className="flex justify-between items-baseline"><span className="text-xs text-text-muted">Resistance</span><div className="flex items-baseline gap-1"><span className="text-sm font-mono font-bold text-red-400">${sr.resistance?.toFixed(2) ?? '--'}</span>{sr.price_vs_resistance_pct != null && <span className="text-xs font-mono text-text-muted">({sr.price_vs_resistance_pct.toFixed(1)}%)</span>}</div></div>
            <div className="flex justify-between items-baseline"><span className="text-xs text-text-muted">Current</span><span className="text-sm font-mono font-bold text-text-primary">${tech.current_price.toFixed(2)}</span></div>
            <div className="flex justify-between items-baseline"><span className="text-xs text-text-muted">Support</span><div className="flex items-baseline gap-1"><span className="text-sm font-mono font-bold text-green-400">${sr.support?.toFixed(2) ?? '--'}</span>{sr.price_vs_support_pct != null && <span className="text-xs font-mono text-text-muted">({sr.price_vs_support_pct.toFixed(1)}%)</span>}</div></div>
          </div>
        </div>
      </div>

      {/* Signals */}
      {tech.signals && tech.signals.length > 0 && (
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Signals</h3></div>
          <div className="card-body p-0">
            <table className="w-full text-xs">
              <thead><tr className="text-text-muted border-b border-border-secondary"><th className="py-1 px-2 text-left">Signal</th><th className="py-1 px-2 text-center">Direction</th><th className="py-1 px-2 text-center">Strength</th><th className="py-1 px-2 text-left">Description</th></tr></thead>
              <tbody>
                {tech.signals.map((sig: TechnicalSignal, i: number) => (
                  <tr key={i} className="border-b border-border-secondary/50">
                    <td className="py-0.5 px-2 font-medium text-text-primary">{sig.name}</td>
                    <td className="py-0.5 px-2 text-center"><span className={clsx('px-1.5 py-0.5 rounded font-semibold text-xs', sig.direction === 'bullish' ? 'bg-green-900/30 text-green-400' : sig.direction === 'bearish' ? 'bg-red-900/30 text-red-400' : 'bg-bg-tertiary text-text-muted')}>{sig.direction}</span></td>
                    <td className="py-0.5 px-2 text-center"><span className={clsx('font-mono', sig.strength === 'strong' ? 'text-text-primary font-bold' : sig.strength === 'moderate' ? 'text-text-secondary' : 'text-text-muted')}>{sig.strength}</span></td>
                    <td className="py-0.5 px-2 text-text-secondary">{sig.description}</td>
                  </tr>
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
// Regime Section — chart on the side (right column)
// ---------------------------------------------------------------------------

function RegimeSection({ ticker }: { ticker: string }) {
  const { data: research, isLoading, isError, error } = useRegimeResearch(ticker || null)
  const { data: chartData, isLoading: chartLoading } = useRegimeChart(ticker || null)

  if (isLoading) return <div className="flex justify-center py-4"><Spinner size="sm" /></div>
  if (isError || !research) return <div className="text-red-400 text-xs py-2 card card-body">Regime failed: {(error as Error)?.message || 'Unknown error'}</div>

  const rr = research.regime_result
  const rc = getRC(rr.regime)

  return (
    <div className="space-y-2">
      {/* Row 1: Classification + Features LEFT, Chart RIGHT */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-2">
        {/* Left: Classification + Features */}
        <div className="space-y-2">
          <div className={clsx('card border-l-4', rc.border)}>
            <div className="card-body py-2 space-y-1.5">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={clsx('px-2 py-0.5 rounded text-xs font-bold border', rc.bg, rc.color, rc.border)}>R{rr.regime} {rc.label}</span>
                <span className={clsx('font-mono text-xs font-semibold', rr.confidence >= 0.8 ? 'text-green-400' : rr.confidence >= 0.5 ? 'text-amber-400' : 'text-red-400')}>{(rr.confidence * 100).toFixed(0)}%</span>
                <TrendBadge direction={rr.trend_direction} />
              </div>
              {research.strategy_comment && <p className="text-xs text-accent-blue font-medium">{research.strategy_comment}</p>}
              {research.explanation_text && (
                <div className="text-xs text-text-secondary leading-snug max-h-[60px] overflow-auto">
                  {research.explanation_text.split('\n').filter((l: string) => l.trim() && !l.trim().startsWith('---') && !l.trim().match(/Feature\s+Z-Score/)).slice(0, 3).map((l: string, i: number) => <p key={i}>{l}</p>)}
                </div>
              )}
            </div>
          </div>
          <div className="card">
            <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Features (Z-Scores)</h3></div>
            <div className="card-body p-0"><FeatureTable features={research.current_features} /></div>
          </div>
        </div>

        {/* Right: Chart — takes full right column */}
        <div className="card flex items-center justify-center">
          <div className="card-body py-2 flex items-center justify-center w-full">
            {chartLoading ? <Spinner size="sm" /> : chartData?.chart_base64 ? (
              <img src={`data:image/png;base64,${chartData.chart_base64}`} alt={`${ticker} regime`} className="rounded object-contain w-full" style={{ maxHeight: 320 }} />
            ) : <span className="text-xs text-text-muted">No chart available</span>}
          </div>
        </div>
      </div>

      {/* Row 2: Transition + Distribution + History */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-2">
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Transition Matrix</h3></div>
          <div className="card-body p-0"><TransitionTable matrix={research.transition_matrix} currentRegime={rr.regime} /></div>
        </div>
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Distribution</h3></div>
          <div className="card-body py-1"><DistributionBars distribution={research.regime_distribution} /></div>
        </div>
        <div className="card">
          <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">State Means</h3></div>
          <div className="card-body p-0"><StateMeansTable means={research.state_means} /></div>
        </div>
      </div>

      {/* Row 3: History */}
      <div className="card">
        <div className="card-header py-1"><h3 className="text-xs font-semibold text-text-secondary uppercase">Recent History (20d)</h3></div>
        <div className="card-body p-0"><HistoryTable history={research.recent_history} /></div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Regime Sub-Components
// ---------------------------------------------------------------------------

function FeatureTable({ features }: { features: FeatureZScore[] }) {
  if (!features?.length) return <div className="p-2 text-xs text-text-muted">No data</div>
  const maxAbsZ = Math.max(...features.map(f => Math.abs(f.z_score)), 0.01)
  return (
    <table className="w-full text-xs">
      <thead><tr className="text-text-muted border-b border-border-secondary"><th className="py-1 px-2 text-left">Feature</th><th className="py-1 px-2 text-right w-12">Z</th><th className="py-1 px-2 w-16">Bar</th><th className="py-1 px-2">Note</th></tr></thead>
      <tbody>
        {features.map((f) => {
          const absZ = Math.abs(f.z_score)
          const zColor = absZ <= 1 ? 'text-green-400' : absZ <= 2 ? 'text-amber-400' : 'text-red-400'
          const barColor = absZ <= 1 ? 'bg-green-500' : absZ <= 2 ? 'bg-amber-500' : 'bg-red-500'
          const barPct = Math.min((absZ / Math.max(maxAbsZ, 3)) * 100, 100)
          return (
            <tr key={f.feature} className="border-b border-border-secondary/50">
              <td className="py-0.5 px-2 font-mono text-text-primary">{f.feature}</td>
              <td className={clsx('py-0.5 px-2 text-right font-mono font-bold', zColor)}>{f.z_score >= 0 ? '+' : ''}{f.z_score.toFixed(2)}</td>
              <td className="py-0.5 px-2">
                <div className="w-full h-1.5 bg-bg-tertiary rounded-full relative overflow-hidden">
                  {f.z_score < 0 ? <div className={clsx('absolute h-full rounded-full', barColor)} style={{ right: '50%', width: `${barPct / 2}%` }} /> : <div className={clsx('absolute h-full rounded-full', barColor)} style={{ left: '50%', width: `${barPct / 2}%` }} />}
                  <div className="absolute left-1/2 top-0 h-full w-px bg-text-muted/50" />
                </div>
              </td>
              <td className="py-0.5 px-2 text-text-secondary truncate max-w-[120px]">{f.comment}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function TransitionTable({ matrix, currentRegime }: { matrix: TransitionRow[]; currentRegime: number }) {
  if (!matrix?.length) return <div className="p-2 text-xs text-text-muted">No data</div>
  return (
    <table className="w-full text-xs">
      <thead><tr className="text-text-muted border-b border-border-secondary"><th className="py-1 px-1.5 text-left">From</th>{[1,2,3,4].map(r=><th key={r} className="py-1 px-1 text-center"><span className={getRC(r).color}>R{r}</span></th>)}<th className="py-1 px-1 text-center">Sticky</th></tr></thead>
      <tbody>
        {matrix.map((row) => (
          <tr key={row.from_regime} className={clsx('border-b border-border-secondary/50', row.from_regime === currentRegime && 'bg-accent-blue/10')}>
            <td className={clsx('py-0.5 px-1.5 font-mono font-semibold', getRC(row.from_regime).color)}>R{row.from_regime}{row.from_regime === currentRegime && '*'}</td>
            {[1,2,3,4].map(toR => {
              const p = row.to_probabilities[String(toR)] ?? 0
              return <td key={toR} className={clsx('py-0.5 px-1 text-center font-mono', row.from_regime === toR ? 'font-bold text-text-primary' : 'text-text-secondary', p >= 0.7 && 'bg-green-900/20')}>{(p*100).toFixed(0)}%</td>
            })}
            <td className="py-0.5 px-1 text-center text-text-secondary">{row.stability}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function DistributionBars({ distribution }: { distribution: RegimeDistributionEntry[] }) {
  if (!distribution?.length) return <div className="text-xs text-text-muted">No data</div>
  const maxPct = Math.max(...distribution.map(d => d.percentage), 1)
  return (
    <div className="space-y-1">
      {distribution.map((d) => {
        const rc = getRC(d.regime)
        return (
          <div key={d.regime} className="flex items-center gap-1.5">
            <div className={clsx('w-8 text-xs font-mono font-semibold shrink-0', rc.color)}>R{d.regime}</div>
            <div className="flex-1 h-3.5 bg-bg-tertiary rounded overflow-hidden relative">
              <div className={clsx('h-full rounded', rc.bg)} style={{ width: `${(d.percentage / maxPct) * 100}%`, opacity: 0.7 }} />
              <span className="absolute inset-0 flex items-center px-1 text-xs font-mono text-text-primary">{d.percentage.toFixed(0)}% ({d.days}d)</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function HistoryTable({ history }: { history: RegimeHistoryDay[] }) {
  if (!history?.length) return <div className="p-2 text-xs text-text-muted">No data</div>
  return (
    <div className="max-h-[180px] overflow-auto">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-bg-secondary"><tr className="text-text-muted border-b border-border-secondary"><th className="py-1 px-2 text-left">Date</th><th className="py-1 px-2">Regime</th><th className="py-1 px-2 text-right">Conf</th><th className="py-1 px-2 text-center">Trend</th><th className="py-1 px-2">Change</th></tr></thead>
        <tbody>
          {history.map((d) => {
            const rc = getRC(d.regime)
            return (
              <tr key={d.date} className={clsx('border-b border-border-secondary/50', d.changed_from != null && 'bg-amber-900/10')}>
                <td className="py-0.5 px-2 font-mono text-text-primary">{d.date}</td>
                <td className="py-0.5 px-2"><span className={clsx('px-1 py-0.5 rounded font-semibold border', rc.bg, rc.color, rc.border)}>R{d.regime}</span></td>
                <td className="py-0.5 px-2 text-right font-mono text-text-secondary">{(d.confidence*100).toFixed(0)}%</td>
                <td className="py-0.5 px-2 text-center"><TrendArrowSmall direction={d.trend_direction} /></td>
                <td className="py-0.5 px-2">{d.changed_from != null ? <span className="text-amber-400 font-mono font-semibold">R{d.changed_from}&#8594;R{d.regime}</span> : <span className="text-text-muted">--</span>}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function StateMeansTable({ means }: { means: StateMeansRow[] }) {
  if (!means?.length) return <div className="p-2 text-xs text-text-muted">No data</div>
  const featureNames = Array.from(new Set(means.flatMap(m => Object.keys(m.feature_means))))
  return (
    <div className="overflow-auto">
      <table className="w-full text-xs">
        <thead><tr className="text-text-muted border-b border-border-secondary"><th className="py-1 px-2 text-left">R</th><th className="py-1 px-2">Vol</th><th className="py-1 px-2">Trend</th>{featureNames.map(f=><th key={f} className="py-1 px-1.5 text-right font-mono">{f}</th>)}</tr></thead>
        <tbody>
          {means.map(m => {
            const rc = getRC(m.regime)
            return (
              <tr key={m.regime} className="border-b border-border-secondary/50">
                <td className={clsx('py-0.5 px-2 font-mono font-semibold', rc.color)}>R{m.regime}</td>
                <td className="py-0.5 px-2 text-text-secondary">{m.vol_character}</td>
                <td className="py-0.5 px-2 text-text-secondary">{m.trend_character}</td>
                {featureNames.map(f=><td key={f} className="py-0.5 px-1.5 text-right font-mono text-text-secondary">{m.feature_means[f]?.toFixed(3) ?? '--'}</td>)}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
