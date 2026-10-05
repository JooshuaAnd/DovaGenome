import { useEffect, type ReactNode } from 'react'
import { ChefHat } from 'lucide-react'

import { AppShell } from '@/components/layout/AppShell'
import type { NavItem } from '@/components/layout/Sidebar'
import { BRAND } from '@/lib/constants'
import { cn } from '@/lib/utils'

/**
 * Kitchen Display System shell.
 *
 * Optimised for a wall-mounted tablet: the dark high-contrast palette is
 * applied to the whole document, `data-touch="lg"` enlarges every tap target,
 * and content starts below the safe area so nothing hides behind a notch.
 */
export function KitchenLayout({
  children,
  title,
}: {
  children: ReactNode
  title?: string
}) {
  useEffect(() => {
    document.documentElement.classList.add('dark')
    return () => document.documentElement.classList.remove('dark')
  }, [])

  const nav: NavItem[] = [{ to: '/kitchen', label: 'Papan Dapur', icon: ChefHat, end: true }]

  return (
    <div data-touch="lg" className="min-h-dvh bg-canvas">
      <AppShell
        nav={nav}
        navLabel="Dapur"
        title={title}
        width="wide"
        className={cn(
          'px-3 py-4 sm:px-6 sm:py-6',
          // Larger base type — this screen is read from a distance.
          '[&_h1]:text-2xl [&_p]:text-base',
        )}
        sidebarFooter={<p>{BRAND.name} · Dapur presisi</p>}
      >
        {children}
      </AppShell>
    </div>
  )
}