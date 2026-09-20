import { Suspense, useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Bell,
  Building2,
  ChartNoAxesCombined,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  CopyCheck,
  FilePlus2,
  House,
  LogOut,
  MapPin,
  Megaphone,
  Menu,
  Route,
  ShieldCheck,
  Siren,
  Users,
  X,
  type LucideIcon,
} from 'lucide-react'
import { api } from '../lib/api'
import { useQuery } from '../lib/cache'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { preloadAllRoutes, preloadRoute } from '../routes'
import { Spinner, Tooltip } from './ui'
import { Brand, DisplayControls } from './Brand'

type NavItem = { to: string; label: string; icon: LucideIcon; end?: boolean }

export function Layout() {
  const { t, language } = useI18n()
  const { profile, signOut, isAuthority, isAdmin } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('sahayatri.sidebar-collapsed') === '1' } catch { return false }
  })
  const drawer = useRef<HTMLDialogElement>(null)
  const menuButton = useRef<HTMLButtonElement>(null)
  const { data: badge } = useQuery(
    profile ? `notifications:unread:${profile.id}` : null,
    () => api.notifications(true),
    { refetchIntervalMs: 30_000 },
  )
  const unread = badge?.unread ?? 0
  const text = (en: string, ne: string) => (language === 'ne' ? ne : en)
  useEffect(() => {
    preloadAllRoutes()
  }, [])
  useEffect(() => {
    try { localStorage.setItem('sahayatri.sidebar-collapsed', collapsed ? '1' : '0') } catch { /* preference remains in memory */ }
  }, [collapsed])
  useEffect(() => {
    if (menuOpen) {
      drawer.current?.showModal()
      const previous = document.body.style.overflow
      document.body.style.overflow = 'hidden'
      return () => {
        document.body.style.overflow = previous
      }
    }
    drawer.current?.close()
  }, [menuOpen])

  const citizen: NavItem[] = [
    { to: '/', label: t('nav.home'), icon: House, end: true },
    { to: '/report', label: t('nav.report'), icon: FilePlus2 },
    { to: '/my-reports', label: t('nav.myReports'), icon: ClipboardList },
    { to: '/civic', label: t('nav.civic'), icon: Users },
  ]
  const explore: NavItem[] = [
    { to: '/nearby', label: t('nav.nearby'), icon: MapPin },
    ...(!isAuthority ? [{ to: '/safe-route', label: t('nav.safeRoute'), icon: Route }] : []),
    { to: '/services', label: t('nav.services'), icon: Building2 },
  ]
  const authority: NavItem[] = [
    {
      to: '/authority',
      label: t('nav.dashboard'),
      icon: ChartNoAxesCombined,
      end: true,
    },
    {
      to: '/authority/duplicates',
      label: t('nav.reviewQueue'),
      icon: CopyCheck,
    },
    { to: '/authority/civic', label: t('nav.civicQueue'), icon: Users },
    { to: '/authority/alerts', label: t('nav.publishAlert'), icon: Megaphone },
    ...(isAdmin
      ? [
          {
            to: '/admin/approvals',
            label: t('nav.approvals'),
            icon: ShieldCheck,
          },
        ]
      : []),
  ]
  const emergency: NavItem = {
    to: isAuthority ? '/authority/emergencies' : '/sos',
    label: t(isAuthority ? 'nav.sosQueue' : 'nav.sos'),
    icon: Siren,
  }
  const groups = [
    {
      label: text('Workspace', 'कार्यस्थल'),
      items: isAuthority ? authority : citizen,
    },
    {
      label: text('Explore your community', 'समुदाय हेर्नुहोस्'),
      items: [
        ...explore,
        {
          to: '/public-dashboard',
          label: t('transparency.title'),
          icon: ChartNoAxesCombined,
        },
      ],
    },
    {
      label: text('Safety & updates', 'सुरक्षा र सूचना'),
      items: [
        emergency,
        { to: '/notifications', label: t('nav.notifications'), icon: Bell },
      ],
    },
  ]
  const current = groups
    .flatMap((g) => g.items)
    .find((i) => i.to === location.pathname)
  const mobile = isAuthority
    ? [authority[0], authority[1], emergency, authority[2], authority[3]]
    : [citizen[0], explore[0], citizen[1], explore[2], emergency]
  const closeMenu = () => {
    setMenuOpen(false)
    menuButton.current?.focus()
  }
  const logout = () => {
    setMenuOpen(false)
    signOut()
    navigate('/login')
  }
  const navigation = (compact = false) => (
    <>
      <div className="space-y-6 px-3 py-6">
        {groups.map((group) => (
          <section key={group.label}>
            <h2 className={compact ? 'mx-3 my-3 border-t border-line text-[0px]' : 'section-label mb-2 px-3'}>{group.label}</h2>
            <div className="space-y-1">
              {group.items.map(({ icon: Icon, ...item }) => (
                <Tooltip key={item.to} content={item.label}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  className={compact ? 'nav-link justify-center px-0' : 'nav-link'}
                  onClick={() => setMenuOpen(false)}
                  onMouseEnter={() => preloadRoute(item.to)}
                  onFocus={() => preloadRoute(item.to)}
                >
                  <Icon aria-hidden="true" />
                  <span className={compact ? 'sr-only' : ''}>{item.label}</span>
                </NavLink>
                </Tooltip>
              ))}
            </div>
          </section>
        ))}
      </div>
      <div className={compact ? 'mt-auto space-y-2 border-t border-line p-2' : 'mt-auto space-y-2 border-t border-line p-4'}>
        <div className="mb-3 flex items-center gap-3">
          <span className="icon-tile font-semibold">
            {profile?.full_name?.slice(0, 1)}
          </span>
          <div className={compact ? 'sr-only' : 'min-w-0'}>
            <p className="truncate text-sm font-semibold">
              {profile?.full_name}
            </p>
            <p className="hint">
              {isAdmin
                ? text('Administrator', 'प्रशासक')
                : isAuthority
                  ? text('Authority workspace', 'अधिकारी कार्यस्थल')
                  : text('Citizen account', 'नागरिक खाता')}
            </p>
          </div>
        </div>
        <Tooltip content={t('nav.logout')}>
          <button
            type="button"
            className={compact ? 'btn btn-secondary w-full px-0' : 'btn btn-secondary w-full'}
            onClick={logout}
          >
            <LogOut size={16} />
            <span className={compact ? 'sr-only' : ''}>{t('nav.logout')}</span>
          </button>
        </Tooltip>
      </div>
    </>
  )
  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-surface focus:p-3"
      >
        {text('Skip to content', 'मुख्य सामग्रीमा जानुहोस्')}
      </a>
      <aside className={`fixed inset-y-0 left-0 z-40 hidden flex-col overflow-visible border-r border-line bg-surface shadow-[8px_0_30px_rgba(29,41,61,0.035)] transition-[width] duration-300 ease-out lg:flex ${collapsed ? 'w-20' : 'w-64'}`}>
        <div className={`flex min-h-20 items-center border-b border-line ${collapsed ? 'justify-center px-2' : 'px-4'}`}>
          <Brand compact={collapsed} />
          <Tooltip content={collapsed ? text('Expand sidebar', 'साइडबार खोल्नुहोस्') : text('Collapse sidebar', 'साइडबार बन्द गर्नुहोस्')}>
            <button type="button" className="absolute -right-3 top-7 z-10 flex size-7 items-center justify-center rounded-full border border-line bg-surface text-ink-soft shadow-sm transition-colors hover:border-brand hover:text-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand" onClick={() => setCollapsed(value => !value)} aria-label={collapsed ? text('Expand sidebar', 'साइडबार खोल्नुहोस्') : text('Collapse sidebar', 'साइडबार बन्द गर्नुहोस्')}>
              {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
            </button>
          </Tooltip>
        </div>
        <div className="sidebar-scroll flex min-h-0 flex-1 flex-col overflow-y-auto">
          {navigation(collapsed)}
        </div>
      </aside>
      <div className={`transition-[padding] duration-300 ease-out ${collapsed ? 'lg:pl-20' : 'lg:pl-64'}`}>
        <header className="sticky top-0 z-30 border-b border-line bg-surface/95 shadow-[0_1px_8px_rgba(29,41,61,0.035)] backdrop-blur-md">
          <div className="flex min-h-20 items-center justify-between gap-3 px-4 sm:px-6 lg:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <button
                ref={menuButton}
                type="button"
                className="btn btn-secondary px-3 lg:hidden"
                onClick={() => setMenuOpen(true)}
                aria-label={t('nav.menu')}
                aria-expanded={menuOpen}
                aria-controls="mobile-navigation"
              >
                <Menu size={20} />
              </button>
              <span className="lg:hidden">
                <Brand />
              </span>
              <div className="hidden items-center gap-2 text-sm text-ink-soft lg:flex">
                <span>{text('Workspace', 'कार्यस्थल')}</span>
                <ChevronRight size={14} />
                <span className="font-medium text-ink">
                  {current?.label ?? text('Report details', 'उजुरी विवरण')}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="hidden sm:block">
                <DisplayControls />
              </div>
              <NavLink
                to="/notifications"
                className="btn btn-secondary relative px-3"
                aria-label={`${t('nav.notifications')} (${unread})`}
              >
                <Bell size={19} />
                {unread > 0 && (
                  <span className="absolute -right-1 -top-1 rounded-full bg-danger px-1.5 text-xs text-white">
                    {unread > 9 ? '9+' : unread}
                  </span>
                )}
              </NavLink>
            </div>
          </div>
        </header>
        <main
          id="main"
          className="mx-auto max-w-[1440px] px-4 py-6 pb-28 sm:px-6 lg:px-8 lg:py-8 lg:pb-10"
        >
          <Suspense fallback={<Spinner />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
      <dialog
        id="mobile-navigation"
        ref={drawer}
        onCancel={closeMenu}
        onClose={() => setMenuOpen(false)}
        aria-labelledby="mobile-menu-title"
        className="fixed inset-y-0 left-0 m-0 h-dvh max-h-none w-[min(88vw,340px)] max-w-none border-0 bg-surface p-0 text-ink backdrop:bg-navy/40"
        onClick={(event) => {
          if (
            event.target === event.currentTarget &&
            event.clientX > event.currentTarget.getBoundingClientRect().right
          )
            closeMenu()
        }}
      >
        <div className="flex min-h-full flex-col">
          <div className="flex items-center justify-between border-b border-line p-4">
            <h2 id="mobile-menu-title" className="font-semibold">
              {t('nav.menu')}
            </h2>
            <button
              type="button"
              className="btn btn-ghost px-3"
              aria-label={text('Close menu', 'मेनु बन्द गर्नुहोस्')}
              onClick={closeMenu}
            >
              <X size={20} />
            </button>
          </div>
          <div className="border-b border-line px-4">
            <DisplayControls />
          </div>
          {navigation(false)}
        </div>
      </dialog>
      <nav
        aria-label={text('Primary navigation', 'मुख्य नेभिगेसन')}
        className="fixed inset-x-0 bottom-0 z-40 flex border-t border-line bg-surface px-1 lg:hidden"
        style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
      >
        {mobile.map(({ icon: Icon, ...item }) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `flex min-h-[68px] min-w-0 flex-1 flex-col items-center justify-center gap-1 px-1 text-center ${isActive ? 'font-semibold text-brand' : 'text-ink-soft'}`
            }
          >
            <span
              className={
                item.to === '/report'
                  ? 'rounded-lg bg-brand p-2 text-white'
                  : 'p-1'
              }
            >
              <Icon size={20} aria-hidden="true" />
            </span>
            <span className="text-[10px] leading-tight">{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
