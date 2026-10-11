import { http } from './http'

export interface SupplierPOItem {
  id: number
  item_name: string
  qty: number
  unit: string
  unit_price: number
  subtotal: number
}

export interface SupplierPO {
  po_id: string
  supplier_id: string
  supplier_name: string
  supplier_phone: string
  category?: string
  email?: string
  status: string
  total_amount: number
  need_by_date: string
  notes?: string
  created_at: string
  items: SupplierPOItem[]
}

export interface SupplierItem {
  id: number
  supplier_id: string
  supplier_name: string
  item_name: string
  unit: string
  price_per_unit: number
  moq: number
  is_available: boolean
}

export interface SupplierSummary {
  total_pos: number
  pending_pos: number
  accepted_pos: number
  suppliers: Array<{
    supplier_id: string
    name: string
    category: string
    phone: string
    email: string
    rating: string
  }>
}

export const supplierService = {
  getPos(supplierId?: string, signal?: AbortSignal) {
    return http.get<SupplierPO[]>('/supplier/pos', {
      query: supplierId ? { supplier_id: supplierId } : undefined,
      signal,
    })
  },

  respondPo(poId: string, data: { status: string; notes?: string }) {
    return http.post<{ status: string; po_id: string; new_status: string }>(
      `/supplier/pos/${encodeURIComponent(poId)}/respond`,
      data
    )
  },

  getCatalog(supplierId?: string, signal?: AbortSignal) {
    return http.get<SupplierItem[]>('/supplier/catalog', {
      query: supplierId ? { supplier_id: supplierId } : undefined,
      signal,
    })
  },

  getSummary(signal?: AbortSignal) {
    return http.get<SupplierSummary>('/supplier/summary', { signal })
  },

  getDemandForecast(signal?: AbortSignal) {
    return http.get<{
      generated_at: any
      materials: any[]
      supplier_7d_forecast: Array<{
        material: string
        projected_kg: number
        unit: string
        urgency: string
        supplier: string
      }>
      peak_day: string
      top_dishes: Array<{
        menu_id: string
        nama_menu: string
        hari: string
        total_portions: number
        total_revenue: number
        share_percentage: number
      }>
    }>('/supplier/demand-forecast', { signal })
  },
}
