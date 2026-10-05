import { ShieldAlert, ShieldCheck, ShieldQuestion } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import type { OrderTone, SafetyTone } from '@/lib/constants'

/**
 * One source of truth for safety colour semantics.
 *
 * Every safety indicator in the product resolves its classes from here, so a
 * "blocked" state can never render amber in one corner of the app and rose in
 * another. Colour is always paired with an icon and a text label — the kitchen
 * screens are read at a distance and in bright light.
 */

export interface ToneClasses {
  /** Badge / chip surface. */
  badge: string
  /** Foreground text on the soft surface. */
  text: string
  /** Panel background + border. */
  surface: string
  /** Left accent border for callouts. */
  border: string
}

export const SAFETY_TONE_CLASSES: Record<SafetyTone, ToneClasses> = {
  safe: {
    badge: 'border-safe-line bg-safe-soft text-safe-strong',
    text: 'text-safe-strong',
    surface: 'bg-safe-soft border-safe-line',
    border: 'border-l-safe',
  },
  caution: {
    badge: 'border-caution-line bg-caution-soft text-caution-strong',
    text: 'text-caution-strong',
    surface: 'bg-caution-soft border-caution-line',
    border: 'border-l-caution',
  },
  blocked: {
    badge: 'border-blocked-line bg-blocked-soft text-blocked-strong',
    text: 'text-blocked-strong',
    surface: 'bg-blocked-soft border-blocked-line',
    border: 'border-l-blocked',
  },
}

/** Order status reuses the safety tones and adds two neutral informational hues. */
export const ORDER_TONE_CLASSES: Record<OrderTone, string> = {
  safe: SAFETY_TONE_CLASSES.safe.badge,
  caution: SAFETY_TONE_CLASSES.caution.badge,
  blocked: SAFETY_TONE_CLASSES.blocked.badge,
  info: 'border-status-info-line bg-status-info-soft text-status-info',
  neutral: 'border-status-neutral-line bg-status-neutral-soft text-status-neutral',
}

/** Panel (non-badge) variants for order status. */
export const ORDER_TONE_SURFACE_CLASSES: Record<OrderTone, string> = {
  safe: SAFETY_TONE_CLASSES.safe.surface,
  caution: SAFETY_TONE_CLASSES.caution.surface,
  blocked: SAFETY_TONE_CLASSES.blocked.surface,
  info: 'bg-status-info-soft border-status-info-line',
  neutral: 'bg-status-neutral-soft border-status-neutral-line',
}

export const SAFETY_TONE_ICON: Record<SafetyTone, LucideIcon> = {
  safe: ShieldCheck,
  caution: ShieldQuestion,
  blocked: ShieldAlert,
}

export const ORDER_TONE_ICON: Record<OrderTone, LucideIcon> = {
  ...SAFETY_TONE_ICON,
  info: ShieldQuestion,
  neutral: ShieldQuestion,
}