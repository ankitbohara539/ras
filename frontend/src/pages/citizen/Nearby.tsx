import { useCallback, useEffect, useState } from 'react'
import { TicketCard } from '../../components/TicketCard'
import {
  Button,
  Card,
  EmptyState,
  ErrorNote,
  PageTitle,
  Spinner,
} from '../../components/ui'
import { api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { useGeolocation } from '../../lib/geo'
import { useI18n } from '../../lib/i18n'
import type { TicketSummary } from '../../lib/types'

/**
 * Two ways to find a report that is not yours.
 *
 * "Around me" is GPS-driven and exists for corroboration: instead of filing a
 * second ticket for the same pothole, you confirm the one already there.
 * "My ward" ignores where the phone currently is, because people leave their
 * ward all day -- work, college, a trip -- and still want to follow what their
 * neighbours reported at home.
 */
type Scope = 'nearby' | 'ward'

export function Nearby() {
  const { t } = useI18n()
  const { profile } = useAuth()
  const { state: geo, locate } = useGeolocation()

  const [scope, setScope] = useState<Scope>('nearby')
  const [tickets, setTickets] = useState<TicketSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (scope === 'nearby') locate()
  }, [scope, locate])

  const load = useCallback(async () => {
    if (scope === 'nearby' && geo.kind !== 'ready') return

    setLoading(true)
    setError(null)
    try {
      const result =
        scope === 'nearby' && geo.kind === 'ready'
          ? await api.nearbyTickets(geo.coords, 1500)
          : // No ward on the profile means the citizen never picked one, so
            // fall back to the whole municipality -- the API scopes it anyway.
            await api.tickets({
              ward_id: profile?.ward_id ?? undefined,
              limit: 30,
            })
      setTickets(result.items)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setLoading(false)
    }
  }, [scope, geo, profile, t])

  useEffect(() => {
    void load()
  }, [load])

  const showGeoError = scope === 'nearby' && geo.kind === 'error'

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageTitle
        title={scope === 'nearby' ? t('nearby.title') : t('nearby.wardTitle')}
        subtitle={scope === 'nearby' ? t('nearby.hint') : t('nearby.wardHint')}
      />

      <div
        role="tablist"
        aria-label={t('nearby.scopeLabel')}
        className="card flex gap-1 p-1"
      >
        {(['nearby', 'ward'] as Scope[]).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={scope === value}
            onClick={() => setScope(value)}
            className="flex-1 rounded-lg px-3 py-2 font-semibold transition"
            style={{
              fontSize: 'var(--step-sm)',
              background:
                scope === value ? 'var(--color-brand)' : 'transparent',
              color: scope === value ? '#fff' : 'var(--color-ink)',
            }}
          >
            {value === 'nearby' ? t('nearby.tabNearby') : t('nearby.tabWard')}
          </button>
        ))}
      </div>

      {showGeoError && (
        <Card>
          <ErrorNote message={geo.message} />
          <Button variant="secondary" onClick={locate} className="mt-3 w-full">
            {t('common.retry')}
          </Button>
        </Card>
      )}

      {((scope === 'nearby' && geo.kind === 'locating') || loading) && <Spinner />}

      {error && <ErrorNote message={error} />}

      {!loading && !showGeoError && tickets.length === 0 && (
        <EmptyState
          title={scope === 'nearby' ? t('nearby.none') : t('nearby.wardNone')}
        />
      )}

      <div className="space-y-3">
        {tickets.map((ticket) => (
          <TicketCard
            key={ticket.id}
            ticket={ticket}
            showDistance={scope === 'nearby'}
          />
        ))}
      </div>
    </div>
  )
}
