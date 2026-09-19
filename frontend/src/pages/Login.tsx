import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button, ErrorNote, Field } from '../components/ui'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { usePrefs } from '../lib/prefs'

const DEMO_ACCOUNTS = [
  { email: 'sita@example.com', label: 'Citizen (Nepali UI)' },
  { email: 'kmc.ward5@sahayatri.np', label: 'Ward 5 authority' },
  { email: 'admin@sahayatri.np', label: 'Administrator' },
]

function AuthShell({ children }: { children: React.ReactNode }) {
  const { t, language, setLanguage } = useI18n()
  const { largeText, highContrast, setLargeText, setHighContrast } = usePrefs()

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
      {/* The accessibility controls are on the sign-in screen too: someone who
          needs large text needs it before they have an account. */}
      <div className="mb-6 flex flex-wrap items-center justify-center gap-2">
        {(['en', 'ne'] as const).map((code) => (
          <button
            key={code}
            type="button"
            onClick={() => setLanguage(code)}
            aria-pressed={language === code}
            className="chip"
            style={{
              borderColor: 'var(--color-line)',
              background:
                language === code ? 'var(--color-brand)' : 'var(--color-surface)',
              color: language === code ? '#fff' : 'var(--color-ink-soft)',
              minHeight: '36px',
            }}
          >
            {code === 'en' ? 'English' : 'नेपाली'}
          </button>
        ))}
        <button
          type="button"
          onClick={() => setLargeText(!largeText)}
          aria-pressed={largeText}
          className="chip"
          style={{
            borderColor: 'var(--color-line)',
            background: largeText ? 'var(--color-brand)' : 'var(--color-surface)',
            color: largeText ? '#fff' : 'var(--color-ink-soft)',
            minHeight: '36px',
          }}
        >
          A+ {t('a11y.largeText')}
        </button>
        <button
          type="button"
          onClick={() => setHighContrast(!highContrast)}
          aria-pressed={highContrast}
          className="chip"
          style={{
            borderColor: 'var(--color-line)',
            background: highContrast ? 'var(--color-brand)' : 'var(--color-surface)',
            color: highContrast ? '#fff' : 'var(--color-ink-soft)',
            minHeight: '36px',
          }}
        >
          ◐ {t('a11y.highContrast')}
        </button>
      </div>

      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <span
            className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl font-bold text-white"
            style={{ background: 'var(--color-brand)', fontSize: 'var(--step-xl)' }}
            aria-hidden="true"
          >
            स
          </span>
          <h1 className="font-bold" style={{ fontSize: 'var(--step-xl)' }}>
            {t('app.name')}
          </h1>
          <p className="hint">{t('app.tagline')}</p>
        </div>
        {children}
      </div>
    </div>
  )
}

export function Login() {
  const { t } = useI18n()
  const { signIn } = useAuth()
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setBusy(true)

    try {
      const profile = await signIn(email, password)
      navigate(profile.role === 'citizen' ? '/' : '/authority', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell>
      <form onSubmit={submit} className="card space-y-4 p-6">
        <h2 className="font-bold" style={{ fontSize: 'var(--step-lg)' }}>
          {t('auth.login')}
        </h2>

        {error && <ErrorNote message={error} />}

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

        <Field label={t('auth.password')} required>
          <input
            type="password"
            className="field"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </Field>

        <Button type="submit" disabled={busy} className="w-full">
          {busy ? t('auth.signingIn') : t('auth.login')}
        </Button>

        <p className="text-center hint">
          {t('auth.noAccount')}{' '}
          <Link to="/register" className="font-semibold underline" style={{ color: 'var(--color-brand)' }}>
            {t('auth.register')}
          </Link>
        </p>
      </form>

      <div className="card mt-4 p-4">
        <p className="mb-2 font-semibold" style={{ fontSize: 'var(--step-sm)' }}>
          Demo accounts
        </p>
        <div className="space-y-1">
          {DEMO_ACCOUNTS.map((account) => (
            <button
              key={account.email}
              type="button"
              onClick={() => {
                setEmail(account.email)
                setPassword('Sahayatri@2025')
              }}
              className="flex w-full items-center justify-between rounded-lg px-2 py-2 text-left hover:bg-[var(--color-canvas)]"
              style={{ fontSize: 'var(--step-xs)' }}
            >
              <span className="font-mono">{account.email}</span>
              <span style={{ color: 'var(--color-ink-faint)' }}>{account.label}</span>
            </button>
          ))}
        </div>
        <p className="mt-2 hint">Password: Sahayatri@2025</p>
      </div>

      <p className="mt-4 text-center">
        <Link to="/transparency" className="font-semibold underline" style={{ color: 'var(--color-brand)' }}>
          {t('transparency.title')}
        </Link>
      </p>
    </AuthShell>
  )
}

export { AuthShell }
