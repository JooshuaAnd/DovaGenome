import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  BarChart3,
  Calculator,
  Database,
  FileSpreadsheet,
  Layers,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  Users,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { adminService } from '@/services/admin'

interface AdminAnalyticsViewProps {
  onOpenTelegram: (recipient: { type: string; name: string; chatId: string; message: string }) => void
  initialSubTab?: 'stats' | 'crm' | 'churn' | 'supply_chain' | 'demand_ai'
}

export function AdminAnalyticsView({ onOpenTelegram, initialSubTab = 'demand_ai' }: AdminAnalyticsViewProps) {
  const [subTab, setSubTab] = useState<'stats' | 'crm' | 'churn' | 'supply_chain' | 'demand_ai'>(initialSubTab)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (initialSubTab) {
      setSubTab(initialSubTab)
    }
  }, [initialSubTab])

  // CRM/RFM uses the live response only; failed requests must not reveal its old fixture.
  const [statsData, setStatsData] = useState<any>(null)
  const [rfmData, setRfmData] = useState<any>(null)
  // Forecast Phase 4 has a strict live contract. Legacy supply-chain payloads
  // are intentionally not used as a silent fallback here.
  // Legacy demand-insights payloads contain demo fallbacks and are not used by
  // the strict Phase 4 panel. Keep this tab unavailable until a live contract
  // replaces that endpoint.
  const [forecastBacktestData, setForecastBacktestData] = useState<any>(null)
  const [forecastHorizon, setForecastHorizon] = useState<7 | 30>(7)
  const [forecastMode, setForecastMode] = useState<'live' | 'demo'>('live')
  const [snapshotLoading, setSnapshotLoading] = useState(false)
  const [rfmSnapshotLoading, setRfmSnapshotLoading] = useState(false)
  const [churnData, setChurnData] = useState<any>(null)
  const [churnBacktestData, setChurnBacktestData] = useState<any>(null)
  const [inventoryReplenishmentData, setInventoryReplenishmentData] = useState<any>(null)

  // Filters
  const [rfmSearch, setRfmSearch] = useState('')
  const [rfmSegmentFilter, setRfmSegmentFilter] = useState('ALL')

  const fetchAnalytics = async (forecastOptions?: { horizonDays?: 7 | 30; mode?: 'live' | 'demo' }) => {
    setLoading(true)
    try {
      const horizonDays = forecastOptions?.horizonDays ?? forecastHorizon
      const mode = forecastOptions?.mode ?? forecastMode
      const [sRes, rRes, fRes, cRes, cbRes, iRes] = await Promise.all([
        adminService.getDescriptiveStats().catch(() => null),
        adminService.getRfmCrm().catch(() => null),
        adminService.getForecastBacktest({ horizonDays, mode }).catch(() => null),
        adminService.getChurnRisk().catch(() => null),
        adminService.getChurnBacktest().catch(() => null),
        adminService.getInventoryReplenishment().catch(() => null),
      ])
      setStatsData(sRes)
      setRfmData(rRes)
      const trustedForecast =
        fRes &&
        fRes.calculation_version === 'forecast_backtest_v2' &&
        ((mode === 'live' && fRes.data_mode === 'live' && fRes.source === 'supabase_postgres') ||
          (mode === 'demo' && fRes.data_mode === 'simulated' && fRes.source === 'seeded_demo_dataset'))
      // Never retain a previous forecast after a failed/invalid refresh.  A
      // missing live response must render unavailable, not stale evidence.
      setForecastBacktestData(trustedForecast ? fRes : null)
      setChurnData(cRes)
      setChurnBacktestData(cbRes)
      setInventoryReplenishmentData(iRes)
    } catch {
      toast.error('Gagal memuat data analitik statistik.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAnalytics()
  }, [])

  const filteredCustomers = (rfmData?.customers || []).filter((c: any) => {
    const matchSearch =
      c.name.toLowerCase().includes(rfmSearch.toLowerCase()) ||
      c.phone.includes(rfmSearch) ||
      c.customer_id.toLowerCase().includes(rfmSearch.toLowerCase())
    const matchSegment = rfmSegmentFilter === 'ALL' || c.segment === rfmSegmentFilter
    return matchSearch && matchSegment
  })

  const forecastSeries = forecastBacktestData?.series || []
  const forecastDependencyMetadata = forecastBacktestData?.dependency_metadata
  const forecastDependencyValid =
    forecastDependencyMetadata &&
    Number.isInteger(forecastDependencyMetadata.paid_order_count) &&
    forecastDependencyMetadata.paid_order_count >= 0 &&
    Number.isInteger(forecastDependencyMetadata.paid_order_item_count) &&
    forecastDependencyMetadata.paid_order_item_count >= 0 &&
    Number.isInteger(forecastDependencyMetadata.invalid_quantity_item_count) &&
    forecastDependencyMetadata.invalid_quantity_item_count === 0 &&
    Number.isInteger(forecastDependencyMetadata.missing_unit_item_count) &&
    forecastDependencyMetadata.missing_unit_item_count === 0 &&
    Number.isInteger(forecastDependencyMetadata.missing_menu_id_item_count) &&
    forecastDependencyMetadata.missing_menu_id_item_count === 0 &&
    typeof forecastDependencyMetadata.latest_paid_date === 'string' &&
    forecastDependencyMetadata.latest_paid_date.length > 0 &&
    typeof forecastDependencyMetadata.latest_non_cancelled_date === 'string' &&
    forecastDependencyMetadata.latest_non_cancelled_date.length > 0
  const forecastRowsValid =
    forecastSeries.length > 0 &&
    forecastSeries.length === Number(forecastBacktestData?.series_count || 0) &&
    forecastSeries.every((series: any) => {
      const quantity = series?.forecast?.[0]?.quantity
      return typeof quantity === 'number' && Number.isFinite(quantity) && quantity >= 0
    })
  const forecastIsOperational =
    forecastBacktestData?.status === 'OK' &&
    forecastBacktestData?.data_mode === 'live' &&
    forecastBacktestData?.source === 'supabase_postgres' &&
    forecastBacktestData?.calculation_version === 'forecast_backtest_v2' &&
    forecastDependencyValid &&
    forecastRowsValid
  const forecastIsDemo =
    forecastMode === 'demo' &&
    forecastBacktestData?.data_mode === 'simulated' &&
    forecastBacktestData?.source === 'seeded_demo_dataset' &&
    forecastRowsValid
  const forecastCanDisplay = forecastIsOperational || forecastIsDemo
  const forecastPeriodTotal = forecastCanDisplay
    ? forecastSeries.reduce(
        (total: number, series: any) => total + (series.forecast || []).reduce(
          (sum: number, point: any) => sum + Number(point.quantity || 0), 0,
        ),
        0,
      )
    : null
  const historicalBestModel = Object.entries(forecastBacktestData?.model_comparison || {})
    .sort(([, left]: any, [, right]: any) => Number(left.mae) - Number(right.mae))[0]?.[0]
  const selectedForecastModel = forecastCanDisplay ? historicalBestModel || '-' : '-'
  const selectedForecastMetrics = forecastCanDisplay && historicalBestModel
    ? forecastBacktestData?.model_comparison?.[historicalBestModel]
    : null
  const forecastMenuTotals = forecastCanDisplay
    ? forecastSeries.map((series: any) => ({
        ...series,
        period_quantity: (series.forecast || []).reduce((sum: number, point: any) => sum + Number(point.quantity || 0), 0),
        period_lower: (series.forecast || []).reduce((sum: number, point: any) => sum + Number(point.lower_bound || 0), 0),
        period_upper: (series.forecast || []).reduce((sum: number, point: any) => sum + Number(point.upper_bound || 0), 0),
      })).sort((a: any, b: any) => b.period_quantity - a.period_quantity)
    : []
  const forecastDailyTotals = forecastCanDisplay
    ? (() => {
        const days = new Map<string, { total: number; menus: Array<{ label: string; quantity: number; unit: string }> }>()
        forecastSeries.forEach((series: any) => (series.forecast || []).forEach((point: any) => {
          const day = days.get(point.target_date) || { total: 0, menus: [] }
          const quantity = Number(point.quantity || 0)
          day.total += quantity
          day.menus.push({ label: series.label, quantity, unit: series.unit })
          days.set(point.target_date, day)
        }))
        return [...days.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([date, day]) => ({
          date,
          total: day.total,
          recommendations: day.menus.sort((left, right) => right.quantity - left.quantity).slice(0, 3),
        }))
      })()
    : []
  const historicalWeekdayRows = forecastBacktestData?.weekday_demand_summary || []
  const replenishmentItems = inventoryReplenishmentData?.items || []
  const formatChurnMetric = (value: unknown) =>
    typeof value === 'number' && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : 'N/A'

  const persistForecastSnapshot = async () => {
    if (!forecastIsOperational) {
      toast.error('Snapshot ditahan: forecast live harus berstatus OK dan fresh.')
      return
    }
    setSnapshotLoading(true)
    try {
      const result = await adminService.persistForecastSnapshot()
      toast.success(`Snapshot forecast tersimpan: ${result.persisted_rows} baris.`)
    } catch {
      toast.error('Snapshot tidak ditulis. Periksa status freshness dan dependency live.')
    } finally {
      setSnapshotLoading(false)
    }
  }

  const rfmIsFresh =
    rfmData?.status === 'OK' &&
    rfmData?.data_mode === 'live' &&
    rfmData?.freshness_status === 'FRESH'

  const persistRfmSnapshot = async () => {
    if (!rfmIsFresh) {
      toast.error('Snapshot RFM ditahan: data live harus fresh maksimal 7 hari.')
      return
    }
    setRfmSnapshotLoading(true)
    try {
      const result = await adminService.persistRfmSnapshot()
      toast.success(`Snapshot RFM tersimpan: ${result.persisted_rows} customer.`)
    } catch {
      toast.error('Snapshot RFM tidak ditulis. Periksa status freshness dan provenance live.')
    } finally {
      setRfmSnapshotLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-stone-200 bg-white px-5 py-3"><p className="text-sm font-bold text-stone-900">Analitik operasional</p><p className="text-xs text-stone-500">Pilih modul lewat navigasi utama di sidebar.</p></div>

      {/* ── SUB-TAB 1: STATISTIK DESKRIPTIF & DETEKSI OUTLIER ─────────────── */}
      {subTab === 'stats' && (
        <div className="space-y-6">
          {/* Top Formula Banner (Matching Excel screenshot header exactly) */}
          <div className="p-4 rounded-3xl bg-amber-500/10 border border-amber-300 text-amber-950 space-y-2 text-xs">
            <div className="flex items-center gap-2 font-black text-sm text-amber-900">
              <Calculator className="size-4.5 text-amber-700" />
              <span>Statistik Deskriptif dan Deteksi Outlier (Rumus Excel pada sheet Data)</span>
            </div>
            <p className="font-mono text-[11px] leading-relaxed text-amber-900/90 bg-white/70 p-3 rounded-2xl border border-amber-200">
              Std = STDEV (sampel); Q1/Q3 = QUARTILE; IQR = Q3 - Q1; batas = Q1 - 1,5 IQR dan Q3 + 1,5 IQR;
              CV = Std / |Rata-rata|; SE = Std / akar(N); CI 95% = Rata-rata ± 1,96 SE. SKEW/KURT Excel
              memakai koreksi sampel.
            </p>
          </div>

          {/* Main Excel-like Summary Table */}
          <div className="bg-white rounded-3xl border border-stone-200/90 shadow-2xs overflow-hidden">
            <div className="p-5 pb-3 border-b border-stone-100 flex items-center justify-between">
              <div>
                <h3 className="font-extrabold text-base text-stone-900 flex items-center gap-2">
                  <FileSpreadsheet className="size-4.5 text-emerald-700" />
                  Tabel Ringkasan Statistik Transaksi
                </h3>
                <p className="text-xs text-stone-500 mt-0.5">
                  {statsData?.status === 'OK' ? `Dihitung realtime dari Supabase dengan sample size N = ${statsData.n}.` : 'Statistik ditahan sampai observasi transaksi live tersedia.'}
                </p>
              </div>
              <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300 font-bold text-xs">
                N = {statsData?.n ?? '—'} Record
              </Badge>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left text-stone-700 border-collapse">
                <thead className="bg-[#14213D] text-white text-[11px] uppercase tracking-wider font-bold">
                  <tr>
                    <th className="py-3 px-3.5 sticky left-0 bg-[#14213D] z-10">Variabel</th>
                    <th className="py-3 px-2.5 text-right">N</th>
                    <th className="py-3 px-2.5 text-right">Rata-rata</th>
                    <th className="py-3 px-2.5 text-right">Median</th>
                    <th className="py-3 px-2.5 text-right">Std Dev</th>
                    <th className="py-3 px-2.5 text-right">Min</th>
                    <th className="py-3 px-2.5 text-right">Q1</th>
                    <th className="py-3 px-2.5 text-right">Q3</th>
                    <th className="py-3 px-2.5 text-right">Maks</th>
                    <th className="py-3 px-2.5 text-right bg-blue-900/60">IQR</th>
                    <th className="py-3 px-2.5 text-right">Batas Bawah</th>
                    <th className="py-3 px-2.5 text-right">Batas Atas</th>
                    <th className="py-3 px-2.5 text-center bg-rose-900/60">Outlier</th>
                    <th className="py-3 px-2.5 text-right">CV</th>
                    <th className="py-3 px-2.5 text-right">Skewness</th>
                    <th className="py-3 px-2.5 text-right">Jumlah</th>
                    <th className="py-3 px-2.5 text-right">Rentang</th>
                    <th className="py-3 px-2.5 text-right">Varians</th>
                    <th className="py-3 px-2.5 text-right">SE</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 font-mono">
                  {statsData?.variables?.map((row: any, idx: number) => {
                    const isEven = idx % 2 === 0
                    return (
                      <tr
                        key={row.variable}
                        className={cn(
                          'hover:bg-amber-50/50 transition-colors',
                          isEven ? 'bg-white' : 'bg-stone-50/60'
                        )}
                      >
                        <td className="py-2.5 px-3.5 font-bold font-sans text-stone-900 sticky left-0 bg-inherit z-10 whitespace-nowrap">
                          {row.variable}
                        </td>
                        <td className="py-2.5 px-2.5 text-right">{row.n.toLocaleString()}</td>
                        <td className="py-2.5 px-2.5 text-right font-semibold text-stone-900">
                          {row.mean.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-2.5 text-right">
                          {row.median.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-2.5 text-right">
                          {row.std_dev.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-2.5 text-right">
                          {row.min.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-2.5 text-right">
                          {row.q1.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-2.5 text-right">
                          {row.q3.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-2.5 text-right">
                          {row.max.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-2.5 text-right font-bold text-blue-700 bg-blue-50/50">
                          {row.iqr.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-2.5 text-right text-stone-500">
                          {row.lower_bound.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-2.5 text-right text-stone-500">
                          {row.upper_bound.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-2.5 text-center">
                          <span
                            className={cn(
                              'px-2 py-0.5 rounded-full text-[10px] font-bold',
                              row.outlier_count > 0
                                ? 'bg-rose-100 text-rose-700 font-extrabold'
                                : 'bg-emerald-50 text-emerald-700'
                            )}
                          >
                            {row.outlier_count}
                          </span>
                        </td>
                        <td className="py-2.5 px-2.5 text-right">
                          {row.cv.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-2.5 text-right">
                          {row.skewness.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-2.5 text-right text-stone-500">
                          {row.sum.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </td>
                        <td className="py-2.5 px-2.5 text-right">
                          {row.range.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                        <td className="py-2.5 px-2.5 text-right text-stone-500 text-[10px]">
                          {row.variance.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                        </td>
                        <td className="py-2.5 px-2.5 text-right font-semibold text-emerald-700">
                          {row.std_err.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Frequency Distribution Table (Matching Excel bottom left exactly) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-7 bg-white rounded-3xl p-5 border border-stone-200/90 shadow-2xs space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-extrabold text-base text-stone-900 flex items-center gap-2">
                    <BarChart3 className="size-4.5 text-blue-600" />
                    Distribusi Frekuensi: Unit Price (10 Kelas Interval)
                  </h3>
                  <p className="text-xs text-stone-500 mt-0.5">
                    Histogram frekuensi dan proporsi kumulatif sesuai format Excel.
                  </p>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead className="bg-[#14213D] text-white text-[11px] font-bold">
                    <tr>
                      <th className="py-2.5 px-3">Interval</th>
                      <th className="py-2.5 px-3 text-right">Frekuensi</th>
                      <th className="py-2.5 px-3 text-right">Proporsi</th>
                      <th className="py-2.5 px-3 text-right">Kumulatif</th>
                      <th className="py-2.5 px-3">Visual Distribusi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100 font-mono">
                    {statsData?.frequency_table?.map((item: any, idx: number) => {
                      const pct = Number.parseFloat(item.proportion) || 0
                      return (
                        <tr key={idx} className="hover:bg-blue-50/30">
                          <td className="py-2 px-3 font-sans font-medium text-stone-800">
                            {item.interval}
                          </td>
                          <td className="py-2 px-3 text-right font-bold text-stone-900">
                            {item.frequency}
                          </td>
                          <td className="py-2 px-3 text-right font-semibold text-blue-600">
                            {item.proportion}
                          </td>
                          <td className="py-2 px-3 text-right text-stone-500">{item.cumulative}</td>
                          <td className="py-2 px-3">
                            <div className="w-24 bg-stone-100 rounded-full h-2 overflow-hidden">
                              <div
                                className="bg-amber-500 h-full rounded-full transition-all"
                                style={{ width: `${Math.min(100, pct * 4)}%` }}
                              />
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                  <tfoot className="bg-stone-50 font-bold border-t-2 border-stone-200">
                    <tr>
                      <td className="py-2 px-3">Total</td>
                      <td className="py-2 px-3 text-right font-mono">{statsData?.n ?? '—'}</td>
                      <td className="py-2 px-3 text-right font-mono">100,0%</td>
                      <td className="py-2 px-3 text-right font-mono">100,0%</td>
                      <td className="py-2 px-3" />
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>

            {/* Quick Insights & Outlier Notes */}
            <div className="lg:col-span-5 bg-gradient-to-br from-stone-900 to-stone-800 text-white rounded-3xl p-6 shadow-md space-y-4">
              <div className="flex items-center gap-2">
                <Sparkles className="size-5 text-amber-400" />
                <h4 className="font-extrabold text-base text-amber-300">
                  Temuan Algoritma Deteksi Outlier (Tukey IQR)
                </h4>
              </div>

              <div className="space-y-3 text-xs leading-relaxed text-stone-200">
                <p>
                  Metode <strong>Interquartile Range (IQR)</strong> mengevaluasi pencilan dengan batas:
                </p>
                <div className="bg-stone-950/60 p-3 rounded-2xl border border-stone-700 font-mono text-[11px] text-amber-200 space-y-1">
                  <div>Batas Bawah = Q1 - 1,5 × IQR</div>
                  <div>Batas Atas  = Q3 + 1,5 × IQR</div>
                </div>
                <p>Outlier, rata-rata, dan sebaran dibaca dari nilai aktual pada tabel di samping. Jika datanya belum ada, ringkasan numerik tidak ditampilkan.</p>
              </div>

              <div className="pt-2 border-t border-stone-700/80 flex items-center justify-between text-xs">
                <span className="text-stone-400">Tingkat Keyakinan (CI):</span>
                <span className="font-bold text-amber-400 font-mono">95% (Z = 1.96)</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── SUB-TAB 2: CRM & PEMASARAN (RFM SEGMENTATION) ────────────────── */}
      {subTab === 'crm' && (
        <div className="space-y-6">
          {!rfmData && (
            <div className="rounded-2xl bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-900">
              RFM live belum tersedia. Tidak ada segment atau angka simulasi yang ditampilkan sebagai pengganti.
            </div>
          )}
          {/* RFM Segment Breakdown Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {[
              { label: 'Champions', count: rfmData?.segment_counts?.Champions || 0, color: 'emerald' },
              { label: 'Loyal Customers', count: rfmData?.segment_counts?.['Loyal Customers'] || 0, color: 'blue' },
              { label: 'Potential Loyalists', count: rfmData?.segment_counts?.['Potential Loyalists'] || 0, color: 'amber' },
              { label: 'At Risk', count: rfmData?.segment_counts?.['At Risk'] || 0, color: 'orange' },
              { label: 'Hibernating', count: rfmData?.segment_counts?.Hibernating || 0, color: 'rose' },
              { label: 'New Customers', count: rfmData?.segment_counts?.['New Customers'] || 0, color: 'purple' },
            ].map((seg) => (
              <div
                key={seg.label}
                onClick={() => setRfmSegmentFilter(seg.label === rfmSegmentFilter ? 'ALL' : seg.label)}
                className={cn(
                  'p-4 rounded-3xl border transition-all cursor-pointer text-center',
                  rfmSegmentFilter === seg.label
                    ? 'bg-stone-900 text-white border-stone-900 shadow-md scale-102'
                    : 'bg-white border-stone-200/90 text-stone-900 hover:border-amber-400'
                )}
              >
                <p className="text-[11px] font-bold truncate opacity-80">{seg.label}</p>
                <h3 className="text-2xl font-black mt-1">{seg.count}</h3>
                <p className="text-[10px] mt-0.5 opacity-60">
                  {Math.round((seg.count / (rfmData?.total_analyzed || 1)) * 100)}% Pelanggan
                </p>
              </div>
            ))}
          </div>

          {/* Customer CRM Table */}
          <div className="bg-white rounded-3xl border border-stone-200/90 p-5 shadow-2xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <h3 className="font-extrabold text-base text-stone-900 flex items-center gap-2">
                  <Users className="size-4.5 text-amber-600" />
                  Daftar Pelanggan Berdasarkan Skor RFM (Recency, Frequency, Monetary)
                </h3>
                <p className="text-xs text-stone-500 mt-0.5">
                  Segmentasi quantile RFM berprovenance untuk bahan review kampanye.
                </p>
              </div>

              <div className="flex items-center gap-2">
                {rfmData && (
                  <span className={cn(
                    'rounded-full px-2.5 py-1 text-[10px] font-bold',
                    rfmData.freshness_status === 'FRESH'
                      ? 'bg-emerald-50 text-emerald-700'
                      : 'bg-amber-50 text-amber-700',
                  )}>
                    {rfmData.freshness_status === 'FRESH' ? 'Fresh' : 'Stale — historical signal'}
                  </span>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={persistRfmSnapshot}
                  disabled={rfmSnapshotLoading || !rfmIsFresh}
                  title={rfmIsFresh ? 'Simpan RFM live yang fresh' : 'Aktif jika RFM live berumur maksimal 7 hari'}
                  className="rounded-full text-xs font-bold"
                >
                  <Database className={cn('size-3', rfmSnapshotLoading && 'animate-pulse')} />
                  {rfmSnapshotLoading ? 'Menyimpan…' : 'Simpan snapshot'}
                </Button>
              </div>

              {/* Search & Filter */}
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="absolute left-3 top-2.5 size-3.5 text-stone-400" />
                  <Input
                    value={rfmSearch}
                    onChange={(e) => setRfmSearch(e.target.value)}
                    placeholder="Cari nama / HP..."
                    className="rounded-2xl pl-9 pr-3 py-1.5 text-xs bg-stone-50 border-stone-200 w-48"
                  />
                </div>
                {rfmSegmentFilter !== 'ALL' && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setRfmSegmentFilter('ALL')}
                    className="rounded-full text-xs font-bold"
                  >
                    Reset Filter
                  </Button>
                )}
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead className="bg-[#14213D] text-white text-[11px] font-bold">
                  <tr>
                    <th className="py-3 px-3">Pelanggan</th>
                    <th className="py-3 px-2.5 text-center">R (Hari)</th>
                    <th className="py-3 px-2.5 text-center">F (Order)</th>
                    <th className="py-3 px-2.5 text-right">Monetary (Rp)</th>
                    <th className="py-3 px-2.5 text-center">Skor RFM</th>
                    <th className="py-3 px-3">Segmen</th>
                    <th className="py-3 px-3">Strategi Tindakan</th>
                    <th className="py-3 px-3 text-center">Aksi Telegram</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 font-mono">
                  {filteredCustomers.map((c: any) => (
                    <tr key={c.customer_id} className="hover:bg-stone-50/60 font-sans">
                      <td className="py-2.5 px-3">
                        <p className="font-bold text-stone-900">{c.name}</p>
                        <p className="text-[11px] text-stone-400 font-mono">{c.phone}</p>
                      </td>
                      <td className="py-2.5 px-2.5 text-center font-mono font-bold text-stone-700">
                        {c.recency_days} hr
                      </td>
                      <td className="py-2.5 px-2.5 text-center font-mono font-bold text-stone-700">
                        {c.frequency}x
                      </td>
                      <td className="py-2.5 px-2.5 text-right font-mono font-bold text-stone-900">
                        Rp {c.monetary.toLocaleString('id-ID')}
                      </td>
                      <td className="py-2.5 px-2.5 text-center">
                        <span className="font-mono bg-stone-900 text-amber-300 px-2.5 py-1 rounded-lg font-black text-xs tracking-wider inline-block shadow-xs border border-stone-800">
                          {c.rfm_score || `${c.r_score ?? ''}${c.f_score ?? ''}${c.m_score ?? ''}`}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <Badge
                          className={cn(
                            'text-[10px] font-bold px-2.5 py-0.5 border-none shadow-2xs',
                            c.segment === 'Champions'
                              ? 'bg-emerald-600 text-white'
                              : c.segment === 'Loyal Customers'
                              ? 'bg-blue-600 text-white'
                              : c.segment === 'Potential Loyalists'
                              ? 'bg-amber-500 text-stone-950 font-black'
                              : c.segment === 'At Risk'
                              ? 'bg-rose-600 text-white animate-pulse'
                              : c.segment === 'Hibernating'
                              ? 'bg-stone-600 text-white'
                              : 'bg-purple-600 text-white'
                          )}
                        >
                          {c.segment}
                        </Badge>
                      </td>
                      <td className="py-2.5 px-3 text-[11px] text-stone-600 max-w-xs">
                        {c.recommended_action}
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <Button
                          size="sm"
                          disabled={!c.telegram_chat_id}
                          title={c.telegram_chat_id ? 'Queue pesan ke Telegram' : 'Pelanggan belum menautkan Telegram'}
                          onClick={() =>
                            onOpenTelegram({
                              type: 'customer',
                              name: c.name,
                              chatId: String(c.telegram_chat_id || ''),
                              message:
                                c.segment === 'At Risk'
                                  ? `Halo Kak ${c.name}! Dova Kitchen sangat merindukanmu 🥰 Kami siapkan voucher diskon 20% khusus untukmu minggu ini. Yuk pesan menu katering sehat favoritmu lagi!`
                                  : `Halo ${c.name}! Terima kasih selalu mempercayakan santapan sehat di Dova Kitchen. ${c.recommended_action} Cek menu minggu depan di website kami sekarang!`,
                            })
                          }
                          className={cn(
                            'rounded-full font-bold text-[11px] px-3 py-1 h-7 gap-1 text-white',
                            !c.telegram_chat_id
                              ? 'bg-stone-300 text-stone-600 cursor-not-allowed'
                              : c.segment === 'At Risk'
                              ? 'bg-rose-600 hover:bg-rose-700'
                              : 'bg-emerald-600 hover:bg-emerald-700'
                          )}
                        >
                          <Send className="size-3" />
                          {!c.telegram_chat_id ? 'Belum tertaut' : c.segment === 'At Risk' ? 'Re-engage' : 'Chat'}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── SUB-TAB 3: SUPPLY CHAIN ML (SAFETY STOCK & ROP) ───────────────── */}
      {subTab === 'churn' && (
        <div className="space-y-6">
          <div className="bg-white rounded-3xl border border-stone-200/90 p-5 shadow-2xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
              <div>
                <h3 className="font-extrabold text-base text-stone-900 flex items-center gap-2">
                  <AlertTriangle className="size-4.5 text-amber-600" />
                  Baseline Churn Risk Pelanggan
                </h3>
                <p className="text-xs text-stone-500 mt-0.5">
                  Rule-based dari cadence order PAID non-CANCELLED; bukan model supervised dan bukan probabilitas.
                </p>
              </div>
              {churnData ? (
                <Badge className="text-[10px] font-bold bg-amber-100 text-amber-900 border-amber-300">
                  {churnData.status} Â· {churnData.freshness_status || 'UNKNOWN'}
                </Badge>
              ) : (
                <Badge className="text-[10px] font-bold bg-stone-200 text-stone-700 border-none">
                  DATA BELUM TERSEDIA
                </Badge>
              )}
            </div>

            {churnData ? (
              <>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Customer dianalisis</span><strong className="block text-lg">{churnData.total_analyzed}</strong></div>
                  <div className="rounded-2xl bg-rose-50 p-3"><span className="text-stone-500">High baseline</span><strong className="block text-lg text-rose-700">{churnData.risk_counts?.HIGH || 0}</strong></div>
                  <div className="rounded-2xl bg-amber-50 p-3"><span className="text-stone-500">Medium baseline</span><strong className="block text-lg text-amber-700">{churnData.risk_counts?.MEDIUM || 0}</strong></div>
                  <div className="rounded-2xl bg-emerald-50 p-3"><span className="text-stone-500">Low baseline</span><strong className="block text-lg text-emerald-700">{churnData.risk_counts?.LOW || 0}</strong></div>
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Order terakhir</span><strong className="block text-sm">{churnData.latest_order_date || '-'}</strong></div>
                </div>

                <div className="rounded-2xl bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-950 space-y-1">
                  <div><strong>Metodologi:</strong> {churnData.methodology}; calculation {churnData.calculation_version}; source {churnData.source}.</div>
                  {(churnData.warnings || []).map((warning: string) => <div key={warning}>â€¢ {warning}</div>)}
                </div>

                <div className="overflow-x-auto rounded-2xl border border-stone-100">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-[#14213D] text-white text-[11px] font-bold">
                      <tr><th className="py-2 px-3">Pelanggan</th><th className="py-2 px-3 text-right">Recency</th><th className="py-2 px-3 text-right">Frequency</th><th className="py-2 px-3 text-right">Cadence</th><th className="py-2 px-3">Risk band</th><th className="py-2 px-3">Alasan</th></tr>
                    </thead>
                    <tbody className="divide-y divide-stone-100">
                      {(churnData.customers || []).map((customer: any) => (
                        <tr key={customer.customer_id}>
                          <td className="py-2 px-3"><strong>{customer.name}</strong><div className="text-[11px] text-stone-400">{customer.phone || customer.customer_id}</div></td>
                          <td className="py-2 px-3 text-right font-mono">{customer.recency_days} hari</td>
                          <td className="py-2 px-3 text-right font-mono">{customer.frequency}x</td>
                          <td className="py-2 px-3 text-right font-mono">{customer.expected_interval_days} hari</td>
                          <td className="py-2 px-3"><Badge className={cn('text-[10px] border-none', customer.risk_band === 'HIGH' ? 'bg-rose-100 text-rose-800' : customer.risk_band === 'MEDIUM' ? 'bg-amber-100 text-amber-800' : customer.risk_band === 'LOW' ? 'bg-emerald-100 text-emerald-800' : 'bg-stone-100 text-stone-700')}>{customer.risk_band}</Badge></td>
                          <td className="py-2 px-3 text-stone-600">{customer.reason_codes?.join(', ')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            ) : (
              <div className="rounded-2xl bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-900">
                Baseline churn live belum tersedia. Tidak ada angka simulasi yang ditampilkan sebagai pengganti.
              </div>
            )}
          </div>

          <div className="bg-white rounded-3xl border border-stone-200/90 p-5 shadow-2xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
              <div>
                <h3 className="font-extrabold text-base text-stone-900">Historical Churn Backtest</h3>
                <p className="text-xs text-stone-500 mt-0.5">
                  Label observasi 30 hari setelah cutoff dengan split waktu; ini evaluasi baseline, bukan model supervised.
                </p>
              </div>
              {churnBacktestData ? (
                <Badge className="text-[10px] font-bold bg-sky-100 text-sky-900 border-sky-300">
                  {churnBacktestData.status} · {churnBacktestData.freshness_status || 'HISTORICAL'}
                </Badge>
              ) : (
                <Badge className="text-[10px] font-bold bg-stone-200 text-stone-700 border-none">
                  DATA BELUM TERSEDIA
                </Badge>
              )}
            </div>

            {churnBacktestData ? (
              <>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Cutoff</span><strong className="block text-lg">{churnBacktestData.cutoff_count ?? 0}</strong></div>
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Train</span><strong className="block text-lg">{churnBacktestData.train_cutoff_count ?? 0}</strong></div>
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Test cutoff</span><strong className="block text-lg">{churnBacktestData.test_cutoff_count ?? 0}</strong></div>
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Holdout rows</span><strong className="block text-lg">{churnBacktestData.metrics?.sample_count ?? 0}</strong></div>
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">ROC-AUC</span><strong className="block text-lg">{formatChurnMetric(churnBacktestData.metrics?.roc_auc)}</strong></div>
                </div>

                {churnBacktestData.metrics ? (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                    <div className="rounded-2xl bg-sky-50 p-3"><span className="text-stone-500">Precision</span><strong className="block text-lg">{formatChurnMetric(churnBacktestData.metrics.precision)}</strong></div>
                    <div className="rounded-2xl bg-sky-50 p-3"><span className="text-stone-500">Recall</span><strong className="block text-lg">{formatChurnMetric(churnBacktestData.metrics.recall)}</strong></div>
                    <div className="rounded-2xl bg-sky-50 p-3"><span className="text-stone-500">F1</span><strong className="block text-lg">{formatChurnMetric(churnBacktestData.metrics.f1)}</strong></div>
                    <div className="rounded-2xl bg-sky-50 p-3"><span className="text-stone-500">Positive labels</span><strong className="block text-lg">{churnBacktestData.metrics.positive_count}</strong></div>
                  </div>
                ) : null}

                <div className="rounded-2xl bg-sky-50 border border-sky-200 px-3 py-2 text-xs text-sky-950 space-y-1">
                  <div><strong>Calculation:</strong> {churnBacktestData.calculation_version}; source {churnBacktestData.source}; model validated: {String(churnBacktestData.model_validated)}.</div>
                  <div><strong>Split:</strong> train sampai {churnBacktestData.train_cutoff_end || '-'}, test mulai {churnBacktestData.test_cutoff_start || '-'}.</div>
                  {(churnBacktestData.warnings || []).map((warning: string) => <div key={warning}>• {warning}</div>)}
                </div>
              </>
            ) : (
              <div className="rounded-2xl bg-sky-50 border border-sky-200 px-3 py-2 text-xs text-sky-900">
                Backtest churn belum tersedia. Tidak ada angka simulasi yang ditampilkan sebagai pengganti.
              </div>
            )}
          </div>
        </div>
      )}

      {(subTab === 'supply_chain' || subTab === 'demand_ai') && (
        <div className="space-y-6">
          {subTab === 'demand_ai' && (<>
          <div className="bg-white rounded-3xl border border-stone-200/90 p-5 shadow-2xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
              <div>
                <h3 className="font-extrabold text-base text-stone-900 flex items-center gap-2">
                  <BarChart3 className="size-4.5 text-blue-700" />
                  Forecast Demand & Rolling-Origin Backtest
                </h3>
                <p className="text-xs text-stone-500 mt-0.5">
                  Horizon 7 atau 30 hari. Live memakai transaksi paid; Seed demo untuk preview sintetis terpisah.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <div className="inline-flex rounded-full border border-stone-200 bg-stone-50 p-1">
                  {([{ days: 7, label: '7 hari · Mingguan' }, { days: 30, label: '30 hari · Bulanan' }] as const).map(({ days, label }) => (
                    <button key={days} type="button" aria-pressed={forecastHorizon === days} disabled={loading} onClick={() => {
                      setForecastHorizon(days)
                      void fetchAnalytics({ horizonDays: days, mode: forecastMode })
                    }} className={cn('rounded-full px-3 py-1.5 text-[10px] font-bold transition-colors', forecastHorizon === days ? 'bg-[#8f1d2c] text-white shadow-sm' : 'text-stone-600 hover:bg-white')}>{label}</button>
                  ))}
                </div>
                <div className="inline-flex rounded-full border border-stone-200 bg-stone-50 p-1">
                  {([{ mode: 'live', label: 'Live' }, { mode: 'demo', label: 'Seed demo' }] as const).map(({ mode, label }) => (
                    <button key={mode} type="button" aria-pressed={forecastMode === mode} disabled={loading} onClick={() => {
                      setForecastMode(mode)
                      void fetchAnalytics({ horizonDays: forecastHorizon, mode })
                    }} className={cn('rounded-full px-3 py-1.5 text-[10px] font-bold transition-colors', forecastMode === mode ? 'bg-[#8f1d2c] text-white shadow-sm' : 'text-stone-600 hover:bg-white')}>{label}</button>
                  ))}
                </div>
                {forecastBacktestData ? (
                  <Badge className={cn(
                    'text-[10px] font-bold border-none',
                    forecastIsDemo
                      ? 'bg-violet-100 text-violet-800'
                      : forecastBacktestData.status === 'OK'
                        ? 'bg-emerald-600 text-white'
                        : 'bg-amber-500 text-white'
                  )}>
                    {forecastIsDemo ? 'SEED · PREVIEW' : `${forecastBacktestData.status} · LIVE`}
                  </Badge>
                ) : (
                  <Badge className="text-[10px] font-bold bg-stone-200 text-stone-700 border-none">
                    DATA BELUM TERSEDIA
                  </Badge>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void fetchAnalytics()}
                  disabled={loading}
                  className="rounded-full text-[10px] font-bold gap-1.5"
                  title={forecastMode === 'demo' ? 'Hitung forecast dari dataset seed lokal' : 'Ambil ulang forecast live dari Supabase'}
                >
                  <RefreshCw className={cn('size-3', loading && 'animate-spin')} />
                  {loading ? 'Memuat...' : forecastMode === 'demo' ? 'Muat ulang seed' : 'Muat ulang data'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={persistForecastSnapshot}
                  disabled={snapshotLoading || !forecastIsOperational}
                  className="rounded-full text-[10px] font-bold gap-1.5"
                  title={forecastIsOperational ? 'Simpan forecast live ke snapshot operasional' : 'Aktif jika forecast live fresh dan berstatus OK'}
                >
                  <Send className={cn('size-3', snapshotLoading && 'animate-pulse')} />
                  {snapshotLoading ? 'Menyimpan…' : 'Simpan snapshot'}
                </Button>
              </div>
            </div>
            {forecastBacktestData ? (
              <>
                <div className="rounded-2xl border border-stone-200 bg-stone-50 px-3 py-2 text-[11px] text-stone-600">
                  Sumber: <strong>{forecastBacktestData.source || '-'}</strong> · Versi: <strong>{forecastBacktestData.calculation_version || '-'}</strong> · Write-gate:{' '}
                  <strong className={forecastIsOperational ? 'text-emerald-700' : 'text-amber-700'}>
                    {forecastIsOperational ? 'OPEN' : forecastIsDemo ? 'CLOSED — seed hanya untuk preview' : 'CLOSED — forecast belum fresh/operasional'}
                  </strong>
                </div>
                {forecastIsDemo && (
                  <div role="status" className="rounded-xl border border-violet-200 bg-violet-50 px-4 py-3 text-sm text-violet-950">
                    <strong>Dataset seed untuk preview.</strong>
                    <p className="mt-1 text-xs">{forecastBacktestData.seed_notice} Snapshot operasional tetap terkunci.</p>
                  </div>
                )}
                {!forecastIsOperational && !forecastIsDemo && (
                  <div role="status" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-950">
                    <strong>Forecast belum bisa dipakai untuk operasional.</strong>
                    <p className="mt-1">
                      Observasi terakhir {forecastBacktestData.latest_observation_date || 'belum tersedia'}
                      {forecastBacktestData.data_age_days != null ? ` (${forecastBacktestData.data_age_days} hari lalu)` : ''};
                      {' '}batas kesegaran {forecastBacktestData.freshness_threshold_days ?? 3} hari.
                    </p>
                    <p className="mt-1 text-xs text-rose-900">
                      Sumber hanya menghitung item dari pesanan PAID yang tidak dibatalkan. Jika ada transaksi terbaru, pastikan status pembayaran, menu, jumlah, dan unitnya sudah tersimpan di Supabase, lalu pilih “Muat ulang data”.
                    </p>
                  </div>
                )}
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 text-xs">
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Series</span><strong className="block text-lg">{forecastBacktestData.series_count}</strong></div>
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Eligible</span><strong className="block text-lg">{forecastBacktestData.eligible_series_count}</strong></div>
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Series stale</span><strong className="block text-lg">{forecastBacktestData.stale_series_count ?? '-'}</strong></div>
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Observasi terakhir</span><strong className="block text-sm">{forecastBacktestData.latest_observation_date || '-'}</strong></div>
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Paid orders</span><strong className="block text-lg">{forecastBacktestData.paid_order_count ?? '-'}</strong></div>
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Paid items</span><strong className="block text-lg">{forecastBacktestData.paid_order_item_count ?? '-'}</strong></div>
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Invalid quantity</span><strong className="block text-lg">{forecastDependencyMetadata?.invalid_quantity_item_count ?? '-'}</strong></div>
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Missing unit</span><strong className="block text-lg">{forecastDependencyMetadata?.missing_unit_item_count ?? '-'}</strong></div>
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Missing menu ID</span><strong className="block text-lg">{forecastDependencyMetadata?.missing_menu_id_item_count ?? '-'}</strong></div>
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Latest paid</span><strong className="block text-sm">{forecastBacktestData.latest_paid_date || '-'}</strong></div>
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Umur data</span><strong className="block text-lg">{forecastBacktestData.data_age_days ?? '-'} hari</strong></div>
                  <div className="rounded-2xl bg-stone-50 p-3"><span className="text-stone-500">Horizon</span><strong className="block text-lg">{forecastBacktestData.horizon_days ?? 7} hari</strong></div>
                </div>
                <details className="rounded-xl border border-stone-200 bg-white">
                  <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-stone-800">Lihat evaluasi backtest historis per model</summary>
                  <div className="overflow-x-auto border-t border-stone-100">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-stone-100 text-stone-700 text-[11px] font-bold">
                        <tr><th className="py-2 px-3">Metode</th><th className="py-2 px-3 text-right">MAE</th><th className="py-2 px-3 text-right">RMSE</th><th className="py-2 px-3 text-right">WAPE</th><th className="py-2 px-3 text-right">sMAPE</th><th className="py-2 px-3 text-right">Holdout</th></tr>
                      </thead>
                      <tbody className="divide-y divide-stone-100">
                        {Object.entries(forecastBacktestData.model_comparison || {}).map(([method, metric]: [string, any]) => (
                          <tr key={method}>
                            <td className="py-2 px-3 font-semibold">{method}</td>
                            <td className="py-2 px-3 text-right font-mono">{metric.mae}</td>
                            <td className="py-2 px-3 text-right font-mono">{metric.rmse}</td>
                            <td className="py-2 px-3 text-right font-mono">{metric.wape_percent == null ? 'N/A' : `${metric.wape_percent}%`}</td>
                            <td className="py-2 px-3 text-right font-mono">{metric.smape_percent == null ? 'N/A' : `${metric.smape_percent}%`}</td>
                            <td className="py-2 px-3 text-right font-mono">{metric.holdout_points}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p className="px-3 py-2 text-[11px] text-stone-500">Metrik ini adalah hasil holdout historis. Data stale atau error tinggi tidak layak dipakai sebagai forecast operasional.</p>
                  </div>
                </details>
                {(forecastBacktestData.warnings || []).length > 0 && (
                  <details className="rounded-xl border border-amber-200 bg-amber-50 text-xs text-amber-950">
                    <summary className="cursor-pointer px-4 py-3 font-semibold">Data quality: {forecastBacktestData.warnings.length} peringatan menu (buka rincian)</summary>
                    <ul className="max-h-56 space-y-1 overflow-y-auto border-t border-amber-200 px-4 py-3">{(forecastBacktestData.warnings || []).map((warning: string) => <li key={warning}>{warning}</li>)}</ul>
                  </details>
                )}
              </>
            ) : (
              <div className="rounded-2xl bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-900">
                Forecast backtest live belum tersedia. Tidak ada angka simulasi yang ditampilkan sebagai pengganti.
              </div>
            )}
          </div>

          {/* Forecast headline metrics: stale evidence never reads as an active recommendation. */}
          <section className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-100 px-5 py-4">
              <div>
                <p className="text-sm font-bold text-stone-900">Ringkasan forecast</p>
                <p className="mt-0.5 text-xs text-stone-500">Metrik operasional hanya aktif saat sumber live lolos freshness gate.</p>
              </div>
              <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-bold ${forecastIsOperational ? 'bg-emerald-50 text-emerald-800' : forecastIsDemo ? 'bg-violet-50 text-violet-800' : 'bg-red-50 text-red-800'}`}>
                <span className={`size-2 rounded-full ${forecastIsOperational ? 'bg-emerald-500' : forecastIsDemo ? 'bg-violet-500' : 'bg-red-500'}`} />
                {forecastIsOperational ? 'LIVE · OPERASIONAL' : forecastIsDemo ? 'SEED · BUKAN TRANSAKSI LIVE' : `DITAHAN · ${forecastBacktestData?.status || 'DATA TIDAK TERSEDIA'}`}
              </span>
            </div>
            <div className="grid grid-cols-1 divide-y divide-stone-100 sm:grid-cols-3 sm:divide-x sm:divide-y-0">
              <div className="px-5 py-4">
                <p className="text-xs font-semibold text-stone-500">Total forecast {forecastHorizon === 7 ? 'mingguan' : 'bulanan'}</p>
                <p className={`mt-2 text-2xl font-bold tracking-tight ${forecastCanDisplay ? 'text-stone-950' : 'text-stone-300'}`}>
                  {forecastPeriodTotal !== null ? `${forecastPeriodTotal.toFixed(0)} porsi` : '—'}
                </p>
                <p className="mt-1 text-xs text-stone-500">{forecastIsOperational ? 'Proyeksi dari data live' : forecastIsDemo ? 'Proyeksi dataset seed' : 'Menunggu data live yang segar'}</p>
              </div>
              <div className="px-5 py-4">
                <p className="text-xs font-semibold text-stone-500">Model terpilih</p>
                <p className={`mt-2 break-words font-mono text-lg font-bold ${forecastCanDisplay ? 'text-[#8f1d2c]' : 'text-stone-300'}`}>
                  {selectedForecastModel}
                </p>
                <p className="mt-1 text-xs text-stone-500">Berdasarkan MAE agregat holdout</p>
              </div>
              <div className="px-5 py-4">
                <p className="text-xs font-semibold text-stone-500">WAPE holdout</p>
                <p className={`mt-2 font-mono text-2xl font-bold ${forecastCanDisplay ? 'text-[#8f1d2c]' : 'text-stone-300'}`}>
                  {selectedForecastMetrics?.wape_percent == null ? '—' : `${selectedForecastMetrics.wape_percent}%`}
                </p>
                <p className="mt-1 text-xs text-stone-500">{forecastIsOperational ? 'Error relatif agregat model terpilih' : forecastIsDemo ? 'Evaluasi dataset seed, bukan akurasi produksi' : 'Metrik operasional disembunyikan karena data stale'}</p>
              </div>
            </div>
            <div className="flex flex-wrap items-start gap-x-6 gap-y-2 border-t border-stone-100 bg-stone-50/70 px-5 py-3 text-xs text-stone-600">
              <span className="font-semibold text-stone-700">Kontrak data</span>
              <code className="max-w-full whitespace-normal break-words font-mono text-[11px]">{forecastBacktestData?.quantity_contract || 'Belum tersedia'}</code>
              <span className="sm:ml-auto">Interval: 80% · Status sumber: {forecastIsDemo ? 'SEED PREVIEW' : forecastBacktestData?.status || 'unavailable'}</span>
            </div>
          </section>

          {historicalWeekdayRows.length > 0 && (
            <section className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
              <div className="border-b border-stone-100 px-5 py-4">
                <h4 className="text-sm font-bold text-stone-900">Menu unggulan menurut hari</h4>
                <p className="mt-1 text-xs text-stone-500">
                  Rata-rata demand historis per hari dan menu, berdasarkan transaksi sampai {forecastBacktestData.latest_observation_date || 'tanggal terakhir tersedia'}.
                  {!forecastIsOperational && !forecastIsDemo ? ' Ini acuan historis, bukan forecast operasional.' : ''}
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-stone-50 text-[11px] uppercase tracking-wide text-stone-500"><tr><th className="px-5 py-3">Hari</th><th className="px-5 py-3">Menu yang paling sering diminati</th><th className="px-5 py-3 text-right">Rata-rata / hari itu</th></tr></thead>
                  <tbody className="divide-y divide-stone-100">{historicalWeekdayRows.map((day: any) => <tr key={`${day.weekday}-${day.unit}`} className="align-top hover:bg-rose-50/40"><td className="whitespace-nowrap px-5 py-3 font-semibold text-stone-800">{day.weekday}</td><td className="px-5 py-3"><ol className="space-y-1">{day.menus.slice(0, 3).map((menu: any, index: number) => <li key={menu.series_key} className="text-xs text-stone-700"><span className="mr-2 inline-flex size-5 items-center justify-center rounded-full bg-rose-50 font-bold text-[#8f1d2c]">{index + 1}</span>{menu.label}<span className="ml-2 text-stone-400">({menu.observed_days} hari observasi)</span></li>)}</ol></td><td className="whitespace-nowrap px-5 py-3 text-right font-mono font-bold text-[#8f1d2c]">{day.menus[0]?.average_quantity?.toFixed(1) || '—'} {day.unit}</td></tr>)}</tbody>
                </table>
              </div>
            </section>
          )}

          {forecastCanDisplay && (
            <section className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
              <div className="border-b border-stone-100 px-5 py-4">
                <h4 className="text-sm font-bold text-stone-900">Rekomendasi menu per hari</h4>
                <p className="mt-1 text-xs text-stone-500">Perkiraan total dan tiga menu dengan demand tertinggi untuk tiap tanggal.</p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-stone-50 text-[11px] uppercase tracking-wide text-stone-500"><tr><th className="px-5 py-3">Hari / tanggal</th><th className="px-5 py-3 text-right">Total demand</th><th className="px-5 py-3">Rekomendasi menu</th></tr></thead>
                  <tbody className="divide-y divide-stone-100">{forecastDailyTotals.map((day: any) => <tr key={day.date} className="align-top hover:bg-rose-50/40"><td className="whitespace-nowrap px-5 py-3 font-semibold text-stone-800">{new Date(`${day.date}T12:00:00`).toLocaleDateString('id-ID', { weekday: 'long', day: 'numeric', month: 'short' })}</td><td className="whitespace-nowrap px-5 py-3 text-right font-mono font-bold text-[#8f1d2c]">{day.total.toFixed(0)} porsi</td><td className="px-5 py-3"><ol className="space-y-1">{day.recommendations.map((menu: any, index: number) => <li key={menu.label} className="text-xs text-stone-700"><span className="mr-2 inline-flex size-5 items-center justify-center rounded-full bg-rose-50 font-bold text-[#8f1d2c]">{index + 1}</span>{menu.label}<span className="ml-2 font-mono font-semibold text-stone-500">{menu.quantity.toFixed(0)} {menu.unit}</span></li>)}</ol></td></tr>)}</tbody>
                </table>
              </div>
            </section>
          )}

          {forecastCanDisplay && (
            <section className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
              <div className="flex flex-wrap items-end justify-between gap-2 border-b border-stone-100 px-5 py-4">
                <div>
                  <h4 className="text-sm font-bold text-stone-900">Rencana demand per menu</h4>
                  <p className="mt-1 text-xs text-stone-500">Jumlah dijumlahkan untuk horizon {forecastHorizon} hari; rentang bawah/atas memakai interval model 80%.</p>
                </div>
                {forecastIsDemo && <span className="rounded-full bg-violet-50 px-3 py-1 text-[10px] font-bold text-violet-800">DATA SEED · PREVIEW</span>}
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-stone-50 text-[11px] uppercase tracking-wide text-stone-500"><tr><th className="px-5 py-3">Menu</th><th className="px-5 py-3 text-right">Perkiraan</th><th className="px-5 py-3 text-right">Rentang 80%</th><th className="px-5 py-3">Model</th></tr></thead>
                  <tbody className="divide-y divide-stone-100">{forecastMenuTotals.map((series: any) => <tr key={series.series_key} className="hover:bg-rose-50/40"><td className="px-5 py-3 font-semibold text-stone-800">{series.label}</td><td className="px-5 py-3 text-right font-mono font-bold text-[#8f1d2c]">{series.period_quantity.toFixed(0)} {series.unit}</td><td className="px-5 py-3 text-right font-mono text-xs text-stone-600">{series.period_lower.toFixed(0)}–{series.period_upper.toFixed(0)} {series.unit}</td><td className="px-5 py-3 text-xs text-stone-600">{series.forecast?.[0]?.method || '—'}</td></tr>)}</tbody>
                </table>
              </div>
            </section>
          )}

          </>)}
          {subTab === 'supply_chain' && (<>
          {/* Mathematical Formulas Banner */}
          <div className="p-4 rounded-3xl bg-amber-500/10 border border-amber-300 text-amber-950 space-y-2 text-xs">
            <div className="flex items-center gap-2 font-black text-sm text-amber-900">
              <Calculator className="size-4.5 text-amber-700" />
              <span>Rumus Machine Learning & Manajemen Persediaan Bahan Baku (BOM Explosion)</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
              <div className="bg-white/80 p-3 rounded-2xl border border-amber-200 space-y-1">
                <span className="font-bold text-amber-900 block">1. Safety Stock (Stok Pengaman):</span>
                <p className="font-mono text-[11px] text-amber-950">
                  SS = Z × σd × √(Lead Time)
                </p>
                <p className="text-[10px] text-stone-500">
                  Z = 1.65 (layanan 95%); lead time harus berasal dari supplier aktif.
                </p>
              </div>

              <div className="bg-white/80 p-3 rounded-2xl border border-amber-200 space-y-1">
                <span className="font-bold text-amber-900 block">2. Reorder Point (Titik Pemesanan Kembali):</span>
                <p className="font-mono text-[11px] text-amber-950">
                  ROP = (Kebutuhan Harian Rata-rata × Lead Time) + Safety Stock
                </p>
                <p className="text-[10px] text-stone-500">
                  Stok &lt; ROP hanya menjadi rekomendasi; PO tidak dibuat otomatis.
                </p>
              </div>
            </div>
          </div>

          {/* Ingredients ROP Table */}
          <div className="bg-white rounded-3xl border border-stone-200/90 p-5 shadow-2xs space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-extrabold text-base text-stone-900 flex items-center gap-2">
                  <Layers className="size-4.5 text-emerald-700" />
                  Kalkulasi Stok Pengaman & Reorder Point (ROP) Bahan Baku
                </h3>
                <p className="text-xs text-stone-500 mt-0.5">
                  Dihitung dari pesanan lunas, konversi resep katering, dan waktu tunggu pengiriman supplier.
                </p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead className="bg-[#14213D] text-white text-[11px] font-bold">
                  <tr>
                    <th className="py-3 px-3">Bahan Baku</th>
                    <th className="py-3 px-2.5 text-right">Stok Fisik</th>
                    <th className="py-3 px-2.5 text-right">Konsumsi/hr (d)</th>
                    <th className="py-3 px-2.5 text-right">Safety Stock (SS)</th>
                    <th className="py-3 px-2.5 text-right bg-blue-900/60">Reorder Point (ROP)</th>
                    <th className="py-3 px-2.5 text-center">Status Gudang</th>
                    <th className="py-3 px-2.5 text-right">Shortage / Target</th>
                    <th className="py-3 px-3 text-center">Tindakan PO</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 font-mono">
                  {inventoryReplenishmentData?.status === 'OK' && replenishmentItems.length > 0 ? (
                    replenishmentItems.map((item: any) => (
                      <tr key={item.ingredient_id}>
                        <td className="py-3 px-3 font-sans font-semibold">{item.ingredient_name}</td>
                        <td className="py-3 px-2.5 text-right">{item.current_stock} {item.unit}</td>
                        <td className="py-3 px-2.5 text-right">{item.daily_demand_average}</td>
                        <td className="py-3 px-2.5 text-right">{item.safety_stock}</td>
                        <td className="py-3 px-2.5 text-right bg-blue-50">{item.reorder_point_rop}</td>
                        <td className="py-3 px-2.5 text-center">
                          <Badge className={cn('text-[10px] border-none', item.status === 'REORDER_REQUIRED' ? 'bg-rose-100 text-rose-800' : 'bg-emerald-100 text-emerald-800')}>
                            {item.status}
                          </Badge>
                        </td>
                        <td className="py-3 px-2.5 text-right">{item.shortage_quantity} {item.unit}</td>
                        <td className="py-3 px-3 text-center text-stone-500 font-sans">Manual approval</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={8} className="py-6 px-3 text-center text-xs text-stone-500 font-sans">
                        {inventoryReplenishmentData ? (
                          <>
                            SS/ROP ditahan: status <strong>{inventoryReplenishmentData.status}</strong>, forecast <strong>{inventoryReplenishmentData.forecast_status || '-'}</strong>.
                            {' '}BOM siap {inventoryReplenishmentData.readiness?.bom_ready_menu_count || 0}/{inventoryReplenishmentData.readiness?.forecast_menu_count || 0} menu; tidak ada angka simulasi.
                          </>
                        ) : (
                          'Inventory replenishment live belum tersedia. Tidak ada angka simulasi yang ditampilkan sebagai pengganti.'
                        )}
                      </td>
                    </tr>
                  )}
                </tbody>
          </table>
        </div>
      </div>
          </>)}
    </div>
  )}

    </div>
  )
}
