import { AlertTriangle, Check, FlaskConical, Utensils } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { MenuIngredient } from '@/types'

export interface IngredientListProps {
  ingredients: MenuIngredient[]
  /** Show the ingredient source when present. */
  showSource?: boolean
  /** Show each ingredient's potential allergen, if declared. */
  showAllergens?: boolean
  /** Render a compact two-column layout inside cards. */
  dense?: boolean
  className?: string
}

/**
 * Presentational list of menu ingredients.
 *
 * Critically-allergenic ingredients are flagged with an explicit icon and a
 * bold label — never by colour alone.
 */
export function IngredientList({
  ingredients,
  showSource = false,
  showAllergens = true,
  dense = false,
  className,
}: IngredientListProps) {
  if (ingredients.length === 0) {
    return (
      <p className={cn('text-sm text-muted-text', className)}>
        Rincian bahan belum diisi di katalog.
      </p>
    )
  }

  return (
    <ul className={cn('divide-y divide-line', dense && 'text-sm', className)}>
      {ingredients.map((ingredient, index) => (
        <li
          key={`${ingredient.nama}-${index}`}
          className={cn('flex items-start gap-3', dense ? 'py-2' : 'py-3 first:pt-0')}
        >
          <span
            aria-hidden="true"
            className={cn(
              'mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md border',
              ingredient.is_critical_allergen
                ? 'border-blocked-line bg-blocked-soft text-blocked-strong'
                : 'border-forest-100 bg-forest-50 text-forest-600',
            )}
          >
            {ingredient.is_critical_allergen ? (
              <AlertTriangle className="size-3.5" />
            ) : (
              <FlaskConical className="size-3.5" />
            )}
          </span>

          <div className="min-w-0 flex-1">
            <p
              className={cn(
                'font-semibold text-ink',
                ingredient.is_critical_allergen && 'text-blocked-strong',
              )}
            >
              {ingredient.nama}
            </p>

            {ingredient.potensi_alergen && showAllergens && (
              <p className="mt-0.5 text-xs text-muted-text">
                <span className="font-bold">Potensi alergen:</span> {ingredient.potensi_alergen}
              </p>
            )}

            {ingredient.sumber && showSource && (
              <p className="mt-0.5 text-xs text-muted-text">Sumber: {ingredient.sumber}</p>
            )}

            {ingredient.is_critical_allergen && (
              <p className="mt-1 inline-flex items-center gap-1 text-xs font-bold text-blocked-strong">
                <AlertTriangle aria-hidden="true" className="size-3" />
                Alergen kritis — wajib dipisah
              </p>
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}

export interface SterileEquipmentListProps {
  equipment: string[]
  className?: string
}

/** Sterilised kitchen equipment required to prepare a menu. */
export function SterileEquipmentList({ equipment, className }: SterileEquipmentListProps) {
  if (equipment.length === 0) {
    return <p className={cn('text-sm text-muted-text', className)}>Belum ada catatan alat.</p>
  }

  return (
    <ul className={cn('grid gap-2 sm:grid-cols-2', className)}>
      {equipment.map((item) => (
        <li
          key={item}
          className="flex items-center gap-2 rounded-lg border border-line bg-surface-sunken px-3 py-2 text-sm text-ink-soft"
        >
          <Check aria-hidden="true" className="size-3.5 shrink-0 text-safe-strong" />
          <span className="min-w-0 truncate">{item}</span>
        </li>
      ))}
    </ul>
  )
}

export interface EquipmentIconProps {
  className?: string
}

/** Small reusable glyph for equipment sections. */
export function EquipmentIcon({ className }: EquipmentIconProps) {
  return <Utensils aria-hidden="true" className={cn('size-4', className)} />
}