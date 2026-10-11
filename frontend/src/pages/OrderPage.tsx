import { useEffect, useMemo, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  Bell,
  CheckCircle2,
  Clock,
  Heart,
  MapPin,
  Menu as MenuIcon,
  Minus,
  Plus,
  Search,
  ShieldAlert,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Star,
  Utensils,
  X,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { DovaChatbot } from '@/components/chat/DovaChatbot'
import { useApi } from '@/hooks/useApi'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'
import { catalogService } from '@/services/catalog'
import { customersService } from '@/services/customers'
import type { Allergen, Menu, Passport } from '@/types'

/* ── Kurasi Foto Makanan Resolusi Tinggi Sesuai Menu Dova Kitchen ──────────── */
const MENU_IMAGES: Record<string, string> = {
  'menu_senin_ayam-rosemary':
    'https://images.unsplash.com/photo-1598515214211-89d3c73ae83b?auto=format&fit=crop&w=800&q=80',
  'Beef Bulgogi Wijen & Nasi Beras Cokelat':
    'https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80',
  'Tumis Tahu Jamur Saus Teriyaki (Vegetarian)':
    'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=800&q=80',
  'Sup Daging Sapi Jamur Rempah':
    'https://images.unsplash.com/photo-1547592166-23ac45744acd?auto=format&fit=crop&w=800&q=80',
  'Ayam Fillet Crispy Saus Salted Egg':
    'https://images.unsplash.com/photo-1562967914-608f82629710?auto=format&fit=crop&w=800&q=80',
  'Fillet Dori Panggang Lemon & Salad Jagung':
    'https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?auto=format&fit=crop&w=800&q=80',
  'Ayam Suwir Sambal Matah & Urap Sayur':
    'https://images.unsplash.com/photo-1569058242253-92a9c755a0ec?auto=format&fit=crop&w=800&q=80',
  'Ikan Kakap Bakar Kunyit & Nasi Merah':
    'https://images.unsplash.com/photo-1534422298391-e4f8c172dddb?auto=format&fit=crop&w=800&q=80',
  'Gado-Gado Roll Saus Kacang Gurih':
    'https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=800&q=80',
  'Tumis Ayam Jamur Brokoli Saus Bawang':
    'https://images.unsplash.com/photo-1512058564366-18510be2db19?auto=format&fit=crop&w=800&q=80',
  'Udang Bakar Madu Jimbaran & Nasi Merah':
    'https://images.unsplash.com/photo-1559737558-2f5a35f4523b?auto=format&fit=crop&w=800&q=80',
  'Rendang Daging Sapi Suwir & Buncis':
    'https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=800&q=80',
  'Ayam Bakar Taliwang & Plecing Kangkung':
    'https://images.unsplash.com/photo-1527477378408-1bc0e2270921?auto=format&fit=crop&w=800&q=80',
  'Salmon Fillet Lemon Herb & Kentang Kukus':
    'https://images.unsplash.com/photo-1467003909585-2f8a72700288?auto=format&fit=crop&w=800&q=80',
  'Pasta Fusilli Ayam Pesto Keju':
    'https://images.unsplash.com/photo-1551183053-bf91a1d81141?auto=format&fit=crop&w=800&q=80',
  'Nasi Merah Ayam Bakar Madu Ketumbar':
    'https://images.unsplash.com/photo-1604908176997-125f25cc6f3d?auto=format&fit=crop&w=800&q=80',
  'Sup Tom Yum Udang & Ikan Kakap':
    'https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=800&q=80',
  'Steak Tempe Lada Hitam (Vegetarian)':
    'https://images.unsplash.com/photo-1585238342024-78d387f4a707?auto=format&fit=crop&w=800&q=80',
}

const DEFAULT_FOOD_IMAGE =
  'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=800&q=80'

const DAYS_LIST: Record<string, { id: string; label: string; icon: string }> = {
  all: { id: 'all', label: 'Semua', icon: '🍽️' },
  Senin: { id: 'Senin', label: 'Senin', icon: '🍗' },
  Selasa: { id: 'Selasa', label: 'Selasa', icon: '🥩' },
  Rabu: { id: 'Rabu', label: 'Rabu', icon: '🐟' },
  Kamis: { id: 'Kamis', label: 'Kamis', icon: '🍤' },
  Jumat: { id: 'Jumat', label: 'Jumat', icon: '🥗' },
  Sabtu: { id: 'Sabtu', label: 'Sabtu', icon: '🍲' },
}

const PRICE_PER_PORTION = 42000

interface CartItem {
  menu: Menu
  quantity: number
  riskAccepted: boolean
  matchedAllergens: string[]
}

export function OrderPage() {
  const { customer, isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()

  // Data fetching
  const { data: menuData } = useApi<Menu[]>((signal) =>
    catalogService.listMenus(signal)
  )
  const menuList = useMemo(() => (Array.isArray(menuData) ? menuData : []), [menuData])

  const { data: passport } = useApi<Passport>(
    (signal) => customersService.getPassport(signal),
    { enabled: isAuthenticated }
  )
  const { data: allergenData } = useApi<Allergen[]>((signal) =>
    catalogService.listAllergens(signal)
  )
  const allergenList = useMemo(() => (Array.isArray(allergenData) ? allergenData : []), [allergenData])
  void allergenList

  // Filters & Search
  const [selectedDay, setSelectedDay] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [favorites, setFavorites] = useState<string[]>([])
  const [aiRecommendations, setAiRecommendations] = useState<any[]>([])

  // Load customer likes and recommendations for precision personalization
  useEffect(() => {
    const cid = customer?.customer_id || 'cust_ml_001'
    customersService
      .getLikes(cid)
      .then((likedIds) => {
        if (Array.isArray(likedIds) && likedIds.length > 0) {
          setFavorites(likedIds)
        }
      })
      .catch(() => null)

    customersService
      .getRecommendations(cid)
      .then((recs) => {
        if (Array.isArray(recs)) {
          setAiRecommendations(recs)
        }
      })
      .catch(() => null)
  }, [customer])

  // Cart & UI State
  const [cart, setCart] = useState<Record<string, CartItem>>({})
  const [isCartOpen, setIsCartOpen] = useState(false)
  const [isSideMenuOpen, setIsSideMenuOpen] = useState(false)

  // SweetAlert: Post-Login Dietary Profile Dialog
  const [showDietaryAlert, setShowDietaryAlert] = useState(false)

  // SweetAlert: Allergen Conflict Warning Dialog
  const [conflictMenu, setConflictMenu] = useState<{
    menu: Menu
    matchedAllergens: string[]
  } | null>(null)

  // Checkout & Payment State
  const [isPaymentOpen, setIsPaymentOpen] = useState(false)
  const [paymentTimer, setPaymentTimer] = useState(600) // 10 minutes in seconds
  const [paymentDone, setPaymentDone] = useState(false)
  const [selectedAddress, setSelectedAddress] = useState('home')
  const [courierNotes, setCourierNotes] = useState('Titip di depan pintu/resepsionis.')
  const [paymentMethod, setPaymentMethod] = useState<'qris' | 'va'>('qris')

  // Check and show post-login dietary alert once per session
  useEffect(() => {
    if (isAuthenticated) {
      const hasShown = sessionStorage.getItem('dova_dietary_popup_seen')
      if (!hasShown) {
        setShowDietaryAlert(true)
      }
    }
  }, [isAuthenticated])


  // Payment Countdown Timer
  useEffect(() => {
    let interval: ReturnType<typeof setInterval>
    if (isPaymentOpen && !paymentDone && paymentTimer > 0) {
      interval = setInterval(() => {
        setPaymentTimer((prev) => prev - 1)
      }, 1000)
    }
    return () => clearInterval(interval)
  }, [isPaymentOpen, paymentDone, paymentTimer])

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
  }

  // Active customer allergens
  const userAllergens = useMemo(() => {
    if (!passport) return []
    const list: string[] = []
    if (passport.allergies) {
      passport.allergies.forEach((a) => list.push(a.label))
    }
    if (passport.avoided_ingredients) {
      passport.avoided_ingredients.forEach((i) => list.push(i))
    }
    return list
  }, [passport])

  // Check if a menu item has allergen conflicts
  function checkMenuConflict(menu: Menu): string[] {
    if (userAllergens.length === 0) return []
    const conflicts: string[] = []
    const menuContent = [
      menu.nama_menu,
      menu.deskripsi,
      ...menu.bahan_detail.map((b) => `${b.nama} ${b.potensi_alergen}`),
      ...menu.allergen_labels,
    ]
      .join(' ')
      .toLowerCase()

    for (const alg of userAllergens) {
      const algLower = alg.toLowerCase()
      if (menuContent.includes(algLower)) {
        conflicts.push(alg)
      }
    }
    return Array.from(new Set(conflicts))
  }

  // Handle Add to Cart with Allergen Conflict Check
  function handleAddToCartClick(menu: Menu) {
    const conflicts = checkMenuConflict(menu)

    // Jika ada bentrok dengan profil alergi user -> Munculkan SweetAlert peringatan!
    if (conflicts.length > 0) {
      setConflictMenu({ menu, matchedAllergens: conflicts })
      return
    }

    // Jika aman -> Tambahkan langsung ke keranjang
    executeAddToCart(menu, false, [])
  }

  function executeAddToCart(menu: Menu, riskAccepted: boolean, matchedAllergens: string[]) {
    setCart((prev) => {
      const existing = prev[menu.menu_id]
      const newQty = existing ? existing.quantity + 1 : 1
      return {
        ...prev,
        [menu.menu_id]: {
          menu,
          quantity: newQty,
          riskAccepted,
          matchedAllergens,
        },
      }
    })

    // Catat interaksi keranjang ke Supabase untuk AI ML
    const cid = customer?.customer_id || 'cust_ml_001'
    customersService
      .trackCartEvent({
        menu_id: menu.menu_id,
        quantity: 1,
        action: 'add',
        customer_id: cid,
      })
      .catch(() => null)

    toast.success(`${menu.nama_menu} ditambahkan ke keranjang!`, {
      description: `Porsi: ${cart[menu.menu_id] ? cart[menu.menu_id].quantity + 1 : 1}x (${menu.hari})`,
    })

    setConflictMenu(null)
  }

  function updateQuantity(menuId: string, delta: number) {
    const cid = customer?.customer_id || 'cust_ml_001'
    customersService
      .trackCartEvent({
        menu_id: menuId,
        quantity: Math.abs(delta),
        action: delta > 0 ? 'add' : 'remove',
        customer_id: cid,
      })
      .catch(() => null)

    setCart((prev) => {
      const existing = prev[menuId]
      if (!existing) return prev
      const updatedQty = existing.quantity + delta
      if (updatedQty <= 0) {
        const next = { ...prev }
        delete next[menuId]
        return next
      }
      return {
        ...prev,
        [menuId]: { ...existing, quantity: updatedQty },
      }
    })
  }

  async function toggleFavorite(menuId: string) {
    const isCurrentlyFav = favorites.includes(menuId)
    setFavorites((prev) =>
      isCurrentlyFav ? prev.filter((id) => id !== menuId) : [...prev, menuId]
    )
    const cid = customer?.customer_id || 'cust_ml_001'
    try {
      const res = await customersService.toggleLike(menuId, cid)
      if (res.liked) {
        toast.success('Disukai! AI Chef mencatat preferensimu untuk rekomendasi presisi.', {
          icon: '❤️',
        })
      }
    } catch {
      // silent fallback
    }
  }


  // Filtered menus
  const filteredMenus = useMemo(() => {
    return menuList.filter((m) => {
      const matchDay = selectedDay === 'all' || m.hari === selectedDay
      const matchSearch =
        searchQuery.trim() === '' ||
        m.nama_menu.toLowerCase().includes(searchQuery.toLowerCase()) ||
        m.deskripsi.toLowerCase().includes(searchQuery.toLowerCase()) ||
        m.bahan_detail.some((b) => b.nama.toLowerCase().includes(searchQuery.toLowerCase()))
      return matchDay && matchSearch
    })
  }, [menuList, selectedDay, searchQuery])

  // Cart calculations
  const cartItemsArray = Object.values(cart)
  const cartItemCount = cartItemsArray.reduce((acc, curr) => acc + curr.quantity, 0)
  const cartSubtotal = cartItemsArray.reduce(
    (acc, curr) => acc + curr.quantity * PRICE_PER_PORTION,
    0
  )
  const deliveryFee = cartItemCount > 0 ? 0 : 0 // Free ongkir promo
  const cartGrandTotal = cartSubtotal + deliveryFee

  async function handleSimulatePaymentSuccess() {
    setPaymentDone(true)
    toast.success('Pembayaran Berhasil Dikonfirmasi!', {
      description: 'Dapur Dova Kitchen mulai memproses tiket masak Anda.',
    })

    // Reset keranjang setelah bayar
    setTimeout(() => {
      setIsPaymentOpen(false)
      setCart({})
      navigate('/orders')
    }, 2000)
  }

  return (
    <div className="min-h-screen bg-[#FAF7F2] text-stone-900 font-sans flex antialiased selection:bg-rose-500 selection:text-white">
      {/* ── Desktop Left Sidebar (Matching Image 2 / Bitepoint) ── */}
      <aside className="hidden lg:flex flex-col w-64 bg-white border-r border-stone-200/80 shrink-0 h-screen sticky top-0 justify-between z-20 shadow-2xs">
        <div>
          <div className="p-6 pb-5 flex items-center justify-between border-b border-stone-100">
            <Link to="/" className="flex items-center gap-3">
              <div className="size-10 rounded-2xl bg-rose-600 flex items-center justify-center text-white font-black shadow-md shadow-rose-600/20 text-lg">
                DK
              </div>
              <div>
                <span className="font-extrabold text-lg text-stone-900 tracking-tight leading-none block">
                  dovakitchen
                </span>
                <span className="text-[11px] font-semibold text-rose-600 uppercase tracking-wider block mt-0.5">
                  Precision Catering
                </span>
              </div>
            </Link>
          </div>

          <nav className="p-4 space-y-2 text-sm font-semibold">
            <Link
              to="/order"
              className="w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl bg-rose-600 text-white font-bold shadow-sm shadow-rose-600/20"
            >
              <Utensils className="size-5" />
              <span>Menu Mingguan</span>
            </Link>

            <Link
              to="/orders"
              className="w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl text-stone-700 hover:bg-stone-100 hover:text-stone-900 transition-all"
            >
              <ShoppingBag className="size-5" />
              <span>Pesanan Saya</span>
            </Link>

            <Link
              to="/passport"
              className="w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl text-stone-700 hover:bg-stone-100 hover:text-stone-900 transition-all"
            >
              <ShieldCheck className="size-5" />
              <span>Dietary Passport</span>
              {userAllergens.length > 0 && (
                <span className="ml-auto px-2 py-0.5 rounded-full text-[10px] bg-rose-100 text-rose-700 font-bold">
                  {userAllergens.length}
                </span>
              )}
            </Link>

            <button
              type="button"
              onClick={() => {
                const btn = document.querySelector('[aria-label="Tanya Chef BOB"]') as HTMLButtonElement
                if (btn) btn.click()
                else navigate('/ai')
              }}
              className="w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl text-stone-700 hover:bg-stone-100 hover:text-stone-900 transition-all text-left"
            >
              <Sparkles className="size-5 text-amber-500" />
              <span>Asisten AI Chef (BOB)</span>
            </button>
          </nav>
        </div>

        {/* User profile footer */}
        <div className="p-4 border-t border-stone-100">
          <div className="flex items-center gap-3 p-2 rounded-2xl bg-stone-50 border border-stone-200/60">
            <div className="size-10 rounded-full bg-rose-100 border border-rose-300 text-rose-900 font-bold flex items-center justify-center text-sm shrink-0">
              {customer?.display_name?.[0] || 'P'}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-bold text-stone-900 truncate">
                {customer?.display_name || customer?.username || 'Pelanggan Dova'}
              </p>
              <p className="text-[11px] text-stone-500">
                {userAllergens.length > 0 ? `${userAllergens.length} Alergi` : 'Diet Sehat'}
              </p>
            </div>
          </div>
        </div>
      </aside>

      {/* ── Center Content Column ── */}
      <div className="flex-1 flex flex-col min-w-0 pb-20 overflow-y-auto">
        {/* ── 1. Top Mobile / Desktop Header ───────────────── */}
        <header className="sticky top-0 z-40 bg-[#FAF7F2]/95 backdrop-blur-md border-b border-stone-200/80 px-4 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-3">
          {/* Left: Hamburger Menu */}
          <button
            type="button"
            onClick={() => setIsSideMenuOpen(true)}
            className="size-10 rounded-full bg-white border border-stone-200 shadow-2xs flex items-center justify-center text-stone-700 hover:text-stone-900 active:scale-95 transition-all"
            aria-label="Menu navigasi"
          >
            <MenuIcon className="size-5" />
          </button>

          {/* Center: Greeting & Brand Logo */}
          <div className="flex flex-col items-center text-center">
            <span className="text-[11px] font-medium text-stone-500">
              Halo, {customer?.display_name || 'Food Lover'}! 👋
            </span>
            <div className="flex items-center gap-1.5 font-black text-rose-600 text-lg md:text-xl tracking-tighter">
              DOVA KITCHEN
              <span className="inline-block size-1.5 rounded-full bg-rose-600"></span>
            </div>
          </div>

          {/* Right: Notification & Cart Bag Icons */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowDietaryAlert(true)}
              className="size-10 rounded-full bg-white border border-stone-200 shadow-2xs flex items-center justify-center text-stone-700 hover:text-rose-600 active:scale-95 transition-all relative"
              aria-label="Info Alergi"
              title="Cek Profil Alergi"
            >
              <Bell className="size-5" />
              {userAllergens.length > 0 && (
                <span className="absolute top-1.5 right-1.5 size-2.5 rounded-full bg-rose-600 border-2 border-white"></span>
              )}
            </button>

            {/* Shopping Bag Button with Badge */}
            <button
              type="button"
              onClick={() => setIsCartOpen(true)}
              className="size-10 rounded-full bg-white border border-stone-200 shadow-2xs flex items-center justify-center text-stone-700 hover:text-rose-600 active:scale-95 transition-all relative"
              aria-label="Keranjang Belanja"
            >
              <ShoppingBag className="size-5" />
              {cartItemCount > 0 && (
                <span className="absolute -top-1 -right-1 flex size-5 items-center justify-center rounded-full bg-rose-600 text-[11px] font-bold text-white shadow-sm animate-pulse">
                  {cartItemCount}
                </span>
              )}
            </button>
          </div>
        </div>

        {/* ── Search Bar (Clean Pill) ────────────────────────────────────────── */}
        <div className="max-w-6xl mx-auto mt-3">
          <div className="relative flex items-center">
            <Search className="absolute left-4 size-4 text-stone-400" />
            <Input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Cari menu sehat, bahan, atau pantangan..."
              className="w-full rounded-full bg-white border-stone-200 pl-11 pr-10 py-2 text-sm shadow-2xs focus-visible:ring-rose-500"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3.5 text-stone-400 hover:text-stone-600"
              >
                <X className="size-4" />
              </button>
            )}
          </div>
        </div>
      </header>

      {/* ── Main Content Area ──────────────────────────────────────────────── */}
      <main className="max-w-6xl mx-auto px-4 pt-4 space-y-6">
        {/* ── 2. Hero Promo Banner (Inspired by KFC "CRISPY. JUICY. IRRESISTIBLE.") ── */}
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-red-700 via-rose-700 to-amber-700 p-6 md:p-8 text-white shadow-xl shadow-rose-950/10">
          <div className="absolute right-0 top-0 bottom-0 w-1/2 opacity-25 md:opacity-40 mix-blend-overlay pointer-events-none">
            <img
              src="https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1000&q=80"
              alt="Culinary"
              className="h-full w-full object-cover"
            />
          </div>

          <div className="relative z-10 max-w-md space-y-3">
            <Badge className="bg-amber-400 text-stone-950 font-bold uppercase tracking-wider text-[10px] px-2.5 py-0.5">
              PRESISI ALERGI • 100% HIGIENIS
            </Badge>

            <h1 className="text-2xl md:text-4xl font-black tracking-tight leading-tight uppercase">
              SEHAT. NIKMAT. <br />
              <span className="text-amber-300">AMAN DARI ALERGI.</span>
            </h1>

            <p className="text-xs md:text-sm text-white/90 font-normal leading-relaxed">
              Katering harian 3 menu per hari. Dipersiapkan dengan workstation steril terpisah untuk
              menjamin nol kontaminasi silang.
            </p>

            <div className="pt-2 flex items-center gap-3">
              <Button
                onClick={() => {
                  setSelectedDay('all')
                  const el = document.getElementById('food-catalog-grid')
                  el?.scrollIntoView({ behavior: 'smooth' })
                }}
                className="rounded-full bg-white text-rose-700 hover:bg-stone-100 font-bold px-6 shadow-md shadow-rose-950/20 active:scale-95 transition-all text-xs md:text-sm"
              >
                Pesan Sekarang →
              </Button>

              {userAllergens.length > 0 ? (
                <div className="flex items-center gap-1.5 text-xs text-white/90 bg-white/10 backdrop-blur-md px-3 py-1.5 rounded-full border border-white/20">
                  <ShieldCheck className="size-4 text-emerald-300 shrink-0" />
                  <span className="truncate max-w-[150px]">
                    Proteksi: {userAllergens.join(', ')}
                  </span>
                </div>
              ) : (
                <button
                  onClick={() => setShowDietaryAlert(true)}
                  className="text-xs text-white/90 underline hover:text-white"
                >
                  Atur Pantangan Alergi
                </button>
              )}
            </div>
          </div>
        </div>

        {/* ── 3. Category & Day Filter Pills (Horizontal Scroll) ─────────────── */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="font-bold text-stone-800 text-sm md:text-base flex items-center gap-1.5">
              <span>Jadwal Menu Mingguan</span>
              <span className="text-xs font-normal text-stone-500">(3 Pilihan / Hari)</span>
            </h2>
            <span className="text-xs text-rose-600 font-semibold">Senin — Sabtu</span>
          </div>

          <div className="flex gap-2.5 overflow-x-auto pb-2 no-scrollbar scroll-smooth">
            {Object.values(DAYS_LIST).map((day) => {
              const isActive = selectedDay === day.id
              return (
                <button
                  key={day.id}
                  onClick={() => setSelectedDay(day.id)}
                  className={cn(
                    'flex items-center gap-2 rounded-full px-4 py-2.5 text-xs font-semibold whitespace-nowrap transition-all duration-200 border active:scale-95',
                    isActive
                      ? 'bg-rose-600 text-white border-rose-600 shadow-md shadow-rose-600/20'
                      : 'bg-white text-stone-700 border-stone-200/90 hover:border-stone-300 hover:bg-stone-50'
                  )}
                >
                  <span className="text-sm">{day.icon}</span>
                  <span>{day.label}</span>
                </button>
              )
            })}
          </div>
        </div>

        {/* ── 4. Popular Food Grid (Like "Popular Combos" in KFC App) ───────── */}
        <div id="food-catalog-grid" className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <h2 className="font-black text-stone-900 text-lg tracking-tight">
                {selectedDay === 'all' ? 'Semua Menu Pilihan Minggu Ini' : `Menu Hari ${selectedDay}`}
              </h2>
              <p className="text-xs text-stone-500">
                Pilih makanan favoritmu dan klik tanda + untuk memesan
              </p>
            </div>
            <span className="text-xs font-bold text-stone-400">
              {filteredMenus.length} Hidangan Tersedia
            </span>
          </div>

          {filteredMenus.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-stone-300 p-12 text-center bg-white space-y-3">
              <Utensils className="size-10 text-stone-400 mx-auto" />
              <h3 className="font-bold text-stone-700">Tidak ada menu yang sesuai</h3>
              <p className="text-xs text-stone-500">Coba ubah kata kunci pencarian atau pilih hari lain.</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setSelectedDay('all')
                  setSearchQuery('')
                }}
              >
                Reset Filter
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredMenus.map((menu) => {
                const conflicts = checkMenuConflict(menu)
                const hasConflict = conflicts.length > 0
                const isFavorite = favorites.includes(menu.menu_id)
                const imageUrl =
                  MENU_IMAGES[menu.menu_id] || MENU_IMAGES[menu.nama_menu] || DEFAULT_FOOD_IMAGE
                const cartItem = cart[menu.menu_id]
                const qtyInCart = cartItem?.quantity || 0

                return (
                  <Card
                    key={menu.menu_id}
                    className="group overflow-hidden rounded-3xl border-stone-200/90 bg-white shadow-2xs hover:shadow-lg transition-all duration-300 flex flex-col justify-between"
                  >
                    {/* Top Food Image Container */}
                    <div className="relative aspect-4/3 w-full overflow-hidden bg-stone-100">
                      <img
                        src={imageUrl}
                        alt={menu.nama_menu}
                        className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                        loading="lazy"
                      />

                      {/* Day Pill Tag & AI Recommendation Tag */}
                      <div className="absolute top-3 left-3 flex items-center gap-1.5">
                        <Badge className="bg-stone-900/80 backdrop-blur-md text-white text-[11px] font-semibold border-none">
                          📅 {menu.hari}
                        </Badge>
                        {(() => {
                          const rec = aiRecommendations.find((r) => r.menu_id === menu.menu_id)
                          if (rec && rec.score >= 50) {
                            return (
                              <Badge className="bg-amber-400 text-stone-950 font-black text-[10px] border-none shadow-xs flex items-center gap-1">
                                <Sparkles className="size-3 text-stone-900" />
                                <span>{Math.round(rec.score)}% Match AI</span>
                              </Badge>
                            )
                          }
                          return null
                        })()}

                      </div>

                      {/* Allergen Warning / Safe Badge */}
                      {hasConflict ? (
                        <Badge className="absolute bottom-3 left-3 bg-rose-600 text-white text-[10px] font-bold border-none shadow-md flex items-center gap-1 animate-pulse">
                          <ShieldAlert className="size-3" />
                          <span>Waspada: {conflicts.join(', ')}</span>
                        </Badge>
                      ) : userAllergens.length > 0 ? (
                        <Badge className="absolute bottom-3 left-3 bg-emerald-700 text-white text-[10px] font-bold border-none shadow-md flex items-center gap-1">
                          <ShieldCheck className="size-3" />
                          <span>Cocok Untukmu</span>
                        </Badge>
                      ) : null}

                      {/* Wishlist Heart Toggle */}
                      <button
                        type="button"
                        onClick={() => toggleFavorite(menu.menu_id)}
                        className="absolute top-3 right-3 size-9 rounded-full bg-white/90 backdrop-blur-md flex items-center justify-center text-stone-700 hover:text-rose-600 active:scale-90 transition-all shadow-sm"
                        aria-label="Favorit"
                      >
                        <Heart
                          className={cn(
                            'size-4 transition-colors',
                            isFavorite ? 'fill-rose-600 text-rose-600' : 'text-stone-600'
                          )}
                        />
                      </button>
                    </div>

                    {/* Card Content & Details */}
                    <div className="p-4 space-y-2.5 flex-1 flex flex-col justify-between">
                      <div className="space-y-1.5">
                        <div className="flex items-start justify-between gap-2">
                          <h3 className="font-bold text-stone-900 text-base leading-snug group-hover:text-rose-600 transition-colors">
                            {menu.nama_menu}
                          </h3>
                        </div>

                        {/* Ingredients snippet */}
                        <p className="text-xs text-stone-500 line-clamp-2 leading-relaxed">
                          {menu.deskripsi ||
                            menu.bahan_detail.map((b) => b.nama).join(', ')}
                        </p>

                        {/* Allergen Tags / Badges */}
                        {menu.allergen_labels.length > 0 ? (
                          <div className="flex flex-wrap gap-1 pt-1">
                            {menu.allergen_labels.map((alg) => (
                              <span
                                key={alg}
                                className="text-[10px] bg-amber-50 text-amber-800 border border-amber-200/80 px-2 py-0.5 rounded-full font-medium"
                              >
                                {alg}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <div className="pt-1">
                            <span className="text-[10px] bg-emerald-50 text-emerald-800 border border-emerald-200 px-2 py-0.5 rounded-full font-medium">
                              Bebas Alergen Mayor
                            </span>
                          </div>
                        )}
                      </div>

                      {/* Rating & Portion Info */}
                      <div className="flex items-center gap-2 text-xs text-stone-500 pt-1">
                        <div className="flex items-center gap-1 font-bold text-stone-700">
                          <Star className="size-3.5 fill-amber-400 text-amber-400" />
                          <span>4.9</span>
                        </div>
                        <span>•</span>
                        <span>1 Porsi Standar (450 kkal)</span>
                      </div>

                      {/* Price & Action Row */}
                      <div className="pt-2 border-t border-stone-100 flex items-center justify-between">
                        <div>
                          <div className="text-[10px] uppercase font-bold text-stone-400">Harga</div>
                          <div className="font-black text-base text-stone-900 tracking-tight">
                            Rp {PRICE_PER_PORTION.toLocaleString('id-ID')}
                          </div>
                        </div>

                        {/* Quantity Stepper if in cart, or circular Plus button */}
                        {qtyInCart > 0 ? (
                          <div className="flex items-center gap-2 bg-stone-100 rounded-full p-1 border border-stone-200">
                            <button
                              type="button"
                              onClick={() => updateQuantity(menu.menu_id, -1)}
                              className="size-7 rounded-full bg-white flex items-center justify-center text-stone-700 hover:bg-stone-200 active:scale-90 transition-all"
                            >
                              <Minus className="size-3.5" />
                            </button>
                            <span className="font-bold text-xs px-1 text-stone-900">{qtyInCart}</span>
                            <button
                              type="button"
                              onClick={() => handleAddToCartClick(menu)}
                              className="size-7 rounded-full bg-rose-600 text-white flex items-center justify-center hover:bg-rose-700 active:scale-90 transition-all shadow-xs"
                            >
                              <Plus className="size-3.5" />
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() => handleAddToCartClick(menu)}
                            className="size-10 rounded-full bg-rose-600 text-white flex items-center justify-center shadow-md shadow-rose-600/30 hover:bg-rose-700 hover:scale-105 active:scale-95 transition-all"
                            aria-label={`Tambah ${menu.nama_menu}`}
                          >
                            <Plus className="size-5 stroke-[2.5]" />
                          </button>
                        )}
                      </div>
                    </div>
                  </Card>
                )
              })}
            </div>
          )}
        </div>
      </main>
      </div>

      {/* ── Desktop Right Column: Order Menu (Cart & Checkout matching Image 2) ── */}
      <aside className="hidden xl:flex flex-col w-96 bg-white border-l border-stone-200/80 shrink-0 h-screen sticky top-0 p-5 overflow-y-auto justify-between z-10 shadow-2xs">
        <div className="space-y-4">
          {/* Your Balance Virtual Card (Image 2 top right) */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-extrabold text-stone-800">Your Balance</span>
              <button
                onClick={() => toast.info('Saldo Dova Pay siap digunakan!')}
                className="text-[11px] font-bold text-amber-600 hover:underline"
              >
                Top Up
              </button>
            </div>
            <div className="rounded-3xl bg-gradient-to-tr from-orange-600 via-amber-600 to-rose-600 p-4 text-white shadow-md relative overflow-hidden">
              <div className="flex justify-between items-start">
                <span className="text-[10px] font-extrabold uppercase tracking-widest text-amber-200">
                  Dova Pay Precision
                </span>
                <div className="size-6 rounded-md bg-amber-400/40 border border-amber-300 flex items-center justify-center text-[10px]">
                  💳
                </div>
              </div>
              <div className="my-3 font-mono text-xs tracking-widest text-white/90">
                •••• •••• •••• 8869
              </div>
              <div className="flex justify-between items-end">
                <div>
                  <span className="text-[9px] uppercase tracking-wider text-white/70 block">
                    Saldo Aktif
                  </span>
                  <span className="font-extrabold text-sm text-white">Rp 5.285.000</span>
                </div>
                <span className="text-[10px] font-mono text-white/80">08/28</span>
              </div>
            </div>
          </div>

          {/* Your Address (Image 2) */}
          <div className="rounded-2xl bg-stone-50 border border-stone-200/80 p-3.5 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-stone-800 flex items-center gap-1.5">
                <MapPin className="size-3.5 text-rose-600" /> Your Address
              </span>
              <span
                onClick={() => setSelectedAddress(selectedAddress === 'home' ? 'office' : 'home')}
                className="text-[11px] font-bold text-rose-600 cursor-pointer hover:underline"
              >
                Change
              </span>
            </div>
            <p className="text-xs font-bold text-stone-900 truncate">
              {selectedAddress === 'home'
                ? 'Jl. Senopati Raya No. 42 (Rumah)'
                : 'Menara Mandiri Lt. 14 (Kantor)'}
            </p>
            <p className="text-[10px] text-stone-500">
              Katering tiba setiap pk 11:30 WIB tepat waktu.
            </p>
          </div>

          {/* Order Menu Items List (Image 2 right middle) */}
          <div className="space-y-2">
            <div className="flex items-center justify-between pb-1.5 border-b border-stone-100">
              <span className="text-xs font-extrabold text-stone-900 flex items-center gap-1.5">
                <ShoppingBag className="size-3.5 text-rose-600" /> Order Menu
              </span>
              <Badge className="bg-rose-100 text-rose-700 text-[10px] font-bold">
                {cartItemCount} Items
              </Badge>
            </div>

            <div className="space-y-2 max-h-[260px] overflow-y-auto pr-1">
              {cartItemsArray.length === 0 ? (
                <div className="text-center py-8 text-xs text-stone-400">
                  Keranjangmu kosong. Klik tanda '+' untuk memilih menu.
                </div>
              ) : (
                cartItemsArray.map(({ menu, quantity }) => (
                  <div
                    key={menu.menu_id}
                    className="flex items-center justify-between gap-2.5 p-2 rounded-2xl bg-stone-50 border border-stone-200/60"
                  >
                    <img
                      src={
                        MENU_IMAGES[menu.menu_id] ||
                        MENU_IMAGES[menu.nama_menu] ||
                        DEFAULT_FOOD_IMAGE
                      }
                      alt={menu.nama_menu}
                      className="size-11 rounded-xl object-cover shrink-0"
                    />
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-bold text-stone-900 truncate">{menu.nama_menu}</p>
                      <p className="text-[11px] font-black text-rose-600">
                        Rp {(PRICE_PER_PORTION * quantity).toLocaleString('id-ID')}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 bg-white rounded-full p-0.5 border border-stone-200">
                      <button
                        onClick={() => updateQuantity(menu.menu_id, -1)}
                        className="size-5 rounded-full flex items-center justify-center text-stone-600 hover:bg-stone-100"
                      >
                        <Minus className="size-2.5" />
                      </button>
                      <span className="text-xs font-bold px-1">{quantity}</span>
                      <button
                        onClick={() => handleAddToCartClick(menu)}
                        className="size-5 rounded-full bg-rose-600 text-white flex items-center justify-center hover:bg-rose-700"
                      >
                        <Plus className="size-2.5" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Pricing breakdown & Checkout Button (Image 2 bottom right) */}
        {cartItemsArray.length > 0 && (
          <div className="space-y-2.5 pt-3 border-t border-stone-200 text-xs">
            <div className="flex justify-between text-stone-600">
              <span>Subtotal ({cartItemCount} porsi):</span>
              <span className="font-bold text-stone-900">
                Rp {cartSubtotal.toLocaleString('id-ID')}
              </span>
            </div>
            <div className="flex justify-between text-emerald-600">
              <span>Delivery Service:</span>
              <span className="font-bold">FREE</span>
            </div>
            <div className="flex justify-between text-sm font-black text-stone-900 pt-1.5 border-t border-stone-100">
              <span>Total:</span>
              <span className="text-rose-600 text-base">
                Rp {cartGrandTotal.toLocaleString('id-ID')}
              </span>
            </div>

            <Button
              onClick={() => {
                setIsPaymentOpen(true)
                setPaymentTimer(600)
                setPaymentDone(false)
              }}
              className="w-full rounded-2xl bg-amber-500 hover:bg-amber-600 text-stone-950 font-black h-11 text-xs shadow-md shadow-amber-500/20 mt-1"
            >
              Checkout / Bayar Sekarang →
            </Button>
          </div>
        )}
      </aside>

      {/* ── 5. SweetAlert: Post-Login Dietary Profile Dialog ───────────────── */}
      {showDietaryAlert && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-950/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
          <Card className="w-full max-w-md overflow-hidden rounded-3xl bg-white shadow-2xl border-none animate-in zoom-in-95 duration-200">
            <div className="bg-gradient-to-r from-red-600 to-rose-700 p-6 text-white text-center relative">
              <div className="size-14 rounded-2xl bg-white/20 backdrop-blur-md mx-auto flex items-center justify-center mb-3">
                <ShieldCheck className="size-8 text-amber-300" />
              </div>
              <h3 className="font-black text-xl tracking-tight">Status Profil Alergi Aktif</h3>
              <p className="text-xs text-white/80 mt-1">
                Halo {customer?.display_name || 'Pelanggan'}! Kami menjaga keamanan makananmu.
              </p>
            </div>

            <div className="p-6 space-y-4">
              <div className="rounded-2xl bg-stone-50 border border-stone-200 p-4 space-y-2">
                <div className="text-xs font-semibold text-stone-500 uppercase tracking-wider">
                  Alergi yang Tercatat di Akunmu:
                </div>
                {userAllergens.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {userAllergens.map((alg) => (
                      <Badge
                        key={alg}
                        className="bg-rose-100 text-rose-800 border-rose-300 text-xs px-2.5 py-1"
                      >
                        ⚠️ {alg}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-xs text-stone-600">
                    <CheckCircle2 className="size-4 text-emerald-600 shrink-0" />
                    <span>Belum ada pantangan alergi yang dicatat.</span>
                  </div>
                )}
                <p className="text-[11px] text-stone-400 pt-1 leading-relaxed">
                  Sistem kami akan otomatis memblokir / memberi peringatan jika kamu memilih menu yang
                  mengandung bahan alergen di atas.
                </p>
              </div>

              <div className="flex flex-col gap-2 pt-2">
                <Button
                  onClick={() => {
                    sessionStorage.setItem('dova_dietary_popup_seen', 'true')
                    setShowDietaryAlert(false)
                  }}
                  className="rounded-full bg-rose-600 hover:bg-rose-700 text-white font-bold h-11 text-sm shadow-md shadow-rose-600/20"
                >
                  Lanjut Pesan Makanan 🍽️
                </Button>

                <Button
                  variant="outline"
                  onClick={() => {
                    sessionStorage.setItem('dova_dietary_popup_seen', 'true')
                    setShowDietaryAlert(false)
                    navigate('/passport')
                  }}
                  className="rounded-full border-stone-300 text-stone-700 h-10 text-xs font-semibold"
                >
                  Perbarui / Tambah Alergi di Profil ⚙️
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* ── 6. SweetAlert: Conflict Warning Dialog (When Clicking + on Risk Item) ── */}
      {conflictMenu && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-950/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
          <Card className="w-full max-w-md overflow-hidden rounded-3xl bg-white shadow-2xl border-none animate-in zoom-in-95 duration-200">
            <div className="bg-gradient-to-r from-red-600 to-rose-800 p-6 text-white text-center">
              <div className="size-14 rounded-2xl bg-white/20 backdrop-blur-md mx-auto flex items-center justify-center mb-3 animate-bounce">
                <ShieldAlert className="size-8 text-amber-300" />
              </div>
              <h3 className="font-black text-xl tracking-tight">PERINGATAN ALERGI!</h3>
              <p className="text-xs text-white/80 mt-1">
                Menu ini bertentangan dengan profil kesehatanmu
              </p>
            </div>

            <div className="p-6 space-y-4">
              <div className="rounded-2xl bg-rose-50 border border-rose-200 p-4 space-y-2">
                <div className="font-bold text-sm text-rose-950">
                  {conflictMenu.menu.nama_menu}
                </div>
                <div className="text-xs text-rose-800 leading-relaxed">
                  Menu ini mengandung bahan yang bentrok dengan alergimu:
                </div>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {conflictMenu.matchedAllergens.map((alg) => (
                    <Badge
                      key={alg}
                      className="bg-rose-600 text-white font-bold text-xs px-2.5 py-1 border-none"
                    >
                      ⚠️ {alg}
                    </Badge>
                  ))}
                </div>
                <p className="text-[11px] text-rose-700 pt-2 leading-relaxed">
                  Dapur Dova Kitchen menyarankan untuk menghindari menu ini demi keselamatanmu. Bila
                  tetap memesan, tiket dapur akan ditandai dengan sorotan risiko khusus.
                </p>
              </div>

              <div className="flex flex-col gap-2 pt-2">
                <Button
                  onClick={() => setConflictMenu(null)}
                  variant="outline"
                  className="rounded-full border-stone-300 text-stone-700 h-11 text-sm font-semibold"
                >
                  Batalkan & Pilih Menu Lain
                </Button>

                <Button
                  onClick={() => executeAddToCart(conflictMenu.menu, true, conflictMenu.matchedAllergens)}
                  className="rounded-full bg-rose-600 hover:bg-rose-700 text-white font-bold h-11 text-xs shadow-md shadow-rose-600/20"
                >
                  Saya Paham Risikonya, Tetap Tambahkan
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* ── 7. Shopping Cart Drawer (Slide-Over Sheet) ──────────────────────── */}
      {isCartOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div
            className="absolute inset-0 bg-stone-950/50 backdrop-blur-2xs transition-opacity"
            onClick={() => setIsCartOpen(false)}
          />

          <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
            <div className="w-screen max-w-md bg-white shadow-2xl flex flex-col justify-between rounded-l-3xl overflow-hidden animate-in slide-in-from-right duration-300">
              {/* Cart Header */}
              <div className="p-5 border-b border-stone-200 flex items-center justify-between bg-stone-50">
                <div className="flex items-center gap-2">
                  <ShoppingBag className="size-5 text-rose-600" />
                  <h3 className="font-bold text-lg text-stone-900">Keranjang Pesanan</h3>
                  <Badge className="bg-rose-100 text-rose-700 text-xs">{cartItemCount} item</Badge>
                </div>
                <button
                  onClick={() => setIsCartOpen(false)}
                  className="size-8 rounded-full bg-white border border-stone-200 flex items-center justify-center text-stone-500 hover:text-stone-800"
                >
                  <X className="size-4" />
                </button>
              </div>

              {/* Cart Items List */}
              <div className="flex-1 overflow-y-auto p-5 space-y-4">
                {cartItemsArray.length === 0 ? (
                  <div className="py-16 text-center space-y-3">
                    <ShoppingBag className="size-12 text-stone-300 mx-auto" />
                    <h4 className="font-bold text-stone-700">Keranjangmu masih kosong</h4>
                    <p className="text-xs text-stone-500">Pilih menu mingguan lezat di katalog.</p>
                    <Button
                      onClick={() => setIsCartOpen(false)}
                      className="rounded-full bg-rose-600 text-white text-xs font-bold"
                    >
                      Mulai Memilih
                    </Button>
                  </div>
                ) : (
                  <>
                    <div className="space-y-3">
                      {cartItemsArray.map(({ menu, quantity, riskAccepted, matchedAllergens }) => (
                        <div
                          key={menu.menu_id}
                          className="flex gap-3 p-3 rounded-2xl border border-stone-200 bg-white shadow-2xs items-center justify-between"
                        >
                          <img
                            src={
                              MENU_IMAGES[menu.menu_id] ||
                              MENU_IMAGES[menu.nama_menu] ||
                              DEFAULT_FOOD_IMAGE
                            }
                            alt={menu.nama_menu}
                            className="size-16 rounded-xl object-cover shrink-0"
                          />

                          <div className="flex-1 min-w-0 space-y-1">
                            <div className="flex items-center gap-1.5">
                              <Badge className="bg-stone-100 text-stone-700 text-[10px] px-1.5 py-0">
                                {menu.hari}
                              </Badge>
                              {riskAccepted && (
                                <Badge className="bg-rose-100 text-rose-700 text-[9px] px-1 py-0">
                                  ⚠️ {matchedAllergens.join(', ')}
                                </Badge>
                              )}
                            </div>
                            <h4 className="font-bold text-xs text-stone-900 truncate">
                              {menu.nama_menu}
                            </h4>
                            <div className="font-black text-xs text-rose-600">
                              Rp {(PRICE_PER_PORTION * quantity).toLocaleString('id-ID')}
                            </div>
                          </div>

                          <div className="flex items-center gap-1.5 bg-stone-100 rounded-full p-1 border border-stone-200 shrink-0">
                            <button
                              onClick={() => updateQuantity(menu.menu_id, -1)}
                              className="size-6 rounded-full bg-white flex items-center justify-center text-stone-700 hover:bg-stone-200"
                            >
                              <Minus className="size-3" />
                            </button>
                            <span className="font-bold text-xs px-1 text-stone-900">{quantity}</span>
                            <button
                              onClick={() => handleAddToCartClick(menu)}
                              className="size-6 rounded-full bg-rose-600 text-white flex items-center justify-center hover:bg-rose-700"
                            >
                              <Plus className="size-3" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Delivery Address Selection */}
                    <div className="rounded-2xl bg-stone-50 border border-stone-200 p-4 space-y-2.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-stone-800 flex items-center gap-1.5">
                          <MapPin className="size-3.5 text-rose-600" /> Alamat Pengantaran
                        </span>
                        <span className="text-[11px] text-rose-600 font-semibold cursor-pointer">
                          Ubah
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <button
                          type="button"
                          onClick={() => setSelectedAddress('home')}
                          className={cn(
                            'rounded-xl p-2.5 text-left border text-xs transition-all',
                            selectedAddress === 'home'
                              ? 'bg-rose-50 border-rose-300 text-rose-900 font-semibold'
                              : 'bg-white border-stone-200 text-stone-600'
                          )}
                        >
                          <div className="font-bold">🏠 Rumah (Utama)</div>
                          <div className="text-[10px] text-stone-500 truncate">Jl. Senopati Raya No. 42</div>
                        </button>

                        <button
                          type="button"
                          onClick={() => setSelectedAddress('office')}
                          className={cn(
                            'rounded-xl p-2.5 text-left border text-xs transition-all',
                            selectedAddress === 'office'
                              ? 'bg-rose-50 border-rose-300 text-rose-900 font-semibold'
                              : 'bg-white border-stone-200 text-stone-600'
                          )}
                        >
                          <div className="font-bold">🏢 Kantor</div>
                          <div className="text-[10px] text-stone-500 truncate">Menara Mandiri Lt. 14</div>
                        </button>
                      </div>

                      <div>
                        <label className="text-[11px] text-stone-500 font-medium">Catatan Kurir:</label>
                        <Input
                          value={courierNotes}
                          onChange={(e) => setCourierNotes(e.target.value)}
                          className="h-8 text-xs mt-1 rounded-lg bg-white"
                        />
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* Cart Footer */}
              {cartItemsArray.length > 0 && (
                <div className="p-5 border-t border-stone-200 bg-white space-y-3 shadow-lg">
                  <div className="space-y-1.5 text-xs text-stone-600">
                    <div className="flex justify-between">
                      <span>Subtotal ({cartItemCount} porsi)</span>
                      <span className="font-bold text-stone-900">
                        Rp {cartSubtotal.toLocaleString('id-ID')}
                      </span>
                    </div>
                    <div className="flex justify-between text-emerald-600">
                      <span>Ongkos Kirim Harian</span>
                      <span className="font-bold">GRATIS</span>
                    </div>
                    <div className="flex justify-between font-black text-sm text-stone-900 pt-2 border-t border-stone-100">
                      <span>Total Pembayaran</span>
                      <span className="text-rose-600 text-base">
                        Rp {cartGrandTotal.toLocaleString('id-ID')}
                      </span>
                    </div>
                  </div>

                  <Button
                    onClick={() => {
                      setIsCartOpen(false)
                      setIsPaymentOpen(true)
                      setPaymentTimer(600)
                      setPaymentDone(false)
                    }}
                    className="w-full rounded-full bg-rose-600 hover:bg-rose-700 text-white font-bold h-12 shadow-lg shadow-rose-600/30 text-sm"
                  >
                    Bayar Sekarang (Rp {cartGrandTotal.toLocaleString('id-ID')}) →
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── 8. Payment Modal (QRIS & VA Simulation) ────────────────────────── */}
      {isPaymentOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-950/70 backdrop-blur-xs p-4 animate-in fade-in duration-200">
          <Card className="w-full max-w-md overflow-hidden rounded-3xl bg-white shadow-2xl border-none animate-in zoom-in-95 duration-200">
            {/* Header */}
            <div className="bg-gradient-to-r from-red-600 to-rose-700 p-5 text-white flex items-center justify-between">
              <div>
                <h3 className="font-black text-lg">Pembayaran Pesanan</h3>
                <p className="text-xs text-white/80">Selesaikan sebelum waktu habis</p>
              </div>
              {/* Countdown Pill */}
              <div className="flex items-center gap-1.5 bg-black/30 backdrop-blur-md px-3 py-1.5 rounded-full text-xs font-mono font-bold text-amber-300 border border-white/20">
                <Clock className="size-3.5" />
                <span>{formatTimer(paymentTimer)}</span>
              </div>
            </div>

            <div className="p-6 space-y-4">
              {/* Payment Method Switcher */}
              <div className="grid grid-cols-2 gap-2 bg-stone-100 p-1 rounded-2xl">
                <button
                  type="button"
                  onClick={() => setPaymentMethod('qris')}
                  className={cn(
                    'py-2 text-xs font-bold rounded-xl transition-all',
                    paymentMethod === 'qris'
                      ? 'bg-white text-stone-900 shadow-2xs'
                      : 'text-stone-500 hover:text-stone-800'
                  )}
                >
                  QRIS Instant
                </button>
                <button
                  type="button"
                  onClick={() => setPaymentMethod('va')}
                  className={cn(
                    'py-2 text-xs font-bold rounded-xl transition-all',
                    paymentMethod === 'va'
                      ? 'bg-white text-stone-900 shadow-2xs'
                      : 'text-stone-500 hover:text-stone-800'
                  )}
                >
                  Virtual Account
                </button>
              </div>

              {/* QRIS View */}
              {paymentMethod === 'qris' ? (
                <div className="rounded-2xl border border-stone-200 p-4 text-center space-y-3 bg-stone-50">
                  <div className="mx-auto size-44 bg-white p-2 rounded-2xl shadow-sm border border-stone-200 flex items-center justify-center">
                    <img
                      src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=DOVA-KITCHEN-ORDER-PAYMENT-SIMULATION"
                      alt="QRIS Code"
                      className="size-full rounded-lg"
                    />
                  </div>
                  <div className="space-y-1">
                    <div className="font-bold text-xs text-stone-800">Scan QRIS via GoPay / OVO / BCA / ShopeePay</div>
                    <div className="font-black text-rose-600 text-lg">
                      Rp {cartGrandTotal.toLocaleString('id-ID')}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="rounded-2xl border border-stone-200 p-4 space-y-3 bg-stone-50">
                  <div className="space-y-1">
                    <span className="text-xs text-stone-500">Nomor Virtual Account BCA:</span>
                    <div className="font-mono font-black text-lg text-stone-900 tracking-wider bg-white p-2.5 rounded-xl border border-stone-200 flex justify-between items-center">
                      <span>8801 2345 6789 001</span>
                      <span className="text-xs text-rose-600 font-sans font-bold cursor-pointer">Salin</span>
                    </div>
                  </div>
                  <div className="text-xs text-stone-600 space-y-1 pt-1">
                    <div className="flex justify-between">
                      <span>Atas Nama:</span>
                      <span className="font-bold">Dova Kitchen Presisi</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Total Tagihan:</span>
                      <span className="font-bold text-rose-600">
                        Rp {cartGrandTotal.toLocaleString('id-ID')}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex flex-col gap-2 pt-2">
                <Button
                  onClick={handleSimulatePaymentSuccess}
                  disabled={paymentDone}
                  className="rounded-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold h-12 shadow-lg shadow-emerald-600/30 text-sm"
                >
                  {paymentDone ? 'Memproses Pesanan...' : 'Simulasi Pembayaran Berhasil ✅'}
                </Button>

                <Button
                  variant="ghost"
                  onClick={() => setIsPaymentOpen(false)}
                  className="rounded-full text-stone-500 h-9 text-xs"
                >
                  Tutup / Bayar Nanti
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* ── 9. Side Navigation Drawer ───────────────────────────────────────── */}
      {isSideMenuOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div
            className="absolute inset-0 bg-stone-950/50 backdrop-blur-2xs transition-opacity"
            onClick={() => setIsSideMenuOpen(false)}
          />

          <div className="fixed inset-y-0 left-0 max-w-full flex pr-10">
            <div className="w-screen max-w-xs bg-white shadow-2xl flex flex-col justify-between p-6 rounded-r-3xl animate-in slide-in-from-left duration-300">
              <div className="space-y-6">
                <div className="flex items-center justify-between pb-4 border-b border-stone-200">
                  <div className="flex items-center gap-2 font-black text-rose-600 text-lg">
                    DOVA KITCHEN
                  </div>
                  <button
                    onClick={() => setIsSideMenuOpen(false)}
                    className="size-8 rounded-full bg-stone-100 flex items-center justify-center text-stone-500"
                  >
                    <X className="size-4" />
                  </button>
                </div>

                <div className="space-y-1">
                  <Link
                    to="/orders"
                    onClick={() => setIsSideMenuOpen(false)}
                    className="flex items-center gap-3 p-3 rounded-2xl text-stone-700 hover:bg-stone-50 font-semibold text-sm"
                  >
                    <ShoppingBag className="size-4" />
                    <span>Pesanan Saya</span>
                  </Link>
                  <Link
                    to="/passport"
                    onClick={() => setIsSideMenuOpen(false)}
                    className="flex items-center gap-3 p-3 rounded-2xl text-stone-700 hover:bg-stone-50 font-semibold text-sm"
                  >
                    <ShieldCheck className="size-4" />
                    <span>Dietary Passport</span>
                  </Link>
                  <button
                    type="button"
                    onClick={() => {
                      setIsSideMenuOpen(false)
                      const btn = document.querySelector('[aria-label="Tanya Chef BOB"]') as HTMLButtonElement
                      if (btn) btn.click()
                      else navigate('/ai')
                    }}
                    className="w-full flex items-center gap-3 p-3 rounded-2xl text-stone-700 hover:bg-stone-50 font-semibold text-sm text-left"
                  >
                    <Sparkles className="size-4 text-amber-500" />
                    <span>Asisten AI Chef (BOB)</span>
                  </button>
                </div>
              </div>

              <div className="pt-6 border-t border-stone-200 space-y-3">
                {isAuthenticated ? (
                  <>
                    <div className="text-xs">
                      <div className="font-bold text-stone-900">{customer?.display_name}</div>
                      <div className="text-stone-500">@{customer?.username}</div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={logout}
                      className="w-full rounded-full border-stone-300 text-stone-700 text-xs"
                    >
                      Keluar
                    </Button>
                  </>
                ) : (
                  <Button
                    onClick={() => navigate('/login')}
                    className="w-full rounded-full bg-rose-600 text-white text-xs font-bold"
                  >
                    Masuk Akun
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── 10. Sticky Bottom Navigation Bar (Matching KFC mobile screenshot) ── */}
      <nav className="fixed bottom-0 inset-x-0 z-40 bg-white/95 backdrop-blur-md border-t border-stone-200 px-6 py-2.5">
        <div className="max-w-md mx-auto flex items-center justify-between">
          <Link
            to="/order"
            className="flex flex-col items-center gap-1 text-rose-600 font-bold text-[11px]"
          >
            <div className="size-7 rounded-full bg-rose-50 flex items-center justify-center">
              <Utensils className="size-4" />
            </div>
            <span>Home</span>
          </Link>

          <Link
            to="/orders"
            className="flex flex-col items-center gap-1 text-stone-500 hover:text-stone-900 font-medium text-[11px] relative"
          >
            <div className="size-7 flex items-center justify-center">
              <ShoppingBag className="size-4" />
            </div>
            <span>Orders</span>
            {cartItemCount > 0 && (
              <span className="absolute top-0 right-2 size-2 rounded-full bg-rose-600"></span>
            )}
          </Link>

          {/* Center Floating Cart Trigger */}
          <button
            type="button"
            onClick={() => setIsCartOpen(true)}
            className="size-12 -mt-5 rounded-full bg-gradient-to-r from-red-600 to-rose-600 text-white shadow-lg shadow-rose-600/30 flex items-center justify-center active:scale-95 transition-all"
            aria-label="Buka Keranjang"
          >
            <div className="relative">
              <ShoppingBag className="size-5" />
              {cartItemCount > 0 && (
                <span className="absolute -top-1.5 -right-2 size-4 rounded-full bg-amber-400 text-stone-950 font-black text-[9px] flex items-center justify-center">
                  {cartItemCount}
                </span>
              )}
            </div>
          </button>

          <Link
            to="/passport"
            className="flex flex-col items-center gap-1 text-stone-500 hover:text-stone-900 font-medium text-[11px]"
          >
            <div className="size-7 flex items-center justify-center">
              <ShieldCheck className="size-4" />
            </div>
            <span>Profile</span>
          </Link>
        </div>
      </nav>

      {/* ── 11. Floating Interactive AI Chatbot Widget ──────────────────────── */}
      <DovaChatbot />
    </div>
  )
}