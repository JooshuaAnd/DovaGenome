import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError, getErrorMessage } from '@/services/http'

export interface UseAsyncState<TArgs extends unknown[], TResult> {
  run: (...args: TArgs) => Promise<TResult | undefined>
  data: TResult | null
  error: ApiError | null
  pending: boolean
  reset: () => void
  setData: (value: TResult | null) => void
}

/**
 * Imperative async runner for mutations (submit a form, advance an order).
 *
 * In contrast to `useApi`, nothing runs on mount — the caller decides when by
 * invoking `run()`. Aborted results are dropped instead of surfaced, and a new
 * `run()` supersedes any in-flight call.
 *
 * @example
 * const { run, pending, error } = useAsync((payload: LoginPayload) => authService.login(payload))
 */
export function useAsync<TArgs extends unknown[], TResult>(
  task: (...args: TArgs) => Promise<TResult>,
): UseAsyncState<TArgs, TResult> {
  const [data, setData] = useState<TResult | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [pending, setPending] = useState(false)

  const taskRef = useRef(task)
  useEffect(() => {
    taskRef.current = task
  }, [task])

  const activeRef = useRef(true)
  const runIdRef = useRef(0)

  useEffect(() => {
    activeRef.current = true
    return () => {
      activeRef.current = false
    }
  }, [])

  const run = useCallback(async (...args: TArgs) => {
    const runId = runIdRef.current + 1
    runIdRef.current = runId

    setPending(true)
    setError(null)

    try {
      const result = await taskRef.current(...args)
      if (!activeRef.current || runIdRef.current !== runId) return undefined
      setData(result)
      return result
    } catch (cause) {
      if (!activeRef.current || runIdRef.current !== runId) return undefined
      const normalised =
        cause instanceof ApiError
          ? cause
          : new ApiError({
              code: 'unknown_error',
              message: getErrorMessage(cause),
              details: {},
              status: 0,
            })
      if (normalised.code !== 'aborted') setError(normalised)
      return undefined
    } finally {
      if (activeRef.current && runIdRef.current === runId) setPending(false)
    }
  }, [])

  const reset = useCallback(() => {
    runIdRef.current += 1
    setData(null)
    setError(null)
    setPending(false)
  }, [])

  return { run, data, error, pending, reset, setData }
}