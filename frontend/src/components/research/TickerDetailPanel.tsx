import { clsx } from 'clsx'
import { X } from 'lucide-react'
import type { ResearchEntry } from '../../api/types'

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
// Helpers
// ---------------------------------------------------------------------------
function fmt(v: number | null | undefined, d = 2): string { return v == null ? '--' : v.toFixed(d) }
function fmtPct(v: number | null | undefined): string { return v == null ? '--' : `${(v * 100).toFixed(1)}%` }
function fmtBigNum(v: number | null | undefined): string {
  if (v == null) return '--'
  if (Math.abs(v) >= 1e12) return `${(v / 1e12).toFixed(1)}T`
  if (Math.abs(v) >= 1e9) return `${(v / 1e9).toFixed(1)}B`
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  return v.toLocaleString()
}

const VERDICT_STYLE: Record<string, { bg: string; text: string; border: string }> = {
  go: { bg: 'bg-green-900/30', text: 'text-green-400', border: 'border-green-700' },
  caution: { bg: 'bg-amber-900/30', text: 'text-amber-400', border: 'border-amber-700' },
  no_go: { bg: 'bg-red-900/30', text: 'text-red-400', border: 'border-red-700' },
}

function VBadge({ verdict, confidence }: { verdict: string | null; confidence: number | null }) {
  if (!verdict) return <span className="text-text-muted text-2xs">--</span>
  const v = verdict.toLowerCase()
  const s = VERDICT_STYLE[v] || VERDICT_STYLE.no_go
  return (
    <span className={clsx('px-1.5 py-0.5 rounded text-2xs font-semibold border uppercase inline-flex items-center gap-1', s.bg, s.text, s.border)}>
      {v === 'no_go' ? 'NO GO' : v}
      {confidence != null && <span className="opacity-70">{Math.round(confidence * 100)}%</span>}
    </span>
  )
}

function KV({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex items-center justify-between py-0.5">
      <span className="text-2xs text-text-muted">{label}</span>
      <span className={clsx('text-xs font-mono', color || 'text-text-primary')}>{value}</span>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="border-t border-border-secondary/50 pt-1.5 mt-1.5">
      <div className="text-2xs font-bold uppercase tracking-wider text-text-muted mb-1">{title}</div>
      {children}
    </div>
  )
}

function LevelRow({ label, price, sources, strength }: { label: string; price: number | null; sources: string | null; strength: number | null }) {
  if (price == null) return null
  return (
    <div className="flex items-center justify-between py-0.5">
      <div className="flex items-center gap-1.5">
        <span className="text-2xs text-text-muted w-6">{label}</span>
        {strength != null && (
          <div className="w-6 h-1 bg-bg-tertiary rounded-full overflow-hidden">
            <div className="h-full rounded-full bg-accent-blue" style={{ width: `${Math.min(strength * 100, 100)}%` }} />
          </div>
        )}
      </div>
      <div className="text-right">
        <span className="text-xs font-mono text-text-primary">${price.toFixed(2)}</span>
        {sources && <span className="text-2xs text-text-muted ml-1">{sources}</span>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------
export function TickerDetailPanel({ entry: r, onClose }: { entry: ResearchEntry; onClose: () => void }) {
  const rc = getRC(r.hmm_regime_id)

  return (
    <div className="w-[340px] flex-shrink-0 border-r border-border-primary bg-bg-secondary overflow-y-auto h-full">
      <div className="px-3 py-2 space-y-1">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold font-mono text-accent-blue">{r.symbol}</span>
            <span className="text-xs text-text-secondary">{r.name || r.long_name}</span>
          </div>
          <button onClick={onClose} className="text-text-muted hover:text-text-primary p-0.5">
            <X size={14} />
          </button>
        </div>

        {/* Price */}
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold font-mono text-text-primary">
            {r.current_price != null ? `$${r.current_price.toFixed(2)}` : '--'}
          </span>
          {r.sector && <span className="text-2xs text-text-muted bg-bg-tertiary px-1.5 py-0.5 rounded">{r.sector}</span>}
          {r.market_cap != null && <span className="text-2xs text-text-muted">{fmtBigNum(r.market_cap)}</span>}
        </div>

        {/* Regime */}
        {r.hmm_regime_id != null && (
          <Section title="Regime">
            <div className="flex items-center gap-2 mb-1">
              <span className={clsx('px-1.5 py-0.5 rounded text-xs font-bold border', rc.bg, rc.color, rc.border)}>
                R{r.hmm_regime_id} {rc.label}
              </span>
              {r.hmm_confidence != null && (
                <span className="text-2xs text-text-muted">{Math.round(r.hmm_confidence * 100)}% conf</span>
              )}
            </div>
            {r.hmm_trend_direction && (
              <KV label="Trend" value={r.hmm_trend_direction}
                color={r.hmm_trend_direction === 'bullish' || r.hmm_trend_direction === 'up' ? 'text-green-400' :
                       r.hmm_trend_direction === 'bearish' || r.hmm_trend_direction === 'down' ? 'text-red-400' : undefined} />
            )}
            {r.hmm_strategy_comment && (
              <div className="text-2xs text-text-secondary mt-0.5">{r.hmm_strategy_comment}</div>
            )}
          </Section>
        )}

        {/* Phase */}
        {r.phase_name && (
          <Section title="Phase (Wyckoff)">
            <div className="flex items-center gap-2 mb-1">
              <span className={clsx('px-1.5 py-0.5 rounded text-xs font-semibold border',
                r.phase_name === 'markup' ? 'bg-green-900/30 text-green-400 border-green-700' :
                r.phase_name === 'accumulation' ? 'bg-blue-900/30 text-blue-400 border-blue-700' :
                r.phase_name === 'distribution' ? 'bg-amber-900/30 text-amber-400 border-amber-700' :
                r.phase_name === 'markdown' ? 'bg-red-900/30 text-red-400 border-red-700' :
                'bg-bg-tertiary text-text-muted border-border-secondary',
              )}>
                {r.phase_name.charAt(0).toUpperCase() + r.phase_name.slice(1)}
              </span>
              {r.phase_confidence != null && <span className="text-2xs text-text-muted">{Math.round(r.phase_confidence * 100)}%</span>}
              {r.phase_age_days != null && <span className="text-2xs text-text-muted">{r.phase_age_days}d old</span>}
            </div>
            {r.phase_cycle_completion != null && (
              <div className="flex items-center gap-2">
                <span className="text-2xs text-text-muted">Cycle</span>
                <div className="flex-1 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                  <div className="h-full rounded-full bg-accent-blue" style={{ width: `${Math.round(r.phase_cycle_completion * 100)}%` }} />
                </div>
                <span className="text-2xs font-mono text-text-secondary">{Math.round(r.phase_cycle_completion * 100)}%</span>
              </div>
            )}
            <div className="flex gap-1 mt-1">
              {r.phase_higher_highs && <span className="text-2xs font-mono text-green-400 bg-green-900/20 px-1 rounded">HH</span>}
              {r.phase_higher_lows && <span className="text-2xs font-mono text-green-400 bg-green-900/20 px-1 rounded">HL</span>}
              {r.phase_lower_highs && <span className="text-2xs font-mono text-red-400 bg-red-900/20 px-1 rounded">LH</span>}
              {r.phase_lower_lows && <span className="text-2xs font-mono text-red-400 bg-red-900/20 px-1 rounded">LL</span>}
            </div>
            {r.phase_strategy_comment && <div className="text-2xs text-text-secondary mt-0.5">{r.phase_strategy_comment}</div>}
          </Section>
        )}

        {/* Technicals */}
        <Section title="Technicals">
          <KV label="RSI(14)" value={fmt(r.rsi_14, 1)}
            color={r.rsi_overbought ? 'text-red-400' : r.rsi_oversold ? 'text-green-400' : undefined} />
          <KV label="ATR%" value={r.atr_pct != null ? `${r.atr_pct.toFixed(1)}%` : '--'} />
          <KV label="MACD Hist" value={fmt(r.macd_histogram, 3)}
            color={r.macd_histogram != null ? (r.macd_histogram > 0 ? 'text-green-400' : 'text-red-400') : undefined} />
          {(r.macd_bullish_cross || r.macd_bearish_cross) && (
            <div className="flex gap-1 mt-0.5">
              {r.macd_bullish_cross && <span className="text-2xs font-bold text-green-400 bg-green-900/20 px-1 rounded">Bull Cross</span>}
              {r.macd_bearish_cross && <span className="text-2xs font-bold text-red-400 bg-red-900/20 px-1 rounded">Bear Cross</span>}
            </div>
          )}
          <KV label="Boll %B" value={fmt(r.bollinger_pct_b, 2)}
            color={r.bollinger_pct_b != null ? (r.bollinger_pct_b > 1 ? 'text-red-400' : r.bollinger_pct_b < 0 ? 'text-green-400' : undefined) : undefined} />
          <KV label="Stoch %K" value={fmt(r.stochastic_k, 1)}
            color={r.stochastic_overbought ? 'text-red-400' : r.stochastic_oversold ? 'text-green-400' : undefined} />
        </Section>

        {/* Moving Averages */}
        <Section title="Moving Averages">
          <KV label="SMA 20" value={r.sma_20 != null ? `$${r.sma_20.toFixed(2)}` : '--'}
            color={r.current_price != null && r.sma_20 != null ? (r.current_price > r.sma_20 ? 'text-green-400' : 'text-red-400') : undefined} />
          <KV label="SMA 50" value={r.sma_50 != null ? `$${r.sma_50.toFixed(2)}` : '--'}
            color={r.current_price != null && r.sma_50 != null ? (r.current_price > r.sma_50 ? 'text-green-400' : 'text-red-400') : undefined} />
          <KV label="SMA 200" value={r.sma_200 != null ? `$${r.sma_200.toFixed(2)}` : '--'}
            color={r.current_price != null && r.sma_200 != null ? (r.current_price > r.sma_200 ? 'text-green-400' : 'text-red-400') : undefined} />
          {r.price_vs_sma_20_pct != null && <KV label="vs SMA20" value={`${r.price_vs_sma_20_pct > 0 ? '+' : ''}${(r.price_vs_sma_20_pct > 1 ? r.price_vs_sma_20_pct : r.price_vs_sma_20_pct * 100).toFixed(1)}%`}
            color={r.price_vs_sma_20_pct > 0 ? 'text-green-400' : 'text-red-400'} />}
          {r.price_vs_sma_200_pct != null && <KV label="vs SMA200" value={`${r.price_vs_sma_200_pct > 0 ? '+' : ''}${(r.price_vs_sma_200_pct > 1 ? r.price_vs_sma_200_pct : r.price_vs_sma_200_pct * 100).toFixed(1)}%`}
            color={r.price_vs_sma_200_pct > 0 ? 'text-green-400' : 'text-red-400'} />}
        </Section>

        {/* Levels */}
        {(r.levels_direction || r.levels_s1_price || r.levels_r1_price) && (
          <Section title="Levels">
            {r.levels_direction && (
              <div className="flex items-center gap-2 mb-1">
                <span className={clsx('text-xs font-bold font-mono',
                  r.levels_direction === 'long' ? 'text-green-400' : 'text-red-400'
                )}>
                  {r.levels_direction === 'long' ? '\u25B2 LONG' : '\u25BC SHORT'}
                </span>
              </div>
            )}
            {r.levels_stop_price != null && (
              <KV label="Stop" value={`$${r.levels_stop_price.toFixed(2)}${r.levels_stop_distance_pct != null ? ` (${r.levels_stop_distance_pct.toFixed(1)}%)` : ''}`} color="text-red-400" />
            )}
            {r.levels_best_target_price != null && (
              <KV label="Target" value={`$${r.levels_best_target_price.toFixed(2)}${r.levels_best_target_rr != null ? ` R:R=${r.levels_best_target_rr.toFixed(1)}` : ''}`} color="text-green-400" />
            )}
            <div className="mt-1">
              <LevelRow label="S1" price={r.levels_s1_price} sources={r.levels_s1_sources} strength={r.levels_s1_strength} />
              <LevelRow label="S2" price={r.levels_s2_price} sources={r.levels_s2_sources} strength={r.levels_s2_strength} />
              <LevelRow label="S3" price={r.levels_s3_price} sources={r.levels_s3_sources} strength={r.levels_s3_strength} />
              <LevelRow label="R1" price={r.levels_r1_price} sources={r.levels_r1_sources} strength={r.levels_r1_strength} />
              <LevelRow label="R2" price={r.levels_r2_price} sources={r.levels_r2_sources} strength={r.levels_r2_strength} />
              <LevelRow label="R3" price={r.levels_r3_price} sources={r.levels_r3_sources} strength={r.levels_r3_strength} />
            </div>
            {r.levels_summary && <div className="text-2xs text-text-secondary mt-1">{r.levels_summary}</div>}
          </Section>
        )}

        {/* Opportunities */}
        {(r.opp_zero_dte_verdict || r.opp_leap_verdict || r.opp_breakout_verdict || r.opp_momentum_verdict) && (
          <Section title="Opportunities">
            {r.opp_zero_dte_verdict && (
              <div className="flex items-center justify-between py-0.5">
                <span className="text-2xs text-text-muted">0DTE</span>
                <div className="flex items-center gap-1">
                  <VBadge verdict={r.opp_zero_dte_verdict} confidence={r.opp_zero_dte_confidence} />
                </div>
              </div>
            )}
            {r.opp_zero_dte_strategy && <div className="text-2xs text-text-secondary ml-8 -mt-0.5">{r.opp_zero_dte_strategy}</div>}

            {r.opp_leap_verdict && (
              <div className="flex items-center justify-between py-0.5">
                <span className="text-2xs text-text-muted">LEAP</span>
                <VBadge verdict={r.opp_leap_verdict} confidence={r.opp_leap_confidence} />
              </div>
            )}
            {r.opp_leap_strategy && <div className="text-2xs text-text-secondary ml-8 -mt-0.5">{r.opp_leap_strategy}</div>}

            {r.opp_breakout_verdict && (
              <div className="flex items-center justify-between py-0.5">
                <span className="text-2xs text-text-muted">Breakout</span>
                <div className="flex items-center gap-1">
                  <VBadge verdict={r.opp_breakout_verdict} confidence={r.opp_breakout_confidence} />
                  {r.opp_breakout_type && (
                    <span className={clsx('text-2xs', r.opp_breakout_type === 'BULLISH' ? 'text-green-400' : 'text-red-400')}>
                      {r.opp_breakout_type === 'BULLISH' ? '\u25B2' : '\u25BC'}
                    </span>
                  )}
                </div>
              </div>
            )}
            {r.opp_breakout_strategy && <div className="text-2xs text-text-secondary ml-8 -mt-0.5">{r.opp_breakout_strategy}</div>}

            {r.opp_momentum_verdict && (
              <div className="flex items-center justify-between py-0.5">
                <span className="text-2xs text-text-muted">Momentum</span>
                <div className="flex items-center gap-1">
                  <VBadge verdict={r.opp_momentum_verdict} confidence={r.opp_momentum_confidence} />
                  {r.opp_momentum_direction && (
                    <span className={clsx('text-2xs', r.opp_momentum_direction === 'BULLISH' ? 'text-green-400' : 'text-red-400')}>
                      {r.opp_momentum_direction === 'BULLISH' ? '\u25B2' : '\u25BC'}
                    </span>
                  )}
                </div>
              </div>
            )}
            {r.opp_momentum_strategy && <div className="text-2xs text-text-secondary ml-8 -mt-0.5">{r.opp_momentum_strategy}</div>}
          </Section>
        )}

        {/* Smart Money */}
        {r.smart_money_score != null && (
          <Section title="Smart Money">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-2xs text-text-muted">Score</span>
              <div className="flex-1 h-1.5 bg-bg-tertiary rounded-full overflow-hidden">
                <div className={clsx('h-full rounded-full',
                  r.smart_money_score >= 0.6 ? 'bg-green-500' : r.smart_money_score >= 0.3 ? 'bg-amber-500' : 'bg-red-500'
                )} style={{ width: `${Math.round(r.smart_money_score * 100)}%` }} />
              </div>
              <span className="text-xs font-mono text-text-secondary">{Math.round(r.smart_money_score * 100)}%</span>
            </div>
            {r.active_ob_count != null && <KV label="Order Blocks" value={String(r.active_ob_count)} />}
            {r.unfilled_fvg_count != null && <KV label="Fair Value Gaps" value={String(r.unfilled_fvg_count)} />}
            {r.smart_money_description && <div className="text-2xs text-text-secondary mt-0.5">{r.smart_money_description}</div>}
          </Section>
        )}

        {/* VCP */}
        {r.vcp_stage && r.vcp_stage !== 'none' && (
          <Section title="VCP Pattern">
            <div className="flex items-center gap-2 mb-1">
              <span className={clsx('px-1.5 py-0.5 rounded text-xs font-semibold border',
                r.vcp_stage === 'breakout' ? 'bg-green-900/30 text-green-400 border-green-700' :
                r.vcp_stage === 'ready' ? 'bg-emerald-900/30 text-emerald-400 border-emerald-700' :
                r.vcp_stage === 'maturing' ? 'bg-amber-900/30 text-amber-400 border-amber-700' :
                'bg-blue-900/30 text-blue-400 border-blue-700',
              )}>
                {r.vcp_stage.charAt(0).toUpperCase() + r.vcp_stage.slice(1)}
              </span>
              {r.vcp_score != null && <span className="text-xs font-mono text-text-secondary">Score: {r.vcp_score.toFixed(1)}</span>}
            </div>
            {r.vcp_pivot_price != null && <KV label="Pivot" value={`$${r.vcp_pivot_price.toFixed(2)}`} />}
            {r.vcp_pivot_distance_pct != null && <KV label="Distance" value={`${r.vcp_pivot_distance_pct.toFixed(1)}%`} />}
            {r.vcp_days_in_base != null && <KV label="Base" value={`${r.vcp_days_in_base}d`} />}
            {r.vcp_range_compression != null && <KV label="Compression" value={`${(r.vcp_range_compression * 100).toFixed(0)}%`} />}
          </Section>
        )}

        {/* Fundamentals */}
        {(r.pe_ratio != null || r.market_cap != null) && (
          <Section title="Fundamentals">
            <KV label="P/E" value={fmt(r.pe_ratio, 1)} />
            <KV label="Fwd P/E" value={fmt(r.forward_pe, 1)} />
            <KV label="PEG" value={fmt(r.peg_ratio, 1)} />
            {r.earnings_growth != null && <KV label="Earn Growth" value={`${(r.earnings_growth * 100).toFixed(1)}%`}
              color={r.earnings_growth > 0 ? 'text-green-400' : 'text-red-400'} />}
            {r.dividend_yield != null && <KV label="Div Yield" value={fmtPct(r.dividend_yield)} />}
            {r.beta != null && <KV label="Beta" value={fmt(r.beta, 2)} />}
            {r.pct_from_52w_high != null && <KV label="52w High" value={`${r.pct_from_52w_high.toFixed(1)}%`}
              color={r.pct_from_52w_high > -5 ? 'text-green-400' : r.pct_from_52w_high < -20 ? 'text-red-400' : 'text-amber-400'} />}
            {r.next_earnings_date && (
              <KV label="Earnings" value={`${r.next_earnings_date}${r.days_to_earnings != null ? ` (${r.days_to_earnings}d)` : ''}`} color="text-amber-400" />
            )}
          </Section>
        )}

        {/* Signals */}
        {r.signals && r.signals.length > 0 && (
          <Section title="Signals">
            <div className="flex flex-wrap gap-1">
              {r.signals.map((sig, i) => (
                <div key={i} className={clsx('px-1.5 py-0.5 rounded text-2xs border',
                  sig.direction === 'bullish' ? 'bg-green-900/20 text-green-400 border-green-800' :
                  sig.direction === 'bearish' ? 'bg-red-900/20 text-red-400 border-red-800' :
                  'bg-bg-tertiary text-text-muted border-border-secondary',
                )}>
                  <span className="font-semibold">{sig.name}</span>
                  <span className="opacity-70 ml-1">{sig.strength}</span>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Triggered templates */}
        {r.triggered_templates && r.triggered_templates.length > 0 && (
          <Section title="Triggered Templates">
            <div className="flex flex-wrap gap-1">
              {r.triggered_templates.map((t, i) => (
                <span key={i} className="px-1.5 py-0.5 rounded text-2xs bg-accent-blue/20 text-accent-blue border border-accent-blue/30">
                  {t}
                </span>
              ))}
            </div>
          </Section>
        )}

        {/* Timestamp */}
        {r.timestamp && (
          <div className="text-2xs text-text-muted mt-2 border-t border-border-secondary/50 pt-1">
            Updated: {r.timestamp}
          </div>
        )}
      </div>
    </div>
  )
}
