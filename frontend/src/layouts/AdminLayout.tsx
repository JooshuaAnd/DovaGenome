import type { ReactNode } from 'react'
import { CalendarDays, ExternalLink, LayoutDashboard } from 'lucide-react'

import { AppShell } from '@/components/layout/AppShell'
import type { NavItem } from '@/components/layout/Sidebar'
import { Badge } from '@/components/ui/badge'
import { useAuth } from '@/hooks/useAuth'
import { BRAND } from '@/lib/constants'

/**
 * Back-office shell. Desktop and tablet first: a persistent sidebar, a wide
 * content column, and denser typography than the customer portal.
 */
export function AdminLayout({
  children,
  title,
}: {
  children: ReactNode
  title?: string
}) {
  const { customer } = useAuth()

  const nav: NavItem[] = [
    { to: '/admin', label: 'Ringkasan', icon: LayoutDashboard, end: true },
    { to: '/admin/daily-menu', label: 'Menu Harian', icon: CalendarDays },
  ]

  return (
    <AppShell
      nav={nav}
      navLabel="Operasional"
      title={title}
      width="wide"
      sidebarFooter={
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate font-semibold text-ink">
              {customer?.display_name || customer?.username}
            </span>
            <Badge variant="outline" className="border-forest-100 bg-forest-50 text-forest-700">
              admin
            </Badge>
          </div>
          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 font-semibold text-forest-700 hover:underline"
          >
            <ExternalLink aria-hidden="true" className="size-3" />
            Dokumentasi API
          </a>
          <p className="text-muted-text">{BRAND.name}</p>
        </div>
      }
    >
      {children}
    </AppShell>
  )
}