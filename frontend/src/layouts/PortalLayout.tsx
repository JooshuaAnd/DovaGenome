import { useEffect, useState, type ReactNode } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import {
  LogOut,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Utensils,
  X,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { DovaChatbot } from '@/components/chat/DovaChatbot'
import { DietaryPassportModal } from '@/components/passport/DietaryPassportModal'
import { Sheet, SheetContent } from '@/components/ui/sheet'
import { useAuth } from '@/hooks/useAuth'
import { useApi } from '@/hooks/useApi'
import { cn } from '@/lib/utils'
import { clearChatPreferences } from '@/lib/chatPreferenceMemory'
import { catalogService } from '@/services/catalog'
import { customersService } from '@/services/customers'
import type { Allergen, Passport } from '@/types'

interface PortalLayoutProps {
  children: ReactNode
  title?: string
}

export function PortalLayout({ children, title }: PortalLayoutProps) {
  const { customer, isAuthenticated, logout, updateProfile } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const standaloneOrder = ['/', '/order', '/menu'].includes(location.pathname)
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const [isPassportOpen, setIsPassportOpen] = useState(false)

  const passportQuery = useApi<Passport>(
    (signal) => customersService.getPassport(signal),
    { enabled: isAuthenticated },
  )
  const allergenQuery = useApi<Allergen[]>((signal) => catalogService.listAllergens(signal))

  useEffect(() => {
    if (!isAuthenticated || !customer || !passportQuery.data) return
    const seenKey = `dova_dietary_onboarding_seen_${customer.customer_id}`
    if (!passportQuery.data.structured && !sessionStorage.getItem(seenKey)) {
      setIsPassportOpen(true)
    }
  }, [customer, isAuthenticated, passportQuery.data])

  useEffect(() => {
    const refresh = () => {
      if (customer?.customer_id) clearChatPreferences(customer.customer_id)
      void passportQuery.refetch()
    }
    window.addEventListener('dova:passport-updated', refresh)
    return () => window.removeEventListener('dova:passport-updated', refresh)
  }, [customer?.customer_id, passportQuery.refetch])

  function openPassport() {
    if (!isAuthenticated) {
      navigate('/login?next=%2Fpassport')
      return
    }
    setIsPassportOpen(true)
  }

  useEffect(() => {
    const open = () => setIsPassportOpen(true)
    window.addEventListener('dova:open-passport', open)
    return () => window.removeEventListener('dova:open-passport', open)
  }, [])

  useEffect(() => {
    if (location.search.includes('passport=1') && isAuthenticated) {
      setIsPassportOpen(true)
      navigate('/order', { replace: true })
    }
  }, [isAuthenticated, location.search, navigate])

  const navItems = [
    { to: '/order', label: 'Menu Mingguan', icon: Utensils },
    { to: '/orders', label: 'Pesanan Saya', icon: ShoppingBag },
    { to: '/passport', label: 'Dietary Passport', icon: ShieldCheck, modal: true },
    { to: '/ai', label: 'Asisten AI Chef (BOB)', icon: Sparkles },
  ]

  return (
    <div className="min-h-screen bg-canvas text-ink-soft font-sans flex antialiased selection:bg-gold-500/30 selection:text-forest-900">
      {/* ── Desktop Left Sidebar (Consistent Bitepoint/Dova Theme) ── */}
      <aside className="hidden">
        <div>
          {/* Brand Logo Header */}
          <div className="p-6 pb-5 flex items-center justify-between border-b border-stone-100">
            <Link to="/" className="flex items-center gap-3">
              <div className="size-10 rounded-2xl bg-forest-900 flex items-center justify-center text-white font-black shadow-md shadow-forest-900/20 text-lg">
                DK
              </div>
              <div>
                <span className="font-extrabold text-lg text-stone-900 tracking-tight leading-none block">
                  dovakitchen
                </span>
                <span className="text-[11px] font-semibold text-gold-700 uppercase tracking-wider block mt-0.5">
                  Precision Catering
                </span>
              </div>
            </Link>
          </div>

          {/* Navigation Links */}
          <nav className="p-4 space-y-2 text-sm font-semibold">
            {navItems.map((item) => {
              const Icon = item.icon
              return (
                item.modal ? (
                  <button
                    key={item.to}
                    type="button"
                    onClick={openPassport}
                    className="w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl text-left text-stone-700 transition-all hover:bg-forest-50 hover:text-forest-900"
                  >
                    <Icon className="size-5 shrink-0" />
                    <span>{item.label}</span>
                  </button>
                ) : (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      cn(
                        'w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl transition-all',
                        isActive
                          ? 'bg-forest-900 text-white font-bold shadow-sm shadow-forest-900/20'
                          : 'text-stone-700 hover:bg-forest-50 hover:text-forest-900'
                      )
                    }
                  >
                    <Icon className="size-5 shrink-0" />
                    <span>{item.label}</span>
                  </NavLink>
                )
              )
            })}
          </nav>
        </div>

        {/* User profile footer */}
        <div className="p-4 border-t border-stone-100 space-y-2">
          {isAuthenticated ? (
            <div className="p-3 rounded-2xl bg-stone-50 border border-stone-200/60 flex items-center justify-between">
              <div className="flex items-center gap-3 min-w-0">
                <div className="size-9 rounded-full bg-forest-50 border border-forest-100 text-forest-900 font-bold flex items-center justify-center text-xs shrink-0">
                  {customer?.display_name?.[0] || customer?.username?.[0] || 'P'}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold text-stone-900 truncate">
                    {customer?.display_name || customer?.username}
                  </p>
                  <p className="text-[11px] text-stone-500 truncate">
                    @{customer?.username}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={logout}
                title="Keluar akun"
                className="size-8 rounded-xl hover:bg-forest-50 text-stone-400 hover:text-forest-700 flex items-center justify-center transition-colors"
              >
                <LogOut className="size-4" />
              </button>
            </div>
          ) : (
            <Button
              onClick={() => navigate('/login')}
              className="w-full rounded-2xl bg-forest-900 hover:bg-forest-800 text-white font-bold text-xs py-2.5 shadow-md shadow-forest-900/20"
            >
              Masuk Akun
            </Button>
          )}
        </div>
      </aside>

      {/* ── Center Content Column ── */}
      <div className={standaloneOrder ? 'w-full min-w-0' : 'flex-1 flex flex-col min-w-0 pb-20 overflow-y-auto'}>
        {/* Mobile & Tablet Header */}
        {!standaloneOrder && <header className="sticky top-0 z-40 bg-canvas/95 backdrop-blur-md border-b border-line px-4 py-3">
          <div className="w-full max-w-[1600px] mx-auto flex items-center justify-between gap-3">
            {/* Desktop Page Title / Mobile Brand */}
            <div className="flex items-center gap-3">
              <span className="hidden lg:block font-black text-lg text-stone-900">
                {title || 'Dova Kitchen'}
              </span>
              <div className="lg:hidden flex items-center gap-1.5 font-black text-forest-900 text-lg tracking-tighter">
                DOVA KITCHEN
                <span className="inline-block size-1.5 rounded-full bg-gold-600"></span>
              </div>
            </div>

            {/* Right: Quick Actions */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={openPassport}
                className="size-10 rounded-full bg-white border border-stone-200 shadow-2xs flex items-center justify-center text-stone-700 hover:text-forest-700 active:scale-95 transition-all"
                title="Dietary Passport"
              >
                <ShieldCheck className="size-5" />
              </button>

              <Link
                to="/order"
                className="size-10 rounded-full bg-white border border-stone-200 shadow-2xs flex items-center justify-center text-stone-700 hover:text-forest-700 active:scale-95 transition-all relative"
                title="Pesan Menu"
              >
                <ShoppingBag className="size-5" />
              </Link>
            </div>
          </div>
        </header>}

        {/* ── Main View Content ── */}
        <main className={standaloneOrder ? 'w-full' : 'w-full max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-6'}>
          {children}
        </main>
      </div>

      {/* ── Slide-over Mobile Sheet Drawer ── */}
      <Sheet open={isMobileMenuOpen} onOpenChange={setIsMobileMenuOpen}>
        <SheetContent side="left" className="w-72 p-0 bg-surface border-r border-line flex flex-col justify-between">
          <div className="p-6">
            <div className="flex items-center justify-between pb-6 border-b border-stone-100">
              <div className="flex items-center gap-2.5 font-black text-forest-900 text-lg">
                <div className="size-8 rounded-xl bg-forest-900 text-white flex items-center justify-center text-sm font-black">
                  DK
                </div>
                DOVA KITCHEN
              </div>
              <button
                onClick={() => setIsMobileMenuOpen(false)}
                className="size-8 rounded-full bg-stone-100 flex items-center justify-center text-stone-500"
              >
                <X className="size-4" />
              </button>
            </div>

            <nav className="space-y-2 mt-6">
              {navItems.map((item) => {
                const Icon = item.icon
                return (
                  item.modal ? (
                    <button
                      key={item.to}
                      type="button"
                      onClick={() => {
                        setIsMobileMenuOpen(false)
                        openPassport()
                      }}
                      className="flex w-full items-center gap-3.5 rounded-2xl p-3 text-left text-sm font-semibold text-stone-700 transition-all hover:bg-forest-50 hover:text-forest-900"
                    >
                      <Icon className="size-5" />
                      <span>{item.label}</span>
                    </button>
                  ) : (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      onClick={() => setIsMobileMenuOpen(false)}
                      className={({ isActive }) =>
                        cn(
                          'flex items-center gap-3.5 p-3 rounded-2xl text-sm font-semibold transition-all',
                          isActive
                            ? 'bg-forest-900 text-white font-bold'
                            : 'text-stone-700 hover:bg-forest-50 hover:text-forest-900'
                        )
                      }
                    >
                      <Icon className="size-5" />
                      <span>{item.label}</span>
                    </NavLink>
                  )
                )
              })}
            </nav>
          </div>

          <div className="p-6 border-t border-stone-100">
            {isAuthenticated ? (
              <div className="space-y-3">
                <div className="text-xs">
                  <div className="font-bold text-stone-900">{customer?.display_name || customer?.username}</div>
                  <div className="text-stone-500">@{customer?.username}</div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setIsMobileMenuOpen(false)
                    logout()
                  }}
                  className="w-full rounded-2xl border-stone-300 text-stone-700 text-xs"
                >
                  Keluar
                </Button>
              </div>
            ) : (
              <Button
                onClick={() => {
                  setIsMobileMenuOpen(false)
                  navigate('/login')
                }}
                className="w-full rounded-2xl bg-forest-900 text-white text-xs font-bold"
              >
                Masuk Akun
              </Button>
            )}
          </div>
        </SheetContent>
      </Sheet>

      {/* ── Sticky Bottom Mobile Navigation Bar ── */}
      <nav aria-label="Navigasi utama" className="fixed bottom-0 inset-x-0 z-40 border-t border-line bg-surface/95 px-5 py-2.5 backdrop-blur-md">
        <div className="mx-auto flex max-w-md items-center justify-between">
          {[
            { to: '/order', label: 'Menu', icon: Utensils },
            { to: '/orders', label: 'Pesanan', icon: ShoppingBag },
            { to: '/ai', label: 'Chef BOB', icon: Sparkles },
          ].map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `flex flex-col items-center gap-1 text-[11px] font-semibold transition-colors ${isActive || (to === '/order' && location.pathname === '/') ? 'text-forest-900' : 'text-stone-500 hover:text-forest-900'}`}>
              {({ isActive }) => { const active = isActive || (to === '/order' && location.pathname === '/'); return <><span className={`flex size-8 items-center justify-center rounded-full ${active ? 'bg-rose-50' : ''}`}><Icon className="size-4" /></span><span>{label}</span></> }}
            </NavLink>
          ))}
          <button
            type="button"
            onClick={() => {
              if (['/', '/order'].includes(location.pathname)) {
                window.dispatchEvent(new Event('dova:open-cart'))
              } else {
                navigate('/order?openCart=1')
              }
            }}
            className="flex flex-col items-center gap-1 text-[10px] font-bold text-forest-900"
            aria-label="Buka keranjang"
          >
            <span className="flex size-10 -mt-4 items-center justify-center rounded-full bg-[#8f2833] text-white shadow-lg shadow-[#8f2833]/25">
              <ShoppingBag className="size-4" />
            </span>
            <span>Keranjang</span>
          </button>
          <button type="button" onClick={openPassport} className="flex flex-col items-center gap-1 text-[11px] font-semibold text-stone-500 hover:text-forest-900">
            <span className="flex size-8 items-center justify-center"><ShieldCheck className="size-4" /></span><span>Profil</span>
          </button>
        </div>
      </nav>

      {/* ── Interactive AI Chef Chatbot ── */}
      <DietaryPassportModal
        open={isPassportOpen}
        onOpenChange={(open) => {
          setIsPassportOpen(open)
          if (!open && customer) {
            sessionStorage.setItem(`dova_dietary_onboarding_seen_${customer.customer_id}`, 'true')
          }
        }}
        passport={passportQuery.data}
        allergens={allergenQuery.data ?? []}
        displayName={customer?.display_name}
        loading={passportQuery.loading}
        loadError={passportQuery.error?.message ?? null}
        onRetry={() => {
          passportQuery.refetch()
          allergenQuery.refetch()
        }}
        onboarding={!passportQuery.data?.structured}
        onSaved={() => {
          window.dispatchEvent(new Event('dova:passport-updated'))
        }}
        onSaveName={async (display_name) => { await updateProfile({ display_name }) }}
      />

      <DovaChatbot />
    </div>
  )
}
