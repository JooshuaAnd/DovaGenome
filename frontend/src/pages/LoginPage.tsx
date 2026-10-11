import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import {
  ArrowRight,
  CheckCircle2,
  Lock,
  Phone,
  ShieldCheck,
  Sparkles,
  User,
  UtensilsCrossed,
  X,
} from 'lucide-react'

import { Brand } from '@/components/layout/Sidebar'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/hooks/useAuth'
import { useAsync } from '@/hooks/useAsync'
import { ApiError } from '@/services/http'
import { BRAND } from '@/lib/constants'

type SubmitValues =
  | { mode: 'customer'; displayName: string; phone: string }
  | { mode: 'staff'; username: string; password: string }

const CURRENT_YEAR = new Date().getFullYear()

export function LoginPage() {
  const { isAuthenticated, signInCustomer, login, error: authError, clearError } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const [phone, setPhone] = useState('')
  const [displayName, setDisplayName] = useState('')

  // Staff secret modal state
  const [showStaffModal, setShowStaffModal] = useState(false)
  const [staffRole, setStaffRole] = useState<'admin' | 'kitchen'>('admin')
  const [staffUsername, setStaffUsername] = useState('admin')
  const [staffPassword, setStaffPassword] = useState('')

  const next = searchParams.get('next')

  const submit = useAsync(async (values: SubmitValues) => {
    if (values.mode === 'customer') {
      const name = values.displayName.trim() || `Pelanggan (${values.phone.slice(-4)})`
      return signInCustomer({ display_name: name, phone: values.phone })
    }
    return login({ username: values.username, password: values.password || null })
  })

  useEffect(() => {
    if (isAuthenticated) {
      if (next) {
        navigate(next, { replace: true })
      } else {
        // Customer default to /order, staff default to /orders
        navigate('/order', { replace: true })
      }
    }
  }, [isAuthenticated, navigate, next])

  if (isAuthenticated) return <Navigate to={next || '/order'} replace />

  async function handleCustomerSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    clearError()
    const cleanPhone = phone.trim()
    if (!cleanPhone) return

    await submit.run({
      mode: 'customer',
      displayName: displayName.trim(),
      phone: cleanPhone,
    })
  }

  async function handleStaffSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    clearError()
    await submit.run({
      mode: 'staff',
      username: staffUsername.trim(),
      password: staffPassword,
    })
  }

  const activeError = submit.error ?? authError
  const fieldErrors = activeError instanceof ApiError ? activeError.fieldMessages : []

  return (
    <div className="relative grid min-h-dvh bg-canvas lg:grid-cols-[1.1fr_1fr]">
      {/* ── Brand & Trust Panel (Left) ───────────────────────────────── */}
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-forest-950 via-forest-900 to-forest-800 p-12 text-white lg:flex">
        {/* Subtle Luxury Pattern Overlay */}
        <div className="pointer-events-none absolute inset-0 opacity-10 bg-[radial-gradient(#b8893a_1px,transparent_1px)] [background-size:24px_24px]" />

        <div className="relative z-10">
          <Brand size="lg" />
        </div>

        <div className="relative z-10 max-w-lg">
          <div className="inline-flex items-center gap-2 rounded-full border border-gold-500/30 bg-gold-500/10 px-3.5 py-1 text-xs font-semibold tracking-wider text-gold-200 uppercase">
            <Sparkles className="size-3.5 text-gold-400" />
            <span>Katering Presisi Modern</span>
          </div>

          <h1 className="mt-5 font-display text-4xl leading-[1.15] font-bold text-white xl:text-5xl">
            Makan siang harian yang aman & tepat untuk tubuhmu.
          </h1>

          <p className="mt-4 text-base leading-relaxed text-slate-300">
            Dova Kitchen menguji setiap resep terhadap riwayat alergimu. Cukup masukkan nomor
            telepon, langsung pesan tanpa ribet mengingat kata sandi.
          </p>

          <div className="mt-8 space-y-3.5 rounded-2xl border border-white/10 bg-white/5 p-5 backdrop-blur-md">
            {[
              'Verifikasi alergen otomatis sebelum pesanan masuk dapur',
              'Satu nomor telepon untuk simpan riwayat & alamat pengiriman',
              'Transparansi bahan baku dan jam pemrosesan real-time (WIB)',
            ].map((text) => (
              <div key={text} className="flex items-start gap-3 text-sm text-slate-200">
                <CheckCircle2 className="mt-0.5 size-4.5 shrink-0 text-emerald-400" />
                <span>{text}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="relative z-10 flex items-center justify-between text-xs text-slate-400">
          <p>© {CURRENT_YEAR} {BRAND.name}. Hak cipta dilindungi.</p>
          <span className="flex items-center gap-1.5 text-slate-400">
            <ShieldCheck className="size-4 text-emerald-400" />
            Keamanan Pangan Terstandarisasi
          </span>
        </div>
      </aside>

      {/* ── Main Customer Login Panel (Right) ────────────────────────── */}
      <div className="flex flex-col justify-between px-6 py-10 sm:px-12 lg:px-16">
        <div className="lg:hidden">
          <Brand size="md" asLink />
        </div>

        <div className="mx-auto my-auto w-full max-w-md">
          {/* Header */}
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-lg bg-forest-50 px-3 py-1 text-xs font-semibold text-forest-700">
              <UtensilsCrossed className="size-3.5" />
              <span>Portal Pelanggan</span>
            </div>
            <h2 className="font-display text-3xl font-bold tracking-tight text-ink">
              Masuk & Mulai Pesan
            </h2>
            <p className="text-sm leading-relaxed text-muted-text">
              Gunakan nomor WhatsApp/HP aktif. Profil alergi dan alamatmu akan otomatis tersambung.
            </p>
          </div>

          {/* Form Utama Pelanggan */}
          <form onSubmit={handleCustomerSubmit} className="mt-8 space-y-5" noValidate>
            {/* Input Phone */}
            <div className="space-y-1.5">
              <Label htmlFor="customer-phone" className="text-xs font-semibold uppercase tracking-wider text-ink-soft">
                Nomor Telepon / WhatsApp <span className="text-rose-600">*</span>
              </Label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-muted-text">
                  <Phone className="size-4 text-forest-600" />
                </div>
                <Input
                  id="customer-phone"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="081234567890"
                  autoComplete="tel"
                  required
                  className="h-12 rounded-xl pl-10 text-base shadow-sm border-line hover:border-forest-600 focus:border-forest-700 focus:ring-forest-700/20"
                />
              </div>
              <p className="text-[0.8125rem] text-muted-text">
                Contoh: <span className="font-mono text-ink">081234567890</span> atau <span className="font-mono text-ink">+62812...</span>
              </p>
            </div>

            {/* Input Nama Lengkap (Opsional / Akun Baru) */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="customer-name" className="text-xs font-semibold uppercase tracking-wider text-ink-soft">
                  Nama Lengkap
                </Label>
                <span className="text-[0.6875rem] text-muted-text">Diperlukan untuk pesanan baru</span>
              </div>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-muted-text">
                  <User className="size-4 text-muted-text" />
                </div>
                <Input
                  id="customer-name"
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="contoh: Maya Indriani"
                  autoComplete="name"
                  className="h-12 rounded-xl pl-10 text-base shadow-sm border-line hover:border-forest-600 focus:border-forest-700 focus:ring-forest-700/20"
                />
              </div>
            </div>

            {activeError && !showStaffModal && (
              <FormError message={activeError.message} fields={fieldErrors} />
            )}

            <Button
              type="submit"
              disabled={submit.pending || !phone.trim()}
              className="group h-12 w-full rounded-xl bg-forest-900 text-base font-semibold text-white shadow-md transition-all hover:bg-forest-800 hover:shadow-lg disabled:opacity-50"
            >
              <span>{submit.pending ? 'Memverifikasi akun…' : 'Masuk Sekarang'}</span>
              <ArrowRight className="ml-2 size-4.5 transition-transform group-hover:translate-x-1" />
            </Button>
          </form>

          {/* Quick info footer */}
          <div className="mt-8 rounded-xl bg-sunken border border-line p-4 text-xs text-muted-text">
            <p className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-emerald-600 shrink-0" />
              <span>
                Belum pernah mendaftar? Cukup isi nomor telepon dan nama Anda di atas, akun langsung dibuat seketika.
              </span>
            </p>
          </div>

          {/* Staff Secret Portal Trigger */}
          <div className="mt-8 pt-6 border-t border-line/60 text-center">
            <button
              type="button"
              onClick={() => {
                clearError()
                setShowStaffModal(true)
              }}
              className="inline-flex items-center gap-1.5 text-xs text-muted-text hover:text-forest-900 transition-colors"
            >
              <Lock className="size-3.5 text-muted-text" />
              <span>Akses Khusus Staf & Tim Dapur</span>
            </button>
          </div>
        </div>

        <div className="mt-6 text-center text-xs text-muted-text">
          <Link to="/" className="font-medium text-forest-700 hover:underline">
            ← Kembali ke Beranda Utama
          </Link>
        </div>
      </div>

      {/* ── Modal Dialog: Secret Staff / Admin Access ────────────────── */}
      {showStaffModal && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-forest-950/60 p-4 backdrop-blur-sm animate-fade-in"
        >
          <div className="relative w-full max-w-md rounded-2xl bg-surface p-6 shadow-2xl border border-line animate-rise-in">
            <button
              type="button"
              onClick={() => {
                setShowStaffModal(false)
                clearError()
              }}
              className="absolute right-4 top-4 rounded-lg p-1.5 text-muted-text hover:bg-muted hover:text-ink transition-colors"
              aria-label="Tutup"
            >
              <X className="size-5" />
            </button>

            <div className="flex items-center gap-3">
              <div className="flex size-10 items-center justify-center rounded-xl bg-forest-900 text-gold-400">
                <Lock className="size-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-ink">Portal Staf Internal</h3>
                <p className="text-xs text-muted-text">Masukkan kode/kredensial admin atau dapur</p>
              </div>
            </div>

            <form onSubmit={handleStaffSubmit} className="mt-6 space-y-4">
              {/* Quick Preset Selector for Staff */}
              <div className="flex rounded-lg border border-line bg-muted/50 p-1 text-xs">
                <button
                  type="button"
                  onClick={() => {
                    setStaffRole('admin')
                    setStaffUsername('admin')
                  }}
                  className={`flex-1 rounded-md py-1.5 font-medium transition-colors ${
                    staffRole === 'admin'
                      ? 'bg-surface font-semibold text-forest-900 shadow-sm'
                      : 'text-muted-text hover:text-ink'
                  }`}
                >
                  Admin / Manajer
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setStaffRole('kitchen')
                    setStaffUsername('dapur')
                  }}
                  className={`flex-1 rounded-md py-1.5 font-medium transition-colors ${
                    staffRole === 'kitchen'
                      ? 'bg-surface font-semibold text-forest-900 shadow-sm'
                      : 'text-muted-text hover:text-ink'
                  }`}
                >
                  Tim Dapur (Katering)
                </button>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="staff-username" className="text-xs font-semibold">
                  Username Staf
                </Label>
                <Input
                  id="staff-username"
                  type="text"
                  value={staffUsername}
                  onChange={(e) => setStaffUsername(e.target.value)}
                  placeholder="admin atau dapur"
                  required
                  className="h-10 rounded-lg text-sm"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="staff-password" className="text-xs font-semibold">
                  Kode Sandi / Password
                </Label>
                <Input
                  id="staff-password"
                  type="password"
                  value={staffPassword}
                  onChange={(e) => setStaffPassword(e.target.value)}
                  placeholder="Masukkan kata sandi staf"
                  required
                  autoFocus
                  className="h-10 rounded-lg text-sm"
                />
              </div>

              {activeError && (
                <FormError message={activeError.message} fields={fieldErrors} />
              )}

              <div className="mt-6 flex items-center justify-end gap-2.5 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setShowStaffModal(false)
                    clearError()
                  }}
                  className="rounded-lg text-xs"
                >
                  Batal
                </Button>
                <Button
                  type="submit"
                  disabled={submit.pending || !staffPassword}
                  className="rounded-lg bg-forest-900 text-xs text-white hover:bg-forest-800"
                >
                  {submit.pending ? 'Memverifikasi…' : 'Otorisasi & Masuk'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

function FormError({ message, fields }: { message: string; fields: string[] }) {
  return (
    <Alert variant="destructive" className="rounded-xl border-rose-200 bg-rose-50 text-rose-900">
      <AlertTitle className="text-sm font-semibold">Gagal memproses</AlertTitle>
      <AlertDescription className="text-xs">
        <p>{message}</p>
        {fields.length > 0 && (
          <ul className="mt-1 list-inside list-disc">
            {fields.map((field) => (
              <li key={field}>{field}</li>
            ))}
          </ul>
        )}
      </AlertDescription>
    </Alert>
  )
}
