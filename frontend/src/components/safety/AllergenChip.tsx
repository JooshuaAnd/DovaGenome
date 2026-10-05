import { Ban, ShieldCheck, TriangleAlert } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { RestrictionCategory } from '@/types'

import { SAFETY_TONE_CLASSES } from './tones'

/**
 * Categories that force steril protocols in the kitchen.
 * Mirrors `domain.SAFETY_CRITICAL_CATEGORIES`; preference does not.
 */
const CATEGORY_TONE: Record<RestrictionCategory, keyof typeof SAFETY_TONE_CLASSES> = {
  allergy: 'blocked',
  intolerance: 'caution',
  medical: 'blocked',
  preference: 'safe',
}

const CATEGORY_ICON: Record<RestrictionCategory, LucideIcon> = {
  allergy: Ban,
  intolerance: TriangleAlert,
  medical: ShieldCheck,
  preference: ShieldCheck,
}

export interface AllergenChipProps {
  label: string
  /** Drives both colour and icon; defaults to the critical `allergy` tone. */
  category?: RestrictionCategory
  /** Optional severity text from the passport record. */
  severity?: string
  size?: 'sm' | 'md'
  className?: string
}

/**
 * A single allergen or dietary restriction. Critical categories are visually
 * louder than preferences, matching the kitchen's handling rules.
 */
export function AllergenChip({
  label,
  category = 'allergy',
  severity,
  size = 'md',
  className,
}: AllergenChipProps) {
  const tone = SAFETY_TONE_CLASSES[CATEGORY_TONE[category]]
  const Icon = CATEGORY_ICON[category]

  return (
    <Badge
      variant="outline"
      className={cn(
        'gap-1.5 font-semibold',
        tone.badge,
        size === 'sm' && 'px-2 py-0 text-[0.6875rem]',
        className,
      )}
    >
      <Icon aria-hidden="true" className="size-3" />
      {label}
      {severity ? <span className="font-normal opacity-80">· {severity}</span> : null}
    </Badge>
  )
}

export interface AllergenChipListProps {
  labels: string[]
  category?: RestrictionCategory
  size?: 'sm' | 'md'
  className?: string
  /** Message shown when the list is empty. */
  emptyLabel?: string
}

/**
 * Row of allergen chips. An empty list is a positive statement ("no declared
 * restrictions") rather than a blank area, so absence is never ambiguous.
 */
export function AllergenChipList({
  labels,
  category = 'allergy',
  size = 'md',
  className,
  emptyLabel = 'Tidak ada pantangan',
}: AllergenChipListProps) {
  if (labels.length === 0) {
    return (
      <span
        className={cn(
          'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold',
          SAFETY_TONE_CLASSES.safe.badge,
          className,
        )}
      >
        <ShieldCheck aria-hidden="true" className="size-3" />
        {emptyLabel}
      </span>
    )
  }

  return (
    <div className={cn('flex flex-wrap gap-1.5', className)}>
      {labels.map((label) => (
        <AllergenChip key={label} label={label} category={category} size={size} />
      ))}
    </div>
  )
}