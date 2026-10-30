import { http } from './http'
import type {
  KitchenBoard,
  KitchenConsumptionPayload,
  KitchenConsumptionResult,
  KitchenInventory,
  KitchenStatusPayload,
  ProductionBatch,
  ProductionBatchCreatePayload,
  ProductionBatchPlanPayload,
  ProductionBatchPlanResult,
  ProductionBatchList,
  ProductionWeighPayload,
  ProductionWeighResult,
  OrderDetail,
  OrderStatus,
} from './types'

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

  inventory(signal?: AbortSignal) {
    return http.get<KitchenInventory>('/kitchen/inventory', { signal })
  },

  consumeInventory(payload: KitchenConsumptionPayload) {
    return http.post<KitchenConsumptionResult>('/kitchen/inventory/consume', payload)
  },

  productionBatches(options?: { serviceDate?: string; signal?: AbortSignal }) {
    return http.get<ProductionBatchList>('/kitchen/production-batches', {
      query: { service_date: options?.serviceDate },
      signal: options?.signal,
    })
  },

  createProductionBatch(payload: ProductionBatchCreatePayload) {
    return http.post<ProductionBatch>('/kitchen/production-batches', payload)
  },

  planProductionBatches(payload: ProductionBatchPlanPayload) {
    return http.post<ProductionBatchPlanResult>('/kitchen/production-batches/plan-from-paid-orders', payload)
  },

  weighProduction(batchId: string, payload: ProductionWeighPayload) {
    return http.post<ProductionWeighResult>(
      `/kitchen/production-batches/${encodeURIComponent(batchId)}/weigh`,
      payload,
    )
  },

  completeProductionBatch(batchId: string) {
    return http.post<ProductionBatch>(
      `/kitchen/production-batches/${encodeURIComponent(batchId)}/complete`,
    )
  },
}
