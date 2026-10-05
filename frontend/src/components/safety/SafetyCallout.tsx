import { SAFETY_LEVELS } from '@/lib/constants'
import { cn } from '@/lib/utils'
import type { SafetyLevel } from '@/types'

import { SAFETY_TONE_CLASSES, SAFETY_TONE_ICON } from './tones'

export interface SafetyCalloutProps {
  level: SafetyLevel
  /** Bold headline. Defaults to the level's own label. */
  title?: string
  /** Plain-language explanation shown to the reader. */
  description?: string
  /** The required action, emphasised under the description. */
  guidance?: string
  /** Trailing element — usually a link or button. */
  action?: React.ReactNode
  /** Extra content rendered under the copy (conflict lists, ingredient rows). */
  children?: React.ReactNode
  className?: string
}

/**
 * The dominant safety message on a screen: a bordered panel with a bold
 * headline, an explanation, and the action the kitchen or customer must take.
 */
export function SafetyCallout({
  level,
  title,
  description,
  guidance,
  action,
  children,
  className,
}: SafetyCalloutProps) {
  const meta = SAFETY_LEVELS[level]
  const tone = SAFETY_TONE_CLASSES[meta.tone]
  const Icon = SAFETY_TONE_ICON[meta.tone]

  return (
    <div
      role={level === 'blocked' ? 'alert' : 'status'}
      className={cn(
        'rounded-xl border border-l-4 p-4 sm:p-5',
        tone.surface,
        tone.border,
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <Icon aria-hidden="true" className={cn('mt-0.5 size-5 shrink-0', tone.text)} />
        <div className="min-w-0 flex-1">
          <p className={cn('font-display text-base font-bold', tone.text)}>
            {title ?? meta.label}
          </p>
          <p className="mt-1 text-sm text-ink-soft">{description ?? meta.description}</p>
          {guidance && <p className={cn('mt-2 text-sm font-semibold', tone.text)}>{guidance}</p>}
          {children}
          {action && <div className="mt-3">{action}</div>}
        </div>
      </div>
    </div>
  )
}

export interface SafetySummaryProps {
  level: SafetyLevel
  headline?: string
  isRecommended?: boolean
  className?: string
}

/** Condensed variant for lists and cards where a full callout would dominate. */
export function SafetySummary({ level, headline, isRecommended, className }: SafetySummaryProps) {
  const meta = SAFETY_LEVELS[level]
  const tone = SAFETY_TONE_CLASSES[meta.tone]
  const Icon = SAFETY_TONE_ICON[meta.tone]

  return (
    <div className={cn('flex items-center gap-3 rounded-lg border p-3', tone.surface, className)}>
      <Icon aria-hidden="true" className={cn('size-4 shrink-0', tone.text)} />
      <div className="min-w-0 flex-1">
        <p className={cn('text-sm font-bold', tone.text)}>{headline || meta.label}</p>
        {typeof isRecommended === 'boolean' && (
          <p className="text-xs text-muted-text">
            {isRecommended ? 'Direkomendasikan' : 'Tidak direkomendasikan'}
          </p>
        )}
      </div>
    </div>
  )
}