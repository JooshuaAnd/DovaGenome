import { BarChart3, Users } from 'lucide-react'

import { PagePlaceholder } from '@/components/common/PagePlaceholder'

/** Operational overview for admins. Reads `GET /admin/dashboard`. */
export function AdminDashboardPage() {
  return (
    <PagePlaceholder
      eyebrow="Administrasi"
      title="Ringkasan operasional"
      description="Pesanan aktif, beban dapur, penanda keselamatan, dan status sistem."
      upcoming="Kartu KPI dan jadwal per hari akan diambil dari GET /admin/dashboard, /admin/kpis, dan /admin/schedule."
      cards={[
        {
          icon: BarChart3,
          title: 'Beban kerja',
          description:
            'Jumlah pesanan per tahap, rata-rata tunggu, dan tiket tertua yang masih aktif.',
        },
        {
          icon: Users,
          title: 'Pelanggan',
          description:
            'Total pelanggan, berapa yang Telegram-nya sudah tertaut, dan berapa yang punya batasan kritis.',
        },
      ]}
    />
  )
}