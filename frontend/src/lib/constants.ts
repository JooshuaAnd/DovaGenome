/**
 * Domain constants mirrored from the backend.
 *
 * Source of truth: `backend/app/core/domain.py` and `backend/app/models/enums.py`.
 * Keep both sides in sync — `lib/constants.ts` only adds presentation metadata
 * (labels, tones) on top of the backend values.
 */

import type {
  AvoidedTimeCode,
  OrderStatus,
  Package,
  PaymentStatus,
  RestrictionCategory,
  SafetyLevel,
  ServiceDay,
  SlaLevel,
} from '@/types'

export const BRAND = {
  name: 'DovaGenome',
  sub: 'Precision Catering',
  tagline: 'Makan siang mingguan yang aman, steril, dan bisa dilacak sampai ke wajan.',
} as const

/* ── Service days ────────────────────────────────────────────────────────── */

/** `domain.DAYS` — Sunday is not a service day. */
export const DAYS: readonly ServiceDay[] = [
  'Senin',
  'Selasa',
  'Rabu',
  'Kamis',
  'Jumat',
  'Sabtu',
] as const

export const DAY_SHORT: Record<ServiceDay, string> = {
  Senin: 'Sen',
  Selasa: 'Sel',
  Rabu: 'Rab',
  Kamis: 'Kam',
  Jumat: 'Jum',
  Sabtu: 'Sab',
}

/** Monday-first index, used to place a day in a weekly strip. */
export const DAY_INDEX: Record<ServiceDay, number> = {
  Senin: 0,
  Selasa: 1,
  Rabu: 2,
  Kamis: 3,
  Jumat: 4,
  Sabtu: 5,
}

/** Indonesian weekday name for an arbitrary date, or `null` on Sunday. */
export function serviceDayForDate(date: Date): ServiceDay | null {
  const names: Array<ServiceDay | 'Minggu'> = [
    'Senin',
    'Selasa',
    'Rabu',
    'Kamis',
    'Jumat',
    'Sabtu',
    'Minggu',
  ]
  const name = names[date.getDay()]
  return name === 'Minggu' ? null : name
}

/* ── Meal types ──────────────────────────────────────────────────────────── */

/**
 * Catering service slots.
 *
 * NOTE: the backend exposes `meal_count` on a package but no per-meal breakdown
 * yet, so these labels are UI-only scaffolding for the order builder.
 */
export const MEAL_TYPES = [
  { value: 'sarapan', label: 'Sarapan', note: 'Aman untuk shift pagi' },
  { value: 'siang', label: 'Makan Siang', note: 'Slot paling umum' },
  { value: 'makan_malam', label: 'Makan Malam', note: 'Untuk tim yang lembur' },
] as const

export type MealType = (typeof MEAL_TYPES)[number]['value']

/** `domain.AVOIDED_TIME_OPTIONS` — delivery windows a customer can skip. */
export const AVOIDED_TIME_OPTIONS: Record<AvoidedTimeCode, string> = {
  avd_pagi: 'Pagi (07.00–09.00)',
  avd_siang: 'Siang (11.00–13.00)',
  avd_sore: 'Sore (15.00–17.00)',
  avd_malam: 'Malam (18.00–20.00)',
}

/* ── Safety levels ───────────────────────────────────────────────────────── */

export type SafetyTone = 'safe' | 'caution' | 'blocked'

export interface SafetyLevelMeta {
  level: SafetyLevel
  label: string
  description: string
  tone: SafetyTone
}

export const SAFETY_LEVELS: Record<SafetyLevel, SafetyLevelMeta> = {
  safe: {
    level: 'safe',
    label: 'Aman',
    description: 'Tidak ada tabrakan dengan batasan yang tercatat.',
    tone: 'safe',
  },
  caution: {
    level: 'caution',
    label: 'Perlu Perhatian',
    description: 'Ada batasan ringan atau preferensi yang perlu dikonfirmasi.',
    tone: 'caution',
  },
  blocked: {
    level: 'blocked',
    label: 'Diblokir',
    description: 'Ada allergen kritis yang dikecualikan passport pada menu ini.',
    tone: 'blocked',
  },
}

export const SAFETY_LEVEL_LIST: SafetyLevelMeta[] = [
  SAFETY_LEVELS.safe,
  SAFETY_LEVELS.caution,
  SAFETY_LEVELS.blocked,
]

/** Categories that force steril protocols in the kitchen; preference does not. */
export const SAFETY_CRITICAL_CATEGORIES: RestrictionCategory[] = [
  'allergy',
  'intolerance',
  'medical',
]

/** `domain.CATEGORY_LABELS` */
export const CATEGORY_LABELS: Record<RestrictionCategory, string> = {
  allergy: 'Alergi',
  intolerance: 'Intoleransi',
  medical: 'Restribusi Medis',
  preference: 'Preferensi',
}

/** `domain.AVOIDED_TIME_OPTIONS` */
export const CATEGORY_ORDER: RestrictionCategory[] = [
  'allergy',
  'intolerance',
  'medical',
  'preference',
]

/* ── Order status ────────────────────────────────────────────────────────── */

export type OrderTone = SafetyTone | 'info' | 'neutral'

export interface OrderStatusMeta {
  status: OrderStatus
  label: string
  short: string
  tone: OrderTone
  next: OrderStatus | null
  action: string
  step: number
}

/** `domain.STATUS_META` — labels and next-step copy verbatim. */
export const ORDER_STATUSES: Record<OrderStatus, OrderStatusMeta> = {
  PENDING: {
    status: 'PENDING',
    label: 'Menunggu Dimasak',
    short: 'Menunggu',
    tone: 'caution',
    next: 'PREPARING',
    action: 'Mulai Masak',
    step: 1,
  },
  PREPARING: {
    status: 'PREPARING',
    label: 'Sedang Dimasak',
    short: 'Dimasak',
    tone: 'info',
    next: 'READY',
    action: 'Tandai Siap Kirim',
    step: 2,
  },
  READY: {
    status: 'READY',
    label: 'Siap Dikirim',
    short: 'Siap Kirim',
    tone: 'safe',
    next: 'COMPLETED',
    action: 'Selesai & Kirim',
    step: 3,
  },
  COMPLETED: {
    status: 'COMPLETED',
    label: 'Sudah Diantar',
    short: 'Selesai',
    tone: 'neutral',
    next: null,
    action: '',
    step: 4,
  },
  CANCELLED: {
    status: 'CANCELLED',
    label: 'Dibatalkan',
    short: 'Dibatalkan',
    tone: 'blocked',
    next: null,
    action: '',
    step: 0,
  },
}

/** Statuses shown on the kitchen board; terminal ones are excluded. */
export const ACTIVE_STATUSES: OrderStatus[] = ['PENDING', 'PREPARING', 'READY']

export const SLA_LEVELS: Record<SlaLevel, { label: string; tone: OrderTone }> = {
  fresh: { label: 'Baru masuk', tone: 'neutral' },
  soon: { label: 'Mendekati SLA', tone: 'caution' },
  late: { label: 'Lewat SLA', tone: 'blocked' },
}

export const PAYMENT_STATUSES: Record<PaymentStatus, { label: string; tone: OrderTone }> = {
  UNPAID: { label: 'Belum Dibayar', tone: 'caution' },
  PENDING: { label: 'Menunggu Verifikasi', tone: 'info' },
  PAID: { label: 'Lunas', tone: 'safe' },
  REFUNDED: { label: 'Dikembalikan', tone: 'neutral' },
}

/* ── Packages ────────────────────────────────────────────────────────────── */

/** Seeded package codes (`seed_catering_data.py`). The API stays source-agnostic. */
export const PACKAGE_CODES = ['pkg_full', 'pkg_workday', 'pkg_3hari'] as const
export type PackageCode = (typeof PACKAGE_CODES)[number]

/* ── Misc ────────────────────────────────────────────────────────────────── */

export const DEFAULT_PAGE_SIZE = 50

/** Terms of the fulfilment flow, shown as a stepper on order detail. */
export const FULFILMENT_STEPS = [
  { step: 1, title: 'Pesanan masuk', description: 'Tiket dari bot Telegram' },
  { step: 2, title: 'Dimasak', description: 'Dapur menerapkan protokol steril' },
  { step: 3, title: 'Dikemas', description: 'Segel anti-kontaminasi' },
  { step: 4, title: 'Diantar', description: 'Selesai & billed' },
] as const

/** Type-only helper used by package pickers. */
export type PackageLike = Pick<Package, 'code' | 'name' | 'days' | 'price'>