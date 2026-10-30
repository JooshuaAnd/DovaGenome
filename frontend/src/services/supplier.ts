import { http } from './http'

export interface SupplierPOItem {
  id: number
  ingredient_id?: string | null
  item_name: string
  qty: number
  received_qty?: number
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

export interface SupplierInvoice {
  supplier_invoice_id: string
  supplier_id: string
  supplier_name?: string
  invoice_number: string
  payment_terms: 'PAY_ON_DELIVERY' | 'WEEKLY_INVOICE'
  period_start?: string | null
  period_end?: string | null
  due_date: string
  amount: number
  expected_amount: number
  currency: string
  match_status: 'MATCHED' | 'REQUIRES_REVIEW'
  status: 'SUBMITTED' | 'APPROVED' | 'REJECTED' | 'PARTIALLY_PAID' | 'PAID'
  notes?: string
  po_ids: string[]
  created_at: string
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

  receivePo(
    poId: string,
    data: { lines: Array<{ po_item_id: number; quantity: number; unit: string }>; notes?: string },
    idempotencyKey: string
  ) {
    return http.post<{
      status: string
      receipt_id: string
      po_id: string
      po_status: string
      items: Array<Record<string, unknown>>
    }>(`/supplier/pos/${encodeURIComponent(poId)}/receive`, data, {
      headers: { 'Idempotency-Key': idempotencyKey },
    })
  },

  getInvoices(signal?: AbortSignal) {
    return http.get<SupplierInvoice[]>('/supplier/invoices', { signal })
  },

  submitInvoice(
    data: {
      invoice_number: string
      payment_terms: 'PAY_ON_DELIVERY' | 'WEEKLY_INVOICE'
      amount: number
      due_date: string
      po_id?: string
      period_start?: string
      period_end?: string
      notes?: string
    },
    idempotencyKey: string
  ) {
    return http.post<SupplierInvoice>('/supplier/invoices', data, {
      headers: { 'Idempotency-Key': idempotencyKey },
    })
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
      status?: string
      data_mode?: string
      source?: string
      calculation_version?: string
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
