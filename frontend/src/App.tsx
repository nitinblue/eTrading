import { Routes, Route, Navigate } from 'react-router-dom'
import { AppShell } from './layout/AppShell'
import { PortfolioPage } from './pages/PortfolioPage'
import { PositionDetailPage } from './pages/PositionDetailPage'
import { ReportsPage } from './pages/ReportsPage'
import { DataExplorerPage } from './pages/DataExplorerPage'
import { AgentsPage } from './pages/AgentsPage'
import { AgentDetailPage } from './pages/AgentDetailPage'
import {
  PortfolioSettingsPage,
  RiskSettingsPage,
  WorkflowSettingsPage,
  CapitalDeploymentPage,
} from './pages/settings'
import { ToastContainer } from './components/common/Toast'

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/portfolio" replace />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/position/:id" element={<PositionDetailPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/data" element={<DataExplorerPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/agents/:name" element={<AgentDetailPage />} />

        {/* Settings / Config */}
        <Route path="/settings" element={<Navigate to="/settings/portfolios" replace />} />
        <Route path="/settings/portfolios" element={<PortfolioSettingsPage />} />
        <Route path="/settings/risk" element={<RiskSettingsPage />} />
        <Route path="/settings/workflow" element={<WorkflowSettingsPage />} />
        <Route path="/settings/capital" element={<CapitalDeploymentPage />} />
      </Routes>
      <ToastContainer />
    </AppShell>
  )
}
