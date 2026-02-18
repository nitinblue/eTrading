import { useState, useEffect } from 'react'
import { ShieldAlert } from 'lucide-react'
import { useAdminRisk, useUpdateRisk } from '../../hooks/useAdminApi'
import { FormSection } from '../../components/common/FormSection'
import { SaveBar } from '../../components/common/SaveBar'
import { Spinner } from '../../components/common/Spinner'
import { showToast } from '../../components/common/Toast'
import type { RiskSettingsResponse } from '../../api/types'

export function RiskSettingsPage() {
  const { data, isLoading } = useAdminRisk()
  const updateMut = useUpdateRisk()
  const [draft, setDraft] = useState<RiskSettingsResponse | null>(null)
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    if (data) {
      setDraft(structuredClone(data))
      setDirty(false)
    }
  }, [data])

  function set(path: string, value: unknown) {
    setDraft((prev) => {
      if (!prev) return prev
      const next = structuredClone(prev)
      const keys = path.split('.')
      let obj: any = next
      for (let i = 0; i < keys.length - 1; i++) obj = obj[keys[i]]
      obj[keys[keys.length - 1]] = value
      return next
    })
    setDirty(true)
  }

  async function save() {
    if (!draft) return
    try {
      await updateMut.mutateAsync({
        portfolio_risk: draft.portfolio_risk,
        concentration: draft.concentration,
        exit_rule_profiles: draft.exit_rule_profiles,
        liquidity_thresholds: draft.liquidity_thresholds,
        margin: draft.margin,
      })
      setDirty(false)
      showToast('success', 'Risk settings saved')
    } catch (e: any) {
      showToast('error', e.response?.data?.detail || 'Failed to save')
    }
  }

  function reset() {
    if (data) {
      setDraft(structuredClone(data))
      setDirty(false)
    }
  }

  if (isLoading || !draft) return <Spinner />

  const pr = draft.portfolio_risk
  const conc = draft.concentration

  return (
    <div className="p-4 overflow-y-auto h-full relative">
      <div className="flex items-center gap-2 mb-4">
        <ShieldAlert size={18} className="text-accent-red" />
        <h2 className="text-sm font-semibold text-text-primary">Risk Settings</h2>
      </div>

      {/* VaR Configuration */}
      <FormSection title="VaR Configuration">
        <div className="grid grid-cols-4 gap-3">
          <NF label="Confidence Level" value={pr.var.confidence_level} onChange={(v) => set('portfolio_risk.var.confidence_level', v)} />
          <NF label="Horizon (days)" value={pr.var.horizon_days} onChange={(v) => set('portfolio_risk.var.horizon_days', v)} />
          <NF label="Max VaR %" value={pr.var.max_var_percent} onChange={(v) => set('portfolio_risk.var.max_var_percent', v)} suffix="%" />
          <NF label="Warning Threshold" value={pr.var.warning_threshold} onChange={(v) => set('portfolio_risk.var.warning_threshold', v)} />
        </div>
      </FormSection>

      {/* Greeks Limits */}
      <FormSection title="Greeks Limits">
        <div className="grid grid-cols-4 gap-3">
          <NF label="Max Portfolio Delta" value={pr.greeks.max_portfolio_delta} onChange={(v) => set('portfolio_risk.greeks.max_portfolio_delta', v)} />
          <NF label="Max Portfolio Gamma" value={pr.greeks.max_portfolio_gamma} onChange={(v) => set('portfolio_risk.greeks.max_portfolio_gamma', v)} />
          <NF label="Max Theta % of Equity" value={pr.greeks.max_portfolio_theta_percent} onChange={(v) => set('portfolio_risk.greeks.max_portfolio_theta_percent', v)} suffix="%" />
          <NF label="Max Vega % of Equity" value={pr.greeks.max_portfolio_vega_percent} onChange={(v) => set('portfolio_risk.greeks.max_portfolio_vega_percent', v)} suffix="%" />
        </div>
      </FormSection>

      {/* Concentration Limits */}
      <FormSection title="Concentration Limits">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-text-muted text-2xs uppercase">
                <th className="text-left py-1 pr-4">Category</th>
                <th className="text-right py-1 px-2">Max %</th>
                <th className="text-right py-1 px-2">Warning %</th>
              </tr>
            </thead>
            <tbody>
              {(['single_underlying', 'strategy_type', 'direction', 'expiration', 'sector'] as const).map((cat) => (
                <tr key={cat} className="border-t border-border-secondary">
                  <td className="py-1.5 pr-4 text-text-secondary">{cat.replace(/_/g, ' ')}</td>
                  <td className="py-1.5 px-2">
                    <input
                      type="number"
                      value={conc[cat]?.max_percent ?? conc[cat]?.max_long_percent ?? 0}
                      onChange={(e) =>
                        set(`concentration.${cat}.${cat === 'direction' ? 'max_long_percent' : 'max_percent'}`, parseFloat(e.target.value) || 0)
                      }
                      className="w-16 bg-bg-tertiary border border-border-primary rounded px-1.5 py-0.5 text-xs text-text-primary text-right"
                    />
                  </td>
                  <td className="py-1.5 px-2">
                    <input
                      type="number"
                      value={conc[cat]?.warning_percent ?? 0}
                      onChange={(e) => set(`concentration.${cat}.warning_percent`, parseFloat(e.target.value) || 0)}
                      className="w-16 bg-bg-tertiary border border-border-primary rounded px-1.5 py-0.5 text-xs text-text-primary text-right"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </FormSection>

      {/* Drawdown & Loss */}
      <FormSection title="Drawdown & Loss">
        <div className="grid grid-cols-2 gap-3">
          <NF label="Max Drawdown" value={pr.drawdown.max_drawdown_percent} onChange={(v) => set('portfolio_risk.drawdown.max_drawdown_percent', v)} suffix="%" />
          <NF label="Daily Loss Limit" value={pr.drawdown.daily_loss_limit_percent} onChange={(v) => set('portfolio_risk.drawdown.daily_loss_limit_percent', v)} suffix="%" />
        </div>
      </FormSection>

      {/* Margin */}
      <FormSection title="Margin">
        <div className="grid grid-cols-4 gap-3">
          <NF label="Min BP Reserve" value={draft.margin.min_buying_power_reserve} onChange={(v) => set('margin.min_buying_power_reserve', v)} suffix="%" />
          <NF label="Warning Threshold" value={draft.margin.margin_warning_percent} onChange={(v) => set('margin.margin_warning_percent', v)} suffix="%" />
          <NF label="Critical Threshold" value={draft.margin.margin_critical_percent} onChange={(v) => set('margin.margin_critical_percent', v)} suffix="%" />
          <NF label="Max Single Trade Margin" value={draft.margin.max_single_trade_margin_percent} onChange={(v) => set('margin.max_single_trade_margin_percent', v)} suffix="%" />
        </div>
      </FormSection>

      {/* Exit Rule Profiles */}
      <FormSection title="Exit Rule Profiles">
        <div className="grid grid-cols-3 gap-4">
          {Object.entries(draft.exit_rule_profiles).map(([name, profile]) => (
            <div key={name} className="border border-border-primary rounded-lg p-3 bg-bg-primary">
              <h4 className="text-xs font-semibold text-text-primary mb-2 capitalize">{name}</h4>
              <div className="space-y-2">
                <NF label="Profit Target" value={profile.profit_target_pct} onChange={(v) => set(`exit_rule_profiles.${name}.profit_target_pct`, v)} suffix="%" />
                <NF label="Stop Loss Multiplier" value={profile.stop_loss_multiplier} onChange={(v) => set(`exit_rule_profiles.${name}.stop_loss_multiplier`, v)} suffix="x" />
                <NF label="Roll DTE" value={profile.roll_dte} onChange={(v) => set(`exit_rule_profiles.${name}.roll_dte`, v)} suffix="d" />
                <NF label="Close DTE" value={profile.close_dte} onChange={(v) => set(`exit_rule_profiles.${name}.close_dte`, v)} suffix="d" />
              </div>
            </div>
          ))}
        </div>
      </FormSection>

      {/* Liquidity Thresholds */}
      <FormSection title="Liquidity Thresholds">
        <div className="grid grid-cols-2 gap-4">
          {(['entry', 'adjustment'] as const).map((type) => (
            <div key={type} className="border border-border-primary rounded-lg p-3 bg-bg-primary">
              <h4 className="text-xs font-semibold text-text-primary mb-2 capitalize">{type}</h4>
              <div className="space-y-2">
                <NF label="Min Open Interest" value={draft.liquidity_thresholds[type].min_open_interest} onChange={(v) => set(`liquidity_thresholds.${type}.min_open_interest`, v)} />
                <NF label="Max Spread" value={draft.liquidity_thresholds[type].max_bid_ask_spread_pct} onChange={(v) => set(`liquidity_thresholds.${type}.max_bid_ask_spread_pct`, v)} suffix="%" />
                <NF label="Min Daily Volume" value={draft.liquidity_thresholds[type].min_daily_volume} onChange={(v) => set(`liquidity_thresholds.${type}.min_daily_volume`, v)} />
              </div>
            </div>
          ))}
        </div>
      </FormSection>

      <SaveBar onSave={save} onReset={reset} dirty={dirty} saving={updateMut.isPending} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Num field helper
// ---------------------------------------------------------------------------

function NF({ label, value, onChange, suffix }: {
  label: string; value: number; onChange: (v: number) => void; suffix?: string
}) {
  return (
    <div>
      <label className="block text-2xs text-text-muted mb-1">{label}</label>
      <div className="relative">
        <input
          type="number"
          step="any"
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          className="w-full bg-bg-tertiary border border-border-primary rounded px-2 py-1.5 text-xs text-text-primary focus:border-accent-blue focus:outline-none pr-6"
        />
        {suffix && <span className="absolute right-2 top-1/2 -translate-y-1/2 text-2xs text-text-muted">{suffix}</span>}
      </div>
    </div>
  )
}
