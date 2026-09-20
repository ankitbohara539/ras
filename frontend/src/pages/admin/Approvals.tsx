import { useCallback, useEffect, useState } from 'react'
import { Check } from 'lucide-react'
import {
  Button,
  Card,
  EmptyState,
  ErrorNote,
  Field,
  PageTitle,
  Spinner,
} from '../../components/ui'
import { api } from '../../lib/api'
import { useI18n } from '../../lib/i18n'
import type { Profile } from '../../lib/types'

/**
 * The admin approval queue. An authority account is created `pending` and
 * cannot sign in at all until it is approved here, so this page is the only
 * thing standing between a signup form and someone with ward-wide powers.
 */
export function Approvals() {
  const { t } = useI18n()

  const [pending, setPending] = useState<Profile[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [rejecting, setRejecting] = useState<string | null>(null)
  const [reason, setReason] = useState('')

  const load = useCallback(async () => {
    try {
      const result = await api.pendingAuthorities()
      setPending(result.items)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => {
    void load()
  }, [load])

  const approve = async (id: string) => {
    setBusy(id)
    setError(null)
    try {
      await api.approveAuthority(id, {})
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setBusy(null)
    }
  }

  const reject = async (id: string) => {
    if (!reason.trim()) return
    setBusy(id)
    setError(null)
    try {
      await api.rejectAuthority(id, reason)
      setRejecting(null)
      setReason('')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    } finally {
      setBusy(null)
    }
  }

  if (loading) return <Spinner />

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <PageTitle title={t('approvals.title')} subtitle={t('approvals.hint')} />

      {error && <ErrorNote message={error} />}

      {pending.length === 0 ? (
        <EmptyState title={t('approvals.none')} />
      ) : (
        <div className="space-y-3">
          {pending.map((account) => (
            <Card key={account.id}>
              <p className="font-semibold" style={{ fontSize: 'var(--step-md)' }}>
                {account.full_name ?? account.email}
              </p>
              <p className="hint">{account.email}</p>
              {account.phone && <p className="hint">{account.phone}</p>}

              <p className="mt-2 hint">
                Requested scope: {account.ward_id ? 'single ward' : 'whole municipality'}
              </p>

              {rejecting === account.id ? (
                <div className="mt-3 space-y-2">
                  <Field label={t('approvals.reason')} required>
                    <input
                      className="field"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      minLength={3}
                      autoFocus
                    />
                  </Field>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="danger"
                      disabled={busy === account.id || reason.trim().length < 3}
                      onClick={() => reject(account.id)}
                    >
                      {t('approvals.reject')}
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setRejecting(null)
                        setReason('')
                      }}
                    >
                      {t('common.cancel')}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    disabled={busy === account.id}
                    onClick={() => approve(account.id)}
                  >
                    <Check size={16} /> {t('approvals.approve')}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => setRejecting(account.id)}
                  >
                    {t('approvals.reject')}
                  </Button>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
