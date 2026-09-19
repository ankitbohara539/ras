import { useEffect, useRef, useState } from 'react'
import { Button, Card, ErrorNote, Field } from '../../components/ui'
import { LocationMap } from '../../components/LocationMap'
import { api } from '../../lib/api'
import { formatCoords, useGeolocation } from '../../lib/geo'
import { useI18n } from '../../lib/i18n'
import type { Category, Coords, Ward } from '../../lib/types'

export const MAX_PHOTOS = 4

// Where the map opens when GPS is refused, so the pin can still be placed by
// hand: Kathmandu. The citizen moves it; nothing is submitted from here.
const FALLBACK_CENTER = { latitude: 27.7172, longitude: 85.324 }

// Above this the fix is a Wi-Fi/cell guess, not GPS: ask for the pin.
const ROUGH_ACCURACY_M = 50

/** What one report in the form currently holds; the page submits these. */
export type DraftValue = {
  description: string
  categoryId: string
  address: string
  photos: File[]
  coords: Coords | null
}

export const EMPTY_DRAFT: DraftValue = {
  description: '',
  categoryId: '',
  address: '',
  photos: [],
  coords: null,
}

/**
 * One report inside the report form. The page can hold several, so each has
 * its own location, place name, ward and photos.
 *
 * The first report locates by GPS. A report added after it starts with its
 * pin where the previous one's is -- the usual case is several problems at
 * the same spot -- and the citizen drags it if this one is somewhere else.
 */
export function ReportDraft({
  index,
  total,
  categories,
  startAt,
  onChange,
  onRemove,
}: {
  index: number
  total: number
  categories: Category[]
  /** Start the pin here instead of asking GPS. */
  startAt: Coords | null
  onChange: (value: DraftValue) => void
  onRemove?: () => void
}) {
  const { t, language } = useI18n()
  const { state: geo, locate, setManual } = useGeolocation()
  const fileInput = useRef<HTMLInputElement>(null)

  const [categoryId, setCategoryId] = useState('')
  const [description, setDescription] = useState('')
  const [address, setAddress] = useState('')
  // Once the citizen types in the address box, the pin stops overwriting it.
  const [addressTouched, setAddressTouched] = useState(false)
  const [place, setPlace] = useState<string | null>(null)
  const [placeLoading, setPlaceLoading] = useState(false)
  const [destinationWard, setDestinationWard] = useState<Ward | null>(null)
  const [photos, setPhotos] = useState<File[]>([])
  const [previews, setPreviews] = useState<string[]>([])

  // Ask for location immediately: it is required, and asking late means the
  // citizen fills in the whole form and then hits a permission wall.
  useEffect(() => {
    if (startAt) setManual(startAt)
    else locate()
    // Only on mount: startAt is where this report *starts*, not a binding.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const urls = photos.map((photo) => URL.createObjectURL(photo))
    setPreviews(urls)
    return () => urls.forEach((url) => URL.revokeObjectURL(url))
  }, [photos])

  const readyLat = geo.kind === 'ready' ? geo.coords.latitude : null
  const readyLon = geo.kind === 'ready' ? geo.coords.longitude : null

  // Report up whenever anything the submit needs changes.
  useEffect(() => {
    onChange({
      description,
      categoryId,
      address,
      photos,
      coords:
        readyLat !== null && readyLon !== null
          ? { latitude: readyLat, longitude: readyLon }
          : null,
    })
    // onChange is a fresh closure each parent render; the values are what matter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [description, categoryId, address, photos, readyLat, readyLon])

  // Resolve which ward will receive this, and show it before submitting.
  // Routing is by location, not by the ward you registered under, and
  // finding that out afterwards is far too late. The same call names the
  // place. Waits for the pin to settle -- GPS refining or a finger dragging
  // would otherwise fire a request per movement.
  useEffect(() => {
    if (readyLat === null || readyLon === null) {
      setDestinationWard(null)
      setPlace(null)
      return
    }

    let cancelled = false
    const coords = { latitude: readyLat, longitude: readyLon }
    setPlaceLoading(true)

    const timer = window.setTimeout(() => {
      api
        .reverseGeocode(coords, language)
        .then((found) => {
          if (cancelled) return
          setPlace(found.place_name)
          setDestinationWard(found.ward)
          if (found.place_name && !addressTouched) setAddress(found.place_name)
        })
        .catch(() => {
          if (cancelled) return
          setPlace(null)
          // The place name is optional; the ward is not. Fall back.
          api
            .nearestWard(coords)
            .then((ward) => {
              if (!cancelled) setDestinationWard(ward)
            })
            .catch(() => {
              if (!cancelled) setDestinationWard(null)
            })
        })
        .finally(() => {
          if (!cancelled) setPlaceLoading(false)
        })
    }, 500)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
    // addressTouched is read, not reacted to: typing must not re-geocode.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readyLat, readyLon, language])

  const addPhotos = (picked: File[]) => {
    if (picked.length === 0) return
    setPhotos((current) => [...current, ...picked].slice(0, MAX_PHOTOS))
  }

  return (
    <section
      className="space-y-4"
      aria-label={total > 1 ? `${t('report.reportN')} ${index + 1}` : undefined}
    >
      {total > 1 && (
        <div className="flex items-center gap-2">
          <h2 className="font-bold" style={{ fontSize: 'var(--step-md)' }}>
            {t('report.reportN')} {index + 1}
          </h2>
          {onRemove && (
            <Button
              type="button"
              variant="ghost"
              className="ml-auto"
              style={{ minHeight: 'auto', padding: '0.25rem 0.6rem' }}
              onClick={onRemove}
            >
              ✕ {t('report.remove')}
            </Button>
          )}
        </div>
      )}

      <Card>
        <Field label={t('report.description')} hint={t('report.descriptionHint')} required>
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
        {startAt && index > 0 && <p className="hint mb-2">{t('report.sameSpotHint')}</p>}

        {geo.kind === 'ready' ? (
          <div className="space-y-2">
            <LocationMap
              coords={geo.coords}
              accuracy={geo.source === 'gps' ? geo.accuracy : 0}
              onChange={setManual}
            />
            <p className="hint">{t('report.pinHint')}</p>

            {geo.source === 'gps' && geo.accuracy > ROUGH_ACCURACY_M && !geo.refining && (
              <p
                className="rounded-lg p-2"
                role="status"
                style={{
                  fontSize: 'var(--step-sm)',
                  background: 'var(--color-warn-soft)',
                  color: 'var(--color-warn)',
                }}
              >
                ⚠ {t('report.lowAccuracy')} (±{geo.accuracy}m)
              </p>
            )}

            <dl
              className="grid gap-1 rounded-lg p-3"
              style={{ background: 'var(--color-good-soft)', fontSize: 'var(--step-sm)' }}
            >
              <div className="flex flex-wrap items-baseline gap-x-2">
                <dt className="hint">📍 {t('report.placeName')}:</dt>
                <dd className="font-semibold">
                  {place ?? (placeLoading ? t('report.findingPlace') : '—')}
                </dd>
              </div>
              <div className="flex flex-wrap items-baseline gap-x-2">
                <dt className="hint">{t('report.coordinates')}:</dt>
                <dd className="font-mono">
                  {formatCoords(geo.coords.latitude, geo.coords.longitude)}
                </dd>
                {geo.source === 'gps' && geo.accuracy > 0 && (
                  <span className="hint">±{geo.accuracy}m</span>
                )}
                {geo.source === 'manual' && (
                  <span className="chip">{t('report.pinnedByHand')}</span>
                )}
                {geo.refining && <span className="hint">{t('report.refining')}</span>}
              </div>
            </dl>

            <button
              type="button"
              onClick={locate}
              className="btn btn-ghost"
              style={{ minHeight: 'auto', padding: '0.25rem 0.6rem' }}
            >
              📡 {geo.source === 'manual' ? t('report.backToGps') : t('common.retry')}
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
            {geo.kind === 'error' && (
              <>
                <ErrorNote message={geo.message} />
                {/* No GPS is no reason to lose the report: place it by hand. */}
                <LocationMap coords={FALLBACK_CENTER} onChange={setManual} />
                <p className="hint">{t('report.pinHint')}</p>
              </>
            )}
            <p className="hint">{t('report.locationNeeded')}</p>
          </div>
        )}

        {destinationWard && (
          <div className="mt-3 rounded-lg p-3" style={{ background: 'var(--color-brand-soft)' }}>
            <p className="font-semibold" style={{ fontSize: 'var(--step-sm)' }}>
              {t('report.goesToWard')}: {t('auth.ward')} {destinationWard.number}
              {destinationWard.name_en
                ? ` — ${language === 'ne' ? destinationWard.name_ne : destinationWard.name_en}`
                : ''}
            </p>
            <p className="mt-0.5 hint">{t('report.wardExplainer')}</p>
          </div>
        )}

        <div className="mt-4">
          <Field label={t('report.address')} hint={t('report.addressHint')}>
            <input
              className="field"
              value={address}
              onChange={(e) => {
                setAddress(e.target.value)
                setAddressTouched(true)
              }}
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
          onChange={(e) => {
            // Copy the files out *now*: `files` is a live list that the reset
            // below empties, and the state update reads it later. Reading it
            // lazily is what made every selected photo silently vanish.
            const picked = Array.from(e.target.files ?? [])
            // Reset so choosing the same file again still fires onChange.
            e.target.value = ''
            addPhotos(picked)
          }}
        />

        <div className="mt-3 flex flex-wrap gap-2">
          {previews.map((url, photoIndex) => (
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
                  setPhotos((current) => current.filter((_, i) => i !== photoIndex))
                }
                className="absolute -right-2 -top-2 flex h-7 w-7 items-center justify-center rounded-full text-white"
                style={{ background: 'var(--color-danger)' }}
                aria-label={`Remove photo ${photoIndex + 1}`}
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
    </section>
  )
}
