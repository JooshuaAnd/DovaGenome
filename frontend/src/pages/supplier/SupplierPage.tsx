import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Check,
  CheckCircle2,
  Clock,
  FileText,
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
import { supplierService, type SupplierInvoice, type SupplierPO, type SupplierItem } from '@/services/supplier'

export function SupplierPage() {
  const { customer, logout } = useAuth()
  void customer
  void logout
  const [loading, setLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<'pos' | 'invoices' | 'catalog' | 'performance' | 'forecast'>('pos')

  // PO & Catalog State (Initialized with verified defaults)
  // Supplier data must come from the authenticated API. Legacy demo constants
  // remain in this file for reference only and are never rendered as fallback.
  const [pos, setPos] = useState<SupplierPO[]>([])
  const [catalogItems, setCatalogItems] = useState<SupplierItem[]>([])
  const [invoices, setInvoices] = useState<SupplierInvoice[]>([])
  const [summary, setSummary] = useState({
    total_pos: 0,
    pending_pos: 0,
    accepted_pos: 0,
    suppliers: [] as any[],
  })
  const [forecastData, setForecastData] = useState<any>(null)
  const [selectedSupplierId, setSelectedSupplierId] = useState<string>('')
  void setSelectedSupplierId
  const [searchQuery, setSearchQuery] = useState('')

  // Modal response
  const [selectedPoForAction, setSelectedPoForAction] = useState<SupplierPO | null>(null)
  const [selectedPoForReceipt, setSelectedPoForReceipt] = useState<SupplierPO | null>(null)
  const [receiptQuantities, setReceiptQuantities] = useState<Record<number, string>>({})
  const [receiptKey, setReceiptKey] = useState('')
  const [responseNotes, setResponseNotes] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [invoiceForm, setInvoiceForm] = useState({
    invoice_number: '',
    payment_terms: 'PAY_ON_DELIVERY' as 'PAY_ON_DELIVERY' | 'WEEKLY_INVOICE',
    amount: '',
    due_date: new Date().toISOString().slice(0, 10),
    po_id: '',
    period_start: '',
    period_end: '',
  })

  const fetchData = async () => {
    setLoading(true)
    try {
      const [posData, catData, sumData, foreData, invoiceData] = await Promise.all([
        supplierService.getPos(selectedSupplierId || undefined).catch(() => []),
        supplierService.getCatalog(selectedSupplierId || undefined).catch(() => []),
        supplierService.getSummary().catch(() => null),
        supplierService.getDemandForecast().catch(() => null),
        supplierService.getInvoices().catch(() => []),
      ])
      setPos(posData)
      setCatalogItems(catData)
      setInvoices(invoiceData)
      if (sumData) {
        setSummary({
          total_pos: sumData.total_pos,
          pending_pos: sumData.pending_pos,
          accepted_pos: sumData.accepted_pos,
          suppliers: sumData.suppliers,
        })
      }
      const trustedForecast =
        foreData &&
        foreData.data_mode === 'live' &&
        foreData.source === 'supabase_postgres' &&
        foreData.calculation_version === 'forecast_backtest_v2' &&
        foreData.status === 'OK' &&
        typeof foreData.peak_day === 'string' &&
        Array.isArray(foreData.supplier_7d_forecast) &&
        Array.isArray(foreData.top_dishes)
      setForecastData(trustedForecast ? foreData : null)
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

  const openReceipt = (po: SupplierPO) => {
    setSelectedPoForReceipt(po)
    setReceiptKey(`receipt:${po.po_id}:${Date.now()}`)
    setReceiptQuantities(
      Object.fromEntries(
        po.items.map((item) => [item.id, String(Math.max(0, item.qty - (item.received_qty || 0)))])
      )
    )
  }

  const handleReceivePo = async () => {
    if (!selectedPoForReceipt) return
    setIsSubmitting(true)
    try {
      const lines = selectedPoForReceipt.items
        .map((item) => ({
          po_item_id: item.id,
          quantity: Number(receiptQuantities[item.id] || 0),
          unit: item.unit,
        }))
        .filter((line) => Number.isFinite(line.quantity) && line.quantity > 0)
      if (!lines.length) {
        toast.error('Isi minimal satu jumlah barang yang diterima.')
        return
      }
      const result = await supplierService.receivePo(
        selectedPoForReceipt.po_id,
        { lines, notes: responseNotes },
        receiptKey
      )
      toast.success(`Goods receipt ${result.receipt_id} tercatat. Stok Supabase sudah diperbarui.`)
      setSelectedPoForReceipt(null)
      setResponseNotes('')
      await fetchData()
    } catch {
      toast.error('Goods receipt belum dapat diposting. Periksa status PO dan migration Supabase.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleSubmitInvoice = async () => {
    const amount = Number(invoiceForm.amount)
    if (!invoiceForm.invoice_number.trim() || !Number.isFinite(amount) || amount <= 0 || !invoiceForm.due_date) {
      toast.error('Nomor invoice, nilai tagihan, dan jatuh tempo wajib diisi.')
      return
    }
    if (invoiceForm.payment_terms === 'PAY_ON_DELIVERY' && !invoiceForm.po_id.trim()) {
      toast.error('PAY_ON_DELIVERY wajib memilih PO yang sudah diterima.')
      return
    }
    if (invoiceForm.payment_terms === 'WEEKLY_INVOICE' && (!invoiceForm.period_start || !invoiceForm.period_end)) {
      toast.error('WEEKLY_INVOICE wajib memiliki periode awal dan akhir.')
      return
    }
    setIsSubmitting(true)
    try {
      const result = await supplierService.submitInvoice(
        {
          invoice_number: invoiceForm.invoice_number.trim(),
          payment_terms: invoiceForm.payment_terms,
          amount,
          due_date: invoiceForm.due_date,
          po_id: invoiceForm.po_id.trim() || undefined,
          period_start: invoiceForm.period_start || undefined,
          period_end: invoiceForm.period_end || undefined,
        },
        `invoice:${invoiceForm.invoice_number.trim()}`,
      )
      toast.success(`Invoice ${result.invoice_number} masuk review admin (${result.match_status}).`)
      setInvoiceForm((current) => ({ ...current, invoice_number: '', amount: '', po_id: '' }))
      await fetchData()
    } catch {
      toast.error('Invoice belum dapat diajukan. Pastikan goods receipt dan migration billing sudah aktif.')
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
    <div className="min-h-screen bg-[#f6f7fb] text-slate-950 font-sans flex flex-col md:flex-row antialiased">
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
              onClick={() => setActiveTab('invoices')}
              className={cn(
                'w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl transition-all text-left',
                activeTab === 'invoices'
                  ? 'bg-amber-400 text-stone-950 font-bold shadow-sm'
                  : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
              )}
            >
              <FileText className="size-5" />
              <span>Invoice & Tagihan</span>
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
                —
              </h2>
              <p className="text-[11px] text-stone-400">Belum ada metrik kualitas live</p>
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
                const isSent = po.status === 'SENT'
                const isAcknowledged = po.status === 'ACKNOWLEDGED' || po.status === 'ACCEPTED'
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
                                openReceipt(po)
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

        {activeTab === 'invoices' && (
          <div className="space-y-5">
            <div className="bg-white rounded-3xl p-6 border border-stone-200/90 shadow-2xs space-y-4">
              <div>
                <h3 className="font-extrabold text-lg text-stone-900">Ajukan Invoice Supplier</h3>
                <p className="text-xs text-stone-500">Invoice tidak otomatis lunas. Admin akan memeriksa PO, goods receipt, dan nilai tagihan.</p>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <Input value={invoiceForm.invoice_number} onChange={(event) => setInvoiceForm((current) => ({ ...current, invoice_number: event.target.value }))} placeholder="Nomor invoice supplier" className="rounded-xl" />
                <Input type="number" min="1" value={invoiceForm.amount} onChange={(event) => setInvoiceForm((current) => ({ ...current, amount: event.target.value }))} placeholder="Nilai tagihan (IDR)" className="rounded-xl" />
                <select value={invoiceForm.payment_terms} onChange={(event) => setInvoiceForm((current) => ({ ...current, payment_terms: event.target.value as 'PAY_ON_DELIVERY' | 'WEEKLY_INVOICE' }))} className="h-10 rounded-xl border border-stone-200 bg-white px-3 text-xs">
                  <option value="PAY_ON_DELIVERY">PAY_ON_DELIVERY</option>
                  <option value="WEEKLY_INVOICE">WEEKLY_INVOICE</option>
                </select>
                <Input type="date" value={invoiceForm.due_date} onChange={(event) => setInvoiceForm((current) => ({ ...current, due_date: event.target.value }))} className="rounded-xl" />
                {invoiceForm.payment_terms === 'PAY_ON_DELIVERY' ? (
                  <select value={invoiceForm.po_id} onChange={(event) => setInvoiceForm((current) => ({ ...current, po_id: event.target.value }))} className="h-10 rounded-xl border border-stone-200 bg-white px-3 text-xs md:col-span-2">
                    <option value="">Pilih PO RECEIVED</option>
                    {pos.filter((po) => po.status === 'RECEIVED').map((po) => <option key={po.po_id} value={po.po_id}>{po.po_id} · Rp {(po.total_amount || 0).toLocaleString('id-ID')}</option>)}
                  </select>
                ) : (
                  <div className="grid grid-cols-2 gap-3 md:col-span-2">
                    <Input type="date" value={invoiceForm.period_start} onChange={(event) => setInvoiceForm((current) => ({ ...current, period_start: event.target.value }))} aria-label="Periode awal" />
                    <Input type="date" value={invoiceForm.period_end} onChange={(event) => setInvoiceForm((current) => ({ ...current, period_end: event.target.value }))} aria-label="Periode akhir" />
                  </div>
                )}
              </div>
              <Button onClick={() => void handleSubmitInvoice()} disabled={isSubmitting} className="rounded-full bg-amber-400 text-stone-950 hover:bg-amber-500 font-bold">{isSubmitting ? 'Mengirim...' : 'Ajukan Invoice untuk Review'}</Button>
            </div>
            <div className="bg-white rounded-3xl p-6 border border-stone-200/90 shadow-2xs space-y-4">
              <h3 className="font-extrabold text-lg text-stone-900">Riwayat Invoice</h3>
              {!invoices.length ? <p className="rounded-2xl border border-dashed border-stone-200 p-5 text-sm text-stone-500">Belum ada invoice supplier yang terdaftar.</p> : invoices.map((invoice) => <div key={invoice.supplier_invoice_id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-stone-200 p-4"><div><p className="font-bold text-stone-900">{invoice.invoice_number} <Badge className="ml-2 bg-stone-100 text-stone-700 border-none">{invoice.status}</Badge></p><p className="text-xs text-stone-500">{invoice.payment_terms} · PO {invoice.po_ids.join(', ') || '-'} · jatuh tempo {invoice.due_date}</p></div><div className="text-right"><p className="font-black text-emerald-700">Rp {invoice.amount.toLocaleString('id-ID')}</p><p className={cn('text-[11px] font-bold', invoice.match_status === 'MATCHED' ? 'text-emerald-600' : 'text-amber-600')}>{invoice.match_status} · expected Rp {invoice.expected_amount.toLocaleString('id-ID')}</p></div></div>)}
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
                <h4 className="text-2xl font-black text-stone-500">—</h4>
                <p className="text-[11px] text-stone-500">Belum ada metrik delivery live yang cukup.</p>
              </div>

              <div className="p-4 rounded-2xl bg-stone-50 border border-stone-200 space-y-2">
                <p className="text-xs font-bold text-stone-700">Kepatuhan Higienitas & Mutu</p>
                <h4 className="text-2xl font-black text-stone-500">—</h4>
                <p className="text-[11px] text-stone-500">Belum ada hasil inspeksi mutu live.</p>
              </div>

              <div className="p-4 rounded-2xl bg-stone-50 border border-stone-200 space-y-2">
                <p className="text-xs font-bold text-stone-700">Tingkat Pemenuhan PO (Fulfillment)</p>
                <h4 className="text-2xl font-black text-stone-500">—</h4>
                <p className="text-[11px] text-stone-500">Menunggu histori goods receipt yang terverifikasi.</p>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB 4: PREDIKSI DEMAND AI & PROYEKSI BAHAN ──────────────────────── */}
        {activeTab === 'forecast' && (
          forecastData ? (
            <div className="space-y-6">
            {/* KPI Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-[#0D4738] text-white p-5 rounded-3xl shadow-md space-y-1">
                <div className="flex items-center justify-between text-emerald-300 text-xs font-bold">
                  <span>Hari Puncak Dapur (Peak Day)</span>
                  <TrendingUp className="size-4" />
                </div>
                <h3 className="text-2xl font-black text-amber-300">
                  Hari {forecastData.peak_day}
                </h3>
                <p className="text-[11px] text-emerald-200">
                  Ringkasan berasal dari payload forecast live yang terverifikasi.
                </p>
              </div>

              <div className="bg-white p-5 rounded-3xl border border-stone-200/90 shadow-2xs space-y-1">
                <div className="flex items-center justify-between text-stone-500 text-xs font-semibold">
                  <span>Model Peramalan</span>
                  <Sparkles className="size-4 text-amber-500" />
                </div>
                <h3 className="text-2xl font-black text-stone-900">Forecast live</h3>
                <p className="text-[11px] text-stone-500">
                  Method dan provenance mengikuti kontrak backend.
                </p>
              </div>

              <div className="bg-white p-5 rounded-3xl border border-stone-200/90 shadow-2xs space-y-1">
                <div className="flex items-center justify-between text-stone-500 text-xs font-semibold">
                  <span>Tingkat Kesiapan Pasokan</span>
                  <CheckCircle2 className="size-4 text-emerald-600" />
                </div>
                <h3 className="text-2xl font-black text-emerald-600">Status terverifikasi</h3>
                <p className="text-[11px] text-stone-500">
                  Angka supply chain hanya tampil setelah gate BOM dan inventory lulus.
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
                    {forecastData.supplier_7d_forecast.map((item: any, idx: number) => (
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
                  Data menu berasal dari payload forecast live yang terverifikasi.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {forecastData.top_dishes.slice(0, 4).map((d: any) => (
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
          ) : (
            <div className="rounded-3xl border border-amber-200 bg-amber-50 p-6 text-sm text-amber-950 space-y-2">
              <h3 className="font-extrabold">Forecast supplier belum tersedia</h3>
              <p>
                Forecast bahan baku ditahan sampai forecast live, BOM, inventory,
                unit conversion, dan lead time supplier terverifikasi. Tidak ada
                angka simulasi yang ditampilkan sebagai pengganti.
              </p>
            </div>
          )
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
                variant="ghost"
                onClick={() => setSelectedPoForAction(null)}
                disabled={isSubmitting}
                className="rounded-full text-xs font-bold text-stone-600"
              >
                Tutup
              </Button>
            </div>
          </div>
        </div>
      )}

      {selectedPoForReceipt && (
        <div className="fixed inset-0 z-50 bg-stone-950/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-stone-200 space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-extrabold text-lg text-stone-900">Posting Barang Diterima</h3>
                <p className="text-xs text-stone-500">PO {selectedPoForReceipt.po_id} · partial receipt diperbolehkan</p>
              </div>
              <button onClick={() => setSelectedPoForReceipt(null)} className="text-stone-400 hover:text-stone-600">
                <X className="size-5" />
              </button>
            </div>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {selectedPoForReceipt.items.map((item) => {
                const remaining = Math.max(0, item.qty - (item.received_qty || 0))
                return (
                  <div key={item.id} className="flex items-center justify-between gap-3 rounded-2xl border border-stone-200 p-3">
                    <div className="min-w-0">
                      <p className="text-xs font-bold text-stone-800 truncate">{item.item_name}</p>
                      <p className="text-[11px] text-stone-500">Sisa PO: {remaining} {item.unit}</p>
                    </div>
                    <Input
                      type="number"
                      min="0"
                      max={remaining}
                      step="0.01"
                      value={receiptQuantities[item.id] || ''}
                      onChange={(event) => setReceiptQuantities((current) => ({ ...current, [item.id]: event.target.value }))}
                      className="w-32 rounded-xl text-xs"
                      aria-label={`Jumlah diterima ${item.item_name}`}
                    />
                  </div>
                )
              })}
            </div>
            <textarea
              rows={2}
              value={responseNotes}
              onChange={(event) => setResponseNotes(event.target.value)}
              placeholder="Catatan penerimaan, kondisi barang, atau nomor surat jalan"
              className="w-full rounded-2xl border border-stone-200 p-3 text-xs focus:ring-emerald-400"
            />
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setSelectedPoForReceipt(null)} className="rounded-full text-xs font-bold">Batal</Button>
              <Button onClick={handleReceivePo} disabled={isSubmitting} className="rounded-full bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-xs">
                {isSubmitting ? 'Memposting...' : 'Post Goods Receipt'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
