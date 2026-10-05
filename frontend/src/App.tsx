import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { toast } from 'sonner'

import { useAuth } from '@/hooks/useAuth'
import { AdminLayout } from '@/layouts/AdminLayout'
import { KitchenLayout } from '@/layouts/KitchenLayout'
import { RootLayout } from '@/layouts/RootLayout'
import { PortalLayout } from '@/layouts/PortalLayout'
import { AiPage } from '@/pages/AiPage'
import { InvoicePage } from '@/pages/InvoicePage'
import { LandingPage } from '@/pages/LandingPage'
import { LoginPage } from '@/pages/LoginPage'
import { MenuPage } from '@/pages/MenuPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { OrderDetailPage } from '@/pages/OrderDetailPage'
import { OrderPage } from '@/pages/OrderPage'
import { OrdersPage } from '@/pages/OrdersPage'
import { PassportPage } from '@/pages/PassportPage'
import { AdminDashboardPage } from '@/pages/admin/AdminDashboardPage'
import { DailyMenuEditorPage } from '@/pages/admin/DailyMenuEditorPage'
import { DailyMenuPage } from '@/pages/admin/DailyMenuPage'
import { KitchenPage } from '@/pages/kitchen/KitchenPage'
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

/** Customer-facing screens share the portal shell. */
function PortalRoute({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <PortalLayout>{children}</PortalLayout>
    </RequireAuth>
  )
}

/* ── Route table ─────────────────────────────────────────────────────────── */

export function AppRoutes() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/" element={<LandingPage />} />
      <Route path="/menu" element={<MenuPage />} />
      <Route path="/login" element={<LoginPage />} />

      {/* Customer — any authenticated role */}
      <Route
        path="/passport"
        element={
          <PortalRoute>
            <PassportPage />
          </PortalRoute>
        }
      />
      <Route
        path="/order"
        element={
          <PortalRoute>
            <OrderPage />
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

      {/* Admin only */}
      <Route
        path="/admin"
        element={
          <RequireRole roles={['admin']}>
            <AdminLayout>
              <AdminDashboardPage />
            </AdminLayout>
          </RequireRole>
        }
      />
      <Route
        path="/admin/daily-menu"
        element={
          <RequireRole roles={['admin']}>
            <AdminLayout title="Menu harian">
              <DailyMenuPage />
            </AdminLayout>
          </RequireRole>
        }
      />
      <Route
        path="/admin/daily-menu/:id"
        element={
          <RequireRole roles={['admin']}>
            <AdminLayout title="Editor menu harian">
              <DailyMenuEditorPage />
            </AdminLayout>
          </RequireRole>
        }
      />
      {/* Editing one option of a day - the day is fixed, the option is addressed by menu_id. */}
      <Route
        path="/admin/daily-menu/:id/:menuId"
        element={
          <RequireRole roles={['admin']}>
            <AdminLayout title="Editor pilihan menu">
              <DailyMenuEditorPage />
            </AdminLayout>
          </RequireRole>
        }
      />

      {/* Kitchen — admin or kitchen role */}
      <Route
        path="/kitchen"
        element={
          <RequireRole roles={['admin', 'kitchen']}>
            <KitchenLayout title="Papan dapur">
              <KitchenPage />
            </KitchenLayout>
          </RequireRole>
        }
      />

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