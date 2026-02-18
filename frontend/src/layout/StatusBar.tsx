import { Circle, Wifi, WifiOff } from 'lucide-react'
import { useWorkflowStatus } from '../hooks/useWorkflowStatus'

export function StatusBar() {
  const { data: status, isError } = useWorkflowStatus()

  const connected = !isError && !!status
  const marketOpen = isMarketOpen()

  return (
    <footer className="h-6 bg-bg-primary border-t border-border-primary flex items-center justify-between px-4 text-2xs text-text-muted font-mono">
      {/* Left */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5">
          {connected ? (
            <Wifi size={10} className="text-accent-green" />
          ) : (
            <WifiOff size={10} className="text-accent-red" />
          )}
          <span>{connected ? 'Connected' : 'Disconnected'}</span>
        </div>

        <div className="flex items-center gap-1.5">
          <Circle
            size={6}
            fill={marketOpen ? '#22c55e' : '#555568'}
            className={marketOpen ? 'text-accent-green' : 'text-text-muted'}
          />
          <span>{marketOpen ? 'Market Open' : 'Market Closed'}</span>
        </div>
      </div>

      {/* Right */}
      <div className="flex items-center gap-4">
        {status?.pending_recommendations != null && status.pending_recommendations > 0 && (
          <span className="text-accent-orange">
            {status.pending_recommendations} pending rec{status.pending_recommendations !== 1 ? 's' : ''}
          </span>
        )}
        {status?.trades_today != null && (
          <span>Trades today: {status.trades_today}</span>
        )}
        <span>Trading CoTrader v0.1</span>
      </div>
    </footer>
  )
}

function isMarketOpen(): boolean {
  const now = new Date()
  const et = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }))
  const day = et.getDay()
  const hours = et.getHours()
  const minutes = et.getMinutes()
  const time = hours * 60 + minutes
  // NYSE: Mon-Fri 9:30-16:00 ET
  return day >= 1 && day <= 5 && time >= 570 && time < 960
}
