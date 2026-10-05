import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

export interface PageHeaderProps {
  title: string
  description?: string
  /** Small uppercase label above the title. */
  eyebrow?: string
  /** Primary action, right-aligned on desktop and full-width on mobile. */
  actions?: ReactNode
  /** Content rendered under the title block, e.g. a safety strip. */
  children?: ReactNode
  /** Trailing content pinned to the far right (tabs, filters, view switch). */
  trailing?: ReactNode
  className?: string
}

/**
 * The standard intro block for every authenticated screen.
 *
 * Hierarchy is fixed on purpose: eyebrow → serif title → one-line description,
 * so no page invents its own spacing rhythm.
 */
export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
  children,
  trailing,
  className,
}: PageHeaderProps) {
  return (
    <header className={cn('space-y-4 pb-2', className)}>
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          {eyebrow && <p className="eyebrow">{eyebrow}</p>}
          <h1 className="mt-1 text-2xl leading-tight sm:text-[1.75rem]">{title}</h1>
          {description && (
            <p className="mt-1.5 max-w-prose text-sm text-muted-text">{description}</p>
          )}
        </div>

        {(actions || trailing) && (
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {trailing}
            {actions}
          </div>
        )}
      </div>

      {children}
    </header>
  )
}

export interface PageSectionProps {
  title?: string
  description?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
}

/** A titled block inside a page — used instead of nesting free-floating cards. */
export function PageSection({
  title,
  description,
  actions,
  children,
  className,
}: PageSectionProps) {
  return (
    <section className={cn('space-y-3', className)}>
      {(title || actions) && (
        <div className="flex items-end justify-between gap-4">
          <div>
            {title && <h2 className="text-lg">{title}</h2>}
            {description && <p className="mt-1 text-sm text-muted-text">{description}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  )
}