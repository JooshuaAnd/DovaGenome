import { Link, NavLink } from 'react-router-dom'
import type { LucideIcon } from 'lucide-react'
import { Utensils } from 'lucide-react'

import { Separator } from '@/components/ui/separator'
import { BRAND } from '@/lib/constants'
import { cn } from '@/lib/utils'

export interface BrandProps {
  /** Compact mark for collapsed sidebars. */
  size?: 'sm' | 'md' | 'lg'
  /** Render the whole brand as a link to the customer home. */
  asLink?: boolean
  className?: string
  tone?: 'forest' | 'red'
}

const MARK_SIZE: Record<NonNullable<BrandProps['size']>, string> = {
  sm: 'size-8 rounded-lg text-sm',
  md: 'size-10 rounded-xl text-base',
  lg: 'size-12 rounded-[14px] text-lg',
}

/**
 * The brand lockup.
 *
 * A single restrained forest mark with a warm gradient edge — the only place
 * in the product where a gradient is allowed, mirroring `theme.py`'s logo.
 */
export function Brand({ size = 'md', asLink = false, className, tone = 'forest' }: BrandProps) {
  const content = (
    <span className={cn('flex items-center gap-3', className)}>
      <span
        aria-hidden="true"
        className={cn(
          cn('flex shrink-0 items-center justify-center font-bold text-white', tone === 'red' ? 'bg-gradient-to-br from-red-900 via-rose-800 to-amber-500' : 'bg-gradient-to-br from-forest-700 via-forest-600 to-gold-600'),
          MARK_SIZE[size],
        )}
      >
        <Utensils className={size === 'sm' ? 'size-4' : 'size-5'} />
      </span>

      {size !== 'sm' && (
        <span className="min-w-0">
          <span className="block font-display text-base leading-tight font-bold text-ink">
            {BRAND.name}
          </span>
          <span className="block text-[0.625rem] leading-tight font-extrabold tracking-[0.16em] text-gold-600 uppercase">
            {BRAND.sub}
          </span>
        </span>
      )}
    </span>
  )

  if (!asLink) return content

  return (
    <Link to="/" className="rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring">
      {content}
    </Link>
  )
}

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** Optional count or status dot rendered on the trailing edge. */
  badge?: React.ReactNode
  /** Mark the item active for nested routes (used by admin/kitchen sections). */
  end?: boolean
}

export interface SidebarNavProps {
  items: NavItem[]
  /** Heading rendered above a group of items. */
  label?: string
  onNavigate?: () => void
  className?: string
  accent?: 'forest' | 'red'
}

/** Vertical navigation list shared by the desktop sidebar and the mobile sheet. */
export function SidebarNav({ items, label, onNavigate, className, accent = 'forest' }: SidebarNavProps) {
  const activeTone = accent === 'red' ? 'bg-rose-50 text-red-900' : 'bg-forest-50 text-forest-700'
  const hoverTone = accent === 'red' ? 'hover:bg-rose-50/70 hover:text-red-900' : 'hover:bg-forest-50/60 hover:text-forest-700'
  const iconActiveTone = accent === 'red' ? 'text-red-800' : 'text-forest-600'
  return (
    <nav className={cn('space-y-1', className)} aria-label={label ?? 'Navigasi utama'}>
      {label && <p className="eyebrow px-3 pt-2 pb-1">{label}</p>}

      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-semibold transition-colors',
              'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
              isActive
                ? activeTone
                : cn('text-ink-soft', hoverTone),
            )
          }
        >
          {({ isActive }) => (
            <>
              <item.icon
                aria-hidden="true"
                className={cn(
                  'size-4 shrink-0',
                  isActive ? iconActiveTone : cn('text-muted-text', accent === 'red' ? 'group-hover:text-red-800' : 'group-hover:text-forest-600'),
                )}
              />
              <span className="min-w-0 flex-1 truncate">{item.label}</span>
              {item.badge}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

export interface SidebarProps {
  items: NavItem[]
  /** Footer slot — session summary or a version stamp. */
  footer?: React.ReactNode
  label?: string
  className?: string
  accent?: 'forest' | 'red'
}

/**
 * Desktop sidebar: brand block, navigation, and an optional footer pinned to
 * the bottom. Deliberately flat — no nested card stacks.
 */
export function Sidebar({ items, footer, label, className, accent = 'forest' }: SidebarProps) {
  return (
    <div className={cn('flex h-full flex-col border-r border-line bg-sidebar', className)}>
      <div className="px-5 py-5">
      <Brand size="md" asLink tone={accent} />
      </div>

      <Separator />

      <div className="flex-1 overflow-y-auto px-3 py-4">
        <SidebarNav items={items} label={label} accent={accent} />
      </div>

      {footer && (
        <div className="border-t border-line px-5 py-4 text-xs text-muted-text">{footer}</div>
      )}
    </div>
  )
}
