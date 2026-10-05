import { Loader2, NotebookPen, PhoneCall, Plus, ShieldCheck, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { PageState } from '@/components/common/PageState'
import { PageHeader } from '@/components/layout/PageHeader'
import { WeekStrip } from '@/components/menu/WeekStrip'
import { SafetyBadge } from '@/components/safety/SafetyBadge'
import { SafetyCallout } from '@/components/safety/SafetyCallout'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useApi } from '@/hooks/useApi'
import { useAsync } from '@/hooks/useAsync'
import { useServiceWeek, worstLevelOrUndefined } from '@/hooks/useServiceWeek'
import { AVOIDED_TIME_OPTIONS, CATEGORY_LABELS, DAY_SHORT } from '@/lib/constants'
import { catalogService } from '@/services/catalog'
import { customersService } from '@/services/customers'
import { getErrorMessage } from '@/services/http'
import type {
  Allergen,
  AvoidedTimeCode,
  Passport,
  PassportIn,
  Restriction,
  RestrictionCategory,
  RestrictionIn,
  SafetyLevel,
  ServiceDay,
} from '@/types'

type Group = 'allergies' | 'intolerances' | 'medical' | 'preferences'

const GROUPS: Array<{ id: Group; category: RestrictionCategory; hint: string }> = [
  {
    id: 'allergies',
    category: 'allergy',
    hint: 'Menyentuh backend sebagai allergen kritis. Menu yang mengandung bahan ini diblokir.',
  },
  {
    id: 'intolerances',
    category: 'intolerance',
    hint: 'Mengtrigger protokol steril dan peringatan di dapur, tanpa memblokir menu.',
  },
  {
    id: 'medical',
    category: 'medical',
    hint: 'Restriksi medis. Dapur wajib memisahkan peralatan dan menandai tiket masak.',
  },
  {
    id: 'preferences',
    category: 'preference',
    hint: 'Preferensi rasa saja. Tidak memblokir menu, hanya memunculkan catatan.',
  },
]

function collectRestrictions(passport: Passport): Array<Restriction & { group: Group }> {
  const out: Array<Restriction & { group: Group }> = []
  for (const group of GROUPS) {
    for (const item of passport[group.id]) out.push({ ...item, group: group.id })
  }
  return out
}

/**
 * Dietary Passport editor.
 *
 * `PUT /customers/me/passport` rejects codes that are not in the allergen
 * catalog, so the only choosable codes come from `/catalog/allergens` - no free
 * text invention. Saving sends all four groups every time so a removal is
 * persisted instead of being ignored as an absent key.
 */
export function PassportPage() {
  const passportQuery = useApi<Passport>((signal) => customersService.getPassport(signal))
  const { data: allergens } = useApi<Allergen[]>((signal) => catalogService.listAllergens(signal))

  // The preview always reflects what the server holds, never the unsaved draft.
  const week = useServiceWeek({ enabled: Boolean(passportQuery.data) })

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Profil dietary"
        title="Preferensi Makanan"
        description="Semua yang diisi di sini dipakai otomatis setiap kali kamu membuka menu mingguan atau membuat pesanan."
      />

      <PageState
        loading={passportQuery.loading}
        error={passportQuery.error}
        skeletonRows={4}
        onRetry={passportQuery.refetch}
      >
        {passportQuery.data && (
          <PassportForm
            // `updated_at` is the server revision: saving changes it, which
            // remounts the form from the freshly stored values instead of
            // syncing them back through an effect.
            key={passportQuery.data.updated_at}
            passport={passportQuery.data}
            allergens={allergens ?? []}
            week={week}
            onSaved={() => {
              passportQuery.refetch()
              week.refetch()
            }}
          />
        )}
      </PageState>

      {passportQuery.data && (
        <p className="text-xs text-muted-text">
          Terakhir diperbarui {passportQuery.data.updated_at || 'belum pernah disimpan'}.
        </p>
      )}
    </div>
  )
}

function PassportForm({
  passport,
  allergens,
  week,
  onSaved,
}: {
  passport: Passport
  allergens: Allergen[]
  week: ReturnType<typeof useServiceWeek>
  onSaved: () => void
}) {
  const [restrictions, setRestrictions] = useState<Array<Restriction & { group: Group }>>(() =>
    collectRestrictions(passport),
  )
  const [avoidedIngredients, setAvoidedIngredients] = useState(
    () => passport.avoided_ingredients.join(', '),
  )
  const [avoidedTimes, setAvoidedTimes] = useState<AvoidedTimeCode[]>(
    () => passport.avoided_times as AvoidedTimeCode[],
  )
  const [medicalNotes, setMedicalNotes] = useState(() => passport.medical_notes)
  const [safetyNotes, setSafetyNotes] = useState(() => passport.safety_notes)
  const [emergencyNotes, setEmergencyNotes] = useState(() => passport.emergency_notes)
  const [contact, setContact] = useState(() => passport.emergency_contact)
  const [dirty, setDirty] = useState(false)

  const save = useAsync((payload: PassportIn) => customersService.savePassport(payload))

  const levelByDay = useMemo(() => {
    const out: Partial<Record<ServiceDay, SafetyLevel>> = {}
    for (const day of week.days) {
      out[day.hari] = worstLevelOrUndefined(day.safety.map((entry) => entry.level))
    }
    return out
  }, [week.days])

  const usedCodes = useMemo(
    () => new Set(restrictions.map((item) => item.code)),
    [restrictions],
  )
  const palette = allergens.filter((item) => item.active && !usedCodes.has(item.code))

  const mutate = (
    updater: (current: Array<Restriction & { group: Group }>) => Array<Restriction & { group: Group }>,
  ) => {
    setRestrictions((current) => updater([...current]))
    setDirty(true)
  }

  const addRestriction = (allergen: Allergen) => {
    mutate((next) => [
      ...next,
      {
        code: allergen.code,
        label: allergen.label,
        category: 'allergy',
        severity: '',
        notes: '',
        group: 'allergies',
      },
    ])
  }

  const patchRestriction = (code: string, patch: Partial<Restriction & { group: Group }>) => {
    mutate((next) =>
      next.map((item) => (item.code === code ? { ...item, ...patch } : item)),
    )
  }

  const removeRestriction = (code: string) => {
    mutate((next) => next.filter((item) => item.code !== code))
  }

  const markDirty = () => setDirty(true)

  const handleSave = async () => {
    const payload: PassportIn = {
      allergies: restrictions.filter((item) => item.group === 'allergies').map(stripGroup),
      intolerances: restrictions.filter((item) => item.group === 'intolerances').map(stripGroup),
      medical: restrictions.filter((item) => item.group === 'medical').map(stripGroup),
      preferences: restrictions.filter((item) => item.group === 'preferences').map(stripGroup),
      avoided_ingredients: splitList(avoidedIngredients),
      avoided_times: avoidedTimes,
      medical_notes: medicalNotes.trim(),
      safety_notes: safetyNotes.trim(),
      emergency_notes: emergencyNotes.trim(),
      emergency_contact: {
        name: contact.name.trim(),
        phone: contact.phone.trim(),
        relationship: contact.relationship.trim(),
      },
    }

    const saved = await save.run(payload)
    if (saved) {
      setDirty(false)
      onSaved()
      toast.success('Preferensi Makanan disimpan', {
        description: `${saved.critical_codes.length} batasan kritis dipakai untuk memeriksa menu.`,
      })
    }
  }

  const criticalCount = restrictions.filter(
    (item) => item.group !== 'preferences',
  ).length

  return (
    <div className="space-y-6">
      {criticalCount > 0 ? (
        <SafetyCallout
          level="caution"
          title={`${criticalCount} batasan kritis aktif`}
          description="Menu yang mengandung bahan ini akan diberi status Diblokir dan tidak bisa dipilih untuk pesananmu."
        />
      ) : (
        <SafetyCallout
          level="safe"
          title="Belum ada batasan kritis"
          description="Tambahkan alergi, intoleransi, atau restriksi medis di bawah supaya status menu selalu akurat."
        />
      )}

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 text-lg">
            <ShieldCheck aria-hidden="true" className="size-4 text-muted-text" />
            Batasan tersimpan
          </h2>
          <Badge variant="outline" className="font-semibold">
            {restrictions.length} batasan
          </Badge>
        </div>

        {restrictions.length === 0 ? (
          <Card className="space-y-2 text-sm text-muted-text">
            <p className="font-display text-base font-bold text-ink">Belum ada batasan</p>
            <p>Pilih kode di bawah untuk menambahkannya ke kelompok yang tepat.</p>
          </Card>
        ) : (
          <ul className="space-y-3">
            {restrictions.map((item) => (
              <li key={item.code}>
                <Card className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-display text-base font-bold text-ink">{item.label}</p>
                      <p className="font-mono text-xs text-muted-text">{item.code}</p>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => removeRestriction(item.code)}
                      aria-label={`Hapus ${item.label}`}
                    >
                      <Trash2 aria-hidden="true" className="size-3.5" />
                    </Button>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label htmlFor={`group-${item.code}`}>Kelompok</Label>
                      <Select
                        value={item.group}
                        onValueChange={(value) =>
                          patchRestriction(item.code, {
                            group: value as Group,
                            category: GROUPS.find((group) => group.id === value)?.category,
                          })
                        }
                      >
                        <SelectTrigger id={`group-${item.code}`}>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {GROUPS.map((group) => (
                            <SelectItem key={group.id} value={group.id}>
                              {CATEGORY_LABELS[group.category]}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      <p className="text-xs text-muted-text">
                        {GROUPS.find((group) => group.id === item.group)?.hint}
                      </p>
                    </div>

                    <div className="space-y-1.5">
                      <Label htmlFor={`notes-${item.code}`}>Catatan</Label>
                      <Input
                        id={`notes-${item.code}`}
                        value={item.notes}
                        onChange={(event) => {
                          patchRestriction(item.code, { notes: event.target.value })
                        }}
                        placeholder="Mis. reaksinyaRuam, originalsaja"
                      />
                    </div>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-lg">Tambah batasan</h2>
        <p className="text-sm text-muted-text">
          Kode diambil dari katalog allergen yang aktif. Backend menolak kode yang tidak dikenal.
        </p>
        <div className="flex flex-wrap gap-2">
          {palette.length === 0 ? (
            <Badge variant="outline" className="font-semibold">
              Semua kode allergen sudah dipakai
            </Badge>
          ) : (
            palette.map((allergen) => (
              <Button
                key={allergen.code}
                type="button"
                size="sm"
                variant="outline"
                onClick={() => addRestriction(allergen)}
              >
                <Plus aria-hidden="true" className="size-3.5" />
                {allergen.label}
              </Button>
            ))
          )}
        </div>
      </section>

      <Separator />

      <section className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="passport-ingredients">Bahan yang dihindari</Label>
          <Input
            id="passport-ingredients"
            value={avoidedIngredients}
            onChange={(event) => {
              setAvoidedIngredients(event.target.value)
              markDirty()
            }}
            placeholder="Pisahkan dengan koma, mis. MSG, jahe"
          />
          <p className="text-xs text-muted-text">Dipakai sebagai catatan tambahan untuk dapur.</p>
        </div>

        <fieldset className="space-y-2">
          <legend className="text-sm font-semibold">Slot waktu yang dihindari</legend>
          <div className="flex flex-wrap gap-2">
            {(Object.keys(AVOIDED_TIME_OPTIONS) as AvoidedTimeCode[]).map((code) => {
              const active = avoidedTimes.includes(code)
              return (
                <Button
                  key={code}
                  type="button"
                  size="sm"
                  variant={active ? 'default' : 'outline'}
                  aria-pressed={active}
                  onClick={() => {
                    setAvoidedTimes((current) =>
                      current.includes(code)
                        ? current.filter((item) => item !== code)
                        : [...current, code],
                    )
                    markDirty()
                  }}
                >
                  {AVOIDED_TIME_OPTIONS[code]}
                </Button>
              )
            })}
          </div>
        </fieldset>

        <div className="space-y-1.5">
          <Label htmlFor="passport-medical">Catatan medis</Label>
          <Textarea
            id="passport-medical"
            value={medicalNotes}
            onChange={(event) => {
              setMedicalNotes(event.target.value)
              markDirty()
            }}
            rows={3}
            placeholder="Mis. maksimal 500 mg per sajian"
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="passport-safety">Catatan keselamatan</Label>
          <Textarea
            id="passport-safety"
            value={safetyNotes}
            onChange={(event) => {
              setSafetyNotes(event.target.value)
              markDirty()
            }}
            rows={3}
            placeholder="Mis. wajib memakai alat dapur terpisah"
          />
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-lg">
          <PhoneCall aria-hidden="true" className="size-4 text-muted-text" />
          Kontak darurat
        </h2>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label htmlFor="contact-name">Nama</Label>
            <Input
              id="contact-name"
              value={contact.name}
              onChange={(event) => {
                setContact({ ...contact, name: event.target.value })
                markDirty()
              }}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="contact-phone">Telepon</Label>
            <Input
              id="contact-phone"
              value={contact.phone}
              onChange={(event) => {
                setContact({ ...contact, phone: event.target.value })
                markDirty()
              }}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="contact-relation">Hubungan</Label>
            <Input
              id="contact-relation"
              value={contact.relationship}
              onChange={(event) => {
                setContact({ ...contact, relationship: event.target.value })
                markDirty()
              }}
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="passport-emergency">Catatan emergencies</Label>
          <Textarea
            id="passport-emergency"
            value={emergencyNotes}
            onChange={(event) => {
              setEmergencyNotes(event.target.value)
              markDirty()
            }}
            rows={2}
          />
        </div>
      </section>

      {save.error && (
        <SafetyCallout
          level="blocked"
          title="Preferensi tidak tersimpan"
          description={getErrorMessage(save.error)}
        />
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={handleSave} disabled={save.pending}>
          {save.pending ? (
            <>
              <Loader2 aria-hidden="true" className="size-4 animate-spin" />
              Menyimpan…
            </>
          ) : (
            <>
              <NotebookPen aria-hidden="true" className="size-4" />
              Simpan preferensi
            </>
          )}
        </Button>
        {dirty && (
          <p className="text-sm text-caution-strong">
            Ada perubahan yang belum disimpan.
          </p>
        )}
      </div>

      <Separator />

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg">Dampak terhadap menu minggu ini</h2>
          {week.loading && <span className="text-xs text-muted-text">Memuat…</span>}
        </div>

        <p className="text-sm text-muted-text">
          Diperhitungkan di server dari passport yang tersimpan, sama seperti saat memesan.
        </p>

        <WeekStrip
          days={week.days}
          active={null}
          onSelect={() => undefined}
          levelByDay={levelByDay}
          className="pointer-events-none"
        />

        <div className="space-y-2">
          {week.days
            .filter((day) => levelByDay[day.hari] === 'blocked')
            .map((day) => (
              <Card key={day.hari} className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold text-ink">
                    {DAY_SHORT[day.hari]} · {day.date_label}
                  </p>
                  <SafetyBadge level="blocked" />
                </div>
                <p className="text-sm text-muted-text">
                  {day.options
                    .filter(
                      (option) =>
                        day.safety[day.options.indexOf(option)]?.menu_id === option.menu_id &&
                        day.safety[day.options.indexOf(option)]?.level === 'blocked',
                    )
                    .map((option) => option.nama_menu)
                    .join(', ')}
                </p>
              </Card>
            ))}

          {week.days.length > 0 &&
            week.days.every((day) => levelByDay[day.hari] !== 'blocked') && (
              <SafetyCallout
                level="safe"
                title="Semua menu minggu ini lolos"
                description="Tidak ada menu yang diblokir oleh preferensi yang tersimpan."
              />
            )}

          <Button asChild variant="outline" size="sm">
            <Link to="/menu">Lihat menu yang sudah dipersonalisasi</Link>
          </Button>
        </div>
      </section>
    </div>
  )
}

function stripGroup(item: Restriction & { group: Group }): RestrictionIn {
  return {
    code: item.code,
    label: item.label,
    severity: item.severity || undefined,
    notes: item.notes || undefined,
  }
}

function splitList(value: string): string[] {
  return value
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean)
}
