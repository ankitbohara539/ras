import { useState } from 'react'
import { Mail } from 'lucide-react'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { Button, ErrorNote, SuccessNote } from './ui'

/**
 * "Didn't get the email?" -- sends the verification link again.
 *
 * Shown after registering and when sign-in is refused for an unverified
 * email. Links go to spam, expire, or get deleted; without this the account
 * is simply stuck.
 */
export function ResendVerification({ email }: { email: string }) {
  const { t } = useI18n()
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const resend = async () => {
    setBusy(true)
    setError(null)
    try {
      const result = await api.resendVerification(email)
      setSent(result.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-2">
      {sent && <SuccessNote>{sent}</SuccessNote>}
      {error && <ErrorNote message={error} />}
      <Button
        type="button"
        variant="secondary"
        className="w-full"
        disabled={busy || !email}
        onClick={resend}
      >
        <Mail size={16} /> {busy ? t('auth.sending') : t('auth.resendVerification')}
      </Button>
      <p className="hint">{t('auth.checkSpam')}</p>
    </div>
  )
}
