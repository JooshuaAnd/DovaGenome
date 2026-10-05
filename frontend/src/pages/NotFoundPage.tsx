import { FileQuestion } from 'lucide-react'
import { Link } from 'react-router-dom'

import { EmptyState } from '@/components/common/EmptyState'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'

/** Catch-all 404 route. */
export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-2xl py-10">
      <PageHeader
        eyebrow="404"
        title="Halaman tidak ditemukan"
        description="Alamat yang kamu buka tidak ada di aplikasi ini, atau sudah dipindahkan."
      />

      <EmptyState
        className="mt-6"
        icon={FileQuestion}
        title="Tidak ada apa-apa di sini"
        description="Periksa kembali tautannya, atau kembali ke beranda untuk melanjutkan."
        size="lg"
        action={
          <Button asChild>
            <Link to="/">Kembali ke beranda</Link>
          </Button>
        }
      />
    </div>
  )
}