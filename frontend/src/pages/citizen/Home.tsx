import { Link } from 'react-router-dom'
import {
  ArrowRight,
  Building2,
  ChartNoAxesCombined,
  FilePlus2,
  MapPin,
  Route,
  Siren,
  Users,
} from 'lucide-react'
import { TicketCard } from '../../components/TicketCard'
import {
  Card,
  EmptyState,
  ErrorNote,
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
  const { t, pick, language } = useI18n()
  const text = (en: string, ne: string) => (language === 'ne' ? ne : en)
  const { profile } = useAuth()

  // Home is the page people return to most, so it paints from cache and
  // refreshes behind the scenes. Each half fails on its own: no alerts is
  // not a reason to hide your reports.
  const mine = useQuery(profile ? `tickets:mine:5:${profile.id}` : null, () =>
    api.tickets({ mine: true, limit: 5 }),
  )
  const active = useQuery(
    profile ? `alerts:${profile.id}` : null,
    () => api.alerts(),
    {
      refetchIntervalMs: 60_000,
    },
  )
  const tickets: TicketSummary[] = mine.data?.items ?? []
  const alerts: Alert[] = active.data ?? []

  if (mine.loading && active.loading) return <Spinner />

  return (
    <div className="dashboard-page space-y-6">
      <section className="dashboard-heading flex flex-wrap items-end justify-between gap-4 p-6 sm:p-7">
        <div>
          <p className="section-label mb-2">
            {text('Your civic workspace', 'तपाईंको नागरिक कार्यस्थल')}
          </p>
          <h1 className="text-3xl font-semibold tracking-tight">
            {text('Welcome back,', 'स्वागत छ,')}{' '}
            {profile?.full_name?.split(' ')[0] ?? ''}
          </h1>
          <p className="mt-2 text-sm text-ink-soft">{t('app.tagline')}</p>
        </div>
        <Link to="/my-reports" className="btn btn-secondary">
          {t('nav.myReports')}
          <ArrowRight size={16} />
        </Link>
      </section>

      <section className="grid gap-4 md:grid-cols-[1.5fr_1fr]">
        <div className="dashboard-primary-action rounded-2xl bg-ink p-6 text-white shadow-[0_18px_45px_rgba(29,41,61,0.16)] sm:p-8">
          <FilePlus2 size={28} className="mb-5" />
          <h2 className="text-2xl font-semibold tracking-tight">
            {text(
              'Make your neighbourhood better.',
              'आफ्नो छिमेक राम्रो बनाऔँ।',
            )}
          </h2>
          <p className="mt-2 max-w-lg text-sm text-mint">
            {t('report.descriptionHint')}
          </p>
          <Link to="/report" className="btn mt-6 bg-white text-ink">
            {t('report.title')}
            <ArrowRight size={16} />
          </Link>
        </div>
        <div className="interactive-card card flex flex-col justify-between p-6">
          <div>
            <span className="icon-tile mb-4 !border-danger/20 !bg-danger-soft text-danger">
              <Siren />
            </span>
            <h2 className="text-lg font-semibold">{t('sos.title')}</h2>
            <p className="mt-2 text-sm text-ink-soft">{t('sos.hint')}</p>
          </div>
          <Link
            to="/sos"
            className="btn btn-secondary mt-5 justify-between !border-danger/20 !text-danger"
          >
            {t('nav.sos')}
            <ArrowRight size={16} />
          </Link>
        </div>
      </section>

      <section className="dashboard-panel p-5 sm:p-6" aria-labelledby="community-tools">
        <h2 id="community-tools" className="mb-3 text-lg font-semibold">
          {text('Explore & participate', 'हेर्नुहोस् र सहभागी बन्नुहोस्')}
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {[
            {
              to: '/nearby',
              label: t('nav.nearby'),
              hint: text('See reports around you', 'आसपासका उजुरी हेर्नुहोस्'),
              icon: MapPin,
            },
            {
              to: '/safe-route',
              label: t('nav.safeRoute'),
              hint: text(
                'Plan around reported hazards',
                'जोखिम हेरेर यात्रा योजना',
              ),
              icon: Route,
            },
            {
              to: '/services',
              label: t('nav.services'),
              hint: text(
                'Find local services and contacts',
                'स्थानीय सेवा र सम्पर्क',
              ),
              icon: Building2,
            },
            {
              to: '/civic',
              label: t('nav.civic'),
              hint: text('Help care for shared spaces', 'साझा ठाउँको हेरचाह'),
              icon: Users,
            },
            {
              to: '/public-dashboard',
              label: t('transparency.title'),
              hint: text(
                'See community-wide progress',
                'समुदायको प्रगति हेर्नुहोस्',
              ),
              icon: ChartNoAxesCombined,
            },
          ].map(({ icon: Icon, ...item }) => (
            <Link
              key={item.to}
              to={item.to}
              className="interactive-card group card flex items-center gap-3 p-4"
            >
              <span className="icon-tile transition-colors duration-200 group-hover:border-brand/25 group-hover:bg-brand-soft group-hover:text-brand">
                <Icon />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold">
                  {item.label}
                </span>
                <span className="mt-1 block hint">{item.hint}</span>
              </span>
              <ArrowRight size={16} className="shrink-0 text-ink-faint transition-transform duration-200 group-hover:translate-x-1 group-hover:text-brand" />
            </Link>
          ))}
        </div>
      </section>
      {active.error instanceof Error && (
        <ErrorNote message={active.error.message} />
      )}
      {mine.error instanceof Error && (
        <ErrorNote message={mine.error.message} />
      )}

      {alerts.length > 0 && (
        <section className="dashboard-panel p-5 sm:p-6">
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
                  <p
                    className="mt-2 font-semibold"
                    style={{ fontSize: 'var(--step-md)' }}
                  >
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
                      <p
                        className="font-semibold"
                        style={{ fontSize: 'var(--step-sm)' }}
                      >
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

      <section className="dashboard-panel p-5 sm:p-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-bold" style={{ fontSize: 'var(--step-lg)' }}>
            {t('nav.myReports')}
          </h2>
          {tickets.length > 0 && (
            <Link
              to="/my-reports"
              className="font-semibold underline"
              style={{
                fontSize: 'var(--step-sm)',
                color: 'var(--color-brand)',
              }}
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
