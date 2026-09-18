import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { TicketCard } from '../../components/TicketCard'
import { EmptyState, PageTitle, Spinner, Stat } from '../../components/ui'
import { api } from '../../lib/api'
import { useI18n } from '../../lib/i18n'
import type { TicketStatus, TicketSummary } from '../../lib/types'

const FILTERS: (TicketStatus | 'all')[] = [
  'all',
  'reported',
  'verified',
  'in_progress',
  'resolved',
]

export function AuthorityDashboard() {
  const { t } = useI18n()

  const [tickets, setTickets] = useState<TicketSummary[]>([])
  const [filter, setFilter] = useState<TicketStatus | 'all'>('all')
  const [counts, setCounts] = useState({ open: 0, duplicates: 0, sos: 0, resolved: 0 })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function loadCounts() {
      try {
        const [reported, verified, inProgress, resolved, queue, sos] =
          await Promise.all([
            api.tickets({ status: 'reported', limit: 1 }),
            api.tickets({ status: 'verified', limit: 1 }),
            api.tickets({ status: 'in_progress', limit: 1 }),
            api.tickets({ status: 'resolved', limit: 1 }),
            api.reviewQueue(100),
            api.sosList('open'),
          ])

        if (cancelled) return
        setCounts({
          open: reported.total + verified.total + inProgress.total,
          duplicates: queue.length,
          sos: sos.length,
          resolved: resolved.total,
        })
      } catch {
        // Counts are decoration; the list below is the real content.
      }
    }

    void loadCounts()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)

    api
      .tickets({ status: filter === 'all' ? undefined : filter, limit: 50 })
      .then((result) => {
        if (!cancelled) setTickets(result.items)
      })
      .catch(() => {
        if (!cancelled) setTickets([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [filter])

  return (
    <div className="space-y-5">
      <PageTitle title={t('dashboard.title')} />

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
