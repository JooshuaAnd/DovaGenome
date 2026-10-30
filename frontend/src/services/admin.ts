import { http } from './http'
import type {
  AdminDashboard,
  AdminKpi,
  AdminSchedule,
  AdminSystem,
  CustomerAdmin,
  Invoice,
  PaymentStatus,
  ServiceWeek,
} from './types'

export interface RecipeReview {
  recipe_version_id: string
  menu_id: string
  nama_menu: string
  version_no: number
  status: string
  source: string
  source_ref: string
  cross_contact_risk: string
  verified_by: string | null
  verified_at: string | null
  notes: string
  component_count: number
  unresolved_component_count: number
}

export interface RecipeComponent {
  recipe_component_id: number
  recipe_version_id: string
  ingredient_id: string
  ingredient_name: string | null
  ingredient_status: string | null
  allergen_codes: string[] | null
  quantity: number | null
  unit: string
  preparation: string
  verification_status: string
  source: string
  sort_order: number
}

export interface RecipeIngredientOption {
  ingredient_id: string
  name: string
  default_unit: string
  verification_status: string
  allergen_codes: string[] | null
}

export interface RecipeNutritionPreview {
  status: 'VERIFIED' | 'ESTIMATED' | 'UNAVAILABLE' | string
  calories_kcal: number | null
  protein_g: number | null
  carbs_g: number | null
  fat_g: number | null
  macro_energy_pct: Record<string, number | null>
  basis: string
  warnings: string[]
}

export interface RecipeAiDraftComponent {
  ingredient_name: string
  quantity: number
  unit: string
  quantity_min: number | null
  quantity_max: number | null
  preparation: string
  allergen_codes: string[]
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  rationale: string
}

export interface RecipeAiDraftSource {
  title: string
  url: string
  excerpt: string
}

export interface RecipeNutritionDraft {
  calories_kcal: number | null
  protein_g: number | null
  carbs_g: number | null
  fat_g: number | null
  protein_energy_pct: number | null
  carbs_energy_pct: number | null
  fat_energy_pct: number | null
  basis: string
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  warnings: string[]
}

export interface RecipeAiDraft {
  dish_name: string
  summary: string
  components: RecipeAiDraftComponent[]
  sources: RecipeAiDraftSource[]
  safety_notes: string[]
  overall_confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  nutrition: RecipeNutritionDraft
  generated_by: string
}

export interface RecipeIntakeResult {
  menu_id: string
  menu_name: string
  service_day: string
  published: boolean
  menu_status: string
  recipe_version_id: string
  recipe_status: string
  source_name: string
  ai_draft: RecipeAiDraft
  nutrition_from_composition: RecipeNutritionPreview
}

/** Every call in this service requires the admin role. */
export const adminService = {
  getAdminServiceWeek(signal?: AbortSignal) {
    return http.get<ServiceWeek>('/admin/menus/week', { signal })
  },

  intakeRecipe(file: File | null, serviceDay: string, menuName = '', context = '', recipeNote = '') {
    const form = new FormData()
    if (file) form.append('file', file)
    form.append('hari', serviceDay)
    form.append('menu_name', menuName)
    form.append('context', context)
    form.append('recipe_note', recipeNote)
    return http.post<RecipeIntakeResult>('/admin/recipe-intake/import-draft', form)
  },

  getRecipeReviews(signal?: AbortSignal) {
    return http.get<RecipeReview[]>('/admin/recipe-reviews', { signal })
  },

  getRecipeComponents(recipeVersionId: string, signal?: AbortSignal) {
    return http.get<RecipeComponent[]>(
      `/admin/recipe-versions/${encodeURIComponent(recipeVersionId)}/components`,
      { signal },
    )
  },

  getRecipeIngredients(search = '', signal?: AbortSignal) {
    return http.get<RecipeIngredientOption[]>('/admin/ingredients', { signal, query: { search, limit: 500 } })
  },

  getRecipeNutritionPreview(recipeVersionId: string, signal?: AbortSignal) {
    return http.get<RecipeNutritionPreview>(
      `/admin/recipe-versions/${encodeURIComponent(recipeVersionId)}/nutrition-preview`,
      { signal },
    )
  },

  replaceRecipeComponents(
    recipeVersionId: string,
    components: Array<{
      ingredient_id: string
      quantity: number
      unit: string
      preparation?: string
      sort_order: number
    }>,
  ) {
    return http.put<RecipeComponent[]>(
      `/admin/recipe-versions/${encodeURIComponent(recipeVersionId)}/components`,
      { components },
    )
  },

  generateRecipeAiDraft(
    recipeVersionId: string,
    payload: { image_data_url?: string; source_url?: string; context?: string },
  ) {
    return http.post<RecipeAiDraft>(
      `/admin/recipe-versions/${encodeURIComponent(recipeVersionId)}/ai-draft`,
      payload,
    )
  },

  importRecipeDocument(recipeVersionId: string, file: File, context = '') {
    const form = new FormData()
    form.append('file', file)
    form.append('context', context)
    return http.post<RecipeAiDraft>(
      `/admin/recipe-versions/${encodeURIComponent(recipeVersionId)}/import-draft`,
      form,
    )
  },

  applyRecipeAiDraft(recipeVersionId: string, draft: RecipeAiDraft) {
    return http.post<RecipeComponent[]>(
      `/admin/recipe-versions/${encodeURIComponent(recipeVersionId)}/apply-ai-draft`,
      {
        dish_name: draft.dish_name,
        summary: draft.summary,
        components: draft.components,
        sources: draft.sources,
        safety_notes: draft.safety_notes,
        overall_confidence: draft.overall_confidence,
        nutrition: draft.nutrition,
      },
    )
  },

  verifyIngredient(ingredientId: string, allergenCodes: string[]) {
    return http.patch<Record<string, unknown>>(
      `/admin/ingredients/${encodeURIComponent(ingredientId)}/verify`,
      { allergen_codes: allergenCodes, evidence: { source: 'admin_recipe_review' } },
    )
  },

  verifyIngredientsBatch(ingredients: Array<{ ingredient_id: string; allergen_codes: string[] }>) {
    return http.post<Record<string, unknown>[]>('/admin/ingredients/verify-batch', { ingredients })
  },

  verifyRecipe(recipeVersionId: string, crossContactRisk: 'LOW' | 'MEDIUM', notes: string) {
    return http.post<Record<string, unknown>>(
      `/admin/recipe-versions/${encodeURIComponent(recipeVersionId)}/verify`,
      { cross_contact_risk: crossContactRisk, notes },
    )
  },

  dashboard(signal?: AbortSignal) {
    return http.get<AdminDashboard>('/admin/dashboard', { signal })
  },

  kpis(signal?: AbortSignal) {
    return http.get<AdminKpi[]>('/admin/kpis', { signal })
  },

  schedule(signal?: AbortSignal) {
    return http.get<AdminSchedule>('/admin/schedule', { signal })
  },

  listCustomers(signal?: AbortSignal) {
    return http.get<CustomerAdmin[]>('/admin/customers', { signal })
  },

  system(signal?: AbortSignal) {
    return http.get<AdminSystem>('/admin/system', { signal })
  },

  /**
   * Manual payment marking. The backend takes query params, not a JSON body
   * (`app/api/routers/admin.py` `set_payment`).
   */
  setPayment(orderId: string, status: PaymentStatus, reference = '') {
    return http.post<Invoice>(`/admin/orders/${encodeURIComponent(orderId)}/payment`, undefined, {
      query: { status, reference },
    })
  },

  getPosKds(signal?: AbortSignal) {
    return http.get<{
      metrics: { new_orders: number; total_orders: number; waiting_list: number }
      orders: any[]
      kitchen_orders: any[]
    }>('/admin/pos-kds', { signal })
  },

  advanceOrder(orderId: string, targetStatus: string) {
    return http.post<{ status: string; order_id: string; new_status: string }>(
      `/admin/orders/${encodeURIComponent(orderId)}/advance`,
      undefined,
      { query: { target_status: targetStatus } }
    )
  },

  getPopularDishes(signal?: AbortSignal) {
    return http.get<
      Array<{ menu_id: string; nama_menu: string; hari: string; order_count: number }>
    >('/admin/popular-dishes', { signal })
  },

  getInventoryAlerts(signal?: AbortSignal) {
    return http.get<
      Array<{
        id: number
        ingredient_name: string
        current_stock: number
        min_stock: number
        unit: string
        status: string
        updated_at: string
      }>
    >('/admin/inventory-alerts', { signal })
  },

  getNotifications(signal?: AbortSignal) {
    return http.get<any[]>('/admin/notifications', { signal })
  },

  sendNotification(params: {
    recipient_type: string
    recipient_name: string
    recipient_chat_id: string
    message: string
  }) {
    return http.post<{ status: string; channel: string; recipient: string }>(
      '/admin/notifications/send',
      undefined,
      { query: params }
    )
  },

  getMarketingCampaigns(signal?: AbortSignal) {
    return http.get<Array<{
      campaign_id: string
      campaign_type: string
      status: string
      channel: string
      data_mode: string
      source: string
      calculation_version: string
      source_calculation_version: string
      source_as_of?: string | null
      data_age_days?: number | null
      audience_count: number
      excluded_count: number
      control_group_percent: number
      rate_limit_per_minute: number
      created_by: string
      approved_by?: string | null
      created_at: string
      approved_at?: string | null
      queued_at?: string | null
    }>>('/admin/marketing/campaigns', { signal })
  },

  createWinbackCampaignDraft(
    channel: 'whatsapp' | 'telegram',
    maxRecipients = 100,
    controlGroupPercent = 0,
    rateLimitPerMinute = 20,
  ) {
    return http.post<Record<string, unknown>>('/admin/marketing/campaigns/winback/draft', {
      channel,
      max_recipients: maxRecipients,
      control_group_percent: controlGroupPercent,
      rate_limit_per_minute: rateLimitPerMinute,
    })
  },

  approveMarketingCampaign(campaignId: string) {
    return http.post<Record<string, unknown>>(
      `/admin/marketing/campaigns/${encodeURIComponent(campaignId)}/approve`,
    )
  },

  queueMarketingCampaign(campaignId: string) {
    return http.post<Record<string, unknown>>(
      `/admin/marketing/campaigns/${encodeURIComponent(campaignId)}/queue`,
    )
  },

  cancelMarketingCampaign(campaignId: string) {
    return http.post<Record<string, unknown>>(
      `/admin/marketing/campaigns/${encodeURIComponent(campaignId)}/cancel`,
    )
  },

  getSuppliers(signal?: AbortSignal) {
    return http.get<{ suppliers: any[]; purchase_orders: any[] }>('/admin/suppliers', { signal })
  },

  getSupplierInvoices(signal?: AbortSignal) {
    return http.get<any[]>('/admin/supplier-invoices', { signal })
  },

  verifySupplierInvoice(invoiceId: string, decision: 'APPROVE' | 'REJECT', notes: string) {
    return http.post<any>(`/admin/supplier-invoices/${encodeURIComponent(invoiceId)}/verify`, { decision, notes })
  },

  paySupplierInvoice(invoiceId: string, amount: number) {
    return http.post<any>(`/admin/supplier-invoices/${encodeURIComponent(invoiceId)}/pay`, {
      amount,
      payment_method: 'MANUAL',
      payment_reference: `MANUAL-${Date.now()}`,
      idempotency_key: globalThis.crypto.randomUUID(),
    })
  },

  createProcurementDraft(idempotencyKey: string, signal?: AbortSignal) {
    return http.post<Record<string, unknown>>(
      '/admin/procurement/drafts',
      {},
      { signal, headers: { 'Idempotency-Key': idempotencyKey } },
    )
  },

  approveProcurementDraft(poId: string, signal?: AbortSignal) {
    return http.post<Record<string, unknown>>(
      `/admin/procurement/purchase-orders/${encodeURIComponent(poId)}/approve`,
      undefined,
      { signal },
    )
  },

  queueProcurementDelivery(poId: string, signal?: AbortSignal) {
    return http.post<Record<string, unknown>>(
      `/admin/procurement/purchase-orders/${encodeURIComponent(poId)}/send`,
      undefined,
      { signal },
    )
  },

  getDescriptiveStats(signal?: AbortSignal) {
    return http.get<{
      n: number
      variables: Array<{
        variable: string
        n: number
        mean: number
        median: number
        std_dev: number
        min: number
        q1: number
        q3: number
        max: number
        iqr: number
        lower_bound: number
        upper_bound: number
        outlier_count: number
        cv: number
        skewness: number
        sum: number
        range: number
        variance: number
        std_err: number
        ci_95_lower: number
        ci_95_upper: number
      }>
      frequency_table: Array<{
        interval: string
        frequency: number
        proportion: string
        cumulative: string
      }>
    }>('/admin/analytics/descriptive-stats', { signal })
  },

  getRfmCrm(signal?: AbortSignal) {
    return http.get<{
      status: string
      data_mode: string
      source: string
      calculation_version: string
      as_of: string
      latest_order_date?: string
      data_age_days?: number
      freshness_status?: string
      freshness_threshold_days?: number
      warnings?: string[]
      total_analyzed: number
      segment_counts: Record<string, number>
      customers: Array<{
        customer_id: string
        name: string
        phone: string
        telegram_chat_id?: number | string | null
        telegram_verified?: boolean
        recency_days: number
        frequency: number
        monetary: number
        r_score: number
        f_score: number
        m_score: number
        rfm_score?: string
        segment: string
        recommended_action: string
      }>
    }>('/admin/analytics/rfm-crm', { signal })
  },

  persistRfmSnapshot(signal?: AbortSignal) {
    return http.post<{
      status: string
      persisted_rows: number
      as_of: string
      calculation_version: string
      data_mode: string
      source: string
    }>('/admin/analytics/rfm-crm/snapshot', undefined, { signal })
  },

  getChurnRisk(signal?: AbortSignal) {
    return http.get<{
      status: string
      data_mode: string
      source: string
      calculation_version: string
      methodology: string
      model_validated: boolean
      as_of: string
      latest_order_date?: string
      data_age_days?: number
      freshness_status?: string
      warnings?: string[]
      total_analyzed: number
      risk_counts: Record<string, number>
      customers: Array<{
        customer_id: string
        name: string
        phone: string
        last_order_date: string
        recency_days: number
        frequency: number
        expected_interval_days: number
        at_risk_after_days: number | null
        churn_after_days: number | null
        risk_band: string
        risk_index: number | null
        reason_codes: string[]
        recommended_action: string
      }>
    }>('/admin/analytics/churn-risk', { signal })
  },

  getChurnBacktest(horizonDays = 30, signal?: AbortSignal) {
    return http.get<{
      status: string
      data_mode: string
      source: string
      calculation_version: string
      methodology: string
      model_validated: boolean
      operational_eligibility?: boolean
      horizon_days: number
      label_definition?: string
      freshness_status?: string
      data_age_days?: number
      cutoff_count?: number
      train_cutoff_count?: number
      test_cutoff_count?: number
      train_cutoff_end?: string
      test_cutoff_start?: string
      train_observation_count?: number
      test_observation_count?: number
      metrics?: {
        sample_count: number
        positive_count: number
        negative_count: number
        predicted_positive_count: number
        precision: number | null
        recall: number | null
        f1: number | null
        roc_auc: number | null
        undefined_metrics: string[]
      }
      warnings?: string[]
    }>(`/admin/analytics/churn-backtest?horizon_days=${horizonDays}`, { signal })
  },

  getDemandInsights(signal?: AbortSignal) {
    return http.get<{
      top_dishes: Array<{
        menu_id: string
        nama_menu: string
        hari: string
        total_portions: number
        total_revenue: number
        share_percentage: number
      }>
      day_stats: Array<{
        day: string
        order_count: number
        portion_count: number
        revenue: number
        percentage: number
      }>
      peak_day: string
      monthly_trends: Array<{
        month_key: string
        month_label: string
        order_count: number
        total_sales: number
        avg_rating: number
      }>
      ai_daily_plan: Array<{
        day: string
        recommended_menu: string
        predicted_portions: number
        rationale: string
        allergen_notice: string
      }>
      supplier_7d_forecast: Array<{
        material: string
        projected_kg: number
        unit: string
        urgency: string
        supplier: string
      }>
    }>('/admin/analytics/demand-insights', { signal })
  },

  getSupplyChainMl(signal?: AbortSignal) {
    return http.get<{
      demand_forecast: {
        average_daily_meals: number
        sigma_daily_demand: number
        moving_average_7d: number
        linear_regression_forecast_tomorrow: number
        confidence_level: string
      }
      materials: Array<{
        ingredient_name: string
        current_stock: number
        unit: string
        daily_consumption_avg: number
        safety_stock: number
        reorder_point_rop: number
        status: string
        suggested_order_qty: number
      }>
      auto_po_recommendations: Array<{
        ingredient: string
        shortage: number
        unit: string
        order_qty: number
        estimated_cost: number
        supplier: string
      }>
    }>('/admin/analytics/supply-chain-ml', { signal })
  },

  getForecastBacktest(options?: { signal?: AbortSignal; horizonDays?: 7 | 30; mode?: 'live' | 'demo' }) {
    return http.get<{
      status: 'OK' | 'STALE_DATA' | 'LOW_VALIDATION' | 'INSUFFICIENT_HISTORY' | 'NO_DATA' | 'SIMULATED'
      data_mode: 'live' | 'simulated'
      source: string
      calculation_version: string
      as_of?: string
      latest_observation_date?: string
      paid_order_count?: number
      paid_order_item_count?: number
      invalid_quantity_item_count?: number
      missing_unit_item_count?: number
      missing_menu_id_item_count?: number
      latest_paid_date?: string | null
      latest_non_cancelled_date?: string | null
      dependency_metadata?: {
        paid_order_count?: number
        paid_order_item_count?: number
        invalid_quantity_item_count?: number
        missing_unit_item_count?: number
        missing_menu_id_item_count?: number
        latest_paid_date?: string | null
        latest_non_cancelled_date?: string | null
      }
      data_age_days?: number
      freshness_threshold_days?: number
      stale_series_count?: number
      horizon_days?: number
      series_count: number
      eligible_series_count: number
      model_comparison: Record<string, {
        mae: number
        rmse: number
        smape_percent: number | null
        wape_percent: number | null
        wape_status?: string
        smape_status?: string
        holdout_points: number
      }>
      series: Array<{
        series_key: string
        label: string
        unit: string
        latest_observation_date?: string
        data_age_days?: number
        history_days: number
        active_days: number
        total_observed: number
        backtest: {
          status: string
          selected_method: string | null
          methods: Record<string, {
            mae: number
            rmse: number
            smape_percent: number | null
            smape_status?: string
            holdout_points: number
          }>
        }
        forecast: Array<{
          target_date: string
          quantity: number
          lower_bound: number
          upper_bound: number
          interval_level: number
          unit: string
          method: string
          model_type: string
        }>
      }>
      weekday_demand_summary?: Array<{
        weekday: string
        weekday_index: number
        unit: string
        menus: Array<{ series_key: string; label: string; average_quantity: number; total_observed: number; observed_days: number }>
      }>
      warnings: string[]
      quantity_contract?: string
      seed_notice?: string
    }>('/admin/analytics/forecast-backtest', {
      signal: options?.signal,
      query: {
        horizon_days: options?.horizonDays ?? 7,
        mode: options?.mode ?? 'live',
      },
    })
  },

  persistForecastSnapshot(signal?: AbortSignal) {
    return http.post<{
      status: string
      persisted_rows: number
      calculation_version: string
      data_mode: string
      source: string
    }>('/admin/analytics/forecast-backtest/snapshot', undefined, { signal })
  },

  getInventoryReplenishment(signal?: AbortSignal) {
    return http.get<{
      status: 'OK' | 'STALE_DATA' | 'INSUFFICIENT_HISTORY' | 'NO_DATA' | 'REQUIRES_VERIFICATION'
      data_mode: 'live'
      source: string
      calculation_version: string
      forecast_status?: string
      forecast_latest_observation_date?: string
      forecast_data_age_days?: number
      horizon_days?: number
      readiness: {
        published_menu_count: number
        forecast_menu_count: number
        latest_recipe_count: number
        bom_ready_menu_count: number
        unresolved_bom: Array<Record<string, unknown>>
        inventory_item_count: number
        missing_inventory_ingredient_ids: string[]
        unsupported_stock_units: string[]
        supplier_mapped_ingredient_count: number
        missing_supplier_ingredient_ids: string[]
        roq_status: string
      }
      items: Array<{
        ingredient_id: string
        ingredient_name: string
        unit: string
        current_stock: number
        daily_demand_average: number
        demand_std_dev: number
        lead_time_days: number
        safety_stock: number
        reorder_point_rop: number
        replenishment_target: number
        shortage_quantity: number
        status: string
      }>
      roq: { status: string; reason_codes: string[]; note: string }
      warnings: string[]
    }>('/admin/analytics/inventory-replenishment', { signal })
  },

  getSupplierSourcing(signal?: AbortSignal) {
    return http.get<{
      status: 'OK' | 'REQUIRES_VERIFICATION'
      data_mode: 'live'
      source: string
      calculation_version: string
      inventory_status?: string
      forecast_status?: string
      weights: { price: number; lead_time: number; rating: number }
      items: Array<{
        ingredient_id: string
        ingredient_name: string
        shortage_quantity: number
        unit: string
        recommended_supplier: {
          supplier_id: string
          supplier_name: string
          price_per_unit: number
          lead_time_days: number
          rating: number
          score: number
        }
        supplier_candidates: Array<Record<string, unknown>>
      }>
      draft_po: {
        status: 'BLOCKED' | 'PREVIEW_ONLY'
        reason_codes: string[]
        message: string
      }
      warnings: string[]
    }>('/admin/analytics/supplier-sourcing', { signal })
  },

  getProductionBatches(serviceDate: string, signal?: AbortSignal) {
    return http.get<{
      items: ProductionBatch[]
      fetched_at: string
    }>('/kitchen/production-batches', { signal, query: { service_date: serviceDate } })
  },

  planProductionBatches(payload: { service_date: string; meal_slot: 'breakfast' | 'lunch' | 'dinner'; site_code?: string }) {
    return http.post<{ status: string; planned_batches?: ProductionBatch[]; batches?: ProductionBatch[]; [key: string]: unknown }>(
      '/kitchen/production-batches/plan-from-paid-orders',
      { site_code: 'main-kitchen', ...payload },
    )
  },

  weighProductionRequirement(batchId: string, payload: {
    requirement_id: string
    actual_net_grams: number
    tare_grams?: number
    idempotency_key: string
    lot_id?: string | null
    note?: string
  }) {
    return http.post<Record<string, unknown>>(
      `/kitchen/production-batches/${encodeURIComponent(batchId)}/weigh`,
      { scale_source: 'manual', ...payload },
    )
  },

  completeProductionBatch(batchId: string) {
    return http.post<ProductionBatch>(
      `/kitchen/production-batches/${encodeURIComponent(batchId)}/complete`,
    )
  },

  getDeliveryStops(serviceDate: string, signal?: AbortSignal) {
    return http.get<DeliveryStop[]>('/admin/delivery/stops', { signal, query: { service_date: serviceDate } })
  },

  createDeliveryStop(payload: { order_id: string; service_date: string; meal_slot: 'breakfast' | 'lunch' | 'dinner' }) {
    return http.post<DeliveryStop>('/admin/delivery/stops', payload)
  },

  assignDeliveryStop(stopId: string, courierId: string) {
    return http.post<DeliveryStop>(`/admin/delivery/stops/${encodeURIComponent(stopId)}/assign`, {
      courier_id: courierId,
    })
  },
}
export interface ProductionBatch {
  batch_id: string
  service_date: string
  meal_slot: 'breakfast' | 'lunch' | 'dinner' | 'snack'
  site_code: string
  recipe_version_id: string
  menu_name: string
  planned_portions: number
  status: string
  notes: string
  requirements: Array<{
    requirement_id: string
    ingredient_id: string
    ingredient_name: string
    planned_quantity: number
    unit: string
    issued_quantity: number
    variance_quantity: number
    planned_grams: number
    issued_grams: number
    remaining_grams: number
  }>
}

export interface DeliveryStop {
  stop_id: string
  order_id: string
  customer_id: string
  customer_name: string
  service_date: string
  meal_slot: string
  status: string
  courier_id: string | null
  proof_ref: string
  notes: string
  address: string
  assigned_at: string | null
  picked_up_at: string | null
  delivered_at: string | null
}
