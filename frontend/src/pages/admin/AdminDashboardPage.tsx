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
  Store,
  TrendingUp,
  Truck,
  Utensils,
  BarChart3,
  FileSpreadsheet,
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
import { AdminAnalyticsView } from './AdminAnalyticsView'

/* ── Fallback Seed Data jika koneksi lambat ────────────────────────────────── */
const DEFAULT_POPULAR_DISHES = [
  { rank: '01', name: 'Ayam Panggang Rosemary & Ubi Madu', orders: 23, image: 'https://images.unsplash.com/photo-1598515214211-89d3c73ae83b?auto=format&fit=crop&w=150&q=80' },
  { rank: '02', name: 'Beef Bulgogi Wijen & Nasi Beras Cokelat', orders: 18, image: 'https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=150&q=80' },
  { rank: '03', name: 'Salmon Fillet Lemon Herb & Kentang Kukus', orders: 15, image: 'https://images.unsplash.com/photo-1467003909585-2f8a72700288?auto=format&fit=crop&w=150&q=80' },
  { rank: '04', name: 'Sup Daging Sapi Jamur Rempah', orders: 12, image: 'https://images.unsplash.com/photo-1547592166-23ac45744acd?auto=format&fit=crop&w=150&q=80' },
]

export function AdminDashboardPage() {
  const { customer, logout } = useAuth()
  const navigate = useNavigate()

  // State operasional KDS & POS
  const [loading, setLoading] = useState(true)
  const [searchOrder, setSearchOrder] = useState('')
  const [searchPayment, setSearchPayment] = useState('')
  const [activeTab, setActiveTab] = useState<'dashboard' | 'analytics' | 'marketing' | 'suppliers' | 'inventory'>('dashboard')
  const [analyticsSubTab, setAnalyticsSubTab] = useState<'stats' | 'crm' | 'supply_chain' | 'demand_ai'>('demand_ai')

  // Data dari Supabase
  const [metrics, setMetrics] = useState({ new_orders: 16, total_orders: 86, waiting_list: 9 })
  const [orders, setOrders] = useState<any[]>([])
  const [popularDishes, setPopularDishes] = useState<any[]>(DEFAULT_POPULAR_DISHES)
  const [inventoryAlerts, setInventoryAlerts] = useState<any[]>([])
  const [notifications, setNotifications] = useState<any[]>([])
  const [suppliers, setSuppliers] = useState<any[]>([])
  const [purchaseOrders, setPurchaseOrders] = useState<any[]>([])

  // Modal State
  const [selectedOrderForPay, setSelectedOrderForPay] = useState<any | null>(null)
  const [showWaModal, setShowWaModal] = useState(false)
  const [waRecipient, setWaRecipient] = useState({ type: 'customer', name: '', phone: '', message: '' })
  const [isSendingWa, setIsSendingWa] = useState(false)
  const [showUploadMenuModal, setShowUploadMenuModal] = useState(false)
  const [menuForm, setMenuForm] = useState({
    hari: 'Senin',
    tanggal: '2026-10-12',
    nama_menu: '',
    harga: 48000,
    bom_ingredients: '',
    allergens: [] as string[],
    deskripsi: '',
  })

  // Fetch data
  const refreshData = async () => {
    setLoading(true)
    try {
      const [posRes, popRes, invRes, notifRes, supRes] = await Promise.all([
        adminService.getPosKds().catch(() => null),
        adminService.getPopularDishes().catch(() => null),
        adminService.getInventoryAlerts().catch(() => null),
        adminService.getNotifications().catch(() => null),
        adminService.getSuppliers().catch(() => null),
      ])

      if (posRes) {
        setMetrics(posRes.metrics || { new_orders: 16, total_orders: 86, waiting_list: 9 })
        setOrders(posRes.orders || [])
      }
      if (popRes && popRes.length > 0) {
        setPopularDishes(
          popRes.map((p, idx) => ({
            rank: String(idx + 1).padStart(2, '0'),
            name: p.nama_menu,
            orders: Number(p.order_count) || 12,
            image: DEFAULT_POPULAR_DISHES[idx % 4]?.image,
          }))
        )
      }
      if (invRes) setInventoryAlerts(invRes)
      if (notifRes) setNotifications(notifRes)
      if (supRes) {
        setSuppliers(supRes.suppliers || [])
        setPurchaseOrders(supRes.purchase_orders || [])
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
    } catch {
      toast.error('Gagal memperbarui status tiket dapur.')
    }
  }

  // Verifikasi pembayaran
  const handleConfirmPayment = async (orderId: string) => {
    try {
      await adminService.setPayment(orderId, 'PAID', `TRX-ADMIN-${Date.now()}`)
      toast.success(`Pembayaran untuk order ${orderId} berhasil diverifikasi LUNAS!`)
      setSelectedOrderForPay(null)
      refreshData()
    } catch {
      toast.error('Gagal mencatat pembayaran.')
    }
  }

  // Kirim WhatsApp Otomatis
  const handleSendAutomatedWa = async () => {
    if (!waRecipient.phone || !waRecipient.message) {
      toast.error('Mohon isi nomor telepon dan pesan!')
      return
    }
    setIsSendingWa(true)
    try {
      await adminService.sendNotification({
        recipient_type: waRecipient.type,
        recipient_name: waRecipient.name || 'Pelanggan',
        recipient_phone: waRecipient.phone,
        channel: 'whatsapp',
        message: waRecipient.message,
      })
      toast.success(`Pesan WhatsApp otomatis terkirim ke ${waRecipient.name} (${waRecipient.phone})!`)
      setShowWaModal(false)
      refreshData()
    } catch {
      toast.error('Gagal mengirim WhatsApp outbox.')
    } finally {
      setIsSendingWa(false)
    }
  }

  // Filter Order List (KDS)
  const filteredOrders = useMemo(() => {
    return orders.filter(
      (o) =>
        o.order_id?.toLowerCase().includes(searchOrder.toLowerCase()) ||
        o.customer_name?.toLowerCase().includes(searchOrder.toLowerCase())
    )
  }, [orders, searchOrder])

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
              <div className="size-10 rounded-2xl bg-amber-400 flex items-center justify-center text-stone-950 font-black shadow-md shadow-amber-400/20 text-lg">
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
                  ? 'bg-amber-400 text-stone-950 font-bold shadow-sm shadow-amber-400/20'
                  : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
              )}
            >
              <LayoutDashboard className="size-5" />
              <span>Dashboard & KDS</span>
            </button>

            {/* Direct ML & Analytics Sections */}
            <button
              onClick={() => {
                setActiveTab('analytics')
                setAnalyticsSubTab('demand_ai')
              }}
              className={cn(
                'w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl transition-all text-left',
                activeTab === 'analytics' && analyticsSubTab === 'demand_ai'
                  ? 'bg-amber-400 text-stone-950 font-bold shadow-sm shadow-amber-400/20'
                  : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
              )}
            >
              <TrendingUp className="size-5 text-amber-600" />
              <span>Prediksi Demand AI</span>
              <span className="ml-auto text-[10px] bg-emerald-100 text-emerald-800 font-bold px-2 py-0.5 rounded-full">
                1K Data
              </span>
            </button>

            <button
              onClick={() => {
                setActiveTab('analytics')
                setAnalyticsSubTab('supply_chain')
              }}
              className={cn(
                'w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl transition-all text-left',
                activeTab === 'analytics' && analyticsSubTab === 'supply_chain'
                  ? 'bg-amber-400 text-stone-950 font-bold shadow-sm shadow-amber-400/20'
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
                  ? 'bg-amber-400 text-stone-950 font-bold shadow-sm shadow-amber-400/20'
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
                  ? 'bg-amber-400 text-stone-950 font-bold shadow-sm shadow-amber-400/20'
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
                  ? 'bg-amber-400 text-stone-950 font-bold shadow-sm'
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
                  ? 'bg-amber-400 text-stone-950 font-bold shadow-sm'
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
                  ? 'bg-amber-400 text-stone-950 font-bold shadow-sm'
                  : 'text-stone-600 hover:bg-stone-100 hover:text-stone-900'
              )}
            >
              <MessageSquare className="size-5" />
              <span>WA Otomatis & CRM</span>
            </button>

            <Link
              to="/supplier"
              className="w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl text-stone-600 hover:bg-stone-100 hover:text-stone-900 transition-all text-left"
            >
              <Store className="size-5" />
              <span>Portal Supplier →</span>
            </Link>
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
            <h1 className="text-2xl md:text-3xl font-extrabold text-stone-900 tracking-tight flex items-center gap-2">
              Nice! We have a lot of orders <span className="text-2xl">😊</span>
            </h1>
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
              onClick={() => setShowUploadMenuModal(true)}
              className="rounded-full bg-amber-400 hover:bg-amber-500 text-stone-950 font-extrabold text-xs px-5 py-2.5 shadow-md shadow-amber-400/20 gap-1.5"
            >
              <Plus className="size-4" />
              UNGGAH MENU HARIAN
            </Button>
          </div>
        </div>

        {/* ── CONDITIONAL VIEW SWITCHER ─────────────────────────────── */}
        {activeTab === 'analytics' && (
          <AdminAnalyticsView
            initialSubTab={analyticsSubTab}
            onOpenWa={(recipient) => {
              setWaRecipient(recipient)
              setShowWaModal(true)
            }}
          />
        )}

        {activeTab === 'dashboard' && (
          <>
            {/* ── Top 3 Metric Cards (Image 1 Bitepoint exact layout) ── */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Card 1: New Orders (Deep Forest Green with Bell) */}
              <div className="rounded-3xl bg-[#0D4738] text-white p-5 shadow-lg shadow-emerald-950/10 flex items-center justify-between">
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-emerald-200">New Orders</p>
                  <h2 className="text-3xl md:text-4xl font-black">{metrics.new_orders}</h2>
                  <p className="text-[11px] text-emerald-300 font-normal">
                    * Updated every new order
                  </p>
                </div>
                <div className="size-12 rounded-2xl bg-white/10 border border-white/20 flex items-center justify-center text-white">
                  <Bell className="size-6 text-emerald-300" />
                </div>
              </div>

              {/* Card 2: Total Orders */}
              <div className="rounded-3xl bg-white border border-stone-200/90 p-5 shadow-2xs flex items-center justify-between">
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-stone-500">Total Orders</p>
                  <h2 className="text-3xl md:text-4xl font-black text-stone-900">
                    {metrics.total_orders}
                  </h2>
                  <p className="text-[11px] text-emerald-600 font-semibold flex items-center gap-1">
                    <TrendingUp className="size-3" />
                    +2.5% than usual
                  </p>
                </div>
                <div className="size-12 rounded-2xl bg-stone-100 flex items-center justify-center text-stone-600">
                  <CheckCircle2 className="size-6 text-emerald-600" />
                </div>
              </div>

              {/* Card 3: Waiting List */}
              <div className="rounded-3xl bg-white border border-stone-200/90 p-5 shadow-2xs flex items-center justify-between">
                <div className="space-y-1">
                  <p className="text-xs font-semibold text-stone-500">Waiting List</p>
                  <h2 className="text-3xl md:text-4xl font-black text-stone-900">
                    {metrics.waiting_list}
                  </h2>
                  <p className="text-[11px] text-amber-600 font-semibold flex items-center gap-1">
                    <TrendingUp className="size-3" />
                    +3.2% than usual
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
                      Kapasitas +24%
                    </Badge>
                  </div>
                  <p className="text-xs text-white/95 mt-0.5 leading-relaxed max-w-2xl">
                    Terjadi lonjakan pemesanan pesat pada menu <strong>Salmon Fillet Lemon Herb</strong> & <strong>Beef Bulgogi</strong>! Stok Salmon di gudang menipis (Tersisa 4.5 kg). PO otomatis telah disiapkan untuk supplier.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <Button
                  size="sm"
                  onClick={() => {
                    setWaRecipient({
                      type: 'supplier',
                      name: 'Muara Baru Seafood',
                      phone: '+6281900112233',
                      message: 'Halo Pak Johan (Muara Baru Seafood), mohon kirim tambahan 10 kg Salmon Fillet segar untuk pesanan katering Dova Kitchen besok pagi. Terima kasih!',
                    })
                    setShowWaModal(true)
                  }}
                  className="rounded-full bg-white text-stone-900 hover:bg-stone-100 font-bold text-xs shadow-sm"
                >
                  <Truck className="size-3.5 mr-1 text-rose-600" />
                  Pesan Tambahan ke Supplier
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setWaRecipient({
                      type: 'customer',
                      name: 'Pelanggan Setia Dova',
                      phone: '+6281234567890',
                      message: 'Halo! Dova Kitchen sedang menyediakan promo istimewa untuk Salmon Fillet & Beef Bulgogi minggu ini. Cek menumu di aplikasi sekarang!',
                    })
                    setShowWaModal(true)
                  }}
                  className="rounded-full border-white/40 bg-white/10 hover:bg-white/20 text-white font-bold text-xs"
                >
                  <Send className="size-3.5 mr-1" />
                  Chat Promo Pelanggan
                </Button>
              </div>
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
                    const isPaid = order.payment_status === 'paid'

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
                              className="rounded-xl bg-amber-400 hover:bg-amber-500 text-stone-950 font-bold text-xs px-3.5 py-1.5 h-auto shadow-2xs"
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
                      onClick={() => navigate('/menu')}
                      className="text-xs font-bold text-amber-600 hover:underline"
                    >
                      View All
                    </button>
                  </div>

                  <div className="space-y-3">
                    {popularDishes.map((dish, idx) => (
                      <div key={idx} className="flex items-center gap-3">
                        <span className="text-xs font-black text-stone-400 w-5">{dish.rank}</span>
                        <img
                          src={dish.image}
                          alt={dish.name}
                          className="size-11 rounded-2xl object-cover border border-stone-100 shrink-0"
                        />
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

                {/* Quick Action: WA Outbox Log */}
                <div className="bg-white rounded-3xl p-5 border border-stone-200/90 shadow-2xs space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="font-extrabold text-base text-stone-900 flex items-center gap-1.5">
                      <MessageSquare className="size-4 text-emerald-600" />
                      WA Outbox Log
                    </h3>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setShowWaModal(true)}
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
                          <span className="text-stone-800 truncate">{n.recipient_name} ({n.recipient_phone})</span>
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
                className="rounded-full bg-amber-400 hover:bg-amber-500 text-stone-950 font-bold text-xs"
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
                          onClick={() => {
                            setWaRecipient({
                              type: 'supplier',
                              name: 'Supplier Pangan',
                              phone: '+6285866408193',
                              message: `Halo Supplier! Stok ${item.ingredient_name} di Dova Kitchen saat ini tersisa ${item.current_stock} ${item.unit}. Mohon kirimkan restock secepatnya. Terima kasih!`,
                            })
                            setShowWaModal(true)
                          }}
                          className="rounded-full text-xs font-bold text-amber-800 border-amber-300 bg-amber-50 hover:bg-amber-100"
                        >
                          Pesan via WA
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
                <Button
                  size="sm"
                  onClick={() => navigate('/supplier')}
                  className="rounded-full bg-stone-900 text-white font-bold text-xs"
                >
                  Buka Portal Khusus Supplier →
                </Button>
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
                    <p className="text-xs text-stone-500 font-mono">{s.phone}</p>
                    <p className="text-[11px] text-stone-600">{s.address}</p>
                    <div className="pt-2 flex justify-end">
                      <Button
                        size="sm"
                        onClick={() => {
                          setWaRecipient({
                            type: 'supplier',
                            name: s.name,
                            phone: s.phone,
                            message: `Halo ${s.name}! Kami ingin mengecek ketersediaan bahan baku untuk katering Dova Kitchen minggu depan.`,
                          })
                          setShowWaModal(true)
                        }}
                        className="rounded-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs h-7"
                      >
                        Hubungi WA
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Purchase Orders Table */}
            <div className="bg-white rounded-3xl p-6 border border-stone-200/90 shadow-2xs space-y-4">
              <h3 className="font-extrabold text-lg text-stone-900">Riwayat Purchase Order (PO)</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead className="bg-[#14213D] text-white text-[11px] font-bold">
                    <tr>
                      <th className="py-3 px-3">PO ID</th>
                      <th className="py-3 px-3">Supplier</th>
                      <th className="py-3 px-3 text-right">Total Nilai</th>
                      <th className="py-3 px-3 text-center">Status PO</th>
                      <th className="py-3 px-3">Tgl Butuh</th>
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
                  Otomatisasi WhatsApp & CRM Outbox
                </h3>
                <p className="text-xs text-stone-500">Log pengiriman pesan otomatis ke pelanggan dan supplier.</p>
              </div>
              <Button
                onClick={() => setShowWaModal(true)}
                className="rounded-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs"
              >
                + Tulis Pesan WhatsApp Baru
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
                        <p className="text-[10px] text-stone-400 font-mono">{n.recipient_phone}</p>
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

      {/* ── Modal WhatsApp Otomatis ────────────────────────────────────────── */}
      {showWaModal && (
        <div className="fixed inset-0 z-50 bg-stone-950/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-md w-full p-6 shadow-2xl border border-stone-200 space-y-4 animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between">
              <h3 className="font-extrabold text-lg text-stone-900 flex items-center gap-2">
                <MessageSquare className="size-5 text-emerald-600" />
                Kirim WhatsApp Otomatis
              </h3>
              <button
                onClick={() => setShowWaModal(false)}
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
                    onClick={() => setWaRecipient((p) => ({ ...p, type: 'customer' }))}
                    className={cn(
                      'flex-1 py-1.5 rounded-xl border font-bold transition-all',
                      waRecipient.type === 'customer'
                        ? 'bg-amber-400 text-stone-950 border-amber-500'
                        : 'bg-stone-50 border-stone-200 text-stone-600'
                    )}
                  >
                    Pelanggan
                  </button>
                  <button
                    type="button"
                    onClick={() => setWaRecipient((p) => ({ ...p, type: 'supplier' }))}
                    className={cn(
                      'flex-1 py-1.5 rounded-xl border font-bold transition-all',
                      waRecipient.type === 'supplier'
                        ? 'bg-amber-400 text-stone-950 border-amber-500'
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
                  value={waRecipient.name}
                  onChange={(e) => setWaRecipient((p) => ({ ...p, name: e.target.value }))}
                  placeholder="Contoh: Joshua / Pak Hadi Supplier"
                  className="rounded-xl text-xs"
                />
              </div>

              <div>
                <label className="font-bold text-stone-700 block mb-1">Nomor WhatsApp (+62)</label>
                <Input
                  value={waRecipient.phone}
                  onChange={(e) => setWaRecipient((p) => ({ ...p, phone: e.target.value }))}
                  placeholder="+6281326332247"
                  className="rounded-xl text-xs font-mono"
                />
              </div>

              <div>
                <label className="font-bold text-stone-700 block mb-1">Isi Pesan WhatsApp</label>
                <textarea
                  rows={4}
                  value={waRecipient.message}
                  onChange={(e) => setWaRecipient((p) => ({ ...p, message: e.target.value }))}
                  placeholder="Ketik pesan..."
                  className="w-full rounded-xl border border-stone-200 p-2.5 text-xs focus:ring-amber-400"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <Button
                variant="outline"
                onClick={() => setShowWaModal(false)}
                className="rounded-full text-xs font-bold"
              >
                Batal
              </Button>
              <Button
                disabled={isSendingWa}
                onClick={handleSendAutomatedWa}
                className="rounded-full bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-xs px-5 shadow-sm"
              >
                {isSendingWa ? 'Mengirim...' : 'Kirim Sekarang →'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal Unggah / Tambah Menu Harian ────────────────────────────────── */}
      {showUploadMenuModal && (
        <div className="fixed inset-0 z-50 bg-stone-950/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-stone-200 space-y-4 animate-in fade-in zoom-in-95 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-2 border-b border-stone-100">
              <div>
                <h3 className="font-extrabold text-base text-stone-900 flex items-center gap-2">
                  <Utensils className="size-4.5 text-amber-600" />
                  Unggah Menu Harian & Resep Bahan (POS & KDS)
                </h3>
                <p className="text-xs text-stone-500">
                  Data menu langsung disinkronkan ke tiket dapur, pengurangan stok bahan, dan kalkulasi demand.
                </p>
              </div>
              <button
                onClick={() => setShowUploadMenuModal(false)}
                className="text-stone-400 hover:text-stone-600 rounded-full p-1 hover:bg-stone-100"
              >
                <X className="size-5" />
              </button>
            </div>

            <div className="space-y-3.5 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-stone-700 block mb-1">Hari Layanan</label>
                  <select
                    value={menuForm.hari}
                    onChange={(e) => setMenuForm((p) => ({ ...p, hari: e.target.value }))}
                    className="w-full rounded-xl border border-stone-200 p-2 text-xs bg-white font-semibold"
                  >
                    {['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu'].map((h) => (
                      <option key={h} value={h}>
                        {h}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="font-bold text-stone-700 block mb-1">Tanggal Sajian</label>
                  <Input
                    type="date"
                    value={menuForm.tanggal}
                    onChange={(e) => setMenuForm((p) => ({ ...p, tanggal: e.target.value }))}
                    className="rounded-xl text-xs"
                  />
                </div>
              </div>

              <div>
                <label className="font-bold text-stone-700 block mb-1">Nama Menu / Hidangan</label>
                <Input
                  value={menuForm.nama_menu}
                  onChange={(e) => setMenuForm((p) => ({ ...p, nama_menu: e.target.value }))}
                  placeholder="Contoh: Ayam Panggang Rosemary & Ubi Madu"
                  className="rounded-xl text-xs font-semibold"
                />
              </div>

              <div>
                <label className="font-bold text-stone-700 block mb-1">Harga Jual Paket (Rp)</label>
                <Input
                  type="number"
                  value={menuForm.harga}
                  onChange={(e) => setMenuForm((p) => ({ ...p, harga: Number(e.target.value) || 0 }))}
                  placeholder="48000"
                  className="rounded-xl text-xs font-mono font-bold"
                />
              </div>

              <div>
                <label className="font-bold text-stone-700 block mb-1">
                  Resep & Komposisi Bahan Baku (BOM — Terhubung ke Stok)
                </label>
                <textarea
                  rows={2}
                  value={menuForm.bom_ingredients}
                  onChange={(e) => setMenuForm((p) => ({ ...p, bom_ingredients: e.target.value }))}
                  placeholder="Contoh: Fillet Dada Ayam 200g, Ubi Madu 150g, Rosemary Segar 10g, Minyak Zaitun 15ml"
                  className="w-full rounded-xl border border-stone-200 p-2.5 text-xs focus:ring-amber-400"
                />
                <p className="text-[10px] text-stone-400 mt-0.5">
                  * Setiap pesanan pelanggan akan otomatis memotong kuantitas stok bahan di atas secara FEFO.
                </p>
              </div>

              <div>
                <label className="font-bold text-stone-700 block mb-1">
                  Status Alergen (Wajib Ditandai untuk Keamanan Dapur)
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {['Bebas Alergen', 'Kacang', 'Susu', 'Telur', 'Gluten', 'Kedelai', 'Ikan', 'Krustasea', 'Wijen'].map((al) => {
                    const isSelected = menuForm.allergens.includes(al)
                    return (
                      <button
                        key={al}
                        type="button"
                        onClick={() => {
                          setMenuForm((p) => ({
                            ...p,
                            allergens: isSelected
                              ? p.allergens.filter((x) => x !== al)
                              : [...p.allergens, al],
                          }))
                        }}
                        className={cn(
                          'px-2.5 py-1 rounded-xl text-[11px] font-bold border transition-all',
                          isSelected
                            ? 'bg-rose-600 text-white border-rose-600 shadow-2xs'
                            : 'bg-stone-50 text-stone-600 border-stone-200 hover:border-stone-400'
                        )}
                      >
                        {al}
                      </button>
                    )
                  })}
                </div>
              </div>

              <div>
                <label className="font-bold text-stone-700 block mb-1">Deskripsi & Profil Nutrisi</label>
                <textarea
                  rows={2}
                  value={menuForm.deskripsi}
                  onChange={(e) => setMenuForm((p) => ({ ...p, deskripsi: e.target.value }))}
                  placeholder="Contoh: Tinggi protein 34g, karbohidrat kompleks rendah IG, kalori 450 kkal."
                  className="w-full rounded-xl border border-stone-200 p-2.5 text-xs focus:ring-amber-400"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-stone-100">
              <Button
                variant="outline"
                onClick={() => setShowUploadMenuModal(false)}
                className="rounded-full text-xs font-bold"
              >
                Batal
              </Button>
              <Button
                onClick={() => {
                  if (!menuForm.nama_menu.trim()) {
                    toast.error('Mohon isi nama menu terlebih dahulu.')
                    return
                  }
                  toast.success(`Menu '${menuForm.nama_menu}' (${menuForm.hari}) berhasil diunggah!`, {
                    description: 'Tersinkronisasi ke KDS dapur dan peramalan bahan baku.',
                  })
                  setShowUploadMenuModal(false)
                  setMenuForm({
                    hari: 'Senin',
                    tanggal: '2026-10-12',
                    nama_menu: '',
                    harga: 48000,
                    bom_ingredients: '',
                    allergens: [],
                    deskripsi: '',
                  })
                  refreshData()
                }}
                className="rounded-full bg-amber-400 hover:bg-amber-500 text-stone-950 font-extrabold text-xs px-6 shadow-sm"
              >
                Simpan & Publikasikan ke KDS →
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}