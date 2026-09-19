import { useCallback, useEffect, useState } from 'react'
import { Card, EmptyState, PageTitle, Spinner } from '../../components/ui'
import { api } from '../../lib/api'
import { formatDistance, useGeolocation } from '../../lib/geo'
import { useI18n } from '../../lib/i18n'
import type { CivicService, ServiceType } from '../../lib/types'

const FILTERS: (ServiceType | 'all')[] = [
  'all',
  'hospital',
  'ambulance',
  'police',
  'fire',
  'shelter',
  'municipality_office',
]

export function Services() {
  const { t, pick } = useI18n()
  const { state: geo, locate } = useGeolocation({ refine: false })

  const [services, setServices] = useState<CivicService[]>([])
  const [filter, setFilter] = useState<ServiceType | 'all'>('all')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    locate()
  }, [locate])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const coords = geo.kind === 'ready' ? geo.coords : undefined
      setServices(
        await api.services({
          service_type: filter === 'all' ? undefined : filter,
          search: search || undefined,
          latitude: coords?.latitude,
          longitude: coords?.longitude,
        }),
      )
    } catch {
      setServices([])
    } finally {
      setLoading(false)
    }
  }, [filter, search, geo])

  useEffect(() => {
    const timer = setTimeout(() => void load(), search ? 300 : 0)
    return () => clearTimeout(timer)
  }, [load, search])

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageTitle title={t('services.title')} />

      <input
        type="search"
        className="field"
        placeholder={t('services.search')}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        aria-label={t('services.search')}
      />

      <div className="flex flex-wrap gap-2" role="group" aria-label={t('services.title')}>
        {FILTERS.map((option) => (
          <button
            key={option}
            type="button"
            onClick={() => setFilter(option)}
            aria-pressed={filter === option}
            className="chip"
            style={{
              minHeight: '38px',
              padding: '0 0.9rem',
              borderColor: filter === option ? 'var(--color-brand)' : 'var(--color-line)',
              background:
                filter === option ? 'var(--color-brand)' : 'var(--color-surface)',
              color: filter === option ? '#fff' : 'var(--color-ink-soft)',
            }}
          >
            {t(`services.${option}` as never)}
          </button>
        ))}
      </div>

      {loading ? (
        <Spinner />
      ) : services.length === 0 ? (
        <EmptyState title={t('services.none')} />
      ) : (
        <div className="space-y-3">
          {services.map((service) => (
            <Card key={service.id}>
              <div className="flex flex-wrap items-start gap-2">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold" style={{ fontSize: 'var(--step-md)' }}>
                    {pick(service.name_en, service.name_ne)}
                  </p>
                  {service.address && <p className="hint">{service.address}</p>}

                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    {service.is_24x7 && (
                      <span
                        className="chip"
                        style={{
                          background: 'var(--color-good-soft)',
                          color: 'var(--color-good)',
                          borderColor: 'var(--color-good)',
                        }}
                      >
                        {t('services.open24')}
                      </span>
                    )}
                    {service.distance_m !== null && (
                      <span className="hint">
                        {formatDistance(service.distance_m)} {t('common.away')}
                      </span>
                    )}
                  </div>
                </div>

                {service.phone && (
                  <a
                    href={`tel:${service.phone}`}
                    className="btn btn-primary"
                    aria-label={`${t('services.call')} ${pick(service.name_en, service.name_ne)} ${service.phone}`}
                  >
                    📞 {service.phone}
                  </a>
                )}
              </div>

              {pick(service.notes_en, service.notes_ne) && (
                <p className="mt-2 hint">{pick(service.notes_en, service.notes_ne)}</p>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
