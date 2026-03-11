import { useState } from 'react'
import { clsx } from 'clsx'
import { Briefcase, Shield, Activity, DollarSign } from 'lucide-react'
import { PortfolioSettingsPage } from './settings/PortfolioSettingsPage'
import { RiskSettingsPage } from './settings/RiskSettingsPage'
import { WorkflowSettingsPage } from './settings/WorkflowSettingsPage'
import { CapitalDeploymentPage } from './settings/CapitalDeploymentPage'

type TabId = 'portfolios' | 'risk' | 'workflow' | 'capital'

const tabs: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: 'portfolios', label: 'Portfolios', icon: Briefcase },
  { id: 'risk', label: 'Risk', icon: Shield },
  { id: 'workflow', label: 'Workflow', icon: Activity },
  { id: 'capital', label: 'Capital', icon: DollarSign },
]

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabId>('portfolios')

  return (
    <div className="p-4">
      {/* Tab bar */}
      <div className="flex items-center gap-1 mb-4 border-b border-border-primary">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-2 text-xs transition-colors border-b-2 -mb-px',
              activeTab === id
                ? 'border-accent-blue text-accent-blue'
                : 'border-transparent text-text-muted hover:text-text-secondary',
            )}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'portfolios' && <PortfolioSettingsPage />}
      {activeTab === 'risk' && <RiskSettingsPage />}
      {activeTab === 'workflow' && <WorkflowSettingsPage />}
      {activeTab === 'capital' && <CapitalDeploymentPage />}
    </div>
  )
}
