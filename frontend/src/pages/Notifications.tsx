import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Button, Card, EmptyState, ErrorNote, PageTitle, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useQuery } from '../lib/cache'
import { formatDate } from '../lib/geo'
import { useI18n } from '../lib/i18n'
import type { Notification } from '../lib/types'

export function Notifications() {
  const { t, language, pick } = useI18n()
  const { profile } = useAuth()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Same cache as the header badge: a write here (marking read) invalidates
  // both, so the badge and this list can never disagree.
  const { data, loading } = useQuery(
    profile ? `notifications:all:${profile.id}` : null,
    () => api.notifications(),
  )
  const items: Notification[] = data?.items ?? []
  const unread = data?.unread ?? 0

  const markRead = async (ids?: string[]) => {
    setBusy(true)
    setError(null)
    try {
      await api.markNotificationsRead(ids)
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

      {items.length === 0 ? (
        <EmptyState title="Nothing here yet." />
      ) : (
        <div className="space-y-2">
          {items.map((item) => {
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
                      aria-label="Unread"
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
