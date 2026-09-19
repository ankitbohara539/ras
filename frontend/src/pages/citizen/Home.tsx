import { Link } from 'react-router-dom'
import { TicketCard } from '../../components/TicketCard'
import {
  Card,
  EmptyState,
  SeverityBadge,
  SpeakButton,
  Spinner,
} from '../../components/ui'
import { api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { useQuery } from '../../lib/cache'
import { useI18n } from '../../lib/i18n'
import type { Alert, TicketSummary } from '../../lib/types'

export function CitizenHome() {
  const { t, pick } = useI18n()
  const { profile } = useAuth()

  // Home is the page people return to most, so it paints from cache and
  // refreshes behind the scenes. Each half fails on its own: no alerts is
  // not a reason to hide your reports.
  const mine = useQuery(profile ? `tickets:mine:5:${profile.id}` : null, () =>
    api.tickets({ mine: true, limit: 5 }),
  )
  const active = useQuery(profile ? `alerts:${profile.id}` : null, () => api.alerts(), {
    refetchIntervalMs: 60_000,
  })
  const tickets: TicketSummary[] = mine.data?.items ?? []
  const alerts: Alert[] = active.data ?? []

  if (mine.loading && active.loading) return <Spinner />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-bold" style={{ fontSize: 'var(--step-xl)' }}>
          {profile?.full_name?.split(' ')[0] ?? ''}
        </h1>
        <p className="hint">{t('app.tagline')}</p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Link
          to="/report"
          className="card flex items-center gap-4 p-5 transition hover:border-[var(--color-brand)]"
          style={{ background: 'var(--color-brand-soft)', borderColor: 'var(--color-brand)' }}
        >
          <span aria-hidden="true" style={{ fontSize: '2rem' }}>
            📝
          </span>
          <div>
            <p className="font-bold" style={{ fontSize: 'var(--step-md)' }}>
              {t('report.title')}
            </p>
            <p className="hint">{t('report.descriptionHint')}</p>
          </div>
        </Link>

        <Link
          to="/sos"
          className="card flex items-center gap-4 p-5 transition"
          style={{ background: 'var(--color-danger-soft)', borderColor: 'var(--color-danger)' }}
        >
          <span aria-hidden="true" style={{ fontSize: '2rem' }}>
            🆘
          </span>
          <div>
            <p
              className="font-bold"
              style={{ fontSize: 'var(--step-md)', color: 'var(--color-danger)' }}
            >
              {t('sos.title')}
            </p>
            <p className="hint">{t('sos.hint')}</p>
          </div>
        </Link>
      </div>

      {alerts.length > 0 && (
        <section>
          <h2 className="mb-3 font-bold" style={{ fontSize: 'var(--step-lg)' }}>
            {t('alerts.title')}
          </h2>
          <div className="space-y-3">
            {alerts.slice(0, 3).map((alert) => {
              const title = pick(alert.title_en, alert.title_ne)
              const body = pick(alert.body_en, alert.body_ne)

              return (
                <Card key={alert.id}>
                  <div className="flex flex-wrap items-center gap-2">
                    <SeverityBadge severity={alert.severity} />
                    <SpeakButton text={`${title}. ${body}`} />
                  </div>
                  <p className="mt-2 font-semibold" style={{ fontSize: 'var(--step-md)' }}>
                    {title}
                  </p>
                  <p className="mt-1" style={{ fontSize: 'var(--step-sm)' }}>
                    {body}
                  </p>
                  {pick(alert.instructions_en, alert.instructions_ne) && (
                    <div
                      className="mt-3 rounded-lg p-3"
                      style={{ background: 'var(--color-canvas)' }}
                    >
                      <p className="font-semibold" style={{ fontSize: 'var(--step-sm)' }}>
                        {t('alerts.instructions')}
                      </p>
                      <p style={{ fontSize: 'var(--step-sm)' }}>
                        {pick(alert.instructions_en, alert.instructions_ne)}
                      </p>
                    </div>
                  )}
                </Card>
              )
            })}
          </div>
        </section>
      )}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-bold" style={{ fontSize: 'var(--step-lg)' }}>
            {t('nav.myReports')}
          </h2>
          {tickets.length > 0 && (
            <Link
              to="/my-reports"
              className="font-semibold underline"
              style={{ fontSize: 'var(--step-sm)', color: 'var(--color-brand)' }}
            >
              {t('common.viewAll')}
            </Link>
          )}
        </div>

        {tickets.length === 0 ? (
          <EmptyState
            title={t('ticket.none')}
            hint={t('ticket.noneHint')}
            action={
              <Link to="/report" className="btn btn-primary">
                {t('report.title')}
              </Link>
            }
          />
        ) : (
          <div className="space-y-3">
            {tickets.map((ticket) => (
              <TicketCard key={ticket.id} ticket={ticket} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
