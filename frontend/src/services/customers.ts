import { http } from './http'
import type { Customer, CustomerAdmin, Passport, PassportIn, SafetyReport } from './types'

export const customersService = {
  me(signal?: AbortSignal) {
    return http.get<Customer>('/customers/me', { signal })
  },

  getPassport(signal?: AbortSignal) {
    return http.get<Passport>('/customers/me/passport', { signal })
  },

  savePassport(payload: PassportIn) {
    return http.put<Passport>('/customers/me/passport', payload)
  },

  /** Simulates the impact of the saved passport on the weekly menu. */
  previewPassport(signal?: AbortSignal) {
    return http.get<SafetyReport>('/customers/me/passport/preview', { signal })
  },

  summary(signal?: AbortSignal) {
    return http.get<Record<string, unknown>>('/customers/me/passport/summary', { signal })
  },

  /** Admin only — see `app/api/routers/customers.py`. */
  listAll(options?: { limit?: number; search?: string; signal?: AbortSignal }) {
    return http.get<CustomerAdmin[]>('/admin/customers', {
      query: { limit: options?.limit ?? 200, search: options?.search },
      signal: options?.signal,
    })
  },

  detail(customerId: string, signal?: AbortSignal) {
    return http.get<CustomerAdmin>(`/customers/${encodeURIComponent(customerId)}`, { signal })
  },

  toggleLike(menuId: string, customerId?: string) {
    return http.post<{ liked: boolean; menu_id: string }>('/customers/likes/toggle', {
      menu_id: menuId,
      customer_id: customerId,
    })
  },

  getLikes(customerId?: string, signal?: AbortSignal) {
    return http.get<string[]>('/customers/likes', {
      query: { customer_id: customerId || 'guest_default' },
      signal,
    })
  },

  trackCartEvent(params: {
    menu_id: string
    quantity?: number
    action?: 'add' | 'remove' | 'abandon'
    customer_id?: string
  }) {
    return http.post<{ status: string; action: string; menu_id: string }>(
      '/customers/cart-event',
      {
        menu_id: params.menu_id,
        quantity: params.quantity ?? 1,
        action: params.action ?? 'add',
        customer_id: params.customer_id,
      }
    )
  },

  getRecommendations(customerId?: string, signal?: AbortSignal) {
    return http.get<
      Array<{
        menu_id: string
        nama_menu: string
        hari: string
        deskripsi: string
        score: number
        is_liked: boolean
        in_cart_history: boolean
        order_count_past: number
        match_reason: string
      }>
    >('/customers/recommendations', {
      query: { customer_id: customerId || 'guest_default' },
      signal,
    })
  },

  getRfm(customerId?: string, signal?: AbortSignal) {
    return http.get<{
      customer_id: string
      segment: string
      recency_days: number
      frequency: number
      monetary: number
      r_score: number
      f_score: number
      m_score: number
      rfm_score: string
      recommended_action: string
    }>('/customers/rfm', {
      query: { customer_id: customerId || 'cust_ml_001' },
      signal,
    })
  },
}