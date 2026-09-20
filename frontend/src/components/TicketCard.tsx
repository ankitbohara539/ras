import { Link } from 'react-router-dom'
import { Check, MapPin, Users } from 'lucide-react'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { prefetch } from '../lib/cache'
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
  const { profile } = useAuth()
  const reporters = ticket.child_count + 1

  // Start loading the ticket the moment the user shows intent -- pointer
  // over it, keyboard focus, or a finger touching down -- so by the time the
  // tap completes the page usually has its data. Same keys as TicketDetail.
  const warm = () => {
    if (!profile) return
    prefetch(`ticket:${ticket.id}:${profile.id}`, () => api.ticket(ticket.id))
    prefetch(`comments:${ticket.id}:${profile.id}`, () => api.comments(ticket.id))
  }

  return (
    <Link
      to={`/tickets/${ticket.id}`}
      className="interactive-card card block p-4"
      onMouseEnter={warm}
      onFocus={warm}
      onTouchStart={warm}
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
            <Check size={13} /> {t('ticket.communityVerified')}
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

        {ticket.ward_number !== null && (
          <span className="inline-flex items-center gap-1">
            <MapPin size={13} /> {t('auth.ward')} {ticket.ward_number}
            {ticket.ward_name ? ` · ${ticket.ward_name}` : ''}
          </span>
        )}

        {reporters > 1 && (
          <span
            className="font-semibold"
            style={{ color: 'var(--color-brand)' }}
          >
            <Users size={13} /> {reporters} {t('ticket.reporters')}
          </span>
        )}

        {ticket.corroboration_count > 0 && (
          <span className="inline-flex items-center gap-1">
            <Check size={13} /> {ticket.corroboration_count} {t('ticket.confirmations')}
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
