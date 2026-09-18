import { Link } from 'react-router-dom'
import { formatDistance, relativeTime } from '../lib/geo'
import { useI18n } from '../lib/i18n'
import type { TicketSummary } from '../lib/types'
import { PriorityBadge, StatusBadge } from './ui'

export function TicketCard({
  ticket,
  showDistance = false,
  showPriority = false,
}: {
  ticket: TicketSummary
  showDistance?: boolean
  showPriority?: boolean
}) {
  const { t } = useI18n()
  const reporters = ticket.child_count + 1

  return (
    <Link
      to={`/tickets/${ticket.id}`}
      className="card block p-4 transition hover:border-[var(--color-brand)]"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono font-semibold" style={{ fontSize: 'var(--step-sm)' }}>
          {ticket.public_code}
        </span>
        <StatusBadge status={ticket.status} />
        {showPriority && <PriorityBadge priority={ticket.priority} />}

        {ticket.community_verified && (
          <span
            className="chip"
            style={{
              background: 'var(--color-good-soft)',
              color: 'var(--color-good)',
              borderColor: 'var(--color-good)',
            }}
          >
            ✓ {t('ticket.communityVerified')}
          </span>
        )}
      </div>

      <p className="mt-2 font-semibold" style={{ fontSize: 'var(--step-md)' }}>
        {ticket.title}
      </p>
      <p
        className="mt-1 line-clamp-2 hint"
        style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}
      >
        {ticket.description}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-3 hint">
        <span>{relativeTime(ticket.created_at)}</span>

        {reporters > 1 && (
          <span
            className="font-semibold"
            style={{ color: 'var(--color-brand)' }}
          >
            👥 {reporters} {t('ticket.reporters')}
          </span>
        )}

        {ticket.corroboration_count > 0 && (
          <span>
            ✓ {ticket.corroboration_count} {t('ticket.confirmations')}
          </span>
        )}

        {showDistance && ticket.distance_m !== null && (
          <span className="ml-auto font-medium">
            {formatDistance(ticket.distance_m)} {t('common.away')}
          </span>
        )}
      </div>
    </Link>
  )
}
