import { http } from './http'
import type { KitchenBoard, KitchenStatusPayload, OrderDetail, OrderStatus } from './types'

export const kitchenService = {
  /** Requires the admin or kitchen role (`app/api/deps.require_staff`). */
  board(options?: { statuses?: OrderStatus[]; signal?: AbortSignal }) {
    return http.get<KitchenBoard>('/kitchen/board', {
      query: { statuses: options?.statuses },
      signal: options?.signal,
    })
  },

  /** Advance one step only — the backend rejects stage skipping. */
  advanceStatus(orderId: string, payload: KitchenStatusPayload) {
    return http.patch<OrderDetail>(`/kitchen/orders/${encodeURIComponent(orderId)}/status`, payload)
  },
}