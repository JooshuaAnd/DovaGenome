import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { KeyRound, LogIn, ShieldCheck, UserPlus } from 'lucide-react'

import { Brand } from '@/components/layout/Sidebar'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useAuth } from '@/hooks/useAuth'
import { useAsync } from '@/hooks/useAsync'
import { ApiError } from '@/services/http'
import { BRAND } from '@/lib/constants'

/** Shared shape for both auth tabs so one runner can serve either flow. */
interface AuthFormValues {
  username: string
  password?: string
  displayName?: string
}

/** Evaluated once per load — never recomputed during render. */
const CURRENT_YEAR = new Date().getFullYear()

/**
 * Sign-in and registration.
 *
 * The backend runs a passwordless MVP for customers and a password-gated login
 * for staff, so the password field is presented as staff-only and stays optional
 * on the customer tab — see `app/api/routers/auth.py`.
 */
export function LoginPage() {
  const { isAuthenticated, login, register } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const next = searchParams.get('next') || '/orders'

  const [tab, setTab] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')

  const submit = useAsync(async (values: AuthFormValues) => {
    if (tab === 'login') {
      return login({ username: values.username, password: values.password || null })
    }
    return register({ username: values.username, display_name: values.displayName ?? '' })
  })

  // Navigate only after a successful authentication.
  useEffect(() => {
    if (isAuthenticated) navigate(next, { replace: true })
  }, [isAuthenticated, navigate, next])

  if (isAuthenticated) return <Navigate to={next} replace />

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (tab === 'login') {
      await submit.run({ username: username.trim(), password })
    } else {
      await submit.run({ username: username.trim(), displayName: displayName.trim() })
    }
  }

  const fieldErrors = submit.error instanceof ApiError ? submit.error.fieldMessages : []

  return (
    <div className="grid min-h-dvh lg:grid-cols-[1fr_minmax(0,26rem)]">
      {/* ── Brand panel ────────────────────────────────────────────── */}
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-gradient-to-br from-forest-900 via-forest-700 to-forest-600 p-10 text-white lg:flex">
        <Brand size="md" />

        <div className="max-w-md">
          <p className="text-[0.6875rem] font-extrabold tracking-[0.18em] text-[#f6e7c6] uppercase">
            Masuk ke akun kamu
          </p>
          <h1 className="mt-4 text-4xl leading-tight text-white">{BRAND.tagline}</h1>
          <p className="mt-4 text-white/80">
            Passport dietary tersimpan di satu tempat, dan dipakai dapur setiap kali pesanan
            kamu dimasak.
          </p>

          <div className="mt-8 space-y-3">
            {[
              'Alergi dipisahkan dari preferensi',
              'Cek kecocokan menu sebelum memesan',
              'Semua waktu ditampilkan dalam WIB',
            ].map((item) => (
              <p key={item} className="flex items-start gap-2.5 text-sm text-white/85">
                <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
                {item}
              </p>
            ))}
          </div>
        </div>

        <p className="text-xs text-white/60">
          © {CURRENT_YEAR} {BRAND.name}
        </p>
      </aside>

      {/* ── Form panel ─────────────────────────────────────────────── */}
      <div className="flex flex-col justify-center px-4 py-10 sm:px-10">
        <div className="mx-auto w-full max-w-sm">
          <div className="lg:hidden">
            <Brand size="md" asLink />
          </div>

          <h2 className="mt-6 text-2xl lg:mt-0">Selamat datang kembali</h2>
          <p className="mt-1.5 text-sm text-muted-text">
            Gunakan username yang sama dengan akun Telegram kamu.
          </p>

          <Tabs
            value={tab}
            onValueChange={(value) => {
              setTab(value as 'login' | 'register')
              submit.reset()
            }}
            className="mt-6"
          >
            <TabsList className="w-full">
              <TabsTrigger value="login" className="flex-1">
                <LogIn aria-hidden="true" className="size-4" />
                Masuk
              </TabsTrigger>
              <TabsTrigger value="register" className="flex-1">
                <UserPlus aria-hidden="true" className="size-4" />
                Daftar
              </TabsTrigger>
            </TabsList>

            {/* ── Sign in ────────────────────────────────────────── */}
            <TabsContent value="login" className="mt-5">
              <form onSubmit={handleSubmit} className="space-y-4" noValidate>
                <Field
                  id="username"
                  label="Username"
                  value={username}
                  onChange={setUsername}
                  autoComplete="username"
                  placeholder="contoh: budi.santoso"
                  required
                />

                <Field
                  id="password"
                  label="Kata sandi"
                  type="password"
                  value={password}
                  onChange={setPassword}
                  autoComplete="current-password"
                  placeholder="Hanya untuk admin dan dapur"
                  hint="Pelanggan tidak memerlukan kata sandi."
                  leadingIcon={<KeyRound aria-hidden="true" className="size-4" />}
                />

                {submit.error && (
                  <FormError message={submit.error.message} fields={fieldErrors} />
                )}

                <Button type="submit" className="w-full" disabled={submit.pending}>
                  {submit.pending ? 'Memproses…' : 'Masuk'}
                </Button>
              </form>
            </TabsContent>

            {/* ── Register ───────────────────────────────────────── */}
            <TabsContent value="register" className="mt-5">
              <form onSubmit={handleSubmit} className="space-y-4" noValidate>
                <Field
                  id="register-username"
                  label="Username"
                  value={username}
                  onChange={setUsername}
                  autoComplete="username"
                  placeholder="3–32 karakter, huruf kecil"
                  hint="Huruf kecil, angka, titik, underscore, atau strip."
                  required
                />

                <Field
                  id="register-name"
                  label="Nama tampilan"
                  value={displayName}
                  onChange={setDisplayName}
                  autoComplete="name"
                  placeholder="Budi Santoso"
                />

                {submit.error && (
                  <FormError message={submit.error.message} fields={fieldErrors} />
                )}

                <Button type="submit" className="w-full" disabled={submit.pending}>
                  {submit.pending ? 'Mendaftarkan…' : 'Buat akun'}
                </Button>
              </form>
            </TabsContent>
          </Tabs>

          <p className="mt-6 text-center text-sm text-muted-text">
            <Link to="/" className="font-semibold text-forest-700 hover:underline">
              Kembali ke beranda
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

/** Inline form error: the server's own sentence plus per-field detail. */
function FormError({ message, fields }: { message: string; fields: string[] }) {
  return (
    <Alert variant="destructive">
      <AlertTitle>Gagal diproses</AlertTitle>
      <AlertDescription>
        <p>{message}</p>
        {fields.length > 0 && (
          <ul className="mt-1 list-inside list-disc text-xs">
            {fields.map((field) => (
              <li key={field}>{field}</li>
            ))}
          </ul>
        )}
      </AlertDescription>
    </Alert>
  )
}

interface FieldProps {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  type?: string
  placeholder?: string
  hint?: string
  autoComplete?: string
  required?: boolean
  leadingIcon?: React.ReactNode
}

function Field({
  id,
  label,
  value,
  onChange,
  type = 'text',
  placeholder,
  hint,
  autoComplete,
  required,
  leadingIcon,
}: FieldProps) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div className="relative">
        {leadingIcon && (
          <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-muted-text">
            {leadingIcon}
          </span>
        )}
        <Input
          id={id}
          type={type}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          autoComplete={autoComplete}
          required={required}
          className={leadingIcon ? 'pl-9' : undefined}
        />
      </div>
      {hint && <p className="text-xs text-muted-text">{hint}</p>}
    </div>
  )
}