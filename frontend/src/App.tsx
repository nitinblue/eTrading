import { Routes, Route } from 'react-router-dom'
import { AppShell } from './layout/AppShell'
import { DashboardPage } from './pages/DashboardPage'
import { PortfolioPage } from './pages/PortfolioPage'
import { PositionDetailPage } from './pages/PositionDetailPage'
import { RecommendationsPage } from './pages/RecommendationsPage'
import { WorkflowPage } from './pages/WorkflowPage'
import { RiskPage } from './pages/RiskPage'
import { PerformancePage } from './pages/PerformancePage'
import { CapitalPage } from './pages/CapitalPage'
import { AgentsPage } from './pages/AgentsPage'
import { AgentDetailPage } from './pages/AgentDetailPage'
import { ReportsPage } from './pages/ReportsPage'
import { DataExplorerPage } from './pages/DataExplorerPage'
import {
  PortfolioSettingsPage,
  RiskSettingsPage,
  WorkflowSettingsPage,
  CapitalDeploymentPage,
} from './pages/settings'
import { TradingDashboardPage } from './pages/TradingDashboardPage'
import { FundsPage } from './pages/FundsPage'
import { MarketDashboardPage } from './pages/MarketDashboardPage'
import { ResearchPage } from './pages/ResearchPage'
import { ToastContainer } from './components/common/Toast'

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<MarketDashboardPage />} />
        <Route path="/market" element={<MarketDashboardPage />} />
        <Route path="/market/:ticker" element={<ResearchPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/position/:id" element={<PositionDetailPage />} />
        <Route path="/recommendations" element={<RecommendationsPage />} />
        <Route path="/workflow" element={<WorkflowPage />} />
        <Route path="/risk" element={<RiskPage />} />
        <Route path="/performance" element={<PerformancePage />} />
        <Route path="/capital" element={<CapitalPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/agents/:name" element={<AgentDetailPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/trading" element={<TradingDashboardPage />} />
        <Route path="/funds" element={<FundsPage />} />
        <Route path="/data" element={<DataExplorerPage />} />

        {/* Settings / Config */}
        <Route path="/settings/portfolios" element={<PortfolioSettingsPage />} />
        <Route path="/settings/risk" element={<RiskSettingsPage />} />
        <Route path="/settings/workflow" element={<WorkflowSettingsPage />} />
        <Route path="/settings/capital" element={<CapitalDeploymentPage />} />
      </Routes>
      <ToastContainer />
    </AppShell>
  )
}
