import type { ReactNode } from 'react'
import { ClipboardList, LayoutDashboard, LogOut, Sparkles, UserRound } from 'lucide-react'

import { AppShell } from '@/components/layout/AppShell'
import type { NavItem } from '@/components/layout/Sidebar'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/useAuth'
import { BRAND } from '@/lib/constants'

/**
 * Customer-facing shell. Mobile-first: bottom-anchored primary actions,
 * a compact topbar, and navigation that collapses into a sheet.
 *
 * Kept visually quieter than the admin and kitchen surfaces — this is the
 * surface where a customer should feel reassured, not operational.
 */
export function PortalLayout({
  children,
  title,
}: {
  children: ReactNode
  title?: string
}) {
  const { customer, isAuthenticated, logout, hasRole } = useAuth()

  const nav: NavItem[] = [
    { to: '/menu', label: 'Menu', icon: ClipboardList },
    ...(isAuthenticated
      ? [
          { to: '/passport', label: 'Passport', icon: UserRound },
          { to: '/orders', label: 'Pesanan', icon: LayoutDashboard },
          { to: '/order', label: 'Pesan', icon: ClipboardList },
          { to: '/ai', label: 'Asisten AI', icon: Sparkles },
        ]
      : []),
  ]

  if (hasRole('admin', 'kitchen')) {
    nav.push(
      { to: '/admin', label: 'Admin', icon: LayoutDashboard, end: true },
      { to: '/kitchen', label: 'Dapur', icon: ClipboardList },
    )
  }

  return (
    <AppShell
      nav={nav}
      title={title}
      width="default"
      sidebarFooter={
        isAuthenticated ? (
          <div className="space-y-2">
            <p className="font-semibold text-ink">{customer?.display_name || customer?.username}</p>
            <p className="text-muted-text">@{customer?.username}</p>
            <Button variant="ghost" size="sm" onClick={logout} className="w-full justify-start gap-2">
              <LogOut aria-hidden="true" className="size-4" />
              Keluar
            </Button>
          </div>
        ) : (
          <p>{BRAND.tagline}</p>
        )
      }
    >
      {children}
    </AppShell>
  )
}