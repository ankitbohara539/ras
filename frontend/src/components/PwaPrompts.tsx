import { useEffect, useState } from 'react'
import { useRegisterSW } from 'virtual:pwa-register/react'
import { useI18n } from '../lib/i18n'

/**
 * The three things an installed web app has to tell people about:
 * that it can be installed, that a new version is ready, and that the
 * network is gone.
 */

type InstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

const DISMISSED_KEY = 'sahayatri.install-dismissed'

function Banner({
  tone,
  children,
}: {
  tone: 'brand' | 'warn'
  children: React.ReactNode
}) {
  const colors =
    tone === 'warn'
      ? { bg: 'var(--color-warn-soft)', fg: 'var(--color-warn)', border: 'var(--color-warn)' }
      : { bg: 'var(--color-brand-soft)', fg: 'var(--color-brand-ink)', border: 'var(--color-brand)' }

  return (
    <div
      role="status"
      className="fixed inset-x-0 z-50 mx-auto max-w-2xl px-3"
      style={{
        bottom: 'calc(env(safe-area-inset-bottom, 0px) + 68px)',
      }}
    >
      <div
        className="card flex flex-wrap items-center gap-3 p-3 shadow-lg"
        style={{
          background: colors.bg,
          borderColor: colors.border,
          color: colors.fg,
        }}
      >
        {children}
      </div>
    </div>
  )
}

export function PwaPrompts() {
  const { t } = useI18n()

  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisterError(error) {
      // A failed service worker must never break the app; it only costs
      // offline support.
      console.warn('Service worker registration failed', error)
    },
  })

  const [installEvent, setInstallEvent] = useState<InstallPromptEvent | null>(null)
  const [offline, setOffline] = useState(!navigator.onLine)

  useEffect(() => {
    const onBeforeInstall = (event: Event) => {
      // Chrome fires this instead of showing its own prompt once we
      // preventDefault, which lets the invitation appear in context.
      event.preventDefault()
      try {
        if (localStorage.getItem(DISMISSED_KEY)) return
      } catch {
        // Storage unavailable: just show it.
      }
      setInstallEvent(event as InstallPromptEvent)
    }

    const onInstalled = () => setInstallEvent(null)
    const onOnline = () => setOffline(false)
    const onOffline = () => setOffline(true)

    window.addEventListener('beforeinstallprompt', onBeforeInstall)
    window.addEventListener('appinstalled', onInstalled)
    window.addEventListener('online', onOnline)
    window.addEventListener('offline', onOffline)

    return () => {
      window.removeEventListener('beforeinstallprompt', onBeforeInstall)
      window.removeEventListener('appinstalled', onInstalled)
      window.removeEventListener('online', onOnline)
      window.removeEventListener('offline', onOffline)
    }
  }, [])

  const install = async () => {
    if (!installEvent) return
    await installEvent.prompt()
    await installEvent.userChoice
    setInstallEvent(null)
  }

  const dismissInstall = () => {
    try {
      localStorage.setItem(DISMISSED_KEY, '1')
    } catch {
      // Then it reappears next visit, which is acceptable.
    }
    setInstallEvent(null)
  }

  // Offline is the most urgent of the three: it changes what the person can
  // trust on screen, so it wins the slot.
  if (offline) {
    return (
      <Banner tone="warn">
        <span aria-hidden="true">📡</span>
        <span className="flex-1" style={{ fontSize: 'var(--step-sm)' }}>
          {t('pwa.offline')}
        </span>
      </Banner>
    )
  }

  if (needRefresh) {
    return (
      <Banner tone="brand">
        <span aria-hidden="true">🔄</span>
        <span className="flex-1" style={{ fontSize: 'var(--step-sm)' }}>
          {t('pwa.updateReady')}
        </span>
        <button
          type="button"
          className="btn btn-primary"
          style={{ minHeight: '38px' }}
          onClick={() => updateServiceWorker(true)}
        >
          {t('pwa.reload')}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          style={{ minHeight: '38px' }}
          onClick={() => setNeedRefresh(false)}
        >
          {t('common.cancel')}
        </button>
      </Banner>
    )
  }

  if (installEvent) {
    return (
      <Banner tone="brand">
        <span aria-hidden="true">📲</span>
        <div className="flex-1">
          <p className="font-semibold" style={{ fontSize: 'var(--step-sm)' }}>
            {t('pwa.installTitle')}
          </p>
          <p className="hint">{t('pwa.installBody')}</p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          style={{ minHeight: '38px' }}
          onClick={install}
        >
          {t('pwa.install')}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          style={{ minHeight: '38px' }}
          onClick={dismissInstall}
          aria-label={t('common.cancel')}
        >
          ✕
        </button>
      </Banner>
    )
  }

  return null
}
