import { useCallback, useMemo, useState } from 'react'

import { useApi } from '@/hooks/useApi'
import { catalogService } from '@/services/catalog'
import type { ServiceWeekQuery } from '@/services/catalog'
import type {
  DayOptions,
  DaySelection,
  DaySelectionInput,
  MenuOptionSafety,
  SafetyLevel,
  ServiceDay,
  ServiceWeek,
} from '@/types'

/** Worst (most restrictive) level across a set of options. */
export function worstLevel(levels: Array<SafetyLevel | undefined>): SafetyLevel | null {
  const present = levels.filter((level): level is SafetyLevel => Boolean(level))
  if (present.length === 0) return null
  if (present.includes('blocked')) return 'blocked'
  if (present.includes('caution')) return 'caution'
  return 'safe'
}

/** Same ranking, but `undefined` instead of `null` for callers keyed by service day. */
export function worstLevelOrUndefined(
  levels: Array<SafetyLevel | undefined>,
): SafetyLevel | undefined {
  return worstLevel(levels) ?? undefined
}

/**
 * Pair a day's options with their safety verdicts.
 *
 * The backend guarantees `day.safety[i]` describes `day.options[i]`, so the two
 * are zipped by index. `menu_id` is cross-checked anyway: if the pairing ever
 * drifts, an option falls back to "no verdict" rather than silently inheriting
 * another menu's status — a wrong "Aman" badge is the one failure this product
 * cannot ship.
 */
export function zipDayOptions(day: DayOptions): Array<{
  menu: DayOptions['options'][number]
  safety: MenuOptionSafety | null
}> {
  return day.options.map((menu, index) => {
    const candidate = day.safety[index]
    return { menu, safety: candidate?.menu_id === menu.menu_id ? candidate : null }
  })
}

export interface UseServiceWeekResult {
  week: ServiceWeek | null
  days: DayOptions[]
  loading: boolean
  error: ReturnType<typeof useApi<ServiceWeek>>['error']
  refetch: () => void
  /** Fast lookup for a single service day. */
  dayFor: (hari: ServiceDay) => DayOptions | undefined
  byMenuId: (menuId: string) => DayOptions | undefined
}

export interface UseServiceWeekOptions extends ServiceWeekQuery {
  enabled?: boolean
}

/**
 * Loads `/catalog/menus/week` and keeps it in sync with the query.
 *
 * The endpoint is public but personalises itself from the stored Dietary
 * Passport whenever a token is present, so no extra auth handling is needed here.
 */
export function useServiceWeek(options: UseServiceWeekOptions = {}): UseServiceWeekResult {
  const { enabled = true, package_code, days, selected_allergen_codes } = options

  const queryKey = JSON.stringify([package_code ?? '', days ?? [], selected_allergen_codes ?? []])

  const { data, loading, error, refetch } = useApi<ServiceWeek>(
    (signal) =>
      catalogService.getServiceWeek(
        {
          package_code,
          days,
          selected_allergen_codes,
        },
        signal,
      ),
    { enabled, deps: [queryKey] },
  )

  // Empty weeks must keep a stable identity or every downstream `useMemo`
  // recomputes on each render.
  const weekDays = useMemo(() => data?.days ?? [], [data])

  const index = useMemo(() => {
    const byDay = new Map<ServiceDay, DayOptions>()
    const byMenu = new Map<string, DayOptions>()
    for (const day of weekDays) {
      byDay.set(day.hari, day)
      for (const option of day.options) byMenu.set(option.menu_id, day)
    }
    return { byDay, byMenu }
  }, [weekDays])

  const dayFor = useCallback((hari: ServiceDay) => index.byDay.get(hari), [index])
  const byMenuId = useCallback((menuId: string) => index.byMenu.get(menuId), [index])

  return { week: data, days: weekDays, loading, error, refetch, dayFor, byMenuId }
}

/**
 * Which menu is chosen for each service day.
 *
 * A day with exactly one option is pre-selected — the customer never has to
 * confirm the obvious — while a day with several options starts unchosen so the
 * backend cannot silently pick on their behalf.
 */
export function useDailySelection(days: DayOptions[]) {
  const [choices, setChoices] = useState<Record<string, string>>({})

  const resolved = useMemo<DaySelection[]>(() => {
    const out: DaySelection[] = []
    for (const day of days) {
      if (day.is_past) continue
      const first = day.options[0]
      if (!first) continue

      const chosenId = choices[day.hari]
      const chosen =
        day.options.find((option) => option.menu_id === chosenId) ??
        (day.options.length === 1 ? first : null)
      if (!chosen) continue

      const verdict = zipDayOptions(day).find((pair) => pair.menu.menu_id === chosen.menu_id)
      out.push({
        hari: day.hari,
        menu_id: chosen.menu_id,
        service_date: day.service_date,
        date_label: day.date_label,
        nama_menu: chosen.nama_menu,
        deskripsi: chosen.deskripsi,
        allergen_labels: chosen.allergen_labels,
        alat_dapur_steril: chosen.alat_dapur_steril,
        level: verdict?.safety?.level,
        is_recommended: verdict?.safety?.is_recommended,
      })
    }
    return out
  }, [choices, days])

  const choose = useCallback((hari: ServiceDay, menuId: string) => {
    setChoices((current) => ({ ...current, [hari]: menuId }))
  }, [])

  const clear = useCallback(() => setChoices({}), [])

  const toInput = useCallback(
    (): DaySelectionInput[] => resolved.map(({ hari, menu_id }) => ({ hari, menu_id })),
    [resolved],
  )

  /** Service days that still need the customer to make a choice. */
  const undecided = useMemo(
    () =>
      days.filter(
        (day) => !day.is_past && day.options.length > 1 && !choices[day.hari],
      ),
    [choices, days],
  )

  return { choices, resolved, choose, clear, toInput, undecided }
}
