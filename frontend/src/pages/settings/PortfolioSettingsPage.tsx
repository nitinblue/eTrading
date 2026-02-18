import { useState, useEffect } from 'react'
import { clsx } from 'clsx'
import { Briefcase, Shield, Tag, Target, Info } from 'lucide-react'
import { useAdminPortfolios, useUpdatePortfolio } from '../../hooks/useAdminApi'
import { FormSection } from '../../components/common/FormSection'
import { SaveBar } from '../../components/common/SaveBar'
import { Badge } from '../../components/common/Badge'
import { Spinner } from '../../components/common/Spinner'
import { showToast } from '../../components/common/Toast'
import type { PortfolioConfig } from '../../api/types'

const ALL_STRATEGIES = [
  'single', 'vertical_spread', 'iron_condor', 'iron_butterfly',
  'straddle', 'strangle', 'butterfly', 'condor',
  'calendar_spread', 'calendar_double_spread', 'diagonal_spread',
  'jade_lizard', 'big_lizard', 'ratio_spread',
  'covered_call', 'protective_put', 'collar',
]

const RISK_FIELDS: { key: string; label: string; suffix: string }[] = [
  { key: 'max_portfolio_delta', label: 'Max Portfolio Delta', suffix: '' },
  { key: 'max_positions', label: 'Max Positions', suffix: '' },
  { key: 'max_single_position_pct', label: 'Max Single Position', suffix: '%' },
  { key: 'max_single_trade_risk_pct', label: 'Max Single Trade Risk', suffix: '%' },
  { key: 'max_total_risk_pct', label: 'Max Total Risk', suffix: '%' },
  { key: 'min_cash_reserve_pct', label: 'Min Cash Reserve', suffix: '%' },
  { key: 'max_concentration_pct', label: 'Max Concentration', suffix: '%' },
]

export function PortfolioSettingsPage() {
  const { data: portfolios, isLoading } = useAdminPortfolios()
  const updateMut = useUpdatePortfolio()
  const [selected, setSelected] = useState<string | null>(null)
  const [draft, setDraft] = useState<Partial<PortfolioConfig> | null>(null)
  const [dirty, setDirty] = useState(false)
  const [newUnderlying, setNewUnderlying] = useState('')

  const names = portfolios ? Object.keys(portfolios) : []
  const realNames = names.filter((n) => portfolios![n].portfolio_type === 'real')
  const whatifNames = names.filter((n) => portfolios![n].portfolio_type === 'what_if')

  useEffect(() => {
    if (portfolios && !selected && names.length > 0) {
      setSelected(names[0])
    }
  }, [portfolios])

  useEffect(() => {
    if (selected && portfolios?.[selected]) {
      setDraft({ ...portfolios[selected] })
      setDirty(false)
    }
  }, [selected, portfolios])

  function update(key: string, value: unknown) {
    setDraft((prev) => prev ? { ...prev, [key]: value } : prev)
    setDirty(true)
  }

  function updateRiskLimit(key: string, value: number) {
    setDraft((prev) => {
      if (!prev) return prev
      return { ...prev, risk_limits: { ...prev.risk_limits!, [key]: value } }
    })
    setDirty(true)
  }

  function toggleStrategy(list: 'allowed_strategies' | 'active_strategies', strat: string) {
    setDraft((prev) => {
      if (!prev) return prev
      const current = (prev[list] || []) as string[]
      const next = current.includes(strat) ? current.filter((s) => s !== strat) : [...current, strat]
      return { ...prev, [list]: next }
    })
    setDirty(true)
  }

  function addUnderlying() {
    const sym = newUnderlying.trim().toUpperCase()
    if (!sym || !draft) return
    const current = (draft.preferred_underlyings || []) as string[]
    if (!current.includes(sym)) {
      update('preferred_underlyings', [...current, sym])
    }
    setNewUnderlying('')
  }

  function removeUnderlying(sym: string) {
    if (!draft) return
    update('preferred_underlyings', ((draft.preferred_underlyings || []) as string[]).filter((s) => s !== sym))
  }

  async function save() {
    if (!selected || !draft) return
    try {
      await updateMut.mutateAsync({ name: selected, updates: draft })
      setDirty(false)
      showToast('success', `Portfolio "${selected}" saved`)
    } catch (e: any) {
      showToast('error', e.response?.data?.detail || 'Failed to save')
    }
  }

  function reset() {
    if (selected && portfolios?.[selected]) {
      setDraft({ ...portfolios[selected] })
      setDirty(false)
    }
  }

  if (isLoading) return <Spinner />

  return (
    <div className="flex h-full">
      {/* Left panel — portfolio list */}
      <div className="w-56 shrink-0 border-r border-border-primary overflow-y-auto">
        <div className="px-3 py-2 text-2xs font-semibold text-text-muted uppercase tracking-wide">Real</div>
        {realNames.map((name) => (
          <PortfolioListItem
            key={name}
            name={name}
            displayName={portfolios![name].display_name}
            type="real"
            active={selected === name}
            onClick={() => setSelected(name)}
          />
        ))}
        <div className="px-3 py-2 mt-2 text-2xs font-semibold text-text-muted uppercase tracking-wide">WhatIf</div>
        {whatifNames.map((name) => (
          <PortfolioListItem
            key={name}
            name={name}
            displayName={portfolios![name].display_name}
            type="what_if"
            active={selected === name}
            onClick={() => setSelected(name)}
          />
        ))}
      </div>

      {/* Right panel — form */}
      <div className="flex-1 overflow-y-auto p-4 relative">
        {!draft ? (
          <div className="text-text-muted text-xs mt-12 text-center">Select a portfolio</div>
        ) : (
          <>
            <div className="flex items-center gap-3 mb-4">
              <Briefcase size={18} className="text-accent-blue" />
              <h2 className="text-sm font-semibold text-text-primary">{draft.display_name || selected}</h2>
              <Badge variant={draft.portfolio_type || 'real'}>{draft.portfolio_type}</Badge>
              {draft.mirrors_real && (
                <span className="text-2xs text-text-muted">mirrors: {draft.mirrors_real}</span>
              )}
            </div>

            {/* General */}
            <FormSection title="General" description="Name, capital, exit profile">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Display Name" value={draft.display_name || ''} onChange={(v) => update('display_name', v)} />
                <Field label="Description" value={draft.description || ''} onChange={(v) => update('description', v)} />
                <NumField label="Initial Capital" value={draft.initial_capital ?? 0} onChange={(v) => update('initial_capital', v)} prefix="$" />
                <NumField label="Target Annual Return" value={draft.target_annual_return_pct ?? 0} onChange={(v) => update('target_annual_return_pct', v)} suffix="%" />
                <div>
                  <label className="block text-2xs text-text-muted mb-1">Exit Rule Profile</label>
                  <select
                    value={draft.exit_rule_profile || 'balanced'}
                    onChange={(e) => update('exit_rule_profile', e.target.value)}
                    className="w-full bg-bg-tertiary border border-border-primary rounded px-2 py-1.5 text-xs text-text-primary"
                  >
                    <option value="conservative">Conservative</option>
                    <option value="balanced">Balanced</option>
                    <option value="aggressive">Aggressive</option>
                  </select>
                </div>
              </div>
            </FormSection>

            {/* Strategies */}
            <FormSection title="Strategy Composition" description="Allowed and active strategies">
              {draft.mirrors_real && !draft.allowed_strategies?.length && (
                <div className="flex items-center gap-2 text-2xs text-accent-blue mb-3 bg-accent-blue/10 px-3 py-1.5 rounded">
                  <Info size={12} />
                  Strategies inherited from {draft.mirrors_real}
                </div>
              )}
              <div className="grid grid-cols-2 gap-x-6 gap-y-1">
                <div className="text-2xs text-text-muted font-semibold mb-1">Strategy</div>
                <div className="grid grid-cols-2 gap-4">
                  <span className="text-2xs text-text-muted font-semibold">Allowed</span>
                  <span className="text-2xs text-text-muted font-semibold">Active</span>
                </div>
                {ALL_STRATEGIES.map((strat) => {
                  const allowed = (draft.allowed_strategies || []).includes(strat)
                  const active = (draft.active_strategies || []).includes(strat)
                  return (
                    <div key={strat} className="contents">
                      <span className="text-xs text-text-secondary py-0.5">{strat.replace(/_/g, ' ')}</span>
                      <div className="grid grid-cols-2 gap-4">
                        <Checkbox checked={allowed} onChange={() => toggleStrategy('allowed_strategies', strat)} />
                        <Checkbox
                          checked={active}
                          onChange={() => toggleStrategy('active_strategies', strat)}
                          disabled={!allowed}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            </FormSection>

            {/* Risk Limits */}
            <FormSection title="Risk Limits">
              <div className="grid grid-cols-2 gap-3">
                {RISK_FIELDS.map(({ key, label, suffix }) => (
                  <NumField
                    key={key}
                    label={label}
                    value={(draft.risk_limits as any)?.[key] ?? 0}
                    onChange={(v) => updateRiskLimit(key, v)}
                    suffix={suffix || undefined}
                  />
                ))}
              </div>
            </FormSection>

            {/* Preferred Underlyings */}
            <FormSection title="Preferred Underlyings">
              <div className="flex flex-wrap gap-1.5 mb-2">
                {((draft.preferred_underlyings || []) as string[]).map((sym) => (
                  <span
                    key={sym}
                    className="inline-flex items-center gap-1 px-2 py-0.5 bg-bg-tertiary border border-border-primary rounded text-xs text-text-primary"
                  >
                    {sym}
                    <button onClick={() => removeUnderlying(sym)} className="text-text-muted hover:text-accent-red ml-0.5">&times;</button>
                  </span>
                ))}
              </div>
              <div className="flex gap-2">
                <input
                  value={newUnderlying}
                  onChange={(e) => setNewUnderlying(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && addUnderlying()}
                  placeholder="Add symbol..."
                  className="bg-bg-tertiary border border-border-primary rounded px-2 py-1 text-xs text-text-primary w-32"
                />
                <button
                  onClick={addUnderlying}
                  className="px-2 py-1 text-xs bg-accent-blue/20 text-accent-blue border border-accent-blue/40 rounded hover:bg-accent-blue/30"
                >
                  Add
                </button>
              </div>
            </FormSection>

            {/* Broker Info (read-only) */}
            <FormSection title="Broker Info" description="Read-only" defaultOpen={false}>
              <div className="grid grid-cols-2 gap-3 opacity-70">
                <ReadOnlyField label="Broker Firm" value={draft.broker_firm || '—'} />
                <ReadOnlyField label="Account Number" value={draft.account_number || '—'} />
                <ReadOnlyField label="Currency" value={draft.currency || '—'} />
                <ReadOnlyField label="Portfolio Type" value={draft.portfolio_type || '—'} />
              </div>
            </FormSection>

            <SaveBar onSave={save} onReset={reset} dirty={dirty} saving={updateMut.isPending} />
          </>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function PortfolioListItem({ name, displayName, type, active, onClick }: {
  name: string; displayName: string; type: string; active: boolean; onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'w-full text-left px-3 py-1.5 text-xs flex items-center gap-2 transition-colors',
        active ? 'bg-bg-active text-accent-blue' : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary',
      )}
    >
      <span className="truncate flex-1">{displayName}</span>
      {type === 'what_if' && <span className="text-2xs text-accent-blue opacity-60">WI</span>}
    </button>
  )
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="block text-2xs text-text-muted mb-1">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-bg-tertiary border border-border-primary rounded px-2 py-1.5 text-xs text-text-primary focus:border-accent-blue focus:outline-none"
      />
    </div>
  )
}

function NumField({ label, value, onChange, prefix, suffix }: {
  label: string; value: number; onChange: (v: number) => void; prefix?: string; suffix?: string
}) {
  return (
    <div>
      <label className="block text-2xs text-text-muted mb-1">{label}</label>
      <div className="relative">
        {prefix && <span className="absolute left-2 top-1/2 -translate-y-1/2 text-2xs text-text-muted">{prefix}</span>}
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          className={clsx(
            'w-full bg-bg-tertiary border border-border-primary rounded py-1.5 text-xs text-text-primary focus:border-accent-blue focus:outline-none',
            prefix ? 'pl-5 pr-2' : suffix ? 'pl-2 pr-6' : 'px-2',
          )}
        />
        {suffix && <span className="absolute right-2 top-1/2 -translate-y-1/2 text-2xs text-text-muted">{suffix}</span>}
      </div>
    </div>
  )
}

function ReadOnlyField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <label className="block text-2xs text-text-muted mb-1">{label}</label>
      <div className="bg-bg-primary border border-border-secondary rounded px-2 py-1.5 text-xs text-text-muted">
        {value}
      </div>
    </div>
  )
}

function Checkbox({ checked, onChange, disabled }: { checked: boolean; onChange: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={disabled ? undefined : onChange}
      className={clsx(
        'w-4 h-4 rounded border flex items-center justify-center transition-colors',
        disabled ? 'opacity-30 cursor-not-allowed border-border-secondary' :
        checked ? 'bg-accent-blue/30 border-accent-blue text-accent-blue' : 'border-border-primary hover:border-text-muted',
      )}
    >
      {checked && <span className="text-2xs">&#10003;</span>}
    </button>
  )
}
