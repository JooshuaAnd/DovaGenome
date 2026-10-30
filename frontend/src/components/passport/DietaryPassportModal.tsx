import { useEffect, useMemo, useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CircleHelp,
  Loader2,
  ShieldCheck,
  Sparkles,
  Target,
  Utensils,
  X,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { customersService } from '@/services/customers'
import { getErrorMessage } from '@/services/http'
import type { Allergen, Passport, PassportIn } from '@/types'

interface DietaryPassportModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  passport?: Passport | null
  allergens?: Allergen[]
  displayName?: string
  loading?: boolean
  loadError?: string | null
  onRetry?: () => void
  onboarding?: boolean
  onSaved?: (passport: Passport) => void
  onSaveName?: (name: string) => Promise<void>
}

const GOALS = [
  {
    value: 'balanced',
    label: 'Makan seimbang',
    description: 'Variasi protein, sayur, dan karbohidrat yang nyaman untuk harian.',
  },
  {
    value: 'high_protein',
    label: 'Fokus protein',
    description: 'Prioritaskan menu dengan protein lebih tinggi untuk energi dan rasa kenyang.',
  },
  {
    value: 'high_fat_high_protein',
    label: 'Tinggi lemak & protein',
    description: 'Cari menu dengan lemak dan protein per porsi yang tercatat terverifikasi.',
  },
  {
    value: 'high_fat',
    label: 'Fokus lemak',
    description: 'Cari menu dengan kandungan lemak per porsi yang tercatat terverifikasi.',
  },
  {
    value: 'lighter',
    label: 'Lebih ringan',
    description: 'Pilih menu yang terasa lebih ringan dengan porsi dan bahan yang seimbang.',
  },
  {
    value: 'fat_loss',
    label: 'Mengurangi lemak tubuh',
    description: 'Simpan target komposisi tubuh; rekomendasi perlu data energi dan lemak menu terverifikasi.',
  },
  {
    value: 'low_fat',
    label: 'Pilihan rendah lemak',
    description: 'Rekomendasi rendah lemak hanya dapat dipastikan jika data lemak resep terverifikasi.',
  },
  {
    value: 'plant_forward',
    label: 'Lebih banyak nabati',
    description: 'Lebihkan pilihan sayur, tahu, tempe, dan bahan nabati lainnya.',
  },
] as const

const STEPS = [
  { label: 'Alergi', icon: ShieldCheck },
  { label: 'Selera', icon: Utensils },
  { label: 'Fokusmu', icon: Target },
]

export function DietaryPassportModal({
  open,
  onOpenChange,
  passport,
  allergens = [],
  displayName,
  loading = false,
  loadError = null,
  onRetry,
  onboarding = false,
  onSaved,
  onSaveName,
}: DietaryPassportModalProps) {
  const [step, setStep] = useState(0)
  const [name, setName] = useState('')
  const [nameSaved, setNameSaved] = useState(false)
  const [savingName, setSavingName] = useState(false)
  const [selectedAllergens, setSelectedAllergens] = useState<string[]>([])
  const [dislikedFoods, setDislikedFoods] = useState<string[]>([])
  const [dislikedInput, setDislikedInput] = useState('')
  const [nutritionGoal, setNutritionGoal] = useState('balanced')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const allergenOptions = useMemo(() => {
    const existing = passport?.allergies ?? []
    const known = new Set(allergens.map((item) => item.code))
    const missingExisting = existing
      .filter((item) => !known.has(item.code))
      .map((item) => ({
        code: item.code,
        label: item.label,
        risiko: 'Tersimpan di profil',
        active: true,
        category: 'saved',
      }))

    return [...missingExisting, ...allergens.filter((item) => item.active)]
  }, [allergens, passport?.allergies])

  useEffect(() => {
    if (!open) return

    setStep(0)
    setName(displayName?.trim() && displayName !== 'Pelanggan' ? displayName : '')
    setNameSaved(false)
    setSelectedAllergens(passport?.allergies.map((item) => item.code) ?? [])
    setDislikedFoods(passport?.avoided_ingredients ?? [])
    setDislikedInput('')
    setNutritionGoal(passport?.nutrition_goal || 'balanced')
    setError(null)
  }, [open, passport, displayName])

  function toggleAllergen(code: string) {
    setSelectedAllergens((current) =>
      current.includes(code) ? current.filter((item) => item !== code) : [...current, code],
    )
  }

  function addDislikedFood() {
    const values = dislikedInput
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)

    if (values.length === 0) return
    setDislikedFoods((current) => Array.from(new Set([...current, ...values])))
    setDislikedInput('')
  }

  function removeDislikedFood(value: string) {
    setDislikedFoods((current) => current.filter((item) => item !== value))
  }

  async function save() {
    setSaving(true)
    setError(null)

    const existingByCode = new Map((passport?.allergies ?? []).map((item) => [item.code, item]))
    const allergyPayload = selectedAllergens
      .map((code) => {
        const existing = existingByCode.get(code)
        const catalogItem = allergenOptions.find((item) => item.code === code)
        return {
          code,
          label: existing?.label || catalogItem?.label || code,
          category: 'allergy' as const,
          severity: existing?.severity || '',
          notes: existing?.notes || '',
        }
      })

    const payload: PassportIn = {
      allergies: allergyPayload,
      avoided_ingredients: dislikedFoods,
      nutrition_goal: nutritionGoal,
    }

    try {
      const saved = await customersService.savePassport(payload)
      onSaved?.(saved)
      onOpenChange(false)
    } catch (cause) {
      setError(getErrorMessage(cause))
    } finally {
      setSaving(false)
    }
  }

  if (!open) return null

  const needsName = onboarding && !nameSaved && (!displayName?.trim() || displayName === 'Pelanggan')
  const stepOffset = needsName ? 1 : 0
  const steps = needsName ? [{ label: 'Namamu', icon: Utensils }, ...STEPS] : STEPS
  const isLastStep = step === steps.length - 1
  const greeting = displayName?.trim() || 'user'

  async function saveNameAndContinue() {
    if (name.trim().length < 2 || !onSaveName) {
      setError('Tulis namamu dulu (minimal 2 karakter).')
      return
    }
    setSavingName(true)
    setError(null)
    try {
      await onSaveName(name.trim())
      setNameSaved(true)
      setStep(0)
    } catch (cause) {
      setError(getErrorMessage(cause))
    } finally {
      setSavingName(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-forest-950/70 p-4 backdrop-blur-sm animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="dietary-passport-title"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !saving) onOpenChange(false)
      }}
    >
      <Card className="relative max-h-[min(760px,calc(100dvh-2rem))] w-full max-w-2xl overflow-y-auto rounded-[2rem] border-line bg-surface p-0 shadow-float animate-rise-in">
        <div className="sticky top-0 z-10 border-b border-line bg-surface/95 px-5 py-4 backdrop-blur-md sm:px-7">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="eyebrow flex items-center gap-2">
                <Sparkles className="size-3.5" /> Profil makanan personal
              </div>
              <h2 id="dietary-passport-title" className="mt-1 text-2xl sm:text-3xl">
                {onboarding ? `Halo ${greeting}!` : 'Atur Dietary Passport'}
              </h2>
              <p className="mt-1 max-w-xl text-sm leading-relaxed text-muted-text">
                {onboarding
                  ? 'Biar rekomendasi menu Dova lebih pas, jawab tiga hal singkat ini.'
                  : 'Atur preferensi yang akan dipakai saat menyaring menu dan memberi rekomendasi.'}
              </p>
            </div>
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              disabled={saving}
              className="rounded-full border border-line p-2 text-muted-text transition-colors hover:bg-muted hover:text-ink disabled:opacity-50"
              aria-label="Tutup Dietary Passport"
            >
              <X className="size-5" />
            </button>
          </div>

          <div className="mt-5 grid grid-cols-3 gap-2">
            {steps.map((item, index) => {
              const Icon = item.icon
              const active = index === step
              const complete = index < step
              return (
                <div key={item.label} className="flex items-center gap-2 text-xs font-semibold">
                  <div
                    className={`flex size-8 shrink-0 items-center justify-center rounded-full border transition-colors ${
                      active
                        ? 'border-forest-900 bg-forest-900 text-white'
                        : complete
                          ? 'border-safe-line bg-safe-soft text-safe-strong'
                          : 'border-line bg-sunken text-muted-text'
                    }`}
                  >
                    {complete ? <Check className="size-4" /> : <Icon className="size-4" />}
                  </div>
                  <span className={active ? 'text-ink' : 'text-muted-text'}>{item.label}</span>
                </div>
              )
            })}
          </div>
        </div>

        <div className="space-y-6 px-5 py-6 sm:px-7">
          {loading ? (
            <div className="flex min-h-56 items-center justify-center text-muted-text">
              <Loader2 className="mr-2 size-5 animate-spin" /> Memuat profilmu…
            </div>
          ) : loadError ? (
            <div className="flex min-h-56 flex-col items-center justify-center text-center">
              <div className="max-w-md rounded-2xl border border-blocked-line bg-blocked-soft px-5 py-4 text-sm text-blocked-strong">
                <p className="font-bold">Profil belum bisa dimuat</p>
                <p className="mt-1 text-xs leading-relaxed">{loadError}</p>
              </div>
              <div className="mt-4 flex gap-2">
                {onRetry && (
                  <Button type="button" variant="outline" onClick={onRetry} className="rounded-xl">
                    Coba lagi
                  </Button>
                )}
                <Button type="button" onClick={() => onOpenChange(false)} className="rounded-xl bg-forest-900 text-white hover:bg-forest-800">
                  Tutup
                </Button>
              </div>
            </div>
          ) : (
            <>
              {needsName && step === 0 && (
                <section className="space-y-4">
                  <div>
                    <p className="text-lg font-bold text-ink">Boleh tahu namamu?</p>
                    <p className="mt-1 text-sm text-muted-text">Nomor teleponmu sudah terhubung. Isi nama supaya Chef BOB bisa menyapa dan menyiapkan pilihan yang lebih personal.</p>
                  </div>
                  <Input autoFocus value={name} onChange={(event) => setName(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void saveNameAndContinue() }} placeholder="Namamu" className="h-12 rounded-xl border-line bg-surface" />
                </section>
              )}

              {step === stepOffset && (
                <section className="space-y-4">
                  <div>
                    <p className="text-lg font-bold text-ink">Kamu alergi apa?</p>
                    <p className="mt-1 text-sm text-muted-text">
                      Pilih semua yang perlu kami tandai untuk keamanan dapur. Kalau tidak ada, lanjutkan saja.
                    </p>
                  </div>

                  {allergenOptions.length === 0 ? (
                    <div className="rounded-2xl border border-dashed border-line-strong bg-sunken p-5 text-sm text-muted-text">
                      Daftar alergen belum tersedia. Kamu tetap bisa lanjut dan mengisinya nanti.
                    </div>
                  ) : (
                    <div className="grid gap-2 sm:grid-cols-2">
                      {allergenOptions.map((item) => {
                        const selected = selectedAllergens.includes(item.code)
                        return (
                          <button
                            type="button"
                            key={item.code}
                            onClick={() => toggleAllergen(item.code)}
                            className={`flex items-center justify-between gap-3 rounded-2xl border p-3 text-left transition-all ${
                              selected
                                ? 'border-rose-200 bg-rose-50 text-rose-950 shadow-sm'
                                : 'border-line bg-surface text-ink-soft hover:border-forest-300 hover:bg-forest-50'
                            }`}
                          >
                            <span>
                              <span className="block text-sm font-bold">{item.label}</span>
                              <span className="mt-0.5 block text-[11px] text-muted-text">{item.risiko}</span>
                            </span>
                            <span
                              className={`flex size-6 shrink-0 items-center justify-center rounded-full border ${
                                selected
                                  ? 'border-rose-600 bg-rose-600 text-white'
                                  : 'border-line-strong text-transparent'
                              }`}
                            >
                              <Check className="size-3.5" />
                            </span>
                          </button>
                        )
                      })}
                    </div>
                  )}

                  <div className="flex items-start gap-2 rounded-2xl border border-safe-line bg-safe-soft p-3 text-xs leading-relaxed text-safe-strong">
                    <ShieldCheck className="mt-0.5 size-4 shrink-0" />
                    Alergi yang dipilih akan memunculkan peringatan sebelum menu masuk keranjang.
                  </div>
                </section>
              )}

              {step === stepOffset + 1 && (
                <section className="space-y-4">
                  <div>
                    <p className="text-lg font-bold text-ink">Kamu tidak suka makan apa?</p>
                    <p className="mt-1 text-sm text-muted-text">
                      Tulis bahan atau rasa yang ingin dihindari. Ini berbeda dari alergi dan tidak akan memblokir menu secara otomatis.
                    </p>
                  </div>

                  <div className="flex gap-2">
                    <Input
                      value={dislikedInput}
                      onChange={(event) => setDislikedInput(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          event.preventDefault()
                          addDislikedFood()
                        }
                      }}
                      placeholder="contoh: petai, jeroan, terlalu pedas"
                      className="h-12 rounded-xl border-line bg-surface"
                    />
                    <Button type="button" variant="outline" onClick={addDislikedFood} className="h-12 rounded-xl px-4">
                      Tambah
                    </Button>
                  </div>

                  {dislikedFoods.length > 0 ? (
                    <div className="flex flex-wrap gap-2 rounded-2xl border border-line bg-sunken p-4">
                      {dislikedFoods.map((item) => (
                        <span key={item} className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1.5 text-xs font-semibold text-amber-900 ring-1 ring-inset ring-amber-200">
                          {item}
                          <button type="button" onClick={() => removeDislikedFood(item)} aria-label={`Hapus ${item}`}>
                            <X className="size-3.5" />
                          </button>
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 rounded-2xl border border-dashed border-line-strong bg-sunken p-5 text-sm text-muted-text">
                      <CircleHelp className="size-4 shrink-0" /> Belum ada yang dihindari — kamu bisa langsung lanjut.
                    </div>
                  )}
                </section>
              )}

              {step === stepOffset + 2 && (
                <section className="space-y-4">
                  <div>
                    <p className="text-lg font-bold text-ink">Kamu butuh fokus apa?</p>
                    <p className="mt-1 text-sm text-muted-text">
                      Pilih tujuan utama supaya rekomendasi menu terasa lebih relevan. Kamu bisa mengubahnya kapan saja.
                    </p>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    {GOALS.map((goal) => {
                      const selected = nutritionGoal === goal.value
                      return (
                        <button
                          type="button"
                          key={goal.value}
                          onClick={() => setNutritionGoal(goal.value)}
                          className={`rounded-2xl border p-4 text-left transition-all ${
                            selected
                              ? 'border-forest-900 bg-forest-50 shadow-sm ring-2 ring-forest-900/10'
                              : 'border-line bg-surface hover:border-forest-300 hover:bg-forest-50/50'
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <span className="text-sm font-bold text-ink">{goal.label}</span>
                            <span className={`flex size-5 items-center justify-center rounded-full border ${selected ? 'border-forest-900 bg-forest-900 text-white' : 'border-line-strong text-transparent'}`}>
                              <Check className="size-3" />
                            </span>
                          </div>
                          <p className="mt-2 text-xs leading-relaxed text-muted-text">{goal.description}</p>
                        </button>
                      )
                    })}
                  </div>
                </section>
              )}

              {error && (
                <div className="rounded-2xl border border-blocked-line bg-blocked-soft px-4 py-3 text-sm text-blocked-strong">
                  {error}
                </div>
              )}
            </>
          )}
        </div>

        {!loading && !loadError && (
          <div className="sticky bottom-0 flex items-center justify-between gap-3 border-t border-line bg-surface/95 px-5 py-4 backdrop-blur-md sm:px-7">
            <Button
              type="button"
              variant="ghost"
              onClick={() => (step > 0 ? setStep((current) => current - 1) : onOpenChange(false))}
              disabled={saving}
              className="rounded-xl text-muted-text"
            >
              {step > 0 ? <ArrowLeft className="mr-2 size-4" /> : <X className="mr-2 size-4" />}
              {step > 0 ? 'Kembali' : 'Nanti saja'}
            </Button>

            {needsName && step === 0 ? (
              <Button type="button" onClick={() => void saveNameAndContinue()} disabled={savingName} className="rounded-xl bg-forest-900 px-5 text-white hover:bg-forest-800">
                {savingName ? <Loader2 className="mr-2 size-4 animate-spin" /> : <ArrowRight className="mr-2 size-4" />}
                Lanjut
              </Button>
            ) : isLastStep ? (
              <Button type="button" onClick={save} disabled={saving} className="rounded-xl bg-forest-900 px-5 text-white hover:bg-forest-800">
                {saving ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Check className="mr-2 size-4" />}
                Simpan profil
              </Button>
            ) : (
              <Button type="button" onClick={() => setStep((current) => current + 1)} className="rounded-xl bg-forest-900 px-5 text-white hover:bg-forest-800">
                Lanjut <ArrowRight className="ml-2 size-4" />
              </Button>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}
