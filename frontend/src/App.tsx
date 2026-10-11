import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { toast } from 'sonner'

import { useAuth } from '@/hooks/useAuth'
import { RootLayout } from '@/layouts/RootLayout'
import { PortalLayout } from '@/layouts/PortalLayout'
import { AiPage } from '@/pages/AiPage'
import { InvoicePage } from '@/pages/InvoicePage'
import { LandingPage } from '@/pages/LandingPage'
import { LoginPage } from '@/pages/LoginPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { OrderDetailPage } from '@/pages/OrderDetailPage'
import { OrderPage } from '@/pages/OrderPage'
import { OrdersPage } from '@/pages/OrdersPage'
import { PassportPage } from '@/pages/PassportPage'
import { AdminDashboardPage } from '@/pages/admin/AdminDashboardPage'
import { SupplierPage } from '@/pages/supplier/SupplierPage'
import type { Role } from '@/types'

/* ── Route guards ────────────────────────────────────────────────────────── */

/**
 * Guard for any authenticated role.
 *
 * While the stored token is being validated nothing is redirected — otherwise a
 * refresh on a guarded page would bounce the user to `/login` before the session
 * had a chance to restore.
 */
function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') return null

  if (status === 'anonymous') {
    const next = `${location.pathname}${location.search}`
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
  }

  return <>{children}</>
}

/**
 * Guard for role-restricted areas (admin, kitchen).
 *
 * A wrong role is bounced home with an explanatory toast, so the redirect is
 * never silent.
 */
function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { status, hasRole } = useAuth()
  const location = useLocation()

  if (status === 'loading') return null

  if (status === 'anonymous') {
    const next = `${location.pathname}${location.search}`
    return <Navigate to={`/login?next=${encodeURIComponent(next)}`} replace />
  }

  if (!hasRole(...roles)) {
    toast.error('Akses ditolak', {
      description: `Bagian ini hanya untuk peran: ${roles.join(' atau ')}.`,
    })
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}

void RequireAuth
void RequireRole

/** Customer-facing screens share the portal shell. */
function PortalRoute({ children }: { children: ReactNode }) {
  return <PortalLayout>{children}</PortalLayout>
}

/* ── Route table ─────────────────────────────────────────────────────────── */

export function AppRoutes() {
  return (
    <Routes>
      {/* Public Food Ordering Experience (Bitepoint/KFC-inspired Modern App) */}
      <Route path="/" element={<OrderPage />} />
      <Route path="/order" element={<OrderPage />} />
      <Route path="/menu" element={<OrderPage />} />
      <Route path="/landing" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />

      {/* Customer Portal */}
      <Route
        path="/passport"
        element={
          <PortalRoute>
            <PassportPage />
          </PortalRoute>
        }
      />
      <Route
        path="/orders"
        element={
          <PortalRoute>
            <OrdersPage />
          </PortalRoute>
        }
      />
      <Route
        path="/orders/:id"
        element={
          <PortalRoute>
            <OrderDetailPage />
          </PortalRoute>
        }
      />
      <Route
        path="/orders/:id/invoice"
        element={
          <PortalRoute>
            <InvoicePage />
          </PortalRoute>
        }
      />
      <Route
        path="/ai"
        element={
          <PortalRoute>
            <AiPage />
          </PortalRoute>
        }
      />

      {/* Admin and Unified Kitchen Portal (Bitepoint POS / KDS Style) */}
      <Route path="/admin" element={<AdminDashboardPage />} />
      <Route path="/kitchen" element={<AdminDashboardPage />} />
      <Route path="/supplier" element={<SupplierPage />} />

      {/* Redirect removed Daily Menu back to Admin POS */}
      <Route path="/admin/daily-menu" element={<Navigate to="/admin" replace />} />
      <Route path="/admin/daily-menu/*" element={<Navigate to="/admin" replace />} />

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <RootLayout>
        <AppRoutes />
      </RootLayout>
    </BrowserRouter>
  )
}