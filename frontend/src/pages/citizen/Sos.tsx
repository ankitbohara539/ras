import { useEffect, useState } from 'react'
import { AlertTriangle, Ambulance, CircleHelp, Flame, LocateFixed, Shield, Siren } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Button, Card, ErrorNote, Field, PageTitle } from '../../components/ui'
import { api } from '../../lib/api'
import { formatDate, useGeolocation } from '../../lib/geo'
import { useI18n } from '../../lib/i18n'
import type { EmergencyType, SosCreateResponse, SosRequest } from '../../lib/types'

const TYPES: { key: EmergencyType; icon: LucideIcon }[] = [
  { key: 'medical', icon: Ambulance },
  { key: 'fire', icon: Flame },
  { key: 'police', icon: Shield },
  { key: 'disaster', icon: AlertTriangle },
  { key: 'other', icon: CircleHelp },
]

export function Sos() {
  const { t, language } = useI18n()
  const { state: geo, locate } = useGeolocation()

  const [type, setType] = useState<EmergencyType>('medical')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState<SosCreateResponse | null>(null)
  const [history, setHistory] = useState<SosRequest[]>([])

  useEffect(() => {
    locate()
    api.sosList().then(setHistory).catch(() => setHistory([]))
  }, [locate])

  const send = async () => {
    if (geo.kind !== 'ready') {
      setError(t('report.locationNeeded'))
      return
    }

    setBusy(true)
    setError(null)
    try {
      const response = await api.raiseSos({
        emergency_type: type,
        latitude: geo.coords.latitude,
        longitude: geo.coords.longitude,
        note: note || undefined,
      })
      setSent(response)
      api.sosList().then(setHistory).catch(() => undefined)
      window.scrollTo({ top: 0 })
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setBusy(false)
    }
  }

  if (sent) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <div
          className="card p-5 text-center"
          style={{
            background: 'var(--color-danger-soft)',
            borderColor: 'var(--color-danger)',
          }}
        >
          <Siren aria-hidden="true" className="mx-auto size-10 text-danger" />
          <h1
            className="font-bold"
            style={{ fontSize: 'var(--step-lg)', color: 'var(--color-danger)' }}
          >
            {t('sos.sent')}
          </h1>
          <p className="mt-2" style={{ fontSize: 'var(--step-sm)' }}>
            {sent.message}
          </p>
        </div>

        <Card>
          <h2
            className="font-bold"
            style={{ fontSize: 'var(--step-md)', color: 'var(--color-danger)' }}
          >
            {t('sos.callNow')}
          </h2>
          <div className="mt-3 space-y-2">
            {sent.emergency_contacts.map((contact) => (
              <a
                key={`${contact.name_en}-${contact.phone}`}
                href={`tel:${contact.phone}`}
                className="flex items-center justify-between rounded-lg border p-3"
                style={{ borderColor: 'var(--color-line)' }}
              >
                <span className="font-medium" style={{ fontSize: 'var(--step-sm)' }}>
                  {language === 'ne' ? contact.name_ne || contact.name_en : contact.name_en}
                </span>
                <span
                  className="font-mono font-bold"
                  style={{ fontSize: 'var(--step-lg)', color: 'var(--color-danger)' }}
                >
                  {contact.phone}
                </span>
              </a>
            ))}
          </div>
        </Card>

        <Button variant="secondary" onClick={() => setSent(null)} className="w-full">
          {t('common.back')}
        </Button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageTitle title={t('sos.title')} subtitle={t('sos.hint')} />

      {error && <ErrorNote message={error} />}

      <Card>
        <fieldset>
          <legend className="label">{t('sos.type')}</legend>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {TYPES.map((option) => (
              <button
                key={option.key}
                type="button"
                onClick={() => setType(option.key)}
                aria-pressed={type === option.key}
                className="card flex flex-col items-center gap-1 p-4"
                style={{
                  borderColor:
                    type === option.key ? 'var(--color-danger)' : 'var(--color-line)',
                  background:
                    type === option.key
                      ? 'var(--color-danger-soft)'
                      : 'var(--color-surface)',
                  fontWeight: type === option.key ? 700 : 500,
                  minHeight: 'var(--tap)',
                }}
              >
                <option.icon size={24} aria-hidden="true" />
                <span style={{ fontSize: 'var(--step-sm)' }}>
                  {t(`sos.${option.key}` as never)}
                </span>
              </button>
            ))}
          </div>
        </fieldset>

        <div className="mt-4">
          <Field label={t('sos.note')}>
            <textarea
              className="field"
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={1000}
            />
          </Field>
        </div>

        {geo.kind === 'ready' ? (
          <p className="mt-3 hint">
            <LocateFixed size={14} className="mr-1 inline" />{geo.coords.latitude.toFixed(5)}, {geo.coords.longitude.toFixed(5)}
          </p>
        ) : (
          <Button
            type="button"
            variant="secondary"
            onClick={locate}
            className="mt-3 w-full"
          >
            <LocateFixed size={16} />{t('report.useMyLocation')}
          </Button>
        )}
      </Card>

      <Button
        variant="danger"
        onClick={send}
        disabled={busy || geo.kind !== 'ready'}
        className="w-full"
        style={{ minHeight: '64px', fontSize: 'var(--step-lg)' }}
      >
        {!busy && <Siren size={20} />}
        {busy ? t('sos.sending') : t('sos.send')}
      </Button>

      {history.length > 0 && (
        <section>
          <h2 className="mb-2 font-bold" style={{ fontSize: 'var(--step-md)' }}>
            {t('sos.myRequests')}
          </h2>
          <div className="space-y-2">
            {history.map((request) => (
              <Card key={request.id}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold" style={{ fontSize: 'var(--step-sm)' }}>
                    {t(`sos.${request.emergency_type}` as never)}
                  </span>
                  <span className="chip" style={{ borderColor: 'var(--color-line)' }}>
                    {request.status}
                  </span>
                  <span className="ml-auto hint">
                    {formatDate(request.created_at, language)}
                  </span>
                </div>
                {request.note && <p className="mt-1 hint">{request.note}</p>}
              </Card>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
