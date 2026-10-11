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

  getPosKds(signal?: AbortSignal) {
    return http.get<{
      metrics: { new_orders: number; total_orders: number; waiting_list: number }
      orders: any[]
    }>('/admin/pos-kds', { signal })
  },

  advanceOrder(orderId: string, targetStatus: string) {
    return http.post<{ status: string; order_id: string; new_status: string }>(
      `/admin/orders/${encodeURIComponent(orderId)}/advance`,
      undefined,
      { query: { target_status: targetStatus } }
    )
  },

  getPopularDishes(signal?: AbortSignal) {
    return http.get<
      Array<{ menu_id: string; nama_menu: string; hari: string; order_count: number }>
    >('/admin/popular-dishes', { signal })
  },

  getInventoryAlerts(signal?: AbortSignal) {
    return http.get<
      Array<{
        id: number
        ingredient_name: string
        current_stock: number
        min_stock: number
        unit: string
        status: string
        updated_at: string
      }>
    >('/admin/inventory-alerts', { signal })
  },

  getNotifications(signal?: AbortSignal) {
    return http.get<any[]>('/admin/notifications', { signal })
  },

  sendNotification(params: {
    recipient_type: string
    recipient_name: string
    recipient_phone: string
    channel: string
    message: string
  }) {
    return http.post<{ status: string; channel: string; recipient: string }>(
      '/admin/notifications/send',
      undefined,
      { query: params }
    )
  },

  getSuppliers(signal?: AbortSignal) {
    return http.get<{ suppliers: any[]; purchase_orders: any[] }>('/admin/suppliers', { signal })
  },

  getDescriptiveStats(signal?: AbortSignal) {
    return http.get<{
      n: number
      variables: Array<{
        variable: string
        n: number
        mean: number
        median: number
        std_dev: number
        min: number
        q1: number
        q3: number
        max: number
        iqr: number
        lower_bound: number
        upper_bound: number
        outlier_count: number
        cv: number
        skewness: number
        sum: number
        range: number
        variance: number
        std_err: number
        ci_95_lower: number
        ci_95_upper: number
      }>
      frequency_table: Array<{
        interval: string
        frequency: number
        proportion: string
        cumulative: string
      }>
    }>('/admin/analytics/descriptive-stats', { signal })
  },

  getRfmCrm(signal?: AbortSignal) {
    return http.get<{
      total_analyzed: number
      segment_counts: Record<string, number>
      customers: Array<{
        customer_id: string
        name: string
        phone: string
        recency_days: number
        frequency: number
        monetary: number
        r_score: number
        f_score: number
        m_score: number
        rfm_score?: string
        segment: string
        recommended_action: string
      }>
    }>('/admin/analytics/rfm-crm', { signal })
  },

  getDemandInsights(signal?: AbortSignal) {
    return http.get<{
      top_dishes: Array<{
        menu_id: string
        nama_menu: string
        hari: string
        total_portions: number
        total_revenue: number
        share_percentage: number
      }>
      day_stats: Array<{
        day: string
        order_count: number
        portion_count: number
        revenue: number
        percentage: number
      }>
      peak_day: string
      monthly_trends: Array<{
        month_key: string
        month_label: string
        order_count: number
        total_sales: number
        avg_rating: number
      }>
      ai_daily_plan: Array<{
        day: string
        recommended_menu: string
        predicted_portions: number
        rationale: string
        allergen_notice: string
      }>
      supplier_7d_forecast: Array<{
        material: string
        projected_kg: number
        unit: string
        urgency: string
        supplier: string
      }>
    }>('/admin/analytics/demand-insights', { signal })
  },

  getSupplyChainMl(signal?: AbortSignal) {
    return http.get<{
      demand_forecast: {
        average_daily_meals: number
        sigma_daily_demand: number
        moving_average_7d: number
        linear_regression_forecast_tomorrow: number
        confidence_level: string
      }
      materials: Array<{
        ingredient_name: string
        current_stock: number
        unit: string
        daily_consumption_avg: number
        safety_stock: number
        reorder_point_rop: number
        status: string
        suggested_order_qty: number
      }>
      auto_po_recommendations: Array<{
        ingredient: string
        shortage: number
        unit: string
        order_qty: number
        estimated_cost: number
        supplier: string
      }>
    }>('/admin/analytics/supply-chain-ml', { signal })
  },
}