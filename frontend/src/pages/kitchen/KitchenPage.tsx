import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Barcode, ChefHat, ClipboardCheck, PackageMinus, RefreshCw, ScanLine } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { kitchenService } from '@/services/kitchen'
import type { KitchenInventory, KitchenInventoryItem, ProductionBatch } from '@/services/types'

const emptyInventory: KitchenInventory = {
  items: [],
  counts: { total: 0, menipis: 0, habis: 0 },
  fetched_at: '',
}

function stockTone(status: string) {
  if (status === 'HABIS') return 'border-rose-400 bg-rose-50 text-rose-800'
  if (status === 'MENIPIS') return 'border-amber-400 bg-amber-50 text-amber-800'
  return 'border-emerald-400 bg-emerald-50 text-emerald-800'
}

/** The scale-ready station. Bluetooth later only fills the same quantity field. */
export function KitchenPage() {
  const [inventory, setInventory] = useState<KitchenInventory>(emptyInventory)
  const [selectedIngredientId, setSelectedIngredientId] = useState('')
  const [scanCode, setScanCode] = useState('')
  const [quantity, setQuantity] = useState('')
  const [batchReference, setBatchReference] = useState('')
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [batches, setBatches] = useState<ProductionBatch[]>([])
  const [batchDate, setBatchDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [recipeVersionId, setRecipeVersionId] = useState('')
  const [plannedPortions, setPlannedPortions] = useState('')
  const [batchSaving, setBatchSaving] = useState(false)
  const [weighingRequirement, setWeighingRequirement] = useState<{ batchId: string; requirementId: string } | null>(null)
  const [weighGrams, setWeighGrams] = useState('')

  const selected = useMemo<KitchenInventoryItem | null>(
    () => inventory.items.find((item) => item.ingredient_id === selectedIngredientId) ?? null,
    [inventory.items, selectedIngredientId],
  )
  const scanReadyItems = useMemo(
    () => inventory.items.filter((item) => item.is_scan_ready),
    [inventory.items],
  )

  const refresh = async () => {
    setLoading(true)
    try {
      const [inventoryResult, batchResult] = await Promise.allSettled([
        kitchenService.inventory(),
        kitchenService.productionBatches({ serviceDate: batchDate }),
      ])
      if (inventoryResult.status === 'fulfilled') {
        const data = inventoryResult.value
        setInventory(data)
        setSelectedIngredientId((current) =>
          data.items.some((item) => item.ingredient_id === current)
            ? current
            : data.items.find((item) => item.is_scan_ready)?.ingredient_id ?? '',
        )
      } else {
        throw inventoryResult.reason
      }
      if (batchResult.status === 'fulfilled') setBatches(batchResult.value.items)
    } catch {
      toast.error('Kartu stok kitchen tidak dapat dimuat.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [batchDate])

  const createBatch = async () => {
    const portions = Number(plannedPortions)
    if (!recipeVersionId.trim() || !Number.isInteger(portions) || portions <= 0) {
      toast.error('Isi recipe version VERIFIED dan jumlah porsi yang valid.')
      return
    }
    setBatchSaving(true)
    try {
      await kitchenService.createProductionBatch({
        service_date: batchDate,
        recipe_version_id: recipeVersionId.trim(),
        planned_portions: portions,
      })
      toast.success('Batch produksi dibuat dari recipe VERIFIED.')
      setRecipeVersionId('')
      setPlannedPortions('')
      await refresh()
    } catch {
      toast.error('Batch belum bisa dibuat. Pastikan recipe sudah VERIFIED dan migration batch sudah aktif.')
    } finally {
      setBatchSaving(false)
    }
  }

  const planFromPaidOrders = async () => {
    setBatchSaving(true)
    try {
      const result = await kitchenService.planProductionBatches({
        service_date: batchDate,
      })
      if (result.status === 'REQUIRES_VERIFICATION') {
        toast.error(`${result.blocked_menus.length} menu belum punya recipe VERIFIED; tidak ada batch yang dibuat.`)
      } else if (result.status === 'NO_PAID_DEMAND') {
        toast.info('Tidak ada order PAID untuk tanggal dan slot ini.')
      } else {
        toast.success(`${result.planned_batches.length} batch direncanakan dari order PAID.`)
      }
      await refresh()
    } catch {
      toast.error('Demand PAID belum bisa direncanakan. Pastikan migration batch dan recipe sudah aktif.')
    } finally {
      setBatchSaving(false)
    }
  }

  const submitBatchWeigh = async () => {
    if (!weighingRequirement) return
    const grams = Number(weighGrams)
    if (!Number.isFinite(grams) || grams <= 0) {
      toast.error('Masukkan berat net dalam gram.')
      return
    }
    setBatchSaving(true)
    try {
      const result = await kitchenService.weighProduction(weighingRequirement.batchId, {
        requirement_id: weighingRequirement.requirementId,
        actual_net_grams: grams,
        idempotency_key: globalThis.crypto.randomUUID(),
        scale_source: 'manual',
      })
      toast.success(`${result.ingredient_name}: ${result.actual_net_grams.toLocaleString('id-ID')} g masuk ke ledger.`)
      setWeighGrams('')
      setWeighingRequirement(null)
      await refresh()
    } catch {
      toast.error('Berat belum bisa dicatat. Periksa stok, BOM, dan unit gram/kg.')
    } finally {
      setBatchSaving(false)
    }
  }

  const completeBatch = async (batchId: string) => {
    setBatchSaving(true)
    try {
      await kitchenService.completeProductionBatch(batchId)
      toast.success('Batch selesai dan dikunci dari input timbang berikutnya.')
      await refresh()
    } catch {
      toast.error('Batch belum dapat diselesaikan. Pastikan semua bahan sudah ditimbang.')
    } finally {
      setBatchSaving(false)
    }
  }

  const useScanCode = () => {
    const code = scanCode.trim().toLowerCase()
    if (!code) return
    const match = scanReadyItems.find((item) =>
      item.ingredient_id.toLowerCase() === code || item.ingredient_name.toLowerCase() === code,
    )
    if (!match) {
      toast.error('Kode bahan belum ditemukan. Pilih bahan dari daftar atau cek label.')
      return
    }
    setSelectedIngredientId(match.ingredient_id)
    setScanCode('')
    toast.success(`${match.ingredient_name} dipilih.`)
  }

  const submitConsumption = async () => {
    if (!selected) {
      toast.error('Pilih bahan terlebih dahulu.')
      return
    }
    const amount = Number(quantity)
    if (!Number.isFinite(amount) || amount <= 0) {
      toast.error('Masukkan berat/pemakaian yang valid.')
      return
    }
    setSaving(true)
    try {
      const result = await kitchenService.consumeInventory({
        ingredient_id: selected.ingredient_id,
        quantity: amount,
        unit: selected.unit,
        batch_reference: batchReference.trim(),
        note: note.trim(),
        idempotency_key: globalThis.crypto.randomUUID(),
      })
      toast.success(`${result.ingredient_name}: stok tersisa ${result.current_stock.toLocaleString('id-ID')} ${result.unit}.`)
      setQuantity('')
      setNote('')
      await refresh()
    } catch {
      toast.error('Pemakaian tidak dapat dicatat. Periksa stok dan unit bahan.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-300">Kitchen operations</p>
          <h1 className="mt-1 text-3xl font-extrabold text-white">Pemakaian bahan & stok</h1>
          <p className="mt-2 max-w-3xl text-sm text-slate-300">Catat pemakaian aktual bahan utama per batch. Saat timbangan Bluetooth ditambahkan, angka berat akan langsung masuk ke form ini tanpa mengubah ledger stok.</p>
        </div>
        <Button variant="outline" onClick={() => void refresh()} disabled={loading || saving} className="border-slate-600 bg-slate-900 text-white hover:bg-slate-800 hover:text-white">
          <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} /> Muat ulang
        </Button>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="border-slate-700 bg-slate-900 text-white"><p className="text-sm text-slate-300">Bahan terdata</p><p className="mt-2 text-3xl font-extrabold">{inventory.counts.total}</p></Card>
        <Card className="border-amber-700/70 bg-amber-950/40 text-white"><p className="text-sm text-amber-200">Stok menipis</p><p className="mt-2 text-3xl font-extrabold">{inventory.counts.menipis}</p></Card>
        <Card className="border-rose-700/70 bg-rose-950/40 text-white"><p className="text-sm text-rose-200">Stok habis</p><p className="mt-2 text-3xl font-extrabold">{inventory.counts.habis}</p></Card>
      </div>

      <Card className="overflow-hidden border-[#ead9d0] bg-[#fffaf6] text-[#301d1b] shadow-[0_20px_55px_rgba(82,35,31,.08)]">
        <div className="-mx-6 -mt-6 mb-6 flex flex-wrap items-start justify-between gap-4 bg-[linear-gradient(115deg,#681d27,#a7353d)] px-6 py-5 text-white">
          <div><p className="text-[10px] font-black uppercase tracking-[.22em] text-[#f1c6b5]">Production calendar</p><h2 className="mt-1 font-display text-2xl font-bold">Batch dapur</h2><p className="mt-1 max-w-2xl text-sm text-white/80">Satu siklus per tanggal. Rencana batch hanya dibuat dari resep VERIFIED dan order PAID.</p></div>
          <Badge variant="outline" className="border-white/30 bg-white/10 text-white">Timbangan Bluetooth · roadmap</Badge>
        </div>
        <div className="grid gap-3 md:grid-cols-[170px_minmax(0,1fr)_150px_auto]">
          <div className="space-y-2"><Label htmlFor="batch-date" className="text-[#674b45]">Tanggal layanan</Label><Input id="batch-date" type="date" value={batchDate} onChange={(event) => setBatchDate(event.target.value)} className="border-[#e4ccc2] bg-white text-[#301d1b]" /></div>
          <div className="space-y-2"><Label htmlFor="recipe-version" className="text-[#674b45]">Recipe version VERIFIED</Label><Input id="recipe-version" value={recipeVersionId} onChange={(event) => setRecipeVersionId(event.target.value)} placeholder="recipe_..." className="border-[#e4ccc2] bg-white text-[#301d1b]" /></div>
          <div className="space-y-2"><Label htmlFor="planned-portions" className="text-[#674b45]">Target porsi</Label><Input id="planned-portions" type="number" min="1" step="1" value={plannedPortions} onChange={(event) => setPlannedPortions(event.target.value)} placeholder="100" className="border-[#e4ccc2] bg-white text-[#301d1b]" /></div>
          <Button onClick={() => void createBatch()} disabled={batchSaving} className="self-end bg-[#8f2833] text-white hover:bg-[#711f2b]"><ChefHat className="size-4" /> Buat batch</Button>
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[#edd2c7] bg-[#f8eee8] p-4">
          <p className="text-xs text-[#674b45]">Demand batch dihitung dari order <span className="font-bold text-[#8f2833]">PAID</span>. Resep yang belum VERIFIED menahan produksi.</p>
          <Button variant="outline" onClick={() => void planFromPaidOrders()} disabled={batchSaving} className="border-[#c77a6d] bg-white text-[#8f2833] hover:bg-[#fbe3dc]"><ClipboardCheck className="size-4" /> Rencanakan dari order PAID</Button>
        </div>
        <div className="mt-6 grid gap-3 lg:grid-cols-2">
          {!batches.length ? <p className="rounded-2xl border border-dashed border-[#d9bcb1] bg-white p-5 text-sm text-[#806a63] lg:col-span-2">Belum ada batch untuk tanggal ini. Setelah resep VERIFIED dan migration 014 aktif, batch akan muncul di kalender produksi.</p> : null}
          {batches.map((batch) => <article key={batch.batch_id} className="overflow-hidden rounded-2xl border border-[#ead9d0] bg-white shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 bg-[#fbf2ed] px-4 py-3">
              <div><p className="text-[10px] font-black uppercase tracking-[.18em] text-[#a7353d]">{batch.service_date} · {batch.planned_portions.toLocaleString('id-ID')} porsi</p><h3 className="mt-1 font-display text-lg font-bold text-[#301d1b]">{batch.menu_name || batch.recipe_version_id}</h3></div>
              <div className="flex items-center gap-2"><Badge variant="outline" className="border-[#dec3b8] text-[#674b45]">#{batch.batch_id.slice(0, 8)}</Badge><Badge className="bg-[#8f2833] text-white">{batch.status}</Badge></div>
            </div>
            <div className="grid gap-2 p-4 sm:grid-cols-2">{batch.requirements.map((requirement) => <div key={requirement.requirement_id} className="flex items-center justify-between gap-3 rounded-xl border border-[#efe4de] bg-[#fffdfb] p-3"><div className="min-w-0"><p className="truncate text-sm font-semibold text-[#483532]">{requirement.ingredient_name}</p><p className="mt-1 text-xs text-[#806a63]">Rencana {requirement.planned_grams.toLocaleString('id-ID')} g · sudah {requirement.issued_grams.toLocaleString('id-ID')} g</p></div><Button size="sm" variant="outline" disabled={batch.status === 'COMPLETED' || batchSaving} onClick={() => setWeighingRequirement({ batchId: batch.batch_id, requirementId: requirement.requirement_id })} className="border-[#d9bcb1] text-[#8f2833] hover:bg-[#fbe3dc]">Input berat</Button></div>)}</div>
            {batch.status !== 'COMPLETED' && <div className="border-t border-[#efe4de] px-4 py-3 text-right"><Button size="sm" onClick={() => void completeBatch(batch.batch_id)} disabled={batchSaving} className="bg-[#8f2833] text-white hover:bg-[#711f2b]">Selesaikan batch</Button></div>}
          </article>)}
        </div>
        {weighingRequirement ? <div className="mt-4 flex flex-wrap items-end gap-3 rounded-2xl border border-[#e3bdb0] bg-[#fbf2ed] p-4"><div className="space-y-2"><Label htmlFor="batch-weigh" className="text-[#674b45]">Berat net (gram)</Label><Input id="batch-weigh" type="number" min="0.01" step="0.01" value={weighGrams} onChange={(event) => setWeighGrams(event.target.value)} placeholder="2500" className="w-48 border-[#e4ccc2] bg-white text-[#301d1b]" /></div><Button onClick={() => void submitBatchWeigh()} disabled={batchSaving} className="bg-[#8f2833] text-white hover:bg-[#711f2b]">Simpan ke ledger</Button><Button variant="ghost" onClick={() => setWeighingRequirement(null)} className="text-[#806a63] hover:bg-[#f4e4dc]">Batal</Button></div> : null}
      </Card>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Card className="border-slate-700 bg-slate-900 text-white">
          <div className="flex items-start gap-3"><div className="rounded-xl bg-amber-400/15 p-2 text-amber-300"><ScanLine className="size-5" /></div><div><h2 className="font-bold">Catat pemakaian aktual</h2><p className="mt-1 text-sm text-slate-300">Scan label atau pilih bahan, lalu masukkan berat yang dipakai kitchen.</p></div></div>
          <div className="mt-6 space-y-4">
            <div className="space-y-2"><Label htmlFor="ingredient-scan" className="text-slate-100">Scan barcode / ID bahan</Label><div className="flex gap-2"><Input id="ingredient-scan" value={scanCode} onChange={(event) => setScanCode(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); useScanCode() } }} placeholder="Scan dengan scanner atau ketik ID" className="border-slate-600 bg-slate-950 text-white" /><Button type="button" variant="outline" onClick={useScanCode} className="border-slate-600 bg-slate-800 text-white hover:bg-slate-700 hover:text-white"><Barcode className="size-4" /> Gunakan</Button></div></div>
            <div className="space-y-2"><Label htmlFor="ingredient-id" className="text-slate-100">Bahan utama</Label><select id="ingredient-id" value={selectedIngredientId} onChange={(event) => setSelectedIngredientId(event.target.value)} className="h-10 w-full rounded-md border border-slate-600 bg-slate-950 px-3 text-sm text-white"><option value="">Pilih bahan…</option>{scanReadyItems.map((item) => <option key={item.ingredient_id} value={item.ingredient_id}>{item.ingredient_name} — tersedia {item.current_stock} {item.unit}</option>)}</select></div>
            {selected ? <div className="rounded-lg border border-slate-700 bg-slate-950 p-3 text-sm"><p className="font-semibold">{selected.ingredient_name}</p><p className="mt-1 text-slate-300">Tersedia {selected.current_stock.toLocaleString('id-ID')} {selected.unit} · batas minimum {selected.min_stock.toLocaleString('id-ID')} {selected.unit}</p></div> : null}
            <div className="grid gap-4 sm:grid-cols-2"><div className="space-y-2"><Label htmlFor="quantity" className="text-slate-100">Berat / pemakaian</Label><Input id="quantity" type="number" min="0.0001" step="0.01" value={quantity} onChange={(event) => setQuantity(event.target.value)} placeholder="0" className="border-slate-600 bg-slate-950 text-white" /></div><div className="space-y-2"><Label className="text-slate-100">Unit stok</Label><div className="flex h-10 items-center rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-300">{selected?.unit || 'Pilih bahan dahulu'}</div></div></div>
            <div className="space-y-2"><Label htmlFor="batch-reference" className="text-slate-100">Referensi batch (opsional)</Label><Input id="batch-reference" value={batchReference} onChange={(event) => setBatchReference(event.target.value)} placeholder="Contoh: Batch 31 Okt" className="border-slate-600 bg-slate-950 text-white" /></div>
            <div className="space-y-2"><Label htmlFor="kitchen-note" className="text-slate-100">Catatan (opsional)</Label><Input id="kitchen-note" value={note} onChange={(event) => setNote(event.target.value)} placeholder="Contoh: trimming/waste sudah dipisahkan" className="border-slate-600 bg-slate-950 text-white" /></div>
            <Button onClick={() => void submitConsumption()} disabled={saving || !selected} className="w-full bg-amber-400 text-slate-950 hover:bg-amber-300"><PackageMinus className="size-4" /> Simpan pemakaian bahan</Button>
          </div>
        </Card>

        <Card className="border-slate-700 bg-slate-900 text-white">
          <div className="flex items-start justify-between gap-3"><div><h2 className="font-bold">Kartu stok kitchen</h2><p className="mt-1 text-sm text-slate-300">Stok ini menjadi sumber rekomendasi reorder dan draft PO admin.</p></div><ClipboardCheck className="size-5 text-emerald-300" /></div>
          <div className="mt-5 max-h-[650px] space-y-2 overflow-auto pr-1">
            {inventory.items.map((item) => <div key={item.ingredient_name} className="flex items-center justify-between gap-3 rounded-xl border border-slate-700 bg-slate-950 p-3"><div className="min-w-0"><p className="truncate font-semibold">{item.ingredient_name}</p><p className="mt-1 text-xs text-slate-400">Min. {item.min_stock.toLocaleString('id-ID')} {item.unit}{!item.is_scan_ready ? ' · perlu mapping ingredient' : ''}</p></div><div className="flex shrink-0 items-center gap-2"><p className="font-bold">{item.current_stock.toLocaleString('id-ID')} {item.unit}</p><Badge variant="outline" className={stockTone(item.status)}>{item.status === 'AMBIL_AMAN' ? 'AMAN' : item.status}</Badge></div></div>)}
            {!loading && !inventory.items.length ? <div className="py-12 text-center text-slate-400"><AlertTriangle className="mx-auto mb-3 size-7" />Belum ada kartu stok yang bisa ditampilkan.</div> : null}
          </div>
        </Card>
      </div>
      <p className="flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-slate-300"><ChefHat className="size-4 text-amber-300" /> Integrasi timbangan Bluetooth ditunda: nantinya hanya mengisi berat otomatis, sedangkan validasi stok dan catatan ledger di atas tetap sama.</p>
    </div>
  )
}
