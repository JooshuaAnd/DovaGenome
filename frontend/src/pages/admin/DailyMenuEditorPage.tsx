import { Loader2, Plus, Save, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { PageState } from '@/components/common/PageState'
import { PageHeader } from '@/components/layout/PageHeader'
import { SafetyCallout } from '@/components/safety/SafetyCallout'
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
import { useServiceWeek } from '@/hooks/useServiceWeek'
import { DAYS, DAY_SHORT } from '@/lib/constants'
import { cn } from '@/lib/utils'
import { catalogService } from '@/services/catalog'
import { getErrorMessage } from '@/services/http'
import type { Menu, MenuIngredient, MenuPatch, Package, ServiceDay } from '@/types'

const EMPTY_INGREDIENT: MenuIngredient = {
  nama: '',
  sumber: '',
  potensi_alergen: '',
  is_critical_allergen: false,
}

/**
 * Editor for ONE menu option of ONE service day.
 *
 * Routes:
 *   `/admin/daily-menu/:id`            -> new option; `:id` is the day, or `new`
 *   `/admin/daily-menu/:id/:menuId`   -> edit an existing option by `menu_id`
 *
 * New options are created with `POST /admin/menus/{hari}` so the existing
 * options of that day are untouched - that is the whole point of supporting
 * several options per day. Edits go through `PATCH /admin/menus/{menu_id}` and
 * only send the fields that actually changed, so a concurrent edit of another
 * field is not reverted.
 */
export function DailyMenuEditorPage() {
  const { id, menuId } = useParams<{ id: string; menuId?: string }>()

  const editing = Boolean(menuId)
  const routeDay = id && id !== 'new' ? (decodeURIComponent(id) as ServiceDay) : null

  const { data: packages } = useApi<Package[]>((signal) => catalogService.listPackages(signal))
  const week = useServiceWeek({ enabled: editing })

  const existing = useMemo(
    () =>
      menuId
        ? (week.days.flatMap((day) => day.options).find((item) => item.menu_id === menuId) ?? null)
        : null,
    [menuId, week.days],
  )

  if (editing && week.loading) {
    return (
      <PageState loading error={null} skeletonRows={4}>
        <span />
      </PageState>
    )
  }

  if (editing && !existing) {
    return (
      <SafetyCallout
        level="blocked"
        title="Pilihan menu tidak ditemukan"
        description={`Tidak ada menu dengan id ${menuId} pada minggu berjalan. Mungkin sudah ditarik atau diganti.`}
        guidance="Kembali ke daftar untuk memilih menu yang tersedia."
      />
    )
  }

  // Keying on `menu_id` remounts the form whenever a different option is loaded,
  // so its state is initialised from props instead of synced by an effect.
  return (
    <MenuOptionForm
      key={existing?.menu_id ?? `new-${routeDay ?? 'any'}`}
      menu={existing}
      defaultDay={routeDay ?? 'Senin'}
      packages={packages ?? []}
    />
  )
}

function MenuOptionForm({
  menu,
  defaultDay,
  packages,
}: {
  menu: Menu | null
  defaultDay: ServiceDay
  packages: Package[]
}) {
  const navigate = useNavigate()
  const editing = menu !== null

  const [day, setDay] = useState<ServiceDay>(menu?.hari ?? defaultDay)
  const [namaMenu, setNamaMenu] = useState(() => menu?.nama_menu ?? '')
  const [deskripsi, setDeskripsi] = useState(() => menu?.deskripsi ?? '')
  const [ingredients, setIngredients] = useState<MenuIngredient[]>(
    () => menu?.bahan_detail ?? [{ ...EMPTY_INGREDIENT }],
  )
  const [equipment, setEquipment] = useState(() => menu?.alat_dapur_steril.join(', ') ?? '')
  const [packageCodes, setPackageCodes] = useState<string[]>(() => menu?.package_codes ?? [])
  const [optionIndex, setOptionIndex] = useState(() => (menu?.option_index ?? 0) + 1)

  const save = useAsync((payload: {
    hari: ServiceDay
    body: Parameters<typeof catalogService.addMenuOption>[1]
  }) =>
    menu
      ? catalogService.patchMenu(menu.menu_id, payload.body as MenuPatch)
      : catalogService.addMenuOption(payload.hari, payload.body),
  )

  const handleSubmit = async () => {
    const body = {
      nama_menu: namaMenu.trim(),
      deskripsi: deskripsi.trim(),
      bahan_detail: ingredients
        .filter((item) => item.nama.trim())
        .map((item) => ({
          nama: item.nama.trim(),
          sumber: item.sumber.trim(),
          potensi_alergen: item.potensi_alergen.trim(),
          is_critical_allergen: item.is_critical_allergen,
        })),
      alat_dapur_steril: splitList(equipment),
      published: true,
      // Empty means "every package"; the backend treats it that way.
      package_codes: packageCodes,
      option_index: Math.max(0, optionIndex - 1),
    }

    const saved = await save.run({ hari: day, body })
    if (saved) {
      toast.success(editing ? 'Pilihan menu diperbarui' : 'Pilihan menu ditambahkan', {
        description: `${saved.nama_menu} · ${DAY_SHORT[saved.hari]}`,
      })
      navigate('/admin/daily-menu')
    }
  }

  const targetDay: ServiceDay = editing && menu ? menu.hari : day

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Administrasi"
        title={editing ? `Ubah pilihan menu ${DAY_SHORT[targetDay]}` : 'Tambah pilihan menu'}
        description={
          editing
            ? 'Perubahan hanya berlaku pada pilihan menu ini. Hari layanan lain tidak terpengaruh.'
            : 'Menambah pilihan baru tidak mengubah pilihan yang sudah ada pada hari yang sama.'
        }
      />

      <div className="space-y-5">
        <Card className="space-y-4">
          <h2 className="font-display text-base font-bold text-ink">Identitas menu</h2>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="menu-day">Hari layanan</Label>
              <Select
                value={targetDay}
                disabled={editing}
                onValueChange={(value) => setDay(value as ServiceDay)}
              >
                <SelectTrigger id="menu-day">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DAYS.map((item) => (
                    <SelectItem key={item} value={item}>
                      {DAY_SHORT[item]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {editing && (
                <p className="text-xs text-muted-text">
                  Hari tidak bisa diubah. Tambahkan pilihan baru sebagai gantinya.
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="menu-order">Urutan pilihan</Label>
              <Input
                id="menu-order"
                type="number"
                min={1}
                value={optionIndex}
                onChange={(event) => setOptionIndex(Number(event.target.value) || 1)}
              />
              <p className="text-xs text-muted-text">
                Pilihan pertama menjadi menu utama hari itu.
              </p>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="menu-name">Nama menu</Label>
            <Input
              id="menu-name"
              value={namaMenu}
              onChange={(event) => setNamaMenu(event.target.value)}
              placeholder="Mis. Nasi Ayam Kemangi"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="menu-desc">Deskripsi</Label>
            <Textarea
              id="menu-desc"
              value={deskripsi}
              onChange={(event) => setDeskripsi(event.target.value)}
              rows={2}
              placeholder="Ringkasan singkat yang dilihat pelanggan."
            />
          </div>
        </Card>

        <Card className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-display text-base font-bold text-ink">Rincian bahan</h2>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setIngredients((current) => [...current, { ...EMPTY_INGREDIENT }])}
            >
              <Plus aria-hidden="true" className="size-3.5" />
              Tambah bahan
            </Button>
          </div>

          {ingredients.length === 0 ? (
            <p className="text-sm text-muted-text">Belum ada bahan. Tambahkan minimal satu.</p>
          ) : (
            <ul className="space-y-3">
              {ingredients.map((item, index) => (
                <li key={index} className="space-y-2 rounded-lg border border-line p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold uppercase tracking-wide text-muted-text">
                      Bahan {index + 1}
                    </span>
                    <Button
                      size="sm"
                      variant="ghost"
                      aria-label={`Hapus bahan ${index + 1}`}
                      onClick={() =>
                        setIngredients((current) => current.filter((_, i) => i !== index))
                      }
                    >
                      <Trash2 aria-hidden="true" className="size-3.5" />
                    </Button>
                  </div>

                  <div className="grid gap-2 sm:grid-cols-2">
                    <Input
                      aria-label="Nama bahan"
                      value={item.nama}
                      onChange={(event) =>
                        setIngredients((current) =>
                          current.map((row, i) =>
                            i === index ? { ...row, nama: event.target.value } : row,
                          ),
                        )
                      }
                      placeholder="Nama bahan"
                    />
                    <Input
                      aria-label="Sumber bahan"
                      value={item.sumber}
                      onChange={(event) =>
                        setIngredients((current) =>
                          current.map((row, i) =>
                            i === index ? { ...row, sumber: event.target.value } : row,
                          ),
                        )
                      }
                      placeholder="Sumber"
                    />
                  </div>

                  <Input
                    aria-label="Potensi alergen"
                    value={item.potensi_alergen}
                    onChange={(event) =>
                      setIngredients((current) =>
                        current.map((row, i) =>
                          i === index
                            ? { ...row, potensi_alergen: event.target.value }
                            : row,
                        ),
                      )
                    }
                    placeholder="Potensi alergen, mis. kacang tanah"
                  />

                  <Button
                    size="sm"
                    variant={item.is_critical_allergen ? 'default' : 'outline'}
                    aria-pressed={item.is_critical_allergen}
                    onClick={() =>
                      setIngredients((current) =>
                        current.map((row, i) =>
                          i === index
                            ? { ...row, is_critical_allergen: !row.is_critical_allergen }
                            : row,
                        ),
                      )
                    }
                    className={cn(item.is_critical_allergen && 'font-semibold')}
                  >
                    {item.is_critical_allergen
                      ? 'Alergen kritis: aktif'
                      : 'Tandai sebagai allergen kritis'}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="space-y-4">
          <h2 className="font-display text-base font-bold text-ink">
            Perlengkapan dan cakupan paket
          </h2>

          <div className="space-y-1.5">
            <Label htmlFor="menu-equipment">Alat dapur steril</Label>
            <Input
              id="menu-equipment"
              value={equipment}
              onChange={(event) => setEquipment(event.target.value)}
              placeholder="Pisahkan dengan koma, mis. Kompor bersih, pisau terpisah"
            />
            <p className="text-xs text-muted-text">
              Alat yang wajib dipakai dapur untuk menu ini.
            </p>
          </div>

          <Separator />

          <fieldset className="space-y-2">
            <legend className="text-sm font-semibold">Tersedia pada paket</legend>
            <p className="text-xs text-muted-text">
              Tidak ada pilihan = tersedia untuk semua paket.
            </p>
            <div className="flex flex-wrap gap-2">
              {(packages ?? []).map((item) => {
                const active = packageCodes.includes(item.code)
                return (
                  <Button
                    key={item.code}
                    type="button"
                    size="sm"
                    variant={active ? 'default' : 'outline'}
                    aria-pressed={active}
                    onClick={() =>
                      setPackageCodes((current) =>
                        current.includes(item.code)
                          ? current.filter((code) => code !== item.code)
                          : [...current, item.code],
                      )
                    }
                  >
                    {item.name}
                  </Button>
                )
              })}
            </div>
          </fieldset>
        </Card>

        {save.error && (
          <SafetyCallout
            level="blocked"
            title="Perubahan tidak tersimpan"
            description={getErrorMessage(save.error)}
          />
        )}

        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={handleSubmit} disabled={save.pending || namaMenu.trim() === ''}>
            {save.pending ? (
              <>
                <Loader2 aria-hidden="true" className="size-4 animate-spin" />
                Menyimpan…
              </>
            ) : (
              <>
                <Save aria-hidden="true" className="size-4" />
                Simpan pilihan menu
              </>
            )}
          </Button>
          <Button variant="ghost" onClick={() => navigate('/admin/daily-menu')}>
            Batal
          </Button>
        </div>
      </div>
    </div>
  )
}

function splitList(value: string): string[] {
  return value
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean)
}
