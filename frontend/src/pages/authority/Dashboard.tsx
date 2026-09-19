import { useEffect, useState } from 'react'
import { useQuery } from '../../lib/cache'
import { Link } from 'react-router-dom'
import { DashboardSummaryModal } from '../../components/DashboardSummaryModal'
import { TicketCard } from '../../components/TicketCard'
import { Button, EmptyState, PageTitle, Spinner, Stat } from '../../components/ui'
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

export function AuthorityDashboard() {
  const { t, language } = useI18n()
  const { profile, isAdmin } = useAuth()
  const [municipality, setMunicipality] = useState<MunicipalityDetail | null>(null)

  // Which area this officer covers, for the heading: an officer switching
  // between accounts (or a demo audience) should never have to guess.
  useEffect(() => {
    if (!profile?.municipality_id) return
    api
      .municipality(profile.municipality_id)
      .then(setMunicipality)
      .catch(() => setMunicipality(null))
  }, [profile?.municipality_id])

  const ward = municipality?.wards.find((w) => w.id === profile?.ward_id) ?? null
  const municipalityName = municipality
    ? language === 'ne'
      ? municipality.name_ne
      : municipality.name_en
    : null
  const wardName = ward ? (language === 'ne' ? ward.name_ne : ward.name_en) : null
  const title = ward
    ? `${t('auth.ward')} ${ward.number}${wardName ? ` — ${wardName}` : ''}`
    : municipalityName
      ? `${municipalityName} — ${t('dashboard.allWards')}`
      : isAdmin
        ? t('dashboard.allMunicipalities')
        : t('dashboard.title')
  const subtitle = ward && municipalityName ? `${municipalityName} · ${t('dashboard.title')}` : t('dashboard.title')

  const [filter, setFilter] = useState<TicketStatus | 'all'>('all')
  const [showSummary, setShowSummary] = useState(false)

  // Counts are decoration; the list below is the real content. Both come
  // through the cache so returning to the dashboard is instant, and both are
  // refreshed every minute -- this is the page an officer leaves open.
  const countsQuery = useQuery(
    profile ? `dashboard:counts:${profile.id}` : null,
    async () => {
      const [reported, verified, inProgress, resolved, queue, sos] = await Promise.all([
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
  const counts = countsQuery.data ?? { open: 0, duplicates: 0, sos: 0, resolved: 0 }

  const listQuery = useQuery(
    profile ? `dashboard:list:${filter}:${profile.id}` : null,
    () => api.tickets({ status: filter === 'all' ? undefined : filter, limit: 50 }),
    { refetchIntervalMs: 60_000 },
  )
  const tickets = listQuery.data?.items ?? []
  const loading = listQuery.loading

  return (
    <div className="space-y-5">
      <PageTitle
        title={title}
        subtitle={subtitle}
        action={
          <Button variant="secondary" onClick={() => setShowSummary(true)}>
            ✨ {t('summary.buttonLabel')}
          </Button>
        }
      />

      {showSummary && <DashboardSummaryModal onClose={() => setShowSummary(false)} />}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={t('dashboard.open')} value={counts.open} />
        <Link to="/authority/duplicates" className="block">
          <Stat
            label={t('dashboard.pendingReview')}
            value={counts.duplicates}
            tone={counts.duplicates > 0 ? 'warn' : 'ink'}
          />
        </Link>
        <Link to="/authority/emergencies" className="block">
          <Stat
            label={t('dashboard.openSos')}
            value={counts.sos}
            tone={counts.sos > 0 ? 'danger' : 'ink'}
          />
        </Link>
        <Stat label={t('dashboard.resolved')} value={counts.resolved} tone="good" />
      </div>

      <section>
        <h2 className="mb-3 font-bold" style={{ fontSize: 'var(--step-lg)' }}>
          {t('dashboard.allReports')}
        </h2>

        <div className="mb-3 flex flex-wrap gap-2">
          {FILTERS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setFilter(option)}
              aria-pressed={filter === option}
              className="chip"
              style={{
                minHeight: '38px',
                padding: '0 0.9rem',
                borderColor:
                  filter === option ? 'var(--color-brand)' : 'var(--color-line)',
                background:
                  filter === option ? 'var(--color-brand)' : 'var(--color-surface)',
                color: filter === option ? '#fff' : 'var(--color-ink-soft)',
              }}
            >
              {option === 'all'
                ? t('dashboard.filterAll')
                : t(`ticket.${option}` as never)}
            </button>
          ))}
        </div>

        {loading ? (
          <Spinner />
        ) : tickets.length === 0 ? (
          <EmptyState title={t('ticket.none')} />
        ) : (
          <div className="space-y-3">
            {tickets.map((ticket) => (
              <TicketCard key={ticket.id} ticket={ticket} showPriority />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
