import { useCallback, useEffect, useState } from 'react'
import { ClipboardList, RefreshCw, Scale } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { adminService, type ProductionBatch } from '@/services/admin'
import { getErrorMessage } from '@/services/http'

const today = () => new Date().toLocaleDateString('en-CA')
export function ProductionBatchesPage() {
  const [searchParams] = useSearchParams()
  const [date, setDate] = useState(() => searchParams.get('date') || today()); const [slot, setSlot] = useState<'breakfast'|'lunch'|'dinner'>('lunch')
  const [items, setItems] = useState<ProductionBatch[]>([]); const [loading, setLoading] = useState(false); const [error, setError] = useState('')
  const load = useCallback(async () => { setLoading(true); setError(''); try { const r = await adminService.getProductionBatches(date); setItems(r.items ?? []) } catch(e) { setItems([]); setError(getErrorMessage(e)) } finally { setLoading(false) } }, [date])
  useEffect(() => { void load() }, [load])
  const plan = async () => { setLoading(true); setError(''); try { await adminService.planProductionBatches({ service_date: date, meal_slot: slot }); toast.success('Perencanaan produksi dibuat dari pesanan berbayar.'); await load() } catch(e) { setError(getErrorMessage(e)) } finally { setLoading(false) } }
  const weigh = async (batch: ProductionBatch, requirementId: string, form: HTMLFormElement) => { const data = new FormData(form); const amount = Number(data.get('grams')); if (!Number.isFinite(amount) || amount <= 0) return; try { await adminService.weighProductionRequirement(batch.batch_id, { requirement_id: requirementId, actual_net_grams: amount, idempotency_key: crypto.randomUUID() }); toast.success('Hasil timbang tercatat.'); await load() } catch(e) { setError(getErrorMessage(e)) } }
  const complete = async (id: string) => { try { await adminService.completeProductionBatch(id); toast.success('Batch produksi diselesaikan.'); await load() } catch(e) { setError(getErrorMessage(e)) } }
  return <div className="space-y-6">
    <PageHeader eyebrow="Supply chain · phase 11" title="Batch produksi" description="Rencana batch berasal dari pesanan berbayar dan BOM resep. Input timbang manual dicatat ke backend." actions={<Button variant="outline" onClick={() => void load()} disabled={loading}><RefreshCw className="mr-2 size-4"/>Muat ulang</Button>}/>
    <section className="flex flex-wrap items-end gap-3 rounded-xl border bg-white p-4"><label className="grid gap-1 text-sm">Tanggal layanan<Input type="date" value={date} onChange={e=>setDate(e.target.value)}/></label><label className="grid gap-1 text-sm">Slot<select className="h-10 rounded-md border bg-white px-3" value={slot} onChange={e=>setSlot(e.target.value as typeof slot)}><option value="breakfast">Sarapan</option><option value="lunch">Siang</option><option value="dinner">Malam</option></select></label><Button onClick={()=>void plan()} disabled={loading}><ClipboardList className="mr-2 size-4"/>Buat batch dari pesanan lunas</Button><span className="text-xs text-stone-500">Timbangan otomatis belum terhubung; entri timbang dicatat manual.</span></section>
    {error && <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-900"><b>Data/aksi produksi tertahan oleh backend</b><p className="mt-1">{error}</p></div>}
    {loading ? <div className="rounded-xl border bg-white p-8 text-stone-500">Memuat batch…</div> : items.length===0 ? <div className="rounded-xl border bg-white p-10 text-center text-stone-500">Belum ada batch untuk tanggal layanan ini.</div> : <div className="grid gap-4">{items.map(b=><article key={b.batch_id} className="rounded-xl border bg-white p-5"><header className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-bold">{b.menu_name}</h2><p className="text-sm text-stone-500">{b.planned_portions} porsi · {b.site_code} · {b.batch_id}</p></div><Badge variant="outline">{b.status}</Badge></header><div className="mt-4 divide-y">{b.requirements.map(r=><div key={r.requirement_id} className="flex flex-wrap items-center justify-between gap-3 py-3"><div><p className="font-medium">{r.ingredient_name}</p><p className="text-xs text-stone-500">Rencana {r.planned_grams || r.planned_quantity} {r.planned_grams ? 'g' : r.unit} · tercatat {r.issued_grams || r.issued_quantity} · sisa {r.remaining_grams} g</p></div>{r.remaining_grams>0 && <form className="flex items-center gap-2" onSubmit={e=>{e.preventDefault();void weigh(b,r.requirement_id,e.currentTarget)}}><Scale className="size-4 text-stone-500"/><Input className="w-28" name="grams" type="number" min="0.01" step="0.01" placeholder="gram aktual" required/><Button size="sm">Catat</Button></form>}</div>)}</div><footer className="mt-3 flex justify-end">{b.status!=='COMPLETED' && <Button variant="outline" onClick={()=>void complete(b.batch_id)}>Selesaikan batch</Button>}</footer></article>)}</div>}
  </div>
}
