import { Check, CircleDot, Info } from 'lucide-react'

import { IngredientList, SterileEquipmentList } from '@/components/safety/IngredientList'
import { SafetyBadge } from '@/components/safety/SafetyBadge'
import { SAFETY_TONE_CLASSES } from '@/components/safety/tones'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { SAFETY_LEVELS } from '@/lib/constants'
import { cn } from '@/lib/utils'
import type { DayOptions, Menu, MenuOptionSafety } from '@/types'

export interface MenuOptionCardProps {
  menu: Menu
  /** Per-option verdict. `null` means the backend sent no matching verdict. */
  safety: MenuOptionSafety | null
  /** Renders as a single-choice control in the order wizard. */
  selectable?: boolean
  selected?: boolean
  onSelect?: () => void
  /** Expanded by default; collapsed cards stay one tap away on small screens. */
  defaultOpen?: boolean
  className?: string
}

/**
 * One menu option for one service day, with its own safety verdict.
 *
 * A day can offer several options with different allergens, so the verdict is
 * rendered from this option's own data — never from a day-level summary. A
 * `blocked` option is shown in full and clearly marked rather than hidden, so the
 * customer can make an informed decision and the kitchen still has the record.
 */
export function MenuOptionCard({
  menu,
  safety,
  selectable = false,
  selected = false,
  onSelect,
  defaultOpen = true,
  className,
}: MenuOptionCardProps) {
  const level = safety?.level ?? 'safe'
  const tone = SAFETY_TONE_CLASSES[SAFETY_LEVELS[level].tone]

  const body = (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-display text-base font-bold text-ink">{menu.nama_menu}</h3>
            {menu.option_index > 0 && (
              <Badge variant="outline" className="font-semibold">
                Pilihan {menu.option_index + 1}
              </Badge>
            )}
          </div>
          {menu.deskripsi && (
            <p className="mt-1 text-sm text-muted-text">{menu.deskripsi}</p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {safety ? (
            <SafetyBadge level={level} />
          ) : (
            <Badge variant="outline" className="gap-1.5 font-semibold">
              <Info aria-hidden="true" className="size-3" />
              Status belum dihitung
            </Badge>
          )}
          {selectable && (
            <span
              aria-hidden="true"
              className={cn(
                'flex size-6 items-center justify-center rounded-full border-2 transition-colors',
                selected
                  ? 'border-forest-600 bg-forest-600 text-white'
                  : 'border-line bg-surface text-transparent',
              )}
            >
              {selected ? <Check className="size-3.5" /> : <CircleDot className="size-3" />}
            </span>
          )}
        </div>
      </div>

      {menu.allergen_labels.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="text-xs font-bold uppercase tracking-wide text-muted-text">
            Mengandung
          </span>
          {menu.allergen_labels.map((label) => (
            <Badge key={label} variant="outline" className="font-semibold">
              {label}
            </Badge>
          ))}
        </div>
      )}

      {safety && safety.explanation && (
        <p className={cn('mt-3 text-sm font-medium', tone.text)}>{safety.explanation}</p>
      )}

      {defaultOpen && (
        <div className="mt-4 grid gap-5 lg:grid-cols-2">
          <div>
            <h4 className="mb-1 text-xs font-bold uppercase tracking-wide text-muted-text">
              Rincian bahan
            </h4>
            <IngredientList ingredients={menu.bahan_detail} dense />
          </div>
          <div>
            <h4 className="mb-1 text-xs font-bold uppercase tracking-wide text-muted-text">
              Alat dapur steril
            </h4>
            <SterileEquipmentList equipment={menu.alat_dapur_steril} />
          </div>
        </div>
      )}
    </>
  )

  if (!selectable) {
    return (
      <Card className={cn('space-y-1', tone.surface, 'border-l-4', tone.border, className)}>
        {body}
      </Card>
    )
  }

  return (
    <Card
      className={cn(
        'space-y-1 transition-shadow',
        selected && 'ring-2 ring-forest-600 ring-offset-2 ring-offset-surface',
        tone.surface,
        'border-l-4',
        tone.border,
        className,
      )}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        className="w-full cursor-pointer text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-forest-600 focus-visible:ring-offset-2 rounded-lg"
      >
        {body}
      </button>
    </Card>
  )
}

export interface DayOptionsListProps {
  day: DayOptions
  selectable?: boolean
  selectedMenuId?: string
  onSelect?: (menuId: string) => void
  className?: string
}

/** All options of a single service day, each with its own verdict. */
export function DayOptionsList({
  day,
  selectable = false,
  selectedMenuId,
  onSelect,
  className,
}: DayOptionsListProps) {
  const pairs = day.options.map((menu, index) => {
    const candidate = day.safety[index]
    return { menu, safety: candidate?.menu_id === menu.menu_id ? candidate : null }
  })

  return (
    <div className={cn('space-y-4', className)}>
      {pairs.map(({ menu, safety }) => (
        <MenuOptionCard
          key={menu.menu_id}
          menu={menu}
          safety={safety}
          selectable={selectable}
          selected={selectable && menu.menu_id === selectedMenuId}
          onSelect={selectable ? () => onSelect?.(menu.menu_id) : undefined}
        />
      ))}
    </div>
  )
}
