import { useCallback, useEffect, useState } from 'react'
import { Map, MapPin, Pencil, Trash2 } from 'lucide-react'
import { CivicStatusBadge } from '../../components/CivicStatusBadge'
import { LocationMap } from '../../components/LocationMap'
import { Button, Card, ConfirmDialog, EmptyState, ErrorNote, Field, PageTitle, Spinner } from '../../components/ui'
import { api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { CIVIC_NEEDS_NOTE, CIVIC_NEXT, CIVIC_STATUSES } from '../../lib/civic'
import { formatCoords, formatDate, mapsLink } from '../../lib/geo'
import { useI18n } from '../../lib/i18n'
import type { CivicComplaint, CivicComplaintList, CivicStatus } from '../../lib/types'

/**
 * The ward office's queue of civic-sense complaints -- people seen littering,
 * blocking footpaths and so on. Scoped by the API to this office's ward
 * (all wards for an admin).
 */
export function CivicQueue() {
  const { t } = useI18n()
  const [filter, setFilter] = useState<CivicStatus | 'all'>('submitted')
  const [data, setData] = useState<CivicComplaintList | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setData(
        await api.civicComplaints({
          status: filter === 'all' ? undefined : filter,
          limit: 100,
        }),
      )
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    }
  }, [filter, t])

  useEffect(() => {
    setData(null)
    void load()
  }, [load])

  const counts = data?.counts ?? {}
  const total = Object.values(counts).reduce((sum, n) => sum + (n ?? 0), 0)

  return (
    <div className="space-y-4">
      <PageTitle title={t('civicQueue.title')} subtitle={t('civicQueue.subtitle')} />

      <div className="flex flex-wrap gap-2" role="tablist">
        {([...CIVIC_STATUSES, 'all'] as const).map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={filter === key}
            className={`btn ${filter === key ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setFilter(key)}
          >
            {key === 'all' ? t('civicQueue.all') : t(`civic.status.${key}` as never)}{' '}
            <span className="chip">{key === 'all' ? total : counts[key] ?? 0}</span>
          </button>
        ))}
      </div>

      {error && <ErrorNote message={error} />}

      {data === null ? (
        <Spinner />
      ) : data.items.length === 0 ? (
        <EmptyState title={t('civicQueue.empty')} />
      ) : (
        <div className="space-y-4">
          {data.items.map((complaint) => (
            <ComplaintCard key={complaint.id} complaint={complaint} onChanged={load} />
          ))}
        </div>
      )}
    </div>
  )
}

function ComplaintCard({
  complaint,
  onChanged,
}: {
  complaint: CivicComplaint
  onChanged: () => Promise<void>
}) {
  const { t, language } = useI18n()
  const { isAdmin } = useAuth()
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showMap, setShowMap] = useState(false)
  const [editing, setEditing] = useState(false)
  const [description, setDescription] = useState(complaint.description)
  const [address, setAddress] = useState(complaint.address_text ?? '')

  const move = async (next: CivicStatus) => {
    if (CIVIC_NEEDS_NOTE.includes(next) && !note.trim()) {
      setError(t('civicQueue.noteRequired'))
      return
    }
    setBusy(true)
    setError(null)
    try {
      await api.updateCivicStatus(complaint.id, next, note.trim() || undefined)
      setNote('')
      await onChanged()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setBusy(false)
    }
  }

  const next = CIVIC_NEXT[complaint.status]
  const saveContent = async () => {
    if (description.trim().length < 10) { setError('Please enter at least 10 characters.'); return }
    setBusy(true); setError(null)
    try { await api.updateCivicComplaint(complaint.id, { description: description.trim(), address_text: address.trim() || null }); setEditing(false); await onChanged() } catch (err) { setError(err instanceof Error ? err.message : t('common.error')) } finally { setBusy(false) }
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono font-bold">{complaint.public_code}</span>
        <CivicStatusBadge status={complaint.status} />
        <span className="chip">{t(`civic.cat.${complaint.category}` as never)}</span>
        <span className="ml-auto hint">
          {t('civic.happened')}: {formatDate(complaint.occurred_at, language)}
        </span>
      </div>

      {editing ? <div className="mt-3 space-y-2"><Field label="Description" required><textarea className="field" rows={3} value={description} onChange={(event) => setDescription(event.target.value)} minLength={10} maxLength={2000} /></Field><Field label="Address or landmark"><input className="field" value={address} onChange={(event) => setAddress(event.target.value)} maxLength={300} /></Field><div className="flex gap-2"><Button type="button" variant="secondary" onClick={() => setEditing(false)}>Cancel</Button><Button type="button" disabled={busy} onClick={() => void saveContent()}>{busy ? 'Saving…' : 'Save changes'}</Button></div></div> : <p className="mt-2" style={{ fontSize: 'var(--step-md)' }}>{complaint.description}</p>}
      {isAdmin && !editing && <div className="mt-3 flex flex-wrap gap-2"><Button type="button" size="sm" variant="secondary" onClick={() => setEditing(true)}><Pencil size={15} /> Edit</Button><ConfirmDialog destructive trigger={<Button type="button" size="sm" variant="danger" disabled={busy}><Trash2 size={15} /> Delete</Button>} title="Delete this civic content?" description="This permanently removes the submission and its evidence photos." confirmLabel="Delete content" onConfirm={async () => { try { await api.deleteCivicComplaint(complaint.id); await onChanged() } catch (err) { setError(err instanceof Error ? err.message : t('common.error')) } }} /></div>}

      {complaint.photos.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {complaint.photos.map((photo) =>
            photo.url ? (
              <a key={photo.id} href={photo.url} target="_blank" rel="noreferrer">
                <img
                  src={photo.url}
                  alt={t('civic.evidence')}
                  className="h-32 w-32 rounded-lg object-cover"
                  style={{ border: '1px solid var(--color-line)' }}
                />
              </a>
            ) : null,
          )}
        </div>
      )}

      <dl className="mt-3 grid gap-1 sm:grid-cols-2" style={{ fontSize: 'var(--step-sm)' }}>
        <div>
          <dt className="hint">{t('report.location')}</dt>
          <dd>
            {complaint.address_text && <span className="inline-flex items-center gap-1 font-medium"><MapPin size={14} />{complaint.address_text}</span>}
            <br />
            <span className="font-mono hint">{formatCoords(complaint.latitude, complaint.longitude)}</span>{' '}
            <a
              href={mapsLink(complaint.latitude, complaint.longitude)}
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
          <dt className="hint">{t('civicQueue.reportedBy')}</dt>
          <dd>
            {complaint.reporter_name ?? '—'}
            {complaint.reporter_phone && (
              <>
                {' · '}
                <a href={`tel:${complaint.reporter_phone}`} className="underline">
                  {complaint.reporter_phone}
                </a>
              </>
            )}
            <br />
            <span className="hint">{formatDate(complaint.created_at, language)}</span>
          </dd>
        </div>
        {complaint.ward_number !== null && (
          <div>
            <dt className="hint">{t('auth.ward')}</dt>
            <dd>
              {complaint.ward_number}
              {complaint.ward_name ? ` — ${complaint.ward_name}` : ''}
            </dd>
          </div>
        )}
      </dl>

      <button
        type="button"
        className="btn btn-ghost mt-2"
        style={{ minHeight: 'auto', padding: '0.25rem 0.6rem' }}
        onClick={() => setShowMap((v) => !v)}
      >
        <Map size={16} />{showMap ? t('civicQueue.hideMap') : t('civicQueue.showMap')}
      </button>
      {showMap && (
        <div className="mt-2">
          <LocationMap coords={{ latitude: complaint.latitude, longitude: complaint.longitude }} height={200} />
        </div>
      )}

      {complaint.action_note && (
        <div className="mt-3 rounded-lg p-2" style={{ background: 'var(--color-canvas)' }}>
          <p className="hint">{t('civic.officeSaid')}</p>
          <p style={{ fontSize: 'var(--step-sm)' }}>{complaint.action_note}</p>
        </div>
      )}

      {next.length > 0 && (
        <div className="mt-3 space-y-2">
          {error && <ErrorNote message={error} />}
          <Field label={t('civicQueue.note')} hint={t('civicQueue.noteHint')}>
            <input
              className="field"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={1000}
              placeholder={t('civicQueue.notePlaceholder')}
            />
          </Field>
          <div className="flex flex-wrap gap-2">
            {next.map((status) => (
              <Button
                key={status}
                variant={status === 'dismissed' ? 'secondary' : 'primary'}
                disabled={busy}
                onClick={() => move(status)}
              >
                {t(`civicQueue.to.${status}` as never)}
              </Button>
            ))}
          </div>
        </div>
      )}
    </Card>
  )
}
