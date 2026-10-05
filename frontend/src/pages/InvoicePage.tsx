import { Printer, Receipt } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { EmptyState } from '@/components/common/EmptyState'
import { PageState } from '@/components/common/PageState'
import { PageHeader } from '@/components/layout/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { useApi } from '@/hooks/useApi'
import { BRAND, DAY_SHORT, PAYMENT_STATUSES } from '@/lib/constants'
import { formatDateTimeWIB, formatIDR, formatNumber } from '@/lib/format'
import { cn } from '@/lib/utils'
import { ordersService } from '@/services/orders'
import type { Invoice } from '@/types'

/**
 * Printable invoice for one order.
 *
 * Amounts come from the values stored on the order, not from the live catalog, so
 * an old invoice never changes when package prices are edited later. The layout
 * is deliberately plain and prints on white - it is a document, not a dashboard.
 */
export function InvoicePage() {
  const { id } = useParams<{ id: string }>()
  const query = useApi<Invoice>(
    (signal) => ordersService.invoice(id ?? '', signal),
    { enabled: Boolean(id), deps: [id ?? ''] },
  )

  const invoice = query.data
  const payment = invoice ? PAYMENT_STATUSES[invoice.payment_status] : null

  return (
    <div className="space-y-6">
      <PageState loading={query.loading} error={query.error} skeletonRows={4} onRetry={query.refetch}>
        {invoice && (
          <>
            <PageHeader
              eyebrow="Dokumen"
              title={invoice.invoice_number}
              description={`Diterbitkan ${formatDateTimeWIB(invoice.issued_at)} · ${invoice.currency}`}
              actions={
                <Button variant="outline" onClick={() => window.print()}>
                  <Printer aria-hidden="true" className="size-4" />
                  Cetak
                </Button>
              }
            />

            <Card className="space-y-6 print:border-0 print:shadow-none">
              <header className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="font-display text-lg font-bold text-ink">{BRAND.name}</p>
                  <p className="text-sm text-muted-text">{BRAND.sub}</p>
                  <p className="mt-1 text-xs text-muted-text">{BRAND.tagline}</p>
                </div>
                <div className="text-right">
                  <p className="font-mono text-sm font-bold text-ink">{invoice.invoice_number}</p>
                  <p className="text-xs text-muted-text">{invoice.order_id}</p>
                  {payment && (
                    <Badge
                      variant="outline"
                      className={cn('mt-1 font-bold', payment.tone === 'info' && 'border-caution-line text-caution-strong')}
                    >
                      {payment.label}
                    </Badge>
                  )}
                </div>
              </header>

              <Separator />

              <section className="grid gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wide text-muted-text">
                    Pelanggan
                  </p>
                  <p className="text-sm font-semibold text-ink">{invoice.customer_name}</p>
                  {invoice.customer_contact && (
                    <p className="text-sm text-muted-text">{invoice.customer_contact}</p>
                  )}
                </div>
                <div>
                  <p className="text-xs font-bold uppercase tracking-wide text-muted-text">Paket</p>
                  <p className="text-sm font-semibold text-ink">{invoice.package_name}</p>
                  <p className="text-sm text-muted-text">
                    {invoice.schedule_days.map((day) => DAY_SHORT[day]).join(', ')} ·{' '}
                    {formatNumber(invoice.meal_count)} meal
                  </p>
                </div>
                <div>
                  <p className="text-xs font-bold uppercase tracking-wide text-muted-text">
                    Referensi pembayaran
                  </p>
                  <p className="text-sm text-ink">
                    {invoice.payment_reference || 'Belum ada referensi'}
                  </p>
                </div>
              </section>

              <section className="space-y-2">
                <h2 className="text-sm font-bold uppercase tracking-wide text-muted-text">Rincian</h2>
                {invoice.lines.length === 0 ? (
                  <EmptyState
                    icon={Receipt}
                    title="Belum ada baris invoice"
                    description="Harga paket belum ditetapkan, sehingga belum ada yang perlu dibayar."
                    size="sm"
                  />
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-muted-text">
                        <th className="pb-2 font-semibold">Item</th>
                        <th className="pb-2 text-right font-semibold">Jumlah</th>
                        <th className="pb-2 text-right font-semibold">Harga satuan</th>
                        <th className="pb-2 text-right font-semibold">Jumlah</th>
                      </tr>
                    </thead>
                    <tbody>
                      {invoice.lines.map((line, index) => (
                        <tr key={`${line.label}-${index}`} className="border-b border-line/60">
                          <td className="py-2 text-ink">{line.label}</td>
                          <td className="py-2 text-right text-ink-soft">
                            {formatNumber(line.quantity)}
                          </td>
                          <td className="py-2 text-right text-ink-soft">
                            {formatIDR(line.unit_price)}
                          </td>
                          <td className="py-2 text-right font-semibold text-ink">
                            {formatIDR(line.amount)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                    <tfoot className="text-sm">
                      <tr>
                        <td colSpan={3} className="py-1 text-right text-muted-text">
                          Subtotal
                        </td>
                        <td className="py-1 text-right text-ink-soft">
                          {formatIDR(invoice.subtotal)}
                        </td>
                      </tr>
                      {invoice.discount > 0 && (
                        <tr>
                          <td colSpan={3} className="py-1 text-right text-muted-text">
                            Diskon
                          </td>
                          <td className="py-1 text-right text-safe-strong">
                            -{formatIDR(invoice.discount)}
                          </td>
                        </tr>
                      )}
                      <tr>
                        <td colSpan={3} className="py-1 text-right font-semibold text-ink">
                          Total
                        </td>
                        <td className="py-1 text-right font-display text-base font-bold text-ink">
                          {formatIDR(invoice.total)}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                )}
              </section>

              {invoice.dietary_safety_summary && (
                <section className="space-y-1 rounded-lg bg-sunken p-3">
                  <p className="text-xs font-bold uppercase tracking-wide text-muted-text">
                    Ringkasan keamanan pangan
                  </p>
                  <p className="text-sm text-ink-soft">{invoice.dietary_safety_summary}</p>
                  {invoice.dietary_safety_items.length > 0 && (
                    <ul className="list-inside list-disc text-sm text-ink-soft">
                      {invoice.dietary_safety_items.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  )}
                </section>
              )}
            </Card>

            <div className="flex flex-wrap gap-2 print:hidden">
              <Button asChild variant="outline">
                <Link to={`/orders/${encodeURIComponent(invoice.order_id)}`}>
                  Kembali ke detail pesanan
                </Link>
              </Button>
            </div>
          </>
        )}
      </PageState>
    </div>
  )
}
