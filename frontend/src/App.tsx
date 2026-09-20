import { Suspense, type ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Toaster } from 'sonner'
import { Layout } from './components/Layout'
import { PwaPrompts } from './components/PwaPrompts'
import { Spinner, TooltipProvider } from './components/ui'
import { AuthProvider, useAuth } from './lib/auth'
import { I18nProvider } from './lib/i18n'
import { PrefsProvider } from './lib/prefs'
import { AuthorityDashboard } from './pages/authority/Dashboard'
import { CitizenHome } from './pages/citizen/Home'
import { Login } from './pages/Login'
import { Register } from './pages/Register'
import {
  Approvals,
  CivicQueue,
  CivicReport,
  MyReports,
  Notifications,
  PublishAlert,
  ReportIssue,
  ReviewQueue,
  SafeRoute,
  Services,
  Sos,
  SosQueue,
  TicketDetailPage,
  Transparency,
  UserManagement,
  WardManagement,
  WardPeople,
  ProfilePage,
} from './routes'

function RequireAuth({
  children,
  role,
}: {
  children: ReactNode
  role?: 'authority' | 'admin'
}) {
  const { profile, loading, isAuthority, isAdmin } = useAuth()

  if (loading) return <Spinner />
  if (!profile) return <Navigate to="/login" replace />

  // Guarding here is a convenience, not the security boundary -- the API
  // enforces the same rules, because anything in the browser can be edited.
  if (role === 'admin' && !isAdmin) return <Navigate to="/" replace />
  if (role === 'authority' && !isAuthority) return <Navigate to="/" replace />

  return <>{children}</>
}

function HomeRedirect() {
  const { isAuthority } = useAuth()
  return isAuthority ? <Navigate to="/authority" replace /> : <CitizenHome />
}

function RequireCitizen({ children }: { children: ReactNode }) {
  const { profile, loading, isCitizen } = useAuth()
  if (loading) return <Spinner />
  if (!profile) return <Navigate to="/login" replace />
  if (!isCitizen) return <Navigate to="/authority" replace />
  return <>{children}</>
}

function HomeEntry() {
  const { profile, loading } = useAuth()
  if (loading) return <Spinner />
  return profile ? (
    <Layout />
  ) : (
    <Suspense fallback={<Spinner />}>
      <Transparency />
    </Suspense>
  )
}

function PublicOnly({ children }: { children: ReactNode }) {
  const { profile, loading } = useAuth()

  if (loading) return <Spinner />
  if (profile) {
    return (
      <Navigate to={profile.role === 'citizen' ? '/' : '/authority'} replace />
    )
  }
  return <>{children}</>
}

export default function App() {
  return (
    <I18nProvider>
      <PrefsProvider>
        <TooltipProvider delayDuration={250}>
          <BrowserRouter>
            <AuthProvider>
            <PwaPrompts />
            <Toaster richColors closeButton position="top-right" />
            <Routes>
              <Route
                path="/login"
                element={
                  <PublicOnly>
                    <Login />
                  </PublicOnly>
                }
              />
              <Route
                path="/register"
                element={
                  <PublicOnly>
                    <Register />
                  </PublicOnly>
                }
              />
              {/* No auth, no PublicOnly redirect -- this is the one page meant
                  to be shared with someone who never logs in at all. */}
              <Route
                path="/public-dashboard"
                element={
                  <Suspense fallback={<Spinner />}>
                    <Transparency />
                  </Suspense>
                }
              />

              <Route
                path="/transparency"
                element={<Navigate to="/public-dashboard" replace />}
              />
              <Route path="/" element={<HomeEntry />}>
                <Route index element={<HomeRedirect />} />
              </Route>

              <Route
                element={
                  <RequireAuth>
                    <Layout />
                  </RequireAuth>
                }
              >
                <Route path="report" element={<ReportIssue />} />
                <Route path="my-reports" element={<MyReports />} />
                <Route path="services" element={<Services />} />
                <Route path="sos" element={<Sos />} />
                <Route path="civic" element={<CivicReport />} />
                <Route path="safe-route" element={<RequireCitizen><SafeRoute /></RequireCitizen>} />
                <Route path="notifications" element={<Notifications />} />
                <Route path="tickets/:id" element={<TicketDetailPage />} />
                <Route path="profile" element={<ProfilePage />} />

                <Route
                  path="authority"
                  element={
                    <RequireAuth role="authority">
                      <AuthorityDashboard />
                    </RequireAuth>
                  }
                />
                <Route
                  path="authority/duplicates"
                  element={
                    <RequireAuth role="authority">
                      <ReviewQueue />
                    </RequireAuth>
                  }
                />
                <Route
                  path="authority/emergencies"
                  element={
                    <RequireAuth role="authority">
                      <SosQueue />
                    </RequireAuth>
                  }
                />
                <Route
                  path="authority/civic"
                  element={
                    <RequireAuth role="authority">
                      <CivicQueue />
                    </RequireAuth>
                  }
                />
                <Route path="authority/people" element={<RequireAuth role="authority"><WardPeople /></RequireAuth>} />
                <Route
                  path="authority/alerts"
                  element={
                    <RequireAuth role="authority">
                      <PublishAlert />
                    </RequireAuth>
                  }
                />
                <Route
                  path="admin/approvals"
                  element={
                    <RequireAuth role="admin">
                      <Approvals />
                    </RequireAuth>
                  }
                />
                <Route path="admin/users" element={<RequireAuth role="admin"><UserManagement /></RequireAuth>} />
                <Route path="admin/wards" element={<RequireAuth role="admin"><WardManagement /></RequireAuth>} />
              </Route>

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
            </AuthProvider>
          </BrowserRouter>
        </TooltipProvider>
      </PrefsProvider>
    </I18nProvider>
  )
}
