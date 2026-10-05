import { http } from './http'
import type {
  AdminDashboard,
  AdminKpi,
  AdminSchedule,
  AdminSystem,
  CustomerAdmin,
  Invoice,
  PaymentStatus,
} from './types'

/** Every call in this service requires the admin role. */
export const adminService = {
  dashboard(signal?: AbortSignal) {
    return http.get<AdminDashboard>('/admin/dashboard', { signal })
  },

  kpis(signal?: AbortSignal) {
    return http.get<AdminKpi[]>('/admin/kpis', { signal })
  },

  schedule(signal?: AbortSignal) {
    return http.get<AdminSchedule>('/admin/schedule', { signal })
  },

  listCustomers(signal?: AbortSignal) {
    return http.get<CustomerAdmin[]>('/admin/customers', { signal })
  },

  system(signal?: AbortSignal) {
    return http.get<AdminSystem>('/admin/system', { signal })
  },

  /**
   * Manual payment marking. The backend takes query params, not a JSON body
   * (`app/api/routers/admin.py` `set_payment`).
   */
  setPayment(orderId: string, status: PaymentStatus, reference = '') {
    return http.post<Invoice>(`/admin/orders/${encodeURIComponent(orderId)}/payment`, undefined, {
      query: { status, reference },
    })
  },
}