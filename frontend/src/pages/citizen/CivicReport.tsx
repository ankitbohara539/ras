import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { AlertTriangle, Camera, ClipboardList, LocateFixed, MapPin, Pencil, Plus, Trash2, X } from 'lucide-react'
import { CivicStatusBadge } from '../../components/CivicStatusBadge'
import { LocationMap } from '../../components/LocationMap'
import { Button, Card, ConfirmDialog, ErrorNote, Field, PageTitle, Spinner, SuccessNote } from '../../components/ui'
import { api } from '../../lib/api'
import { CIVIC_GROUPS } from '../../lib/civic'
import { formatCoords, formatDate, useGeolocation } from '../../lib/geo'
import { useI18n } from '../../lib/i18n'
import type { CivicCategory, CivicComplaint, Ward } from '../../lib/types'

const MAX_PHOTOS = 3
const FALLBACK_CENTER = { latitude: 27.7172, longitude: 85.324 }

/** Local "now" in the format a datetime-local input wants. */
function localNow(): string {
  const now = new Date()
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset())
  return now.toISOString().slice(0, 16)
}

/**
 * Report a person's conduct -- littering, spitting, blocking the footpath.
 *
 * Unlike a ticket this is private: only the ward office where it happened
 * sees it (and the photo). The page says so up front, along with the rules
 * that keep it from turning into a way to harass people.
 */
export function CivicReport() {
  const { t, language } = useI18n()
  const [tab, setTab] = useState<'new' | 'mine'>('new')
  const [mine, setMine] = useState<CivicComplaint[] | null>(null)
  const [editing, setEditing] = useState<CivicComplaint | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadMine = useCallback(async () => {
    try {
      setMine((await api.civicComplaints({ limit: 100 })).items)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load civic-sense content.')
      setMine([])
    }
  }, [])

  useEffect(() => {
    if (tab === 'mine') void loadMine()
  }, [tab, loadMine])

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageTitle title={t('civic.title')} subtitle={t('civic.subtitle')} />
      {error && <ErrorNote message={error} />}

      <div className="flex gap-2" role="tablist">
        {(['new', 'mine'] as const).map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            className={`btn ${tab === key ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setTab(key)}
          >
            {key === 'new' ? <Plus size={16} /> : <ClipboardList size={16} />}
            {key === 'new' ? t('civic.newTab') : t('civic.mineTab')}
          </button>
        ))}
      </div>

      {tab === 'new' ? (
        <NewComplaint language={language} onFiled={() => setTab('mine')} />
      ) : mine === null ? (
        <Spinner />
      ) : mine.length === 0 ? (
        <Card>
          <p className="hint">{t('civic.noneYet')}</p>
        </Card>
      ) : (
        mine.map((complaint) => (
          <Card key={complaint.id}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono font-bold">{complaint.public_code}</span>
              <CivicStatusBadge status={complaint.status} />
              <span className="ml-auto hint">{formatDate(complaint.created_at, language)}</span>
            </div>
            <p className="mt-1 font-semibold">{t(`civic.cat.${complaint.category}` as never)}</p>
            <p className="mt-1" style={{ fontSize: 'var(--step-sm)' }}>
              {complaint.description}
            </p>
            {complaint.address_text && <p className="mt-1 flex items-center gap-1.5 hint"><MapPin size={14} />{complaint.address_text}</p>}
            {complaint.action_note && (
              <div className="mt-2 rounded-lg p-2" style={{ background: 'var(--color-canvas)' }}>
                <p className="hint">{t('civic.officeSaid')}</p>
                <p style={{ fontSize: 'var(--step-sm)' }}>{complaint.action_note}</p>
              </div>
            )}
            {complaint.status === 'submitted' && (
              <div className="mt-3 flex flex-wrap gap-2">
                <Button type="button" size="sm" variant="secondary" onClick={() => setEditing(complaint)}><Pencil size={15} /> Edit</Button>
                <ConfirmDialog destructive trigger={<Button type="button" size="sm" variant="danger"><Trash2 size={15} /> Delete</Button>} title="Delete this civic complaint?" description="This removes the complaint and its evidence photos permanently." confirmLabel="Delete complaint" onConfirm={async () => { try { await api.deleteCivicComplaint(complaint.id); await loadMine() } catch (err) { setError(err instanceof Error ? err.message : 'Could not delete the civic complaint.') } }} />
              </div>
            )}
          </Card>
        ))
      )}
      {editing && <EditComplaint complaint={editing} onClose={() => setEditing(null)} onSaved={async () => { setEditing(null); await loadMine() }} />}
    </div>
  )
}

function EditComplaint({ complaint, onClose, onSaved }: { complaint: CivicComplaint; onClose: () => void; onSaved: () => Promise<void> }) {
  const { t } = useI18n()
  const [description, setDescription] = useState(complaint.description)
  const [address, setAddress] = useState(complaint.address_text ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const save = async () => {
    if (description.trim().length < 10) { setError('Please enter at least 10 characters.'); return }
    setBusy(true); setError(null)
    try { await api.updateCivicComplaint(complaint.id, { description: description.trim(), address_text: address.trim() || null }); await onSaved() } catch (err) { setError(err instanceof Error ? err.message : 'Could not update the civic complaint.') } finally { setBusy(false) }
  }
  return <div className="fixed inset-0 z-50 flex items-end bg-navy/40 p-3 sm:items-center sm:justify-center"><Card className="w-full max-w-lg space-y-4"><div className="flex items-center justify-between"><h2 className="font-semibold">Edit civic complaint</h2><Button type="button" size="sm" variant="ghost" onClick={onClose}>Close</Button></div>{error && <ErrorNote message={error} />}<Field label={t('civic.describe')} required><textarea className="field" rows={4} minLength={10} maxLength={2000} value={description} onChange={(event) => setDescription(event.target.value)} /></Field><Field label="Address or landmark"><input className="field" maxLength={300} value={address} onChange={(event) => setAddress(event.target.value)} /></Field><div className="flex gap-2"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="button" disabled={busy} onClick={() => void save()}>{busy ? 'Saving…' : 'Save changes'}</Button></div></Card></div>
}

function NewComplaint({
  language,
  onFiled,
}: {
  language: 'en' | 'ne'
  onFiled: () => void
}) {
  const { t } = useI18n()
  const { state: geo, locate, setManual } = useGeolocation()
  const fileInput = useRef<HTMLInputElement>(null)

  const [category, setCategory] = useState<CivicCategory | ''>('')
  const [description, setDescription] = useState('')
  const [occurredAt, setOccurredAt] = useState(localNow)
  const [photos, setPhotos] = useState<File[]>([])
  const [previews, setPreviews] = useState<string[]>([])
  const [place, setPlace] = useState<string | null>(null)
  const [ward, setWard] = useState<Ward | null>(null)
  const [acknowledged, setAcknowledged] = useState(false)

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filed, setFiled] = useState<CivicComplaint | null>(null)

  useEffect(() => {
    locate()
  }, [locate])

  useEffect(() => {
    const urls = photos.map((photo) => URL.createObjectURL(photo))
    setPreviews(urls)
    return () => urls.forEach((url) => URL.revokeObjectURL(url))
  }, [photos])

  const lat = geo.kind === 'ready' ? geo.coords.latitude : null
  const lon = geo.kind === 'ready' ? geo.coords.longitude : null

  useEffect(() => {
    if (lat === null || lon === null) return
    let cancelled = false
    const timer = window.setTimeout(() => {
      api
        .reverseGeocode({ latitude: lat, longitude: lon }, language)
        .then((found) => {
          if (cancelled) return
          setPlace(found.place_name)
          setWard(found.ward)
        })
        .catch(() => {
          if (!cancelled) setPlace(null)
        })
    }, 500)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [lat, lon, language])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    if (lat === null || lon === null) {
      setError(t('report.locationNeeded'))
      return
    }
    if (!category) {
      setError(t('civic.pickCategory'))
      return
    }
    if (photos.length === 0) {
      setError(t('civic.photoRequired'))
      return
    }

    setBusy(true)
    try {
      const complaint = await api.fileCivicComplaint(
        {
          category,
          description,
          latitude: lat,
          longitude: lon,
          address_text: place ?? undefined,
          occurred_at: new Date(occurredAt).toISOString(),
        },
        photos,
      )
      setFiled(complaint)
      window.scrollTo({ top: 0 })
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setBusy(false)
    }
  }

  if (filed) {
    return (
      <Card>
        <SuccessNote>
          {t('civic.filed')} <span className="font-mono font-bold">{filed.public_code}</span>
        </SuccessNote>
        <p className="mt-2 hint">
          {t('civic.filedNote')}
          {filed.ward_number !== null &&
            ` ${t('auth.ward')} ${filed.ward_number}${filed.ward_name ? ` — ${filed.ward_name}` : ''}.`}
        </p>
        <Button className="mt-3" onClick={onFiled}>
          <ClipboardList size={16} /> {t('civic.mineTab')}
        </Button>
      </Card>
    )
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      {/* Privacy and safety first: this photographs real people. */}
      <div
        className="rounded-lg border p-3"
        style={{ background: 'var(--color-warn-soft)', borderColor: 'var(--color-warn)' }}
      >
        <p className="font-semibold" style={{ color: 'var(--color-warn)' }}>
          <AlertTriangle size={17} className="mr-1.5 inline" />{t('civic.rulesTitle')}
        </p>
        <ul className="mt-1 list-disc space-y-0.5 pl-5" style={{ fontSize: 'var(--step-sm)' }}>
          <li>{t('civic.rulePhotoAct')}</li>
          <li>{t('civic.ruleSafety')}</li>
          <li>{t('civic.ruleChildren')}</li>
          <li>{t('civic.rulePrivate')}</li>
          <li>{t('civic.ruleFalse')}</li>
        </ul>
      </div>

      {error && <ErrorNote message={error} />}

      <Card>
        <p className="label">{t('civic.whatHappened')}</p>
        <div className="grid gap-3 sm:grid-cols-2">
          {CIVIC_GROUPS.map((group) => (
            <fieldset key={group.key} className="rounded-lg border p-2" style={{ borderColor: 'var(--color-line)' }}>
              <legend className="px-1 font-semibold" style={{ fontSize: 'var(--step-sm)' }}>
                <group.icon size={16} className="mr-1.5 inline" />{t(`civic.group.${group.key}` as never)}
              </legend>
              {group.categories.map((key) => (
                <label key={key} className="flex items-center gap-2 py-1" style={{ fontSize: 'var(--step-sm)' }}>
                  <input
                    type="radio"
                    name="civic-category"
                    value={key}
                    checked={category === key}
                    onChange={() => setCategory(key)}
                  />
                  {t(`civic.cat.${key}` as never)}
                </label>
              ))}
            </fieldset>
          ))}
        </div>

        <div className="mt-4">
          <Field label={t('civic.describe')} hint={t('civic.describeHint')} required>
            <textarea
              className="field"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
              minLength={10}
              maxLength={2000}
            />
          </Field>
        </div>

        <div className="mt-4">
          <Field label={t('civic.when')}>
            <input
              type="datetime-local"
              className="field"
              value={occurredAt}
              max={localNow()}
              onChange={(e) => setOccurredAt(e.target.value)}
              required
            />
          </Field>
        </div>
      </Card>

      <Card>
        <p className="label">{t('civic.photos')} *</p>
        <p className="hint">{t('civic.photosHint')}</p>
        <input
          ref={fileInput}
          type="file"
          accept="image/*"
          capture="environment"
          multiple
          className="sr-only"
          onChange={(e) => {
            // Copy before resetting: the reset empties the live FileList,
            // and the state update would otherwise read it after that.
            const picked = Array.from(e.target.files ?? [])
            e.target.value = ''
            if (picked.length) setPhotos((current) => [...current, ...picked].slice(0, MAX_PHOTOS))
          }}
        />
        <div className="mt-3 flex flex-wrap gap-2">
          {previews.map((url, index) => (
            <div key={url} className="relative">
              <img src={url} alt="" className="h-24 w-24 rounded-lg object-cover" />
              <button
                type="button"
                onClick={() => setPhotos((current) => current.filter((_, i) => i !== index))}
                className="absolute -right-2 -top-2 flex h-7 w-7 items-center justify-center rounded-full text-white"
                style={{ background: 'var(--color-danger)' }}
                aria-label={`Remove photo ${index + 1}`}
              >
                <X size={15} />
              </button>
            </div>
          ))}
          {photos.length < MAX_PHOTOS && (
            <button
              type="button"
              onClick={() => fileInput.current?.click()}
              className="flex h-24 w-24 flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed"
              style={{ borderColor: 'var(--color-line)', color: 'var(--color-ink-soft)' }}
            >
              <Camera size={22} aria-hidden="true" />
              <span style={{ fontSize: '0.7rem' }}>{t('report.addPhoto')}</span>
            </button>
          )}
        </div>
      </Card>

      <Card>
        <p className="label">{t('civic.where')}</p>
        {geo.kind === 'ready' ? (
          <div className="space-y-2">
            <LocationMap coords={geo.coords} accuracy={geo.source === 'gps' ? geo.accuracy : 0} onChange={setManual} />
            <p className="hint">{t('report.pinHint')}</p>
            <p style={{ fontSize: 'var(--step-sm)' }}>
              <MapPin size={15} className="mr-1 inline" /> <span className="font-semibold">{place ?? '—'}</span>
              <br />
              <span className="font-mono hint">{formatCoords(geo.coords.latitude, geo.coords.longitude)}</span>
            </p>
            {ward && (
              <p className="hint">
                {t('civic.goesTo')}: {t('auth.ward')} {ward.number}
                {ward.name_en ? ` — ${language === 'ne' ? ward.name_ne : ward.name_en}` : ''}
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            <Button type="button" variant="secondary" onClick={locate} className="w-full" disabled={geo.kind === 'locating'}>
              <LocateFixed size={16} /> {geo.kind === 'locating' ? t('report.locating') : t('report.useMyLocation')}
            </Button>
            {geo.kind === 'error' && (
              <>
                <ErrorNote message={geo.message} />
                <LocationMap coords={FALLBACK_CENTER} onChange={setManual} />
              </>
            )}
          </div>
        )}
      </Card>

      <label className="flex items-start gap-2" style={{ fontSize: 'var(--step-sm)' }}>
        <input
          type="checkbox"
          className="mt-1"
          checked={acknowledged}
          onChange={(e) => setAcknowledged(e.target.checked)}
          required
        />
        {t('civic.acknowledge')}
      </label>

      <Button type="submit" className="w-full" disabled={busy || !acknowledged || geo.kind !== 'ready'}>
        {busy ? t('report.submitting') : t('civic.submit')}
      </Button>
    </form>
  )
}
