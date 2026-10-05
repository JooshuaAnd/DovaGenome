import { ArrowRight, Check, ChevronLeft, Loader2, Lock, ShieldCheck } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { PageState } from '@/components/common/PageState'
import { DayOptionsList } from '@/components/menu/MenuOptionCard'
import { WeekEmptyCard, WeekStrip } from '@/components/menu/WeekStrip'
import { SafetyBadge } from '@/components/safety/SafetyBadge'
import { SafetyCallout } from '@/components/safety/SafetyCallout'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useApi } from '@/hooks/useApi'
import { useAsync } from '@/hooks/useAsync'
import { useAuth } from '@/hooks/useAuth'
import { useDailySelection, useServiceWeek, worstLevelOrUndefined } from '@/hooks/useServiceWeek'
import { DAY_SHORT } from '@/lib/constants'
import { cn } from '@/lib/utils'
import { formatIDR } from '@/lib/format'
import { catalogService } from '@/services/catalog'
import { customersService } from '@/services/customers'
import { getErrorMessage } from '@/services/http'
import { ordersService } from '@/services/orders'
import type {
  Allergen,
  DaySelection,
  Package,
  Passport,
  PassportIn,
  Restriction,
  RestrictionIn,
  SafetyLevel,
  ServiceDay,
} from '@/types'

type Step = 'profile' | 'package' | 'menu' | 'review'

const STEPS: Array<{ id: Step; title: string }> = [
  { id: 'profile', title: 'Batasan makanan' },
  { id: 'package', title: 'Paket & hari' },
  { id: 'menu', title: 'Menu tiap hari' },
  { id: 'review', title: 'Konfirmasi' },
]

/**
 * Weekly order wizard.
 *
 * Four linear steps, mobile-first, one decision per screen. The dietary profile
 * comes first on purpose: every later screen shows safety verdicts, and a verdict
 * means nothing before the restrictions it was computed against are known.
 *
 * Safety is never decided here. The backend recomputes it from the stored
 * passport on submit, so a blocked option is shown and marked rather than hidden
 * — a rejection is never a surprise on the last screen.
 */
export function OrderPage() {
  const { customer } = useAuth()

  const [step, setStep] = useState<Step>('profile')
  const [packageCode, setPackageCode] = useState('')
  const [scheduleDays, setScheduleDays] = useState<ServiceDay[]>([])
  const [activeDay, setActiveDay] = useState<ServiceDay | null>(null)
  const [note, setNote] = useState('')
  const [address, setAddress] = useState(customer?.phone ?? '')
  const [created, setCreated] = useState<string | null>(null)

  const { data: packages } = useApi<Package[]>((signal) => catalogService.listPackages(signal))
  const allergensQuery = useApi<Allergen[]>((signal) => catalogService.listAllergens(signal))
  const allergens = allergensQuery.data
  const passportQuery = useApi<Passport>((signal) => customersService.getPassport(signal))

  const activePackage = useMemo(
    () => packages?.find((item) => item.code === packageCode) ?? null,
    [packageCode, packages],
  )

  // Scoped to the chosen package so options hidden for that package cannot be picked,
  // and not fetched at all until a package exists.
  const week = useServiceWeek({
    package_code: packageCode || undefined,
    enabled: Boolean(packageCode),
  })
  const selection = useDailySelection(week.days.filter((day) => scheduleDays.includes(day.hari)))

  const submit = useAsync((payload: Parameters<typeof ordersService.create>[0]) =>
    ordersService.create(payload),
  )
  const savePassport = useAsync((payload: PassportIn) => customersService.savePassport(payload))

  const selectableDays = week.days.filter((day) => !day.is_past)
  const activeWeekDay = week.days.find((day) => day.hari === (activeDay ?? scheduleDays[0] ?? null))

  const levelByDay = useMemo(() => {
    const out: Partial<Record<ServiceDay, SafetyLevel>> = {}
    for (const day of week.days) {
      out[day.hari] = worstLevelOrUndefined(day.safety.map((entry) => entry.level))
    }
    return out
  }, [week.days])

  const chosenLevel = worstLevelOrUndefined(selection.resolved.map((item) => item.level))
  const blockedChosen = selection.resolved.filter((item) => item.level === 'blocked')

  const stepIndex = STEPS.findIndex((item) => item.id === step)

  const canContinuePackage = Boolean(packageCode) && scheduleDays.length > 0
  const canContinueMenu =
    scheduleDays.length > 0 && selection.undecided.length === 0 && selection.resolved.length > 0

  /* ── Dietary profile draft ──────────────────────────────────────────────
     Unedited, the form mirrors the stored passport and the sticky action bar can
     submit it unchanged. The first tap switches to `draft`, which then owns the
     values — so a successful save re-seeds from the refreshed passport instead
     of leaving the screen showing stale state. */

  const [draft, setDraft] = useState<{ codes: string[]; ingredients: string } | null>(null)

  const storedPassport = passportQuery.data
  const profileCodes = draft?.codes ?? (storedPassport ? criticalCodes(storedPassport) : [])
  const profileIngredients =
    draft?.ingredients ?? storedPassport?.avoided_ingredients.join(', ') ?? ''

  const editDraft = (patch: Partial<{ codes: string[]; ingredients: string }>) =>
    setDraft({ codes: profileCodes, ingredients: profileIngredients, ...patch })

  const toggleCode = (code: string) =>
    editDraft({
      codes: profileCodes.includes(code)
        ? profileCodes.filter((item) => item !== code)
        : [...profileCodes, code],
    })

  const handleSaveProfile = async () => {
    const passport = passportQuery.data
    if (!passport) return

    const saved = await savePassport.run(
      buildPassportPayload(passport, profileCodes, profileIngredients),
    )
    if (!saved) return

    toast.success('Batasan tersimpan', {
      description: `${saved.critical_codes.length} batasan dipakai saat memeriksa menu.`,
    })
    passportQuery.refetch()
    week.refetch()
    setStep('package')
  }

  /* ── Navigation ──────────────────────────────────────────────────────── */

  const toggleDay = (hari: ServiceDay) => {
    const next = scheduleDays.includes(hari)
      ? scheduleDays.filter((item) => item !== hari)
      : // Keep the service week's Monday-first order so the payload is deterministic.
        selectableDays
          .filter((day) => day.hari === hari || scheduleDays.includes(day.hari))
          .map((day) => day.hari)

    if (next.length === 0) return
    setScheduleDays(next)
    if (activeDay && !next.includes(activeDay)) setActiveDay(next[0])
    selection.clear()
  }

  const goBack = () => {
    if (step === 'menu') setStep('package')
    else if (step === 'review') setStep('menu')
    else setStep('profile')
  }

  const handleSubmit = async () => {
    const result = await submit.run({
      package_code: packageCode,
      schedule_days: scheduleDays,
      selections: selection.toInput(),
      customer_note: note.trim() || undefined,
      delivery_address: address.trim() || undefined,
      apply_passport: true,
    })

    if (result) {
      setCreated(result.order_id)
      toast.success('Pesanan terkirim', {
        description: `${result.selections.length} menu masuk ke dapur.`,
      })
    }
  }

  if (created) {
    return <OrderDone orderId={created} selections={selection.resolved} />
  }

  return (
    <div className="mx-auto w-full max-w-2xl">
      <ProgressHeader stepIndex={stepIndex} title={STEPS[stepIndex].title} onBack={goBack} />

      <div className="space-y-4 px-4 py-5 sm:px-6">
        {step === 'profile' && (
          <PageState
            loading={passportQuery.loading || allergensQuery.loading}
            error={passportQuery.error ?? allergensQuery.error}
            skeletonRows={3}
            onRetry={passportQuery.refetch}
          >
            {passportQuery.data && allergens && (
              <div className="space-y-5">
                <p className="text-sm text-ink-soft">
                  Semua status aman di langkah berikutnya dihitung dari batasan yang kamu pilih di
                  sini.
                </p>

                <section className="space-y-2">
                  <h2 className="text-sm font-bold uppercase tracking-wide text-muted-text">
                    Yang harus dihindari
                  </h2>

                  {allergens.filter((item) => item.active).length === 0 ? (
                    <p className="text-sm text-muted-text">Katalog allergen masih kosong.</p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {allergens
                        .filter((item) => item.active)
                        .map((item) => {
                          const active = profileCodes.includes(item.code)
                          return (
                            <Button
                              key={item.code}
                              type="button"
                              size="lg"
                              variant={active ? 'default' : 'outline'}
                              aria-pressed={active}
                              onClick={() => toggleCode(item.code)}
                              className="rounded-full"
                            >
                              {active && <Check aria-hidden="true" className="size-3.5" />}
                              {item.label}
                            </Button>
                          )
                        })}
                    </div>
                  )}

                  <p className="text-xs text-muted-text">
                    Yang dipilih dicatat sebagai alergi, jadi menu yang mengandung bahan itu diblokir
                    total.{' '}
                    <Link
                      to="/passport"
                      className="font-semibold text-forest-700 underline underline-offset-2"
                    >
                      Atur rinci di Preferensi Makanan
                    </Link>
                  </p>
                </section>

                <section className="space-y-1.5">
                  <Label htmlFor="profile-ingredients">Bahan lain yang dihindari</Label>
                  <Input
                    id="profile-ingredients"
                    value={profileIngredients}
                    onChange={(event) => editDraft({ ingredients: event.target.value })}
                    placeholder="MSG, jahe, gula"
                  />
                  <p className="text-xs text-muted-text">
                    Pisahkan dengan koma. Diteruskan ke dapur sebagai catatan.
                  </p>
                </section>

                {profileCodes.length > 0 && (
                  <SafetyCallout
                    level="caution"
                    title={`${profileCodes.length} batasan aktif`}
                    description="Menu yang mengandung bahan itu ditandai Diblokir dan tidak bisa dipilih di langkah berikutnya."
                  />
                )}

                {savePassport.error && (
                  <SafetyCallout
                    level="blocked"
                    title="Batasan gagal disimpan"
                    description={getErrorMessage(savePassport.error)}
                  />
                )}
              </div>
            )}
          </PageState>
        )}

        {step === 'package' && (
          <div className="space-y-5">
            <section className="space-y-2">
              <h2 className="text-sm font-bold uppercase tracking-wide text-muted-text">Paket</h2>

              {(packages ?? []).map((item) => {
                const active = item.code === packageCode
                return (
                  <button
                    key={item.code}
                    type="button"
                    onClick={() => {
                      setPackageCode(item.code)
                      setScheduleDays([])
                      selection.clear()
                    }}
                    aria-pressed={active}
                    className={cn(
                      'flex w-full items-start gap-3 rounded-xl border bg-surface p-4 text-left transition-colors',
                      active
                        ? 'border-forest-600 ring-1 ring-forest-600'
                        : 'border-line hover:border-line-strong',
                    )}
                  >
                    <span
                      aria-hidden="true"
                      className={cn(
                        'mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border-2',
                        active
                          ? 'border-forest-600 bg-forest-600 text-white'
                          : 'border-line text-transparent',
                      )}
                    >
                      <Check className="size-3" />
                    </span>

                    <span className="min-w-0 flex-1">
                      <span className="block font-display text-base font-bold text-ink">
                        {item.name}
                      </span>
                      {item.description && (
                        <span className="mt-0.5 block text-sm text-muted-text">
                          {item.description}
                        </span>
                      )}
                      <span className="mt-1 block text-xs font-semibold text-forest-700">
                        {item.days.length} hari layanan
                      </span>
                    </span>

                    <span className="shrink-0 text-right text-sm font-bold text-ink">
                      {item.price === null ? 'Belum ada harga' : formatIDR(item.price)}
                    </span>
                  </button>
                )
              })}

              {packages && packages.length === 0 && <WeekEmptyCard hasDays={false} />}
            </section>

            {activePackage && (
              <section className="space-y-2">
                <h2 className="text-sm font-bold uppercase tracking-wide text-muted-text">
                  Hari yang mau diisi
                </h2>
                <div className="flex flex-wrap gap-2">
                  {activePackage.days.map((hari) => {
                    const active = scheduleDays.includes(hari)
                    return (
                      <Button
                        key={hari}
                        type="button"
                        variant={active ? 'default' : 'outline'}
                        aria-pressed={active}
                        onClick={() => toggleDay(hari)}
                        className="min-w-16"
                      >
                        {DAY_SHORT[hari]}
                      </Button>
                    )
                  })}
                </div>
                {scheduleDays.length === 0 && (
                  <p className="text-sm text-muted-text">Pilih minimal satu hari.</p>
                )}
              </section>
            )}
          </div>
        )}

        {step === 'menu' && (
          <PageState loading={week.loading} error={week.error} skeletonRows={3} onRetry={week.refetch}>
            <div className="space-y-4">
              <WeekStrip
                days={week.days.filter((day) => scheduleDays.includes(day.hari))}
                active={activeWeekDay?.hari ?? null}
                onSelect={setActiveDay}
                levelByDay={levelByDay}
              />

              {selection.undecided.length > 0 && (
                <p className="text-sm font-medium text-caution-strong">
                  {selection.undecided.length} hari belum memilih menu —{' '}
                  {selection.undecided.map((day) => DAY_SHORT[day.hari]).join(', ')}.
                </p>
              )}

              {activeWeekDay && activeWeekDay.options.length > 0 ? (
                <DayOptionsList
                  day={activeWeekDay}
                  selectable
                  selectedMenuId={selection.choices[activeWeekDay.hari]}
                  onSelect={(menuId) => selection.choose(activeWeekDay.hari, menuId)}
                />
              ) : (
                <WeekEmptyCard hasDays={Boolean(activeWeekDay)} />
              )}
            </div>
          </PageState>
        )}

        {step === 'review' && (
          <div className="space-y-4">
            {chosenLevel && chosenLevel !== 'safe' && (
              <SafetyCallout
                level={blockedChosen.length > 0 ? 'blocked' : 'caution'}
                title={
                  blockedChosen.length > 0
                    ? `${blockedChosen.length} menu tidak cocok dengan batasanmu`
                    : 'Sebagian menu perlu perhatian'
                }
                description="Pesanan dengan alergen kritis yang bertabrakan ditolak backend. Ganti menunya untuk hari tersebut."
              />
            )}

            <section className="overflow-hidden rounded-xl border border-line bg-surface">
              <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
                <h2 className="text-base">Ringkasan</h2>
                {chosenLevel && <SafetyBadge level={chosenLevel} />}
              </div>

              <dl className="divide-y divide-line text-sm">
                <Row label="Paket" value={activePackage?.name ?? packageCode} />
                <Row
                  label="Harga"
                  value={
                    activePackage?.price == null
                      ? 'Belum ditetapkan'
                      : formatIDR(activePackage.price)
                  }
                />
                <Row label="Jumlah hari" value={`${scheduleDays.length} hari`} />
                <Row
                  label="Batasan dipakai"
                  value={
                    week.week?.applied_codes.length
                      ? `${week.week.applied_codes.length} kode`
                      : 'Tidak ada'
                  }
                />
              </dl>

              <ul className="divide-y divide-line border-t border-line">
                {selection.resolved.map((item) => (
                  <li key={item.hari} className="flex items-center gap-3 px-4 py-2.5">
                    <span className="w-9 shrink-0 text-xs font-bold uppercase tracking-wide text-muted-text">
                      {DAY_SHORT[item.hari]}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-sm font-semibold text-ink">
                      {item.nama_menu}
                    </span>
                    {item.level && <SafetyBadge level={item.level} size="sm" />}
                  </li>
                ))}
              </ul>
            </section>

            <section className="space-y-3 rounded-xl border border-line bg-surface p-4">
              <div className="space-y-1.5">
                <Label htmlFor="order-address">Alamat / nomor kontak</Label>
                <Textarea
                  id="order-address"
                  value={address}
                  onChange={(event) => setAddress(event.target.value)}
                  placeholder="Kantor Lt. 3, Jl. Sudirman, atau 0812…"
                  rows={2}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="order-note">Catatan untuk dapur</Label>
                <Textarea
                  id="order-note"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="Mis. toples pisahkan, tidak pedas"
                  rows={2}
                />
              </div>
            </section>

            {submit.error && (
              <SafetyCallout
                level="blocked"
                title="Pesanan ditolak"
                description={getErrorMessage(submit.error)}
                guidance={
                  submit.error.code === 'conflict'
                    ? 'Ubah pilihan menu lalu coba lagi.'
                    : undefined
                }
              />
            )}
          </div>
        )}
      </div>

      <ActionBar step={step} stepIndex={stepIndex}>
        {step === 'profile' ? (
          <>
            <Button variant="ghost" onClick={() => setStep('package')}>
              Lewati
            </Button>
            <Button
              size="lg"
              className="flex-1"
              disabled={savePassport.pending}
              onClick={() => void handleSaveProfile()}
            >
              {savePassport.pending ? (
                <>
                  <Loader2 aria-hidden="true" className="size-4 animate-spin" />
                  Menyimpan…
                </>
              ) : (
                <>
                  <ShieldCheck aria-hidden="true" className="size-4" />
                  Simpan & lanjut
                </>
              )}
            </Button>
          </>
        ) : (
          <>
            {step === 'review' && (
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-bold text-ink">
                  {activePackage?.price == null ? 'Harga menyusul' : formatIDR(activePackage.price)}
                </p>
                <p className="text-xs text-muted-text">{scheduleDays.length} hari</p>
              </div>
            )}

            <Button
              size="lg"
              className="flex-1"
              disabled={
                step === 'package'
                  ? !canContinuePackage
                  : step === 'menu'
                    ? !canContinueMenu
                    : submit.pending || selection.resolved.length === 0
              }
              onClick={() => {
                if (step === 'package') setStep('menu')
                else if (step === 'menu') setStep('review')
                else void handleSubmit()
              }}
            >
              {step === 'review' ? (
                submit.pending ? (
                  <>
                    <Loader2 aria-hidden="true" className="size-4 animate-spin" />
                    Mengirim…
                  </>
                ) : (
                  <>
                    <Lock aria-hidden="true" className="size-4" />
                    Kirim pesanan
                  </>
                )
              ) : (
                <>
                  {step === 'package' ? 'Pilih menu' : 'Tinjau pesanan'}
                  <ArrowRight aria-hidden="true" className="size-4" />
                </>
              )}
            </Button>
          </>
        )}
      </ActionBar>
    </div>
  )
}

/* ── Pieces ──────────────────────────────────────────────────────────────── */

function ProgressHeader({
  stepIndex,
  title,
  onBack,
}: {
  stepIndex: number
  title: string
  onBack: () => void
}) {
  return (
    <div className="sticky top-0 z-20 border-b border-line bg-canvas/95 backdrop-blur">
      <div className="flex items-center gap-2 px-4 pt-3 sm:px-6">
        {stepIndex > 0 ? (
          <Button variant="ghost" size="icon-sm" onClick={onBack} aria-label="Langkah sebelumnya">
            <ChevronLeft aria-hidden="true" className="size-5" />
          </Button>
        ) : (
          <span className="size-8 shrink-0" />
        )}

        <div className="min-w-0 flex-1 pb-1">
          <p className="text-[0.6875rem] font-bold uppercase tracking-wide text-muted-text">
            Langkah {stepIndex + 1} dari {STEPS.length}
          </p>
          <h1 className="truncate text-lg leading-tight">{title}</h1>
        </div>
      </div>

      <div className="flex gap-1 px-4 pb-2.5 sm:px-6" aria-hidden="true">
        {STEPS.map((item, index) => (
          <span
            key={item.id}
            className={cn(
              'h-1 flex-1 rounded-full transition-colors',
              index <= stepIndex ? 'bg-forest-600' : 'bg-line',
            )}
          />
        ))}
      </div>
    </div>
  )
}

function ActionBar({
  step,
  stepIndex,
  children,
}: {
  step: Step
  stepIndex: number
  children: ReactNode
}) {
  return (
    <div
      data-step={step}
      data-step-index={stepIndex}
      className="sticky bottom-0 z-20 flex items-center gap-2 border-t border-line bg-canvas/95 px-4 py-3 backdrop-blur sm:px-6"
    >
      {children}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2.5">
      <dt className="text-muted-text">{label}</dt>
      <dd className="truncate font-semibold text-ink">{value}</dd>
    </div>
  )
}

function OrderDone({ orderId, selections }: { orderId: string; selections: DaySelection[] }) {
  const navigate = useNavigate()

  return (
    <div className="mx-auto w-full max-w-2xl space-y-5 px-4 py-6 sm:px-6">
      <SafetyCallout
        level="safe"
        title="Pesanan terkirim ke dapur"
        description="Setiap hari punya tepat satu menu. Dapur menerima catatan bahan dan alat steril per menu, bukan menu utama hari itu."
      />

      <ul className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
        {selections.map((item) => (
          <li key={item.hari} className="flex items-center gap-3 px-4 py-3">
            <span className="w-9 shrink-0 text-xs font-bold uppercase tracking-wide text-muted-text">
              {DAY_SHORT[item.hari]}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-semibold text-ink">{item.nama_menu}</span>
              <span className="block text-xs text-muted-text">{item.date_label}</span>
            </span>
            {item.level && <SafetyBadge level={item.level} size="sm" />}
          </li>
        ))}
      </ul>

      <div className="flex flex-col gap-2 sm:flex-row">
        <Button onClick={() => navigate(`/orders/${orderId}`)} className="sm:flex-1">
          Lacak pesanan
        </Button>
        <Button asChild variant="outline" className="sm:flex-1">
          <Link to="/menu">Menu minggu ini</Link>
        </Button>
      </div>
    </div>
  )
}

/* ── Passport draft helpers ──────────────────────────────────────────────── */

function criticalCodes(passport: Passport): string[] {
  return [...passport.allergies, ...passport.intolerances, ...passport.medical].map(
    (item) => item.code,
  )
}

/**
 * Merge the chip selection back into the stored passport.
 *
 * Existing critical restrictions keep their original category so a customer who
 * recorded an intolerance does not silently get promoted to an allergy. Chips
 * that were not recorded before land in `allergies` — the most restrictive
 * bucket, so a mis-tap over-blocks rather than under-blocks. Preferences are
 * carried over untouched because they never block a menu.
 */
function buildPassportPayload(
  passport: Passport,
  codes: string[],
  ingredients: string,
): PassportIn {
  const existing: Restriction[] = [
    ...passport.allergies,
    ...passport.intolerances,
    ...passport.medical,
  ]
  const kept = existing.filter((item) => codes.includes(item.code))
  const keptCodes = new Set(kept.map((item) => item.code))
  const added: RestrictionIn[] = codes
    .filter((code) => !keptCodes.has(code))
    .map((code) => ({
      code,
      label:
        passport.allergies.find((item) => item.code === code)?.label ??
        existing.find((item) => item.code === code)?.label ??
        code,
      category: 'allergy',
    }))

  return {
    allergies: [...kept.filter((item) => item.category === 'allergy'), ...added],
    intolerances: kept.filter((item) => item.category === 'intolerance'),
    medical: kept.filter((item) => item.category === 'medical'),
    preferences: passport.preferences,
    avoided_ingredients: ingredients
      .split(',')
      .map((part) => part.trim())
      .filter(Boolean),
  }
}