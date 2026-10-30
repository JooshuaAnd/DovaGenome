import { useEffect, useState } from 'react'
import { ArrowRight, CalendarDays, RefreshCw, TrendingUp } from 'lucide-react'
import { Link } from 'react-router-dom'

import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { adminService } from '@/services/admin'
import { getErrorMessage } from '@/services/http'

type DemandData = Awaited<ReturnType<typeof adminService.getForecastBacktest>>

export function MenuDemandPage() {
  const [data, setData] = useState<DemandData | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const report = await adminService.getForecastBacktest({ horizonDays: 7, mode: 'live' })
      setData(report)
    } catch (cause) {
      setData(null)
      setError(getErrorMessage(cause, 'Data demand belum dapat dimuat.'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { void load() }, [])

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Perencanaan katalog"
        title="Menu & rekomendasi harian"
        description="Gunakan menu yang paling diminati pada hari layanan yang sama sebagai acuan saat menambah pilihan baru."
        actions={<Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCw className={loading ? 'size-4 animate-spin' : 'size-4'} /> Perbarui demand</Button>}
      />

      <Card className="flex flex-wrap items-start justify-between gap-4 border-[#ead2c8] bg-[#fffaf6] p-5">
        <div className="flex gap-3">
          <span className="grid size-11 place-items-center rounded-2xl bg-[#8f1d2c] text-white"><TrendingUp className="size-5" /></span>
          <div>
            <p className="font-bold text-ink">Acuan dari riwayat demand per hari</p>
            <p className="mt-1 max-w-2xl text-sm text-muted-text">Peringkat membandingkan menu pada hari layanan yang sama. Data aktual yang stale tetap hanya menjadi konteks historis, bukan instruksi produksi.</p>
          </div>
        </div>
        <p className="text-xs text-muted-text">Sumber: {data?.source ?? 'menunggu data'} · Observasi terakhir: {data?.latest_observation_date ?? '—'}</p>
      </Card>

      {error && <Card className="border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">Demand belum dapat dimuat: {error}</Card>}
      {loading && <Card className="p-6 text-sm text-muted-text">Memuat rekomendasi dari histori pesanan…</Card>}
      {!loading && data && (data.weekday_demand_summary ?? []).length === 0 && (
        <Card className="p-6 text-sm text-muted-text">Belum ada riwayat demand yang cukup untuk menyusun rekomendasi harian.</Card>
      )}

      {!loading && (data?.weekday_demand_summary ?? []).length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data!.weekday_demand_summary!.map((day) => (
            <Card key={`${day.weekday}-${day.unit}`} className="gap-0 overflow-hidden p-0">
              <div className="flex items-center justify-between border-b border-line bg-white px-5 py-4">
                <div className="flex items-center gap-2"><CalendarDays className="size-4 text-[#8f1d2c]" /><h2 className="font-bold text-ink">{day.weekday}</h2></div>
                <span className="text-xs text-muted-text">rata-rata / hari · {day.unit}</span>
              </div>
              <ol className="space-y-3 px-5 py-4">
                {day.menus.slice(0, 5).map((menu, index) => (
                  <li key={menu.series_key} className="flex items-start gap-3">
                    <span className="grid size-7 shrink-0 place-items-center rounded-full bg-[#f8e9e4] text-xs font-bold text-[#8f1d2c]">{index + 1}</span>
                    <div className="min-w-0 flex-1"><p className="font-semibold text-ink">{menu.label}</p><p className="mt-0.5 text-xs text-muted-text">{menu.average_quantity.toFixed(1)} {day.unit} · {menu.observed_days} hari observasi</p></div>
                  </li>
                ))}
                {!day.menus.length && <li className="text-sm text-muted-text">Belum ada menu dengan demand tercatat.</li>}
              </ol>
              <div className="border-t border-line p-4">
                <Button asChild variant="outline" className="w-full justify-between">
                  <Link to={`/admin/daily-menu/${encodeURIComponent(day.weekday)}`}><span>Tambah menu hari {day.weekday}</span><ArrowRight className="size-4" /></Link>
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
