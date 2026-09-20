import { useEffect, useState } from 'react'
import {
  ChartNoAxesCombined,
  CircleCheckBig,
  ClipboardList,
  CopyCheck,
  Search,
  Siren,
  Sparkles,
} from 'lucide-react'
import { useQuery } from '../../lib/cache'
import { Link } from 'react-router-dom'
import { DashboardSummaryModal } from '../../components/DashboardSummaryModal'
import { TicketCard } from '../../components/TicketCard'
import {
  EmptyState,
  ErrorNote,
  Pagination,
  Skeleton,
  Stat,
} from '../../components/ui'
import { api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { useI18n } from '../../lib/i18n'
import type { MunicipalityDetail, TicketStatus } from '../../lib/types'

const FILTERS: (TicketStatus | 'all')[] = [
  'all',
  'reported',
  'verified',
  'in_progress',
  'resolved',
]
const PAGE_SIZE = 20

export function AuthorityDashboard() {
  const { t, language } = useI18n()
  const { profile, isAdmin } = useAuth()
  const [municipality, setMunicipality] = useState<MunicipalityDetail | null>(
    null,
  )

  // Which area this officer covers, for the heading: an officer switching
  // between accounts (or a demo audience) should never have to guess.
  useEffect(() => {
    if (!profile?.municipality_id) return
    api
      .municipality(profile.municipality_id)
      .then(setMunicipality)
      .catch(() => setMunicipality(null))
  }, [profile?.municipality_id])

  const ward =
    municipality?.wards.find((w) => w.id === profile?.ward_id) ?? null
  const municipalityName = municipality
    ? language === 'ne'
      ? municipality.name_ne
      : municipality.name_en
    : null
  const wardName = ward
    ? language === 'ne'
      ? ward.name_ne
      : ward.name_en
    : null
  const title = ward
    ? `${t('auth.ward')} ${ward.number}${wardName ? ` — ${wardName}` : ''}`
    : municipalityName
      ? `${municipalityName} — ${t('dashboard.allWards')}`
      : isAdmin
        ? t('dashboard.allMunicipalities')
        : t('dashboard.title')
  const subtitle =
    ward && municipalityName
      ? `${municipalityName} · ${t('dashboard.title')}`
      : t('dashboard.title')

  const [filter, setFilter] = useState<TicketStatus | 'all'>('all')
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)
  const [showSummary, setShowSummary] = useState(false)
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(search.trim())
      setPage(0)
    }, 350)
    return () => window.clearTimeout(timer)
  }, [search])

  // Counts are decoration; the list below is the real content. Both come
  // through the cache so returning to the dashboard is instant, and both are
  // refreshed every minute -- this is the page an officer leaves open.
  const countsQuery = useQuery(
    profile ? `dashboard:counts:${profile.id}` : null,
    async () => {
      const [reported, verified, inProgress, resolved, queue, sos] =
        await Promise.all([
          api.tickets({ status: 'reported', limit: 1 }),
          api.tickets({ status: 'verified', limit: 1 }),
          api.tickets({ status: 'in_progress', limit: 1 }),
          api.tickets({ status: 'resolved', limit: 1 }),
          api.reviewQueue(100),
          api.sosList('open'),
        ])
      return {
        open: reported.total + verified.total + inProgress.total,
        duplicates: queue.length,
        sos: sos.length,
        resolved: resolved.total,
      }
    },
    { refetchIntervalMs: 60_000 },
  )
  const counts = countsQuery.data ?? {
    open: 0,
    duplicates: 0,
    sos: 0,
    resolved: 0,
  }

  const listQuery = useQuery(
    profile ? `dashboard:list:${filter}:${query}:${page}:${profile.id}` : null,
    () =>
      api.tickets({
        status: filter === 'all' ? undefined : filter,
        search: query || undefined,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
    { refetchIntervalMs: 60_000 },
  )
  const tickets = listQuery.data?.items ?? []
  const totalPages = Math.ceil((listQuery.data?.total ?? 0) / PAGE_SIZE)
  const loading = listQuery.loading

  return (
    <div className="dashboard-page space-y-6">
      <section className="dashboard-heading p-6 sm:p-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="section-label mb-2">
              {language === 'ne' ? 'अधिकारी कार्यक्षेत्र' : 'Authority operations'}
            </p>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
              {title}
            </h1>
            <p className="mt-1.5 text-sm text-ink-soft">{subtitle}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => setShowSummary(true)}
            >
              <Sparkles size={16} />
              {t('summary.buttonLabel')}
            </button>
            <Link className="btn btn-secondary" to="/public-dashboard">
              <ChartNoAxesCombined size={16} />
              {t('transparency.title')}
            </Link>
          </div>
        </div>
      </section>
      {showSummary && (
        <DashboardSummaryModal onClose={() => setShowSummary(false)} />
      )}
      {countsQuery.error instanceof Error && (
        <ErrorNote message={countsQuery.error.message} />
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          label={t('dashboard.open')}
          value={counts.open}
          icon={<ClipboardList size={18} />}
        />
        <Link to="/authority/duplicates" className="block">
          <Stat
            label={t('dashboard.pendingReview')}
            value={counts.duplicates}
            tone={counts.duplicates > 0 ? 'warn' : 'ink'}
            icon={<CopyCheck size={18} />}
            className="interactive-card"
          />
        </Link>
        <Link to="/authority/emergencies" className="block">
          <Stat
            label={t('dashboard.openSos')}
            value={counts.sos}
            tone={counts.sos > 0 ? 'danger' : 'ink'}
            icon={<Siren size={18} />}
            className="interactive-card"
          />
        </Link>
        <Stat
          label={t('dashboard.resolved')}
          value={counts.resolved}
          tone="good"
          icon={<CircleCheckBig size={18} />}
        />
      </div>

      <section className="dashboard-panel" aria-labelledby="all-reports-title">
        <div className="flex flex-wrap items-center justify-between gap-3 p-5">
          <h2 id="all-reports-title" className="text-lg font-semibold">
            {t('dashboard.allReports')}
          </h2>
          <span className="chip border-line bg-brand-soft text-brand">
            {(listQuery.data?.total ?? 0).toLocaleString(language)}{' '}
            {language === 'ne' ? 'उजुरी' : 'reports'}
          </span>
        </div>

        <div className="dashboard-toolbar flex flex-col gap-3 p-4 sm:p-5 xl:flex-row xl:items-center xl:justify-between">
          <label className="relative block w-full xl:max-w-md">
            <Search
              size={17}
              className="absolute left-3 top-3.5 text-ink-faint"
            />
            <input
              className="field pl-10"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={
                language === 'ne' ? 'उजुरी खोज्नुहोस्…' : 'Search reports…'
              }
              aria-label={
                language === 'ne' ? 'उजुरी खोज्नुहोस्' : 'Search reports'
              }
            />
          </label>
          <div className="flex flex-wrap gap-2">
            {FILTERS.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => {
                  setFilter(option)
                  setPage(0)
                }}
                aria-pressed={filter === option}
                className="chip"
                style={{
                  minHeight: '38px',
                  padding: '0 0.9rem',
                  borderColor:
                    filter === option
                      ? 'var(--color-brand)'
                      : 'var(--color-line)',
                  background:
                    filter === option
                      ? 'var(--color-brand)'
                      : 'var(--color-surface)',
                  color: filter === option ? '#fff' : 'var(--color-ink-soft)',
                }}
              >
                {option === 'all'
                  ? t('dashboard.filterAll')
                  : t(`ticket.${option}` as never)}
              </button>
            ))}
          </div>
        </div>

        <div className="p-4 sm:p-5">
          {listQuery.error instanceof Error ? (
            <ErrorNote message={listQuery.error.message} />
          ) : loading ? (
            <div className="grid gap-3 xl:grid-cols-2" role="status" aria-label={t('common.loading')}>
              {[0, 1, 2, 3].map((item) => <Skeleton key={item} className="h-44" />)}
            </div>
          ) : tickets.length === 0 ? (
            <EmptyState title={t('ticket.none')} />
          ) : (
            <>
              <div className="grid gap-3 xl:grid-cols-2">
                {tickets.map((ticket) => (
                  <TicketCard key={ticket.id} ticket={ticket} showPriority />
                ))}
              </div>
              <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
            </>
          )}
        </div>
      </section>
    </div>
  )
}
