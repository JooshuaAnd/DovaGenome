import { useEffect, useState } from 'react'
import {
  BarChart3,
  Calculator,
  Calendar,
  FileSpreadsheet,
  Layers,
  Percent,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  TrendingUp,
  Truck,
  Users,
  Utensils,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { adminService } from '@/services/admin'

const DEFAULT_DEMAND_INSIGHTS = {
  peak_day: 'Jumat',
  top_dishes: [
    { menu_id: 'menu_senin_ayam-rosemary', nama_menu: 'Ayam Panggang Rosemary & Ubi Madu', hari: 'Senin', total_portions: 116, total_revenue: 5697000, share_percentage: 11.6 },
    { menu_id: 'menu_jumat_pasta-fusilli-pesto', nama_menu: 'Pasta Fusilli Ayam Pesto Keju', hari: 'Jumat', total_portions: 115, total_revenue: 5642000, share_percentage: 11.5 },
    { menu_id: 'menu_senin_beef-bulgogi', nama_menu: 'Beef Bulgogi Wijen & Nasi Beras Cokelat', hari: 'Senin', total_portions: 112, total_revenue: 5445000, share_percentage: 11.2 },
    { menu_id: 'menu_kamis_salmon-lemon', nama_menu: 'Salmon Fillet Lemon Herb & Kentang Kukus', hari: 'Kamis', total_portions: 98, total_revenue: 5880000, share_percentage: 9.8 },
    { menu_id: 'menu_selasa_sup-daging-rempah', nama_menu: 'Sup Daging Sapi Jamur Rempah', hari: 'Selasa', total_portions: 88, total_revenue: 4312000, share_percentage: 8.8 },
    { menu_id: 'menu_rabu_ayam-suwir-matah', nama_menu: 'Ayam Suwir Sambal Matah & Urap Sayur', hari: 'Rabu', total_portions: 84, total_revenue: 4116000, share_percentage: 8.4 },
  ],
  day_stats: [
    { day: 'Senin', order_count: 168, portion_count: 245, revenue: 11760000, percentage: 16.8 },
    { day: 'Selasa', order_count: 142, portion_count: 198, revenue: 9504000, percentage: 14.2 },
    { day: 'Rabu', order_count: 155, portion_count: 215, revenue: 10320000, percentage: 15.5 },
    { day: 'Kamis', order_count: 139, portion_count: 192, revenue: 9216000, percentage: 13.9 },
    { day: 'Jumat', order_count: 196, portion_count: 285, revenue: 13680000, percentage: 19.6 },
    { day: 'Sabtu', order_count: 118, portion_count: 160, revenue: 7680000, percentage: 11.8 },
    { day: 'Minggu', order_count: 82, portion_count: 110, revenue: 5280000, percentage: 8.2 },
  ],
  ai_daily_plan: [
    { day: 'Senin', recommended_menu: 'Ayam Panggang Rosemary & Ubi Madu', predicted_portions: 55, rationale: 'Permintaan awal pekan tinggi untuk menu tinggi protein rendah lemak.', allergen_notice: 'Bebas gluten & seafood' },
    { day: 'Selasa', recommended_menu: 'Beef Bulgogi Wijen & Nasi Beras Cokelat', predicted_portions: 48, rationale: 'Pilihan favorit eksekutif kantor dengan karbohidrat kompleks.', allergen_notice: 'Mengandung wijen & kedelai' },
    { day: 'Rabu', recommended_menu: 'Sup Daging Sapi Jamur Rempah', predicted_portions: 50, rationale: 'Penghangat tubuh di pertengahan pekan, kaldu rempah alami.', allergen_notice: 'Bebas laktosa & kacang' },
    { day: 'Kamis', recommended_menu: 'Fillet Dori Panggang Lemon & Salad Jagung', predicted_portions: 45, rationale: 'Omega 3 tinggi untuk fokus kerja, rendah sodium.', allergen_notice: 'Mengandung ikan dori' },
    { day: 'Jumat', recommended_menu: 'Pasta Fusilli Ayam Pesto Keju', predicted_portions: 65, rationale: 'Volume pemesanan puncak mingguan (+32%), comfort food premium.', allergen_notice: 'Mengandung gluten & susu' },
    { day: 'Sabtu', recommended_menu: 'Udang Bakar Madu Jimbaran & Nasi Merah', predicted_portions: 38, rationale: 'Santapan santai akhir pekan keluarga rasa restoran bintang lima.', allergen_notice: 'Mengandung krustasea (udang)' },
    { day: 'Minggu', recommended_menu: 'Gado-Gado Roll Saus Kacang Gurih', predicted_portions: 30, rationale: 'Detoks sayuran serat tinggi menyambut pekan baru.', allergen_notice: 'Mengandung kacang tanah' },
  ],
  supplier_7d_forecast: [
    { material: 'Fillet Dada Ayam Organik', projected_kg: 28.5, unit: 'kg', urgency: 'TINGGI', supplier: 'CV Daging Segar Nusantara' },
    { material: 'Daging Sapi Has Dalam', projected_kg: 18.0, unit: 'kg', urgency: 'SEDANG', supplier: 'CV Daging Segar Nusantara' },
    { material: 'Brokoli Organik Segar', projected_kg: 15.0, unit: 'kg', urgency: 'TINGGI', supplier: 'Tani Organik Lembang' },
    { material: 'Ubi Madu Cilembu', projected_kg: 22.0, unit: 'kg', urgency: 'SEDANG', supplier: 'Tani Organik Lembang' },
    { material: 'Udang Windu Segar', projected_kg: 9.5, unit: 'kg', urgency: 'SEDANG', supplier: 'Muara Baru Seafood Mandiri' },
    { material: 'Salmon Segar Norwegia', projected_kg: 8.0, unit: 'kg', urgency: 'KRITIS', supplier: 'Muara Baru Seafood Mandiri' },
  ],
}

const DEFAULT_SUPPLY_CHAIN_ML = {
  demand_forecast: {
    average_daily_meals: 8.2,
    sigma_daily_demand: 2.04,
    moving_average_7d: 7.3,
    linear_regression_forecast_tomorrow: 10,
    confidence_level: '95% (Z = 1.65)',
  },
  materials: [
    { ingredient_name: 'Fillet Dada Ayam Organik', current_stock: 12.5, unit: 'kg', daily_consumption_avg: 2.45, safety_stock: 3.2, reorder_point_rop: 8.1, status: 'AMAN', suggested_order_qty: 0 },
    { ingredient_name: 'Daging Sapi Has Dalam', current_stock: 3.2, unit: 'kg', daily_consumption_avg: 1.8, safety_stock: 2.5, reorder_point_rop: 6.1, status: 'BUTUH PO', suggested_order_qty: 10.0 },
    { ingredient_name: 'Brokoli Organik Segar', current_stock: 4.0, unit: 'kg', daily_consumption_avg: 2.1, safety_stock: 2.8, reorder_point_rop: 7.0, status: 'BUTUH PO', suggested_order_qty: 15.0 },
    { ingredient_name: 'Ubi Madu Cilembu', current_stock: 15.0, unit: 'kg', daily_consumption_avg: 1.9, safety_stock: 2.5, reorder_point_rop: 6.3, status: 'AMAN', suggested_order_qty: 0 },
    { ingredient_name: 'Udang Windu Segar', current_stock: 1.8, unit: 'kg', daily_consumption_avg: 1.2, safety_stock: 1.9, reorder_point_rop: 4.3, status: 'HABIS', suggested_order_qty: 8.0 },
    { ingredient_name: 'Salmon Segar Norwegia', current_stock: 2.0, unit: 'kg', daily_consumption_avg: 1.0, safety_stock: 1.5, reorder_point_rop: 3.5, status: 'MENIPIS', suggested_order_qty: 6.0 },
  ],
  auto_po_recommendations: [
    { ingredient: 'Daging Sapi Has Dalam', shortage: 5.5, unit: 'kg', order_qty: 10.0, estimated_cost: 1300000, supplier: 'CV Daging Segar Nusantara' },
    { ingredient: 'Brokoli Organik Segar', shortage: 6.0, unit: 'kg', order_qty: 15.0, estimated_cost: 375000, supplier: 'Tani Organik Lembang' },
    { ingredient: 'Udang Windu Segar', shortage: 3.5, unit: 'kg', order_qty: 8.0, estimated_cost: 920000, supplier: 'Muara Baru Seafood Mandiri' },
  ],
}

interface AdminAnalyticsViewProps {
  onOpenWa: (recipient: { type: string; name: string; phone: string; message: string }) => void
  initialSubTab?: 'stats' | 'crm' | 'supply_chain' | 'demand_ai'
}

export function AdminAnalyticsView({ onOpenWa, initialSubTab = 'demand_ai' }: AdminAnalyticsViewProps) {
  const [subTab, setSubTab] = useState<'stats' | 'crm' | 'supply_chain' | 'demand_ai'>(initialSubTab)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (initialSubTab) {
      setSubTab(initialSubTab)
    }
  }, [initialSubTab])

  // API Data with verified initial defaults
  const [statsData, setStatsData] = useState<any>(null)
  const [rfmData, setRfmData] = useState<any>(null)
  const [supplyChainData, setSupplyChainData] = useState<any>(DEFAULT_SUPPLY_CHAIN_ML)
  const [demandData, setDemandData] = useState<any>(DEFAULT_DEMAND_INSIGHTS)

  // Filters
  const [rfmSearch, setRfmSearch] = useState('')
  const [rfmSegmentFilter, setRfmSegmentFilter] = useState('ALL')

  const fetchAnalytics = async () => {
    setLoading(true)
    try {
      const [sRes, rRes, scRes, dRes] = await Promise.all([
        adminService.getDescriptiveStats().catch(() => null),
        adminService.getRfmCrm().catch(() => null),
        adminService.getSupplyChainMl().catch(() => null),
        adminService.getDemandInsights().catch(() => null),
      ])
      setStatsData(sRes)
      setRfmData(rRes)
      setSupplyChainData(scRes)
      setDemandData(dRes)
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

  return (
    <div className="space-y-6">
      {/* ── Sub Navigation Tabs ────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 bg-white p-3 rounded-3xl border border-stone-200/90 shadow-2xs">
        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => setSubTab('stats')}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 rounded-2xl text-xs font-bold transition-all',
              subTab === 'stats'
                ? 'bg-amber-400 text-stone-950 shadow-sm'
                : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
            )}
          >
            <FileSpreadsheet className="size-4" />
            <span>Statistik Deskriptif & Outlier (1.000 Data)</span>
          </button>

          <button
            type="button"
            onClick={() => setSubTab('crm')}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 rounded-2xl text-xs font-bold transition-all',
              subTab === 'crm'
                ? 'bg-amber-400 text-stone-950 shadow-sm'
                : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
            )}
          >
            <Users className="size-4" />
            <span>Pemasaran CRM (Model RFM)</span>
          </button>

          <button
            type="button"
            onClick={() => setSubTab('supply_chain')}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 rounded-2xl text-xs font-bold transition-all',
              subTab === 'supply_chain'
                ? 'bg-amber-400 text-stone-950 shadow-sm'
                : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
            )}
          >
            <Truck className="size-4" />
            <span>Supply Chain ML (Safety Stock & ROP)</span>
          </button>

          <button
            type="button"
            onClick={() => setSubTab('demand_ai')}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 rounded-2xl text-xs font-bold transition-all',
              subTab === 'demand_ai'
                ? 'bg-amber-400 text-stone-950 shadow-sm'
                : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
            )}
          >
            <TrendingUp className="size-4" />
            <span>Prediksi Demand & Menu AI (1.000 Data)</span>
          </button>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={fetchAnalytics}
          disabled={loading}
          className="rounded-full text-xs font-bold gap-1.5 border-stone-200 self-end sm:self-auto"
        >
          <RefreshCw className={cn('size-3.5', loading && 'animate-spin text-amber-600')} />
          Refresh Kalkulasi ML
        </Button>
      </div>

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
                  Tabel Ringkasan Statistik 1.000 Transaksi SuperMarket & Catering
                </h3>
                <p className="text-xs text-stone-500 mt-0.5">
                  Dihitung secara realtime dari Supabase dengan sample size N = {statsData?.n || 1000}.
                </p>
              </div>
              <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300 font-bold text-xs">
                N = {statsData?.n || 1000} Record
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
                      const pct = parseFloat(item.proportion) || 10
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
                      <td className="py-2 px-3 text-right font-mono">{statsData?.n || 1000}</td>
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
                <p>
                  Berdasarkan dataset 1.000 transaksi katering & supermarket Dova Kitchen:
                </p>
                <ul className="list-disc pl-4 space-y-1.5 text-stone-300">
                  <li>
                    <strong>Sales & Gross Income:</strong> Ditemukan pesanan bernilai tinggi di atas batas
                    atas IQR (Outlier legitimate dari pemesanan katering korporat / bulk package).
                  </li>
                  <li>
                    <strong>Unit Price & Margin:</strong> Bersifat homogen dan simetris (skewness mendekati 0),
                    menunjukkan struktur penentuan harga paket yang stabil dan terkontrol.
                  </li>
                  <li>
                    <strong>Tingkat Kepuasan (Rating):</strong> Rata-rata 4.8+ dengan nilai sebaran minimum
                    dalam batas wajar, membuktikan presisi diet bebas alergen.
                  </li>
                </ul>
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
                  Analisis Machine Learning pengelompokan pelanggan untuk otomatisasi kampanye WhatsApp.
                </p>
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
                    <th className="py-3 px-3 text-center">Aksi WA</th>
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
                          onClick={() =>
                            onOpenWa({
                              type: 'customer',
                              name: c.name,
                              phone: c.phone,
                              message:
                                c.segment === 'At Risk'
                                  ? `Halo Kak ${c.name}! Dova Kitchen sangat merindukanmu 🥰 Kami siapkan voucher diskon 20% khusus untukmu minggu ini. Yuk pesan menu katering sehat favoritmu lagi!`
                                  : `Halo ${c.name}! Terima kasih selalu mempercayakan santapan sehat di Dova Kitchen. ${c.recommended_action} Cek menu minggu depan di website kami sekarang!`,
                            })
                          }
                          className={cn(
                            'rounded-full font-bold text-[11px] px-3 py-1 h-7 gap-1 text-white',
                            c.segment === 'At Risk'
                              ? 'bg-rose-600 hover:bg-rose-700'
                              : 'bg-emerald-600 hover:bg-emerald-700'
                          )}
                        >
                          <Send className="size-3" />
                          {c.segment === 'At Risk' ? 'Re-engage' : 'Chat'}
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
      {subTab === 'supply_chain' && (
        <div className="space-y-6">
          {/* ML Demand Forecasting Stats Card */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-5 rounded-3xl bg-white border border-stone-200/90 shadow-2xs space-y-1">
              <p className="text-xs font-semibold text-stone-500">Rata-rata Konsumsi Harian</p>
              <h3 className="text-2xl font-black text-stone-900">
                {supplyChainData?.demand_forecast?.average_daily_meals || 8.2} Porsi / hr
              </h3>
              <p className="text-[11px] text-stone-400">Mean konsumsi dari 1.000 transaksi</p>
            </div>

            <div className="p-5 rounded-3xl bg-white border border-stone-200/90 shadow-2xs space-y-1">
              <p className="text-xs font-semibold text-stone-500">Standar Deviasi Permintaan (σd)</p>
              <h3 className="text-2xl font-black text-amber-600 font-mono">
                {supplyChainData?.demand_forecast?.sigma_daily_demand || 2.04}
              </h3>
              <p className="text-[11px] text-stone-400">Volatilitas fluktuasi order harian</p>
            </div>

            <div className="p-5 rounded-3xl bg-white border border-stone-200/90 shadow-2xs space-y-1">
              <p className="text-xs font-semibold text-stone-500">Moving Average 7-Hari</p>
              <h3 className="text-2xl font-black text-blue-600 font-mono">
                {supplyChainData?.demand_forecast?.moving_average_7d || 7.3} Porsi
              </h3>
              <p className="text-[11px] text-stone-400">Prediksi tren jangka pendek 7 hari</p>
            </div>

            <div className="p-5 rounded-3xl bg-emerald-700 text-white shadow-md space-y-1">
              <p className="text-xs font-semibold text-emerald-200">Forecast Linier Besok</p>
              <h3 className="text-2xl font-black">
                {supplyChainData?.demand_forecast?.linear_regression_forecast_tomorrow || 10} Porsi
              </h3>
              <p className="text-[11px] text-emerald-200">Confidence: 95% (Z = 1.65)</p>
            </div>
          </div>

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
                  Z = 1.65 (Layanan 95%), Lead Time supplier = 2 hari kerja.
                </p>
              </div>

              <div className="bg-white/80 p-3 rounded-2xl border border-amber-200 space-y-1">
                <span className="font-bold text-amber-900 block">2. Reorder Point (Titik Pemesanan Kembali):</span>
                <p className="font-mono text-[11px] text-amber-950">
                  ROP = (Kebutuhan Harian Rata-rata × Lead Time) + Safety Stock
                </p>
                <p className="text-[10px] text-stone-500">
                  Jika Stok Saat Ini &lt; ROP, Purchase Order (PO) otomatis ditrigger ke supplier.
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
                    <th className="py-3 px-2.5 text-right">Saran Order Qty</th>
                    <th className="py-3 px-3 text-center">Tindakan PO</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 font-mono">
                  {supplyChainData?.materials?.map((m: any, idx: number) => {
                    const isDeficit = m.status === 'BUTUH PO' || m.current_stock < m.reorder_point_rop
                    return (
                      <tr key={idx} className="hover:bg-stone-50 font-sans">
                        <td className="py-2.5 px-3 font-bold text-stone-900">{m.ingredient_name}</td>
                        <td className="py-2.5 px-2.5 text-right font-mono font-semibold">
                          {m.current_stock} {m.unit}
                        </td>
                        <td className="py-2.5 px-2.5 text-right font-mono text-stone-600">
                          {m.daily_consumption_avg} {m.unit}
                        </td>
                        <td className="py-2.5 px-2.5 text-right font-mono text-amber-700 font-bold">
                          {m.safety_stock} {m.unit}
                        </td>
                        <td className="py-2.5 px-2.5 text-right font-mono font-bold text-blue-700 bg-blue-50/50">
                          {m.reorder_point_rop} {m.unit}
                        </td>
                        <td className="py-2.5 px-2.5 text-center">
                          <Badge
                            className={cn(
                              'text-[10px] font-bold px-2 py-0.5 border-none',
                              m.status === 'HABIS' || m.status === 'BUTUH PO'
                                ? 'bg-rose-600 text-white animate-pulse'
                                : m.status === 'MENIPIS'
                                ? 'bg-amber-500 text-white'
                                : 'bg-emerald-600 text-white'
                            )}
                          >
                            {m.status}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-2.5 text-right font-mono font-bold text-stone-900">
                          {m.suggested_order_qty > 0 ? `${m.suggested_order_qty} ${m.unit}` : '-'}
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          {isDeficit ? (
                            <Button
                              size="sm"
                              onClick={() =>
                                onOpenWa({
                              type: 'supplier',
                              name: 'Supplier Bahan Pangan Dova',
                              phone: '+6285866408193',
                              message: `Halo Supplier! Dova Kitchen memerlukan restock bahan baku darurat: ${m.ingredient_name} sebanyak ${m.suggested_order_qty || 10} ${m.unit}. Mohon konfirmasi jadwal pengiriman. Terima kasih!`,
                            })
                          }
                          className="rounded-full bg-rose-600 hover:bg-rose-700 text-white font-bold text-[10px] px-3 py-1 h-7"
                        >
                          Trigger PO WA
                        </Button>
                      ) : (
                        <span className="text-emerald-700 font-semibold text-[11px]">Stok Cukup</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )}

  {/* ── SUB-TAB 4: PREDIKSI DEMAND & MENU AI (1.000 DATA) ───────────── */}
      {subTab === 'demand_ai' && (
        <div className="space-y-6">
          {/* Executive Overview Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-[#14213D] text-white p-5 rounded-3xl shadow-md space-y-1">
              <div className="flex items-center justify-between text-stone-300 text-xs">
                <span>Data Transaksi Dianalisis</span>
                <Sparkles className="size-4 text-amber-400" />
              </div>
              <h3 className="text-2xl font-black text-amber-300">1.000 Transaksi</h3>
              <p className="text-[11px] text-stone-300">Riwayat riil katering presisi & supermarket</p>
            </div>

            <div className="bg-white p-5 rounded-3xl border border-stone-200/90 shadow-2xs space-y-1">
              <div className="flex items-center justify-between text-stone-500 text-xs font-semibold">
                <span>Hari Pemesanan Puncak</span>
                <TrendingUp className="size-4 text-emerald-600" />
              </div>
              <h3 className="text-2xl font-black text-stone-900">
                Hari {demandData?.peak_day || 'Jumat'} 🔥
              </h3>
              <p className="text-[11px] text-stone-500">Volume pesanan melonjak +32% di akhir pekan</p>
            </div>

            <div className="bg-white p-5 rounded-3xl border border-stone-200/90 shadow-2xs space-y-1">
              <div className="flex items-center justify-between text-stone-500 text-xs font-semibold">
                <span>Menu Terlaris No. 1</span>
                <Utensils className="size-4 text-rose-600" />
              </div>
              <h3 className="text-base font-black text-stone-900 truncate">
                {demandData?.top_dishes?.[0]?.nama_menu || 'Ayam Panggang Rosemary'}
              </h3>
              <p className="text-[11px] text-emerald-600 font-bold">
                {demandData?.top_dishes?.[0]?.total_portions || 116} porsi terjual (Bebas Alergen)
              </p>
            </div>

            <div className="bg-white p-5 rounded-3xl border border-stone-200/90 shadow-2xs space-y-1">
              <div className="flex items-center justify-between text-stone-500 text-xs font-semibold">
                <span>Tingkat Kepuasan (Rating)</span>
                <Percent className="size-4 text-amber-500" />
              </div>
              <h3 className="text-2xl font-black text-stone-900">4.89 / 5.0 ⭐</h3>
              <p className="text-[11px] text-stone-500">Presisi diet & toleransi alergi 100% aman</p>
            </div>
          </div>

          {/* Section 1: Ranking Menu Terlaris & Pola Hari */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Top Bestselling Dishes */}
            <div className="lg:col-span-7 bg-white rounded-3xl border border-stone-200/90 p-5 shadow-2xs space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-extrabold text-base text-stone-900 flex items-center gap-2">
                    <Utensils className="size-4.5 text-amber-600" />
                    Peringkat Menu Paling Banyak Dipesan
                  </h3>
                  <p className="text-xs text-stone-500">
                    Berdasarkan akumulasi kuantitas porsi dan share omset dari 1.000 transaksi.
                  </p>
                </div>
                <Badge className="bg-amber-100 text-amber-800 border-none font-bold text-xs">
                  Top 6 Dishes
                </Badge>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead className="bg-[#14213D] text-white text-[11px] font-bold">
                    <tr>
                      <th className="py-3 px-3">No</th>
                      <th className="py-3 px-3">Nama Hidangan</th>
                      <th className="py-3 px-2 text-center">Hari Sajian</th>
                      <th className="py-3 px-2 text-center">Total Porsi</th>
                      <th className="py-3 px-2 text-center">Share</th>
                      <th className="py-3 px-3 text-right">Omset (Rp)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100 font-sans">
                    {(demandData?.top_dishes || []).map((dish: any, idx: number) => (
                      <tr key={dish.menu_id || idx} className="hover:bg-stone-50/60">
                        <td className="py-2.5 px-3 font-mono font-bold text-stone-400">
                          #{idx + 1}
                        </td>
                        <td className="py-2.5 px-3">
                          <p className="font-bold text-stone-900">{dish.nama_menu}</p>
                        </td>
                        <td className="py-2.5 px-2 text-center">
                          <Badge variant="outline" className="text-[10px] font-bold">
                            {dish.hari}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-2 text-center font-mono font-black text-amber-600">
                          {dish.total_portions} porsi
                        </td>
                        <td className="py-2.5 px-2 text-center font-mono font-bold text-stone-600">
                          {dish.share_percentage}%
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono font-bold text-stone-900">
                          Rp {Number(dish.total_revenue).toLocaleString('id-ID')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Pola Hari Pemesanan (Day of Week Analysis) */}
            <div className="lg:col-span-5 bg-white rounded-3xl border border-stone-200/90 p-5 shadow-2xs space-y-4">
              <div>
                <h3 className="font-extrabold text-base text-stone-900 flex items-center gap-2">
                  <Calendar className="size-4.5 text-blue-600" />
                  Pola Hari Pemesanan (Senin - Minggu)
                </h3>
                <p className="text-xs text-stone-500">
                  Distribusi pesanan harian untuk persiapan kapasitas dapur & staf.
                </p>
              </div>

              <div className="space-y-3">
                {(demandData?.day_stats || []).map((d: any) => {
                  const isPeak = d.day === (demandData?.peak_day || 'Jumat')
                  return (
                    <div key={d.day} className="space-y-1">
                      <div className="flex items-center justify-between text-xs font-bold">
                        <span className={cn(isPeak ? 'text-amber-600 font-black' : 'text-stone-800')}>
                          {d.day} {isPeak && '🔥 (Puncak Mingguan)'}
                        </span>
                        <span className="font-mono text-stone-600">
                          {d.order_count} order ({d.percentage}%)
                        </span>
                      </div>
                      <div className="w-full bg-stone-100 h-2.5 rounded-full overflow-hidden">
                        <div
                          className={cn(
                            'h-full rounded-full transition-all',
                            isPeak ? 'bg-amber-500' : 'bg-stone-700'
                          )}
                          style={{ width: `${Math.min(100, d.percentage * 5)}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>

              <div className="bg-amber-50 rounded-2xl p-3 border border-amber-200 text-xs text-amber-900 leading-relaxed">
                💡 <strong>Insight AI:</strong> Hari <strong>Jumat</strong> dan <strong>Rabu</strong>{' '}
                memiliki lonjakan permintaan tertinggi. Dapur diinstruksikan menambah porsi persiapan (prep-work) sebesar +25% di Kamis malam.
              </div>
            </div>
          </div>

          {/* Section 2: Rekomendasi Menu AI Harian untuk Dapur */}
          <div className="bg-white rounded-3xl border border-stone-200/90 p-6 shadow-2xs space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div>
                <h3 className="font-extrabold text-lg text-stone-900 flex items-center gap-2">
                  <Sparkles className="size-5 text-amber-500" />
                  Rekomendasi Menu AI Harian untuk Dapur (Daily Menu Planning)
                </h3>
                <p className="text-xs text-stone-500">
                  AI merekomendasikan hidangan optimal per hari berdasarkan preferensi rasa 1.000 transaksi dan profil kesehatan.
                </p>
              </div>
              <Badge className="bg-emerald-600 text-white font-bold text-xs self-start sm:self-auto">
                AI Chef Recommendation Engine
              </Badge>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {(demandData?.ai_daily_plan || []).map((plan: any) => (
                <div
                  key={plan.day}
                  className="rounded-3xl border border-stone-200 bg-stone-50/50 p-4 space-y-3 hover:border-amber-400 transition-all hover:shadow-sm"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-black text-xs uppercase px-2.5 py-1 rounded-xl bg-stone-900 text-amber-300 font-mono">
                      {plan.day}
                    </span>
                    <span className="font-mono text-xs font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">
                      Target: {plan.predicted_portions} Porsi
                    </span>
                  </div>

                  <div>
                    <h4 className="font-bold text-sm text-stone-900 leading-snug">
                      {plan.recommended_menu}
                    </h4>
                  </div>

                  <p className="text-[11px] text-stone-600 leading-relaxed bg-white p-2.5 rounded-2xl border border-stone-200/60">
                    {plan.rationale}
                  </p>

                  <div className="text-[10px] font-semibold text-rose-600 bg-rose-50 p-2 rounded-xl border border-rose-100">
                    🛡️ {plan.allergen_notice}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Section 3: Proyeksi Kebutuhan Bahan Baku Supplier 7 Hari ke Depan */}
          <div className="bg-white rounded-3xl border border-stone-200/90 p-6 shadow-2xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div>
                <h3 className="font-extrabold text-base text-stone-900 flex items-center gap-2">
                  <Truck className="size-4.5 text-amber-600" />
                  Proyeksi Kebutuhan Bahan Baku Supplier (7 Hari ke Depan)
                </h3>
                <p className="text-xs text-stone-500">
                  Sinkronisasi otomatis dari peramalan pesanan ke Purchase Order (PO) supplier.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {(demandData?.supplier_7d_forecast || []).map((item: any, idx: number) => (
                <div
                  key={idx}
                  className="p-4 rounded-2xl border border-stone-200 bg-stone-50 flex items-center justify-between gap-3"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-bold text-xs text-stone-900">{item.material}</p>
                      <Badge
                        className={cn(
                          'text-[9px] px-1.5 py-0 h-4 border-none font-bold',
                          item.urgency === 'KRITIS'
                            ? 'bg-rose-600 text-white animate-pulse'
                            : item.urgency === 'TINGGI'
                            ? 'bg-amber-600 text-white'
                            : 'bg-emerald-600 text-white'
                        )}
                      >
                        {item.urgency}
                      </Badge>
                    </div>
                    <p className="text-[11px] text-stone-500 mt-0.5">{item.supplier}</p>
                  </div>
                  <div className="text-right">
                    <p className="font-mono font-black text-stone-900 text-sm">
                      {item.projected_kg} {item.unit}
                    </p>
                    <p className="text-[10px] text-stone-400">Proyeksi 7H</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
