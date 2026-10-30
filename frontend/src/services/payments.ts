import { http } from './http'

export interface PaymentIntentRequest {
  provider: 'qris' | 'va'
  idempotency_key: string
}

export interface PaymentIntent {
  payment_attempt_id: string
  order_id: string
  provider: string
  provider_payment_id: string
  idempotency_key: string
  status: string
  amount: number
  currency: string
  expires_at: string | null
}

export const paymentsService = {
  createIntent(orderId: string, payload: PaymentIntentRequest) {
    return http.post<PaymentIntent>(
      `/payments/orders/${encodeURIComponent(orderId)}/intent`,
      payload,
    )
  },
}
