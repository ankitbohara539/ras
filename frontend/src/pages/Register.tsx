import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button, ErrorNote, Field, SuccessNote } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import type { Municipality, Ward } from '../lib/types'
import { AuthShell } from './Login'

export function Register() {
  const { t, language } = useI18n()
  const { signIn } = useAuth()
  const navigate = useNavigate()

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<'citizen' | 'authority'>('citizen')

  const [municipalities, setMunicipalities] = useState<Municipality[]>([])
  const [wards, setWards] = useState<Ward[]>([])
  const [municipalityId, setMunicipalityId] = useState('')
  const [wardId, setWardId] = useState('')

  const [error, setError] = useState<string | null>(null)
  const [pendingMessage, setPendingMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.municipalities().then(setMunicipalities).catch(() => setMunicipalities([]))
  }, [])

  useEffect(() => {
    if (!municipalityId) {
      setWards([])
      setWardId('')
      return
    }
    api
      .municipality(municipalityId)
      .then((detail) => setWards(detail.wards))
      .catch(() => setWards([]))
  }, [municipalityId])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setBusy(true)

    try {
      const result = await api.register({
        email,
        password,
        full_name: fullName,
        phone: phone || undefined,
        requested_role: role,
        municipality_id: municipalityId || undefined,
        ward_id: wardId || undefined,
        preferred_language: language,
      })

      if (result.requires_approval) {
        // An authority account cannot sign in yet, so say so rather than
        // bouncing them to a login that will refuse them.
        setPendingMessage(result.message)
        return
      }

      const profile = await signIn(email, password)
      navigate(profile.role === 'citizen' ? '/' : '/authority', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setBusy(false)
    }
  }

  if (pendingMessage) {
    return (
      <AuthShell>
        <div className="card space-y-4 p-6">
          <SuccessNote>{pendingMessage}</SuccessNote>
          <p className="hint">
            An administrator has to approve officer accounts before they can sign
            in. You will be notified once that happens.
          </p>
          <Link to="/login" className="btn btn-secondary w-full">
            {t('auth.login')}
          </Link>
        </div>
      </AuthShell>
    )
  }

  return (
    <AuthShell>
      <form onSubmit={submit} className="card space-y-4 p-6">
        <h2 className="font-bold" style={{ fontSize: 'var(--step-lg)' }}>
          {t('auth.register')}
        </h2>

        {error && <ErrorNote message={error} />}

        <fieldset>
          <legend className="label">{t('auth.accountType')}</legend>
          <div className="grid grid-cols-2 gap-2">
            {(['citizen', 'authority'] as const).map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setRole(option)}
                aria-pressed={role === option}
                className="card p-3 text-left"
                style={{
                  borderColor:
                    role === option ? 'var(--color-brand)' : 'var(--color-line)',
                  background:
                    role === option ? 'var(--color-brand-soft)' : 'var(--color-surface)',
                  fontSize: 'var(--step-sm)',
                  fontWeight: role === option ? 700 : 500,
                }}
              >
                {option === 'citizen' ? t('auth.citizen') : t('auth.authority')}
              </button>
            ))}
          </div>
        </fieldset>

        <Field label={t('auth.fullName')} required>
          <input
            className="field"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            autoComplete="name"
            required
            minLength={2}
          />
        </Field>

        <Field label={t('auth.email')} required>
          <input
            type="email"
            className="field"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </Field>

        <Field label={t('auth.phone')}>
          <input
            type="tel"
            className="field"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            autoComplete="tel"
          />
        </Field>

        <Field
          label={t('auth.password')}
          hint="At least 8 characters."
          required
        >
          <input
            type="password"
            className="field"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            required
            minLength={8}
          />
        </Field>

        <Field label={t('auth.municipality')} required={role === 'authority'}>
          <select
            className="field"
            value={municipalityId}
            onChange={(e) => setMunicipalityId(e.target.value)}
            required={role === 'authority'}
          >
            <option value="">{t('auth.selectMunicipality')}</option>
            {municipalities.map((municipality) => (
              <option key={municipality.id} value={municipality.id}>
                {language === 'ne' ? municipality.name_ne : municipality.name_en}
              </option>
            ))}
          </select>
        </Field>

        {wards.length > 0 && (
          <Field
            label={t('auth.ward')}
            hint={
              role === 'authority'
                ? 'Leave blank to cover every ward in the municipality.'
                : undefined
            }
          >
            <select
              className="field"
              value={wardId}
              onChange={(e) => setWardId(e.target.value)}
            >
              <option value="">{t('auth.selectWard')}</option>
              {wards.map((ward) => (
                <option key={ward.id} value={ward.id}>
                  {t('auth.ward')} {ward.number}
                  {ward.name_en
                    ? ` — ${language === 'ne' ? ward.name_ne : ward.name_en}`
                    : ''}
                </option>
              ))}
            </select>
          </Field>
        )}

        <Button type="submit" disabled={busy} className="w-full">
          {busy ? t('auth.creating') : t('auth.register')}
        </Button>

        <p className="text-center hint">
          {t('auth.haveAccount')}{' '}
          <Link
            to="/login"
            className="font-semibold underline"
            style={{ color: 'var(--color-brand)' }}
          >
            {t('auth.login')}
          </Link>
        </p>
      </form>
    </AuthShell>
  )
}
