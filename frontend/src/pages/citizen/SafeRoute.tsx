import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Accessibility,
  AlertTriangle,
  CarFront,
  CheckCircle2,
  LocateFixed,
  LoaderCircle,
  MapPin,
  Moon,
  MousePointer2,
  Navigation,
  PersonStanding,
  Pin,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { HazardMap } from '../../components/HazardMap'
import { Button, Card, ErrorNote, PageTitle } from '../../components/ui'
import { api } from '../../lib/api'
import { formatDistance, useGeolocation } from '../../lib/geo'
import { formatDuration, hazardKind, HAZARD_KINDS, SEVERITY_COLOR } from '../../lib/hazards'
import { useI18n } from '../../lib/i18n'
import type { Coords, Hazard, PlaceResult, RoutePlan, TravelMode } from '../../lib/types'

const KATHMANDU = { latitude: 27.7172, longitude: 85.324 }

const MODES: { key: TravelMode; icon: LucideIcon }[] = [
  { key: 'walk', icon: PersonStanding },
  { key: 'wheelchair', icon: Accessibility },
  { key: 'drive', icon: CarFront },
]

/**
 * Hazard-aware map: reported hazards around you, and a route that avoids
 * them where it can. Every route carries the same warning -- these are
 * citizen reports, and streets change faster than reports do.
 */
export function SafeRoute() {
  const { t, language } = useI18n()
  const { state: geo, locate } = useGeolocation({ refine: false })

  const [mode, setMode] = useState<TravelMode>('walk')
  const [start, setStart] = useState<Coords | null>(null)
  const [startIsMe, setStartIsMe] = useState(true)
  const [end, setEnd] = useState<Coords | null>(null)
  const [endLabel, setEndLabel] = useState<string | null>(null)
  const [endAddress, setEndAddress] = useState<string | null>(null)
  const [endResolving, setEndResolving] = useState(false)
  const [picking, setPicking] = useState<'start' | 'end'>('end')

  const [hazards, setHazards] = useState<Hazard[]>([])
  const [night, setNight] = useState(false)
  const [plan, setPlan] = useState<RoutePlan | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [queryText, setQueryText] = useState('')
  const [results, setResults] = useState<PlaceResult[]>([])
  const [searching, setSearching] = useState(false)
  const viewTimer = useRef<number | null>(null)
  const searchRequest = useRef(0)
  const addressRequest = useRef(0)

  useEffect(() => {
    locate()
  }, [locate])

  // Start at the citizen's own location until they choose otherwise.
  useEffect(() => {
    if (startIsMe && geo.kind === 'ready') setStart(geo.coords)
  }, [geo, startIsMe])

  // Hazards follow the map view (debounced: panning fires many events).
  const onView = useCallback((box: { min_lat: number; min_lon: number; max_lat: number; max_lon: number }) => {
    if (viewTimer.current) window.clearTimeout(viewTimer.current)
    viewTimer.current = window.setTimeout(() => {
      api
        .hazards(box)
        .then((result) => {
          setHazards(result.items)
          setNight(result.night)
        })
        .catch(() => {
          // Zoomed too far out, or offline: keep what is shown.
        })
    }, 400)
  }, [])

  // Place search, debounced.
  useEffect(() => {
    const q = queryText.trim()
    const requestId = ++searchRequest.current
    if (q.length < 3) {
      setResults([])
      setSearching(false)
      return
    }
    const timer = window.setTimeout(() => {
      setSearching(true)
      api
        .searchPlaces(q, language)
        .then((places) => {
          if (requestId === searchRequest.current) setResults(places)
        })
        .catch(() => {
          if (requestId === searchRequest.current) setResults([])
        })
        .finally(() => {
          if (requestId === searchRequest.current) setSearching(false)
        })
    }, 600)
    return () => window.clearTimeout(timer)
  }, [queryText, language])

  const resolveEndAddress = useCallback(
    async (coords: Coords) => {
      const requestId = ++addressRequest.current
      setEndResolving(true)
      setEndLabel(null)
      setEndAddress(null)
      try {
        const place = await api.reverseGeocode(coords, language)
        if (requestId !== addressRequest.current) return
        setEndLabel(place.place_name)
        setEndAddress(place.display_name ?? place.place_name)
      } catch {
        if (requestId === addressRequest.current) {
          setEndLabel(null)
          setEndAddress(null)
        }
      } finally {
        if (requestId === addressRequest.current) setEndResolving(false)
      }
    },
    [language],
  )

  const onPick = useCallback(
    (coords: Coords) => {
      setPlan(null)
      if (picking === 'start') {
        setStart(coords)
        setStartIsMe(false)
        setPicking('end')
      } else {
        searchRequest.current += 1
        setQueryText('')
        setResults([])
        setEnd(coords)
        void resolveEndAddress(coords)
      }
    },
    [picking, resolveEndAddress],
  )

  const findRoute = async () => {
    if (!start || !end) return
    setBusy(true)
    setError(null)
    try {
      const result = await api.planRoute({ start, end, mode, night })
      setPlan(result)
      setHazards((current) => {
        // Merge in hazards along the route that may be outside the view.
        const byId = new Map(current.map((h) => [h.id, h]))
        for (const h of result.hazards) byId.set(h.id, h)
        return [...byId.values()]
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setBusy(false)
    }
  }

  const hazardById = useMemo(() => new Map(hazards.map((h) => [h.id, h])), [hazards])
  const recommended = plan ? (plan.recommended === 'safer' && plan.safer ? plan.safer : plan.fastest) : null
  const remaining = recommended ? recommended.hazard_ids.map((id) => hazardById.get(id)).filter(Boolean) as Hazard[] : []
  const avoided =
    plan && plan.safer && plan.recommended === 'safer'
      ? (plan.fastest.hazard_ids
          .filter((id) => !plan.safer!.hazard_ids.includes(id))
          .map((id) => hazardById.get(id))
          .filter(Boolean) as Hazard[])
      : []

  const visibleForMode = hazards.filter((h) => h.modes.includes(mode))
  const kindLabel = (kind: string) => {
    const meta = hazardKind(kind)
    const Icon = meta.icon
    return (
      <span className="inline-flex items-center gap-1.5">
        <Icon size={15} aria-hidden="true" />
        {language === 'ne' ? meta.label[1] : meta.label[0]}
      </span>
    )
  }

  return (
    <div className="space-y-4">
      <PageTitle title={t('hazard.title')} subtitle={t('hazard.subtitle')} />

      <p
        className="rounded-lg border p-3"
        role="note"
        style={{ background: 'var(--color-warn-soft)', borderColor: 'var(--color-warn)', fontSize: 'var(--step-sm)' }}
      >
        <AlertTriangle size={17} className="mr-2 inline" aria-hidden="true" />
        {t('hazard.disclaimer')}
      </p>

      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="space-y-2">
          <HazardMap
            center={geo.kind === 'ready' ? geo.coords : KATHMANDU}
            hazards={visibleForMode}
            plan={plan}
            start={start}
            end={end}
            language={language}
            onPick={onPick}
            onView={onView}
          />
          <p className="flex flex-wrap items-center gap-1.5 hint">
            <MousePointer2 size={14} aria-hidden="true" />
            {picking === 'start' ? t('hazard.tapStart') : t('hazard.tapEnd')}
            {night && (
              <><span aria-hidden="true">·</span><Moon size={14} aria-hidden="true" />{t('hazard.nightMode')}</>
            )}
          </p>
        </div>

        <div className="space-y-4">
          <Card>
            <p className="label">{t('hazard.mode')}</p>
            <div className="flex flex-wrap gap-2" role="radiogroup">
              {MODES.map((m) => (
                <button
                  key={m.key}
                  type="button"
                  role="radio"
                  aria-checked={mode === m.key}
                  className={`btn ${mode === m.key ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => {
                    setMode(m.key)
                    setPlan(null)
                  }}
                >
                  <m.icon size={16} aria-hidden="true" />
                  {t(`hazard.mode.${m.key}` as never)}
                </button>
              ))}
            </div>

            <p className="label mt-4">{t('hazard.from')}</p>
            <div className="flex flex-wrap items-center gap-2" style={{ fontSize: 'var(--step-sm)' }}>
              <span>
                {startIsMe
                  ? geo.kind === 'ready'
                    ? <span className="inline-flex items-center gap-1.5"><LocateFixed size={15} />{t('hazard.myLocation')}</span>
                    : geo.kind === 'locating'
                      ? t('report.locating')
                      : t('hazard.noLocation')
                  : start
                    ? <span className="inline-flex items-center gap-1.5"><Pin size={15} />{t('hazard.pointOnMap')}</span>
                    : '—'}
              </span>
              <button
                type="button"
                className="btn btn-ghost"
                style={{ minHeight: 'auto', padding: '0.2rem 0.5rem' }}
                onClick={() => setPicking('start')}
              >
                {t('hazard.setStartOnMap')}
              </button>
              {!startIsMe && (
                <button
                  type="button"
                  className="btn btn-ghost"
                  style={{ minHeight: 'auto', padding: '0.2rem 0.5rem' }}
                  onClick={() => {
                    setStartIsMe(true)
                    locate()
                  }}
                >
                  {t('hazard.useMyLocation')}
                </button>
              )}
            </div>

            <p className="label mt-4">{t('hazard.to')}</p>
            <div className="relative">
              <input
                className="field pr-10"
                type="search"
                value={queryText}
                onChange={(e) => setQueryText(e.target.value)}
                placeholder={t('hazard.searchPlaceholder')}
                aria-label={t('hazard.to')}
                aria-describedby={searching ? 'destination-search-status' : undefined}
              />
              {searching && (
                <LoaderCircle
                  size={17}
                  className="absolute right-3 top-3.5 animate-spin text-ink-soft"
                  aria-hidden="true"
                />
              )}
            </div>
            {searching && (
              <p id="destination-search-status" className="mt-1 flex items-center gap-1.5 hint" role="status">
                {t('hazard.searchingPlaces')}
              </p>
            )}
            {results.length > 0 && (
              <ul className="mt-1 max-h-48 overflow-auto rounded-lg border" style={{ borderColor: 'var(--color-line)' }}>
                {results.map((place) => (
                  <li key={`${place.latitude},${place.longitude}`}>
                    <button
                      type="button"
                      className="w-full px-3 py-2 text-left hover:underline"
                      style={{ fontSize: 'var(--step-sm)' }}
                      onClick={() => {
                        searchRequest.current += 1
                        addressRequest.current += 1
                        setEnd({ latitude: place.latitude, longitude: place.longitude })
                        setEndLabel(place.name)
                        setEndAddress(place.display_name)
                        setEndResolving(false)
                        setQueryText('')
                        setResults([])
                        setPlan(null)
                      }}
                    >
                      <span className="font-semibold">{place.name}</span>
                      <br />
                      <span className="line-clamp-2 hint">{place.display_name}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <div
              className="mt-2 flex items-start gap-3 rounded-lg border border-line bg-canvas p-3"
              data-testid="destination-summary"
              aria-live="polite"
            >
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-danger text-xs font-bold text-white">
                B
              </span>
              <div className="min-w-0 flex-1" style={{ fontSize: 'var(--step-sm)' }}>
                {endResolving ? (
                  <span className="inline-flex items-center gap-2 text-ink-soft" role="status">
                    <LoaderCircle size={15} className="animate-spin" aria-hidden="true" />
                    {t('hazard.loadingAddress')}
                  </span>
                ) : end ? (
                  <>
                    <p className="flex items-center gap-1.5 font-semibold">
                      <MapPin size={15} aria-hidden="true" />
                      {endLabel ?? t('hazard.pointOnMap')}
                    </p>
                    {endAddress && (
                      <p className="mt-1 line-clamp-3 text-ink-soft">{endAddress}</p>
                    )}
                  </>
                ) : (
                  <span className="hint">{t('hazard.tapEnd')}</span>
                )}
              </div>
            </div>

            <Button className="mt-4 w-full" disabled={busy || !start || !end} onClick={findRoute}>
              {!busy && <Navigation size={16} aria-hidden="true" />}
              {busy ? t('hazard.finding') : t('hazard.findRoute')}
            </Button>
          </Card>

          {error && <ErrorNote message={error} />}

          {plan && recommended && (
            <Card>
              <h2 className="font-bold" style={{ fontSize: 'var(--step-md)' }}>
                {plan.recommended === 'safer' ? <CheckCircle2 size={18} className="mr-2 inline text-good" /> : <Navigation size={18} className="mr-2 inline" />}
                {plan.recommended === 'safer' ? t('hazard.saferFound') : t('hazard.usualRoute')}
              </h2>
              <p className="mt-1" style={{ fontSize: 'var(--step-sm)' }}>
                {formatDistance(recommended.distance_m)} · {formatDuration(recommended.duration_s)}
                {plan.profile_used !== plan.mode && ` · ${t(`hazard.mode.${plan.profile_used}` as never)}`}
              </p>

              <ul className="mt-2 list-disc space-y-1 pl-5" style={{ fontSize: 'var(--step-sm)' }}>
                {plan.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>

              {avoided.length > 0 && (
                <div className="mt-3">
                  <p className="font-semibold" style={{ color: 'var(--color-good)' }}>
                    {t('hazard.avoided')}
                  </p>
                  <ul style={{ fontSize: 'var(--step-sm)' }}>
                    {avoided.map((h) => (
                      <li key={h.id}>
                        {kindLabel(h.kind)} — {h.title}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {remaining.length > 0 && (
                <div className="mt-3">
                  <p className="font-semibold" style={{ color: 'var(--color-warn)' }}>
                    {t('hazard.stillOnRoute')}
                  </p>
                  <ul style={{ fontSize: 'var(--step-sm)' }}>
                    {remaining.map((h) => (
                      <li key={h.id}>
                        {kindLabel(h.kind)} — {h.title}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {plan.safer && plan.recommended === 'safer' && (
                <p className="mt-3 hint">
                  {t('hazard.greyIsUsual')} ({formatDistance(plan.fastest.distance_m)} ·{' '}
                  {formatDuration(plan.fastest.duration_s)})
                </p>
              )}
              <p className="mt-3 hint">{plan.disclaimer}</p>
            </Card>
          )}

          <Card>
            <p className="label">{t('hazard.legend')}</p>
            <ul className="grid grid-cols-1 gap-1" style={{ fontSize: 'var(--step-sm)' }}>
              {Object.keys(HAZARD_KINDS).map((kind) => {
                const count = visibleForMode.filter((h) => h.kind === kind).length
                return (
                  <li key={kind} className="flex items-center justify-between gap-2">
                    <span>{kindLabel(kind)}</span>
                    <span className="hint">{count}</span>
                  </li>
                )
              })}
            </ul>
            <p className="mt-2 hint">
              <span className="inline-block size-2 rounded-full" style={{ background: SEVERITY_COLOR.high }} /> {t('hazard.sevHigh')}{' '}
              <span className="inline-block size-2 rounded-full" style={{ background: SEVERITY_COLOR.medium }} /> {t('hazard.sevMedium')}{' '}
              <span className="inline-block size-2 rounded-full" style={{ background: SEVERITY_COLOR.low }} /> {t('hazard.sevLow')}
            </p>
            <p className="mt-1 hint">{t('hazard.reportHint')}</p>
          </Card>
        </div>
      </div>
    </div>
  )
}
