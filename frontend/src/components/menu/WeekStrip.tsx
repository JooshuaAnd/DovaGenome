import { AlertTriangle, CalendarDays, Info } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { DAY_SHORT } from '@/lib/constants'
import { cn } from '@/lib/utils'
import type { DayOptions, SafetyLevel, ServiceDay } from '@/types'

export interface WeekStripProps {
  days: DayOptions[]
  active: ServiceDay | null
  onSelect: (hari: ServiceDay) => void
  /** `hari -> worst verdict across that day's options`. */
  levelByDay?: Partial<Record<ServiceDay, SafetyLevel>>
  className?: string
}

const DOT_TONE: Record<SafetyLevel, string> = {
  safe: 'bg-safe-strong',
  caution: 'bg-caution-strong',
  blocked: 'bg-blocked-strong',
}

/**
 * Monday-first strip of the current service week.
 *
 * Dates come from the backend (`service_date`/`date_label`) rather than being
 * recomputed here, so `/menu` and `/order` can never disagree about which date a
 * service day falls on. Past days are disabled instead of hidden — the customer
 * still sees the whole week and understands why those days cannot be chosen.
 */
export function WeekStrip({ days, active, onSelect, levelByDay, className }: WeekStripProps) {
  if (days.length === 0) return null

  return (
    <div
      role="tablist"
      aria-label="Hari layanan minggu ini"
      className={cn('grid grid-cols-3 gap-2 sm:grid-cols-6', className)}
    >
      {days.map((day) => {
        const isActive = day.hari === active
        const level = levelByDay?.[day.hari]
        const optionCount = day.options.length

        return (
          <Button
            key={day.hari}
            role="tab"
            type="button"
            variant="outline"
            aria-selected={isActive}
            disabled={day.is_past}
            onClick={() => onSelect(day.hari)}
            className={cn(
              'h-auto flex-col items-start gap-1 px-3 py-2.5 text-left',
              isActive && 'border-forest-600 bg-forest-50 ring-1 ring-forest-600',
              day.is_past && 'cursor-not-allowed opacity-50',
            )}
          >
            <span className="flex w-full items-center justify-between gap-1">
              <span className="text-xs font-bold uppercase tracking-wide text-muted-text">
                {DAY_SHORT[day.hari]}
              </span>
              {level && (
                <span
                  aria-hidden="true"
                  className={cn('size-2 shrink-0 rounded-full', DOT_TONE[level])}
                />
              )}
            </span>

            <span className="text-sm font-bold text-ink">
              {day.date_label ? day.date_label.split(' ')[0] : '—'}
            </span>

            <span className="flex items-center gap-1 text-[0.6875rem] text-muted-text">
              {day.is_past ? (
                ' Lewat'
              ) : (
                <>
                  {optionCount} menu
                  {optionCount > 1 && optionCount < 3 ? ' opsi' : ''}
                </>
              )}
            </span>
          </Button>
        )
      })}
    </div>
  )
}

export interface DayNoticesProps {
  day: DayOptions | undefined
  /** Restriction codes the verdicts were computed with. */
  appliedCodes?: string[]
  className?: string
}

/** Context lines above the option list: how many options, and against what. */
export function DayNotices({ day, appliedCodes = [], className }: DayNoticesProps) {
  if (!day) return null

  return (
    <div className={cn('flex flex-wrap items-center gap-2', className)}>
      <Badge variant="outline" className="gap-1.5 font-semibold">
        <CalendarDays aria-hidden="true" className="size-3" />
        {day.options.length} pilihan menu
      </Badge>

      {day.is_past && (
        <Badge variant="outline" className="gap-1.5 font-semibold">
          <Info aria-hidden="true" className="size-3" />
          Hari ini sudah lewat
        </Badge>
      )}

      {appliedCodes.length > 0 ? (
        <Badge variant="outline" className="gap-1.5 border-caution-line bg-caution-soft text-caution-strong">
          <AlertTriangle aria-hidden="true" className="size-3" />
          Diperiksa terhadap {appliedCodes.length} batasan tersimpan
        </Badge>
      ) : (
        <Badge variant="outline" className="gap-1.5 font-semibold">
          <Info aria-hidden="true" className="size-3" />
          Belum ada batasan tersimpan
        </Badge>
      )}
    </div>
  )
}

export interface WeekEmptyCardProps {
  hasDays: boolean
  className?: string
}

/** Shown when the week exists on paper but has no published menus. */
export function WeekEmptyCard({ hasDays, className }: WeekEmptyCardProps) {
  return (
    <Card className={cn('space-y-2 text-center', className)}>
      <CalendarDays aria-hidden="true" className="mx-auto size-6 text-muted-text" />
      <p className="font-display text-base font-bold text-ink">
        {hasDays ? 'Menu minggu ini belum tersedia' : 'Belum ada hari layanan'}
      </p>
      <p className="text-sm text-muted-text">
        {hasDays
          ? 'Dapur belum memublikasikan menu untuk minggu ini. Silakan cek lagi nanti.'
          : 'Belum ada menu yang dipublikasikan. Tim dapur sedang menyiapkan jadwal.'}
      </p>
    </Card>
  )
}
