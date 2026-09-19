import { useCallback, useEffect, useState } from 'react'
import { Link2 } from 'lucide-react'
import { toast } from 'sonner'
import { Link } from 'react-router-dom'
import {
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorNote,
  PageTitle,
  Spinner,
  StatusBadge,
} from '../../components/ui'
import { api } from '../../lib/api'
import { formatDistance } from '../../lib/geo'
import { useI18n } from '../../lib/i18n'
import type { DuplicateCandidate, TicketSummary } from '../../lib/types'

function Signal({ label, value }: { label: string; value: number }) {
  const percent = Math.round(value * 100)

  return (
    <div>
      <div className="flex items-center justify-between">
        <span className="hint">{label}</span>
        <span className="tabular-nums hint">{percent}%</span>
      </div>
      <div
        className="mt-1 h-1.5 overflow-hidden rounded-full"
        style={{ background: 'var(--color-canvas)' }}
      >
        <div
          className="h-full rounded-full"
          style={{ width: `${percent}%`, background: 'var(--color-brand)' }}
        />
      </div>
    </div>
  )
}

function TicketPane({
  label,
  ticket,
  highlight,
}: {
  label: string
  ticket: TicketSummary | null
  highlight?: boolean
}) {
  if (!ticket) {
    return (
      <div
        className="rounded-lg border p-3"
        style={{ borderColor: 'var(--color-line)' }}
      >
        <p className="hint">{label}</p>
        <p className="hint">—</p>
      </div>
    )
  }

  return (
    <div
      className="rounded-lg border p-3"
      style={{
        borderColor: highlight ? 'var(--color-brand)' : 'var(--color-line)',
      }}
    >
      <p className="hint">{label}</p>
      <Link
        to={`/tickets/${ticket.id}`}
        className="font-mono font-semibold underline"
        style={{ fontSize: 'var(--step-sm)', color: 'var(--color-brand)' }}
      >
        {ticket.public_code}
      </Link>
      <div className="mt-1">
        <StatusBadge status={ticket.status} />
      </div>
      <p className="mt-1" style={{ fontSize: 'var(--step-sm)' }}>
        {ticket.title}
      </p>
      <p
        className="mt-1 hint"
        style={{
          display: '-webkit-box',
          WebkitLineClamp: 3,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}
      >
        {ticket.description}
      </p>
    </div>
  )
}

/**
 * The merge review queue -- the human half of the deduplication story.
 * The model has already ranked these; nothing here has been applied.
 */
export function ReviewQueue() {
  const { t } = useI18n()

  const [candidates, setCandidates] = useState<DuplicateCandidate[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setCandidates(await api.reviewQueue(50))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    void load()
  }, [load])

  const act = async (id: string, action: () => Promise<unknown>) => {
    setBusy(id)
    setError(null)
    try {
      await action()
      await load()
      toast.success(t('common.success'))
    } catch (err) {
      const message = err instanceof Error ? err.message : t('common.error')
      setError(message)
      toast.error(message)
    } finally {
      setBusy(null)
    }
  }

  if (loading) return <Spinner />

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <PageTitle title={t('review.title')} subtitle={t('review.hint')} />

      {error && <ErrorNote message={error} />}

      {candidates.length === 0 ? (
        <EmptyState title={t('review.none')} />
      ) : (
        <div className="space-y-4">
          {candidates.map((candidate) => (
            <Card key={candidate.id}>
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className="chip"
                  style={{
                    background: 'var(--color-brand-soft)',
                    color: 'var(--color-brand-ink)',
                    borderColor: 'var(--color-brand)',
                  }}
                >
                  {t('review.confidence')} {Math.round(candidate.score * 100)}%
                </span>
                <span className="hint">
                  {formatDistance(candidate.distance_m)} {t('common.away')}
                </span>
              </div>

              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <TicketPane
                  label={t('review.newReport')}
                  ticket={candidate.ticket}
                  highlight
                />
                <TicketPane
                  label={t('review.existingTicket')}
                  ticket={candidate.candidate}
                />
              </div>

              <div className="mt-3">
                <p className="label">{t('review.why')}</p>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Signal
                    label={t('report.category')}
                    value={candidate.category_score}
                  />
                  <Signal label="Description" value={candidate.text_score} />
                  <Signal label="Photo" value={candidate.image_score} />
                  <Signal label="Distance" value={candidate.geo_score} />
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                <ConfirmDialog
                  trigger={<Button disabled={busy === candidate.id}><Link2 size={16} />{t('review.merge')}</Button>}
                  title={t('review.merge')}
                  description="This will combine both reports into one public ticket and notify its reporters."
                  confirmLabel={t('review.merge')}
                  onConfirm={() => act(candidate.id, () => api.mergeTicket(candidate.ticket_id, candidate.candidate_ticket_id))}
                />
                <Button
                  variant="secondary"
                  disabled={busy === candidate.id}
                  onClick={() =>
                    act(candidate.id, () => api.dismissCandidate(candidate.id))
                  }
                >
                  {t('review.dismiss')}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
