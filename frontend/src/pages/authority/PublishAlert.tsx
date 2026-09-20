import { useEffect, useState, type FormEvent } from 'react'
import { LocateFixed } from 'lucide-react'
import {
  Button,
  Card,
  ErrorNote,
  Field,
  PageTitle,
  SeverityBadge,
  SuccessNote,
} from '../../components/ui'
import { api } from '../../lib/api'
import { useAuth } from '../../lib/auth'
import { useGeolocation } from '../../lib/geo'
import { useI18n } from '../../lib/i18n'
import type { Alert, AlertSeverity, Ward } from '../../lib/types'

export function PublishAlert() {
  const { t, language, pick } = useI18n()
  const { profile } = useAuth()
  const { state: geo, locate } = useGeolocation()

  const [titleEn, setTitleEn] = useState('')
  const [titleNe, setTitleNe] = useState('')
  const [bodyEn, setBodyEn] = useState('')
  const [bodyNe, setBodyNe] = useState('')
  const [instructionsEn, setInstructionsEn] = useState('')
  const [severity, setSeverity] = useState<AlertSeverity>('info')
  const [targetType, setTargetType] = useState<'ward' | 'radius'>('ward')
  const [wardIds, setWardIds] = useState<string[]>([])
  const [radius, setRadius] = useState(1000)

  const [wards, setWards] = useState<Ward[]>([])
  const [active, setActive] = useState<Alert[]>([])
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!profile?.municipality_id) return
    api
      .municipality(profile.municipality_id)
      .then((detail) => {
        setWards(detail.wards)
        // Ward-scoped officers can only sensibly target their own ward.
        if (profile.ward_id) setWardIds([profile.ward_id])
      })
      .catch(() => setWards([]))
  }, [profile])

  const loadActive = () => {
    api.alerts().then(setActive).catch(() => setActive([]))
  }

  useEffect(loadActive, [])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setMessage(null)

    if (targetType === 'radius' && geo.kind !== 'ready') {
      setError('Set a centre point first.')
      return
    }

    setBusy(true)
    try {
      await api.publishAlert({
        title_en: titleEn,
        title_ne: titleNe || undefined,
        body_en: bodyEn,
        body_ne: bodyNe || undefined,
        instructions_en: instructionsEn || undefined,
        severity,
        target_type: targetType,
        ward_ids: targetType === 'ward' ? wardIds : undefined,
        center_lat: targetType === 'radius' && geo.kind === 'ready' ? geo.coords.latitude : undefined,
        center_lon: targetType === 'radius' && geo.kind === 'ready' ? geo.coords.longitude : undefined,
        radius_m: targetType === 'radius' ? radius : undefined,
      })

      setMessage(t('publish.published'))
      setTitleEn('')
      setTitleNe('')
      setBodyEn('')
      setBodyNe('')
      setInstructionsEn('')
      loadActive()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageTitle title={t('publish.title')} />

      {error && <ErrorNote message={error} />}
      {message && <SuccessNote>{message}</SuccessNote>}

      <form onSubmit={submit} className="space-y-4">
        <Card>
          <div className="space-y-4">
            <Field label={t('publish.titleEn')} required>
              <input
                className="field"
                value={titleEn}
                onChange={(e) => setTitleEn(e.target.value)}
                required
                minLength={3}
                maxLength={200}
              />
            </Field>

            <Field label={t('publish.titleNe')}>
              <input
                className="field"
                value={titleNe}
                onChange={(e) => setTitleNe(e.target.value)}
                maxLength={200}
                lang="ne"
              />
            </Field>

            <Field label={t('publish.bodyEn')} required>
              <textarea
                className="field"
                rows={3}
                value={bodyEn}
                onChange={(e) => setBodyEn(e.target.value)}
                required
                minLength={3}
              />
            </Field>

            <Field label={t('publish.bodyNe')}>
              <textarea
                className="field"
                rows={3}
                value={bodyNe}
                onChange={(e) => setBodyNe(e.target.value)}
                lang="ne"
              />
            </Field>

            <Field label={t('publish.instructions')}>
              <textarea
                className="field"
                rows={2}
                value={instructionsEn}
                onChange={(e) => setInstructionsEn(e.target.value)}
              />
            </Field>
          </div>
        </Card>

        <Card>
          <fieldset>
            <legend className="label">{t('publish.severity')}</legend>
            <div className="flex flex-wrap gap-2">
              {(['info', 'warning', 'critical'] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setSeverity(option)}
                  aria-pressed={severity === option}
                  className="chip"
                  style={{
                    minHeight: '40px',
                    padding: '0 1rem',
                    borderWidth: severity === option ? 2 : 1,
                    borderColor:
                      severity === option ? 'var(--color-ink)' : 'var(--color-line)',
                  }}
                >
                  <SeverityBadge severity={option} />
                </button>
              ))}
            </div>
          </fieldset>

          <fieldset className="mt-4">
            <legend className="label">{t('publish.target')}</legend>
            <div className="grid grid-cols-2 gap-2">
              {(['ward', 'radius'] as const).map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setTargetType(option)}
                  aria-pressed={targetType === option}
                  className="card p-3"
                  style={{
                    borderColor:
                      targetType === option
                        ? 'var(--color-brand)'
                        : 'var(--color-line)',
                    background:
                      targetType === option
                        ? 'var(--color-brand-soft)'
                        : 'var(--color-surface)',
                    fontSize: 'var(--step-sm)',
                    fontWeight: targetType === option ? 700 : 500,
                  }}
                >
                  {option === 'ward'
                    ? t('publish.targetWard')
                    : t('publish.targetRadius')}
                </button>
              ))}
            </div>
          </fieldset>

          {targetType === 'ward' ? (
            <div className="mt-4">
              <p className="label">{t('auth.ward')}</p>
              <div
                className="max-h-56 space-y-1 overflow-y-auto rounded-lg border p-2"
                style={{ borderColor: 'var(--color-line)' }}
              >
                {wards.map((ward) => (
                  <label
                    key={ward.id}
                    className="flex items-center gap-2 rounded px-2 py-1.5"
                    style={{ fontSize: 'var(--step-sm)' }}
                  >
                    <input
                      type="checkbox"
                      checked={wardIds.includes(ward.id)}
                      onChange={(e) =>
                        setWardIds((current) =>
                          e.target.checked
                            ? [...current, ward.id]
                            : current.filter((id) => id !== ward.id),
                        )
                      }
                      style={{ width: 20, height: 20 }}
                    />
                    {t('auth.ward')} {ward.number}
                    {ward.name_en ? ` — ${pick(ward.name_en, ward.name_ne)}` : ''}
                  </label>
                ))}
              </div>
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              {geo.kind === 'ready' ? (
                <p className="hint">
                  <LocateFixed size={14} className="mr-1 inline" />{geo.coords.latitude.toFixed(5)}, {geo.coords.longitude.toFixed(5)}
                </p>
              ) : (
                <Button type="button" variant="secondary" onClick={locate} className="w-full">
                  <LocateFixed size={16} />{t('report.useMyLocation')}
                </Button>
              )}

              <Field label={t('publish.radius')}>
                <input
                  type="number"
                  className="field"
                  value={radius}
                  min={100}
                  max={50000}
                  step={100}
                  onChange={(e) => setRadius(Number(e.target.value))}
                />
              </Field>
            </div>
          )}
        </Card>

        <Button type="submit" disabled={busy} className="w-full">
          {busy ? t('common.loading') : t('publish.submit')}
        </Button>
      </form>

      {active.length > 0 && (
        <section>
          <h2 className="mb-2 font-bold" style={{ fontSize: 'var(--step-md)' }}>
            {t('alerts.title')}
          </h2>
          <div className="space-y-2">
            {active.map((alert) => (
              <Card key={alert.id}>
                <div className="flex flex-wrap items-center gap-2">
                  <SeverityBadge severity={alert.severity} />
                  <span className="font-semibold" style={{ fontSize: 'var(--step-sm)' }}>
                    {language === 'ne' ? alert.title_ne || alert.title_en : alert.title_en}
                  </span>
                  <button
                    type="button"
                    className="btn btn-ghost ml-auto"
                    style={{ minHeight: 'auto', padding: '0.25rem 0.6rem' }}
                    onClick={() =>
                      api
                        .deactivateAlert(alert.id)
                        .then(loadActive)
                        .catch(() => setError(t('common.error')))
                    }
                  >
                    Deactivate
                  </button>
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
