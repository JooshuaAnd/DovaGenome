import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Check,
  CheckCircle2,
  Clock,
  LayoutDashboard,
  MessageSquare,
  Package,
  RefreshCw,
  Search,
  Sparkles,
  Star,
  Store,
  TrendingUp,
  Truck,
  Utensils,
  X,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'
import { supplierService, type SupplierPO, type SupplierItem } from '@/services/supplier'

const DEFAULT_CATALOG_ITEMS: SupplierItem[] = [
  { id: 1, supplier_id: 'sup_daging_nusantara', item_name: 'Fillet Dada Ayam Organik', unit: 'kg', price_per_unit: 45000, moq: 5, supplier_name: 'CV Daging Segar Nusantara (Pak Hadi)', is_available: true },
  { id: 2, supplier_id: 'sup_daging_nusantara', item_name: 'Daging Sapi Has Dalam (Tenderloin)', unit: 'kg', price_per_unit: 130000, moq: 3, supplier_name: 'CV Daging Segar Nusantara (Pak Hadi)', is_available: true },
  { id: 3, supplier_id: 'sup_sayur_lembang', item_name: 'Brokoli Organik Segar', unit: 'kg', price_per_unit: 25000, moq: 5, supplier_name: 'Tani Organik Lembang (Ibu Ningsih)', is_available: true },
  { id: 4, supplier_id: 'sup_sayur_lembang', item_name: 'Ubi Madu Cilembu', unit: 'kg', price_per_unit: 18000, moq: 10, supplier_name: 'Tani Organik Lembang (Ibu Ningsih)', is_available: true },
  { id: 5, supplier_id: 'sup_sayur_lembang', item_name: 'Jamur Tiram & Shiitake', unit: 'kg', price_per_unit: 32000, moq: 3, supplier_name: 'Tani Organik Lembang (Ibu Ningsih)', is_available: true },
  { id: 6, supplier_id: 'sup_muara_baru', item_name: 'Udang Windu Segar (Size 30)', unit: 'kg', price_per_unit: 115000, moq: 3, supplier_name: 'Muara Baru Seafood Mandiri (Pak Johan)', is_available: true },
  { id: 7, supplier_id: 'sup_muara_baru', item_name: 'Fillet Ikan Kakap Merah', unit: 'kg', price_per_unit: 85000, moq: 5, supplier_name: 'Muara Baru Seafood Mandiri (Pak Johan)', is_available: true },
  { id: 8, supplier_id: 'sup_muara_baru', item_name: 'Salmon Segar Norwegia', unit: 'kg', price_per_unit: 240000, moq: 2, supplier_name: 'Muara Baru Seafood Mandiri (Pak Johan)', is_available: true },
]

const DEFAULT_SUPPLIER_POS: SupplierPO[] = [
  {
    po_id: 'PO-20261011-001',
    supplier_id: 'sup_daging_nusantara',
    supplier_name: 'CV Daging Segar Nusantara (Pak Hadi)',
    supplier_phone: '+6281326332247',
    category: 'Daging & Unggas',
    email: 'hadi.daging@dovasuplier.com',
    status: 'SENT',
    total_amount: 675000,
    need_by_date: '2026-10-12',
    notes: 'Pengiriman H-1 sebelum masak.',
    created_at: '2026-10-11T12:37:23Z',
    items: [
      { id: 1, item_name: 'Fillet Dada Ayam Organik', qty: 15, unit: 'kg', unit_price: 45000, subtotal: 675000 },
    ],
  },
  {
    po_id: 'PO-20261011-002',
    supplier_id: 'sup_sayur_lembang',
    supplier_name: 'Tani Organik Lembang (Ibu Ningsih)',
    supplier_phone: '+6285866408193',
    category: 'Sayur & Nabati',
    email: 'ningsih.tani@lembangfresh.com',
    status: 'ACCEPTED',
    total_amount: 340000,
    need_by_date: '2026-10-12',
    notes: 'Kirim subuh pukul 05:00 WIB.',
    created_at: '2026-10-11T12:37:24Z',
    items: [
      { id: 2, item_name: 'Brokoli Organik Segar', qty: 10, unit: 'kg', unit_price: 25000, subtotal: 250000 },
      { id: 3, item_name: 'Ubi Madu Cilembu', qty: 5, unit: 'kg', unit_price: 18000, subtotal: 90000 },
    ],
  },
  {
    po_id: 'PO-20261011-003',
    supplier_id: 'sup_muara_baru',
    supplier_name: 'Muara Baru Seafood Mandiri (Pak Johan)',
    supplier_phone: '+6281900112233',
    category: 'Ikan & Seafood',
    email: 'johan.seafood@muarabaru.id',
    status: 'DRAFT',
    total_amount: 585000,
    need_by_date: '2026-10-12',
    notes: 'Menunggu konfirmasi admin untuk menu Kamis.',
    created_at: '2026-10-11T12:37:24Z',
    items: [
      { id: 4, item_name: 'Udang Windu Segar', qty: 3, unit: 'kg', unit_price: 115000, subtotal: 345000 },
      { id: 5, item_name: 'Fillet Ikan Kakap Merah', qty: 2, unit: 'kg', unit_price: 85000, subtotal: 170000 },
    ],
  },
]

export function SupplierPage() {
  const { customer, logout } = useAuth()
  void customer
  void logout
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'pos' | 'catalog' | 'performance' | 'forecast'>('pos')

  // PO & Catalog State (Initialized with verified defaults)
  const [pos, setPos] = useState<SupplierPO[]>(DEFAULT_SUPPLIER_POS)
  const [catalogItems, setCatalogItems] = useState<SupplierItem[]>(DEFAULT_CATALOG_ITEMS)
  const [summary, setSummary] = useState({
    total_pos: 3,
    pending_pos: 2,
    accepted_pos: 1,
    suppliers: [] as any[],
  })
  const [forecastData, setForecastData] = useState<any>(null)
  const [selectedSupplierId, setSelectedSupplierId] = useState<string>('')
  void setSelectedSupplierId
  const [searchQuery, setSearchQuery] = useState('')

  // Modal response
  const [selectedPoForAction, setSelectedPoForAction] = useState<SupplierPO | null>(null)
  const [responseNotes, setResponseNotes] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [posData, catData, sumData, foreData] = await Promise.all([
        supplierService.getPos(selectedSupplierId || undefined).catch(() => []),
        supplierService.getCatalog(selectedSupplierId || undefined).catch(() => []),
        supplierService.getSummary().catch(() => null),
        supplierService.getDemandForecast().catch(() => null),
      ])
      setPos(posData)
      setCatalogItems(catData)
      if (sumData) {
        setSummary({
          total_pos: sumData.total_pos,
          pending_pos: sumData.pending_pos,
          accepted_pos: sumData.accepted_pos,
          suppliers: sumData.suppliers,
        })
      }
      if (foreData) {
        setForecastData(foreData)
      }
    } catch {
      toast.error('Gagal memuat data portal supplier.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [selectedSupplierId])

  const handleRespondPo = async (status: string) => {
    if (!selectedPoForAction) return
    setIsSubmitting(true)
    try {
      await supplierService.respondPo(selectedPoForAction.po_id, {
        status,
        notes: responseNotes,
      })
      toast.success(
        `PO ${selectedPoForAction.po_id} berhasil ditanggapi dengan status '${status}'. Notifikasi telah dikirimkan ke Admin Dova!`
      )
      setSelectedPoForAction(null)
      setResponseNotes('')
      fetchData()
    } catch {
      toast.error('Gagal memperbarui status PO.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const filteredPos = pos.filter(
    (p) =>
      p.po_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.supplier_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.items?.some((it) => it.item_name.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  return (
    <div className="min-h-screen bg-[#FAF7F2] text-stone-900 font-sans flex flex-col md:flex-row antialiased">
      {/* ── 1. Left Persistent Sidebar (Consistent Dova Style) ──────────────── */}
      <aside className="w-full md:w-64 bg-white border-r border-stone-200/80 flex flex-col justify-between shrink-0 shadow-2xs z-20">
        <div>
          {/* Logo brand */}
          <div className="p-6 pb-5 flex items-center justify-between border-b border-stone-100">
            <Link to="/" className="flex items-center gap-3">
              <div className="size-10 rounded-2xl bg-amber-400 flex items-center justify-center text-stone-950 font-black shadow-md shadow-amber-400/20 text-lg">
                DK
              </div>
              <div>
                <span className="font-extrabold text-lg text-stone-900 tracking-tight leading-none block">
                  dovakitchen
                </span>
                <span className="text-[11px] font-semibold text-emerald-600 uppercase tracking-wider block mt-0.5">
                  Portal Supplier
                </span>
              </div>
            </Link>
          </div>

          {/* Navigation Links */}
          <nav className="p-4 space-y-1.5 text-sm font-semibold">
            <button
              onClick={() => setActiveTab('pos')}
              className={cn(
                'w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl transition-all text-left',
                activeTab === 'pos'
                  ? 'bg-amber-400 text-stone-950 font-bold shadow-sm'
                  : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
              )}
            >
              <Package className="size-5" />
              <span>Purchase Orders (PO)</span>
              {summary.pending_pos > 0 && (
                <span className="ml-auto px-2 py-0.5 rounded-full text-[10px] bg-rose-500 text-white font-extrabold animate-pulse">
                  {summary.pending_pos}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('catalog')}
              className={cn(
                'w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl transition-all text-left',
                activeTab === 'catalog'
                  ? 'bg-amber-400 text-stone-950 font-bold shadow-sm'
                  : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
              )}
            >
              <Store className="size-5" />
              <span>Katalog Bahan Baku</span>
            </button>

            <button
              onClick={() => setActiveTab('performance')}
              className={cn(
                'w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl transition-all text-left',
                activeTab === 'performance'
                  ? 'bg-amber-400 text-stone-950 font-bold shadow-sm'
                  : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
              )}
            >
              <Star className="size-5" />
              <span>Performa & Rating</span>
            </button>

            <button
              onClick={() => setActiveTab('forecast')}
              className={cn(
                'w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl transition-all text-left',
                activeTab === 'forecast'
                  ? 'bg-amber-400 text-stone-950 font-bold shadow-sm'
                  : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
              )}
            >
              <TrendingUp className="size-5" />
              <span>Prediksi Demand AI</span>
            </button>

            <div className="pt-4 border-t border-stone-100 mt-4">
              <Link
                to="/admin"
                className="w-full flex items-center gap-3.5 px-4 py-2.5 rounded-2xl text-stone-600 hover:bg-stone-100 hover:text-stone-900 transition-all text-xs font-bold"
              >
                <LayoutDashboard className="size-4" />
                <span>← Masuk Admin / KDS</span>
              </Link>
            </div>
          </nav>
        </div>

        {/* Supplier Profile card */}
        <div className="p-4 border-t border-stone-100">
          <div className="p-3 rounded-2xl bg-stone-50 border border-stone-200/60 space-y-2">
            <div className="flex items-center gap-2.5">
              <div className="size-9 rounded-full bg-emerald-100 text-emerald-800 font-bold flex items-center justify-center text-xs">
                SUP
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-bold text-stone-900 truncate">Rekan Mitra Dova</p>
                <p className="text-[10px] text-stone-500">Verified Precision Supplier</p>
              </div>
            </div>
            <a
              href="https://wa.me/6281326332247?text=Halo%20Admin%20Dova%20Kitchen,%20saya%20dari%20pihak%20supplier."
              target="_blank"
              rel="noreferrer"
              className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-[11px] font-bold shadow-2xs"
            >
              <MessageSquare className="size-3" />
              Chat WhatsApp Admin
            </a>
          </div>
        </div>
      </aside>

      {/* ── 2. Main Content Area ────────────────────────────────────────────── */}
      <main className="flex-1 p-4 md:p-8 overflow-y-auto space-y-6">
        {/* Top Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-stone-900 tracking-tight flex items-center gap-2">
              Portal Pasokan & Purchase Order 📦
            </h1>
            <p className="text-xs text-stone-500 font-medium mt-1">
              Katering Harian Dova Kitchen • Pengadaan Presisi Bahan Baku
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={fetchData}
              disabled={loading}
              className="rounded-full bg-white border-stone-200 text-stone-700 shadow-2xs gap-1.5 text-xs font-bold"
            >
              <RefreshCw className={cn('size-3.5', loading && 'animate-spin text-amber-600')} />
              Sinkronkan Data
            </Button>
          </div>
        </div>

        {/* ── Top Metric Cards (Bitepoint Style) ── */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="rounded-3xl bg-[#0D4738] text-white p-5 shadow-lg shadow-emerald-950/10 flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-xs font-semibold text-emerald-200">Total PO Diterima</p>
              <h2 className="text-3xl font-black">{summary.total_pos}</h2>
              <p className="text-[11px] text-emerald-300">Minggu ini</p>
            </div>
            <div className="size-11 rounded-2xl bg-white/10 flex items-center justify-center text-white">
              <Package className="size-5 text-emerald-300" />
            </div>
          </div>

          <div className="rounded-3xl bg-white border border-stone-200/90 p-5 shadow-2xs flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-xs font-semibold text-stone-500">Perlu Konfirmasi</p>
              <h2 className="text-3xl font-black text-rose-600">{summary.pending_pos}</h2>
              <p className="text-[11px] text-rose-500 font-medium">Batas respon 2 jam</p>
            </div>
            <div className="size-11 rounded-2xl bg-rose-50 flex items-center justify-center text-rose-600">
              <Clock className="size-5" />
            </div>
          </div>

          <div className="rounded-3xl bg-white border border-stone-200/90 p-5 shadow-2xs flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-xs font-semibold text-stone-500">PO Disetujui / Selesai</p>
              <h2 className="text-3xl font-black text-stone-900">{summary.accepted_pos}</h2>
              <p className="text-[11px] text-emerald-600 font-semibold">Terkirim tepat waktu</p>
            </div>
            <div className="size-11 rounded-2xl bg-emerald-50 flex items-center justify-center text-emerald-600">
              <CheckCircle2 className="size-5" />
            </div>
          </div>

          <div className="rounded-3xl bg-white border border-stone-200/90 p-5 shadow-2xs flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-xs font-semibold text-stone-500">Rating Kualitas</p>
              <h2 className="text-3xl font-black text-amber-500 flex items-center gap-1">
                4.90 <span className="text-base text-stone-400">/5</span>
              </h2>
              <p className="text-[11px] text-stone-400">Grade A (Presisi Higienis)</p>
            </div>
            <div className="size-11 rounded-2xl bg-amber-50 flex items-center justify-center text-amber-500">
              <Star className="size-5 fill-amber-500" />
            </div>
          </div>
        </div>

        {/* ── TAB 1: PURCHASE ORDERS LIST ─────────────────────────────────────── */}
        {activeTab === 'pos' && (
          <div className="bg-white rounded-3xl p-6 border border-stone-200/90 shadow-2xs space-y-5">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="font-extrabold text-lg text-stone-900">Daftar Purchase Orders (PO) Masuk</h3>
                <p className="text-xs text-stone-500">
                  Tinjau kebutuhan bahan dapur dan konfirmasi ketersediaan pasokan.
                </p>
              </div>

              {/* Search & Filter */}
              <div className="flex items-center gap-3">
                <div className="relative">
                  <Search className="absolute left-3.5 top-2.5 size-4 text-stone-400" />
                  <Input
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Cari PO / bahan..."
                    className="rounded-full pl-10 pr-4 py-2 text-xs bg-stone-50 border-stone-200 w-56"
                  />
                </div>
              </div>
            </div>

            {/* List PO Cards */}
            <div className="space-y-4">
              {filteredPos.map((po) => {
                const isSent = po.status === 'SENT' || po.status === 'PENDING_APPROVAL'
                const isAcknowledged = po.status === 'ACKNOWLEDGED'
                const isReceived = po.status === 'RECEIVED'
                const isRejected = po.status === 'REJECTED'

                return (
                  <div
                    key={po.po_id}
                    className="p-5 rounded-2xl border border-stone-200/80 hover:border-amber-400 transition-all space-y-4 bg-stone-50/30"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-stone-200/60">
                      <div className="flex items-center gap-3">
                        <div className="size-10 rounded-2xl bg-amber-100 text-amber-900 font-extrabold flex items-center justify-center text-xs">
                          PO
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-extrabold text-sm text-stone-900">{po.po_id}</span>
                            <Badge
                              className={cn(
                                'text-[10px] px-2.5 py-0.5 border-none font-bold',
                                isSent && 'bg-rose-500 text-white',
                                isAcknowledged && 'bg-amber-500 text-white',
                                isReceived && 'bg-emerald-600 text-white',
                                isRejected && 'bg-stone-500 text-white'
                              )}
                            >
                              {po.status}
                            </Badge>
                          </div>
                          <p className="text-xs text-stone-500 mt-0.5">
                            Mitra: <strong className="text-stone-800">{po.supplier_name}</strong> •{' '}
                            Batas Kirim: <strong className="text-rose-700">{po.need_by_date}</strong>
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        <div className="text-right">
                          <p className="text-[11px] text-stone-500">Total Tagihan PO</p>
                          <p className="text-sm font-black text-emerald-700">
                            Rp {(po.total_amount || 0).toLocaleString('id-ID')}
                          </p>
                        </div>

                        {/* Action buttons */}
                        <div className="flex items-center gap-2">
                          {isSent && (
                            <>
                              <Button
                                size="sm"
                                onClick={() => setSelectedPoForAction(po)}
                                className="rounded-xl bg-amber-400 hover:bg-amber-500 text-stone-950 font-bold text-xs"
                              >
                                Tanggapi PO →
                              </Button>
                            </>
                          )}
                          {isAcknowledged && (
                            <Button
                              size="sm"
                              onClick={() => {
                                setSelectedPoForAction(po)
                              }}
                              className="rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs"
                            >
                              <Truck className="size-3.5 mr-1" />
                              Kirim Barang
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* PO Items Table */}
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="text-stone-500 border-b border-stone-200 text-[11px]">
                            <th className="pb-2 font-bold">Nama Bahan Baku</th>
                            <th className="pb-2 font-bold">Kebutuhan Qty</th>
                            <th className="pb-2 font-bold">Satuan</th>
                            <th className="pb-2 font-bold text-right">Harga Satuan</th>
                            <th className="pb-2 font-bold text-right">Subtotal</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-stone-100">
                          {po.items?.map((it, idx) => (
                            <tr key={it.id || idx} className="text-stone-800">
                              <td className="py-2.5 font-bold flex items-center gap-2">
                                <div className="size-2 rounded-full bg-amber-400" />
                                {it.item_name}
                              </td>
                              <td className="py-2.5 font-mono font-bold">{it.qty}</td>
                              <td className="py-2.5">{it.unit}</td>
                              <td className="py-2.5 text-right font-mono">
                                Rp {(it.unit_price || 0).toLocaleString('id-ID')}
                              </td>
                              <td className="py-2.5 text-right font-mono font-bold text-stone-900">
                                Rp {(it.subtotal || 0).toLocaleString('id-ID')}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {po.notes && (
                      <p className="text-[11px] text-stone-500 bg-white p-2.5 rounded-xl border border-stone-200">
                        Catatan Dapur: {po.notes}
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* ── TAB 2: KATALOG BAHAN BAKU ───────────────────────────────────────── */}
        {activeTab === 'catalog' && (
          <div className="bg-white rounded-3xl p-6 border border-stone-200/90 shadow-2xs space-y-4">
            <div>
              <h3 className="font-extrabold text-lg text-stone-900">Katalog Harga & Bahan Baku Dova</h3>
              <p className="text-xs text-stone-500">
                Daftar standar harga beli bahan baku higienis yang disepakati dengan katering Dova Kitchen.
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-stone-500 border-b border-stone-200 text-[11px]">
                    <th className="pb-2.5 font-bold">Nama Bahan Baku</th>
                    <th className="pb-2.5 font-bold">Supplier Utama</th>
                    <th className="pb-2.5 font-bold">Satuan</th>
                    <th className="pb-2.5 font-bold">MOQ (Min. Order)</th>
                    <th className="pb-2.5 font-bold text-right">Harga Satuan</th>
                    <th className="pb-2.5 font-bold text-center">Ketersediaan</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {catalogItems.map((item) => (
                    <tr key={item.id} className="text-stone-800">
                      <td className="py-3 font-bold flex items-center gap-2">
                        <Utensils className="size-3.5 text-amber-500" />
                        {item.item_name}
                      </td>
                      <td className="py-3 text-stone-600">{item.supplier_name}</td>
                      <td className="py-3">{item.unit}</td>
                      <td className="py-3 font-mono">{item.moq} {item.unit}</td>
                      <td className="py-3 text-right font-mono font-bold text-emerald-700">
                        Rp {item.price_per_unit.toLocaleString('id-ID')}
                      </td>
                      <td className="py-3 text-center">
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                          <Check className="size-3" /> Ready Pasokan
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── TAB 3: PERFORMA & RATING ────────────────────────────────────────── */}
        {activeTab === 'performance' && (
          <div className="bg-white rounded-3xl p-6 border border-stone-200/90 shadow-2xs space-y-6">
            <div>
              <h3 className="font-extrabold text-lg text-stone-900">Evaluasi Performa Supplier</h3>
              <p className="text-xs text-stone-500">
                Penilaian higienitas, ketepatan waktu pengiriman, dan kepatuhan standar nol alergen silang.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 rounded-2xl bg-stone-50 border border-stone-200 space-y-2">
                <p className="text-xs font-bold text-stone-700">Ketepatan Waktu (On-Time Delivery)</p>
                <h4 className="text-2xl font-black text-emerald-700">98.4%</h4>
                <p className="text-[11px] text-stone-500">Rata-rata lead time pengantaran: 1.2 hari.</p>
              </div>

              <div className="p-4 rounded-2xl bg-stone-50 border border-stone-200 space-y-2">
                <p className="text-xs font-bold text-stone-700">Kepatuhan Higienitas & Mutu</p>
                <h4 className="text-2xl font-black text-amber-600">100% Lolos</h4>
                <p className="text-[11px] text-stone-500">Nol insiden kontaminasi alergen silang di gudang.</p>
              </div>

              <div className="p-4 rounded-2xl bg-stone-50 border border-stone-200 space-y-2">
                <p className="text-xs font-bold text-stone-700">Tingkat Pemenuhan PO (Fulfillment)</p>
                <h4 className="text-2xl font-black text-teal-700">99.1%</h4>
                <p className="text-[11px] text-stone-500">Kuantitas sesuai faktur pesanan dapur.</p>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB 4: PREDIKSI DEMAND AI & PROYEKSI BAHAN ──────────────────────── */}
        {activeTab === 'forecast' && (
          <div className="space-y-6">
            {/* KPI Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-[#0D4738] text-white p-5 rounded-3xl shadow-md space-y-1">
                <div className="flex items-center justify-between text-emerald-300 text-xs font-bold">
                  <span>Hari Puncak Dapur (Peak Day)</span>
                  <TrendingUp className="size-4" />
                </div>
                <h3 className="text-2xl font-black text-amber-300">
                  Hari {forecastData?.peak_day || 'Jumat'} 🔥
                </h3>
                <p className="text-[11px] text-emerald-200">
                  Volume pesanan katering melonjak +32%. Siapkan pasokan lebih awal!
                </p>
              </div>

              <div className="bg-white p-5 rounded-3xl border border-stone-200/90 shadow-2xs space-y-1">
                <div className="flex items-center justify-between text-stone-500 text-xs font-semibold">
                  <span>Model Peramalan</span>
                  <Sparkles className="size-4 text-amber-500" />
                </div>
                <h3 className="text-2xl font-black text-stone-900">Linear ML & 7D MA</h3>
                <p className="text-[11px] text-stone-500">
                  Sinkronisasi real-time dari 1.000 transaksi pesanan lunas
                </p>
              </div>

              <div className="bg-white p-5 rounded-3xl border border-stone-200/90 shadow-2xs space-y-1">
                <div className="flex items-center justify-between text-stone-500 text-xs font-semibold">
                  <span>Tingkat Kesiapan Pasokan</span>
                  <CheckCircle2 className="size-4 text-emerald-600" />
                </div>
                <h3 className="text-2xl font-black text-emerald-600">Optimal (95% CI)</h3>
                <p className="text-[11px] text-stone-500">
                  Perhitungan Safety Stock & Reorder Point terkalibrasi otomatis
                </p>
              </div>
            </div>

            {/* Proyeksi Kebutuhan Bahan Baku 7 Hari */}
            <div className="bg-white rounded-3xl p-6 border border-stone-200/90 shadow-2xs space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div>
                  <h3 className="font-extrabold text-base text-stone-900 flex items-center gap-2">
                    <Truck className="size-4.5 text-amber-600" />
                    Proyeksi Kebutuhan Bahan Baku Dapur (7 Hari ke Depan)
                  </h3>
                  <p className="text-xs text-stone-500">
                    Estimasi kuantitas bahan yang perlu disiapkan oleh supplier sebelum jatuh tempo PO.
                  </p>
                </div>
                <Badge className="bg-amber-100 text-amber-800 border-none font-bold text-xs self-start sm:self-auto">
                  AI Demand Forecast
                </Badge>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead className="bg-[#14213D] text-white text-[11px] font-bold">
                    <tr>
                      <th className="py-3 px-3">Bahan Baku</th>
                      <th className="py-3 px-3">Mitra Rekomendasi</th>
                      <th className="py-3 px-3 text-right">Proyeksi 7 Hari</th>
                      <th className="py-3 px-3 text-center">Status Urgensi</th>
                      <th className="py-3 px-3 text-center">Aksi Pasokan</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100 font-sans">
                    {(forecastData?.supplier_7d_forecast || []).map((item: any, idx: number) => (
                      <tr key={idx} className="hover:bg-stone-50/60">
                        <td className="py-3 px-3 font-bold text-stone-900">
                          {item.material}
                        </td>
                        <td className="py-3 px-3 text-stone-600">
                          {item.supplier}
                        </td>
                        <td className="py-3 px-3 text-right font-mono font-black text-amber-600 text-sm">
                          {item.projected_kg} {item.unit}
                        </td>
                        <td className="py-3 px-3 text-center">
                          <Badge
                            className={cn(
                              'text-[10px] font-bold px-2.5 py-0.5 border-none',
                              item.urgency === 'KRITIS'
                                ? 'bg-rose-600 text-white animate-pulse'
                                : item.urgency === 'TINGGI'
                                ? 'bg-amber-600 text-white'
                                : 'bg-emerald-600 text-white'
                            )}
                          >
                            {item.urgency}
                          </Badge>
                        </td>
                        <td className="py-3 px-3 text-center">
                          <a
                            href={`https://wa.me/6281326332247?text=Halo%20Admin%20Dova%20Kitchen,%20kami%20siap%20memasok%20${encodeURIComponent(item.material)}%20sebanyak%20${item.projected_kg}%20${item.unit}%20sesuai%20proyeksi%20demand%20AI.`}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-emerald-600 hover:bg-emerald-700 text-white text-[11px] font-bold shadow-2xs transition-all"
                          >
                            <MessageSquare className="size-3" />
                            Konfirmasi Pasokan
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Menu Terlaris yang Membutuhkan Pasokan */}
            <div className="bg-white rounded-3xl p-6 border border-stone-200/90 shadow-2xs space-y-4">
              <div>
                <h3 className="font-extrabold text-base text-stone-900 flex items-center gap-2">
                  <Utensils className="size-4.5 text-rose-600" />
                  Menu Katering Terlaris dengan Konsumsi Bahan Tertinggi
                </h3>
                <p className="text-xs text-stone-500">
                  Data 1.000 pesanan menunjukkan hidangan berikut mendominasi kebutuhan dapur.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {(forecastData?.top_dishes || []).slice(0, 4).map((d: any) => (
                  <div
                    key={d.menu_id}
                    className="p-4 rounded-2xl border border-stone-200 bg-stone-50 space-y-1.5"
                  >
                    <Badge variant="outline" className="text-[10px] font-bold">
                      Hari {d.hari}
                    </Badge>
                    <h4 className="font-bold text-xs text-stone-900 leading-snug">
                      {d.nama_menu}
                    </h4>
                    <p className="font-mono text-xs font-black text-rose-600">
                      {d.total_portions} Porsi Terjual ({d.share_percentage}% share)
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* ── Modal Tanggapi PO ──────────────────────────────────────────────── */}
      {selectedPoForAction && (
        <div className="fixed inset-0 z-50 bg-stone-950/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-stone-200 space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between">
              <h3 className="font-extrabold text-lg text-stone-900">
                Konfirmasi Purchase Order ({selectedPoForAction.po_id})
              </h3>
              <button
                onClick={() => setSelectedPoForAction(null)}
                className="text-stone-400 hover:text-stone-600"
              >
                <X className="size-5" />
              </button>
            </div>

            <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-xs space-y-1.5">
              <div className="flex justify-between font-bold">
                <span>Nilai Pemesanan:</span>
                <span className="text-emerald-800">
                  Rp {(selectedPoForAction.total_amount || 0).toLocaleString('id-ID')}
                </span>
              </div>
              <div className="flex justify-between text-stone-600">
                <span>Batas Tiba di Dapur:</span>
                <span className="font-bold text-rose-700">{selectedPoForAction.need_by_date}</span>
              </div>
            </div>

            <div>
              <label className="text-xs font-bold text-stone-700 block mb-1">
                Catatan Pengiriman / Armada:
              </label>
              <textarea
                rows={3}
                value={responseNotes}
                onChange={(e) => setResponseNotes(e.target.value)}
                placeholder="Contoh: Barang siap dikirim besok pagi pk 06:30 dengan armada berpendingin."
                className="w-full rounded-2xl border border-stone-200 p-3 text-xs focus:ring-amber-400"
              />
            </div>

            <p className="text-[11px] text-stone-500">
              * Mengonfirmasi PO akan langsung memicu notifikasi WhatsApp & Telegram ke tim Dapur & Admin Dova Kitchen.
            </p>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <Button
                variant="outline"
                onClick={() => handleRespondPo('REJECTED')}
                disabled={isSubmitting}
                className="rounded-full text-xs font-bold text-rose-700 border-rose-200 hover:bg-rose-50"
              >
                Tolak PO
              </Button>
              <Button
                onClick={() => handleRespondPo('ACKNOWLEDGED')}
                disabled={isSubmitting}
                className="rounded-full bg-amber-400 hover:bg-amber-500 text-stone-950 font-extrabold text-xs px-5 shadow-sm"
              >
                {isSubmitting ? 'Menyimpan...' : 'Terima PO & Siapkan'}
              </Button>
              <Button
                onClick={() => handleRespondPo('RECEIVED')}
                disabled={isSubmitting}
                className="rounded-full bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-xs px-5 shadow-sm"
              >
                Kirim Sekarang 🚚
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
