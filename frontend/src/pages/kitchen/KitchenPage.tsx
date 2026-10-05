import { ChefHat, ShieldAlert } from 'lucide-react'

import { PagePlaceholder } from '@/components/common/PagePlaceholder'

/**
 * Kitchen Display System board. Reads `GET /kitchen/board` and advances orders
 * through `PATCH /kitchen/orders/:id/status`.
 */
export function KitchenPage() {
  return (
    <PagePlaceholder
      eyebrow="Dapur"
      title="Papan dapur"
      description="Tiket aktif dikelompokkan per tahap: menunggu, dimasak, dan siap kirim."
      upcoming="Papan tiga kolom dengan penanda alergen kritis dan tombol majukan status akan dibangun pada tahap berikutnya."
      cards={[
        {
          icon: ChefHat,
          title: 'Belum ada tiket aktif',
          description: 'Tiket yang masuk akan tampil per kolom mengikuti alur fulfilment.',
        },
        {
          icon: ShieldAlert,
          title: 'Tiket kritis',
          description:
            'Pesanan dengan alergen kritis didahulukan, dengan daftar bahan dan equipment yang wajib dipisah.',
        },
      ]}
    />
  )
}