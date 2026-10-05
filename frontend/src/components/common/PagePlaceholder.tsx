import type { LucideIcon } from 'lucide-react'
import { Construction } from 'lucide-react'
import type { ReactNode } from 'react'

import { EmptyState } from '@/components/common/EmptyState'
import { PageHeader } from '@/components/layout/PageHeader'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

export interface PlaceholderCard {
  icon?: LucideIcon
  title: string
  description: string
}

export interface PagePlaceholderProps {
  title: string
  description: string
  eyebrow?: string
  /** What this page will contain once implemented. */
  upcoming?: string
  cards?: PlaceholderCard[]
  actions?: ReactNode
  className?: string
}

/**
 * Foundation-stage screen placeholder.
 *
 * Deliberately obvious: it states that the feature is not implemented yet and
 * shows empty containers instead of fabricated data, so nobody mistakes a mock
 * for the real thing.
 */
export function PagePlaceholder({
  title,
  description,
  eyebrow,
  upcoming,
  cards = [],
  actions,
  className,
}: PagePlaceholderProps) {
  return (
    <div className={className}>
      <PageHeader title={title} description={description} eyebrow={eyebrow} actions={actions} />

      <Alert className="mt-4 border-line-strong bg-surface">
        <Construction aria-hidden="true" />
        <AlertTitle>Belum diimplementasikan pada tahap fondasi.</AlertTitle>
        <AlertDescription>
          {upcoming ?? 'Rute, kerangka, dan komponennya sudah siap. Data nyata menyusul di tahap berikutnya.'}
        </AlertDescription>
      </Alert>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {cards.map((card) => (
          <EmptyState
            key={card.title}
            icon={card.icon}
            title={card.title}
            description={card.description}
            size="lg"
            className="h-full"
          />
        ))}
      </div>
    </div>
  )
}