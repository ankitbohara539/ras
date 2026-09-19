import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Card,
  EmptyState,
  ErrorNote,
  PageTitle,
  Spinner,
} from '../../components/ui'
import { api } from '../../lib/api'
import { formatDate, relativeTime } from '../../lib/geo'
import { useI18n } from '../../lib/i18n'
import type { SosRequest, SosStatus } from '../../lib/types'

const NEXT: Record<SosStatus, SosStatus[]> = {
  open: ['acknowledged', 'closed'],
  acknowledged: ['dispatched', 'closed'],
  dispatched: ['closed'],
  closed: [],
}

const LABELS: Record<SosStatus, string> = {
  open: 'sosQueue.acknowledge',
  acknowledged: 'sosQueue.dispatch',
  dispatched: 'sosQueue.close',
  closed: '',
}

const TYPE_ICON: Record<string, string> = {
  medical: '🚑',
  fire: '🔥',
  police: '🚓',
  disaster: '⚠️',
  other: '❓',
}

export function SosQueue() {
  const { t, language } = useI18n()

  const [requests, setRequests] = useState<SosRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setRequests(await api.sosList())
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    void load()
    // Emergencies are the one thing worth polling quickly.
    const timer = setInterval(() => void load(), 15_000)
    return () => clearInterval(timer)
  }, [load])

  const update = async (id: string, status: SosStatus) => {
    setBusy(id)
    setError(null)
    try {
      await api.updateSos(id, { status })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setBusy(null)
    }
  }

  if (loading) return <Spinner />

  const open = requests.filter((r) => r.status !== 'closed')
  const closed = requests.filter((r) => r.status === 'closed')

  const renderCard = (request: SosRequest) => (
    <Card
      key={request.id}
      className={request.status === 'open' ? 'border-l-4' : ''}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span aria-hidden="true" style={{ fontSize: '1.4rem' }}>
          {TYPE_ICON[request.emergency_type] ?? '❓'}
        </span>
        <span className="font-bold" style={{ fontSize: 'var(--step-md)' }}>
          {t(`sos.${request.emergency_type}` as never)}
        </span>
        <span
          className="chip"
          style={{
            background:
              request.status === 'open'
                ? 'var(--color-danger-soft)'
                : 'var(--color-canvas)',
            color:
              request.status === 'open'
                ? 'var(--color-danger)'
                : 'var(--color-ink-soft)',
            borderColor:
              request.status === 'open'
                ? 'var(--color-danger)'
                : 'var(--color-line)',
          }}
        >
          {request.status}
        </span>
        <span className="ml-auto hint">{relativeTime(request.created_at)}</span>
      </div>

      {request.note && (
        <p className="mt-2" style={{ fontSize: 'var(--step-sm)' }}>
          {request.note}
        </p>
      )}

      <dl
        className="mt-3 grid gap-2 sm:grid-cols-2"
        style={{ fontSize: 'var(--step-sm)' }}
      >
        <div>
          <dt className="hint">Citizen</dt>
          <dd className="font-medium">{request.citizen_name ?? '—'}</dd>
        </div>
        <div>
          <dt className="hint">Contact</dt>
          <dd>
            {request.contact_phone ? (
              <a
                href={`tel:${request.contact_phone}`}
                className="font-semibold underline"
                style={{ color: 'var(--color-brand)' }}
              >
                📞 {request.contact_phone}
              </a>
            ) : (
              '—'
            )}
          </dd>
        </div>
        <div>
          <dt className="hint">Location</dt>
          <dd>
            <a
              href={`https://www.openstreetmap.org/?mlat=${request.latitude}&mlon=${request.longitude}#map=18/${request.latitude}/${request.longitude}`}
              target="_blank"
              rel="noreferrer"
              className="font-mono underline"
              style={{ color: 'var(--color-brand)' }}
            >
              {request.latitude.toFixed(5)}, {request.longitude.toFixed(5)}
            </a>
          </dd>
        </div>
        <div>
          <dt className="hint">Raised</dt>
          <dd>{formatDate(request.created_at, language)}</dd>
        </div>
      </dl>

      {NEXT[request.status].length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {NEXT[request.status].map((next) => (
            <Button
              key={next}
              variant={next === 'closed' ? 'secondary' : 'primary'}
              disabled={busy === request.id}
              onClick={() => update(request.id, next)}
            >
              {next === 'closed'
                ? t('sosQueue.close')
                : t(LABELS[request.status] as never)}
            </Button>
          ))}
        </div>
      )}
    </Card>
  )

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <PageTitle title={t('sosQueue.title')} />

      {error && <ErrorNote message={error} />}

      {open.length === 0 && closed.length === 0 ? (
        <EmptyState title={t('sosQueue.none')} />
      ) : (
        <>
          <div className="space-y-3">{open.map(renderCard)}</div>

          {closed.length > 0 && (
            <details className="mt-4">
              <summary
                className="cursor-pointer font-semibold"
                style={{ fontSize: 'var(--step-sm)' }}
              >
                Closed ({closed.length})
              </summary>
              <div className="mt-3 space-y-3">{closed.map(renderCard)}</div>
            </details>
          )}
        </>
      )}
    </div>
  )
}
