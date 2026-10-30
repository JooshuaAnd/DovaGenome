import { useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircle2, ClipboardCheck, ExternalLink, RefreshCw, ShieldAlert, Sparkles, Trash2, Upload } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  adminService,
  type RecipeAiDraft,
  type RecipeAiDraftComponent,
  type RecipeComponent,
  type RecipeIngredientOption,
  type RecipeIntakeResult,
  type RecipeNutritionPreview,
  type RecipeReview,
} from '@/services/admin'
import { getErrorMessage } from '@/services/http'

type EditableComponent = RecipeComponent & { allergenText: string }

export function RecipeReviewPage() {
  const [reviews, setReviews] = useState<RecipeReview[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [components, setComponents] = useState<EditableComponent[]>([])
  const [ingredientOptions, setIngredientOptions] = useState<RecipeIngredientOption[]>([])
  const [componentLoading, setComponentLoading] = useState(false)
  const [nutritionPreview, setNutritionPreview] = useState<RecipeNutritionPreview | null>(null)
  const [nutritionLoading, setNutritionLoading] = useState(false)
  const [newIngredientId, setNewIngredientId] = useState('')
  const [newIngredientQuantity, setNewIngredientQuantity] = useState('')
  const [newIngredientUnit, setNewIngredientUnit] = useState('g')
  const [risk, setRisk] = useState<'LOW' | 'MEDIUM'>('LOW')
  const [notes, setNotes] = useState('')
  const [aiPhoto, setAiPhoto] = useState('')
  const [aiPhotoName, setAiPhotoName] = useState('')
  const [aiDocument, setAiDocument] = useState<File | null>(null)
  const [aiSourceUrl, setAiSourceUrl] = useState('')
  const [aiContext, setAiContext] = useState('')
  const [aiDraft, setAiDraft] = useState<RecipeAiDraft | null>(null)
  const [aiGenerating, setAiGenerating] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [intakeFile, setIntakeFile] = useState<File | null>(null)
  const [intakeDay, setIntakeDay] = useState('Senin')
  const [intakeMenuName, setIntakeMenuName] = useState('')
  const [intakeBusy, setIntakeBusy] = useState(false)
  const [intakeResult, setIntakeResult] = useState<RecipeIntakeResult | null>(null)
  const selectionRequest = useRef(0)

  const selected = useMemo(
    () => reviews.find((review) => review.recipe_version_id === selectedId) ?? null,
    [reviews, selectedId],
  )

  const loadReviews = async (preferredId = selectedId) => {
    setLoading(true)
    try {
      const data = await adminService.getRecipeReviews()
      setReviews(data)
      const next = data.find((review) => review.recipe_version_id === preferredId)
        ?? data.find((review) => review.status !== 'VERIFIED')
        ?? data[0]
      if (next) await selectRecipe(next.recipe_version_id)
      else {
        setSelectedId('')
        setComponents([])
      }
    } catch (error) {
      setReviews([])
      setSelectedId('')
      setComponents([])
      toast.error('Daftar recipe review tidak dapat dimuat.', { description: getErrorMessage(error) })
    } finally {
      setLoading(false)
    }
  }

  const selectRecipe = async (recipeVersionId: string) => {
    const requestId = ++selectionRequest.current
    setSelectedId(recipeVersionId)
    setComponents([])
    setNutritionPreview(null)
    setAiDraft(null)
    setComponentLoading(true)
    try {
      const rows = await adminService.getRecipeComponents(recipeVersionId)
      if (requestId !== selectionRequest.current) return
      setComponents(
        rows.map((row) => ({
          ...row,
          allergenText: (row.allergen_codes ?? []).join(', '),
        })),
      )
    } catch (error) {
      if (requestId !== selectionRequest.current) return
      toast.error('Komponen recipe tidak dapat dimuat.', { description: getErrorMessage(error) })
    } finally {
      if (requestId === selectionRequest.current) setComponentLoading(false)
    }
  }

  useEffect(() => {
    void loadReviews()
    adminService.getRecipeIngredients().then(setIngredientOptions).catch((error) => {
      toast.error('Master bahan belum dapat dimuat.', { description: getErrorMessage(error) })
    })
  }, [])

  const updateComponent = (index: number, patch: Partial<EditableComponent>) => {
    setComponents((current) =>
      current.map((component, rowIndex) =>
        rowIndex === index ? { ...component, ...patch } : component,
      ),
    )
  }

  const saveComponents = async () => {
    if (!selected) return
    const invalid = components.some(
      (component) => !component.ingredient_id || !component.quantity || !component.unit.trim(),
    )
    if (invalid) {
      toast.error('Semua komponen harus memiliki quantity dan unit nyata.')
      return
    }
    setSaving(true)
    try {
      await adminService.replaceRecipeComponents(
        selected.recipe_version_id,
        components.map((component, index) => ({
          ingredient_id: component.ingredient_id,
          quantity: Number(component.quantity),
          unit: component.unit.trim(),
          preparation: component.preparation,
          sort_order: index,
        })),
      )
      toast.success('Komponen recipe tersimpan sebagai pending verification.')
      await loadReviews(selected.recipe_version_id)
    } catch (error) {
      toast.error('Komponen recipe gagal disimpan.', { description: getErrorMessage(error) })
    } finally {
      setSaving(false)
    }
  }

  const verifyIngredient = async (component: EditableComponent) => {
    if (!component.ingredient_id) return
    setSaving(true)
    try {
      const codes = component.allergenText
        .split(',')
        .map((code) => code.trim())
        .filter(Boolean)
      await adminService.verifyIngredient(component.ingredient_id, codes)
      toast.success(`${component.ingredient_name ?? 'Ingredient'} diverifikasi.`)
      if (selected) await loadReviews(selected.recipe_version_id)
    } catch (error) {
      toast.error('Ingredient gagal diverifikasi.', { description: getErrorMessage(error) })
    } finally {
      setSaving(false)
    }
  }

  const verifyRecipe = async () => {
    if (!selected) return
    setSaving(true)
    try {
      await adminService.verifyRecipe(selected.recipe_version_id, risk, notes)
      toast.success('Recipe VERIFIED. Menu akan dihitung ulang oleh Allergy Guard.')
      setNotes('')
      await loadReviews(selected.recipe_version_id)
    } catch (error) {
      toast.error('Recipe belum dapat diverifikasi.', { description: getErrorMessage(error) })
    } finally {
      setSaving(false)
    }
  }

  const handleAiPhoto = (file: File | undefined) => {
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      toast.error('Gunakan foto JPEG, PNG, atau WebP.')
      return
    }
    if (file.size > 4_500_000) {
      toast.error('Ukuran foto maksimal 4,5 MB.')
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      setAiPhoto(String(reader.result ?? ''))
      setAiPhotoName(file.name)
    }
    reader.onerror = () => toast.error('Foto tidak dapat dibaca.')
    reader.readAsDataURL(file)
  }

  const generateAiDraft = async () => {
    if (!selected) return
    if (!aiPhoto && !aiSourceUrl.trim() && !aiDocument) {
      toast.error('Unggah foto, dokumen resep, atau masukkan link resep.')
      return
    }
    setAiGenerating(true)
    try {
      const draft = aiDocument
        ? await adminService.importRecipeDocument(selected.recipe_version_id, aiDocument, aiContext.trim())
        : await adminService.generateRecipeAiDraft(selected.recipe_version_id, {
            image_data_url: aiPhoto,
            source_url: aiSourceUrl.trim(),
            context: aiContext.trim(),
          })
      setAiDraft(draft)
      toast.success('Draft komposisi AI siap untuk ditinjau.')
    } catch (error) {
      toast.error('Draft AI gagal dibuat.', { description: getErrorMessage(error) })
    } finally {
      setAiGenerating(false)
    }
  }

  const createMenuFromUpload = async () => {
    if (!intakeFile) {
      toast.error('Pilih foto atau dokumen resep terlebih dahulu.')
      return
    }
    setIntakeBusy(true)
    setIntakeResult(null)
    try {
      const result = await adminService.intakeRecipe(intakeFile, intakeDay, intakeMenuName.trim(), aiContext.trim())
      setIntakeResult(result)
      setIntakeFile(null)
      setIntakeMenuName('')
      await loadReviews(result.recipe_version_id)
      toast.success('Menu dan recipe draft dibuat. Menu tetap unpublished sampai diverifikasi.')
    } catch (error) {
      toast.error('Menu draft belum dapat dibuat.', { description: getErrorMessage(error) })
    } finally {
      setIntakeBusy(false)
    }
  }

  const updateAiDraftComponent = (index: number, patch: Partial<RecipeAiDraftComponent>) => {
    setAiDraft((current) => current && ({
      ...current,
      components: current.components.map((component, componentIndex) =>
        componentIndex === index ? { ...component, ...patch } : component,
      ),
    }))
  }

  const handleAiDocument = (file: File | undefined) => {
    if (!file) return
    const allowed = ['.pdf', '.xlsx', '.csv', '.txt', '.md']
    const extension = `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`
    if (!allowed.includes(extension)) {
      toast.error('Dokumen harus PDF, XLSX, CSV, TXT, atau MD.')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      toast.error('Ukuran dokumen maksimal 10 MB.')
      return
    }
    setAiDocument(file)
  }

  const applyAiDraft = async () => {
    if (!selected || !aiDraft) return
    const invalid = aiDraft.components.some(
      (component) => !component.ingredient_name.trim() || !component.quantity || !component.unit.trim(),
    )
    if (invalid) {
      toast.error('Setiap bahan AI harus memiliki nama, takaran, dan unit.')
      return
    }
    setSaving(true)
    try {
      await adminService.applyRecipeAiDraft(selected.recipe_version_id, aiDraft)
      toast.success('Draft diterapkan sebagai PENDING. Bahan belum otomatis disetujui.')
      setAiDraft(null)
      setIngredientOptions(await adminService.getRecipeIngredients())
      await loadReviews(selected.recipe_version_id)
    } catch (error) {
      toast.error('Draft AI gagal diterapkan.', { description: getErrorMessage(error) })
    } finally {
      setSaving(false)
    }
  }

  const verifyAllIngredients = async () => {
    const pending = components.filter(
      (component) => component.ingredient_id &&
        (component.ingredient_status !== 'VERIFIED' || component.verification_status !== 'VERIFIED' ||
          component.allergenText !== (component.allergen_codes ?? []).join(', ')),
    )
    if (!pending.length) return
    setSaving(true)
    try {
      await adminService.verifyIngredientsBatch(
        pending.map((component) => ({
          ingredient_id: component.ingredient_id,
          allergen_codes: component.allergenText.split(',').map((code) => code.trim()).filter(Boolean),
        })),
      )
      toast.success(`${pending.length} bahan ditandai sudah direview.`)
      if (selected) await loadReviews(selected.recipe_version_id)
    } catch (error) {
      toast.error('Verifikasi bahan massal gagal.', { description: getErrorMessage(error) })
    } finally {
      setSaving(false)
    }
  }

  const addIngredient = () => {
    const ingredient = ingredientOptions.find((option) => option.ingredient_id === newIngredientId)
    const quantity = Number(newIngredientQuantity)
    if (!ingredient || !Number.isFinite(quantity) || quantity <= 0 || !newIngredientUnit.trim()) {
      toast.error('Pilih bahan dan isi takaran serta unit yang valid.')
      return
    }
    if (components.some((component) => component.ingredient_id === ingredient.ingredient_id)) {
      toast.error('Bahan itu sudah ada di BOM resep ini.')
      return
    }
    setComponents((current) => [...current, {
      recipe_component_id: -Date.now(),
      recipe_version_id: selectedId,
      ingredient_id: ingredient.ingredient_id,
      ingredient_name: ingredient.name,
      ingredient_status: ingredient.verification_status,
      allergen_codes: ingredient.allergen_codes,
      allergenText: (ingredient.allergen_codes ?? []).join(', '),
      quantity,
      unit: newIngredientUnit.trim(),
      preparation: '',
      verification_status: 'UNVERIFIED',
      source: 'admin_review',
      sort_order: current.length,
    }])
    setNewIngredientId('')
    setNewIngredientQuantity('')
  }

  const loadNutritionPreview = async () => {
    if (!selected) return
    setNutritionLoading(true)
    try {
      setNutritionPreview(await adminService.getRecipeNutritionPreview(selected.recipe_version_id))
    } catch (error) {
      setNutritionPreview(null)
      toast.error('Preview gizi tidak dapat dihitung.', { description: getErrorMessage(error) })
    } finally {
      setNutritionLoading(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 px-4 py-8 sm:px-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Safety control</p>
          <h1 className="text-2xl sm:text-3xl">Recipe & BOM Verification</h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-text">
            Menu tetap ditahan sampai ingredient, takaran, unit, allergen mapping, dan risiko
            cross-contact diverifikasi operator. Tidak ada status Aman dari prompt atau UI.
          </p>
        </div>
        <Button variant="outline" onClick={() => void loadReviews()} disabled={loading || saving}>
          <RefreshCw className="size-4" /> Muat ulang
        </Button>
      </header>

      <Card className="gap-4 border-[#ead2c8] bg-[#fffaf6] p-5">
        <div>
          <p className="font-bold text-ink">Tambah menu dari resep</p>
          <p className="mt-1 text-sm text-muted-text">Unggah PDF, Excel, foto, atau dokumen teks. AI menyiapkan menu, bahan, takaran, dan estimasi gizi sebagai draft untuk ditinjau.</p>
        </div>
        <div className="grid gap-3 md:grid-cols-4">
          <div className="space-y-1.5">
            <Label htmlFor="intake-day">Hari menu</Label>
            <select id="intake-day" value={intakeDay} onChange={(event) => setIntakeDay(event.target.value)} className="h-10 w-full rounded-lg border border-line bg-white px-3 text-sm">
              {['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'].map((day) => <option key={day}>{day}</option>)}
            </select>
          </div>
          <div className="space-y-1.5 md:col-span-2">
            <Label htmlFor="intake-name">Nama menu (opsional)</Label>
            <Input id="intake-name" value={intakeMenuName} onChange={(event) => setIntakeMenuName(event.target.value)} placeholder="AI mengambil dari resep jika kosong" />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="intake-file">Foto / resep</Label>
            <Input id="intake-file" type="file" accept="image/jpeg,image/png,image/webp,.pdf,.xlsx,.csv,.txt,.md" onChange={(event) => setIntakeFile(event.target.files?.[0] ?? null)} />
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-muted-text">Menu otomatis tetap unpublished; resep menunggu verifikasi operator.</p>
          <Button onClick={() => void createMenuFromUpload()} disabled={intakeBusy || !intakeFile} className="bg-[#8f1d2c] text-white hover:bg-[#741624]">
            {intakeBusy ? <RefreshCw className="size-4 animate-spin" /> : <Upload className="size-4" />} Buat menu & resep draft
          </Button>
        </div>
        {intakeResult && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm">
          <p className="font-bold text-amber-950">{intakeResult.menu_name} · {intakeResult.service_day} — belum dipublikasikan</p>
          <p className="mt-1 text-amber-900">Estimasi AI per porsi: {intakeResult.ai_draft.nutrition.calories_kcal ?? '—'} kcal · protein {intakeResult.ai_draft.nutrition.protein_g ?? '—'} g · karbo {intakeResult.ai_draft.nutrition.carbs_g ?? '—'} g · lemak {intakeResult.ai_draft.nutrition.fat_g ?? '—'} g ({intakeResult.ai_draft.nutrition.confidence} confidence).</p>
          <p className="mt-1 text-xs text-amber-900">Komposisi nutrisi berbasis bahan: {intakeResult.nutrition_from_composition.status}. {intakeResult.nutrition_from_composition.warnings.join(' ')}</p>
        </div>}
      </Card>

      <div className="grid gap-5 lg:grid-cols-[minmax(260px,0.8fr)_minmax(0,2fr)]">
        <Card className="gap-0 overflow-hidden py-0">
          <div className="border-b border-line px-5 py-4">
            <p className="font-bold text-ink">Daftar recipe</p>
            <p className="mt-1 text-xs text-muted-text">{reviews.length} version ditemukan</p>
          </div>
          <div className="max-h-[680px] divide-y divide-line overflow-auto">
            {reviews.map((review) => (
              <button
                key={review.recipe_version_id}
                type="button"
                onClick={() => void selectRecipe(review.recipe_version_id)}
                className={`w-full px-5 py-4 text-left transition-colors hover:bg-forest-50 ${selectedId === review.recipe_version_id ? 'bg-forest-50' : ''}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="font-semibold text-ink">{review.nama_menu}</span>
                  <Badge variant="outline" className={review.status === 'VERIFIED' ? 'text-safe-strong' : 'text-caution-strong'}>
                    {review.status === 'VERIFIED' ? 'VERIFIED' : 'PENDING'}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-muted-text">
                  {review.component_count} komponen · {review.unresolved_component_count} unresolved
                </p>
              </button>
            ))}
          </div>
        </Card>

        <Card className="gap-5">
          {!selected ? (
            <div className="flex min-h-60 flex-col items-center justify-center gap-3 text-center text-muted-text">
              <ClipboardCheck className="size-8" />
              <p>Pilih recipe untuk mulai review.</p>
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-start justify-between gap-3 px-6">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wide text-muted-text">Recipe v{selected.version_no}</p>
                  <h2 className="mt-1 text-xl font-bold text-ink">{selected.nama_menu}</h2>
                  <p className="mt-1 text-sm text-muted-text">Status sumber: {selected.source}</p>
                </div>
                {selected.status === 'VERIFIED' ? (
                  <Badge><CheckCircle2 className="size-3" /> VERIFIED</Badge>
                ) : (
                  <Badge variant="outline"><ShieldAlert className="size-3" /> Requires verification</Badge>
                )}
              </div>

              <div className="space-y-3 px-6">
                <div className="rounded-xl border border-dashed border-forest-300 bg-forest-50/50 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="flex items-center gap-2 font-bold text-ink"><Sparkles className="size-4 text-forest-700" /> Draft AI dari foto atau resep</p>
                      <p className="mt-1 max-w-2xl text-xs text-muted-text">AI hanya membuat perkiraan per porsi beserta sumber dan tingkat keyakinan. Admin tetap meninjau sebelum bahan atau recipe diverifikasi.</p>
                    </div>
                    {aiDraft ? <Badge variant="outline">Draft siap ditinjau</Badge> : null}
                  </div>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label htmlFor="ai-photo">Foto makanan / kemasan</Label>
                      <Input id="ai-photo" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => handleAiPhoto(event.target.files?.[0])} disabled={saving || aiGenerating} />
                      <p className="text-xs text-muted-text">{aiPhotoName || 'JPEG, PNG, atau WebP • maks. 4,5 MB'}</p>
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="ai-source-url">Link resep / produk (opsional)</Label>
                      <Input id="ai-source-url" type="url" value={aiSourceUrl} onChange={(event) => setAiSourceUrl(event.target.value)} placeholder="https://…" disabled={saving || aiGenerating} />
                    </div>
                  </div>
                  <div className="mt-3 space-y-1.5">
                    <Label htmlFor="ai-recipe-document">Buku resep / komposisi</Label>
                    <Input id="ai-recipe-document" type="file" accept=".pdf,.xlsx,.csv,.txt,.md" onChange={(event) => handleAiDocument(event.target.files?.[0])} disabled={saving || aiGenerating} />
                    <p className="text-xs text-muted-text">{aiDocument ? `${aiDocument.name} - dibaca private di backend` : 'PDF, XLSX, CSV, TXT, atau MD - maks. 10 MB'}</p>
                  </div>
                  <div className="mt-3 flex flex-wrap items-end gap-3">
                    <div className="min-w-56 flex-1 space-y-1.5">
                      <Label htmlFor="ai-context">Catatan untuk AI (opsional)</Label>
                      <Input id="ai-context" value={aiContext} onChange={(event) => setAiContext(event.target.value)} placeholder="Contoh: porsi makan siang, tanpa topping" disabled={saving || aiGenerating} />
                    </div>
                    <Button type="button" variant="outline" onClick={() => void generateAiDraft()} disabled={saving || aiGenerating}>
                      {aiGenerating ? <RefreshCw className="size-4 animate-spin" /> : <Upload className="size-4" />} Buat draft AI
                    </Button>
                  </div>

                  {aiDraft ? (
                    <div className="mt-4 space-y-3 rounded-lg border border-forest-200 bg-background p-3">
                      <div>
                        <p className="font-semibold text-ink">{aiDraft.dish_name || selected.nama_menu}</p>
                        <p className="mt-1 text-xs text-muted-text">{aiDraft.summary}</p>
                        <p className="mt-2 text-xs text-muted-text">
                          Nutrition draft: {aiDraft.nutrition.calories_kcal == null ? 'belum tersedia' : `${aiDraft.nutrition.calories_kcal} kcal`} · P {aiDraft.nutrition.protein_g ?? '-'} g · KH {aiDraft.nutrition.carbs_g ?? '-'} g · L {aiDraft.nutrition.fat_g ?? '-'} g · basis {aiDraft.nutrition.basis}
                        </p>
                        {aiDraft.nutrition.warnings.length ? <p className="mt-1 text-xs text-caution-strong">{aiDraft.nutrition.warnings.join(' · ')}</p> : null}
                      </div>
                      <div className="grid grid-cols-[minmax(0,1fr)_80px_92px_auto] gap-2 text-[11px] font-bold uppercase tracking-wide text-muted-text">
                        <span>Bahan</span><span>Takaran</span><span>Unit</span><span>Keyakinan</span>
                      </div>
                      {aiDraft.components.map((component, index) => (
                        <div key={`${component.ingredient_name}-${index}`} className="grid items-center gap-2 sm:grid-cols-[minmax(0,1fr)_80px_92px_auto]">
                          <div className="space-y-1">
                            <Input value={component.ingredient_name} onChange={(event) => updateAiDraftComponent(index, { ingredient_name: event.target.value })} aria-label={`Bahan AI ${index + 1}`} />
                            <Input value={component.allergen_codes.join(', ')} onChange={(event) => updateAiDraftComponent(index, { allergen_codes: event.target.value.split(',').map((code) => code.trim()).filter(Boolean) })} placeholder="Kode alergen" className="h-7 text-xs" aria-label={`Alergen AI ${component.ingredient_name}`} />
                          </div>
                          <Input type="number" min="0.0001" value={component.quantity} onChange={(event) => updateAiDraftComponent(index, { quantity: Number(event.target.value) || 0 })} aria-label={`Takaran AI ${component.ingredient_name}`} />
                          <Input value={component.unit} onChange={(event) => updateAiDraftComponent(index, { unit: event.target.value })} aria-label={`Unit AI ${component.ingredient_name}`} />
                          <Badge variant="outline" className={component.confidence === 'HIGH' ? 'text-safe-strong' : 'text-caution-strong'}>{component.confidence}</Badge>
                        </div>
                      ))}
                      {aiDraft.safety_notes.length ? <p className="text-xs text-caution-strong">{aiDraft.safety_notes.join(' · ')}</p> : null}
                      {aiDraft.sources.length ? (
                        <div className="flex flex-wrap gap-2 text-xs">
                          {aiDraft.sources.map((source, index) => source.url ? <a key={`${source.url}-${index}`} href={source.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-forest-700 underline">{source.title || 'Sumber AI'} <ExternalLink className="size-3" /></a> : null)}
                        </div>
                      ) : null}
                      <div className="flex justify-end"><Button type="button" onClick={() => void applyAiDraft()} disabled={saving || aiGenerating}>Terapkan draft setelah review</Button></div>
                    </div>
                  ) : null}
                </div>

                <section className="rounded-xl border border-line bg-surface p-4">
                  <div className="flex flex-wrap items-end gap-3">
                    <div className="min-w-56 flex-1 space-y-1.5">
                      <Label htmlFor="add-recipe-ingredient">Tambah bahan dari master bahan</Label>
                      <select id="add-recipe-ingredient" value={newIngredientId} onChange={(event) => {
                        const option = ingredientOptions.find((item) => item.ingredient_id === event.target.value)
                        setNewIngredientId(event.target.value)
                        if (option) setNewIngredientUnit(option.default_unit || 'g')
                      }} disabled={saving || selected.status === 'VERIFIED'} className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm">
                        <option value="">Pilih bahan…</option>
                        {ingredientOptions.map((ingredient) => <option key={ingredient.ingredient_id} value={ingredient.ingredient_id}>{ingredient.name} · {ingredient.verification_status}</option>)}
                      </select>
                    </div>
                    <div className="w-28 space-y-1.5"><Label htmlFor="new-ingredient-quantity">Takaran</Label><Input id="new-ingredient-quantity" type="number" min="0.0001" step="any" value={newIngredientQuantity} onChange={(event) => setNewIngredientQuantity(event.target.value)} disabled={saving || selected.status === 'VERIFIED'} /></div>
                    <div className="w-28 space-y-1.5"><Label htmlFor="new-ingredient-unit">Unit</Label><Input id="new-ingredient-unit" value={newIngredientUnit} onChange={(event) => setNewIngredientUnit(event.target.value)} disabled={saving || selected.status === 'VERIFIED'} /></div>
                    <Button type="button" variant="outline" onClick={addIngredient} disabled={saving || selected.status === 'VERIFIED'}>Tambah ke BOM</Button>
                  </div>
                  <p className="mt-2 text-xs text-muted-text">Bahan baru dapat dibuat lewat draft AI. Di sini pilih bahan master yang sudah ada; bahan berstatus UNVERIFIED tetap harus direview.</p>
                </section>

                {componentLoading ? <p className="rounded-lg bg-surface p-4 text-sm text-muted-text">Memuat komponen resep…</p> : null}
                <div className="grid grid-cols-[minmax(0,1fr)_120px_120px_auto] gap-3 text-xs font-bold uppercase tracking-wide text-muted-text">
                  <span>Ingredient</span><span>Quantity</span><span>Unit</span><span>Status</span>
                </div>
                {components.map((component, index) => (
                  <div key={component.recipe_component_id} className="grid items-center gap-3 rounded-lg border border-line p-3 sm:grid-cols-[minmax(0,1fr)_120px_120px_auto]">
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-ink">{component.ingredient_name ?? component.ingredient_id}</p>
                      <Input
                        value={component.allergenText}
                        onChange={(event) => updateComponent(index, { allergenText: event.target.value })}
                        placeholder="alg_gluten, alg_dairy"
                        aria-label={`Allergen codes ${component.ingredient_name ?? component.ingredient_id}`}
                        className="mt-2 text-xs"
                      />
                      <Input
                        value={component.preparation}
                        onChange={(event) => updateComponent(index, { preparation: event.target.value })}
                        placeholder="Cara persiapan bahan (opsional)"
                        aria-label={`Preparation ${component.ingredient_name ?? component.ingredient_id}`}
                        className="mt-2 text-xs"
                      />
                    </div>
                    <Input
                      type="number"
                      min="0.0001"
                      value={component.quantity ?? ''}
                      onChange={(event) => updateComponent(index, { quantity: Number(event.target.value) || null })}
                      aria-label={`Quantity ${component.ingredient_name ?? component.ingredient_id}`}
                    />
                    <Input
                      value={component.unit === 'UNKNOWN' ? '' : component.unit}
                      onChange={(event) => updateComponent(index, { unit: event.target.value })}
                      placeholder="gram/kg"
                      aria-label={`Unit ${component.ingredient_name ?? component.ingredient_id}`}
                    />
                    <div className="flex items-center gap-1">
                      <Button variant="outline" size="sm" onClick={() => void verifyIngredient(component)} disabled={saving || (component.ingredient_status === 'VERIFIED' && component.verification_status === 'VERIFIED' && component.allergenText === (component.allergen_codes ?? []).join(', '))}>
                        {component.ingredient_status === 'VERIFIED' && component.verification_status === 'VERIFIED' && component.allergenText === (component.allergen_codes ?? []).join(', ') ? 'Verified' : 'Review bahan'}
                      </Button>
                      <Button type="button" variant="ghost" size="icon" aria-label={`Hapus ${component.ingredient_name || 'bahan'} dari BOM`} onClick={() => setComponents((current) => current.filter((_, rowIndex) => rowIndex !== index))} disabled={saving || selected.status === 'VERIFIED' || components.length <= 1}>
                        <Trash2 className="size-4 text-red-700" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>

              <div className="grid gap-4 border-t border-line px-6 pt-5 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="cross-contact-risk">Cross-contact risk</Label>
                  <select id="cross-contact-risk" value={risk} onChange={(event) => setRisk(event.target.value as 'LOW' | 'MEDIUM')} className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm">
                    <option value="LOW">LOW — terkendali</option>
                    <option value="MEDIUM">MEDIUM — protokol terpisah</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="recipe-notes">Catatan verifikator</Label>
                  <Textarea id="recipe-notes" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Evidence supplier, reviewer, atau instruksi cross-contact" />
                </div>
              </div>

              <div className="flex flex-wrap justify-end gap-2 px-6">
                <Button variant="outline" onClick={() => void saveComponents()} disabled={saving || components.length === 0 || selected.status === 'VERIFIED'}>
                  Simpan BOM & minta review ulang
                </Button>
                <Button variant="outline" onClick={() => void verifyAllIngredients()} disabled={saving || components.every((component) => component.ingredient_status === 'VERIFIED' && component.verification_status === 'VERIFIED')}>
                  Verifikasi semua bahan
                </Button>
                <Button variant="outline" onClick={() => void loadNutritionPreview()} disabled={saving || nutritionLoading || components.length === 0}>
                  {nutritionLoading ? 'Menghitung…' : 'Hitung preview gizi'}
                </Button>
                <Button onClick={() => void verifyRecipe()} disabled={saving || selected.status === 'VERIFIED' || componentLoading}>
                  <CheckCircle2 className="size-4" /> Verifikasi recipe
                </Button>
              </div>
              {nutritionPreview ? <div className="mx-6 rounded-xl border border-line bg-surface p-4 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2"><strong>Preview gizi per takaran resep</strong><Badge variant="outline">{nutritionPreview.status} · basis {nutritionPreview.basis}</Badge></div>
                <p className="mt-2">{nutritionPreview.calories_kcal == null ? 'Energi belum tersedia' : `${nutritionPreview.calories_kcal} kcal`} · Protein {nutritionPreview.protein_g ?? '—'} g · Karbohidrat {nutritionPreview.carbs_g ?? '—'} g · Lemak {nutritionPreview.fat_g ?? '—'} g</p>
                {nutritionPreview.warnings.length > 0 && <ul className="mt-2 list-disc pl-5 text-xs text-caution-strong">{nutritionPreview.warnings.map((warning, index) => <li key={`${warning}-${index}`}>{warning}</li>)}</ul>}
              </div> : null}
            </>
          )}
        </Card>
      </div>
    </div>
  )
}
