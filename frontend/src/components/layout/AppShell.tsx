import { useState, type ReactNode } from 'react'

import { Sidebar, SidebarNav, Brand, type NavItem } from '@/components/layout/Sidebar'
import { Topbar } from '@/components/layout/Topbar'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { cn } from '@/lib/utils'

export interface AppShellProps {
  /** Persistent navigation. Rendered as a sidebar from `lg` upwards. */
  nav: NavItem[]
  /** Heading above the navigation groups in the sidebar. */
  navLabel?: string
  /** Page title shown in the mobile topbar. */
  title?: string
  /** Sidebar footer — session summary, environment stamp, etc. */
  sidebarFooter?: ReactNode
  /** Extra controls pinned to the trailing edge of the topbar. */
  topbarActions?: ReactNode
  /** Constrain the main column and widen it for dense data tables. */
  width?: 'default' | 'wide' | 'full'
  children: ReactNode
  className?: string
}

const WIDTH: Record<NonNullable<AppShellProps['width']>, string> = {
  default: 'max-w-6xl',
  wide: 'max-w-[88rem]',
  full: 'max-w-none',
}

/**
 * The shared application frame: sidebar on desktop, slide-over sheet on mobile,
 * sticky topbar, and a width-constrained main column.
 *
 * Layout differences between the portal, admin, and kitchen surfaces are
 * expressed through props here rather than by forking the shell three times.
 */
export function AppShell({
  nav,
  navLabel,
  title,
  sidebarFooter,
  topbarActions,
  width = 'default',
  children,
  className,
}: AppShellProps) {
  const [navOpen, setNavOpen] = useState(false)

  return (
    <div className="min-h-dvh lg:flex">
      {/* Persistent sidebar — desktop and tablet. */}
      <aside className="hidden lg:fixed lg:inset-y-0 lg:left-0 lg:block lg:w-64 xl:w-72">
        <Sidebar items={nav} label={navLabel} footer={sidebarFooter} className="h-full" />
      </aside>

      {/* Slide-over navigation — small screens. */}
      <Sheet open={navOpen} onOpenChange={setNavOpen}>
        <SheetContent side="left" className="w-72 p-0">
          <SheetHeader className="px-5 pt-5 pb-4">
            <SheetTitle asChild>
              <Brand size="md" asLink />
            </SheetTitle>
          </SheetHeader>
          <SidebarNav
            items={nav}
            label={navLabel}
            onNavigate={() => setNavOpen(false)}
            className="px-3 pb-6"
          />
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col lg:pl-64 xl:pl-72">
        <Topbar onOpenNav={() => setNavOpen(true)} title={title} actions={topbarActions} />

        <main className={cn('flex-1 px-4 py-6 sm:px-6 sm:py-8', className)}>
          <div className={cn('mx-auto w-full', WIDTH[width])}>{children}</div>
        </main>
      </div>
    </div>
  )
}