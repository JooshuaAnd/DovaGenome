import { CalendarRange, Filter, ShieldQuestion } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { DayOptionsList } from '@/components/menu/MenuOptionCard'
import { DayNotices, WeekEmptyCard, WeekStrip } from '@/components/menu/WeekStrip'
import { PageState } from '@/components/common/PageState'
import { SafetyCallout } from '@/components/safety/SafetyCallout'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { worstLevelOrUndefined, useServiceWeek } from '@/hooks/useServiceWeek'
import { useAuth } from '@/hooks/useAuth'
import { formatIDR } from '@/lib/format'
import { useApi } from '@/hooks/useApi'
import { catalogService } from '@/services/catalog'
import type { Package, SafetyLevel, ServiceDay } from '@/types'

const ALL_PACKAGES = '__all__'

/**
 * Public weekly menu.
 *
 * Reads `/catalog/menus/week`: each service day, its date, and every menu option
 * with its own safety verdict. A package filter narrows the options to what that
 * package actually offers — the backend re-applies the same rule when the order
 * is submitted, so nothing shown here can fail at checkout.
 */
export function MenuPage() {
  const { customer } = useAuth()
  const [packageCode, setPackageCode] = useState<string>(ALL_PACKAGES)
  const [activeDay, setActiveDay] = useState<ServiceDay | null>(null)

  const { data: packages } = useApi<Package[]>((signal) => catalogService.listPackages(signal))

  const week = useServiceWeek({
    package_code: packageCode === ALL_PACKAGES ? undefined : packageCode,
  })

  const days = week.days
  const active = activeDay ?? days[0]?.hari ?? null
  const activeData = days.find((day) => day.hari === active)

  const levelByDay = useMemo(() => {
    const out: Partial<Record<ServiceDay, SafetyLevel>> = {}
    for (const day of days) {
      out[day.hari] = worstLevelOrUndefined(day.safety.map((entry) => entry.level))
    }
    return out
  }, [days])

  const selectedPackage = packages?.find((item) => item.code === packageCode) ?? null
  const blockedDays = days.filter((day) => levelByDay[day.hari] === 'blocked')

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 px-4 py-8 sm:px-6 sm:py-10">
      <header className="space-y-2">
        <p className="eyebrow">Katalog</p>
        <h1 className="text-2xl leading-tight sm:text-3xl">Menu minggu ini</h1>
        <p className="max-w-prose text-sm text-muted-text">
          Enam hari layanan, Senin sampai Sabtu. Setiap hari bisa punya beberapa pilihan menu —
          lihat bahan, alat dapur steril, dan status kecocokan sebelum memilih.
        </p>
      </header>

      {week.week?.has_passport && (
        <SafetyCallout
          level="safe"
          title="Preferensi makananmu sudah dipakai"
          description="Status aman/perhatian di halaman ini dihitung otomatis dari batasan yang tersimpan di Preferensi Makanan."
          action={
            <Button asChild size="sm" variant="outline">
              <Link to="/passport">Kelola Preferensi Makanan</Link>
            </Button>
          }
        />
      )}

      {!customer && (
        <Card className="flex flex-wrap items-center justify-between gap-3">
          <p className="flex items-center gap-2 text-sm text-ink-soft">
            <ShieldQuestion aria-hidden="true" className="size-4 text-muted-text" />
            Masuk untuk melihat status keamanan sesuai batasanmu.
          </p>
          <Button asChild size="sm">
            <Link to="/login?next=%2Fmenu">Masuk</Link>
          </Button>
        </Card>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <label
            htmlFor="menu-package-filter"
            className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-muted-text"
          >
            <Filter aria-hidden="true" className="size-3.5" />
            Paket
          </label>
          <Select value={packageCode} onValueChange={setPackageCode}>
            <SelectTrigger id="menu-package-filter" className="w-full sm:w-72">
              <SelectValue placeholder="Semua paket" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectLabel>Tampilkan menu untuk</SelectLabel>
                <SelectItem value={ALL_PACKAGES}>Semua paket</SelectItem>
                {(packages ?? []).map((item) => (
                  <SelectItem key={item.code} value={item.code}>
                    {item.name}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </div>

        {selectedPackage && (
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="font-semibold">
              <CalendarRange aria-hidden="true" className="size-3" />
              {selectedPackage.days.length} hari layanan
            </Badge>
            <Badge variant="outline" className="font-semibold">
              {selectedPackage.price === null
                ? 'Harga belum ditetapkan'
                : formatIDR(selectedPackage.price)}
            </Badge>
          </div>
        )}
      </div>

      <PageState loading={week.loading} error={week.error} skeletonRows={4} onRetry={week.refetch}>
        {days.length === 0 ? (
          <WeekEmptyCard hasDays={Boolean(week.week)} />
        ) : (
          <>
            <WeekStrip days={days} active={active} onSelect={setActiveDay} levelByDay={levelByDay} />

            {blockedDays.length > 0 && (
              <SafetyCallout
                level="blocked"
                title={`${blockedDays.length} hari punya menu yang tidak cocok`}
                description={`Menu pada ${blockedDays.map((day) => day.hari).join(', ')} mengandung bahan yang tidak boleh kamu makan. Menu yang tetap tersedia di hari yang sama bisa dipilih sebagai gantinya.`}
              />
            )}

            <section className="space-y-3">
              <DayNotices day={activeData} appliedCodes={week.week?.applied_codes} />

              {activeData && activeData.options.length > 0 ? (
                <DayOptionsList day={activeData} />
              ) : (
                <WeekEmptyCard hasDays />
              )}
            </section>

            <Card className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-ink-soft">
                Sudah punya batasan? Simpan di Preferensi Makanan supaya peringatan muncul otomatis.
              </p>
              <Button asChild size="sm">
                <Link to="/order">Mulai pesan</Link>
              </Button>
            </Card>
          </>
        )}
      </PageState>
    </div>
  )
}
