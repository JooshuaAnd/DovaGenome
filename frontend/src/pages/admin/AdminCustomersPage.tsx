import { useEffect, useMemo, useState } from 'react'
import { Search, Users } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { PageState } from '@/components/common/PageState'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { adminService } from '@/services/admin'
import { getErrorMessage } from '@/services/http'
import type { CustomerAdmin } from '@/services/types'

export function AdminCustomersPage() {
  const [items, setItems] = useState<CustomerAdmin[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<unknown>(null)
  const [query, setQuery] = useState('')
  const load = () => {
    setLoading(true); setError(null)
    adminService.listCustomers().then(setItems).catch((e) => { setItems([]); setError(e) }).finally(() => setLoading(false))
  }
  useEffect(load, [])
  const filtered = useMemo(() => items.filter((c) => `${c.display_name} ${c.phone} ${c.username}`.toLowerCase().includes(query.toLowerCase())), [items, query])
  return <div className="space-y-6">
    <PageHeader eyebrow="CRM · data pelanggan" title="Pelanggan" description="Daftar pelanggan dari endpoint admin. Detail Passport tidak disertakan oleh API daftar." />
    <div className="flex items-center gap-2"><Search className="size-4 text-muted-text"/><Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Cari nama, nomor telepon, atau akun" className="max-w-md"/><Badge variant="outline">{filtered.length} pelanggan</Badge></div>
    <PageState loading={loading} error={error ? new Error(getErrorMessage(error)) : null} skeletonRows={4} onRetry={load}>
      {filtered.length === 0 ? <div className="rounded-xl border bg-white p-10 text-center text-muted-text"><Users className="mx-auto mb-2 size-7"/>Belum ada data pelanggan yang cocok.</div> :
        <div className="overflow-x-auto rounded-xl border bg-white"><table className="w-full text-left text-sm"><thead className="bg-stone-50 text-xs uppercase text-stone-500"><tr><th className="p-3">Pelanggan</th><th className="p-3">Kontak</th><th className="p-3">Pesanan</th><th className="p-3">Status</th><th className="p-3">Profil dietary</th><th className="p-3">Terakhir aktif</th></tr></thead><tbody>{filtered.map(c => <tr key={c.customer_id} className="border-t"><td className="p-3 font-semibold">{c.display_name || c.username || 'Tanpa nama'}<div className="text-xs font-normal text-stone-500">{c.username}</div></td><td className="p-3">{c.phone || '—'}</td><td className="p-3">{c.order_count} total <span className="text-stone-500">· {c.active_order_count} aktif</span></td><td className="p-3"><Badge variant="outline">{c.status}</Badge></td><td className="p-3">Detail tidak disertakan API daftar</td><td className="p-3">{c.last_order_at ? new Date(c.last_order_at).toLocaleString('id-ID') : 'Belum ada'}</td></tr>)}</tbody></table></div>}
    </PageState>
  </div>
}
