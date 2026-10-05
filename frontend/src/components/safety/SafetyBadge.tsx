import { Badge } from '@/components/ui/badge'
import { SAFETY_LEVELS } from '@/lib/constants'
import { cn } from '@/lib/utils'
import type { SafetyLevel } from '@/types'

import { SAFETY_TONE_CLASSES, SAFETY_TONE_ICON } from './tones'

export interface SafetyBadgeProps {
  level: SafetyLevel
  /** Override the default label from `SAFETY_LEVELS`. */
  label?: string
  /** Set false where horizontal space is very tight (table cells, chips). */
  showIcon?: boolean
  size?: 'sm' | 'md'
  className?: string
}

/**
 * Compact safety indicator. Pairs colour with an icon and a text label so the
 * meaning survives greyscale printing and colour-vision differences.
 */
export function SafetyBadge({
  level,
  label,
  showIcon = true,
  size = 'md',
  className,
}: SafetyBadgeProps) {
  const meta = SAFETY_LEVELS[level]
  const tone = SAFETY_TONE_CLASSES[meta.tone]
  const Icon = SAFETY_TONE_ICON[meta.tone]

  return (
    <Badge
      variant="outline"
      className={cn(
        'gap-1.5 font-bold',
        tone.badge,
        size === 'sm' && 'px-2 py-0 text-[0.6875rem]',
        className,
      )}
    >
      {showIcon && <Icon aria-hidden="true" className="size-3" />}
      {label ?? meta.label}
    </Badge>
  )
}