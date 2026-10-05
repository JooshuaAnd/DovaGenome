import type { LucideIcon } from 'lucide-react'
import { Inbox } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description?: string
  /** Primary recovery action — usually a "create" or "retry" button. */
  action?: ReactNode
  /** Secondary action rendered next to the primary one. */
  secondaryAction?: ReactNode
  /** `dashed` for "nothing here yet", `solid` for "nothing matches the filter". */
  variant?: 'dashed' | 'solid'
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

/**
 * The single way this product says "there is nothing here".
 *
 * Empty is a normal state in this domain (no orders today, no conflicts found),
 * so it gets a designed surface rather than a blank table.
 */
export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  secondaryAction,
  variant = 'dashed',
  size = 'md',
  className,
}: EmptyStateProps) {
  const iconSize = size === 'lg' ? 'size-12' : size === 'sm' ? 'size-8' : 'size-10'
  const iconBox = size === 'lg' ? 'p-5' : 'p-4'

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center rounded-xl text-center',
        variant === 'dashed'
          ? 'border border-dashed border-line-strong bg-sunken'
          : 'border border-line bg-surface',
        size === 'lg' ? 'gap-4 px-6 py-12' : 'gap-3 px-5 py-8',
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          'flex items-center justify-center rounded-xl border border-forest-100 bg-forest-50 text-forest-600',
          iconBox,
        )}
      >
        <Icon className={iconSize} />
      </span>

      <div className="space-y-1">
        <p className="font-display text-base font-bold text-ink">{title}</p>
        {description && (
          <p className="mx-auto max-w-prose text-sm text-muted-text">{description}</p>
        )}
      </div>

      {(action || secondaryAction) && (
        <div className="mt-1 flex flex-wrap items-center justify-center gap-2">
          {action}
          {secondaryAction}
        </div>
      )}
    </div>
  )
}