import {
  CalendarDays,
  Eye,
  EyeOff,
  Loader2,
  Plus,
  UtensilsCrossed,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { EmptyState } from '@/components/common/EmptyState'
import { PageState } from '@/components/common/PageState'
import { PageHeader } from '@/components/layout/PageHeader'
import { SafetyBadge } from '@/components/safety/SafetyBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useAsync } from '@/hooks/useAsync'
import { useServiceWeek } from '@/hooks/useServiceWeek'
import { DAY_SHORT } from '@/lib/constants'
import { cn } from '@/lib/utils'
import { catalogService } from '@/services/catalog'
import { getErrorMessage } from '@/services/http'
import type { Menu } from '@/types'

/**
 * Daily menu management, one card per service day.
 *
 * A day holds several options and the customer picks one per served day, so this
 * page edits options by `menu_id` - never by day. Publishing is separate from
 * saving: an unpublished option stays in the catalog and keeps its history in
 * past orders, it just disappears from `/menu`.
 */
export function DailyMenuPage() {
  const week = useServiceWeek()
  const toggle = useAsync((menuId: string, published: boolean) =>
    catalogService.setMenuPublished(menuId, published),
  )

  const handleToggle = async (menu: Menu) => {
    const result = await toggle.run(menu.menu_id, !menu.published)
    if (result) {
      toast.success(
        result.published ? 'Menu dipublikasikan' : 'Menu ditarik dari mingguan',
        {
          description: `${result.nama_menu} · ${DAY_SHORT[result.hari]}`,
        },
      )
      week.refetch()
    }
  }

  const days = week.days
  const totalOptions = days.reduce((sum, day) => sum + day.options.length, 0)

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Administrasi"
        title="Menu harian"
        description="Setiap hari layanan bisa punya beberapa pilihan menu. Pelanggan memilih satu per hari saat memesan."
        actions={
          <Button asChild>
            <Link to="/admin/daily-menu/new">
              <Plus aria-hidden="true" />
              Tambah pilihan menu
            </Link>
          </Button>
        }
      />

      <PageState loading={week.loading} error={week.error} skeletonRows={3} onRetry={week.refetch}>
        {totalOptions === 0 ? (
          <EmptyState
            icon={UtensilsCrossed}
            title="Belum ada menu"
            description="Tambahkan pilihan menu pertama untuk mulai mengisi minggu layanan."
            action={
              <Button asChild>
                <Link to="/admin/daily-menu/new">
                  <Plus aria-hidden="true" />
                  Tambah pilihan menu
                </Link>
              </Button>
            }
          />
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-muted-text">
              {totalOptions} pilihan menu pada {days.filter((day) => day.options.length > 0).length} hari
              layanan.
            </p>

            {toggle.error && (
              <Card className="border-l-4 border-l-blocked-strong text-sm">
                {getErrorMessage(toggle.error)}
              </Card>
            )}

            {days.map((day) => (
              <Card key={day.hari} className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <CalendarDays aria-hidden="true" className="size-4 text-muted-text" />
                    <h2 className="font-display text-base font-bold text-ink">
                      {DAY_SHORT[day.hari]}
                    </h2>
                    <span className="text-xs text-muted-text">{day.date_label}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="font-semibold">
                      {day.options.length} pilihan
                    </Badge>
                    <Button asChild size="sm" variant="outline">
                      <Link
                        to={`/admin/daily-menu/${encodeURIComponent(day.hari)}`}
                        aria-label={`Tambah pilihan menu untuk ${day.hari}`}
                      >
                        <Plus aria-hidden="true" className="size-3.5" />
                        Opsi
                      </Link>
                    </Button>
                  </div>
                </div>

                {day.options.length === 0 ? (
                  <p className="text-sm text-muted-text">Belum ada pilihan menu untuk hari ini.</p>
                ) : (
                  <ul className="space-y-2">
                    {day.options.map((menu) => {
                      const verdict = day.safety.find((entry) => entry.menu_id === menu.menu_id)
                      return (
                        <li
                          key={menu.menu_id}
                          className={cn(
                            'flex flex-wrap items-start justify-between gap-3 rounded-lg border p-3',
                            !menu.published && 'border-dashed opacity-70',
                          )}
                        >
                          <div className="min-w-0 flex-1 space-y-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-semibold text-ink">{menu.nama_menu}</p>
                              {menu.option_index > 0 && (
                                <Badge variant="outline">Pilihan {menu.option_index + 1}</Badge>
                              )}
                              {!menu.published && (
                                <Badge variant="outline" className="font-semibold">
                                  Belum dipublikasikan
                                </Badge>
                              )}
                              {verdict && <SafetyBadge level={verdict.level} size="sm" />}
                            </div>
                            {menu.deskripsi && (
                              <p className="text-sm text-muted-text">{menu.deskripsi}</p>
                            )}
                            <p className="font-mono text-xs text-muted-text">
                              {menu.menu_id}
                            </p>
                            <p className="text-xs text-muted-text">
                              Paket:{' '}
                              {menu.package_codes.length === 0
                                ? 'semua paket'
                                : menu.package_codes.join(', ')}
                            </p>
                          </div>

                          <div className="flex shrink-0 items-center gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={toggle.pending}
                              onClick={() => handleToggle(menu)}
                            >
                              {toggle.pending ? (
                                <Loader2 aria-hidden="true" className="size-3.5 animate-spin" />
                              ) : menu.published ? (
                                <EyeOff aria-hidden="true" className="size-3.5" />
                              ) : (
                                <Eye aria-hidden="true" className="size-3.5" />
                              )}
                              {menu.published ? 'Tarik' : 'Publikasikan'}
                            </Button>
                            <Button asChild size="sm">
                              <Link
                                to={`/admin/daily-menu/${encodeURIComponent(day.hari)}/${encodeURIComponent(menu.menu_id)}`}
                              >
                                Ubah
                              </Link>
                            </Button>
                          </div>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </Card>
            ))}
          </div>
        )}
      </PageState>
    </div>
  )
}
