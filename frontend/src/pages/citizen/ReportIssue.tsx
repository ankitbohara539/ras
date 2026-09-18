import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Button,
  Card,
  ErrorNote,
  Field,
  PageTitle,
  StatusBadge,
} from '../../components/ui'
import { api } from '../../lib/api'
import { formatDistance, useGeolocation } from '../../lib/geo'
import { useI18n } from '../../lib/i18n'
import type { Category, DuplicateCandidate, TicketDetail } from '../../lib/types'

const MAX_PHOTOS = 4

export function ReportIssue() {
  const { t, language } = useI18n()
  const navigate = useNavigate()
  const { state: geo, locate } = useGeolocation()
  const fileInput = useRef<HTMLInputElement>(null)

  const [categories, setCategories] = useState<Category[]>([])
  const [categoryId, setCategoryId] = useState('')
  const [description, setDescription] = useState('')
  const [address, setAddress] = useState('')
  const [photos, setPhotos] = useState<File[]>([])
  const [previews, setPreviews] = useState<string[]>([])

  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{
    ticket: TicketDetail
    duplicates: DuplicateCandidate[]
  } | null>(null)

  useEffect(() => {
    api.categories().then(setCategories).catch(() => setCategories([]))
  }, [])

  // Ask for location immediately: it is required, and asking late means the
  // citizen fills in the whole form and then hits a permission wall.
  useEffect(() => {
    locate()
  }, [locate])

  useEffect(() => {
    const urls = photos.map((photo) => URL.createObjectURL(photo))
    setPreviews(urls)
    return () => urls.forEach((url) => URL.revokeObjectURL(url))
  }, [photos])

  const addPhotos = (files: FileList | null) => {
    if (!files) return
    setPhotos((current) => [...current, ...Array.from(files)].slice(0, MAX_PHOTOS))
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)

    if (geo.kind !== 'ready') {
      setError(t('report.locationNeeded'))
      return
    }

    setBusy(true)
    try {
      const response = await api.createTicket(
        {
          description,
          latitude: geo.coords.latitude,
          longitude: geo.coords.longitude,
          category_id: categoryId || undefined,
          address_text: address || undefined,
          description_lang: language,
        },
        photos,
      )
      setResult({
        ticket: response.ticket,
        duplicates: response.possible_duplicates,
      })
      window.scrollTo({ top: 0 })
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setBusy(false)
    }
  }

  if (result) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <div
          className="card p-5 text-center"
          style={{
            background: 'var(--color-good-soft)',
            borderColor: 'var(--color-good)',
          }}
        >
          <p aria-hidden="true" style={{ fontSize: '2.5rem' }}>
            ✅
          </p>
          <h1
            className="font-bold"
            style={{ fontSize: 'var(--step-lg)', color: 'var(--color-good)' }}
          >
            {t('report.submitted')}
          </h1>
          <p className="mt-1 font-mono font-bold" style={{ fontSize: 'var(--step-lg)' }}>
            {result.ticket.public_code}
          </p>
          <div className="mt-2 flex justify-center">
            <StatusBadge status={result.ticket.status} />
          </div>
        </div>

        {result.duplicates.length > 0 && (
          <Card>
            <h2 className="font-bold" style={{ fontSize: 'var(--step-md)' }}>
              {t('report.possibleDuplicates')}
            </h2>
            <p className="mt-1 hint">{t('report.duplicateNote')}</p>

            <div className="mt-3 space-y-2">
              {result.duplicates.map((candidate) => (
                <div
                  key={candidate.id}
                  className="rounded-lg border p-3"
                  style={{ borderColor: 'var(--color-line)' }}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono font-semibold">
                      {candidate.candidate?.public_code}
                    </span>
                    {candidate.candidate && (
                      <StatusBadge status={candidate.candidate.status} />
                    )}
                    <span className="ml-auto hint">
                      {formatDistance(candidate.distance_m)} {t('common.away')}
                    </span>
                  </div>
                  <p className="mt-1" style={{ fontSize: 'var(--step-sm)' }}>
                    {candidate.candidate?.title}
                  </p>
                </div>
              ))}
            </div>
          </Card>
        )}

        <div className="flex flex-wrap gap-2">
          <Button onClick={() => navigate(`/tickets/${result.ticket.id}`)}>
            View my report
          </Button>
          <Link to="/" className="btn btn-secondary">
            {t('nav.home')}
          </Link>
        </div>
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-2xl space-y-4">
      <PageTitle title={t('report.title')} />

      {error && <ErrorNote message={error} />}

      <Card>
        <Field
          label={t('report.description')}
          hint={t('report.descriptionHint')}
          required
        >
          <textarea
            className="field"
            rows={5}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
            minLength={10}
            maxLength={4000}
            placeholder={
              language === 'ne'
                ? 'जस्तै: बस स्टप नजिक सडकमा ठूलो खाल्डो छ...'
                : 'e.g. There is a big pothole on the road near the bus stop...'
            }
          />
        </Field>

        <div className="mt-4">
          <Field label={t('report.category')}>
            <select
              className="field"
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
            >
              <option value="">{t('report.categoryAuto')}</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {language === 'ne' ? category.name_ne : category.name_en}
                </option>
              ))}
            </select>
          </Field>
        </div>
      </Card>

      <Card>
        <p className="label">{t('report.location')}</p>

        {geo.kind === 'ready' ? (
          <div
            className="flex flex-wrap items-center gap-2 rounded-lg p-3"
            style={{ background: 'var(--color-good-soft)' }}
          >
            <span aria-hidden="true">📍</span>
            <span className="font-mono" style={{ fontSize: 'var(--step-sm)' }}>
              {geo.coords.latitude.toFixed(5)}, {geo.coords.longitude.toFixed(5)}
            </span>
            {geo.accuracy > 0 && (
              <span className="hint">±{geo.accuracy}m</span>
            )}
            <button
              type="button"
              onClick={locate}
              className="btn btn-ghost ml-auto"
              style={{ minHeight: 'auto', padding: '0.25rem 0.6rem' }}
            >
              {t('common.retry')}
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <Button
              type="button"
              variant="secondary"
              onClick={locate}
              disabled={geo.kind === 'locating'}
              className="w-full"
            >
              📍 {geo.kind === 'locating' ? t('report.locating') : t('report.useMyLocation')}
            </Button>
            {geo.kind === 'error' && <ErrorNote message={geo.message} />}
            <p className="hint">{t('report.locationNeeded')}</p>
          </div>
        )}

        <div className="mt-4">
          <Field label={t('report.address')}>
            <input
              className="field"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              maxLength={300}
            />
          </Field>
        </div>
      </Card>

      <Card>
        <p className="label">{t('report.photos')}</p>
        <p className="hint">{t('report.photoHint')}</p>

        <input
          ref={fileInput}
          type="file"
          accept="image/*"
          capture="environment"
          multiple
          className="sr-only"
          onChange={(e) => addPhotos(e.target.files)}
        />

        <div className="mt-3 flex flex-wrap gap-2">
          {previews.map((url, index) => (
            <div key={url} className="relative">
              <img
                src={url}
                alt=""
                className="h-24 w-24 rounded-lg object-cover"
                style={{ border: '1px solid var(--color-line)' }}
              />
              <button
                type="button"
                onClick={() =>
                  setPhotos((current) => current.filter((_, i) => i !== index))
                }
                className="absolute -right-2 -top-2 flex h-7 w-7 items-center justify-center rounded-full text-white"
                style={{ background: 'var(--color-danger)' }}
                aria-label={`Remove photo ${index + 1}`}
              >
                ×
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
              <span aria-hidden="true" style={{ fontSize: '1.5rem' }}>
                📷
              </span>
              <span style={{ fontSize: '0.7rem' }}>{t('report.addPhoto')}</span>
            </button>
          )}
        </div>
      </Card>

      <Button
        type="submit"
        disabled={busy || geo.kind !== 'ready'}
        className="w-full"
      >
        {busy ? t('report.submitting') : t('report.submit')}
      </Button>
    </form>
  )
}
