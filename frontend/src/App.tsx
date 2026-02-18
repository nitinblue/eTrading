import { Routes, Route, Navigate } from 'react-router-dom'
import { AppShell } from './layout/AppShell'
import { PortfolioPage } from './pages/PortfolioPage'
import { PositionDetailPage } from './pages/PositionDetailPage'

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<Navigate to="/portfolio" replace />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/position/:id" element={<PositionDetailPage />} />
      </Routes>
    </AppShell>
  )
}
