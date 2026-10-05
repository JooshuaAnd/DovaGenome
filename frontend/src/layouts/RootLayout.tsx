import { useEffect, type ReactNode } from 'react'

import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { AuthProvider } from '@/hooks/useAuth'

/**
 * Process-wide providers: auth session, tooltips, and toasts.
 *
 * Every route tree lives inside this layout, so `useAuth`, `toast`, and
 * tooltips are available everywhere without further wrapping.
 */
export function RootLayout({ children }: { children: ReactNode }) {
  useEffect(() => {
    document.title = 'DovaGenome — Precision Catering'
  }, [])

  return (
    <AuthProvider>
      <TooltipProvider delayDuration={200}>
        {children}
        <Toaster position="bottom-right" richColors closeButton />
      </TooltipProvider>
    </AuthProvider>
  )
}