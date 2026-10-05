import { http } from './http'
import type { Customer, LoginPayload, RegisterPayload, StaffIn, TelegramLinkResult, Token } from './types'

export const authService = {
  register(payload: RegisterPayload) {
    return http.post<Token>('/auth/register', payload, { auth: false })
  },

  login(payload: LoginPayload) {
    return http.post<Token>('/auth/login', payload, { auth: false })
  },

  me(signal?: AbortSignal) {
    return http.get<Customer>('/auth/me', { signal })
  },

  createLinkCode() {
    return http.post<Customer>('/customers/me/telegram/code')
  },

  unlinkTelegram() {
    return http.delete<Customer>('/customers/me/telegram')
  },

  resolveTelegramLink(payload: {
    code: string
    chat_id: number
    telegram_username?: string
  }) {
    return http.post<TelegramLinkResult>('/auth/telegram/resolve', payload, { auth: false })
  },

  /** Admin only — see `app/api/routers/admin.py`. */
  createStaff(payload: StaffIn) {
    return http.post<Customer>('/admin/staff', payload)
  },
}