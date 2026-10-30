import { useEffect, useState, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Bell,
  Calendar,
  Check,
  CheckCircle2,
  Clock,
  Flame,
  Layers,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Plus,
  RefreshCw,
  Search,
  Send,
  Truck,
  Utensils,
  BarChart3,
  FileSpreadsheet,
  Bot,
  CircleCheck,
  CircleX,
  Users,
  X,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'
import { adminService } from '@/services/admin'
import { ApiError, getErrorMessage } from '@/services/http'
import type { AdminDashboard, AdminSystem } from '@/types'
import { AdminAnalyticsView } from './AdminAnalyticsView'

/* ── Fallback Seed Data jika koneksi lambat ────────────────────────────────── */
export function AdminDashboardPage() {
  const { customer, logout } = useAuth()
  const navigate = useNavigate()

  // State operasional KDS & POS
  const [loading, setLoading] = useState(true)
  const [dataWarning, setDataWarning] = useState<string | null>(null)
  const [searchOrder, setSearchOrder] = useState('')
  const [searchPayment, setSearchPayment] = useState('')
  const [activeTab, setActiveTab] = useState<'dashboard' | 'analytics' | 'marketing' | 'suppliers' | 'inventory'>('dashboard')
  const [analyticsSubTab, setAnalyticsSubTab] = useState<'stats' | 'crm' | 'supply_chain' | 'demand_ai'>('demand_ai')

  // Data dari Supabase
  const [metrics, setMetrics] = useState({ new_orders: 0, total_orders: 0, waiting_list: 0 })
  const [orders, setOrders] = useState<any[]>([])
  const [kitchenOrders, setKitchenOrders] = useState<any[]>([])
  const [popularDishes, setPopularDishes] = useState<any[]>([])
  const [inventoryAlerts, setInventoryAlerts] = useState<any[]>([])
  const [notifications, setNotifications] = useState<any[]>([])
  const [suppliers, setSuppliers] = useState<any[]>([])
  const [purchaseOrders, setPurchaseOrders] = useState<any[]>([])
  const [supplierInvoices, setSupplierInvoices] = useState<any[]>([])
  const [supplierInvoiceWarning, setSupplierInvoiceWarning] = useState<string | null>(null)
  const [adminOverview, setAdminOverview] = useState<AdminDashboard | null>(null)
  const [systemStatus, setSystemStatus] = useState<AdminSystem | null>(null)

  // Modal State
  const [selectedOrderForPay, setSelectedOrderForPay] = useState<any | null>(null)
  const [showTelegramModal, setShowTelegramModal] = useState(false)
  const [telegramRecipient, setTelegramRecipient] = useState({ type: 'customer', name: '', chatId: '', message: '' })
  const [isSendingTelegram, setIsSendingTelegram] = useState(false)
  

  // Fetch data
  const refreshData = async () => {
    setLoading(true)
    setDataWarning(null)
    try {
      const failures: string[] = []
      const safe = async <T,>(label: string, request: Promise<T>, timeoutMs = 10000): Promise<T | null> => {
        let timeoutId: ReturnType<typeof setTimeout> | undefined
        try {
          return await Promise.race([
            request,
            new Promise<T>((_, reject) => {
              timeoutId = setTimeout(() => reject(new Error(`${label} timeout setelah ${Math.round(timeoutMs / 1000)} detik`)), timeoutMs)
            }),
          ])
        } catch (error) {
          const detail = error instanceof ApiError ? `HTTP ${error.status}: ${error.message}` : getErrorMessage(error)
          if (label === 'Invoice supplier') {
            setSupplierInvoiceWarning(`Invoice supplier belum tersedia: ${detail}. Modul billing memerlukan migration Supabase yang sesuai.`)
          } else {
            failures.push(`${label} — ${detail}`)
          }
          return null
        } finally {
          if (timeoutId) clearTimeout(timeoutId)
        }
      }

      // Data dashboard utama dimuat sebelum widget sekunder.
      const overviewRes = await safe('Ringkasan dashboard', adminService.dashboard(), 30000)

      setAdminOverview(overviewRes)
      setLoading(false)

      const posRes = await safe('POS/KDS', adminService.getPosKds())
      const popRes = await safe('Menu terlaris', adminService.getPopularDishes())
      const invRes = await safe('Inventory', adminService.getInventoryAlerts())
      const notifRes = await safe('Telegram outbox', adminService.getNotifications())
      const supRes = await safe('Supplier/PO', adminService.getSuppliers())
      const invoiceRes = await safe('Invoice supplier', adminService.getSupplierInvoices())
      if (invoiceRes) setSupplierInvoiceWarning(null)

      setMetrics(posRes?.metrics || { new_orders: 0, total_orders: 0, waiting_list: 0 })
      setOrders(posRes?.orders || [])
      setKitchenOrders(posRes?.kitchen_orders || [])
      setPopularDishes(popRes?.map((p, idx) => ({
        rank: String(idx + 1).padStart(2, '0'),
        name: p.nama_menu,
        orders: Number(p.order_count),
      })) || [])
      setInventoryAlerts(invRes || [])
      setNotifications(notifRes || [])
      setSuppliers(supRes?.suppliers || [])
      setPurchaseOrders(supRes?.purchase_orders || [])
      setSupplierInvoices(invoiceRes || [])
      const systemRes = await safe('Status sistem', adminService.system(), 30000)
      setSystemStatus(systemRes)
      const dashboardFailures = failures.filter((failure) => !failure.startsWith('Invoice supplier'))
      if (dashboardFailures.length > 0) {
        setDataWarning(`Sebagian data gagal dimuat: ${dashboardFailures.join(' • ')}`)
      }
    } catch {
      toast.error('Gagal menyinkronkan data dengan Supabase.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refreshData()
  }, [])

  // Majukan status pesanan dapur (KDS)
  const handleAdvanceStatus = async (orderId: string, currentStatus: string) => {
    let nextStatus = 'READY'
    if (currentStatus === 'PENDING') nextStatus = 'PREPARING'
    else if (currentStatus === 'PREPARING') nextStatus = 'READY'
    else if (currentStatus === 'READY') nextStatus = 'COMPLETED'

    try {
      await adminService.advanceOrder(orderId, nextStatus)
      toast.success(`Pesanan ${orderId} diperbarui ke status: ${nextStatus}!`)
      refreshData()
    } catch (error) {
      toast.error('Status tiket dapur tidak berubah.', { description: getErrorMessage(error) })
    }
  }

  // Verifikasi pembayaran
  const handleConfirmPayment = async (orderId: string) => {
    try {
      await adminService.setPayment(orderId, 'PAID', `TRX-ADMIN-${Date.now()}`)
      toast.success(`Pembayaran untuk order ${orderId} berhasil diverifikasi LUNAS!`)
      setSelectedOrderForPay(null)
      refreshData()
    } catch (error) {
      toast.error('Pembayaran tidak tercatat.', { description: getErrorMessage(error) })
    }
  }

  // Queue pesan Telegram admin; kanal manual admin sengaja dibatasi ke Telegram.
  const handleSendTelegram = async () => {
    if (!telegramRecipient.chatId || !telegramRecipient.message) {
      toast.error('Mohon isi Telegram chat ID dan pesan!')
      return
    }
    setIsSendingTelegram(true)
    try {
      await adminService.sendNotification({
        recipient_type: telegramRecipient.type,
        recipient_name: telegramRecipient.name || 'Pelanggan',
        recipient_chat_id: telegramRecipient.chatId,
        message: telegramRecipient.message,
      })
      toast.success(`Pesan Telegram masuk outbox untuk ${telegramRecipient.name || 'penerima'}.`)
      setShowTelegramModal(false)
      refreshData()
    } catch (error) {
      toast.error('Pesan Telegram tidak masuk outbox.', { description: getErrorMessage(error) })
    } finally {
      setIsSendingTelegram(false)
    }
  }

  const handleCreateProcurementDraft = async () => {
    try {
      await adminService.createProcurementDraft(`admin-${Date.now()}`)
      toast.success('Draft PO berhasil dibuat dari sourcing live dan menunggu approval admin.')
      refreshData()
    } catch (error) {
      toast.error('Draft PO belum dapat dibuat.', { description: getErrorMessage(error) })
    }
  }

  const handleApproveProcurementDraft = async (poId: string) => {
    try {
      await adminService.approveProcurementDraft(poId)
      toast.success(`PO ${poId} disetujui. Silakan queue untuk delivery.`)
      refreshData()
    } catch (error) {
      toast.error(`PO ${poId} belum dapat disetujui.`, { description: getErrorMessage(error) })
    }
  }

  const handleQueueProcurementDelivery = async (poId: string) => {
    try {
      await adminService.queueProcurementDelivery(poId)
      toast.success(`PO ${poId} masuk outbox delivery dengan status PENDING.`)
      refreshData()
    } catch (error) {
      toast.error(`PO ${poId} belum dapat di-queue.`, { description: getErrorMessage(error) })
    }
  }

  const handleVerifySupplierInvoice = async (invoiceId: string, decision: 'APPROVE' | 'REJECT') => {
    try {
      await adminService.verifySupplierInvoice(
        invoiceId,
        decision,
        decision === 'APPROVE' ? 'Diverifikasi admin melalui dashboard setelah review PO-GR-Invoice.' : 'Ditolak admin; supplier perlu mengajukan koreksi.',
      )
      toast.success(`Invoice supplier ${decision === 'APPROVE' ? 'disetujui' : 'ditolak'}.`)
      refreshData()
    } catch (error) {
      toast.error('Invoice supplier belum dapat diverifikasi.', { description: getErrorMessage(error) })
    }
  }

  const handlePaySupplierInvoice = async (invoice: any) => {
    try {
      await adminService.paySupplierInvoice(invoice.supplier_invoice_id, Number(invoice.amount))
      toast.success(`Pembayaran manual invoice ${invoice.invoice_number} tercatat.`)
      refreshData()
    } catch (error) {
      toast.error('Pembayaran invoice belum dapat dicatat.', { description: getErrorMessage(error) })
    }
  }

  // Filter Order List (KDS)
  const filteredOrders = useMemo(() => {
    return kitchenOrders.filter(
      (o) =>
        o.order_id?.toLowerCase().includes(searchOrder.toLowerCase()) ||
        o.customer_name?.toLowerCase().includes(searchOrder.toLowerCase())
    )
  }, [kitchenOrders, searchOrder])

  // Filter Payment List
  const paymentOrders = useMemo(() => {
    return orders.filter(
      (o) =>
        o.order_id?.toLowerCase().includes(searchPayment.toLowerCase()) ||
        o.customer_name?.toLowerCase().includes(searchPayment.toLowerCase())
    )
  }, [orders, searchPayment])

  const formatOrderDate = (dateStr?: string) => {
    if (!dateStr) return '-'
    try {
      const d = new Date(dateStr)
      return new Intl.DateTimeFormat('id-ID', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }).format(d)
    } catch {
      return dateStr
    }
  }

  const currentDateString = new Intl.DateTimeFormat('id-ID', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).format(new Date())

  return (
    <div className="min-h-screen bg-[#FAF7F2] text-stone-900 font-sans flex flex-col md:flex-row antialiased">
      {/* ── 1. Left Persistent Sidebar (Bitepoint / Dova Style) ──────────────── */}
      <aside className="w-full md:w-64 bg-white border-r border-stone-200/80 flex flex-col justify-between shrink-0 shadow-2xs z-20">
        <div>
          {/* Logo brand */}
          <div className="p-6 pb-5 flex items-center justify-between border-b border-stone-100">
            <Link to="/" className="flex items-center gap-3">
              <div className="size-10 rounded-2xl bg-amber-400 flex items-center justify-center text-stone-950 font-black shadow-md shadow-red-900/20 text-lg">
                DK
              </div>
              <div>
                <span className="font-extrabold text-lg text-stone-900 tracking-tight leading-none block">
                  dovakitchen
                </span>
                <span className="text-[11px] font-semibold text-amber-600 uppercase tracking-wider block mt-0.5">
                  POS & KDS Admin
                </span>
              </div>
            </Link>
          </div>

          {/* Navigation Links */}
          <nav className="p-4 space-y-1.5 text-sm font-semibold">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={cn(
                'w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl transition-all text-left',
                activeTab === 'dashboard'
                  ? 'bg-red-800 text-white font-bold shadow-sm shadow-red-900/20'
                  : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
              )}
            >
              <LayoutDashboard className="size-5" />
              <span>Dashboard & KDS</span>
            </button>

            {/* Direct ML & Analytics Sections */}
            <Link to="/admin/menu-demand" className="w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl transition-all text-left text-stone-600 hover:bg-stone-100 hover:text-stone-900">
              <Calendar className="size-5 text-red-700" />
              <span>Menu & rekomendasi harian</span>
            </Link>

            <button
              onClick={() => {
                setActiveTab('analytics')
                setAnalyticsSubTab('supply_chain')
              }}
              className={cn(
                'w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl transition-all text-left',
                activeTab === 'analytics' && analyticsSubTab === 'supply_chain'
                  ? 'bg-red-800 text-white font-bold shadow-sm shadow-red-900/20'
                  : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
              )}
            >
              <BarChart3 className="size-5 text-blue-600" />
              <span>Supply Chain & ROP ML</span>
            </button>

            <button
              onClick={() => {
                setActiveTab('analytics')
                setAnalyticsSubTab('crm')
              }}
              className={cn(
                'w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl transition-all text-left',
                activeTab === 'analytics' && analyticsSubTab === 'crm'
                  ? 'bg-red-800 text-white font-bold shadow-sm shadow-red-900/20'
                  : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
              )}
            >
              <Users className="size-5 text-purple-600" />
              <span>Pemasaran CRM (RFM)</span>
            </button>

            <button
              onClick={() => {
                setActiveTab('analytics')
                setAnalyticsSubTab('stats')
              }}
              className={cn(
                'w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl transition-all text-left',
                activeTab === 'analytics' && analyticsSubTab === 'stats'
                  ? 'bg-red-800 text-white font-bold shadow-sm shadow-red-900/20'
                  : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
              )}
            >
              <FileSpreadsheet className="size-5 text-stone-500" />
              <span>Statistik Deskriptif</span>
            </button>



            <button
              onClick={() => setActiveTab('inventory')}
              className={cn(
                'w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl transition-all text-left',
                activeTab === 'inventory'
                  ? 'bg-red-800 text-white font-bold shadow-sm'
                  : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
              )}
            >
              <Layers className="size-5" />
              <span>Stok & Bahan</span>
              {inventoryAlerts.some((i) => i.status === 'HABIS') && (
                <span className="ml-auto size-2 rounded-full bg-rose-500 animate-pulse" />
              )}
            </button>

            <button
              onClick={() => setActiveTab('suppliers')}
              className={cn(
                'w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl transition-all text-left',
                activeTab === 'suppliers'
                  ? 'bg-red-800 text-white font-bold shadow-sm'
                  : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
              )}
            >
              <Truck className="size-5" />
              <span>Supplier & PO</span>
            </button>

            <button
              onClick={() => setActiveTab('marketing')}
              className={cn(
                'w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl transition-all text-left',
                activeTab === 'marketing'
                  ? 'bg-red-800 text-white font-bold shadow-sm'
                  : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
              )}
            >
              <MessageSquare className="size-5" />
              <span>Telegram Ops & CRM</span>
            </button>
            <div className="my-3 border-t border-stone-100" />
            <Link to="/admin/daily-menu" className="w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl text-stone-600 hover:bg-stone-100 hover:text-stone-900 transition-all text-left"><Utensils className="size-5" /><span>Menu Mingguan</span></Link>
            <Link to="/admin/customers" className="w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl text-stone-600 hover:bg-stone-100 hover:text-stone-900 transition-all text-left"><Users className="size-5" /><span>Pelanggan</span></Link>
            <Link to="/admin/production" className="w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl text-stone-600 hover:bg-stone-100 hover:text-stone-900 transition-all text-left"><Layers className="size-5" /><span>Batch Produksi</span></Link>
            <Link to="/admin/delivery" className="w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl text-stone-600 hover:bg-stone-100 hover:text-stone-900 transition-all text-left"><Truck className="size-5" /><span>Pengiriman & Rute</span></Link>
            <Link to="/admin/campaigns" className="w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl text-stone-600 hover:bg-stone-100 hover:text-stone-900 transition-all text-left"><MessageSquare className="size-5" /><span>Kampanye CRM</span></Link>
          </nav>
        </div>

        {/* User profile & Logout */}
        <div className="p-4 border-t border-stone-100">
          <div className="flex items-center gap-3 p-2 rounded-2xl bg-stone-50 border border-stone-200/60">
            <div className="size-10 rounded-full bg-amber-100 border border-amber-300 text-amber-900 font-bold flex items-center justify-center text-sm shrink-0">
              {customer?.display_name?.[0] || 'A'}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-bold text-stone-900 truncate">
                {customer?.display_name || customer?.username || 'Admin Dova'}
              </p>
              <p className="text-[11px] text-stone-500">Kitchen & Ops Lead</p>
            </div>
            <button
              onClick={logout}
              className="text-stone-400 hover:text-rose-600 transition-colors p-1"
              title="Keluar"
            >
              <LogOut className="size-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* ── 2. Main Content Area ────────────────────────────────────────────── */}
      <main className="flex-1 p-4 md:p-8 overflow-y-auto space-y-6">
        {/* ── Top Bar (Greeting & Date) ── */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-extrabold text-stone-900 tracking-tight">Operasional Dova Kitchen</h1>
            <p className="text-xs text-stone-500 font-medium mt-1">{currentDateString}</p>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={refreshData}
              disabled={loading}
              className="rounded-full bg-white border-stone-200 text-stone-700 shadow-2xs gap-1.5 text-xs font-bold"
            >
              <RefreshCw className={cn('size-3.5', loading && 'animate-spin text-amber-600')} />
              Sinkron Supabase
            </Button>

            <Button
              onClick={() => navigate('/admin/daily-menu')}
              className="rounded-full bg-amber-400 hover:bg-red-900 text-stone-950 font-extrabold text-xs px-5 py-2.5 shadow-md shadow-red-900/20 gap-1.5"
            >
              <Plus className="size-4" />
              UNGGAH MENU HARIAN
            </Button>
          </div>
        </div>

        {/* ── CONDITIONAL VIEW SWITCHER ─────────────────────────────── */}
        {dataWarning && (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-900">
            <p className="font-extrabold">Data dashboard belum lengkap</p>
            <p className="mt-1 break-words">{dataWarning}</p>
            <p className="mt-1 text-rose-700">Pastikan login memakai role admin dan backend berjalan di http://localhost:8000.</p>
          </div>
        )}

        {activeTab === 'analytics' && (
          <AdminAnalyticsView
            initialSubTab={analyticsSubTab}
            onOpenTelegram={(recipient) => {
              setTelegramRecipient(recipient)
              setShowTelegramModal(true)
            }}
          />
        )}

        {activeTab === 'dashboard' && (
          <>
            {/* ── Top 3 Metric Cards (Image 1 Bitepoint exact layout) ── */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Card 1: live active queue */}
              <div className="rounded-3xl bg-[#0D4738] text-white p-5 shadow-lg shadow-emerald-950/10 flex items-center justify-between">
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-emerald-200">Pesanan Aktif</p>
                  <h2 className="text-3xl md:text-4xl font-black">{adminOverview?.active_orders ?? metrics.new_orders}</h2>
                  <p className="text-[11px] text-emerald-300 font-normal">
                    Pending + diproses + siap
                  </p>
                </div>
                <div className="size-12 rounded-2xl bg-white/10 border border-white/20 flex items-center justify-center text-white">
                  <Bell className="size-6 text-emerald-300" />
                </div>
              </div>

              {/* Card 2: completed today */}
              <div className="rounded-3xl bg-white border border-stone-200/90 p-5 shadow-2xs flex items-center justify-between">
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-stone-500">Selesai Hari Ini</p>
                  <h2 className="text-3xl md:text-4xl font-black text-stone-900">
                    {adminOverview?.completed_today ?? metrics.total_orders}
                  </h2>
                  <p className="text-[11px] text-stone-500 font-semibold flex items-center gap-1">
                    Dibatalkan: {adminOverview?.cancelled_today ?? 0}
                  </p>
                </div>
                <div className="size-12 rounded-2xl bg-stone-100 flex items-center justify-center text-stone-600">
                  <CheckCircle2 className="size-6 text-emerald-600" />
                </div>
              </div>

              {/* Card 3: live kitchen latency */}
              <div className="rounded-3xl bg-white border border-stone-200/90 p-5 shadow-2xs flex items-center justify-between">
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-stone-500">Rata-rata Tunggu</p>
                  <h2 className="text-3xl md:text-4xl font-black text-stone-900">
                    {adminOverview?.average_wait_minutes ?? metrics.waiting_list} <span className="text-base font-bold">mnt</span>
                  </h2>
                  <p className="text-[11px] text-amber-600 font-semibold flex items-center gap-1">
                    Tiket tertua: {adminOverview?.oldest_ticket_minutes ?? 0} mnt
                  </p>
                </div>
                <div className="size-12 rounded-2xl bg-amber-50 flex items-center justify-center text-amber-600">
                  <Clock className="size-6" />
                </div>
              </div>
            </div>

            {/* ── Trending Orders & Admin Alert Banner ── */}
            <div className="rounded-3xl bg-gradient-to-r from-amber-500 via-orange-500 to-rose-600 p-5 text-white shadow-md flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-start gap-3.5">
                <div className="size-10 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center shrink-0">
                  <Flame className="size-6 text-yellow-200 animate-bounce" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-extrabold text-sm uppercase tracking-wider text-yellow-200">
                      Trending Order Alert
                    </span>
                    <Badge className="bg-white/20 text-white text-[10px] px-2 py-0 border-none">
                      {adminOverview?.pending_orders ?? 0} menunggu
                    </Badge>
                  </div>
                  <p className="text-xs text-white/95 mt-0.5 leading-relaxed max-w-2xl">
                    Panel ini memakai ringkasan live. Forecast, BOM, dan PO tetap memiliki gate masing-masing; tidak ada angka kapasitas contoh yang ditampilkan sebagai fakta.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <Button
                  size="sm"
                  onClick={() => setActiveTab('suppliers')}
                  className="rounded-full bg-white text-stone-900 hover:bg-stone-100 font-bold text-xs shadow-sm"
                >
                  <Truck className="size-3.5 mr-1 text-rose-600" />
                  Buka workflow Supplier/PO
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setTelegramRecipient({
                      type: 'customer',
                      name: '',
                      chatId: '',
                      message: '',
                    })
                    setShowTelegramModal(true)
                  }}
                  className="rounded-full border-white/40 bg-white/10 hover:bg-white/20 text-white font-bold text-xs"
                >
                  <Send className="size-3.5 mr-1" />
                  Kirim via Telegram
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
              <section className="rounded-3xl bg-slate-950 p-5 text-white shadow-lg shadow-slate-950/10">
                <div className="flex items-start justify-between gap-4 mb-4">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.18em] text-indigo-300 font-bold">Koneksi AI & kanal</p>
                    <h3 className="mt-1 text-lg font-extrabold">Chatbot terhubung di mana?</h3>
                  </div>
                  <Bot className="size-6 text-indigo-300" />
                </div>
                <div className="space-y-3 text-xs">
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-bold">Web Chatbot Chef BOB</span>
                      <span className="flex items-center gap-1.5 text-[10px] font-bold">
                        {systemStatus?.langflow_configured ? <CircleCheck className="size-4 text-emerald-300" /> : <CircleX className="size-4 text-rose-300" />}
                        {systemStatus ? (systemStatus.langflow_configured ? 'Flow ID terpasang' : 'Belum dikonfigurasi') : 'Memuat...'}
                      </span>
                    </div>
                    <p className="mt-1 text-white/65">React → <code className="text-indigo-200">POST /api/ai/consult</code> → Langflow. API key hanya berada di backend.</p>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-bold">Telegram Bot</span>
                      <Badge className="border-none bg-sky-400/15 text-sky-200 text-[10px]">{systemStatus?.telegram_bot_username ? `@${systemStatus.telegram_bot_username.replace(/^@/, '')}` : 'Belum dikonfigurasi'}</Badge>
                    </div>
                    <p className="mt-1 text-white/65">`telegram_bot.py` memakai endpoint AI yang sama. Approval PO admin memakai route Telegram internal terpisah.</p>
                  </div>
                </div>
              </section>

              <section className="rounded-3xl bg-white p-5 border border-stone-200/90 shadow-2xs">
                <div className="flex items-start justify-between gap-4 mb-4">
                  <div>
                    <p className="text-[10px] uppercase tracking-[0.18em] text-amber-600 font-bold">Live operations snapshot</p>
                    <h3 className="mt-1 text-lg font-extrabold text-stone-900">Yang perlu ditindak hari ini</h3>
                  </div>
                  <Badge className={cn(
                    'border-none text-[10px]',
                    systemStatus?.demo_mode
                      ? 'bg-amber-100 text-amber-800'
                      : systemStatus?.supabase_connected
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-rose-100 text-rose-800'
                  )}>
                    {systemStatus
                      ? systemStatus.demo_mode
                        ? 'Demo mode'
                        : systemStatus.supabase_connected
                        ? 'Supabase live'
                        : 'Database offline'
                      : 'Memuat status DB'}
                  </Badge>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                  {[
                    ['Menunggu', adminOverview?.pending_orders ?? '-'],
                    ['Dimasak', adminOverview?.preparing_orders ?? '-'],
                    ['Siap', adminOverview?.packed_orders ?? '-'],
                    ['Safety alert', adminOverview?.safety_alerts ?? '-'],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-2xl bg-stone-50 border border-stone-100 p-3">
                      <span className="block text-stone-500">{label}</span>
                      <strong className="mt-1 block text-xl text-stone-900">{value}</strong>
                    </div>
                  ))}
                </div>
                <p className="mt-4 text-[11px] text-stone-500">Pelanggan: <strong>{adminOverview?.total_customers ?? '-'}</strong> · Tertaut Telegram: <strong>{adminOverview?.verified_customers ?? '-'}</strong> · Diperbarui: {adminOverview?.generated_at ? formatOrderDate(adminOverview.generated_at) : 'memuat'}</p>
              </section>
            </div>

            {/* ── Main 3 Columns: [Order List KDS] | [Payment] | [Popular Dishes & Out of Stock] ── */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* ── COLUMN 1: Order List (KDS & Kitchen Queue) (Col-span 4) ── */}
              <div className="lg:col-span-4 bg-white rounded-3xl p-5 border border-stone-200/90 shadow-2xs space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-extrabold text-base text-stone-900">Order List</h3>
                  <Badge variant="outline" className="text-xs font-bold text-stone-600">
                    {filteredOrders.length} Pesanan
                  </Badge>
                </div>

                {/* Search a Order input */}
                <div className="relative">
                  <Search className="absolute left-3.5 top-2.5 size-4 text-stone-400" />
                  <Input
                    value={searchOrder}
                    onChange={(e) => setSearchOrder(e.target.value)}
                    placeholder="Search a Order..."
                    className="rounded-2xl pl-10 pr-3 py-2 text-xs bg-stone-50 border-stone-200 focus-visible:ring-amber-400"
                  />
                </div>

                {/* Order Items */}
                <div className="space-y-2.5 max-h-[580px] overflow-y-auto pr-1">
                  {filteredOrders.map((order, idx) => {
                    const code = order.table_code || `A${idx + 1}`
                    const isReady = order.status === 'READY'
                    const isCooking = order.status === 'PREPARING'
                    const isCompleted = order.status === 'COMPLETED'

                    return (
                      <div
                        key={order.order_id || idx}
                        className="p-3.5 rounded-2xl border border-stone-100 hover:border-amber-300 hover:bg-amber-50/20 transition-all flex items-center justify-between gap-3 group"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          {/* Avatar Badge (A4, B2, TA, etc.) */}
                          <div
                            className={cn(
                              'size-11 rounded-2xl flex items-center justify-center font-black text-sm text-white shrink-0 shadow-2xs',
                              isReady
                                ? 'bg-emerald-700'
                                : isCooking
                                ? 'bg-amber-600'
                                : isCompleted
                                ? 'bg-teal-800'
                                : 'bg-stone-700'
                            )}
                          >
                            {code}
                          </div>

                          <div className="min-w-0">
                            <div className="flex items-center gap-1.5">
                              <p className="text-xs font-bold text-stone-900 truncate">
                                {order.customer_name || 'Pelanggan'}
                              </p>
                              <span className="text-[10px] text-stone-400 font-mono">
                                #{order.order_id?.slice(-5)}
                              </span>
                            </div>
                            <p className="text-[11px] text-stone-500">
                              {order.items_count || order.item_count || 3} Items • {order.hari || 'Hari ini'}
                            </p>
                            <div className="flex items-center gap-1 text-[10px] font-semibold text-amber-800 bg-amber-50 px-2 py-0.5 rounded-md w-fit mt-1 border border-amber-200/60">
                              <Calendar className="size-2.5 text-amber-600" />
                              <span>Pesan: {formatOrderDate(order.created_at)}</span>
                            </div>
                          </div>
                        </div>

                        <div className="text-right shrink-0 space-y-1">
                          {/* Status Tag */}
                          {isReady && (
                            <div className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <Check className="size-3" /> Ready to serve
                            </div>
                          )}
                          {isCooking && (
                            <div className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                              <Clock className="size-3" /> Cooking Now
                            </div>
                          )}
                          {isCompleted && (
                            <div className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-stone-100 text-stone-600 border border-stone-200">
                              <CheckCircle2 className="size-3" /> Completed
                            </div>
                          )}
                          {!isReady && !isCooking && !isCompleted && (
                            <div className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
                              Menunggu Dapur
                            </div>
                          )}

                          {/* Advance Button */}
                          <div>
                            <button
                              onClick={() => handleAdvanceStatus(order.order_id, order.status)}
                              className="text-[10px] font-bold text-amber-700 hover:text-amber-800 hover:underline block ml-auto"
                            >
                              {isCooking ? 'Tandai Siap →' : isReady ? 'Selesaikan →' : 'Mulai Masak →'}
                            </button>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* ── COLUMN 2: Payment (Col-span 4) ── */}
              <div className="lg:col-span-4 bg-white rounded-3xl p-5 border border-stone-200/90 shadow-2xs space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-extrabold text-base text-stone-900">Payment</h3>
                  <Badge variant="outline" className="text-xs font-bold text-stone-600">
                    Kasir & QRIS
                  </Badge>
                </div>

                {/* Search a Order input */}
                <div className="relative">
                  <Search className="absolute left-3.5 top-2.5 size-4 text-stone-400" />
                  <Input
                    value={searchPayment}
                    onChange={(e) => setSearchPayment(e.target.value)}
                    placeholder="Search a Order..."
                    className="rounded-2xl pl-10 pr-3 py-2 text-xs bg-stone-50 border-stone-200 focus-visible:ring-amber-400"
                  />
                </div>

                {/* Payment Items */}
                <div className="space-y-2.5 max-h-[580px] overflow-y-auto pr-1">
                  {paymentOrders.map((order, idx) => {
                    const code = `C${idx + 1}`
                    const isPaid = String(order.payment_status || '').toUpperCase() === 'PAID'

                    return (
                      <div
                        key={order.order_id || idx}
                        className="p-3.5 rounded-2xl border border-stone-100 hover:border-amber-300 transition-all flex items-center justify-between gap-3"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="size-11 rounded-2xl bg-teal-800 flex items-center justify-center font-black text-sm text-white shrink-0 shadow-2xs">
                            {code}
                          </div>

                          <div className="min-w-0">
                            <p className="text-xs font-bold text-stone-900 truncate">
                              {order.customer_name || 'Pelanggan'}
                            </p>
                            <p className="text-[11px] text-stone-500">
                              {order.order_id} • Rp {(order.total || 84000).toLocaleString('id-ID')}
                            </p>
                            <div className="flex items-center gap-1 text-[10px] font-semibold text-stone-500 mt-1">
                              <Calendar className="size-2.5 text-stone-400" />
                              <span>Tgl: {formatOrderDate(order.created_at)}</span>
                            </div>
                          </div>
                        </div>

                        <div>
                          {isPaid ? (
                            <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-full border border-emerald-200 flex items-center gap-1">
                              <Check className="size-3" /> Lunas
                            </span>
                          ) : (
                            <Button
                              size="sm"
                              onClick={() => setSelectedOrderForPay(order)}
                              className="rounded-xl bg-amber-400 hover:bg-red-900 text-stone-950 font-bold text-xs px-3.5 py-1.5 h-auto shadow-2xs"
                            >
                              Pay Now →
                            </Button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* ── COLUMN 3: Popular Dishes & Out of Stock Alerts (Col-span 4) ── */}
              <div className="lg:col-span-4 space-y-6">
                {/* Popular Dishes Card (Image 1 top right) */}
                <div className="bg-white rounded-3xl p-5 border border-stone-200/90 shadow-2xs space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="font-extrabold text-base text-stone-900">Popular Dishes</h3>
                    <button
                      onClick={() => navigate('/admin/daily-menu')}
                      className="text-xs font-bold text-amber-600 hover:underline"
                    >
                      View All
                    </button>
                  </div>

                  <div className="space-y-3">
                    {popularDishes.length === 0 ? <p className="rounded-xl bg-stone-50 p-4 text-xs text-stone-500">Belum ada agregasi menu terlaris dari data order.</p> : popularDishes.map((dish, idx) => (
                      <div key={idx} className="flex items-center gap-3">
                        <span className="text-xs font-black text-stone-400 w-5">{dish.rank}</span>
                        <div aria-hidden="true" className="size-11 rounded-2xl bg-rose-50 border border-rose-100 text-rose-800 flex items-center justify-center shrink-0">
                          <Utensils className="size-5" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-bold text-stone-900 truncate">{dish.name}</p>
                          <p className="text-[11px] text-stone-500">Orders : {dish.orders}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Out of Stock Card (Image 1 bottom right) */}
                <div className="bg-white rounded-3xl p-5 border border-stone-200/90 shadow-2xs space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="font-extrabold text-base text-stone-900">Stok & Bahan Kritis</h3>
                    <button
                      onClick={() => setActiveTab('inventory')}
                      className="text-xs font-bold text-amber-600 hover:underline"
                    >
                      View All
                    </button>
                  </div>

                  <div className="space-y-3">
                    {inventoryAlerts.length > 0 ? (
                      inventoryAlerts.slice(0, 4).map((item) => (
                        <div
                          key={item.id}
                          className="flex items-center justify-between p-2.5 rounded-2xl bg-stone-50 border border-stone-100"
                        >
                          <div className="min-w-0">
                            <p className="text-xs font-bold text-stone-900 truncate">
                              {item.ingredient_name}
                            </p>
                            <p className="text-[11px] text-stone-500">
                              Sisa: {item.current_stock} {item.unit} (Min: {item.min_stock} {item.unit})
                            </p>
                          </div>
                          <Badge
                            className={cn(
                              'text-[10px] px-2 py-0.5 border-none font-bold',
                              item.status === 'HABIS'
                                ? 'bg-rose-500 text-white'
                                : item.status === 'MENIPIS'
                                ? 'bg-amber-500 text-white'
                                : 'bg-emerald-500 text-white'
                            )}
                          >
                            {item.status}
                          </Badge>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-4 text-xs text-stone-400">
                        Semua stok bahan baku saat ini berada dalam batas aman.
                      </div>
                    )}
                  </div>
                </div>

                {/* Quick Action: Telegram Outbox Log */}
                <div className="bg-white rounded-3xl p-5 border border-stone-200/90 shadow-2xs space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="font-extrabold text-base text-stone-900 flex items-center gap-1.5">
                      <MessageSquare className="size-4 text-emerald-600" />
                      Telegram Outbox Log
                    </h3>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setTelegramRecipient({ type: 'customer', name: '', chatId: '', message: '' })
                        setShowTelegramModal(true)
                      }}
                      className="rounded-full text-[11px] h-7 font-bold border-stone-200"
                    >
                      + Tulis Pesan
                    </Button>
                  </div>

                  <div className="space-y-2 max-h-44 overflow-y-auto text-xs">
                    {notifications.slice(0, 3).map((n) => (
                      <div
                        key={n.id}
                        className="p-2.5 rounded-xl bg-stone-50 border border-stone-100 space-y-1"
                      >
                        <div className="flex items-center justify-between text-[11px] font-bold">
                          <span className="text-stone-800 truncate">{n.recipient_name} ({n.recipient_chat_id || 'chat ID belum ada'})</span>
                          <span className="text-emerald-700 bg-emerald-100/60 px-1.5 py-0.2 rounded font-semibold text-[10px]">
                            {n.status}
                          </span>
                        </div>
                        <p className="text-[11px] text-stone-600 line-clamp-2 leading-relaxed">
                          {n.message}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        {/* ── TAB INVENTORY ────────────────────────────────────────────── */}
        {activeTab === 'inventory' && (
          <div className="bg-white rounded-3xl p-6 border border-stone-200/90 shadow-2xs space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-extrabold text-lg text-stone-900">Manajemen Stok & Bahan Baku</h3>
                <p className="text-xs text-stone-500">Monitoring level persediaan bahan baku kitchen secara realtime.</p>
              </div>
              <Button
                size="sm"
                onClick={() => setActiveTab('analytics')}
                className="rounded-full bg-amber-400 hover:bg-red-900 text-stone-950 font-bold text-xs"
              >
                Cek Perhitungan ROP Machine Learning →
              </Button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead className="bg-[#14213D] text-white text-[11px] font-bold">
                  <tr>
                    <th className="py-3 px-3">Bahan Baku</th>
                    <th className="py-3 px-3 text-right">Stok Gudang</th>
                    <th className="py-3 px-3 text-right">Batas Minimum</th>
                    <th className="py-3 px-3 text-center">Status</th>
                    <th className="py-3 px-3 text-center">Tindakan Restock</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 font-sans">
                  {inventoryAlerts.map((item) => (
                    <tr key={item.id} className="hover:bg-stone-50">
                      <td className="py-3 px-3 font-bold text-stone-900">{item.ingredient_name}</td>
                      <td className="py-3 px-3 text-right font-mono font-bold text-stone-900">
                        {item.current_stock} {item.unit}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-stone-500">
                        {item.min_stock} {item.unit}
                      </td>
                      <td className="py-3 px-3 text-center">
                        <Badge
                          className={cn(
                            'text-[10px] font-bold px-2 py-0.5 border-none',
                            item.status === 'HABIS'
                              ? 'bg-rose-600 text-white animate-pulse'
                              : item.status === 'MENIPIS'
                              ? 'bg-amber-500 text-white'
                              : 'bg-emerald-600 text-white'
                          )}
                        >
                          {item.status}
                        </Badge>
                      </td>
                      <td className="py-3 px-3 text-center">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => void handleCreateProcurementDraft()}
                          className="rounded-full text-xs font-bold text-red-800 border-red-300 bg-red-50 hover:bg-red-100"
                        >
                          Buat draft PO
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── TAB SUPPLIERS ────────────────────────────────────────────── */}
        {activeTab === 'suppliers' && (
          <div className="space-y-6">
            <div className="bg-white rounded-3xl p-6 border border-stone-200/90 shadow-2xs space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-extrabold text-lg text-stone-900">Daftar Mitra Supplier Terverifikasi</h3>
                  <p className="text-xs text-stone-500">Vendor bahan pangan organik bersertifikasi Dova Kitchen.</p>
                </div>
                <Badge variant="outline">Data supplier live</Badge>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                {suppliers.map((s) => (
                  <div key={s.supplier_id} className="p-4 rounded-2xl bg-stone-50 border border-stone-200/80 space-y-2">
                    <div className="flex items-start justify-between">
                      <h4 className="font-bold text-sm text-stone-900">{s.name}</h4>
                      <Badge className="bg-amber-100 text-amber-800 border-none text-[10px] font-bold">
                        ★ {s.rating}
                      </Badge>
                    </div>
                    <p className="text-xs text-stone-500 font-mono">Kontak internal: {s.phone || '-'}</p>
                    <p className={cn('text-[11px] font-semibold', s.telegram_chat_id ? 'text-sky-700' : 'text-rose-600')}>
                      Telegram: {s.telegram_chat_id ? `chat ID ${s.telegram_chat_id}` : 'belum tertaut'}
                    </p>
                    <p className="text-[11px] text-stone-600">{s.address}</p>
                    <div className="pt-2 flex justify-end">
                      <Button
                        size="sm"
                        disabled={!s.telegram_chat_id}
                        onClick={() => {
                          setTelegramRecipient({
                            type: 'supplier',
                            name: s.name,
                            chatId: String(s.telegram_chat_id || s.telegram_chat_id_supplier || ''),
                            message: `Halo ${s.name}! Kami ingin mengecek ketersediaan bahan baku untuk katering Dova Kitchen minggu depan.`,
                          })
                          setShowTelegramModal(true)
                        }}
                        className="rounded-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs h-7 disabled:cursor-not-allowed disabled:bg-stone-300"
                      >
                        Hubungi Telegram
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-3xl p-6 border border-stone-200/90 shadow-2xs space-y-4">
              <div>
                <h3 className="font-extrabold text-lg text-stone-900">Invoice Supplier & Three-Way Match</h3>
                <p className="text-xs text-stone-500">Invoice tidak dianggap lunas sebelum admin memverifikasi PO, goods receipt, dan nilai tagihan.</p>
              </div>
              {supplierInvoiceWarning && (
                <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-950">
                  <p className="font-bold">Invoice supplier belum tersambung</p>
                  <p className="mt-1">{supplierInvoiceWarning}</p>
                  <p className="mt-1 font-mono">supabase/migrations/015_goods_receipt.sql → 016_supplier_billing.sql</p>
                </div>
              )}
              {!supplierInvoices.length ? <p className="rounded-2xl border border-dashed border-stone-200 p-5 text-sm text-stone-500">{supplierInvoiceWarning ? 'Daftar invoice belum bisa dibaca sebelum migration Supabase diterapkan.' : 'Belum ada invoice supplier.'}</p> : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left border-collapse">
                    <thead className="bg-[#14213D] text-white text-[11px] font-bold"><tr><th className="py-3 px-3">Invoice</th><th className="py-3 px-3">Supplier</th><th className="py-3 px-3">PO</th><th className="py-3 px-3 text-right">Nilai / Expected</th><th className="py-3 px-3">Match</th><th className="py-3 px-3 text-center">Aksi</th></tr></thead>
                    <tbody className="divide-y divide-stone-100">
                      {supplierInvoices.map((invoice) => <tr key={invoice.supplier_invoice_id}><td className="py-3 px-3 font-bold">{invoice.invoice_number}<span className="block text-[10px] text-stone-500">{invoice.payment_terms} · jatuh tempo {invoice.due_date}</span></td><td className="py-3 px-3">{invoice.supplier_name || invoice.supplier_id}</td><td className="py-3 px-3 font-mono">{(invoice.po_ids || []).join(', ') || '-'}</td><td className="py-3 px-3 text-right font-mono">Rp {Number(invoice.amount || 0).toLocaleString('id-ID')}<span className="block text-[10px] text-stone-500">expected Rp {Number(invoice.expected_amount || 0).toLocaleString('id-ID')}</span></td><td className="py-3 px-3"><Badge className={cn('border-none text-[10px]', invoice.match_status === 'MATCHED' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-800')}>{invoice.match_status}</Badge></td><td className="py-3 px-3"><div className="flex justify-center gap-1">{invoice.status === 'SUBMITTED' && <><Button size="sm" onClick={() => void handleVerifySupplierInvoice(invoice.supplier_invoice_id, 'APPROVE')} className="h-7 rounded-full bg-emerald-600 text-[10px] text-white">Approve</Button><Button size="sm" onClick={() => void handleVerifySupplierInvoice(invoice.supplier_invoice_id, 'REJECT')} className="h-7 rounded-full bg-rose-600 text-[10px] text-white">Reject</Button></>}{invoice.status === 'APPROVED' && <Button size="sm" onClick={() => void handlePaySupplierInvoice(invoice)} className="h-7 rounded-full bg-amber-400 text-[10px] font-bold text-stone-950">Catat Bayar</Button>}{invoice.status !== 'SUBMITTED' && invoice.status !== 'APPROVED' && <span className="text-[10px] text-stone-400">{invoice.status}</span>}</div></td></tr>)}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Purchase Orders Table */}
            <div className="bg-white rounded-3xl p-6 border border-stone-200/90 shadow-2xs space-y-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h3 className="font-extrabold text-lg text-stone-900">Riwayat Purchase Order (PO)</h3>
                  <p className="text-xs text-stone-500">Draft hanya dibuat dari sourcing live; approval dan queue tetap manual.</p>
                </div>
                <Button
                  size="sm"
                  onClick={handleCreateProcurementDraft}
                  className="rounded-full bg-red-800 text-white font-bold text-xs"
                >
                  Buat draft dari sourcing live
                </Button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead className="bg-[#14213D] text-white text-[11px] font-bold">
                    <tr>
                      <th className="py-3 px-3">PO ID</th>
                      <th className="py-3 px-3">Supplier</th>
                      <th className="py-3 px-3 text-right">Total Nilai</th>
                      <th className="py-3 px-3 text-center">Status PO</th>
                      <th className="py-3 px-3">Tgl Butuh</th>
                      <th className="py-3 px-3 text-center">Tindakan</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100 font-sans">
                    {purchaseOrders.map((po) => (
                      <tr key={po.po_id} className="hover:bg-stone-50">
                        <td className="py-2.5 px-3 font-mono font-bold text-stone-900">{po.po_id}</td>
                        <td className="py-2.5 px-3 font-semibold text-stone-800">{po.supplier_name}</td>
                        <td className="py-2.5 px-3 text-right font-mono font-bold text-emerald-700">
                          Rp {(po.total_amount || 0).toLocaleString('id-ID')}
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <Badge className="bg-blue-100 text-blue-800 border-none font-bold text-[10px]">
                            {po.status}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-3 text-stone-500 font-mono text-[11px]">
                          {po.need_by_date || '-'}
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <div className="flex justify-center gap-1">
                            {po.status === 'DRAFT' && (
                              <Button
                                size="sm"
                                onClick={() => handleApproveProcurementDraft(po.po_id)}
                                className="h-7 rounded-full bg-emerald-600 text-white text-[10px] font-bold"
                              >
                                Approve
                              </Button>
                            )}
                            {po.status === 'APPROVED' && (
                              <Button
                                size="sm"
                                onClick={() => handleQueueProcurementDelivery(po.po_id)}
                                className="h-7 rounded-full bg-blue-600 text-white text-[10px] font-bold"
                              >
                                Queue delivery
                              </Button>
                            )}
                            {po.status !== 'DRAFT' && po.status !== 'APPROVED' && (
                              <span className="text-[10px] text-stone-400">-</span>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB MARKETING ────────────────────────────────────────────── */}
        {activeTab === 'marketing' && (
          <div className="bg-white rounded-3xl p-6 border border-stone-200/90 shadow-2xs space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-extrabold text-lg text-stone-900 flex items-center gap-2">
                  <MessageSquare className="size-5 text-emerald-600" />
                  Telegram Ops & CRM Outbox
                </h3>
                <p className="text-xs text-stone-500">Log pengiriman pesan otomatis ke pelanggan dan supplier.</p>
              </div>
              <Button
                onClick={() => {
                  setTelegramRecipient({ type: 'customer', name: '', chatId: '', message: '' })
                  setShowTelegramModal(true)
                }}
                className="rounded-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs"
              >
                + Tulis Pesan Telegram Baru
              </Button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead className="bg-[#14213D] text-white text-[11px] font-bold">
                  <tr>
                    <th className="py-3 px-3">Tgl & Jam</th>
                    <th className="py-3 px-3">Penerima</th>
                    <th className="py-3 px-3">Tipe</th>
                    <th className="py-3 px-3">Isi Pesan</th>
                    <th className="py-3 px-3 text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 font-sans">
                  {notifications.map((n) => (
                    <tr key={n.id} className="hover:bg-stone-50">
                      <td className="py-2.5 px-3 font-mono text-[11px] text-stone-500">
                        {formatOrderDate(n.created_at)}
                      </td>
                      <td className="py-2.5 px-3">
                        <p className="font-bold text-stone-900">{n.recipient_name}</p>
                        <p className="text-[10px] text-stone-400 font-mono">chat ID: {n.recipient_chat_id || '-'}</p>
                      </td>
                      <td className="py-2.5 px-3 uppercase text-[10px] font-bold text-stone-500">
                        {n.recipient_type}
                      </td>
                      <td className="py-2.5 px-3 text-stone-700 max-w-md">
                        {n.message}
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <Badge className="bg-emerald-100 text-emerald-800 border-none font-bold text-[10px]">
                          {n.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>


      {/* ── Modal Verifikasi Pembayaran ────────────────────────────────────── */}
      {selectedOrderForPay && (
        <div className="fixed inset-0 z-50 bg-stone-950/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-stone-200 space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between">
              <h3 className="font-extrabold text-lg text-stone-900">Verifikasi Pembayaran</h3>
              <button
                onClick={() => setSelectedOrderForPay(null)}
                className="text-stone-400 hover:text-stone-600"
              >
                <X className="size-5" />
              </button>
            </div>

            <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-xs space-y-2">
              <div className="flex justify-between font-semibold">
                <span>Order ID:</span>
                <span className="font-mono">{selectedOrderForPay.order_id}</span>
              </div>
              <div className="flex justify-between font-semibold">
                <span>Nama Pelanggan:</span>
                <span>{selectedOrderForPay.customer_name}</span>
              </div>
              <div className="flex justify-between text-base font-extrabold text-amber-950 pt-2 border-t border-amber-200">
                <span>Total Tagihan:</span>
                <span>Rp {(selectedOrderForPay.total || 84000).toLocaleString('id-ID')}</span>
              </div>
            </div>

            <p className="text-xs text-stone-500 leading-relaxed">
              Konfirmasi bahwa uang telah masuk ke rekening / QRIS Midtrans Dova Kitchen. Tiket dapur akan otomatis dibuka untuk koki memasak.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <Button
                variant="outline"
                onClick={() => setSelectedOrderForPay(null)}
                className="rounded-full text-xs font-bold"
              >
                Batal
              </Button>
              <Button
                onClick={() => handleConfirmPayment(selectedOrderForPay.order_id)}
                className="rounded-full bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-xs px-5 shadow-sm"
              >
                Konfirmasi LUNAS
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal Telegram Admin ───────────────────────────────────────────── */}
      {showTelegramModal && (
        <div className="fixed inset-0 z-50 bg-stone-950/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-stone-200 space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between">
              <h3 className="font-extrabold text-lg text-stone-900 flex items-center gap-2">
                <MessageSquare className="size-5 text-emerald-600" />
                Queue Pesan Telegram
              </h3>
              <button
                onClick={() => setShowTelegramModal(false)}
                className="text-stone-400 hover:text-stone-600"
              >
                <X className="size-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="font-bold text-stone-700 block mb-1">Tipe Penerima</label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setTelegramRecipient((p) => ({ ...p, type: 'customer' }))}
                    className={cn(
                      'flex-1 py-1.5 rounded-xl border font-bold transition-all',
                      telegramRecipient.type === 'customer'
                        ? 'bg-red-800 text-white border-amber-500'
                        : 'bg-stone-50 border-stone-200 text-stone-600'
                    )}
                  >
                    Pelanggan
                  </button>
                  <button
                    type="button"
                    onClick={() => setTelegramRecipient((p) => ({ ...p, type: 'supplier' }))}
                    className={cn(
                      'flex-1 py-1.5 rounded-xl border font-bold transition-all',
                      telegramRecipient.type === 'supplier'
                        ? 'bg-red-800 text-white border-amber-500'
                        : 'bg-stone-50 border-stone-200 text-stone-600'
                    )}
                  >
                    Supplier
                  </button>
                </div>
              </div>

              <div>
                <label className="font-bold text-stone-700 block mb-1">Nama Penerima</label>
                <Input
                  value={telegramRecipient.name}
                  onChange={(e) => setTelegramRecipient((p) => ({ ...p, name: e.target.value }))}
                  placeholder="Contoh: Joshua / Pak Hadi Supplier"
                  className="rounded-xl text-xs"
                />
              </div>

              <div>
                <label className="font-bold text-stone-700 block mb-1">Telegram chat ID</label>
                <Input
                  value={telegramRecipient.chatId}
                  onChange={(e) => setTelegramRecipient((p) => ({ ...p, chatId: e.target.value }))}
                  placeholder="Contoh: 123456789"
                  className="rounded-xl text-xs font-mono"
                />
                <p className="mt-1 text-[10px] text-stone-500">Chat ID harus berasal dari user/supplier yang sudah memulai chat dengan bot Telegram Dova.</p>
              </div>

              <div>
                <label className="font-bold text-stone-700 block mb-1">Isi Pesan Telegram</label>
                <textarea
                  rows={4}
                  value={telegramRecipient.message}
                  onChange={(e) => setTelegramRecipient((p) => ({ ...p, message: e.target.value }))}
                  placeholder="Ketik pesan..."
                  className="w-full rounded-xl border border-stone-200 p-2.5 text-xs focus:ring-amber-400"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <Button
                variant="outline"
                onClick={() => setShowTelegramModal(false)}
                className="rounded-full text-xs font-bold"
              >
                Batal
              </Button>
              <Button
                disabled={isSendingTelegram}
                onClick={handleSendTelegram}
                className="rounded-full bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-xs px-5 shadow-sm"
              >
                {isSendingTelegram ? 'Mengantrikan...' : 'Queue ke Telegram →'}
              </Button>
            </div>
          </div>
        </div>
      )}


    </div>
  )
}
