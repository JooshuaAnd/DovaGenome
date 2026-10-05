import { MessagesSquare, Sparkles } from 'lucide-react'

import { PagePlaceholder } from '@/components/common/PagePlaceholder'

/**
 * AI assistant. Safety decisions stay deterministic on the backend — the model
 * only explains them (`app/api/routers/ai.py`).
 */
export function AiPage() {
  return (
    <PagePlaceholder
      eyebrow="Asisten"
      title="Asisten AI"
      description="Tanya tentang menu, batasan dietary, atau cara kerja dapur kami."
      upcoming="Sesi chat akan memakai POST /ai/consult, dan saran menu memakai POST /ai/menu-suggestion."
      cards={[
        {
          icon: MessagesSquare,
          title: 'Percakapan',
          description: 'Riwayat chat tersimpan per sesi, dengan jawaban singkat dalam Bahasa Indonesia.',
        },
        {
          icon: Sparkles,
          title: 'Saran menu aman',
          description:
            'Saran hari mana yang aman — keputusan aman / tidak aman tetap dihitung di backend, bukan oleh model.',
        },
      ]}
    />
  )
}