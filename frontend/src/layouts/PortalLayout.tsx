import { useState, type ReactNode } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import {
  LogOut,
  Menu as MenuIcon,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Utensils,
  X,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { DovaChatbot } from '@/components/chat/DovaChatbot'
import { Sheet, SheetContent } from '@/components/ui/sheet'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'

interface PortalLayoutProps {
  children: ReactNode
  title?: string
}

export function PortalLayout({ children, title }: PortalLayoutProps) {
  const { customer, isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

  const navItems = [
    { to: '/order', label: 'Menu Mingguan', icon: Utensils },
    { to: '/orders', label: 'Pesanan Saya', icon: ShoppingBag },
    { to: '/passport', label: 'Dietary Passport', icon: ShieldCheck },
    { to: '/ai', label: 'Asisten AI Chef (BOB)', icon: Sparkles },
  ]

  return (
    <div className="min-h-screen bg-[#FAF7F2] text-stone-900 font-sans flex antialiased selection:bg-rose-500 selection:text-white">
      {/* ── Desktop Left Sidebar (Consistent Bitepoint/Dova Theme) ── */}
      <aside className="hidden lg:flex flex-col w-64 bg-white border-r border-stone-200/80 shrink-0 h-screen sticky top-0 justify-between z-20 shadow-2xs">
        <div>
          {/* Brand Logo Header */}
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

          {/* Navigation Links */}
          <nav className="p-4 space-y-2 text-sm font-semibold">
            {navItems.map((item) => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    cn(
                      'w-full flex items-center gap-3.5 px-4 py-3 rounded-2xl transition-all',
                      isActive
                        ? 'bg-rose-600 text-white font-bold shadow-sm shadow-rose-600/20'
                        : 'text-stone-700 hover:bg-stone-100 hover:text-stone-900'
                    )
                  }
                >
                  <Icon className="size-5 shrink-0" />
                  <span>{item.label}</span>
                </NavLink>
              )
            })}
          </nav>
        </div>

        {/* User profile footer */}
        <div className="p-4 border-t border-stone-100 space-y-2">
          {isAuthenticated ? (
            <div className="p-3 rounded-2xl bg-stone-50 border border-stone-200/60 flex items-center justify-between">
              <div className="flex items-center gap-3 min-w-0">
                <div className="size-9 rounded-full bg-rose-100 border border-rose-300 text-rose-900 font-bold flex items-center justify-center text-xs shrink-0">
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
                className="size-8 rounded-xl hover:bg-rose-50 text-stone-400 hover:text-rose-600 flex items-center justify-center transition-colors"
              >
                <LogOut className="size-4" />
              </button>
            </div>
          ) : (
            <Button
              onClick={() => navigate('/login')}
              className="w-full rounded-2xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs py-2.5 shadow-md shadow-rose-600/20"
            >
              Masuk Akun
            </Button>
          )}
        </div>
      </aside>

      {/* ── Center Content Column ── */}
      <div className="flex-1 flex flex-col min-w-0 pb-20 overflow-y-auto">
        {/* Mobile & Tablet Header */}
        <header className="sticky top-0 z-40 bg-[#FAF7F2]/95 backdrop-blur-md border-b border-stone-200/80 px-4 py-3">
          <div className="max-w-6xl mx-auto flex items-center justify-between gap-3">
            {/* Left: Mobile Drawer Trigger */}
            <button
              type="button"
              onClick={() => setIsMobileMenuOpen(true)}
              className="size-10 rounded-full bg-white border border-stone-200 shadow-2xs flex items-center justify-center text-stone-700 hover:text-stone-900 active:scale-95 transition-all lg:hidden"
              aria-label="Menu navigasi"
            >
              <MenuIcon className="size-5" />
            </button>

            {/* Desktop Page Title / Mobile Brand */}
            <div className="flex items-center gap-3">
              <span className="hidden lg:block font-black text-lg text-stone-900">
                {title || 'Dova Kitchen'}
              </span>
              <div className="lg:hidden flex items-center gap-1.5 font-black text-rose-600 text-lg tracking-tighter">
                DOVA KITCHEN
                <span className="inline-block size-1.5 rounded-full bg-rose-600"></span>
              </div>
            </div>

            {/* Right: Quick Actions */}
            <div className="flex items-center gap-2">
              <Link
                to="/passport"
                className="size-10 rounded-full bg-white border border-stone-200 shadow-2xs flex items-center justify-center text-stone-700 hover:text-rose-600 active:scale-95 transition-all"
                title="Dietary Passport"
              >
                <ShieldCheck className="size-5" />
              </Link>

              <Link
                to="/order"
                className="size-10 rounded-full bg-white border border-stone-200 shadow-2xs flex items-center justify-center text-stone-700 hover:text-rose-600 active:scale-95 transition-all relative"
                title="Pesan Menu"
              >
                <ShoppingBag className="size-5" />
              </Link>
            </div>
          </div>
        </header>

        {/* ── Main View Content ── */}
        <main className="max-w-6xl w-full mx-auto px-4 py-6">
          {children}
        </main>
      </div>

      {/* ── Slide-over Mobile Sheet Drawer ── */}
      <Sheet open={isMobileMenuOpen} onOpenChange={setIsMobileMenuOpen}>
        <SheetContent side="left" className="w-72 p-0 bg-white border-r border-stone-200 flex flex-col justify-between">
          <div className="p-6">
            <div className="flex items-center justify-between pb-6 border-b border-stone-100">
              <div className="flex items-center gap-2.5 font-black text-rose-600 text-lg">
                <div className="size-8 rounded-xl bg-rose-600 text-white flex items-center justify-center text-sm font-black">
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
                  <NavLink
                    key={item.to}
                    to={item.to}
                    onClick={() => setIsMobileMenuOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-3.5 p-3 rounded-2xl text-sm font-semibold transition-all',
                        isActive
                          ? 'bg-rose-600 text-white font-bold'
                          : 'text-stone-700 hover:bg-stone-50'
                      )
                    }
                  >
                    <Icon className="size-5" />
                    <span>{item.label}</span>
                  </NavLink>
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
                className="w-full rounded-2xl bg-rose-600 text-white text-xs font-bold"
              >
                Masuk Akun
              </Button>
            )}
          </div>
        </SheetContent>
      </Sheet>

      {/* ── Sticky Bottom Mobile Navigation Bar ── */}
      <nav className="lg:hidden fixed bottom-0 inset-x-0 z-40 bg-white/95 backdrop-blur-md border-t border-stone-200 px-6 py-2.5">
        <div className="max-w-md mx-auto flex items-center justify-between">
          <Link
            to="/order"
            className="flex flex-col items-center gap-1 text-stone-500 hover:text-stone-900 font-medium text-[11px]"
          >
            <div className="size-7 flex items-center justify-center">
              <Utensils className="size-4" />
            </div>
            <span>Menu</span>
          </Link>

          <Link
            to="/orders"
            className="flex flex-col items-center gap-1 text-stone-500 hover:text-stone-900 font-medium text-[11px]"
          >
            <div className="size-7 flex items-center justify-center">
              <ShoppingBag className="size-4" />
            </div>
            <span>Pesanan</span>
          </Link>

          <Link
            to="/ai"
            className="flex flex-col items-center gap-1 text-amber-600 hover:text-amber-700 font-bold text-[11px]"
          >
            <div className="size-7 rounded-full bg-amber-50 flex items-center justify-center text-amber-600">
              <Sparkles className="size-4" />
            </div>
            <span>AI BOB</span>
          </Link>

          <Link
            to="/passport"
            className="flex flex-col items-center gap-1 text-stone-500 hover:text-stone-900 font-medium text-[11px]"
          >
            <div className="size-7 flex items-center justify-center">
              <ShieldCheck className="size-4" />
            </div>
            <span>Passport</span>
          </Link>
        </div>
      </nav>

      {/* ── Interactive AI Chef Chatbot ── */}
      <DovaChatbot />
    </div>
  )
}