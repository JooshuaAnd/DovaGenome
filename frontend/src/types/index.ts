/**
 * Single re-export point for domain types.
 *
 * Components and pages import from `@/types` rather than reaching into
 * `@/services/types` directly, so the storage location can change without
 * touching call sites.
 */
export type * from '@/services/types'