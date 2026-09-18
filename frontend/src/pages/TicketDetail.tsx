import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  Button,
  Card,
  ErrorNote,
  Field,
  PriorityBadge,
  SpeakButton,
  Spinner,
  StatusBadge,
  SuccessNote,
} from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { formatDate, formatDistance, useGeolocation } from '../lib/geo'
import { useI18n } from '../lib/i18n'
import type { TicketDetail as Ticket, TicketStatus, Ward } from '../lib/types'

const NEXT_STATUSES: Record<TicketStatus, TicketStatus[]> = {
  reported: ['verified', 'in_progress', 'rejected'],
  verified: ['in_progress', 'resolved', 'rejected'],
  in_progress: ['resolved', 'rejected'],
  resolved: ['in_progress'],
  rejected: ['reported'],
  merged: [],
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-20 shrink-0 hint">{label}</span>
      <div
        className="h-2 flex-1 overflow-hidden rounded-full"
        style={{ background: 'var(--color-canvas)' }}
      >
        <div
          className="h-full rounded-full"
          style={{
            width: `${Math.round(value * 100)}%`,
            background: 'var(--color-brand)',
          }}
        />
      </div>
      <span className="w-10 text-right tabular-nums hint">
        {Math.round(value * 100)}%
      </span>
    </div>
  )
}

export function TicketDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { t, language } = useI18n()
  const { profile, isAuthority } = useAuth()
  const navigate = useNavigate()
  const { state: geo, locate } = useGeolocation()

  const [ticket, setTicket] = useState<Ticket | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const [wards, setWards] = useState<Ward[]>([])
  const [showReassign, setShowReassign] = useState(false)

  const load = useCallback(async () => {
    if (!id) return
    try {
      setTicket(await api.ticket(id))
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setLoading(false)
    }
  }, [id, t])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (!showReassign || !ticket) return
    api
      .municipality(ticket.municipality_id)
      .then((detail) => setWards(detail.wards))
      .catch(() => setWards([]))
  }, [showReassign, ticket])

  const act = async (action: () => Promise<unknown>, successMessage?: string) => {
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      await action()
      if (successMessage) setMessage(successMessage)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <Spinner />
  if (!ticket) return <ErrorNote message={error ?? t('common.error')} />

  const isMine = ticket.reporter_id === profile?.id
  const reporters = ticket.child_count + 1
  const canCorroborate =
    !isAuthority && !isMine && ticket.my_corroboration === null &&
    ['reported', 'verified', 'in_progress'].includes(ticket.status)

  const narration = [
    ticket.title,
    ticket.description,
    ticket.resolution_note ?? '',
  ].join('. ')

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="btn btn-ghost"
        style={{ minHeight: 'auto', padding: '0.25rem 0' }}
      >
        ← {t('common.back')}
      </button>

      {error && <ErrorNote message={error} />}
      {message && <SuccessNote>{message}</SuccessNote>}

      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono font-bold" style={{ fontSize: 'var(--step-md)' }}>
            {ticket.public_code}
          </span>
          <StatusBadge status={ticket.status} />
          {isAuthority && <PriorityBadge priority={ticket.priority} />}
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
          <div className="ml-auto">
            <SpeakButton text={narration} />
          </div>
        </div>

        <h1 className="mt-3 font-bold" style={{ fontSize: 'var(--step-lg)' }}>
          {ticket.title}
        </h1>
        <p className="mt-2" style={{ fontSize: 'var(--step-md)' }}>
          {ticket.description}
        </p>

        <dl className="mt-4 grid gap-2 sm:grid-cols-2" style={{ fontSize: 'var(--step-sm)' }}>
          <div>
            <dt className="hint">{t('ticket.reportedBy')}</dt>
            <dd className="font-medium">{ticket.reporter_name ?? '—'}</dd>
          </div>
          <div>
            <dt className="hint">{t('report.location')}</dt>
            <dd className="font-medium">
              {ticket.address_text ?? `${ticket.latitude.toFixed(5)}, ${ticket.longitude.toFixed(5)}`}
            </dd>
          </div>
          <div>
            <dt className="hint">{t('auth.ward')}</dt>
            <dd className="font-medium">
              {ticket.ward_number !== null
                ? `${t('auth.ward')} ${ticket.ward_number}${ticket.ward_name ? ` — ${ticket.ward_name}` : ''}`
                : '—'}
            </dd>
          </div>
          {reporters > 1 && (
            <div>
              <dt className="hint">{t('ticket.reporters')}</dt>
              <dd className="font-bold" style={{ color: 'var(--color-brand)' }}>
                👥 {reporters}
              </dd>
            </div>
          )}
          {ticket.corroboration_count > 0 && (
            <div>
              <dt className="hint">{t('ticket.confirmations')}</dt>
              <dd className="font-medium">✓ {ticket.corroboration_count}</dd>
            </div>
          )}
        </dl>

        {ticket.photos.length > 0 && (
          <div className="mt-4">
            <p className="label">{t('ticket.photos')}</p>
            <div className="flex flex-wrap gap-2">
              {ticket.photos.map((photo) =>
                photo.url ? (
                  <a key={photo.id} href={photo.url} target="_blank" rel="noreferrer">
                    <img
                      src={photo.url}
                      alt=""
                      className="h-28 w-28 rounded-lg object-cover"
                      style={{ border: '1px solid var(--color-line)' }}
                    />
                  </a>
                ) : null,
              )}
            </div>
          </div>
        )}

        {ticket.resolution_note && (
          <div
            className="mt-4 rounded-lg p-3"
            style={{ background: 'var(--color-good-soft)' }}
          >
            <p className="font-semibold" style={{ fontSize: 'var(--step-sm)' }}>
              {t('ticket.resolution')}
            </p>
            <p style={{ fontSize: 'var(--step-sm)' }}>{ticket.resolution_note}</p>
          </div>
        )}
      </Card>

      {ticket.parent_id && (
        <Card>
          <p className="hint">{t('manage.duplicateOf')}</p>
          <Link
            to={`/tickets/${ticket.parent_id}`}
            className="font-semibold underline"
            style={{ color: 'var(--color-brand)' }}
          >
            View the main report →
          </Link>
        </Card>
      )}

      {canCorroborate && (
        <Card>
          <h2 className="font-bold" style={{ fontSize: 'var(--step-md)' }}>
            {t('corroborate.title')}
          </h2>
          <p className="mt-1 hint">{t('corroborate.hint')}</p>

          {geo.kind === 'ready' ? (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                disabled={busy}
                onClick={() =>
                  act(
                    () =>
                      api.corroborate(ticket.id, {
                        is_confirmed: true,
                        latitude: geo.coords.latitude,
                        longitude: geo.coords.longitude,
                      }),
                    t('corroborate.done'),
                  )
                }
              >
                ✓ {t('corroborate.yes')}
              </Button>
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() =>
                  act(
                    () =>
                      api.corroborate(ticket.id, {
                        is_confirmed: false,
                        latitude: geo.coords.latitude,
                        longitude: geo.coords.longitude,
                      }),
                    t('corroborate.disputed'),
                  )
                }
              >
                ✕ {t('corroborate.no')}
              </Button>
            </div>
          ) : (
            <Button variant="secondary" onClick={locate} className="mt-3 w-full">
              📍 {geo.kind === 'locating' ? t('report.locating') : t('report.useMyLocation')}
            </Button>
          )}

          {geo.kind === 'error' && (
            <div className="mt-2">
              <ErrorNote message={geo.message} />
            </div>
          )}
        </Card>
      )}

      {ticket.my_corroboration !== null && (
        <SuccessNote>
          {ticket.my_corroboration ? t('corroborate.done') : t('corroborate.disputed')}
        </SuccessNote>
      )}

      {/* Authority: the merge review. Suggestions only, never auto-applied. */}
      {isAuthority && ticket.duplicate_candidates.length > 0 && (
        <Card>
          <h2 className="font-bold" style={{ fontSize: 'var(--step-md)' }}>
            {t('review.title')}
          </h2>
          <p className="mt-1 hint">{t('review.hint')}</p>

          <div className="mt-3 space-y-3">
            {ticket.duplicate_candidates.map((candidate) => (
              <div
                key={candidate.id}
                className="rounded-lg border p-3"
                style={{ borderColor: 'var(--color-line)' }}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    to={`/tickets/${candidate.candidate_ticket_id}`}
                    className="font-mono font-semibold underline"
                    style={{ color: 'var(--color-brand)' }}
                  >
                    {candidate.candidate?.public_code}
                  </Link>
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
                </div>

                <p className="mt-2" style={{ fontSize: 'var(--step-sm)' }}>
                  {candidate.candidate?.title}
                </p>

                <div className="mt-3 space-y-1.5">
                  <p className="label" style={{ marginBottom: 0 }}>
                    {t('review.why')}
                  </p>
                  <ScoreBar label={t('report.category')} value={candidate.category_score} />
                  <ScoreBar label="Text" value={candidate.text_score} />
                  <ScoreBar label="Photo" value={candidate.image_score} />
                  <ScoreBar label="Distance" value={candidate.geo_score} />
                  <p className="hint">
                    {formatDistance(candidate.distance_m)} {t('common.away')}
                  </p>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    disabled={busy}
                    onClick={() =>
                      act(
                        () =>
                          api.mergeTicket(ticket.id, candidate.candidate_ticket_id),
                        'Merged.',
                      )
                    }
                  >
                    🔗 {t('review.merge')}
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={busy}
                    onClick={() =>
                      act(() => api.dismissCandidate(candidate.id), 'Dismissed.')
                    }
                  >
                    {t('review.dismiss')}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Authority: status control. */}
      {isAuthority && !ticket.parent_id && NEXT_STATUSES[ticket.status].length > 0 && (
        <Card>
          <h2 className="font-bold" style={{ fontSize: 'var(--step-md)' }}>
            {t('manage.updateStatus')}
          </h2>

          <div className="mt-3">
            <Field
              label={
                ticket.status === 'in_progress' || ticket.status === 'verified'
                  ? t('manage.resolutionNote')
                  : t('manage.note')
              }
            >
              <input
                className="field"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={1000}
              />
            </Field>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            {NEXT_STATUSES[ticket.status].map((next) => (
              <Button
                key={next}
                variant={next === 'rejected' ? 'danger' : 'primary'}
                disabled={busy}
                onClick={() =>
                  act(
                    () =>
                      api.updateTicketStatus(ticket.id, {
                        status: next,
                        note: note || undefined,
                        resolution_note: next === 'resolved' ? note || undefined : undefined,
                      }),
                    undefined,
                  ).then(() => setNote(''))
                }
              >
                {t(`ticket.${next}` as never)}
              </Button>
            ))}
          </div>

          {ticket.child_count > 0 && (
            <p className="mt-3 hint">
              Resolving this will also resolve its {ticket.child_count} duplicate
              {ticket.child_count === 1 ? '' : 's'} and notify every reporter.
            </p>
          )}
        </Card>
      )}

      {isAuthority && ticket.parent_id && (
        <Card>
          <Button
            variant="secondary"
            disabled={busy}
            onClick={() => act(() => api.splitTicket(ticket.id), 'Split out.')}
          >
            {t('manage.split')}
          </Button>
        </Card>
      )}

      {/* GPS decides the ward, and GPS is imperfect near boundaries. Without
          this, a misrouted report is invisible to the office that should
          handle it and there is no way to put it right. */}
      {isAuthority && !ticket.parent_id && (
        <Card>
          {showReassign ? (
            <>
              <h2 className="font-bold" style={{ fontSize: 'var(--step-md)' }}>
                {t('manage.reassignWard')}
              </h2>
              <p className="mt-1 hint">{t('manage.reassignHint')}</p>

              <div className="mt-3 flex flex-wrap gap-2">
                <select
                  className="field"
                  style={{ maxWidth: 280 }}
                  defaultValue=""
                  onChange={(e) => {
                    if (!e.target.value) return
                    void act(
                      () => api.reassignWard(ticket.id, e.target.value),
                      'Moved to the selected ward.',
                    )
                  }}
                >
                  <option value="">{t('auth.selectWard')}</option>
                  {wards
                    .filter((ward) => ward.id !== ticket.ward_id)
                    .map((ward) => (
                      <option key={ward.id} value={ward.id}>
                        {t('auth.ward')} {ward.number}
                        {ward.name_en ? ` — ${ward.name_en}` : ''}
                      </option>
                    ))}
                </select>
                <Button variant="secondary" onClick={() => setShowReassign(false)}>
                  {t('common.cancel')}
                </Button>
              </div>
            </>
          ) : (
            <Button variant="secondary" onClick={() => setShowReassign(true)}>
              📍 {t('manage.wrongWard')}
            </Button>
          )}
        </Card>
      )}

      {ticket.children.length > 0 && (
        <Card>
          <h2 className="font-bold" style={{ fontSize: 'var(--step-md)' }}>
            {t('ticket.alsoReportedBy')} ({ticket.children.length})
          </h2>
          <div className="mt-3 space-y-2">
            {ticket.children.map((child) => (
              <Link
                key={child.id}
                to={`/tickets/${child.id}`}
                className="flex flex-wrap items-center gap-2 rounded-lg border p-3"
                style={{ borderColor: 'var(--color-line)' }}
              >
                <span className="font-mono font-semibold" style={{ fontSize: 'var(--step-sm)' }}>
                  {child.public_code}
                </span>
                <span className="hint">{formatDate(child.created_at, language)}</span>
              </Link>
            ))}
          </div>
        </Card>
      )}

      {ticket.history.length > 0 && (
        <Card>
          <h2 className="font-bold" style={{ fontSize: 'var(--step-md)' }}>
            {t('ticket.history')}
          </h2>
          <ol className="mt-3 space-y-3">
            {ticket.history.map((entry, index) => (
              <li key={index} className="flex gap-3">
                <span
                  className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                  style={{ background: 'var(--color-brand)' }}
                  aria-hidden="true"
                />
                <div>
                  <StatusBadge status={entry.to_status} />
                  {entry.note && (
                    <p className="mt-1" style={{ fontSize: 'var(--step-sm)' }}>
                      {entry.note}
                    </p>
                  )}
                  <p className="hint">{formatDate(entry.created_at, language)}</p>
                </div>
              </li>
            ))}
          </ol>
        </Card>
      )}
    </div>
  )
}
