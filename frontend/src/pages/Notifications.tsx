import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Button, Card, EmptyState, PageTitle, Spinner } from '../components/ui'
import { api } from '../lib/api'
import { formatDate } from '../lib/geo'
import { useI18n } from '../lib/i18n'
import type { Notification } from '../lib/types'

export function Notifications() {
  const { t, language, pick } = useI18n()
  const [items, setItems] = useState<Notification[]>([])
  const [unread, setUnread] = useState(0)
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const result = await api.notifications()
      setItems(result.items)
      setUnread(result.unread)
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const markAllRead = async () => {
    try {
      const result = await api.markNotificationsRead()
      setItems(result.items)
      setUnread(result.unread)
    } catch {
      // Leave the list as it is; the next load will reconcile.
    }
  }

  if (loading) return <Spinner />

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageTitle
        title={t('nav.notifications')}
        action={
          unread > 0 ? (
            <Button variant="secondary" onClick={markAllRead}>
              Mark all read ({unread})
            </Button>
          ) : undefined
        }
      />

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

            return item.ticket_id ? (
              <Link key={item.id} to={`/tickets/${item.ticket_id}`} className="block">
                {body}
              </Link>
            ) : (
              <div key={item.id}>{body}</div>
            )
          })}
        </div>
      )}
    </div>
  )
}
