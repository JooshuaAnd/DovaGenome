import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { ApiError, getErrorMessage, readToken, writeToken } from '@/services/http'
import { authService } from '@/services/auth'
import type { Customer, LoginPayload, RegisterPayload, Role } from '@/types'

/** `status` — the session is being restored from a stored token. */
export type AuthStatus = 'loading' | 'authenticated' | 'anonymous'

export interface AuthContextValue {
  status: AuthStatus
  customer: Customer | null
  token: string | null
  error: ApiError | null
  isAuthenticated: boolean
  role: Role | null
  hasRole: (...roles: Role[]) => boolean
  login: (payload: LoginPayload) => Promise<Customer | null>
  register: (payload: RegisterPayload) => Promise<Customer | null>
  logout: () => void
  refresh: () => Promise<void>
  clearError: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => readToken())
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [error, setError] = useState<ApiError | null>(null)

  /**
   * Status is derived, never stored: a token without a loaded profile means the
   * session is still being restored, and clearing the token resolves to
   * `anonymous` automatically — no state synchronisation needed.
   */
  const status: AuthStatus = !token ? 'anonymous' : customer ? 'authenticated' : 'loading'

  /** Restore the profile behind a stored token exactly once per token. */
  useEffect(() => {
    if (!token) return

    const controller = new AbortController()
    let active = true

    authService
      .me(controller.signal)
      .then((profile) => {
        if (!active) return
        setCustomer(profile)
      })
      .catch((cause: unknown) => {
        if (!active || controller.signal.aborted) return
        // An expired or tampered token must not linger in storage.
        writeToken(null)
        setToken(null)
        setCustomer(null)
        if (cause instanceof ApiError && cause.code !== 'aborted') setError(cause)
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [token])

  const adopt = useCallback((accessToken: string, profile: Customer) => {
    writeToken(accessToken)
    setCustomer(profile)
    setToken(accessToken)
    setError(null)
  }, [])

  const login = useCallback(
    async (payload: LoginPayload) => {
      setError(null)
      try {
        const result = await authService.login(payload)
        adopt(result.access_token, result.customer)
        return result.customer
      } catch (cause) {
        setError(
          cause instanceof ApiError
            ? cause
            : new ApiError({
                code: 'unknown_error',
                message: getErrorMessage(cause),
                details: {},
                status: 0,
              }),
        )
        return null
      }
    },
    [adopt],
  )

  const register = useCallback(
    async (payload: RegisterPayload) => {
      setError(null)
      try {
        const result = await authService.register(payload)
        adopt(result.access_token, result.customer)
        return result.customer
      } catch (cause) {
        setError(
          cause instanceof ApiError
            ? cause
            : new ApiError({
                code: 'unknown_error',
                message: getErrorMessage(cause),
                details: {},
                status: 0,
              }),
        )
        return null
      }
    },
    [adopt],
  )

  const logout = useCallback(() => {
    writeToken(null)
    setToken(null)
    setCustomer(null)
    setError(null)
  }, [])

  const refresh = useCallback(async () => {
    if (!token) return
    try {
      setCustomer(await authService.me())
    } catch {
      logout()
    }
  }, [token, logout])

  const clearError = useCallback(() => setError(null), [])

  const hasRole = useCallback(
    (...roles: Role[]) => (customer ? roles.includes(customer.role) : false),
    [customer],
  )

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      customer,
      token,
      error,
      isAuthenticated: status === 'authenticated',
      role: customer?.role ?? null,
      hasRole,
      login,
      register,
      logout,
      refresh,
      clearError,
    }),
    [status, customer, token, error, hasRole, login, register, logout, refresh, clearError],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

/** Access the auth session. Must be used inside `<AuthProvider>`. */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth harus dipakai di dalam <AuthProvider>.')
  }
  return context
}