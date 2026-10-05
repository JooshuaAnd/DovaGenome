import { http } from './http'
import type {
  Invoice,
  Order,
  OrderCreatePayload,
  OrderDetail,
  OrderTimelineEntry,
  OrderUpdatePayload,
} from './types'

export const ordersService = {
  /** "Pesanan saya" — always scoped to the authenticated customer. */
  listMine(options?: { limit?: number; signal?: AbortSignal }) {
    return http.get<Order[]>('/orders', {
      query: { limit: options?.limit ?? 50 },
      signal: options?.signal,
    })
  },

  create(payload: OrderCreatePayload) {
    return http.post<OrderDetail>('/orders', payload)
  },

  detail(orderId: string, signal?: AbortSignal) {
    return http.get<OrderDetail>(`/orders/${encodeURIComponent(orderId)}`, { signal })
  },

  update(orderId: string, payload: OrderUpdatePayload) {
    return http.patch<OrderDetail>(`/orders/${encodeURIComponent(orderId)}`, payload)
  },

  timeline(orderId: string, signal?: AbortSignal) {
    return http.get<OrderTimelineEntry[]>(`/orders/${encodeURIComponent(orderId)}/timeline`, {
      signal,
    })
  },

  invoice(orderId: string, signal?: AbortSignal) {
    return http.get<Invoice>(`/orders/${encodeURIComponent(orderId)}/invoice`, { signal })
  },
}