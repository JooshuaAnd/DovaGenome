/**
 * Base HTTP client for the DovaGenome FastAPI backend.
 *
 * Responsibilities:
 *  - build URLs from `VITE_API_BASE_URL` + `VITE_API_PREFIX`
 *  - attach the bearer token stored by `useAuth`
 *  - unwrap the backend error envelope into a typed `ApiError`
 *
 * Raw JSON never reaches the UI: pages read `error.message`.
 */

import type { ErrorBody, ValidationFieldError } from './types'

const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
).replace(/\/+$/, '')

const API_PREFIX = (import.meta.env.VITE_API_PREFIX ?? '/api').replace(/\/+$/, '')

export const TOKEN_STORAGE_KEY = 'dova.auth.token'

/** Query values the API accepts; arrays become repeated keys (FastAPI list query). */
export type QueryValue = string | number | boolean | null | undefined
export type QueryParams = Record<string, QueryValue | QueryValue[]>

export interface ApiErrorShape {
  code: string
  message: string
  details: Record<string, unknown>
  status: number
}

/** Typed, user-displayable error. Every failure path in this client produces one. */
export class ApiError extends Error implements ApiErrorShape {
  readonly code: string
  readonly details: Record<string, unknown>
  readonly status: number

  constructor({ code, message, details = {}, status }: ApiErrorShape) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.details = details
    this.status = status
  }

  /** Field-level messages from a 422 response, flattened for display. */
  get fieldErrors(): ValidationFieldError[] {
    const fields = this.details.fields
    return Array.isArray(fields) ? (fields as ValidationFieldError[]) : []
  }

  /** Human-readable summary of every field problem, newline separated. */
  get fieldMessages(): string[] {
    return this.fieldErrors
      .map((f) => (f.field ? `${f.field}: ${f.message}` : f.message))
      .filter(Boolean)
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError
}

/** Safely render any thrown value as a sentence a customer can act on. */
export function getErrorMessage(value: unknown, fallback = 'Terjadi kesalahan.'): string {
  if (value instanceof ApiError) return value.message
  if (value instanceof Error && value.message) return value.message
  return fallback
}

/* ── Token storage ───────────────────────────────────────────────────────── */

export function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY)
  } catch {
    return null
  }
}

export function writeToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_STORAGE_KEY, token)
    else localStorage.removeItem(TOKEN_STORAGE_KEY)
  } catch {
    /* storage unavailable (private mode) — the session simply won't persist. */
  }
}

/* ── URL building ────────────────────────────────────────────────────────── */

export function buildUrl(path: string, query?: QueryParams): string {
  const suffix = path.startsWith('/') ? path : `/${path}`
  const url = `${BASE_URL}${API_PREFIX}${suffix}`
  if (!query) return url

  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item === undefined || item === null) continue
        params.append(key, String(item))
      }
    } else {
      params.append(key, String(value))
    }
  }

  const qs = params.toString()
  return qs ? `${url}?${qs}` : url
}

/* ── Error normalisation ─────────────────────────────────────────────────── */

const STATUS_FALLBACKS: Record<number, string> = {
  400: 'Permintaan tidak valid.',
  401: 'Silakan masuk terlebih dahulu.',
  403: 'Kamu tidak punya akses ke bagian ini.',
  404: 'Data yang diminta tidak ditemukan.',
  409: 'Data sudah berubah. Muat ulang halaman lalu coba lagi.',
  422: 'Data yang dikirim belum lengkap atau tidak valid.',
  429: 'Terlalu banyak permintaan. Coba lagi sebentar lagi.',
  500: 'Terjadi kesalahan di sisi kami. Tim sudah diberi tahu.',
  502: 'Layanan sedang tidak tersedia. Coba lagi sebentar lagi.',
  503: 'Layanan sedang tidak tersedia. Coba lagi sebentar lagi.',
}

/** Map an HTTP status to the backend's error `code` vocabulary. */
export function codeForStatus(status: number): string {
  if (status === 401) return 'unauthorized'
  if (status === 403) return 'forbidden'
  if (status === 404) return 'not_found'
  if (status === 409) return 'conflict'
  if (status === 422) return 'validation_error'
  if (status === 429) return 'rate_limited'
  if (status === 503) return 'database_unavailable'
  if (status >= 500) return 'internal_error'
  return 'bad_request'
}

/** The backend's top-level error envelope: `{ error: { code, message, details } }`. */
interface ErrorEnvelope {
  error: ErrorBody
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (!value || typeof value !== 'object') return false
  const body = (value as { error?: unknown }).error
  if (!body || typeof body !== 'object') return false
  const candidate = body as Record<string, unknown>
  return typeof candidate.code === 'string' && typeof candidate.message === 'string'
}

/**
 * Turn a non-OK response into an `ApiError`.
 *
 * The backend always answers errors as `{ error: { code, message, details } }`
 * (see `app/main.py`). Anything else — a proxy HTML page, an empty body, a
 * malformed envelope — degrades to a status-derived message instead of leaking
 * a raw body into the UI.
 */
export async function normaliseError(response: Response): Promise<ApiError> {
  const status = response.status
  let body: unknown = null
  try {
    const text = await response.text()
    body = text ? (JSON.parse(text) as unknown) : null
  } catch {
    body = null
  }

  if (isErrorEnvelope(body)) {
    const details = (body.error.details ?? {}) as Record<string, unknown>
    return new ApiError({
      code: body.error.code,
      message: body.error.message || STATUS_FALLBACKS[status] || 'Permintaan gagal.',
      details,
      status,
    })
  }

  return new ApiError({
    code: codeForStatus(status),
    message: STATUS_FALLBACKS[status] ?? `Permintaan gagal (HTTP ${status}).`,
    details: {},
    status,
  })
}

/* ── Request ─────────────────────────────────────────────────────────────── */

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  /** Plain object is JSON-encoded; pass `undefined` to omit the body. */
  body?: unknown
  query?: QueryParams
  signal?: AbortSignal
  /** Set false for public endpoints that must not send a stale token. */
  auth?: boolean
}

const networkError = (cause: unknown) =>
  new ApiError({
    code: 'network_error',
    message: 'Tidak dapat terhubung ke server. Periksa koneksi lalu coba lagi.',
    details: { cause: cause instanceof Error ? cause.message : String(cause) },
    status: 0,
  })

/**
 * Perform an API call and return the decoded JSON body.
 *
 * @throws {ApiError} for every failure, including network and abort failures
 *   that callers may want to filter by `error.code === 'aborted'`.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, signal, auth = true } = options

  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  if (auth) {
    const token = readToken()
    if (token) headers.Authorization = `Bearer ${token}`
  }

  let response: Response
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') {
      throw new ApiError({
        code: 'aborted',
        message: 'Permintaan dibatalkan.',
        details: {},
        status: 0,
      })
    }
    throw networkError(cause)
  }

  if (!response.ok) throw await normaliseError(response)

  if (response.status === 204) return undefined as T

  const text = await response.text()
  if (!text) return undefined as T

  try {
    return JSON.parse(text) as T
  } catch {
    throw new ApiError({
      code: 'invalid_response',
      message: 'Respons server tidak dapat dibaca.',
      details: {},
      status: response.status,
    })
  }
}

/** Convenience wrappers so services read declaratively. */
export const http = {
  get: <T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    apiRequest<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    apiRequest<T>(path, { ...options, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    apiRequest<T>(path, { ...options, method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    apiRequest<T>(path, { ...options, method: 'PATCH', body }),
  delete: <T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    apiRequest<T>(path, { ...options, method: 'DELETE' }),
}

export { BASE_URL, API_PREFIX }