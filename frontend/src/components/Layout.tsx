import { useEffect, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { usePrefs } from '../lib/prefs'

type NavItem = { to: string; label: string; icon: string; end?: boolean }

function AccessibilityBar() {
  const { t, language, setLanguage } = useI18n()
  const { largeText, highContrast, setLargeText, setHighContrast } = usePrefs()

  return (
    <div
      className="border-b"
      style={{ background: 'var(--color-brand-ink)', borderColor: 'transparent' }}
    >
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-end gap-2 px-4 py-1.5">
        <div
          className="flex items-center gap-1 rounded-full p-0.5"
          style={{ background: 'rgba(255,255,255,0.14)' }}
          role="group"
          aria-label={t('a11y.language')}
        >
          {(['en', 'ne'] as const).map((code) => (
            <button
              key={code}
              type="button"
              onClick={() => setLanguage(code)}
              aria-pressed={language === code}
              className="rounded-full px-3 py-1 font-semibold"
              style={{
                fontSize: 'var(--step-xs)',
                background: language === code ? '#ffffff' : 'transparent',
                color: language === code ? 'var(--color-brand-ink)' : '#ffffff',
              }}
            >
              {code === 'en' ? 'English' : 'नेपाली'}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={() => setLargeText(!largeText)}
          aria-pressed={largeText}
          className="rounded-full px-3 py-1 font-semibold"
          style={{
            fontSize: 'var(--step-xs)',
            background: largeText ? '#ffffff' : 'rgba(255,255,255,0.14)',
            color: largeText ? 'var(--color-brand-ink)' : '#ffffff',
          }}
        >
          <span aria-hidden="true">A+</span> {t('a11y.largeText')}
        </button>

        <button
          type="button"
          onClick={() => setHighContrast(!highContrast)}
          aria-pressed={highContrast}
          className="rounded-full px-3 py-1 font-semibold"
          style={{
            fontSize: 'var(--step-xs)',
            background: highContrast ? '#ffffff' : 'rgba(255,255,255,0.14)',
            color: highContrast ? 'var(--color-brand-ink)' : '#ffffff',
          }}
        >
          <span aria-hidden="true">◐</span> {t('a11y.highContrast')}
        </button>
      </div>
    </div>
  )
}

export function Layout() {
  const { t } = useI18n()
  const { profile, signOut, isAuthority, isAdmin } = useAuth()
  const navigate = useNavigate()
  const [unread, setUnread] = useState(0)
  const [menuOpen, setMenuOpen] = useState(false)

  // Poll for notifications. Supabase Realtime would need RLS policies that
  // duplicate the backend's ward rules; a 30s poll keeps one source of truth.
  useEffect(() => {
    if (!profile) return

    let cancelled = false
    const tick = async () => {
      try {
        const result = await api.notifications(true)
        if (!cancelled) setUnread(result.unread)
      } catch {
        // Offline or expired token; the next tick retries.
      }
    }

    void tick()
    const timer = setInterval(tick, 30_000)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [profile])

  const citizenNav: NavItem[] = [
    { to: '/', label: t('nav.home'), icon: '🏠', end: true },
    { to: '/report', label: t('nav.report'), icon: '📝' },
    { to: '/nearby', label: t('nav.nearby'), icon: '📍' },
    { to: '/services', label: t('nav.services'), icon: '🏥' },
    { to: '/sos', label: t('nav.sos'), icon: '🆘' },
  ]

  const authorityNav: NavItem[] = [
    { to: '/authority', label: t('nav.dashboard'), icon: '📊', end: true },
    { to: '/authority/duplicates', label: t('nav.reviewQueue'), icon: '🔗' },
    { to: '/authority/emergencies', label: t('nav.sosQueue'), icon: '🆘' },
    { to: '/authority/alerts', label: t('nav.publishAlert'), icon: '📢' },
  ]

  const items = isAuthority ? authorityNav : citizenNav
  if (isAdmin) {
    items.push({ to: '/admin/approvals', label: t('nav.approvals'), icon: '✅' })
  }

  const handleSignOut = () => {
    signOut()
    navigate('/login')
  }

  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-white focus:px-4 focus:py-2"
      >
        Skip to content
      </a>

      <AccessibilityBar />

      <header
        className="sticky top-0 z-40 border-b"
        style={{ background: 'var(--color-surface)', borderColor: 'var(--color-line)' }}
      >
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3">
          <NavLink to="/" className="flex items-center gap-2 font-bold">
            <span
              className="flex h-9 w-9 items-center justify-center rounded-lg font-bold text-white"
              style={{ background: 'var(--color-brand)' }}
              aria-hidden="true"
            >
              स
            </span>
            <span style={{ fontSize: 'var(--step-lg)' }}>{t('app.name')}</span>
          </NavLink>

          <nav className="ml-auto hidden items-center gap-1 md:flex">
            {items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className="rounded-lg px-3 py-2 font-medium"
                style={({ isActive }) => ({
                  fontSize: 'var(--step-sm)',
                  background: isActive ? 'var(--color-brand-soft)' : 'transparent',
                  color: isActive ? 'var(--color-brand-ink)' : 'var(--color-ink-soft)',
                })}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2 md:ml-0">
            <NavLink
              to="/notifications"
              className="relative rounded-lg px-2 py-2"
              aria-label={`${t('nav.notifications')}${unread ? ` (${unread})` : ''}`}
            >
              <span aria-hidden="true" style={{ fontSize: 'var(--step-lg)' }}>
                🔔
              </span>
              {unread > 0 && (
                <span
                  className="absolute -right-0.5 -top-0.5 flex h-5 min-w-5 items-center justify-center rounded-full px-1 font-bold text-white"
                  style={{ background: 'var(--color-danger)', fontSize: '0.7rem' }}
                >
                  {unread > 9 ? '9+' : unread}
                </span>
              )}
            </NavLink>

            <button
              type="button"
              className="btn btn-secondary hidden md:inline-flex"
              onClick={handleSignOut}
              style={{ minHeight: '38px' }}
            >
              {t('nav.logout')}
            </button>

            <button
              type="button"
              className="btn btn-secondary md:hidden"
              onClick={() => setMenuOpen((open) => !open)}
              aria-expanded={menuOpen}
              aria-label={t('nav.menu')}
              style={{ minHeight: '38px', padding: '0 0.7rem' }}
            >
              ☰
            </button>
          </div>
        </div>

        {menuOpen && (
          <nav
            className="border-t px-4 py-2 md:hidden"
            style={{ borderColor: 'var(--color-line)' }}
          >
            {items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={() => setMenuOpen(false)}
                className="flex items-center gap-3 rounded-lg px-3 py-3"
                style={({ isActive }) => ({
                  background: isActive ? 'var(--color-brand-soft)' : 'transparent',
                  color: isActive ? 'var(--color-brand-ink)' : 'var(--color-ink)',
                })}
              >
                <span aria-hidden="true">{item.icon}</span>
                {item.label}
              </NavLink>
            ))}
            <button
              type="button"
              onClick={handleSignOut}
              className="mt-1 flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left"
            >
              <span aria-hidden="true">🚪</span>
              {t('nav.logout')}
            </button>
          </nav>
        )}
      </header>

      <main id="main" className="mx-auto max-w-6xl px-4 py-6 pb-28 md:pb-10">
        <Outlet />
      </main>

      {/* Bottom bar on phones: thumb-reachable, which matters for SOS. */}
      <nav
        className="fixed inset-x-0 bottom-0 z-40 border-t md:hidden"
        style={{
          background: 'var(--color-surface)',
          borderColor: 'var(--color-line)',
          paddingBottom: 'env(safe-area-inset-bottom, 0px)',
        }}
      >
        <div className="flex">
          {items.slice(0, 5).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className="flex flex-1 flex-col items-center justify-center gap-0.5 py-2"
              style={({ isActive }) => ({
                minHeight: 'var(--tap)',
                color: isActive ? 'var(--color-brand)' : 'var(--color-ink-faint)',
                fontWeight: isActive ? 700 : 500,
              })}
            >
              <span aria-hidden="true" style={{ fontSize: '1.15rem' }}>
                {item.icon}
              </span>
              <span style={{ fontSize: '0.7rem' }}>{item.label}</span>
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}
