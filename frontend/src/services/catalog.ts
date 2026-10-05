import { http } from './http'
import type {
  Allergen,
  AllergenPatch,
  Catalog,
  CatalogMeta,
  Menu,
  MenuIn,
  MenuPatch,
  Package,
  PackageIn,
  PackagePatch,
  SafetyReport,
  ServiceDay,
  ServiceWeek,
} from './types'

export interface SafetyPreviewQuery {
  /** Allergen codes to check against the menu. */
  selected_allergen_codes?: string[]
  /** Restrict the report to these service days; defaults to all of them. */
  days?: ServiceDay[]
}

export interface ServiceWeekQuery {
  /** Only show options available in this package. */
  package_code?: string
  /** Restrict to these service days; defaults to every service day. */
  days?: ServiceDay[]
  /** Extra codes to check alongside the signed-in customer's passport. */
  selected_allergen_codes?: string[]
}

export const catalogService = {
  getCatalog(options?: { includeInactive?: boolean; signal?: AbortSignal }) {
    return http.get<Catalog>('/catalog', {
      query: { include_inactive: options?.includeInactive ? true : undefined },
      signal: options?.signal,
    })
  },

  getMeta(signal?: AbortSignal) {
    return http.get<CatalogMeta>('/catalog/meta', { signal })
  },

  listPackages(signal?: AbortSignal) {
    return http.get<Package[]>('/catalog/packages', { signal })
  },

  listAllergens(signal?: AbortSignal) {
    return http.get<Allergen[]>('/catalog/allergens', { signal })
  },

  listMenus(signal?: AbortSignal) {
    return http.get<Menu[]>('/catalog/menus', { signal })
  },

  /**
   * The weekly read model: each service day with its date and every menu option,
   * each option carrying its own safety verdict.
   *
   * Public — no token required — but a signed-in customer's passport is applied
   * automatically, so the cards read "aman"/"mengandung X" out of the box.
   */
  getServiceWeek(query: ServiceWeekQuery = {}, signal?: AbortSignal) {
    return http.get<ServiceWeek>('/catalog/menus/week', {
      query: {
        package_code: query.package_code || undefined,
        days: query.days,
        selected_allergen_codes: query.selected_allergen_codes,
      },
      signal,
    })
  },

  /** Public, unauthenticated safety preview. */
  previewSafety(query: SafetyPreviewQuery = {}, signal?: AbortSignal) {
    return http.get<SafetyReport>('/catalog/safety', {
      auth: false,
      query: {
        selected_allergen_codes: query.selected_allergen_codes,
        days: query.days,
      },
      signal,
    })
  },

  /* ── Admin mutations ────────────────────────────────────────────────── */

  savePackage(code: string, payload: PackageIn) {
    return http.put<Package>(`/admin/packages/${encodeURIComponent(code)}`, payload)
  },

  patchPackage(code: string, patch: PackagePatch) {
    return http.patch<Package>(`/admin/packages/${encodeURIComponent(code)}`, patch)
  },

  saveAllergen(code: string, payload: Omit<AllergenPatch, 'label'> & { code: string; label: string }) {
    return http.put<Allergen>(`/admin/allergens/${encodeURIComponent(code)}`, payload)
  },

  patchAllergen(code: string, patch: AllergenPatch) {
    return http.patch<Allergen>(`/admin/allergens/${encodeURIComponent(code)}`, patch)
  },

  /** Upsert: `payload.menu_id` decides which option is written. */
  saveMenu(hari: ServiceDay, payload: MenuIn) {
    return http.put<Menu>(`/admin/menus/${encodeURIComponent(hari)}`, payload)
  },

  /** Add another option to the same day without touching the existing ones. */
  addMenuOption(hari: ServiceDay, payload: MenuIn) {
    return http.post<Menu>(`/admin/menus/${encodeURIComponent(hari)}`, payload)
  },

  /** Partial update of one option, addressed by `menu_id`. */
  patchMenu(menuId: string, patch: MenuPatch) {
    return http.patch<Menu>(`/admin/menus/${encodeURIComponent(menuId)}`, patch)
  },

  /**
   * Publish or withdraw an option.
   *
   * Withdrawing hides it from `/menu` without deleting it, so orders that already
   * reference the `menu_id` keep their history.
   */
  setMenuPublished(menuId: string, published: boolean) {
    const path = `/admin/menus/${encodeURIComponent(menuId)}/publish`
    return published ? http.post<Menu>(path) : http.delete<Menu>(path)
  },

  /** `kind` must be `packages` or `allergens` — menus are toggled via `saveMenu`. */
  toggleCatalogEntry(kind: 'packages' | 'allergens', code: string) {
    return http.post<{ code: string; active: boolean }>(
      `/admin/catalog/${kind}/${encodeURIComponent(code)}/toggle`,
    )
  },
}