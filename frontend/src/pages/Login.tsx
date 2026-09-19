import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ResendVerification } from '../components/ResendVerification'
import { Button, ErrorNote, Field, PasswordInput, SuccessNote } from '../components/ui'
import { ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useI18n } from '../lib/i18n'
import { ArrowRight, ShieldCheck } from 'lucide-react'
import { Brand, DisplayControls } from '../components/Brand'

const DEMO_ACCOUNTS = [
  { email: 'sita@example.com', label: 'Citizen (Nepali UI)' },
  { email: 'kmc.ward5@sahayatri.np', label: 'Ward 5 authority' },
  { email: 'admin@sahayatri.np', label: 'Administrator' },
]

function AuthShell({ children }: { children: React.ReactNode }) {
  const { t, language } = useI18n()
  const text = (en: string, ne: string) => (language === 'ne' ? ne : en)
  return (
    <div className="min-h-screen">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-surface px-5 py-4 sm:px-8">
        <Brand to="/public-dashboard" />
        <DisplayControls />
      </header>
      <main className="mx-auto grid max-w-6xl items-start gap-12 px-4 py-8 sm:px-8 lg:grid-cols-2 lg:py-16">
        <section className="hidden space-y-6 lg:sticky lg:top-12 lg:block">
          <p className="section-label">
            {text(
              'Your voice. Your neighbourhood.',
              'तपाईंको आवाज। तपाईंको छिमेक।',
            )}
          </p>
          <h1 className="max-w-md text-5xl font-semibold leading-tight tracking-tight">
            {text(
              'Better places, built together.',
              'मिलेर बनाऔँ, राम्रो समुदाय।',
            )}
          </h1>
          <p className="max-w-md text-base text-ink-soft">{t('app.tagline')}</p>
          <div className="space-y-4 border-y border-line py-6">
            {[
              text(
                'Report issues in your neighbourhood',
                'आफ्नो छिमेकका समस्या दर्ता गर्नुहोस्',
              ),
              text(
                'Follow every update, from report to resolution',
                'दर्तादेखि समाधानसम्मको प्रगति हेर्नुहोस्',
              ),
              text(
                'Find services and explore safer routes',
                'सेवा खोज्नुहोस् र सुरक्षित मार्ग हेर्नुहोस्',
              ),
            ].map((label) => (
              <p key={label} className="flex items-center gap-3 text-sm">
                <ShieldCheck size={18} className="text-ink-soft" />
                {label}
              </p>
            ))}
          </div>
          <Link to="/public-dashboard" className="btn btn-secondary">
            {t('transparency.title')}
            <ArrowRight size={16} />
          </Link>
        </section>
        <div className="mx-auto w-full max-w-md">
          <div className="mb-6 lg:hidden">
            <p className="section-label">{t('app.name')}</p>
            <p className="mt-2 text-xl font-semibold">{t('app.tagline')}</p>
          </div>
          {children}
          <p className="mt-6 text-center">
            <Link to="/public-dashboard" className="btn btn-ghost">
              {t('transparency.title')}
              <ArrowRight size={16} />
            </Link>
          </p>
        </div>
      </main>
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
  // Sign-in was refused because the email is not verified yet.
  const [unverified, setUnverified] = useState(false)
  // Arrived from the link in the verification email.
  const [justVerified, setJustVerified] = useState(false)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''))
    if (params.get('verified') === '1' || hash.get('type') === 'signup') {
      setJustVerified(!hash.get('error'))
      if (hash.get('error_description')) setError(hash.get('error_description'))
      // Supabase appends the new session's tokens to the link. This app
      // signs in through its own API, so drop them from the address bar
      // (and from history) rather than leave tokens lying around.
      window.history.replaceState(null, '', '/login')
    }
  }, [])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setUnverified(false)
    setBusy(true)

    try {
      const profile = await signIn(email, password)
      navigate(profile.role === 'citizen' ? '/' : '/authority', {
        replace: true,
      })
    } catch (err) {
      if (
        err instanceof ApiError &&
        err.status === 403 &&
        /verify your email/i.test(err.message)
      ) {
        setUnverified(true)
      }
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

        {justVerified && <SuccessNote>{t('auth.verified')}</SuccessNote>}
        {error && <ErrorNote message={error} />}
        {unverified && <ResendVerification email={email} />}

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
          <PasswordInput
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
          <Link
            to="/register"
            className="font-semibold underline"
            style={{ color: 'var(--color-brand)' }}
          >
            {t('auth.register')}
          </Link>
        </p>
      </form>

      <div className="card mt-4 p-4">
        <p
          className="mb-2 font-semibold"
          style={{ fontSize: 'var(--step-sm)' }}
        >
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
              <span style={{ color: 'var(--color-ink-faint)' }}>
                {account.label}
              </span>
            </button>
          ))}
        </div>
        <p className="mt-2 hint">Password: Sahayatri@2025</p>
      </div>

    </AuthShell>
  )
}

export { AuthShell }
