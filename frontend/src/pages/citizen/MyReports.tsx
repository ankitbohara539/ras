import { useState } from 'react'
import { Link } from 'react-router-dom'
import { TicketCard } from '../../components/TicketCard'
import { EmptyState, PageTitle, Spinner } from '../../components/ui'
import { api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { useQuery } from '../../lib/cache'
import { useI18n } from '../../lib/i18n'
import type { TicketStatus } from '../../lib/types'

const FILTERS: (TicketStatus | 'all')[] = [
  'all',
  'reported',
  'verified',
  'in_progress',
  'resolved',
]

export function MyReports() {
  const { t } = useI18n()
  const { profile } = useAuth()
  const [filter, setFilter] = useState<TicketStatus | 'all'>('all')

  // One cache entry per filter: switching back to a tab you already opened
  // is instant, and still refreshed.
  const query = useQuery(profile ? `tickets:mine:${filter}:${profile.id}` : null, () =>
    api.tickets({
      mine: true,
      status: filter === 'all' ? undefined : filter,
      limit: 100,
    }),
  )
  const tickets = query.data?.items ?? []
  const loading = query.loading

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageTitle title={t('nav.myReports')} />

      <div className="flex flex-wrap gap-2">
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
              borderColor: filter === option ? 'var(--color-brand)' : 'var(--color-line)',
              background: filter === option ? 'var(--color-brand)' : 'var(--color-surface)',
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
        <EmptyState
          title={t('ticket.none')}
          hint={t('ticket.noneHint')}
          action={
            <Link to="/report" className="btn btn-primary">
              {t('report.title')}
            </Link>
          }
        />
      ) : (
        <div className="space-y-3">
          {tickets.map((ticket) => (
            <TicketCard key={ticket.id} ticket={ticket} />
          ))}
        </div>
      )}
    </div>
  )
}
