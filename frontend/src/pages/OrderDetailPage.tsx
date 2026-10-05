import {
  AlertTriangle,
  ChefHat,
  ClipboardList,
  FileText,
  MapPin,
  Receipt,
  ShieldAlert,
  StickyNote,
  Workflow,
} from 'lucide-react'
import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'

import { EmptyState } from '@/components/common/EmptyState'
import { PageState } from '@/components/common/PageState'
import { PageHeader } from '@/components/layout/PageHeader'
import { AllergenChip } from '@/components/safety/AllergenChip'
import { SafetyBadge } from '@/components/safety/SafetyBadge'
import { SafetyCallout } from '@/components/safety/SafetyCallout'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { useApi } from '@/hooks/useApi'
import { DAY_SHORT, ORDER_STATUSES, SLA_LEVELS } from '@/lib/constants'
import {
  formatDateTimeWIB,
  formatIDR,
  formatMinutes,
  formatRelativeTime,
  joinTruthy,
} from '@/lib/format'
import { cn } from '@/lib/utils'
import { ordersService } from '@/services/orders'
import type { DaySafety, DaySelection, OrderDetail } from '@/types'

/** A service day of this order, with the menu the customer actually chose. */
interface ResolvedDay {
  hari: DaySafety['hari']
  nama_menu: string
  deskripsi: string
  allergen_labels: string[]
  alat_dapur_steril: string[]
  level: DaySafety['level']
  headline: string
  explanation: string
  guidance: string
  is_recommended: boolean
  service_date?: string
  date_label?: string
}

/**
 * Order detail: what was ordered, and why it was safe to order.
 *
 * The chosen menu comes from `selections` (schema `v3`). Orders created before
 * multi-option menus have none, so their days are resolved from the safety
 * report instead - that path is labelled as reconstructed rather than shown as if
 * the customer had picked it.
 */
export function OrderDetailPage() {
  const { id } = useParams<{ id: string }>()
  const query = useApi<OrderDetail>((signal) => ordersService.detail(id ?? '', signal), {
    enabled: Boolean(id),
    deps: [id ?? ''],
  })

  const order = query.data
  const status = order ? ORDER_STATUSES[order.status] : null

  const days = useMemo<ResolvedDay[]>(() => {
    if (!order) return []

    const fromSelections: ResolvedDay[] = order.selections.map((selection: DaySelection) => {
      const report = order.safety?.per_day.find((item) => item.hari === selection.hari)
      return {
        hari: selection.hari,
        nama_menu: selection.nama_menu ?? report?.nama_menu ?? 'Menu tidak tercatat',
        deskripsi: selection.deskripsi ?? report?.deskripsi ?? '',
        allergen_labels: selection.allergen_labels ?? report?.allergen_labels ?? [],
        alat_dapur_steril: selection.alat_dapur_steril ?? report?.alat_dapur_steril ?? [],
        level: selection.level ?? report?.level ?? 'safe',
        headline: report?.headline ?? '',
        explanation: report?.explanation ?? '',
        guidance: report?.guidance ?? '',
        is_recommended: selection.is_recommended ?? report?.is_recommended ?? false,
        service_date: selection.service_date,
        date_label: selection.date_label,
      }
    })

    if (fromSelections.length > 0) return fromSelections

    return (order.safety?.per_day ?? []).map((item) => ({
      hari: item.hari,
      nama_menu: item.nama_menu,
      deskripsi: item.deskripsi,
      allergen_labels: item.allergen_labels,
      alat_dapur_steril: item.alat_dapur_steril,
      level: item.level,
      headline: item.headline,
      explanation: item.explanation,
      guidance: item.guidance,
      is_recommended: item.is_recommended,
    }))
  }, [order])

  const isLegacy = order !== null && order.selections.length === 0
  const safety = order?.safety ?? null

  return (
    <div className="space-y-6">
      <PageState loading={query.loading} error={query.error} skeletonRows={4} onRetry={query.refetch}>
        {order && (
          <>
            <PageHeader
              eyebrow="Pesanan"
              title={order.order_id}
              description={`Dibuat ${formatDateTimeWIB(order.created_at)} · ${formatRelativeTime(order.created_at)}`}
              actions={
                <Button asChild variant="outline">
                  <Link to={`/orders/${order.order_id}/invoice`}>
                    <Receipt aria-hidden="true" className="size-4" />
                    Lihat invoice
                  </Link>
                </Button>
              }
            />

            <div className="flex flex-wrap items-center gap-2">
              {status && (
                <Badge variant="outline" className="gap-1.5 font-bold">
                  {status.label}
                </Badge>
              )}
              <Badge variant="outline" className="font-semibold">
                <Workflow aria-hidden="true" className="size-3" />
                {formatMinutes(order.elapsed_minutes)}
              </Badge>
              {order.sla_level !== 'fresh' && (
                <Badge
                  variant="outline"
                  className={cn(
                    'font-semibold',
                    order.sla_level === 'late'
                      ? 'border-blocked-line bg-blocked-soft text-blocked-strong'
                      : 'border-caution-line bg-caution-soft text-caution-strong',
                  )}
                >
                  {SLA_LEVELS[order.sla_level].label}
                </Badge>
              )}
              {order.has_safety_flags && (
                <Badge variant="outline" className="gap-1.5 font-semibold">
                  <ShieldAlert aria-hidden="true" className="size-3" />
                  Ada catatan safety
                </Badge>
              )}
              <Badge variant="outline" className="font-semibold">
                {ORDER_STATUSES[order.status].label} · {order.next_status ? `berikutnya ${order.next_status}` : 'selesai'}
              </Badge>
            </div>

            {isLegacy && (
              <SafetyCallout
                level="caution"
                title="Menu hari ini dipulihkan dari laporan safety"
                description="Pesanan ini dibuat sebelum memilih satu menu per hari. Nama menu di bawah berasal dari menu utama saat itu, bukan dari pilihan eksplisit."
                guidance="Pesanan baru selalu menyimpan pilihan menu per hari."
              />
            )}

            {safety && (
              <SafetyCallout
                level={safety.level}
                title={safety.headline}
                description={safety.explanation}
                guidance={safety.guidance}
              />
            )}

            <section className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="flex items-center gap-2 text-lg">
                  <ChefHat aria-hidden="true" className="size-4 text-muted-text" />
                  Menu per hari layanan
                </h2>
                <Badge variant="outline" className="font-semibold">
                  {days.length} hari
                </Badge>
              </div>

              {days.length === 0 ? (
                <EmptyState
                  icon={ClipboardList}
                  title="Belum ada menu tercatat"
                  description="Pesanan ini tidak punya rincian menu per hari."
                  size="sm"
                />
              ) : (
                <ul className="space-y-3">
                  {days.map((day) => (
                    <li key={day.hari}>
                      <Card className="space-y-3">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="text-xs font-bold uppercase tracking-wide text-muted-text">
                              {DAY_SHORT[day.hari]}
                              {day.date_label ? ` · ${day.date_label}` : ''}
                            </p>
                            <p className="font-display text-base font-bold text-ink">
                              {day.nama_menu}
                            </p>
                            {day.deskripsi && (
                              <p className="mt-1 text-sm text-muted-text">{day.deskripsi}</p>
                            )}
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            {day.is_recommended && (
                              <Badge variant="outline" className="font-semibold">
                                Direkomendasikan
                              </Badge>
                            )}
                            <SafetyBadge level={day.level} />
                          </div>
                        </div>

                        {day.explanation && (
                          <p className="text-sm text-ink-soft">{day.explanation}</p>
                        )}

                        {day.allergen_labels.length > 0 && (
                          <div className="flex flex-wrap items-center gap-1.5">
                            <span className="text-xs font-bold uppercase tracking-wide text-muted-text">
                              Mengandung
                            </span>
                            {day.allergen_labels.map((label) => (
                              <AllergenChip key={label} label={label} />
                            ))}
                          </div>
                        )}

                        {day.alat_dapur_steril.length > 0 && (
                          <div className="rounded-lg bg-sunken p-3">
                            <p className="mb-1 text-xs font-bold uppercase tracking-wide text-muted-text">
                              Alat dapur steril
                            </p>
                            <ul className="list-inside list-disc space-y-0.5 text-sm text-ink-soft">
                              {day.alat_dapur_steril.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </Card>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {safety && safety.conflicts.length > 0 && (
              <section className="space-y-3">
                <h2 className="flex items-center gap-2 text-lg">
                  <AlertTriangle aria-hidden="true" className="size-4 text-muted-text" />
                  Konflik bahan
                </h2>
                {safety.conflicts.map((conflict) => (
                  <Card key={`${conflict.allergen_code}-${conflict.found_in.join()}`} className="space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-semibold text-ink">{conflict.allergen_label}</p>
                      <Badge variant="outline" className="font-semibold">
                        {conflict.category}
                      </Badge>
                    </div>
                    <p className="text-sm text-ink-soft">{conflict.explanation}</p>
                    {conflict.ingredient_names.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {conflict.ingredient_names.map((name) => (
                          <Badge key={name} variant="outline">
                            {name}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </Card>
                ))}
              </section>
            )}

            <Separator />

            <section className="grid gap-4 sm:grid-cols-2">
              <Card className="space-y-2">
                <h2 className="flex items-center gap-2 font-display text-base font-bold text-ink">
                  <FileText aria-hidden="true" className="size-4 text-muted-text" />
                  Ringkasan
                </h2>
                <dl className="space-y-1.5 text-sm">
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-text">Paket</dt>
                    <dd className="text-right font-semibold text-ink">
                      {order.package_code}
                      {order.subscription_type && order.subscription_type !== '—'
                        ? ` · ${order.subscription_type}`
                        : ''}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-text">Jumlah makan</dt>
                    <dd className="text-right font-semibold text-ink">{order.meal_count}</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-text">Total</dt>
                    <dd className="text-right font-semibold text-ink">{formatIDR(order.total)}</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-text">Pembayaran</dt>
                    <dd className="text-right font-semibold text-ink">{order.payment_status}</dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-muted-text">Versi data</dt>
                    <dd className="text-right font-mono text-xs text-muted-text">
                      {order.schema_version}
                    </dd>
                  </div>
                </dl>
              </Card>

              <Card className="space-y-3">
                <h2 className="flex items-center gap-2 font-display text-base font-bold text-ink">
                  <StickyNote aria-hidden="true" className="size-4 text-muted-text" />
                  Catatan
                </h2>

                {order.allergen_labels.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {order.allergen_labels.map((label) => (
                      <AllergenChip key={label} label={label} />
                    ))}
                  </div>
                )}

                {order.kitchen_notes && (
                  <p className="text-sm text-ink-soft">{order.kitchen_notes}</p>
                )}
                {order.customer_note && (
                  <p className="text-sm text-ink-soft">
                    <span className="font-semibold">Catatan pelanggan: </span>
                    {order.customer_note}
                  </p>
                )}
                {order.delivery_address && (
                  <p className="flex items-start gap-1.5 text-sm text-ink-soft">
                    <MapPin aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
                    {order.delivery_address}
                  </p>
                )}
                {order.avoided_times.length > 0 && (
                  <p className="text-sm text-ink-soft">
                    Slot dihindari: {joinTruthy(order.avoided_times, ', ')}
                  </p>
                )}
              </Card>
            </section>

            {order.timeline.length > 0 && (
              <section className="space-y-3">
                <h2 className="flex items-center gap-2 text-lg">
                  <Workflow aria-hidden="true" className="size-4 text-muted-text" />
                  Linimasa status
                </h2>
                <Card>
                  <ol className="space-y-3">
                    {order.timeline.map((entry, index) => {
                      const at = String(entry.at ?? entry.created_at ?? '')
                      const entryStatus = entry.status as keyof typeof ORDER_STATUSES | undefined
                      const meta = entryStatus ? ORDER_STATUSES[entryStatus] : null
                      return (
                        <li key={`${at}-${index}`} className="flex gap-3">
                          <span
                            aria-hidden="true"
                            className="mt-1 size-2.5 shrink-0 rounded-full bg-forest-600"
                          />
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-ink">
                              {meta?.label ?? String(entry.status ?? 'Status')}
                            </p>
                            <p className="text-xs text-muted-text">
                              {formatDateTimeWIB(at)}
                              {entry.actor ? ` · ${String(entry.actor)}` : ''}
                            </p>
                            {entry.note ? (
                              <p className="mt-0.5 text-sm text-ink-soft">{String(entry.note)}</p>
                            ) : null}
                          </div>
                        </li>
                      )
                    })}
                  </ol>
                </Card>
              </section>
            )}

            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline">
                <Link to="/orders">Semua pesanan</Link>
              </Button>
              <Button asChild variant="ghost">
                <Link to="/order">Buat pesanan lain</Link>
              </Button>
            </div>
          </>
        )}
      </PageState>
    </div>
  )
}
