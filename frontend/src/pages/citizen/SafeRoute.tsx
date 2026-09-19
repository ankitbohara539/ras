import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { HazardMap } from '../../components/HazardMap'
import { Button, Card, ErrorNote, PageTitle } from '../../components/ui'
import { api } from '../../lib/api'
import { formatDistance, useGeolocation } from '../../lib/geo'
import { formatDuration, hazardKind, HAZARD_KINDS, SEVERITY_COLOR } from '../../lib/hazards'
import { useI18n } from '../../lib/i18n'
import type { Coords, Hazard, PlaceResult, RoutePlan, TravelMode } from '../../lib/types'

const KATHMANDU = { latitude: 27.7172, longitude: 85.324 }

const MODES: { key: TravelMode; icon: string }[] = [
  { key: 'walk', icon: '🚶' },
  { key: 'wheelchair', icon: '♿' },
  { key: 'drive', icon: '🚗' },
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
  const [picking, setPicking] = useState<'start' | 'end'>('end')

  const [hazards, setHazards] = useState<Hazard[]>([])
  const [night, setNight] = useState(false)
  const [plan, setPlan] = useState<RoutePlan | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [queryText, setQueryText] = useState('')
  const [results, setResults] = useState<PlaceResult[]>([])
  const viewTimer = useRef<number | null>(null)

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
    if (q.length < 3) {
      setResults([])
      return
    }
    const timer = window.setTimeout(() => {
      api
        .searchPlaces(q, language)
        .then(setResults)
        .catch(() => setResults([]))
    }, 600)
    return () => window.clearTimeout(timer)
  }, [queryText, language])

  const onPick = useCallback(
    (coords: Coords) => {
      setPlan(null)
      if (picking === 'start') {
        setStart(coords)
        setStartIsMe(false)
        setPicking('end')
      } else {
        setEnd(coords)
        setEndLabel(null)
      }
    },
    [picking],
  )

  const findRoute = async () => {
    if (!start || !end) return
    setBusy(true)
    setError(null)
    try {
      const result = await api.planRoute({ start, end, mode })
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
    return `${meta.icon} ${language === 'ne' ? meta.label[1] : meta.label[0]}`
  }

  return (
    <div className="space-y-4">
      <PageTitle title={t('hazard.title')} subtitle={t('hazard.subtitle')} />

      <p
        className="rounded-lg border p-3"
        role="note"
        style={{ background: 'var(--color-warn-soft)', borderColor: 'var(--color-warn)', fontSize: 'var(--step-sm)' }}
      >
        ⚠ {t('hazard.disclaimer')}
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
          <p className="hint">
            {picking === 'start' ? `👆 ${t('hazard.tapStart')}` : `👆 ${t('hazard.tapEnd')}`}
            {night && ` · 🌙 ${t('hazard.nightMode')}`}
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
                  {m.icon} {t(`hazard.mode.${m.key}` as never)}
                </button>
              ))}
            </div>

            <p className="label mt-4">🅰 {t('hazard.from')}</p>
            <div className="flex flex-wrap items-center gap-2" style={{ fontSize: 'var(--step-sm)' }}>
              <span>
                {startIsMe
                  ? geo.kind === 'ready'
                    ? `📍 ${t('hazard.myLocation')}`
                    : geo.kind === 'locating'
                      ? t('report.locating')
                      : t('hazard.noLocation')
                  : start
                    ? `📌 ${t('hazard.pointOnMap')}`
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

            <p className="label mt-4">🅱 {t('hazard.to')}</p>
            <input
              className="field"
              type="search"
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
              placeholder={t('hazard.searchPlaceholder')}
              aria-label={t('hazard.to')}
            />
            {results.length > 0 && (
              <ul className="mt-1 max-h-48 overflow-auto rounded-lg border" style={{ borderColor: 'var(--color-line)' }}>
                {results.map((place) => (
                  <li key={`${place.latitude},${place.longitude}`}>
                    <button
                      type="button"
                      className="w-full px-3 py-2 text-left hover:underline"
                      style={{ fontSize: 'var(--step-sm)' }}
                      onClick={() => {
                        setEnd({ latitude: place.latitude, longitude: place.longitude })
                        setEndLabel(place.name)
                        setQueryText('')
                        setResults([])
                        setPlan(null)
                      }}
                    >
                      <span className="font-semibold">{place.name}</span>
                      <br />
                      <span className="hint">{place.display_name}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-1" style={{ fontSize: 'var(--step-sm)' }}>
              {end ? `📌 ${endLabel ?? t('hazard.pointOnMap')}` : <span className="hint">{t('hazard.tapEnd')}</span>}
            </p>

            <Button className="mt-4 w-full" disabled={busy || !start || !end} onClick={findRoute}>
              {busy ? t('hazard.finding') : `🧭 ${t('hazard.findRoute')}`}
            </Button>
          </Card>

          {error && <ErrorNote message={error} />}

          {plan && recommended && (
            <Card>
              <h2 className="font-bold" style={{ fontSize: 'var(--step-md)' }}>
                {plan.recommended === 'safer' ? `✅ ${t('hazard.saferFound')}` : `🧭 ${t('hazard.usualRoute')}`}
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
              <span style={{ color: SEVERITY_COLOR.high }}>●</span> {t('hazard.sevHigh')}{' '}
              <span style={{ color: SEVERITY_COLOR.medium }}>●</span> {t('hazard.sevMedium')}{' '}
              <span style={{ color: SEVERITY_COLOR.low }}>●</span> {t('hazard.sevLow')}
            </p>
            <p className="mt-1 hint">{t('hazard.reportHint')}</p>
          </Card>
        </div>
      </div>
    </div>
  )
}
