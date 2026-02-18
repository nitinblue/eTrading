import { useState, useEffect } from 'react'
import { clsx } from 'clsx'
import { Activity, Zap, Clock, Calendar, PlayCircle, BookOpen } from 'lucide-react'
import { useAdminWorkflow, useUpdateWorkflow, useAdminStrategies, useUpdateStrategy } from '../../hooks/useAdminApi'
import { FormSection } from '../../components/common/FormSection'
import { SaveBar } from '../../components/common/SaveBar'
import { Spinner } from '../../components/common/Spinner'
import { showToast } from '../../components/common/Toast'
import type { WorkflowRulesResponse, StrategyRule } from '../../api/types'

export function WorkflowSettingsPage() {
  const { data: wfData, isLoading: wfLoading } = useAdminWorkflow()
  const { data: stratData, isLoading: stratLoading } = useAdminStrategies()
  const updateWf = useUpdateWorkflow()
  const updateStrat = useUpdateStrategy()

  const [wfDraft, setWfDraft] = useState<WorkflowRulesResponse | null>(null)
  const [stratDraft, setStratDraft] = useState<Record<string, StrategyRule> | null>(null)
  const [wfDirty, setWfDirty] = useState(false)
  const [stratDirty, setStratDirty] = useState(false)
  const [expandedStrat, setExpandedStrat] = useState<string | null>(null)
  const [newFomc, setNewFomc] = useState('')

  useEffect(() => {
    if (wfData) { setWfDraft(structuredClone(wfData)); setWfDirty(false) }
  }, [wfData])

  useEffect(() => {
    if (stratData) { setStratDraft(structuredClone(stratData)); setStratDirty(false) }
  }, [stratData])

  function setWf(path: string, value: unknown) {
    setWfDraft((prev) => {
      if (!prev) return prev
      const next = structuredClone(prev)
      const keys = path.split('.')
      let obj: any = next
      for (let i = 0; i < keys.length - 1; i++) obj = obj[keys[i]]
      obj[keys[keys.length - 1]] = value
      return next
    })
    setWfDirty(true)
  }

  function setStrat(name: string, key: string, value: unknown) {
    setStratDraft((prev) => {
      if (!prev) return prev
      const next = structuredClone(prev)
      if (key.startsWith('entry_filters.')) {
        const subKey = key.split('.')[1]
        if (!next[name].entry_filters) next[name].entry_filters = {}
        ;(next[name].entry_filters as any)[subKey] = value
      } else {
        ;(next[name] as any)[key] = value
      }
      return next
    })
    setStratDirty(true)
  }

  async function saveWorkflow() {
    if (!wfDraft) return
    try {
      await updateWf.mutateAsync({
        circuit_breakers: wfDraft.circuit_breakers,
        trading_constraints: wfDraft.trading_constraints,
        trading_schedule: wfDraft.trading_schedule,
        execution_defaults: wfDraft.execution_defaults,
      })
      setWfDirty(false)
      showToast('success', 'Workflow rules saved')
    } catch (e: any) {
      showToast('error', e.response?.data?.detail || 'Failed to save')
    }
  }

  async function saveStrategy(name: string) {
    if (!stratDraft?.[name]) return
    try {
      await updateStrat.mutateAsync({ name, updates: stratDraft[name] })
      setStratDirty(false)
      showToast('success', `Strategy "${name}" saved`)
    } catch (e: any) {
      showToast('error', e.response?.data?.detail || 'Failed to save')
    }
  }

  function resetWorkflow() {
    if (wfData) { setWfDraft(structuredClone(wfData)); setWfDirty(false) }
  }

  function resetStrategies() {
    if (stratData) { setStratDraft(structuredClone(stratData)); setStratDirty(false) }
  }

  function addFomcDate() {
    if (!newFomc || !wfDraft) return
    const current = wfDraft.trading_schedule.fomc_dates || []
    if (!current.includes(newFomc)) {
      setWf('trading_schedule.fomc_dates', [...current, newFomc].sort())
    }
    setNewFomc('')
  }

  function removeFomcDate(date: string) {
    if (!wfDraft) return
    setWf('trading_schedule.fomc_dates', (wfDraft.trading_schedule.fomc_dates || []).filter((d: string) => d !== date))
  }

  if (wfLoading || stratLoading || !wfDraft || !stratDraft) return <Spinner />

  const cb = wfDraft.circuit_breakers
  const tc = wfDraft.trading_constraints
  const ts = wfDraft.trading_schedule
  const ex = wfDraft.execution_defaults

  return (
    <div className="p-4 overflow-y-auto h-full relative">
      <div className="flex items-center gap-2 mb-4">
        <Activity size={18} className="text-accent-orange" />
        <h2 className="text-sm font-semibold text-text-primary">Workflow & Strategy Rules</h2>
      </div>

      {/* Circuit Breakers */}
      <FormSection title="Circuit Breakers">
        <div className="grid grid-cols-3 gap-3">
          <NF label="Daily Loss Halt" value={cb.daily_loss_pct} onChange={(v) => setWf('circuit_breakers.daily_loss_pct', v)} suffix="%" />
          <NF label="Weekly Loss Halt" value={cb.weekly_loss_pct} onChange={(v) => setWf('circuit_breakers.weekly_loss_pct', v)} suffix="%" />
          <NF label="VIX Halt Threshold" value={cb.vix_halt_threshold} onChange={(v) => setWf('circuit_breakers.vix_halt_threshold', v)} />
          <NF label="Consecutive Loss Pause" value={cb.consecutive_loss_pause} onChange={(v) => setWf('circuit_breakers.consecutive_loss_pause', v)} />
          <NF label="Consecutive Loss Halt" value={cb.consecutive_loss_halt} onChange={(v) => setWf('circuit_breakers.consecutive_loss_halt', v)} />
        </div>
        {cb.max_portfolio_drawdown && (
          <div className="mt-3">
            <label className="block text-2xs text-text-muted mb-1 font-semibold">Max Portfolio Drawdown</label>
            <div className="grid grid-cols-5 gap-2">
              {Object.entries(cb.max_portfolio_drawdown).map(([port, val]) => (
                <div key={port}>
                  <label className="block text-2xs text-text-muted mb-0.5">{port}</label>
                  <input
                    type="number"
                    value={val}
                    onChange={(e) => setWf(`circuit_breakers.max_portfolio_drawdown.${port}`, parseFloat(e.target.value) || 0)}
                    className="w-full bg-bg-tertiary border border-border-primary rounded px-1.5 py-1 text-xs text-text-primary"
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </FormSection>

      {/* Trading Constraints */}
      <FormSection title="Trading Constraints">
        <div className="grid grid-cols-3 gap-3">
          <NF label="Max Trades/Day" value={tc.max_trades_per_day} onChange={(v) => setWf('trading_constraints.max_trades_per_day', v)} />
          <NF label="Max Trades/Week/Portfolio" value={tc.max_trades_per_week_per_portfolio} onChange={(v) => setWf('trading_constraints.max_trades_per_week_per_portfolio', v)} />
          <NF label="No Entry First Min" value={tc.no_entry_first_minutes} onChange={(v) => setWf('trading_constraints.no_entry_first_minutes', v)} suffix="min" />
          <NF label="No Entry Last Min" value={tc.no_entry_last_minutes} onChange={(v) => setWf('trading_constraints.no_entry_last_minutes', v)} suffix="min" />
          <Toggle label="Require Approval for Undefined Risk" checked={tc.require_approval_undefined_risk} onChange={(v) => setWf('trading_constraints.require_approval_undefined_risk', v)} />
          <Toggle label="No Adding to Losers" checked={tc.no_adding_to_losers_without_rationale} onChange={(v) => setWf('trading_constraints.no_adding_to_losers_without_rationale', v)} />
        </div>
      </FormSection>

      {/* Trading Schedule */}
      <FormSection title="Trading Schedule">
        <div className="grid grid-cols-2 gap-3 mb-3">
          <div>
            <label className="block text-2xs text-text-muted mb-1">Monthly DTE Window</label>
            <div className="flex gap-2 items-center">
              <input
                type="number"
                value={ts.monthly_dte_window[0]}
                onChange={(e) => setWf('trading_schedule.monthly_dte_window', [parseInt(e.target.value) || 0, ts.monthly_dte_window[1]])}
                className="w-16 bg-bg-tertiary border border-border-primary rounded px-1.5 py-1 text-xs text-text-primary"
              />
              <span className="text-2xs text-text-muted">to</span>
              <input
                type="number"
                value={ts.monthly_dte_window[1]}
                onChange={(e) => setWf('trading_schedule.monthly_dte_window', [ts.monthly_dte_window[0], parseInt(e.target.value) || 0])}
                className="w-16 bg-bg-tertiary border border-border-primary rounded px-1.5 py-1 text-xs text-text-primary"
              />
              <span className="text-2xs text-text-muted">DTE</span>
            </div>
          </div>
          <Toggle label="Skip 0DTE on FOMC" checked={ts.skip_0dte_on_fomc} onChange={(v) => setWf('trading_schedule.skip_0dte_on_fomc', v)} />
        </div>
        <div>
          <label className="block text-2xs text-text-muted mb-1 font-semibold">FOMC Dates</label>
          <div className="flex flex-wrap gap-1.5 mb-2">
            {(ts.fomc_dates || []).map((d: string) => (
              <span key={d} className="inline-flex items-center gap-1 px-2 py-0.5 bg-bg-tertiary border border-border-primary rounded text-xs text-text-primary">
                {d}
                <button onClick={() => removeFomcDate(d)} className="text-text-muted hover:text-accent-red">&times;</button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              type="date"
              value={newFomc}
              onChange={(e) => setNewFomc(e.target.value)}
              className="bg-bg-tertiary border border-border-primary rounded px-2 py-1 text-xs text-text-primary"
            />
            <button
              onClick={addFomcDate}
              className="px-2 py-1 text-xs bg-accent-blue/20 text-accent-blue border border-accent-blue/40 rounded hover:bg-accent-blue/30"
            >
              Add
            </button>
          </div>
        </div>
      </FormSection>

      {/* Execution Defaults */}
      <FormSection title="Execution Defaults">
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-2xs text-text-muted mb-1">Order Type</label>
            <select value={ex.order_type} onChange={(e) => setWf('execution_defaults.order_type', e.target.value)}
              className="w-full bg-bg-tertiary border border-border-primary rounded px-2 py-1.5 text-xs text-text-primary">
              <option value="limit">Limit</option>
              <option value="market">Market</option>
            </select>
          </div>
          <div>
            <label className="block text-2xs text-text-muted mb-1">Time in Force</label>
            <select value={ex.time_in_force} onChange={(e) => setWf('execution_defaults.time_in_force', e.target.value)}
              className="w-full bg-bg-tertiary border border-border-primary rounded px-2 py-1.5 text-xs text-text-primary">
              <option value="Day">Day</option>
              <option value="GTC">GTC</option>
              <option value="IOC">IOC</option>
            </select>
          </div>
          <div>
            <label className="block text-2xs text-text-muted mb-1">Price Strategy</label>
            <select value={ex.price_strategy} onChange={(e) => setWf('execution_defaults.price_strategy', e.target.value)}
              className="w-full bg-bg-tertiary border border-border-primary rounded px-2 py-1.5 text-xs text-text-primary">
              <option value="mid">Mid (bid-ask midpoint)</option>
              <option value="natural">Natural (best price)</option>
              <option value="aggressive">Aggressive</option>
            </select>
          </div>
          <NF label="Price Offset" value={ex.price_offset} onChange={(v) => setWf('execution_defaults.price_offset', v)} />
          <Toggle label="Require Dry Run" checked={ex.require_dry_run} onChange={(v) => setWf('execution_defaults.require_dry_run', v)} />
        </div>
      </FormSection>

      <SaveBar onSave={saveWorkflow} onReset={resetWorkflow} dirty={wfDirty} saving={updateWf.isPending} />

      {/* Strategy Rules */}
      <div className="mt-6 flex items-center gap-2 mb-3">
        <BookOpen size={16} className="text-accent-purple" />
        <h3 className="text-xs font-semibold text-text-primary uppercase tracking-wide">Strategy Rules</h3>
      </div>

      <div className="border border-border-primary rounded-lg overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-bg-tertiary text-text-muted text-2xs uppercase">
              <th className="text-left px-3 py-2">Strategy</th>
              <th className="text-right px-2 py-2">Min IV Rank</th>
              <th className="text-left px-2 py-2">Outlook</th>
              <th className="text-right px-2 py-2">DTE Range</th>
              <th className="text-left px-2 py-2">Requires</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(stratDraft).map(([name, rule]) => (
              <StrategyRow
                key={name}
                name={name}
                rule={rule}
                expanded={expandedStrat === name}
                onToggle={() => setExpandedStrat(expandedStrat === name ? null : name)}
                onChange={(key, val) => setStrat(name, key, val)}
                onSave={() => saveStrategy(name)}
              />
            ))}
          </tbody>
        </table>
      </div>

      {stratDirty && (
        <div className="mt-2">
          <SaveBar onSave={() => { /* save all */ }} onReset={resetStrategies} dirty={stratDirty} saving={updateStrat.isPending} />
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Strategy row with inline expand
// ---------------------------------------------------------------------------

function StrategyRow({ name, rule, expanded, onToggle, onChange, onSave }: {
  name: string; rule: StrategyRule; expanded: boolean;
  onToggle: () => void; onChange: (key: string, val: unknown) => void; onSave: () => void
}) {
  return (
    <>
      <tr
        className={clsx(
          'border-t border-border-secondary cursor-pointer transition-colors',
          expanded ? 'bg-bg-active' : 'hover:bg-bg-hover',
        )}
        onClick={onToggle}
      >
        <td className="px-3 py-2 text-text-primary font-medium">{name.replace(/_/g, ' ')}</td>
        <td className="px-2 py-2 text-right text-text-secondary">{rule.min_iv_rank}</td>
        <td className="px-2 py-2 text-text-secondary">{(rule.market_outlook || []).join(', ')}</td>
        <td className="px-2 py-2 text-right text-text-secondary">{(rule.dte_range || []).join(' - ')}</td>
        <td className="px-2 py-2 text-text-muted">{rule.requires || '—'}</td>
      </tr>
      {expanded && (
        <tr className="border-t border-border-secondary bg-bg-secondary">
          <td colSpan={5} className="px-4 py-3">
            <div className="grid grid-cols-4 gap-3 mb-3">
              <NF label="Min IV Rank" value={rule.min_iv_rank} onChange={(v) => onChange('min_iv_rank', v)} />
              <NF label="Preferred IV Rank" value={rule.preferred_iv_rank ?? 0} onChange={(v) => onChange('preferred_iv_rank', v)} />
              <div>
                <label className="block text-2xs text-text-muted mb-1">DTE Min</label>
                <input type="number" value={rule.dte_range?.[0] ?? 0}
                  onChange={(e) => onChange('dte_range', [parseInt(e.target.value) || 0, rule.dte_range?.[1] ?? 45])}
                  className="w-full bg-bg-tertiary border border-border-primary rounded px-2 py-1.5 text-xs text-text-primary" />
              </div>
              <div>
                <label className="block text-2xs text-text-muted mb-1">DTE Max</label>
                <input type="number" value={rule.dte_range?.[1] ?? 45}
                  onChange={(e) => onChange('dte_range', [rule.dte_range?.[0] ?? 0, parseInt(e.target.value) || 45])}
                  className="w-full bg-bg-tertiary border border-border-primary rounded px-2 py-1.5 text-xs text-text-primary" />
              </div>
            </div>
            {rule.entry_filters && (
              <div className="mt-2">
                <label className="block text-2xs text-text-muted mb-1 font-semibold">Entry Filters</label>
                <div className="grid grid-cols-4 gap-3">
                  {rule.entry_filters.rsi_range && (
                    <>
                      <NF label="RSI Min" value={rule.entry_filters.rsi_range[0]} onChange={(v) => onChange('entry_filters.rsi_range', [v, rule.entry_filters!.rsi_range![1]])} />
                      <NF label="RSI Max" value={rule.entry_filters.rsi_range[1]} onChange={(v) => onChange('entry_filters.rsi_range', [rule.entry_filters!.rsi_range![0], v])} />
                    </>
                  )}
                  {rule.entry_filters.min_atr_percent !== undefined && (
                    <NF label="Min ATR %" value={rule.entry_filters.min_atr_percent} onChange={(v) => onChange('entry_filters.min_atr_percent', v)} suffix="%" />
                  )}
                  {rule.entry_filters.min_iv_percentile !== undefined && (
                    <NF label="Min IV Percentile" value={rule.entry_filters.min_iv_percentile} onChange={(v) => onChange('entry_filters.min_iv_percentile', v)} />
                  )}
                </div>
              </div>
            )}
            <div className="mt-3 flex justify-end">
              <button
                onClick={(e) => { e.stopPropagation(); onSave() }}
                className="px-3 py-1.5 text-xs bg-accent-blue/20 text-accent-blue border border-accent-blue/40 rounded hover:bg-accent-blue/30"
              >
                Save Strategy
              </button>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function NF({ label, value, onChange, suffix }: {
  label: string; value: number; onChange: (v: number) => void; suffix?: string
}) {
  return (
    <div>
      <label className="block text-2xs text-text-muted mb-1">{label}</label>
      <div className="relative">
        <input type="number" step="any" value={value}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          className="w-full bg-bg-tertiary border border-border-primary rounded px-2 py-1.5 text-xs text-text-primary focus:border-accent-blue focus:outline-none pr-6" />
        {suffix && <span className="absolute right-2 top-1/2 -translate-y-1/2 text-2xs text-text-muted">{suffix}</span>}
      </div>
    </div>
  )
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={clsx(
          'w-8 h-4 rounded-full relative transition-colors',
          checked ? 'bg-accent-blue/50' : 'bg-bg-tertiary border border-border-primary',
        )}
      >
        <span className={clsx(
          'absolute top-0.5 w-3 h-3 rounded-full transition-all',
          checked ? 'left-4 bg-accent-blue' : 'left-0.5 bg-text-muted',
        )} />
      </button>
      <label className="text-2xs text-text-muted">{label}</label>
    </div>
  )
}
