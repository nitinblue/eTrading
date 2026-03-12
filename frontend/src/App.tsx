import { Routes, Route } from 'react-router-dom'
import { AppShell } from './layout/AppShell'
import { PortfolioPage } from './pages/PortfolioPage'
import { PositionDetailPage } from './pages/PositionDetailPage'
import { RiskPage } from './pages/RiskPage'
import { AgentsPage } from './pages/AgentsPage'
import { AgentDetailPage } from './pages/AgentDetailPage'
import { ReportsPage } from './pages/ReportsPage'
import { DataExplorerPage } from './pages/DataExplorerPage'
import { SettingsPage } from './pages/SettingsPage'
import { TradingTerminal } from './pages/TradingTerminal'
import { ResearchDashboardPage } from './pages/ResearchDashboardPage'
import { ToastContainer } from './components/common/Toast'

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<ResearchDashboardPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/position/:id" element={<PositionDetailPage />} />
        <Route path="/risk" element={<RiskPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/agents/:name" element={<AgentDetailPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/trading" element={<TradingTerminal />} />
        <Route path="/data" element={<DataExplorerPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
      <ToastContainer />
    </AppShell>
  )
}
