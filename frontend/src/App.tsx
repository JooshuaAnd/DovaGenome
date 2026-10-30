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
import { AdminDashboardPage } from '@/pages/admin/AdminDashboardPage'
import { RecipeReviewPage } from '@/pages/admin/RecipeReviewPage'
import { AdminLayout } from '@/layouts/AdminLayout'
import { SupplierPage } from '@/pages/supplier/SupplierPage'
import { DailyMenuPage } from '@/pages/admin/DailyMenuPage'
import { DailyMenuEditorPage } from '@/pages/admin/DailyMenuEditorPage'
import { AdminCustomersPage } from '@/pages/admin/AdminCustomersPage'
import { ProductionBatchesPage } from '@/pages/admin/ProductionBatchesPage'
import { DeliveryAdminPage } from '@/pages/admin/DeliveryAdminPage'
import { AdminCampaignsPage } from '@/pages/admin/AdminCampaignsPage'
import { MenuDemandPage } from '@/pages/admin/MenuDemandPage'
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
      {/* Customer menu, chat, profile, and order history share phone sign-in. */}
      <Route path="/" element={<PortalRoute><OrderPage /></PortalRoute>} />
      <Route path="/order" element={<PortalRoute><OrderPage /></PortalRoute>} />
      <Route path="/menu" element={<PortalRoute><OrderPage /></PortalRoute>} />
      <Route path="/landing" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />

      {/* Customer Portal */}
      {/* Dietary Passport is intentionally a modal from the menu shell. */}
      <Route path="/passport" element={<Navigate to="/order?passport=1" replace />} />
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
      <Route
        path="/admin"
        element={
          <RequireRole roles={['admin']}>
            <AdminDashboardPage />
          </RequireRole>
        }
      />
      <Route
        path="/kitchen"
        element={
          <RequireRole roles={['admin', 'kitchen']}>
            <AdminDashboardPage />
          </RequireRole>
        }
      />
      <Route
        path="/admin/recipes"
        element={
          <RequireRole roles={['admin']}>
            <AdminLayout title="Recipe Verification">
              <RecipeReviewPage />
            </AdminLayout>
          </RequireRole>
        }
      />
      <Route
        path="/supplier"
        element={
          <RequireRole roles={['supplier']}>
            <SupplierPage />
          </RequireRole>
        }
      />

      <Route path="/admin/daily-menu" element={<RequireRole roles={['admin']}><AdminLayout title="Menu mingguan"><DailyMenuPage /></AdminLayout></RequireRole>} />
      <Route path="/admin/menu-demand" element={<RequireRole roles={['admin']}><AdminLayout title="Menu & rekomendasi"><MenuDemandPage /></AdminLayout></RequireRole>} />
      <Route path="/admin/daily-menu/:id/:menuId?" element={<RequireRole roles={['admin']}><AdminLayout title="Editor menu"><DailyMenuEditorPage /></AdminLayout></RequireRole>} />
      <Route path="/admin/customers" element={<RequireRole roles={['admin']}><AdminLayout title="Pelanggan"><AdminCustomersPage /></AdminLayout></RequireRole>} />
      <Route path="/admin/production" element={<RequireRole roles={['admin', 'kitchen']}><AdminLayout title="Batch produksi"><ProductionBatchesPage /></AdminLayout></RequireRole>} />
      <Route path="/admin/delivery" element={<RequireRole roles={['admin']}><AdminLayout title="Pengiriman"><DeliveryAdminPage /></AdminLayout></RequireRole>} />
      <Route path="/admin/campaigns" element={<RequireRole roles={['admin']}><AdminLayout title="Kampanye CRM"><AdminCampaignsPage /></AdminLayout></RequireRole>} />

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
