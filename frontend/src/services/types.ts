/**
 * Shared TypeScript types mirroring the FastAPI schemas in `backend/app/schemas/`.
 *
 * Field names are kept in the backend's snake_case so the DTOs can be consumed
 * without a translation layer. Enum-like values are modelled as string unions
 * (not TS `enum`) so they stay erasable and match `StrEnum` semantics exactly.
 */

/* ── Primitives ──────────────────────────────────────────────────────────── */

/** `app.models.enums.Role` */
export type Role = 'customer' | 'kitchen' | 'admin'

/** `app.models.enums.OrderStatus` */
export type OrderStatus = 'PENDING' | 'PREPARING' | 'READY' | 'COMPLETED' | 'CANCELLED'

/** `app.models.enums.PaymentStatus` */
export type PaymentStatus = 'UNPAID' | 'PENDING' | 'PAID' | 'REFUNDED'

/** `app.models.enums.RestrictionCategory` */
export type RestrictionCategory = 'allergy' | 'intolerance' | 'medical' | 'preference'

/** `app.models.enums.SafetyLevel` — the core domain concept of this product. */
export type SafetyLevel = 'safe' | 'caution' | 'blocked'

/** `app.core.domain.DAYS` — Sunday is not a service day. */
export type ServiceDay =
  | 'Senin'
  | 'Selasa'
  | 'Rabu'
  | 'Kamis'
  | 'Jumat'
  | 'Sabtu'

/** `app.core.domain.AVOIDED_TIME_OPTIONS` */
export type AvoidedTimeCode = 'avd_pagi' | 'avd_siang' | 'avd_sore' | 'avd_malam'

/* ── Auth / customer ─────────────────────────────────────────────────────── */

export interface Customer {
  customer_id: string
  username: string
  display_name: string
  phone: string
  role: Role
  status: string
  telegram_chat_id: number | null
  telegram_verified: boolean
  telegram_link_code: string
  telegram_deep_link: string
  created_at: string
  updated_at: string
}

export interface CustomerAdmin extends Customer {
  order_count: number
  active_order_count: number
  last_order_at: string | null
  passport: Passport | null
}

export interface Restriction {
  code: string
  label: string
  category: RestrictionCategory
  severity: string
  notes: string
}

export interface EmergencyContact {
  name: string
  phone: string
  relationship: string
}

export interface Passport {
  allergies: Restriction[]
  intolerances: Restriction[]
  medical: Restriction[]
  preferences: Restriction[]
  avoided_ingredients: string[]
  avoided_times: string[]
  medical_notes: string
  safety_notes: string
  emergency_notes: string
  emergency_contact: EmergencyContact
  critical_codes: string[]
  legacy_dietary_profile: string
  structured: boolean
  updated_at: string
}

export interface RestrictionIn {
  code: string
  label: string
  category?: RestrictionCategory
  severity?: string
  notes?: string
}

export interface PassportIn {
  allergies?: RestrictionIn[]
  intolerances?: RestrictionIn[]
  medical?: RestrictionIn[]
  preferences?: RestrictionIn[]
  avoided_ingredients?: string[]
  medical_notes?: string
  safety_notes?: string
  emergency_notes?: string
  emergency_contact?: EmergencyContact
  avoided_times?: string[]
}

export interface Token {
  access_token: string
  token_type: string
  expires_in: number
  customer: Customer
}

export interface LoginPayload {
  username: string
  password?: string | null
}

export interface RegisterPayload {
  username: string
  display_name?: string
  phone?: string
}

export interface StaffIn {
  username: string
  password: string
  display_name?: string
  role?: Role
}

export interface TelegramLinkResult {
  customer_id: string
  telegram_chat_id: number
  linked_at: string
}

/* ── Catalog ─────────────────────────────────────────────────────────────── */

export interface Allergen {
  code: string
  label: string
  risiko: string
  active: boolean
  category: string
}

export interface AllergenPatch {
  label?: string
  risiko?: string
  active?: boolean
  category?: string
}

export interface Package {
  code: string
  name: string
  days: ServiceDay[]
  description: string
  meal_count: number
  price: number | null
  active: boolean
}

export interface PackageIn {
  code: string
  name: string
  days: ServiceDay[]
  description?: string
  price?: number | null
  active?: boolean
}

export interface PackagePatch {
  name?: string
  days?: ServiceDay[]
  description?: string
  price?: number | null
  active?: boolean
}

export interface MenuIngredient {
  nama: string
  sumber: string
  potensi_alergen: string
  is_critical_allergen: boolean
}

/**
 * One menu option for one service day.
 *
 * A day can hold several options (`menu_id` is the document id, not `hari`),
 * which is what makes "pick one menu per day" possible. `package_codes` empty
 * means available to every package.
 */
export interface Menu {
  menu_id: string
  hari: ServiceDay
  nama_menu: string
  deskripsi: string
  bahan_detail: MenuIngredient[]
  alat_dapur_steril: string[]
  allergen_codes: string[]
  allergen_labels: string[]
  published: boolean
  package_codes: string[]
  option_index: number
}

export interface MenuIn {
  /** Omit to create a new option; supply to update an existing one. */
  menu_id?: string
  /** Filled from the URL path by the admin routes, so it may be omitted. */
  hari?: ServiceDay
  nama_menu: string
  deskripsi?: string
  bahan_detail?: MenuIngredient[]
  alat_dapur_steril: string[]
  published?: boolean
  package_codes?: string[]
  option_index?: number
}

export interface MenuPatch {
  nama_menu?: string
  deskripsi?: string
  bahan_detail?: MenuIngredient[]
  alat_dapur_steril?: string[]
  published?: boolean
  package_codes?: string[]
  option_index?: number
}

/** One service day: its calendar date plus every menu option offered that day. */
export interface DayOptions {
  hari: ServiceDay
  /** ISO `YYYY-MM-DD`, derived from the current service week in WIB. */
  service_date: string
  /** Pre-formatted Indonesian date, e.g. `5 Oktober 2026`. */
  date_label: string
  is_past: boolean
  options: Menu[]
  /** Positionally aligned with `options`: same index = same menu. */
  safety: MenuOptionSafety[]
}

/** Read model behind `/catalog/menus/week`, `/menu`, and the `/order` wizard. */
export interface ServiceWeek {
  /** ISO date of the Monday that anchors the shown week. */
  week_start: string
  days: DayOptions[]
  /** Restriction codes the `safety` verdicts in this response were computed with. */
  applied_codes: string[]
  has_passport: boolean
  is_live: boolean
}

export interface Catalog {
  packages: Package[]
  allergens: Allergen[]
  menus: Menu[]
  service_days: ServiceDay[]
  is_live: boolean
  source: string
}

export interface CatalogMeta {
  service_days: ServiceDay[]
  total_packages: number
  total_allergens: number
  total_menus: number
  is_live: boolean
  generated_at: string
}

/* ── Safety ──────────────────────────────────────────────────────────────── */

export interface SafetyConflict {
  allergen_code: string
  allergen_label: string
  category: string
  found_in: string[]
  ingredient_names: string[]
  explanation: string
}

export interface DaySafety {
  hari: ServiceDay
  /** The option actually chosen for this day; empty when nothing was chosen. */
  menu_id: string
  nama_menu: string
  deskripsi: string
  allergen_codes: string[]
  allergen_labels: string[]
  alat_dapur_steril: string[]
  level: SafetyLevel
  conflicts: SafetyConflict[]
  headline: string
  explanation: string
  guidance: string
  is_recommended: boolean
}

/**
 * Safety verdict for ONE menu option.
 *
 * Options of the same day can hold different allergens, so the verdict has to
 * live on the option — never on the day.
 */
export interface MenuOptionSafety {
  menu_id: string
  level: SafetyLevel
  headline: string
  explanation: string
  guidance: string
  is_recommended: boolean
  conflicts: SafetyConflict[]
}

export interface SafetyReport {
  level: SafetyLevel
  is_recommended: boolean
  headline: string
  explanation: string
  guidance: string
  menu_contains: string[]
  passport_excludes: string[]
  conflicts: SafetyConflict[]
  per_day: DaySafety[]
  critical_codes: string[]
  keywords_detected: string[]
}

/* ── Orders ──────────────────────────────────────────────────────────────── */

/** One service day paired with the menu option the customer picked for it. */
export interface DaySelection {
  hari: ServiceDay
  menu_id: string
  /** Resolved by the backend so the UI never has to re-join the catalog. */
  service_date?: string
  date_label?: string
  nama_menu?: string
  deskripsi?: string
  allergen_labels?: string[]
  alat_dapur_steril?: string[]
  level?: SafetyLevel
  is_recommended?: boolean
}

export interface Order {
  id: string
  order_id: string
  customer_id: string | null
  customer_name: string
  chat_id: number | null
  package_code: string
  subscription_type: string
  schedule_days: ServiceDay[]
  /** Exactly one menu per scheduled day; empty only on pre-v3 orders. */
  selections: DaySelection[]
  selected_allergens: string[]
  allergen_labels: string[]
  dietary_profile: string
  kitchen_notes: string
  customer_note: string
  delivery_address: string
  avoided_times: string[]
  meal_count: number
  status: OrderStatus
  status_meta: Record<string, unknown>
  next_status: OrderStatus | null
  next_action: string
  created_at: string
  updated_at: string
  elapsed_minutes: number
  sla_level: SlaLevel
  service_day: ServiceDay | null
  service_menu: string | null
  has_safety_flags: boolean
  schema_version: string
  invoice_number: string
  subtotal: number
  discount: number
  total: number
  payment_status: PaymentStatus
}

/** `app.core.domain` SLA buckets. */
export type SlaLevel = 'fresh' | 'soon' | 'late'

export interface OrderDetail extends Order {
  safety: SafetyReport | null
  passport: Passport | null
  timeline: Array<Record<string, unknown>>
  demo: boolean
}

export interface OrderCreatePayload {
  package_code: string
  selected_allergen_codes?: string[]
  customer_note?: string
  schedule_days?: ServiceDay[] | null
  /**
   * One entry per scheduled day. Omit to let the backend fall back to each day's
   * primary option — that is what Telegram and the older web form rely on.
   */
  selections?: DaySelectionInput[] | null
  delivery_address?: string
  apply_passport?: boolean
}

export interface DaySelectionInput {
  hari: ServiceDay
  menu_id: string
}

export interface OrderUpdatePayload {
  selected_allergen_codes?: string[] | null
  customer_note?: string | null
  delivery_address?: string | null
  schedule_days?: ServiceDay[] | null
  /** Replaces the stored selection; the safety check re-runs afterwards. */
  selections?: DaySelectionInput[] | null
}

export interface OrderTimelineEntry {
  status?: OrderStatus
  at?: string
  note?: string
  actor?: string
}

/* ── Invoice ─────────────────────────────────────────────────────────────── */

export interface InvoiceLine {
  label: string
  quantity: number
  unit_price: number
  amount: number
}

export interface Invoice {
  invoice_number: string
  order_id: string
  issued_at: string
  currency: string
  customer_name: string
  customer_contact: string
  package_name: string
  schedule_days: ServiceDay[]
  meal_count: number
  dietary_safety_summary: string
  dietary_safety_items: string[]
  lines: InvoiceLine[]
  subtotal: number
  discount: number
  total: number
  payment_status: PaymentStatus
  payment_reference: string
  demo: boolean
}

/* ── Kitchen ─────────────────────────────────────────────────────────────── */

export interface KitchenTicket extends Order {
  critical_allergens: string[]
  is_critical: boolean
  safety_banner: string
  equipment_notes: string[]
  menu_ingredients: string[]
}

export interface KitchenBoard {
  columns: Record<string, KitchenTicket[]>
  counts: Record<string, number>
  critical_count: number
  total_active: number
  fetched_at: string
  demo: boolean
}

export interface KitchenStatusPayload {
  status: OrderStatus
  note?: string
}

/* ── Admin ───────────────────────────────────────────────────────────────── */

export interface AdminKpi {
  key: string
  label: string
  value: number
  note: string
  tone: string
}

export interface AdminDashboard {
  generated_at: string
  active_orders: number
  pending_orders: number
  preparing_orders: number
  packed_orders: number
  delivering_orders: number
  completed_today: number
  cancelled_today: number
  safety_alerts: number
  average_wait_minutes: number
  oldest_ticket_minutes: number
  total_customers: number
  verified_customers: number
  orders_by_package: Array<Record<string, unknown>>
  orders_by_restriction: Array<Record<string, unknown>>
  orders_by_status: Array<Record<string, unknown>>
  weekly_trend: Array<Record<string, unknown>>
  demo: boolean
}

export interface AdminOrderRow {
  id: string
  order_id: string
  customer_name: string
  customer_id: string | null
  subscription_type: string
  status: OrderStatus
  allergen_labels: string[]
  created_at: string
  elapsed_minutes: number
  total: number
  payment_status: PaymentStatus
}

export interface AdminDaySchedule {
  hari: ServiceDay
  nama_menu: string
  deskripsi: string
  order_count: number
  orders: AdminOrderRow[]
  flagged_count: number
  alat_dapur_steril: string[]
  is_today: boolean
  /** How many options this day currently offers. */
  option_count: number
  option_names: string[]
  /** `order_id -> menu name actually chosen` for this day. */
  chosen_menus: Record<string, string>
}

export interface AdminSchedule {
  days: AdminDaySchedule[]
  is_service_day: boolean
  generated_at: string
}

export interface CollectionCount {
  name: string
  documents: number | null
  managed: boolean
}

export interface AdminSystem {
  astra_connected: boolean
  demo_mode: boolean
  credentials: Record<string, boolean>
  collections: CollectionCount[]
  foreign_collections: string[]
  telegram_bot_username: string
  telegram_deep_link_order: string
  langflow_configured: boolean
  version: string
}

/* ── AI ──────────────────────────────────────────────────────────────────── */

export interface AiConsultPayload {
  message: string
  session_id?: string
  context?: Record<string, unknown>
}

export interface AiConsultResult {
  reply: string
  session_id: string
  model: string
  flow_id: string
  latency_ms: number
  degraded: boolean
  message: string
}

export interface AiMenuSuggestionPayload {
  selected_allergen_codes?: string[]
  service_days?: ServiceDay[]
}

export interface AiMenuSuggestionResult {
  reply: string
  safety: SafetyReport
  suggested_days: ServiceDay[]
  avoided_days: ServiceDay[]
  session_id: string
  degraded: boolean
}

export interface FeedbackPayload {
  category?: string
  message: string
  email?: string
  order_id?: string
  rating?: number | null
}

export interface FeedbackResult {
  feedback_id: string
  received_at: string
  category: string
}

/* ── Health ──────────────────────────────────────────────────────────────── */

export interface HealthPayload {
  status: string
  version: string
  environment: string
  demo_mode: boolean
  astra_connected: boolean
  collections: Record<string, unknown>
  credentials: Record<string, boolean>
  telegram_bot_username: string
}

/* ── Error envelope ──────────────────────────────────────────────────────── */

/** One entry of `error.details.fields` produced by FastAPI's RequestValidationError. */
export interface ValidationFieldError {
  field: string
  message: string
  type: string
}

/** `app.schemas.common.ErrorBody` — the backend's error envelope. */
export interface ErrorBody {
  code: string
  message: string
  details?: {
    fields?: ValidationFieldError[]
    [key: string]: unknown
  }
}