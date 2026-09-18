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
import { useGeolocation } from '../../lib/geo'
import { useI18n } from '../../lib/i18n'
import type { TicketSummary } from '../../lib/types'

/**
 * Nearby open reports, so a citizen can corroborate a neighbour's report.
 * This is the second half of the duplicate story: instead of filing a second
 * ticket for the same pothole, you confirm the one that exists.
 */
export function Nearby() {
  const { t } = useI18n()
  const { state: geo, locate } = useGeolocation()

  const [tickets, setTickets] = useState<TicketSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    locate()
  }, [locate])

  const load = useCallback(async () => {
    if (geo.kind !== 'ready') return

    setLoading(true)
    setError(null)
    try {
      const result = await api.nearbyTickets(geo.coords, 1500)
      setTickets(result.items)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setLoading(false)
    }
  }, [geo, t])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageTitle title={t('nearby.title')} subtitle={t('nearby.hint')} />

      {geo.kind === 'error' && (
        <Card>
          <ErrorNote message={geo.message} />
          <Button variant="secondary" onClick={locate} className="mt-3 w-full">
            {t('common.retry')}
          </Button>
        </Card>
      )}

      {(geo.kind === 'locating' || loading) && <Spinner />}

      {error && <ErrorNote message={error} />}

      {geo.kind === 'ready' && !loading && tickets.length === 0 && (
        <EmptyState title={t('nearby.none')} />
      )}

      <div className="space-y-3">
        {tickets.map((ticket) => (
          <TicketCard key={ticket.id} ticket={ticket} showDistance />
        ))}
      </div>
    </div>
  )
}
