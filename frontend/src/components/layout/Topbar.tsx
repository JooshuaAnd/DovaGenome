import { ChevronDown, LogOut, Menu as MenuIcon, UserRound } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'

import { Brand } from '@/components/layout/Sidebar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'

export interface TopbarProps {
  /** Opens the mobile navigation sheet. */
  onOpenNav?: () => void
  /** Page label shown on mobile where the sidebar is hidden. */
  title?: string
  /** Portal-level links rendered inline (desktop only). */
  nav?: Array<{ to: string; label: string }>
  actions?: ReactNode
  className?: string
}

/**
 * Sticky application bar: brand, primary navigation, and the session menu.
 *
 * On small screens the navigation collapses into a sheet and only the brand,
 * a title, and the account menu remain visible.
 */
export function Topbar({ onOpenNav, title, nav, actions, className }: TopbarProps) {
  const { customer, isAuthenticated, logout } = useAuth()

  return (
    <header
      className={cn(
        'sticky top-0 z-40 border-b border-line bg-surface/85 backdrop-blur-md',
        className,
      )}
    >
      <div className="flex h-16 items-center gap-3 px-4 sm:px-6">
        {onOpenNav && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onOpenNav}
            aria-label="Buka navigasi"
            className="lg:hidden"
          >
            <MenuIcon aria-hidden="true" />
          </Button>
        )}

        <div className="lg:hidden">
          <Brand size="sm" asLink />
        </div>
        <div className="hidden lg:block">
          <Brand size="sm" asLink />
        </div>

        {title && (
          <span className="truncate text-sm font-semibold text-ink lg:hidden">{title}</span>
        )}

        {nav && nav.length > 0 && (
          <nav className="ml-6 hidden items-center gap-5 lg:flex" aria-label="Navigasi portal">
            {nav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'rounded text-sm font-semibold transition-colors hover:text-forest-700',
                    isActive ? 'text-forest-700' : 'text-ink-soft',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        )}

        <div className="ml-auto flex items-center gap-2">
          {actions}

          {isAuthenticated && customer ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="gap-2 px-2">
                  <span
                    aria-hidden="true"
                    className="flex size-7 items-center justify-center rounded-full bg-forest-100 text-xs font-bold text-forest-700"
                  >
                    {(customer.display_name || customer.username).slice(0, 1).toUpperCase()}
                  </span>
                  <span className="hidden max-w-28 truncate text-sm font-semibold sm:inline">
                    {customer.display_name || customer.username}
                  </span>
                  <ChevronDown aria-hidden="true" className="size-3.5 opacity-60" />
                </Button>
              </DropdownMenuTrigger>

              <DropdownMenuContent align="end" className="w-60">
                <DropdownMenuLabel className="space-y-0.5">
                  <span className="block truncate text-sm font-bold text-ink">
                    {customer.display_name || customer.username}
                  </span>
                  <span className="block truncate text-xs font-normal text-muted-text">
                    @{customer.username}
                  </span>
                </DropdownMenuLabel>

                <div className="px-2 pb-2">
                  <Badge variant="outline" className="border-forest-100 bg-forest-50 text-forest-700">
                    <UserRound aria-hidden="true" className="size-3" />
                    {customer.role}
                  </Badge>
                </div>

                <DropdownMenuSeparator />

                <DropdownMenuItem asChild>
                  <Link to="/passport">Dietary Passport</Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to="/orders">Pesanan saya</Link>
                </DropdownMenuItem>

                <DropdownMenuSeparator />

                <DropdownMenuItem
                  variant="destructive"
                  onSelect={() => logout()}
                  className="gap-2"
                >
                  <LogOut aria-hidden="true" className="size-4" />
                  Keluar
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <Button asChild size="sm">
              <Link to="/login">Masuk</Link>
            </Button>
          )}
        </div>
      </div>
    </header>
  )
}