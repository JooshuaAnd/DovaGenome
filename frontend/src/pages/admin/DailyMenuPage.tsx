import { useEffect, useState } from 'react'
import { CalendarDays, ChefHat, Eye, EyeOff, FileUp, ImagePlus, Loader2, Paperclip, Plus, Send, Sparkles, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { PageState } from '@/components/common/PageState'
import { PageHeader } from '@/components/layout/PageHeader'
import { SafetyBadge } from '@/components/safety/SafetyBadge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { useAsync } from '@/hooks/useAsync'
import { useApi } from '@/hooks/useApi'
import { DAY_SHORT } from '@/lib/constants'
import { cn } from '@/lib/utils'
import { adminService, type ProductionBatch, type RecipeIntakeResult } from '@/services/admin'
import { catalogService } from '@/services/catalog'
import { getErrorMessage } from '@/services/http'
import { DEFAULT_FOOD_IMAGE, MENU_IMAGES } from '@/lib/menuImages'
import type { Menu, ServiceDay, ServiceWeek } from '@/types'

const DAYS: ServiceDay[] = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu']

export function DailyMenuPage() {
  const { data: weekData, loading: weekLoading, error: weekError, refetch } = useApi<ServiceWeek>(
    (signal) => adminService.getAdminServiceWeek(signal),
  )
  const days = weekData?.days ?? []
  const [selectedDay, setSelectedDay] = useState<ServiceDay>('Senin')
  const [chatOpen, setChatOpen] = useState(true)
  const [chatText, setChatText] = useState('')
  const [chatFile, setChatFile] = useState<File | null>(null)
  const [chatBusy, setChatBusy] = useState(false)
  const [chatResult, setChatResult] = useState<RecipeIntakeResult | null>(null)
  const [batchByDate, setBatchByDate] = useState<Record<string, ProductionBatch[]>>({})
  const toggle = useAsync((menuId: string, published: boolean) => catalogService.setMenuPublished(menuId, published))
  const selected = days.find((day) => day.hari === selectedDay)
  const totalOptions = days.reduce((sum, day) => sum + day.options.length, 0)

  useEffect(() => {
    if (days.length && !days.some((day) => day.hari === selectedDay)) setSelectedDay(days[0].hari)
  }, [days, selectedDay])

  useEffect(() => {
    if (!days.length) return
    let active = true
    void Promise.all(days.map(async (day) => {
      try {
        const result = await adminService.getProductionBatches(day.service_date)
        return [day.service_date, result.items ?? []] as const
      } catch {
        return [day.service_date, []] as const
      }
    })).then((entries) => {
      if (active) setBatchByDate(Object.fromEntries(entries))
    })
    return () => { active = false }
  }, [days])

  const handleToggle = async (menu: Menu) => {
    const result = await toggle.run(menu.menu_id, !menu.published)
    if (result) {
      toast.success(result.published ? 'Menu aktif di katalog' : 'Menu dinonaktifkan dari katalog', {
        description: `${result.nama_menu} · ${DAY_SHORT[result.hari]}`,
      })
      refetch()
    }
  }

  const sendRecipe = async () => {
    if (!chatFile && !chatText.trim()) {
      toast.error('Kirim catatan resep atau lampirkan file/foto dulu.')
      return
    }
    setChatBusy(true)
    setChatResult(null)
    try {
      const mentionedDay = chatText.match(/\b(senin|selasa|rabu|kamis|jumat|sabtu)\b/i)?.[1]
      const serviceDay = DAYS.find((day) => day.toLowerCase() === mentionedDay?.toLowerCase()) ?? selectedDay
      const result = await adminService.intakeRecipe(
        chatFile,
        serviceDay,
        '',
        chatFile ? chatText.trim() : '',
        chatFile ? '' : chatText.trim(),
      )
      setChatResult(result)
      setChatText('')
      setChatFile(null)
      toast.success('Draft menu dibuat untuk ditinjau.')
      refetch()
    } catch (error) {
      toast.error('Chef BOB belum dapat membuat draft.', { description: getErrorMessage(error) })
    } finally {
      setChatBusy(false)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Administrasi · kalender produksi"
        title="Menu mingguan"
        description="Pilih tanggal untuk melihat menu, status katalog, dan batch produksi. Susun menu baru lewat chat Chef BOB."
        actions={<Button asChild variant="outline"><Link to="/admin/menu-demand"><Sparkles className="size-4" /> Rekomendasi demand</Link></Button>}
      />

      <PageState loading={weekLoading} error={weekError} skeletonRows={3} onRetry={refetch}>
        <section className="overflow-hidden rounded-3xl border border-[#eadbd3] bg-white shadow-sm">
          <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[#f0e7e1] bg-[#fffaf6] px-5 py-4">
            <div><p className="flex items-center gap-2 font-display text-lg font-bold text-ink"><CalendarDays className="size-5 text-[#922638]" /> Kalender menu</p><p className="mt-1 text-sm text-muted-text">{totalOptions} menu · minggu {weekData?.week_start ?? ''}</p></div>
            <Link to="/admin/production" className="inline-flex items-center gap-2 rounded-full border border-[#eadbd3] bg-white px-4 py-2 text-sm font-semibold text-[#762032] hover:bg-[#fff2ed]"><ChefHat className="size-4" /> Lihat batch produksi</Link>
          </header>
          <div className="grid grid-cols-2 gap-2 p-4 sm:grid-cols-3 lg:grid-cols-6">
            {DAYS.map((dayName) => {
              const day = days.find((entry) => entry.hari === dayName)
              const batches = day ? batchByDate[day.service_date] ?? [] : []
              const active = selectedDay === dayName
              return <button key={dayName} type="button" onClick={() => { setSelectedDay(dayName); setChatResult(null) }} aria-pressed={active} className={cn('rounded-2xl border p-3 text-left transition-all', active ? 'border-[#842033] bg-[#842033] text-white shadow-md shadow-[#842033]/15' : 'border-[#eee4de] bg-white text-ink hover:border-[#d5aab0] hover:bg-[#fff8f5]')}>
                <span className="block text-sm font-bold">{dayName}</span>
                <span className={cn('mt-1 block text-xs', active ? 'text-white/75' : 'text-muted-text')}>{day?.date_label ?? '—'}</span>
                <span className={cn('mt-2 flex items-center justify-between text-[11px]', active ? 'text-white/85' : 'text-muted-text')}><span>{day?.options.length ?? 0} menu</span>{batches.length > 0 && <span className="rounded-full bg-emerald-100 px-2 py-0.5 font-bold text-emerald-800">{batches.length} batch</span>}</span>
              </button>
            })}
          </div>
        </section>

        <Card className="gap-0 overflow-hidden border-[#eadbd3] p-0 shadow-sm">
          <button type="button" onClick={() => setChatOpen((value) => !value)} className="flex w-full items-center justify-between gap-3 bg-gradient-to-r from-[#761b2b] via-[#972b3b] to-[#be503f] px-5 py-4 text-left text-white">
            <span className="flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl bg-white/15"><ChefHat className="size-5" /></span><span><strong className="block">Tambah menu lewat chat Chef BOB</strong><span className="text-xs text-white/75">Kirim catatan, PDF, Excel, atau foto resep · hari terpilih: {selectedDay}</span></span></span>
            {chatOpen ? <X className="size-5" /> : <Plus className="size-5" />}
          </button>
          {chatOpen && <div className="bg-[#fbf8f5] p-4 sm:p-5">
            <div className="mx-auto max-w-4xl space-y-3">
              <div className="flex gap-2"><span className="grid size-8 shrink-0 place-items-center rounded-full bg-[#842033] text-white"><Sparkles className="size-4" /></span><div className="max-w-2xl rounded-2xl rounded-tl-sm border border-[#eadbd3] bg-white px-4 py-3 text-sm text-stone-700">Halo Chef! Kirim resep dalam bentuk catatan atau lampirkan PDF, spreadsheet, dan foto. Aku akan menyusun nama menu, bahan, takaran, dan estimasi gizi. Draft akan masuk kalender sebagai belum dipublikasikan sampai tim memverifikasinya.</div></div>
              {chatFile && <div className="ml-10 flex w-fit items-center gap-2 rounded-full border border-[#eadbd3] bg-white px-3 py-2 text-xs"><Paperclip className="size-3.5 text-[#842033]" />{chatFile.name}<button type="button" onClick={() => setChatFile(null)} aria-label="Hapus lampiran"><X className="size-3.5" /></button></div>}
              {chatResult && <div className="flex gap-2"><span className="grid size-8 shrink-0 place-items-center rounded-full bg-[#842033] text-white"><Sparkles className="size-4" /></span><div className="max-w-3xl space-y-2 rounded-2xl rounded-tl-sm border border-emerald-200 bg-white px-4 py-3 text-sm text-stone-700"><p className="font-bold text-ink">Draft dibuat: {chatResult.menu_name} · {chatResult.service_day}</p><p>Estimasi AI per porsi: {chatResult.ai_draft.nutrition.calories_kcal ?? '—'} kcal · protein {chatResult.ai_draft.nutrition.protein_g ?? '—'} g · karbo {chatResult.ai_draft.nutrition.carbs_g ?? '—'} g · lemak {chatResult.ai_draft.nutrition.fat_g ?? '—'} g.</p><p className="text-xs text-muted-text">{chatResult.ai_draft.components.map((item) => `${item.ingredient_name} ${item.quantity} ${item.unit}`).join(' · ')}</p><Badge variant="outline" className="border-amber-200 text-amber-800">Belum dipublikasikan · menunggu verifikasi resep</Badge><p className="text-xs text-muted-text">Gizi berbasis komposisi bahan: {chatResult.nutrition_from_composition.status}. Estimasi AI belum menjadi hasil terverifikasi.</p></div></div>}
              <div className="flex items-end gap-2 rounded-2xl border border-[#e6d9d2] bg-white p-2 shadow-sm">
                <label className="grid size-10 shrink-0 cursor-pointer place-items-center rounded-xl text-[#842033] hover:bg-[#fff2ed]" title="Lampirkan resep"><input className="sr-only" type="file" accept="image/jpeg,image/png,image/webp,.pdf,.xlsx,.csv,.txt,.md" onChange={(event) => setChatFile(event.target.files?.[0] ?? null)} /><FileUp className="size-5" /></label>
                <textarea value={chatText} onChange={(event) => setChatText(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void sendRecipe() } }} rows={2} placeholder="Tulis catatan resep atau jelaskan menunya…" className="max-h-32 min-h-10 flex-1 resize-y border-0 bg-transparent px-2 py-2 text-sm outline-none placeholder:text-stone-400" />
                <Button onClick={() => void sendRecipe()} disabled={chatBusy || (!chatFile && !chatText.trim())} className="size-10 shrink-0 rounded-xl bg-[#842033] p-0 text-white hover:bg-[#671526]">{chatBusy ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}<span className="sr-only">Kirim resep</span></Button>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2 pl-10 text-xs text-muted-text"><span>Chat ini membuat draft; verifikasi alergi, gramasi, dan keamanan tetap dilakukan admin.</span><Link to={`/admin/daily-menu/${encodeURIComponent(selectedDay)}`} className="underline decoration-[#c98b83] underline-offset-2">Isi menu manual</Link></div>
            </div>
          </div>}
        </Card>

        {toggle.error && <Card className="border-l-4 border-l-blocked-strong text-sm">{getErrorMessage(toggle.error)}</Card>}

        {selected && <section className="space-y-4">
          <header className="flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-[0.16em] text-[#a23a3f]">{selectedDay} · {selected.date_label}</p><h2 className="mt-1 font-display text-2xl font-bold text-ink">Menu hari {selectedDay}</h2></div><div className="flex flex-wrap gap-2">{(batchByDate[selected.service_date] ?? []).map((batch) => <span key={batch.batch_id} className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-800">Batch {batch.status} · {batch.planned_portions} porsi</span>)}<Button asChild size="sm" variant="outline"><Link to={`/admin/production?date=${encodeURIComponent(selected.service_date)}`}><ChefHat className="size-4" /> Lihat / rencanakan batch</Link></Button><Button asChild size="sm" variant="outline"><Link to={`/admin/daily-menu/${encodeURIComponent(selectedDay)}`}><Plus className="size-4" /> Tambah manual</Link></Button></div></header>
          {selected.options.length === 0 ? <Card className="grid min-h-48 place-items-center border-dashed bg-white text-center text-muted-text"><div><ImagePlus className="mx-auto size-8 text-[#b66a6b]" /><p className="mt-3 font-semibold text-ink">Belum ada menu untuk hari ini</p><p className="mt-1 text-sm">Pakai chat Chef BOB untuk mengirim resep atau catatan.</p></div></Card> : <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{selected.options.map((menu, index) => {
            const verdict = selected.safety.find((entry) => entry.menu_id === menu.menu_id)
            return <article key={menu.menu_id} className={cn('overflow-hidden rounded-3xl border bg-white shadow-sm transition-shadow hover:shadow-md', !menu.published && 'border-dashed opacity-80')}>
              <div className="relative h-44 overflow-hidden bg-[#f4e8e2]"><img src={MENU_IMAGES[menu.menu_id] || MENU_IMAGES[menu.nama_menu] || DEFAULT_FOOD_IMAGE} alt={menu.nama_menu} className="size-full object-cover" loading="lazy"/><span className="absolute left-3 top-3 rounded-full bg-white/95 px-3 py-1 text-[11px] font-bold uppercase tracking-wide text-[#842033]">{DAY_SHORT[selectedDay]} · Pilihan {index + 1}</span><span className="absolute right-3 top-3"><Badge variant="outline" className={menu.published ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-amber-200 bg-amber-50 text-amber-800'}>{menu.published ? 'Tayang' : 'Draft'}</Badge></span></div>
              <div className="space-y-3 p-4"><div className="flex flex-wrap items-center gap-2"><h3 className="font-display text-lg font-bold leading-snug text-ink">{menu.nama_menu}</h3>{verdict && <SafetyBadge level={verdict.level} size="sm" />}</div>{menu.deskripsi && <p className="line-clamp-2 text-sm leading-relaxed text-muted-text">{menu.deskripsi}</p>}<p className="text-xs text-muted-text">Paket: {menu.package_codes.length ? menu.package_codes.join(', ') : 'semua paket'}</p>{menu.recipe_verification_status && <p className="text-xs text-amber-800">Resep: {menu.recipe_verification_status === 'VERIFIED' ? 'terverifikasi' : 'perlu verifikasi'}</p>}
                <div className="flex gap-2 border-t border-[#f0e7e1] pt-3"><Button size="sm" variant="outline" className="flex-1" disabled={toggle.pending} onClick={() => void handleToggle(menu)}>{toggle.pending ? <Loader2 className="size-4 animate-spin" /> : menu.published ? <EyeOff className="size-4" /> : <Eye className="size-4" />}{menu.published ? 'Nonaktifkan' : 'Aktifkan'}</Button><Button asChild size="sm" className="flex-1 bg-[#842033] text-white hover:bg-[#671526]"><Link to={`/admin/daily-menu/${encodeURIComponent(selectedDay)}/${encodeURIComponent(menu.menu_id)}`}>Ubah detail</Link></Button></div>
              </div>
            </article>
          })}</div>}
        </section>}
      </PageState>
    </div>
  )
}
