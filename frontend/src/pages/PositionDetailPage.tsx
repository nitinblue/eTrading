import { useParams, useNavigate } from 'react-router-dom'
import { usePosition } from '../hooks/usePositions'
import { TradeDetailModal } from '../components/modals/TradeDetailModal'
import { Spinner } from '../components/common/Spinner'
import { EmptyState } from '../components/common/EmptyState'

export function PositionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: trade, isLoading } = usePosition(id || '')

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner size="lg" />
      </div>
    )
  }

  if (!trade) {
    return <EmptyState message="Trade not found" />
  }

  return (
    <TradeDetailModal
      trade={trade}
      onClose={() => navigate('/portfolio')}
    />
  )
}
