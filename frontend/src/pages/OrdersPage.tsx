import { AlertTriangle, CalendarCheck, ChevronRight, Clock, ShoppingBag } from 'lucide-react'
import { Link } from 'react-router-dom'

import { EmptyState } from '@/components/common/EmptyState'
import { PageState } from '@/components/common/PageState'
import { PageHeader } from '@/components/layout/PageHeader'
import { AllergenChip } from '@/components/safety/AllergenChip'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { DAY_SHORT, ORDER_STATUSES, SLA_LEVELS } from '@/lib/constants'
import { formatDateTimeWIB, formatIDR, formatMinutes, formatRelativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useApi } from '@/hooks/useApi'
import { ordersService } from '@/services/orders'
import type { Order, OrderStatus } from '@/types'

const FILTER_GROUPS: Array<{ id: string; label: string; statuses: OrderStatus[] | null }> = [
  { id: 'all', label: 'Semua', statuses: null },
  { id: 'active', label: 'Aktif', statuses: ['PENDING', 'PREPARING', 'READY'] },
  { id: 'done', label: 'Selesai', statuses: ['COMPLETED'] },
  { id: 'cancelled', label: 'Dibatalkan', statuses: ['CANCELLED'] },
]

/**
 * Customer order history, scoped to the signed-in customer by `GET /orders`.
 *
 * Each row shows the service menu that was actually chosen (`service_menu`, or
 * the v3 selections) rather than the day's default, because that is the part a
 * customer needs to recognise when checking what arrived.
 */
export function OrdersPage() {
  const query = useApi<Order[]>((signal) => ordersService.listMine({ signal }))
  const orders = query.data ?? []

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Pesanan"
        title="Pesanan saya"
        description="Riwayat pesanan beserta status, menu yang dipilih untuk tiap hari layanan, dan penanda keselamatan."
        actions={
          <Button asChild>
            <Link to="/order">
              <ShoppingBag aria-hidden="true" className="size-4" />
              Pesanan baru
            </Link>
          </Button>
        }
      />

      <PageState loading={query.loading} error={query.error} skeletonRows={4} onRetry={query.refetch}>
        {orders.length === 0 ? (
          <EmptyState
            icon={ShoppingBag}
            title="Belum ada pesanan"
            description="Pesanan pertamamu akan muncul di sini lengkap dengan menu per hari dan statusnya."
            action={
              <Button asChild>
                <Link to="/order">Buat pesanan mingguan</Link>
              </Button>
            }
          />
        ) : (
          <OrdersList orders={orders} />
        )}
      </PageState>
    </div>
  )
}

function OrdersList({ orders }: { orders: Order[] }) {
  return (
    <div className="space-y-4">
      {FILTER_GROUPS.map((group) => {
        const rows = group.statuses
          ? orders.filter((order) => group.statuses!.includes(order.status))
          : orders
        if (rows.length === 0) return null

        return (
          <section key={group.id} className="space-y-2">
            <h2 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-muted-text">
              {group.label}
              <Badge variant="outline" className="font-semibold">
                {rows.length}
              </Badge>
            </h2>

            <ul className="space-y-3">
              {rows.map((order) => (
                <li key={order.order_id}>
                  <OrderRow order={order} />
                </li>
              ))}
            </ul>
          </section>
        )
      })}
    </div>
  )
}

function OrderRow({ order }: { order: Order }) {
  const status = ORDER_STATUSES[order.status]
  const chosen = order.selections.filter((item) => item.nama_menu)
  const menuSummary =
    chosen.length > 0
      ? chosen.map((item) => `${DAY_SHORT[item.hari]}: ${item.nama_menu}`).join(' · ')
      : (order.service_menu ?? `Menu utama ${order.schedule_days.length} hari`)

  return (
    <Card className="transition-shadow hover:shadow-sm">
      <Link
        to={`/orders/${encodeURIComponent(order.order_id)}`}
        className="block cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-forest-600 rounded-xl"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1 space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm font-bold text-ink">{order.order_id}</span>
              <Badge variant="outline" className="font-bold">
                {status.label}
              </Badge>
              {order.has_safety_flags && (
                <Badge variant="outline" className="gap-1.5 font-semibold">
                  <AlertTriangle aria-hidden="true" className="size-3" />
                  Ada catatan safety
                </Badge>
              )}
            </div>

            <p className="text-sm text-ink-soft">{menuSummary}</p>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-text">
              <span className="flex items-center gap-1">
                <CalendarCheck aria-hidden="true" className="size-3" />
                {order.schedule_days.map((day) => DAY_SHORT[day]).join(', ')}
              </span>
              <span className="flex items-center gap-1">
                <Clock aria-hidden="true" className="size-3" />
                {formatRelativeTime(order.created_at)}
              </span>
              <span>{formatDateTimeWIB(order.created_at)}</span>
              {order.status !== 'COMPLETED' && order.status !== 'CANCELLED' && (
                <span
                  className={cn(
                    'font-semibold',
                    order.sla_level === 'late'
                      ? 'text-blocked-strong'
                      : order.sla_level === 'soon'
                        ? 'text-caution-strong'
                        : 'text-muted-text',
                  )}
                >
                  {SLA_LEVELS[order.sla_level].label} · {formatMinutes(order.elapsed_minutes)}
                </span>
              )}
              <span>{formatIDR(order.total)}</span>
            </div>

            {order.allergen_labels.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-0.5">
                {order.allergen_labels.map((label) => (
                  <AllergenChip key={label} label={label} />
                ))}
              </div>
            )}
          </div>

          <ChevronRight aria-hidden="true" className="mt-1 size-4 shrink-0 text-muted-text" />
        </div>
      </Link>
    </Card>
  )
}
