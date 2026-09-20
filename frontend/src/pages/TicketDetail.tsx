import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Check, Link2, LocateFixed, LockKeyhole, MapPin, Pencil, Trash2, Users, X, Zap } from 'lucide-react'
import { toast } from 'sonner'
import {
  Button,
  Card,
  ConfirmDialog,
  ErrorNote,
  Field,
  PriorityBadge,
  SpeakButton,
  Spinner,
  StatusBadge,
  SuccessNote,
} from '../components/ui'
import { LocationMap } from '../components/LocationMap'
import { api } from '../lib/api'
import { useQuery } from '../lib/cache'
import { useAuth } from '../lib/auth'
import {
  formatCoords,
  formatDate,
  formatDistance,
  mapsLink,
  useGeolocation,
} from '../lib/geo'
import { useI18n } from '../lib/i18n'
import type { TicketComment, TicketDetail as Ticket, TicketStatus, Ward } from '../lib/types'

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

  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  const [wards, setWards] = useState<Ward[]>([])
  const [priorityNote, setPriorityNote] = useState('')
  const [showReassign, setShowReassign] = useState(false)
  const [editingReport, setEditingReport] = useState(false)
  const [editTitle, setEditTitle] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editAddress, setEditAddress] = useState('')

  const [commentDraft, setCommentDraft] = useState('')
  const [commentBusy, setCommentBusy] = useState(false)
  const [commentError, setCommentError] = useState<string | null>(null)

  // Through the shared cache: a ticket opened from a list (prefetched on
  // hover or touch) paints at once and is refreshed straight away. Keyed per
  // viewer because an officer's copy carries duplicate suggestions a
  // citizen's does not.
  const ticketQuery = useQuery(id && profile ? `ticket:${id}:${profile.id}` : null, () =>
    api.ticket(id!),
  )
  const commentsQuery = useQuery(id && profile ? `comments:${id}:${profile.id}` : null, () =>
    api.comments(id!),
  )
  const ticket: Ticket | null = ticketQuery.data ?? null
  const loading = ticketQuery.loading
  // The ticket load already surfaces a permission error; a failed thread
  // just shows as empty rather than a second error banner.
  const comments: TicketComment[] = commentsQuery.data?.items ?? []
  const loadError =
    ticketQuery.error instanceof Error ? ticketQuery.error.message : null

  // After an action: wait for the fresh copy before clearing the busy state.
  // (The write itself already invalidated the cache.)
  const load = ticketQuery.refetch
  const loadComments = commentsQuery.refetch

  const submitComment = async () => {
    if (!id || !commentDraft.trim()) return
    setCommentBusy(true)
    setCommentError(null)
    try {
      await api.postComment(id, commentDraft.trim())
      setCommentDraft('')
      // An urgent comment can raise the priority; show it without a refresh.
      await Promise.all([loadComments(), load()])
      toast.success(t('common.success'))
    } catch (err) {
      const message = err instanceof Error ? err.message : t('common.error')
      setCommentError(message)
      toast.error(message)
    } finally {
      setCommentBusy(false)
    }
  }

  const removeComment = async (commentId: string) => {
    if (!id) return
    setCommentBusy(true)
    try {
      await api.deleteComment(id, commentId)
      await Promise.all([loadComments(), load()])
      toast.success(t('common.success'))
    } catch (err) {
      const message = err instanceof Error ? err.message : t('common.error')
      setCommentError(message)
      toast.error(message)
    } finally {
      setCommentBusy(false)
    }
  }

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
      toast.success(successMessage ?? t('common.success'))
    } catch (err) {
      const message = err instanceof Error ? err.message : t('common.error')
      setError(message)
      toast.error(message)
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <Spinner />
  if (!ticket) return <ErrorNote message={error ?? loadError ?? t('common.error')} />

  const isMine = ticket.reporter_id === profile?.id
  const canManageContent = isMine || profile?.role === 'admin'
  const reporters = ticket.child_count + 1
  const canCorroborate =
    !isAuthority && !isMine && ticket.my_corroboration === null &&
    ['reported', 'verified', 'in_progress'].includes(ticket.status)

  const narration = [
    ticket.title,
    ticket.description,
    ticket.resolution_note ?? '',
  ].join('. ')

  const beginEdit = () => {
    setEditTitle(ticket.title)
    setEditDescription(ticket.description)
    setEditAddress(ticket.address_text ?? '')
    setEditingReport(true)
  }

  const saveReport = async () => {
    if (!editTitle.trim() || editDescription.trim().length < 10) {
      setError('Enter a title and at least 10 characters of description.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.updateTicket(ticket.id, { title: editTitle.trim(), description: editDescription.trim(), address_text: editAddress.trim() || null })
      setEditingReport(false)
      setMessage('Report updated successfully.')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally { setBusy(false) }
  }

  const deleteReport = async () => {
    setBusy(true)
    setError(null)
    try {
      await api.deleteTicket(ticket.id)
      toast.success('Report deleted.')
      navigate(profile?.role === 'admin' ? '/authority' : '/my-reports')
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally { setBusy(false) }
  }

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
          {isAuthority && ticket.priority_locked && (
            <span className="chip" title={t('priority.lockedHint')}>
              <LockKeyhole size={13} /> {t('priority.manual')}
            </span>
          )}
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
          <div className="ml-auto">
            <SpeakButton text={narration} />
          </div>
        </div>

        {editingReport ? <div className="mt-4 space-y-3 rounded-lg border border-line bg-canvas p-3"><Field label="Title" required><input className="field" value={editTitle} maxLength={200} onChange={(event) => setEditTitle(event.target.value)} /></Field><Field label="Description" required><textarea className="field" rows={4} value={editDescription} minLength={10} maxLength={4000} onChange={(event) => setEditDescription(event.target.value)} /></Field><Field label="Address or landmark"><input className="field" value={editAddress} maxLength={300} onChange={(event) => setEditAddress(event.target.value)} /></Field><div className="flex flex-wrap gap-2"><Button type="button" variant="secondary" onClick={() => setEditingReport(false)}>Cancel</Button><Button type="button" disabled={busy} onClick={() => void saveReport()}>{busy ? 'Saving…' : 'Save changes'}</Button></div></div> : <><h1 className="mt-3 font-bold" style={{ fontSize: 'var(--step-lg)' }}>{ticket.title}</h1><p className="mt-2" style={{ fontSize: 'var(--step-md)' }}>{ticket.description}</p>{canManageContent && !ticket.parent_id && (ticket.status === 'reported' || profile?.role === 'admin') && <div className="mt-3 flex flex-wrap gap-2"><Button type="button" size="sm" variant="secondary" onClick={beginEdit}><Pencil size={15} /> Edit report</Button><ConfirmDialog destructive trigger={<Button type="button" size="sm" variant="danger" disabled={busy}><Trash2 size={15} /> Delete report</Button>} title="Delete this report?" description="This permanently removes the report and its attached photos." confirmLabel="Delete report" onConfirm={deleteReport} /></div>}</>}

        <dl className="mt-4 grid gap-2 sm:grid-cols-2" style={{ fontSize: 'var(--step-sm)' }}>
          <div>
            <dt className="hint">{t('ticket.reportedBy')}</dt>
            <dd className="font-medium">{ticket.reporter_name ?? '—'}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="hint">{t('report.location')}</dt>
            {ticket.address_text && (
              <dd className="inline-flex items-center gap-1 font-medium"><MapPin size={14} />{ticket.address_text}</dd>
            )}
            <dd className="font-mono" style={{ fontSize: 'var(--step-xs)' }}>
              {formatCoords(ticket.latitude, ticket.longitude)}
              {' · '}
              <a
                href={mapsLink(ticket.latitude, ticket.longitude)}
                target="_blank"
                rel="noreferrer"
                className="underline"
                style={{ color: 'var(--color-brand)' }}
              >
                {t('ticket.openInMaps')} ↗
              </a>
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
              <dd className="flex items-center gap-1 font-bold" style={{ color: 'var(--color-brand)' }}>
                <Users size={15} /> {reporters}
              </dd>
            </div>
          )}
          {ticket.corroboration_count > 0 && (
            <div>
              <dt className="hint">{t('ticket.confirmations')}</dt>
              <dd className="flex items-center gap-1 font-medium"><Check size={14} />{ticket.corroboration_count}</dd>
            </div>
          )}
          {ticket.urgent_commenter_count > 0 && (
            <div>
              <dt className="hint">{t('comments.urgent')}</dt>
              <dd className="font-medium" style={{ color: 'var(--color-warn)' }}>
                <Zap size={14} className="mr-1 inline" />{ticket.urgent_commenter_count} {t('comments.urgentCount')}
              </dd>
            </div>
          )}
        </dl>

        <div className="mt-4">
          <LocationMap
            coords={{ latitude: ticket.latitude, longitude: ticket.longitude }}
            height={200}
          />
        </div>

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
                <Check size={16} /> {t('corroborate.yes')}
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
                <X size={16} /> {t('corroborate.no')}
              </Button>
            </div>
          ) : (
            <Button variant="secondary" onClick={locate} className="mt-3 w-full">
              <LocateFixed size={16} /> {geo.kind === 'locating' ? t('report.locating') : t('report.useMyLocation')}
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

      {/* Authority: the merge review. Matches of 80% or more were already
          merged on submission; what is left here is for a human to judge. */}
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
                  <ConfirmDialog
                    trigger={<Button disabled={busy}><Link2 size={16} />{t('review.merge')}</Button>}
                    title={t('review.merge')}
                    description="This will combine both reports into one public ticket and notify its reporters."
                    confirmLabel={t('review.merge')}
                    onConfirm={() => act(() => api.mergeTicket(ticket.id, candidate.candidate_ticket_id), 'Merged.')}
                  />
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

      {/* Priority is computed -- category severity, how many people reported
          it, and how long it has gone unresolved. An officer standing in
          front of the problem knows things the formula does not, so they can
          overrule it; doing so locks the ticket, because an override the next
          corroboration silently wipes is worse than no override at all. */}
      {isAuthority && !ticket.parent_id && (
        <Card>
          <h2 className="font-bold" style={{ fontSize: 'var(--step-md)' }}>
            {t('priority.title')}
          </h2>
          <p className="mt-1 hint">
            {ticket.priority_locked
              ? t('priority.lockedHint')
              : t('priority.autoHint')}
          </p>

          {ticket.priority_locked && ticket.priority_set_by_name && (
            <p className="mt-2" style={{ fontSize: 'var(--step-sm)' }}>
              {t('priority.setBy')} {ticket.priority_set_by_name}
              {ticket.priority_set_at
                ? ` · ${formatDate(ticket.priority_set_at, language)}`
                : ''}
              {ticket.priority_note ? ` — ${ticket.priority_note}` : ''}
            </p>
          )}

          <div className="mt-3">
            <Field label={t('priority.reason')}>
              <input
                className="field"
                value={priorityNote}
                onChange={(e) => setPriorityNote(e.target.value)}
                maxLength={500}
                placeholder={t('priority.reasonHint')}
              />
            </Field>
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            {(['low', 'medium', 'high', 'critical'] as const).map((level) => (
              <Button
                key={level}
                variant={ticket.priority === level ? 'primary' : 'secondary'}
                disabled={busy}
                onClick={() =>
                  act(() =>
                    api.setPriority(ticket.id, level, priorityNote || undefined),
                  ).then(() => setPriorityNote(''))
                }
              >
                {t(`ticket.${level}` as never)}
              </Button>
            ))}
          </div>

          {ticket.priority_locked && (
            <Button
              variant="ghost"
              className="mt-3"
              disabled={busy}
              onClick={() =>
                act(() => api.setPriority(ticket.id, null)).then(() =>
                  setPriorityNote(''),
                )
              }
            >
              ↩ {t('priority.clear')}
            </Button>
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
              <MapPin size={16} /> {t('manage.wrongWard')}
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

      {/* Visible to anyone who could load this ticket at all -- any citizen
          in the municipality, the ward authority, an admin -- because
          "when will this be fixed?" asked where the ward office and a
          neighbour both see it is the point of a public thread. */}
      <Card>
        <h2 className="font-bold" style={{ fontSize: 'var(--step-md)' }}>
          {t('comments.title')} {comments.length > 0 ? `(${comments.length})` : ''}
        </h2>

        {commentError && <ErrorNote message={commentError} />}

        {comments.length === 0 ? (
          <p className="mt-2 hint">{t('comments.none')}</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {comments.map((comment) => (
              <li
                key={comment.id}
                className="rounded-lg p-3"
                style={{ background: 'var(--color-canvas)' }}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="font-semibold" style={{ fontSize: 'var(--step-sm)' }}>
                      {comment.author_name ?? t('comments.someone')}
                    </span>
                    {comment.author_role && comment.author_role !== 'citizen' && (
                      <span
                        className="chip ml-2"
                        style={{ fontSize: 'var(--step-xs)', padding: '0.05rem 0.5rem' }}
                      >
                        {t(`comments.role.${comment.author_role}` as never)}
                      </span>
                    )}
                    {comment.is_urgent && comment.author_role === 'citizen' && (
                      <span
                        className="chip ml-2"
                        title={t('comments.urgentHint')}
                        style={{
                          fontSize: 'var(--step-xs)',
                          padding: '0.05rem 0.5rem',
                          background: 'var(--color-warn-soft)',
                          color: 'var(--color-warn)',
                          borderColor: 'var(--color-warn)',
                        }}
                      >
                        <Zap size={13} className="mr-1 inline" />{t('comments.urgent')}
                      </span>
                    )}
                  </div>
                  {(comment.is_mine || isAuthority) && (
                    <ConfirmDialog
                      trigger={<button type="button" className="rounded-md p-1.5 text-ink-soft hover:bg-surface" disabled={commentBusy} aria-label={t('common.delete')}><X size={15} /></button>}
                      title={t('common.delete')}
                      description="This comment will be permanently removed from the public discussion."
                      confirmLabel={t('common.delete')}
                      destructive
                      onConfirm={() => removeComment(comment.id)}
                    />
                  )}
                </div>
                <p className="mt-1" style={{ fontSize: 'var(--step-sm)' }}>
                  {comment.body}
                </p>
                <p className="mt-1 hint">{formatDate(comment.created_at, language)}</p>
              </li>
            ))}
          </ul>
        )}

        <div className="mt-4">
          <p className="hint mb-2">{t('comments.urgentHint')}</p>
          <Field label={t('comments.addLabel')}>
            <textarea
              className="field"
              rows={2}
              value={commentDraft}
              onChange={(e) => setCommentDraft(e.target.value)}
              maxLength={2000}
              placeholder={t('comments.placeholder')}
            />
          </Field>
          <Button
            variant="secondary"
            className="mt-2"
            disabled={commentBusy || !commentDraft.trim()}
            onClick={submitComment}
          >
            {t('comments.post')}
          </Button>
        </div>
      </Card>
    </div>
  )
}
