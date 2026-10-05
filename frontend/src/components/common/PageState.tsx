import { AlertOctagon, Loader2, ShieldAlert } from 'lucide-react'
import type { ReactNode } from 'react'

import { EmptyState } from '@/components/common/EmptyState'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError, getErrorMessage } from '@/services/http'
import { cn } from '@/lib/utils'

export interface PageStateProps {
  /** First load in progress. */
  loading?: boolean
  /** Normalised error from `useApi` / `useAsync`. */
  error?: ApiError | Error | null
  /** Skeleton count while `loading` is true. */
  skeletonRows?: number
  /** Rendered instead of the skeleton/error shell. */
  children?: ReactNode
  onRetry?: () => void
  className?: string
}

/**
 * The loading / error / empty shell every data-backed screen composes.
 *
 * Error copy comes from `ApiError.message`, which the HTTP client already
 * unwrapped from the backend envelope — raw JSON never reaches the user.
 */
export function PageState({
  loading = false,
  error = null,
  skeletonRows = 3,
  children,
  onRetry,
  className,
}: PageStateProps) {
  if (loading) return <PageStateSkeleton rows={skeletonRows} className={className} />
  if (error) return <PageStateError error={error} onRetry={onRetry} className={className} />
  return <>{children}</>
}

export interface PageStateSkeletonProps {
  rows?: number
  className?: string
}

/** Neutral placeholder blocks — no fake numbers or fake records. */
export function PageStateSkeleton({ rows = 3, className }: PageStateSkeletonProps) {
  return (
    <div className={cn('space-y-3', className)} aria-busy="true" aria-live="polite">
      <span className="sr-only">Memuat data…</span>
      {Array.from({ length: Math.max(1, rows) }).map((_, index) => (
        <div key={index} className="surface-card flex items-center gap-4 p-4">
          <Skeleton className="size-10 shrink-0 rounded-lg" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3.5 w-1/3" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="hidden h-6 w-20 rounded-full sm:block" />
        </div>
      ))}
    </div>
  )
}

export interface PageStateErrorProps {
  error: ApiError | Error
  onRetry?: () => void
  className?: string
}

/** Error panel with the server's own message and optional field-level detail. */
export function PageStateError({ error, onRetry, className }: PageStateErrorProps) {
  const apiError = error instanceof ApiError ? error : null
  const isAuthIssue = apiError?.status === 401
  const isForbidden = apiError?.status === 403
  const fields = apiError?.fieldMessages ?? []

  const title = isAuthIssue
    ? 'Sesi berakhir'
    : isForbidden
      ? 'Akses dibatasi'
      : 'Data tidak bisa dimuat'

  return (
    <Alert variant="destructive" className={cn('items-start', className)}>
      <ShieldAlert aria-hidden="true" />
      <AlertTitle className="flex items-center gap-2">
        {isAuthIssue || isForbidden ? <AlertOctagon className="size-4" /> : null}
        {title}
      </AlertTitle>
      <AlertDescription className="space-y-3">
        <p>{getErrorMessage(error, 'Terjadi kesalahan yang tidak terduga.')}</p>

        {fields.length > 0 && (
          <ul className="list-inside list-disc space-y-0.5 text-xs">
            {fields.map((field) => (
              <li key={field}>{field}</li>
            ))}
          </ul>
        )}

        {apiError && (
          <p className="font-mono text-[0.6875rem] opacity-70">
            {apiError.code} · HTTP {apiError.status || 'n/a'}
          </p>
        )}

        {onRetry && (
          <Button size="sm" variant="outline" onClick={onRetry} className="mt-1">
            <Loader2 aria-hidden="true" className="size-3.5" />
            Coba lagi
          </Button>
        )}
      </AlertDescription>
    </Alert>
  )
}

export interface PageStateEmptyProps {
  title: string
  description?: string
  action?: ReactNode
  icon?: React.ComponentProps<typeof EmptyState>['icon']
  className?: string
}

/** Convenience wrapper so pages can express the three states uniformly. */
export function PageStateEmpty({
  title,
  description,
  action,
  icon,
  className,
}: PageStateEmptyProps) {
  return (
    <EmptyState
      title={title}
      description={description}
      action={action}
      icon={icon}
      className={className}
    />
  )
}