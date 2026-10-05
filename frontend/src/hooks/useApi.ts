import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError, getErrorMessage } from '@/services/http'

export interface UseApiState<T> {
  data: T | null
  error: ApiError | null
  loading: boolean
  /** False only before the first request starts. */
  settled: boolean
  refetch: () => void
}

export interface UseApiOptions {
  /** Skip fetching entirely — handy while a guard is still resolving. */
  enabled?: boolean
  /** Extra dependencies; re-runs the request when they change. */
  deps?: readonly unknown[]
}

/**
 * Typed GET helper around {@link apiRequest} with cancellation.
 *
 * Every in-flight request is aborted on unmount or on a dependency change, and
 * a late abort is never surfaced as an error to the user.
 *
 * @example
 * const { data, error, loading } = useApi<Catalog>(() => catalogService.getCatalog(), { enabled })
 */
export function useApi<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  options: UseApiOptions = {},
): UseApiState<T> {
  const { enabled = true, deps = [] } = options

  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(enabled)
  const [settled, setSettled] = useState(false)
  const [nonce, setNonce] = useState(0)

  // Keep the latest fetcher without making it an effect dependency — callers
  // usually pass an inline arrow function.
  const fetcherRef = useRef(fetcher)
  useEffect(() => {
    fetcherRef.current = fetcher
  }, [fetcher])

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }

    const controller = new AbortController()
    let active = true

    setLoading(true)
    setError(null)

    fetcherRef
      .current(controller.signal)
      .then((result) => {
        if (!active) return
        setData(result)
        setError(null)
      })
      .catch((cause: unknown) => {
        if (!active || controller.signal.aborted) return
        const normalised =
          cause instanceof ApiError ? cause : new ApiError({
            code: 'unknown_error',
            message: getErrorMessage(cause),
            details: {},
            status: 0,
          })
        if (normalised.code === 'aborted') return
        setData(null)
        setError(normalised)
      })
      .finally(() => {
        if (!active) return
        setLoading(false)
        setSettled(true)
      })

    return () => {
      active = false
      controller.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, nonce, ...deps])

  const refetch = useCallback(() => setNonce((value) => value + 1), [])

  return { data, error, loading, settled, refetch }
}