import { Link } from 'react-router-dom'
import {
  ArrowRight,
  ClipboardList,
  Microscope,
  ShieldCheck,
  Sparkles,
  Truck,
} from 'lucide-react'

import { Brand } from '@/components/layout/Sidebar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { useAuth } from '@/hooks/useAuth'
import { BRAND } from '@/lib/constants'

/** Value propositions — the three claims the product actually makes. */
const PILLARS = [
  {
    icon: Microscope,
    title: 'Bahan terlacak',
    description:
      'Setiap bahan dicatat dengan sumbernya, sehingga resep danvenance bisa diaudit kapan saja.',
  },
  {
    icon: ShieldCheck,
    title: 'Protokol steril',
    description:
      'Alat masak dipisahkan untuk setiap batasan kritis. Alergen bukan catatan, tapi prosedur.',
  },
  {
    icon: Truck,
    title: 'Jalur terlacak',
    description:
      'Status pesanan bergerak dari dapur sampai ke tanganmu, dengan jam yang selalu dalam WIB.',
  },
]

const STEPS = [
  { step: '01', title: 'Pilih paket', description: 'Jadwal dan hari layanan mengikuti katalog.' },
  { step: '02', title: 'Isi passport', description: 'Alergi, intoleransi, dan preferensi dipisah.' },
  { step: '03', title: 'Cek kecocokan', description: 'Menu diuji terhadap batasan sebelum dipesan.' },
  { step: '04', title: 'Dapur menjalankan', description: 'Protokol steril diterapkan per tiket.' },
]

/** Evaluated once per load — never recomputed during render. */
const CURRENT_YEAR = new Date().getFullYear()

/**
 * Public landing page.
 *
 * Content is limited to the product's real value propositions — no invented
 * statistics, testimonials, or customer counts.
 */
export function LandingPage() {
  const { isAuthenticated } = useAuth()

  return (
    <div className="min-h-dvh">
      <SiteHeader isAuthenticated={isAuthenticated} />

      <main>
        {/* ── Hero ─────────────────────────────────────────────────────── */}
        <section className="px-4 pt-10 pb-16 sm:px-6 sm:pt-16 sm:pb-20">
          <div className="mx-auto max-w-6xl">
            <div className="overflow-hidden rounded-[1.75rem] bg-gradient-to-br from-forest-900 via-forest-700 to-forest-600 px-6 py-12 text-white sm:px-12 sm:py-16">
              <Badge
                variant="outline"
                className="gap-2 border-white/25 bg-white/10 px-3 py-1 text-[0.6875rem] font-extrabold tracking-[0.18em] text-[#f6e7c6] uppercase"
              >
                <ShieldCheck aria-hidden="true" className="size-3" />
                Catering dengan pemeriksa kontaminasi
              </Badge>

              <h1 className="mt-6 max-w-18ch text-4xl leading-[1.08] text-white sm:text-5xl">
                {BRAND.tagline}
              </h1>

<p className="mt-5 max-w-2xl text-base leading-relaxed text-white/85 sm:text-lg">
              Kami memisahkan alergi, intoleransi, restriksi medis, dan preferensi — lalu
              mengujinya terhadap menu sebelum pesanan masuk ke dapur.
            </p>

              <div className="mt-8 flex flex-wrap items-center gap-3">
                <Button asChild size="lg" className="bg-white text-forest-800 hover:bg-white/90">
                  <Link to={isAuthenticated ? '/order' : '/login'}>
                    Mulai pesan
                    <ArrowRight aria-hidden="true" />
                  </Link>
                </Button>
                <Button
                  asChild
                  size="lg"
                  variant="outline"
                  className="border-white/30 bg-transparent text-white hover:bg-white/10 hover:text-white"
                >
                  <Link to="/menu">Lihat menu mingguan</Link>
                </Button>
              </div>

              <div className="mt-8 flex flex-wrap gap-2">
                {['Dietary Passport', 'Cek kecocokan per hari', 'Status real-time'].map((item) => (
                  <span
                    key={item}
                    className="rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-semibold text-white/90"
                  >
                    {item}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ── Pillars ──────────────────────────────────────────────────── */}
        <section className="px-4 pb-16 sm:px-6 sm:pb-20">
          <div className="mx-auto max-w-6xl">
            <p className="eyebrow">Kenapa DovaGenome</p>
            <h2 className="mt-2 max-w-2xl text-2xl sm:text-3xl">
              Keamanan pangan yang bisa diaudit, bukan sekadar diklaim.
            </h2>

            <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {PILLARS.map((pillar) => (
                <div key={pillar.title} className="surface-card p-6">
                  <span
                    aria-hidden="true"
                    className="flex size-11 items-center justify-center rounded-xl border border-forest-100 bg-forest-50 text-forest-600"
                  >
                    <pillar.icon className="size-5" />
                  </span>
                  <h3 className="mt-4 font-display text-base font-bold">{pillar.title}</h3>
                  <p className="mt-1.5 text-sm text-muted-text">{pillar.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── How it works ─────────────────────────────────────────────── */}
        <section
          id="alur"
          className="scroll-mt-16 border-y border-line bg-surface-sunken px-4 py-16 sm:px-6"
        >
          <div className="mx-auto max-w-6xl">
            <p className="eyebrow">Alurnya</p>
            <h2 className="mt-2 text-2xl sm:text-3xl">Empat langkah, tanpa tebak-tebakan.</h2>

            <ol className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {STEPS.map((item) => (
                <li key={item.step} className="surface-card p-5">
                  <span className="flex size-8 items-center justify-center rounded-lg bg-cream font-mono text-xs font-bold text-muted-text">
                    {item.step}
                  </span>
                  <h3 className="mt-3 text-sm font-bold">{item.title}</h3>
                  <p className="mt-1 text-sm text-muted-text">{item.description}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* ── CTA ──────────────────────────────────────────────────────── */}
        <section className="px-4 py-16 sm:px-6 sm:py-20">
          <div className="mx-auto flex max-w-6xl flex-col items-start gap-6 rounded-[1.75rem] border border-line bg-surface p-8 sm:p-10 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-xl">
              <p className="eyebrow">Langkah berikutnya</p>
              <h2 className="mt-2 text-2xl sm:text-3xl">
                Lihat menu minggu ini dan cek kecocokannya.
              </h2>
              <p className="mt-3 text-sm text-muted-text">
                Tidak perlu akun untuk melihat menu dan menjalankan pemeriksa kontaminasi.
              </p>
            </div>

            <div className="flex flex-wrap gap-3">
              <Button asChild size="lg">
                <Link to="/menu">
                  <ClipboardList aria-hidden="true" />
                  Lihat menu
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link to={isAuthenticated ? '/ai' : '/login'}>
                  <Sparkles aria-hidden="true" />
                  Tanya asisten
                </Link>
              </Button>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  )
}

/* ── Chrome ─────────────────────────────────────────────────────────────── */

function SiteHeader({ isAuthenticated }: { isAuthenticated: boolean }) {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-surface/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-4 px-4 sm:px-6">
        <Brand asLink />

        <nav className="ml-auto hidden items-center gap-6 sm:flex" aria-label="Navigasi situs">
          <Link
            to="/menu"
            className="text-sm font-semibold text-ink-soft transition-colors hover:text-forest-700"
          >
            Menu
          </Link>
          <button
            type="button"
            onClick={() =>
              document.getElementById('alur')?.scrollIntoView({ behavior: 'smooth' })
            }
            className="rounded text-sm font-semibold text-ink-soft transition-colors hover:text-forest-700"
          >
            Cara kerja
          </button>
        </nav>

        {isAuthenticated ? (
          <Button asChild size="sm" className="sm:ml-2">
            <Link to="/orders">Dashboard saya</Link>
          </Button>
        ) : (
          <Button asChild size="sm" className="sm:ml-2">
            <Link to="/login">Masuk</Link>
          </Button>
        )}
      </div>
    </header>
  )
}

function SiteFooter() {
  return (
    <footer className="border-t border-line bg-surface">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-10 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div>
          <Brand size="sm" />
          <p className="mt-3 max-w-sm text-xs text-muted-text">{BRAND.tagline}</p>
        </div>

        <Separator className="hidden sm:block sm:orientation-vertical sm:h-10" />

        <div className="text-xs text-muted-text">
          <p>Dapur presisi · Traceable · Allergen-safe</p>
          <p className="mt-1">© {CURRENT_YEAR} {BRAND.name}</p>
        </div>
      </div>
    </footer>
  )
}