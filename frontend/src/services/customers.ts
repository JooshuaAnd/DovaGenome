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
}