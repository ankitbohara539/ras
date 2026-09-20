import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Button, Card, EmptyState, ErrorNote, PageTitle, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useQuery } from '../lib/cache'
import { formatDate } from '../lib/geo'
import { useI18n } from '../lib/i18n'
import type { Notification } from '../lib/types'

type NotificationFilter = 'all' | 'unread' | 'read'

export function Notifications() {
  const { t, language, pick } = useI18n()
  const { profile } = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<NotificationFilter>('all')

  // Same cache as the header badge: a write here (marking read) invalidates
  // both, so the badge and this list can never disagree.
  const { data, loading, refetch } = useQuery(
    profile ? `notifications:all:${profile.id}` : null,
    () => api.notifications(),
  )
  const items: Notification[] = data?.items ?? []
  const unread = items.filter((item) => !item.read_at).length
  const filteredItems = items.filter((item) => {
    if (filter === 'unread') return !item.read_at
    if (filter === 'read') return Boolean(item.read_at)
    return true
  })
  const filters: { value: NotificationFilter; label: string; count: number }[] = [
    { value: 'all', label: t('notifications.all'), count: items.length },
    { value: 'unread', label: t('notifications.unread'), count: unread },
    { value: 'read', label: t('notifications.read'), count: items.length - unread },
  ]

  const markRead = async (ids?: string[]) => {
    setBusy(true)
    setError(null)
    try {
      await api.markNotificationsRead(ids)
      await refetch()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <Spinner />

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageTitle
        title={t('nav.notifications')}
        action={
          unread > 0 ? (
            <Button variant="secondary" disabled={busy} onClick={() => markRead()}>
              {t('notifications.markAllRead')} ({unread})
            </Button>
          ) : undefined
        }
      />

      {error && <ErrorNote message={error} />}

      <div
        className="flex w-fit max-w-full gap-1 overflow-x-auto rounded-lg border border-line bg-surface p-1"
        role="group"
        aria-label={t('notifications.filter')}
      >
        {filters.map((option) => (
          <button
            key={option.value}
            type="button"
            className={`btn min-h-9 whitespace-nowrap px-3 ${filter === option.value ? 'btn-primary' : 'btn-ghost'}`}
            aria-pressed={filter === option.value}
            onClick={() => setFilter(option.value)}
          >
            {option.label}
            <span className={filter === option.value ? 'text-white/75' : 'text-ink-faint'}>
              {option.count}
            </span>
          </button>
        ))}
      </div>

      {filteredItems.length === 0 ? (
        <EmptyState
          title={t(
            filter === 'unread'
              ? 'notifications.noneUnread'
              : filter === 'read'
                ? 'notifications.noneRead'
                : 'notifications.noneAll',
          )}
        />
      ) : (
        <div className="space-y-2">
          {filteredItems.map((item) => {
            const body = (
              <Card
                className={item.read_at ? '' : 'border-l-4'}
                key={item.id}
              >
                <div className="flex items-start gap-3">
                  {!item.read_at && (
                    <span
                      className="mt-2 h-2 w-2 shrink-0 rounded-full"
                      style={{ background: 'var(--color-brand)' }}
                      aria-label={t('notifications.unread')}
                    />
                  )}
                  <div className="min-w-0">
                    <p
                      className="font-semibold"
                      style={{ fontSize: 'var(--step-sm)' }}
                    >
                      {pick(item.title_en, item.title_ne)}
                    </p>
                    {item.body_en && <p className="mt-0.5 hint">{item.body_en}</p>}
                    <p className="mt-1 hint">
                      {formatDate(item.created_at, language)}
                    </p>
                  </div>
                </div>
              </Card>
            )

            // Opening a notification reads it.
            const open = () => {
              if (!item.read_at) void markRead([item.id])
            }

            return item.ticket_id ? (
              <Link key={item.id} to={`/tickets/${item.ticket_id}`} className="block" onClick={open}>
                {body}
              </Link>
            ) : (
              <button key={item.id} type="button" className="block w-full text-left" onClick={open}>
                {body}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
