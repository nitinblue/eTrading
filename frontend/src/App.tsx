import { useState, useEffect } from 'react'
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
import SystemOverviewPage from './pages/SystemOverviewPage'
import DeskPerformancePage from './pages/DeskPerformancePage'
import TradeJourneyPage from './pages/TradeJourneyPage'
import UserManualPage from './pages/UserManualPage'
import LoginPage from './pages/LoginPage'
import { ToastContainer } from './components/common/Toast'

// Auth state: check localStorage for existing token
function useAuth() {
  const [user, setUser] = useState<{ id: string; email: string; name: string } | null>(null)
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('cotrader_token')
    if (token) {
      // Verify token is still valid
      fetch('/api/auth/me', { headers: { Authorization: `Bearer ${token}` } })
        .then(r => r.json())
        .then(data => {
          if (data.authenticated && data.user) {
            setUser(data.user)
          }
        })
        .catch(() => {})
        .finally(() => setChecked(true))
    } else {
      // No token — show login page (user can skip)
      setChecked(true)
    }
  }, [])

  const login = (token: string, userData: { id: string; email: string; name: string }) => {
    setUser(userData)
  }

  const logout = () => {
    localStorage.removeItem('cotrader_token')
    localStorage.removeItem('cotrader_refresh')
    setUser(null)
  }

  const skip = () => {
    setUser({ id: 'anonymous', email: '', name: 'Anonymous' })
  }

  return { user, checked, login, logout, skip }
}

export default function App() {
  const { user, checked, login, logout, skip } = useAuth()

  // Still checking auth status
  if (!checked) {
    return (
      <div className="min-h-screen bg-bg-primary flex items-center justify-center">
        <div className="text-text-muted text-sm">Loading...</div>
      </div>
    )
  }

  // Not authenticated — show login (with skip option)
  if (!user) {
    return (
      <LoginPage
        onLogin={login}
        onSkip={skip}
      />
    )
  }

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<SystemOverviewPage />} />
        <Route path="/research" element={<ResearchDashboardPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/position/:id" element={<PositionDetailPage />} />
        <Route path="/risk" element={<RiskPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/agents/:name" element={<AgentDetailPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/trading" element={<TradingTerminal />} />
        <Route path="/desks" element={<DeskPerformancePage />} />
        <Route path="/journey" element={<TradeJourneyPage />} />
        <Route path="/data" element={<DataExplorerPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/manual" element={<UserManualPage />} />
      </Routes>
      <ToastContainer />
    </AppShell>
  )
}
