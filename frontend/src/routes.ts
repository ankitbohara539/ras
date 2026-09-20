import { lazy } from 'react'

/**
 * Pages loaded on demand, and the preloading that makes that invisible.
 *
 * Everything used to ship as one ~530 kB bundle, map library included, which
 * every visitor downloaded before the login screen could appear. Now the
 * first screen loads only what it needs, and the rest follows:
 *
 *  - on idle, once the first page has painted, every page's code is fetched
 *    in the background (so navigating later is instant, and works offline --
 *    the service worker caches these chunks too);
 *  - on intent, a nav link's page starts loading when it is hovered, focused
 *    or touched, in case the user is faster than the idle preload.
 *
 * Login, register, home and the dashboard stay in the main bundle: they are
 * the first thing anyone sees.
 */

const loaders = {
  ticketDetail: () => import('./pages/TicketDetail'),
  report: () => import('./pages/citizen/ReportIssue'),
  myReports: () => import('./pages/citizen/MyReports'),
  services: () => import('./pages/citizen/Services'),
  sos: () => import('./pages/citizen/Sos'),
  civic: () => import('./pages/citizen/CivicReport'),
  safeRoute: () => import('./pages/citizen/SafeRoute'),
  notifications: () => import('./pages/Notifications'),
  transparency: () => import('./pages/Transparency'),
  reviewQueue: () => import('./pages/authority/ReviewQueue'),
  sosQueue: () => import('./pages/authority/SosQueue'),
  publishAlert: () => import('./pages/authority/PublishAlert'),
  civicQueue: () => import('./pages/authority/CivicQueue'),
  approvals: () => import('./pages/admin/Approvals'),
  users: () => import('./pages/admin/Users'),
  wards: () => import('./pages/admin/Wards'),
  wardPeople: () => import('./pages/authority/WardPeople'),
  profile: () => import('./pages/Profile'),
}

export const TicketDetailPage = lazy(() => loaders.ticketDetail().then((m) => ({ default: m.TicketDetailPage })))
export const ReportIssue = lazy(() => loaders.report().then((m) => ({ default: m.ReportIssue })))
export const MyReports = lazy(() => loaders.myReports().then((m) => ({ default: m.MyReports })))
export const Services = lazy(() => loaders.services().then((m) => ({ default: m.Services })))
export const Sos = lazy(() => loaders.sos().then((m) => ({ default: m.Sos })))
export const CivicReport = lazy(() => loaders.civic().then((m) => ({ default: m.CivicReport })))
export const SafeRoute = lazy(() => loaders.safeRoute().then((m) => ({ default: m.SafeRoute })))
export const Notifications = lazy(() => loaders.notifications().then((m) => ({ default: m.Notifications })))
export const Transparency = lazy(() => loaders.transparency().then((m) => ({ default: m.Transparency })))
export const ReviewQueue = lazy(() => loaders.reviewQueue().then((m) => ({ default: m.ReviewQueue })))
export const SosQueue = lazy(() => loaders.sosQueue().then((m) => ({ default: m.SosQueue })))
export const PublishAlert = lazy(() => loaders.publishAlert().then((m) => ({ default: m.PublishAlert })))
export const CivicQueue = lazy(() => loaders.civicQueue().then((m) => ({ default: m.CivicQueue })))
export const Approvals = lazy(() => loaders.approvals().then((m) => ({ default: m.Approvals })))
export const UserManagement = lazy(() => loaders.users().then((m) => ({ default: m.UserManagement })))
export const WardManagement = lazy(() => loaders.wards().then((m) => ({ default: m.WardManagement })))
export const WardPeople = lazy(() => loaders.wardPeople().then((m) => ({ default: m.WardPeople })))
export const ProfilePage = lazy(() => loaders.profile().then((m) => ({ default: m.ProfilePage })))

const BY_PATH: [RegExp, () => Promise<unknown>][] = [
  [/^\/tickets\//, loaders.ticketDetail],
  [/^\/report$/, loaders.report],
  [/^\/my-reports$/, loaders.myReports],
  [/^\/services$/, loaders.services],
  [/^\/sos$/, loaders.sos],
  [/^\/civic$/, loaders.civic],
  [/^\/safe-route$/, loaders.safeRoute],
  [/^\/notifications$/, loaders.notifications],
  [/^\/(transparency|public-dashboard)$/, loaders.transparency],
  [/^\/authority\/duplicates$/, loaders.reviewQueue],
  [/^\/authority\/emergencies$/, loaders.sosQueue],
  [/^\/authority\/alerts$/, loaders.publishAlert],
  [/^\/authority\/civic$/, loaders.civicQueue],
  [/^\/admin\/approvals$/, loaders.approvals],
  [/^\/admin\/users$/, loaders.users],
  [/^\/admin\/wards$/, loaders.wards],
  [/^\/authority\/people$/, loaders.wardPeople],
  [/^\/profile$/, loaders.profile],
]

/** Start loading a page's code (hover / focus / touch on a link to it). */
export function preloadRoute(path: string): void {
  const match = BY_PATH.find(([pattern]) => pattern.test(path))
  if (match) match[1]().catch(() => {})
}

let preloaded = false

/**
 * Fetch every page's code once the browser is idle. One at a time, so it
 * never competes with what the user is actually doing.
 */
export function preloadAllRoutes(): void {
  if (preloaded) return
  preloaded = true

  const idle: (cb: () => void) => void =
    'requestIdleCallback' in window
      ? (cb) => window.requestIdleCallback(cb, { timeout: 4000 })
      : (cb) => window.setTimeout(cb, 1500)

  const queue = Object.values(loaders)
  const next = () => {
    const load = queue.shift()
    if (!load) return
    load()
      .catch(() => {})
      .finally(() => idle(next))
  }
  idle(next)
}
