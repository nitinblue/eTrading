import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import { endpoints } from '../api/endpoints'

export interface LiveOrder {
  order_id: string
  status: string
  underlying: string
  price: number | null
  broker: string
  legs: {
    symbol: string
    action: string
    quantity: number
    remaining_quantity: number
    instrument_type: string
  }[]
  filled_quantity: number
  received_at: string | null
  live_at: string | null
  cancellable: boolean
  reject_reason: string | null
}

interface LiveOrdersResponse {
  orders: LiveOrder[]
  count: number
}

export function useLiveOrders() {
  return useQuery<LiveOrder[]>({
    queryKey: ['liveOrders'],
    queryFn: async () => {
      const { data } = await api.get<LiveOrdersResponse>(endpoints.liveOrders)
      return data.orders || []
    },
    refetchInterval: 10_000,
  })
}
