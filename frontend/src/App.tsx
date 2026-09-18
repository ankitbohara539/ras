import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Spinner } from './components/ui'
import { AuthProvider, useAuth } from './lib/auth'
import { I18nProvider } from './lib/i18n'
import { PrefsProvider } from './lib/prefs'
import { Approvals } from './pages/admin/Approvals'
import { AuthorityDashboard } from './pages/authority/Dashboard'
import { PublishAlert } from './pages/authority/PublishAlert'
import { ReviewQueue } from './pages/authority/ReviewQueue'
import { SosQueue } from './pages/authority/SosQueue'
import { CitizenHome } from './pages/citizen/Home'
import { MyReports } from './pages/citizen/MyReports'
import { Nearby } from './pages/citizen/Nearby'
import { ReportIssue } from './pages/citizen/ReportIssue'
import { Services } from './pages/citizen/Services'
import { Sos } from './pages/citizen/Sos'
import { Login } from './pages/Login'
import { Notifications } from './pages/Notifications'
import { Register } from './pages/Register'
import { TicketDetailPage } from './pages/TicketDetail'

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
        <BrowserRouter>
          <AuthProvider>
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

              <Route
                element={
                  <RequireAuth>
                    <Layout />
                  </RequireAuth>
                }
              >
                <Route index element={<HomeRedirect />} />
                <Route path="report" element={<ReportIssue />} />
                <Route path="my-reports" element={<MyReports />} />
                <Route path="nearby" element={<Nearby />} />
                <Route path="services" element={<Services />} />
                <Route path="sos" element={<Sos />} />
                <Route path="notifications" element={<Notifications />} />
                <Route path="tickets/:id" element={<TicketDetailPage />} />

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
              </Route>

              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </AuthProvider>
        </BrowserRouter>
      </PrefsProvider>
    </I18nProvider>
  )
}
