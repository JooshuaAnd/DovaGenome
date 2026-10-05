/**
 * Formatting helpers.
 *
 * Every timestamp coming from the backend is ISO-8601 with an explicit offset;
 * display is always normalised to WIB (Asia/Jakarta, UTC+7) because that is the
 * only timezone this product operates in.
 */

const WIB = 'Asia/Jakarta'

const idrFormatter = new Intl.NumberFormat('id-ID', {
  style: 'currency',
  currency: 'IDR',
  maximumFractionDigits: 0,
})

const numberFormatter = new Intl.NumberFormat('id-ID')

/** Compact IDR for KPI tiles: `Rp1,2 jt`. */
export function formatIDRCompact(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const abs = Math.abs(value)
  if (abs >= 1_000_000) {
    const millions = value / 1_000_000
    return `Rp${millions.toLocaleString('id-ID', { maximumFractionDigits: 1 })} jt`
  }
  if (abs >= 1_000) {
    const thousands = value / 1_000
    return `Rp${thousands.toLocaleString('id-ID', { maximumFractionDigits: 0 })} rb`
  }
  return idrFormatter.format(value)
}

/** Full IDR: `Rp12.500`. */
export function formatIDR(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return idrFormatter.format(value)
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  return numberFormatter.format(value)
}

/** Minutes as a compact duration: `45 mnt`. */
export function formatMinutes(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return '—'
  return `${numberFormatter.format(minutes)} mnt`
}

/* ── Dates ───────────────────────────────────────────────────────────────── */

function toDate(value: Date | string | number | null | undefined): Date | null {
  if (value === null || value === undefined || value === '') return null
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

/** `Sen, 4 Mei 2026 · 11.30 WIB` */
export function formatDateWIB(value: Date | string | null | undefined): string {
  const date = toDate(value)
  if (!date) return '—'
  return new Intl.DateTimeFormat('id-ID', {
    timeZone: WIB,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(date)
}

/** `11.30 WIB` */
export function formatTimeWIB(value: Date | string | null | undefined): string {
  const date = toDate(value)
  if (!date) return '—'
  return `${new Intl.DateTimeFormat('id-ID', {
    timeZone: WIB,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)} WIB`
}

/** `4 Mei 2026, 11.30` — used on invoices where the `WIB` suffix repeats. */
export function formatDateTimeWIB(value: Date | string | null | undefined): string {
  const date = toDate(value)
  if (!date) return '—'
  return new Intl.DateTimeFormat('id-ID', {
    timeZone: WIB,
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date)
}

const RELATIVE_UNITS: Array<[Intl.RelativeTimeFormatUnit, number]> = [
  ['year', 31_536_000_000],
  ['month', 2_592_000_000],
  ['day', 86_400_000],
  ['hour', 3_600_000],
  ['minute', 60_000],
]

/** `5 menit lalu`, `2 jam lalu`, `baru saja`. */
export function formatRelativeTime(
  value: Date | string | null | undefined,
  now: Date = new Date(),
): string {
  const date = toDate(value)
  if (!date) return '—'

  const diff = date.getTime() - now.getTime()
  const abs = Math.abs(diff)
  if (abs < 45_000) return 'baru saja'

  const formatter = new Intl.RelativeTimeFormat('id-ID', { numeric: 'auto' })
  for (const [unit, ms] of RELATIVE_UNITS) {
    if (abs >= ms) return formatter.format(Math.round(diff / ms), unit)
  }
  return formatter.format(Math.round(diff / 60_000), 'minute')
}

/** Join truthy strings with a separator, dropping empties. */
export function joinTruthy(parts: Array<string | null | undefined>, separator = ' · '): string {
  return parts.filter((part): part is string => Boolean(part && part.trim())).join(separator)
}

/** Truncate long labels without cutting mid-word where possible. */
export function truncate(value: string, max: number): string {
  if (value.length <= max) return value
  return `${value.slice(0, Math.max(0, max - 1)).trimEnd()}…`
}