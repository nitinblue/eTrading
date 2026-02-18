import { useState, useEffect } from 'react'
import { DollarSign, TrendingUp, AlertTriangle } from 'lucide-react'
import { useAdminCapitalPlan, useUpdateCapitalPlan } from '../../hooks/useAdminApi'
import { useQuery } from '@tanstack/react-query'
import { api } from '../../api/client'
import { endpoints } from '../../api/endpoints'
import { FormSection } from '../../components/common/FormSection'
import { SaveBar } from '../../components/common/SaveBar'
import { Spinner } from '../../components/common/Spinner'
import { Badge } from '../../components/common/Badge'
import { showToast } from '../../components/common/Toast'
import type { CapitalPlanResponse, CapitalUtilization } from '../../api/types'

export function CapitalDeploymentPage() {
  const { data: plan, isLoading: planLoading } = useAdminCapitalPlan()
  const { data: liveCapital } = useQuery<CapitalUtilization[]>({
    queryKey: ['capital'],
    queryFn: async () => { const { data } = await api.get(endpoints.capital); return data },
    refetchInterval: 30_000,
  })
  const updateMut = useUpdateCapitalPlan()
  const [draft, setDraft] = useState<CapitalPlanResponse | null>(null)
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    if (plan) { setDraft(structuredClone(plan)); setDirty(false) }
  }, [plan])

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
      await updateMut.mutateAsync(draft)
      setDirty(false)
      showToast('success', 'Capital plan saved')
    } catch (e: any) {
      showToast('error', e.response?.data?.detail || 'Failed to save')
    }
  }

  function reset() {
    if (plan) { setDraft(structuredClone(plan)); setDirty(false) }
  }

  if (planLoading || !draft) return <Spinner />

  const portfolioNames = Object.keys(draft.idle_alert_pct)

  return (
    <div className="p-4 overflow-y-auto h-full relative">
      <div className="flex items-center gap-2 mb-4">
        <DollarSign size={18} className="text-accent-green" />
        <h2 className="text-sm font-semibold text-text-primary">Capital Deployment</h2>
      </div>

      {/* Current Capital Status (read-only, live) */}
      <FormSection title="Current Capital Status" description="Live from engine">
        {liveCapital && liveCapital.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-muted text-2xs uppercase">
                  <th className="text-left py-1 px-2">Portfolio</th>
                  <th className="text-right py-1 px-2">Equity</th>
                  <th className="text-right py-1 px-2">Cash</th>
                  <th className="text-right py-1 px-2">Deployed</th>
                  <th className="text-right py-1 px-2">Idle</th>
                  <th className="text-center py-1 px-2">Severity</th>
                </tr>
              </thead>
              <tbody>
                {liveCapital.map((c) => (
                  <tr key={c.name} className="border-t border-border-secondary">
                    <td className="py-1.5 px-2 text-text-primary font-medium">{c.name}</td>
                    <td className="py-1.5 px-2 text-right text-text-secondary">${c.total_equity.toLocaleString()}</td>
                    <td className="py-1.5 px-2 text-right text-text-secondary">${c.cash_balance.toLocaleString()}</td>
                    <td className="py-1.5 px-2 text-right text-text-primary">{c.deployed_pct.toFixed(1)}%</td>
                    <td className="py-1.5 px-2 text-right text-accent-yellow">${c.idle_capital.toLocaleString()}</td>
                    <td className="py-1.5 px-2 text-center">
                      <SeverityBadge severity={c.severity} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-text-muted text-xs">No live capital data available. Start the workflow engine.</div>
        )}
      </FormSection>

      {/* Idle Alert Thresholds */}
      <FormSection title="Idle Alert Thresholds" description="% of capital idle before alerting">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-text-muted text-2xs uppercase">
                <th className="text-left py-1 px-2">Portfolio</th>
                <th className="text-right py-1 px-2">Idle Alert %</th>
              </tr>
            </thead>
            <tbody>
              {portfolioNames.map((name) => (
                <tr key={name} className="border-t border-border-secondary">
                  <td className="py-1.5 px-2 text-text-primary">{name}</td>
                  <td className="py-1.5 px-2 text-right">
                    <input
                      type="number"
                      step="0.5"
                      value={draft.idle_alert_pct[name]}
                      onChange={(e) => set(`idle_alert_pct.${name}`, parseFloat(e.target.value) || 0)}
                      className="w-20 bg-bg-tertiary border border-border-primary rounded px-1.5 py-0.5 text-xs text-text-primary text-right"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </FormSection>

      {/* Escalation Rules */}
      <FormSection title="Escalation Rules">
        <div className="grid grid-cols-3 gap-3">
          <NF label="Warning (days idle)" value={draft.escalation.warning_days_idle} onChange={(v) => set('escalation.warning_days_idle', v)} suffix="d" />
          <NF label="Critical (days idle)" value={draft.escalation.critical_days_idle} onChange={(v) => set('escalation.critical_days_idle', v)} suffix="d" />
          <NF label="Nag Frequency" value={draft.escalation.nag_frequency_hours} onChange={(v) => set('escalation.nag_frequency_hours', v)} suffix="hr" />
        </div>
      </FormSection>

      {/* Target Annual Returns */}
      <FormSection title="Target Annual Returns">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-text-muted text-2xs uppercase">
                <th className="text-left py-1 px-2">Portfolio</th>
                <th className="text-right py-1 px-2">Target Return %</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(draft.target_annual_return_pct).map(([name, val]) => (
                <tr key={name} className="border-t border-border-secondary">
                  <td className="py-1.5 px-2 text-text-primary">{name}</td>
                  <td className="py-1.5 px-2 text-right">
                    <input
                      type="number"
                      step="0.5"
                      value={val}
                      onChange={(e) => set(`target_annual_return_pct.${name}`, parseFloat(e.target.value) || 0)}
                      className="w-20 bg-bg-tertiary border border-border-primary rounded px-1.5 py-0.5 text-xs text-text-primary text-right"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </FormSection>

      {/* Staggered Deployment */}
      <FormSection title="Staggered Deployment Ramp">
        <NF label="Ramp Weeks" value={draft.staggered_deployment.ramp_weeks} onChange={(v) => set('staggered_deployment.ramp_weeks', v)} suffix="wk" />
        <div className="mt-3">
          <label className="block text-2xs text-text-muted mb-1 font-semibold">Max Deploy per Week (%)</label>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-muted text-2xs uppercase">
                  <th className="text-left py-1 px-2">Portfolio</th>
                  <th className="text-right py-1 px-2">Max %/Week</th>
                  <th className="text-left py-1 px-2">Ramp Preview</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(draft.staggered_deployment.max_deploy_per_week_pct).map(([name, pct]) => (
                  <tr key={name} className="border-t border-border-secondary">
                    <td className="py-1.5 px-2 text-text-primary">{name}</td>
                    <td className="py-1.5 px-2 text-right">
                      <input
                        type="number"
                        step="1"
                        value={pct}
                        onChange={(e) => set(`staggered_deployment.max_deploy_per_week_pct.${name}`, parseFloat(e.target.value) || 0)}
                        className="w-20 bg-bg-tertiary border border-border-primary rounded px-1.5 py-0.5 text-xs text-text-primary text-right"
                      />
                    </td>
                    <td className="py-1.5 px-2">
                      <RampBar weeks={draft.staggered_deployment.ramp_weeks} pctPerWeek={pct} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </FormSection>

      <SaveBar onSave={save} onReset={reset} dirty={dirty} saving={updateMut.isPending} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SeverityBadge({ severity }: { severity: string }) {
  const variant = severity === 'critical' ? 'rejected'
    : severity === 'warning' ? 'pending'
    : severity === 'info' ? 'what_if'
    : 'default'
  return <Badge variant={variant}>{severity}</Badge>
}

function RampBar({ weeks, pctPerWeek }: { weeks: number; pctPerWeek: number }) {
  const bars = Array.from({ length: Math.min(weeks, 12) }, (_, i) => {
    const cumulative = Math.min((i + 1) * pctPerWeek, 100)
    return cumulative
  })
  return (
    <div className="flex items-end gap-px h-4">
      {bars.map((pct, i) => (
        <div
          key={i}
          className="w-2 bg-accent-green/60 rounded-t"
          style={{ height: `${Math.max(pct / 100 * 16, 2)}px` }}
          title={`Week ${i + 1}: ${pct.toFixed(0)}%`}
        />
      ))}
    </div>
  )
}

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
