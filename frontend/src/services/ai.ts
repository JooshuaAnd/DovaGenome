import { http } from './http'
import type {
  AiConsultPayload,
  AiConsultResult,
  AiMenuSuggestionPayload,
  AiMenuSuggestionResult,
  FeedbackPayload,
  FeedbackResult,
} from './types'

/** Configuration snapshot — never contains secrets (`app/api/routers/ai.py`). */
export interface AiConfig {
  provider: string
  configured: boolean
  flow_id_set: boolean
  telegram_bot_username: string
  checked_at: string
}

export const aiService = {
  consult(payload: AiConsultPayload, signal?: AbortSignal) {
    return http.post<AiConsultResult>('/ai/consult', payload, { signal })
  },

  menuSuggestion(payload: AiMenuSuggestionPayload, signal?: AbortSignal) {
    return http.post<AiMenuSuggestionResult>('/ai/menu-suggestion', payload, { signal })
  },

  feedback(payload: FeedbackPayload) {
    return http.post<FeedbackResult>('/ai/feedback', payload)
  },

  config(signal?: AbortSignal) {
    return http.get<AiConfig>('/ai/config', { signal })
  },
}