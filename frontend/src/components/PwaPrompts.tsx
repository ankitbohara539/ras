import { useEffect, useState, useSyncExternalStore } from 'react'
import { RefreshCw, WifiOff } from 'lucide-react'
import { toast } from 'sonner'
import { useRegisterSW } from 'virtual:pwa-register/react'
import { useI18n } from '../lib/i18n'
import { cn } from '../lib/utils'

type InstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

let installPrompt: InstallPromptEvent | null = null
let installed = typeof window !== 'undefined' && window.matchMedia('(display-mode: standalone)').matches
const installListeners = new Set<() => void>()

function notifyInstallState() {
  installListeners.forEach(listener => listener())
}

function subscribeInstall(listener: () => void) {
  installListeners.add(listener)
  return () => installListeners.delete(listener)
}

export function useInstallApp() {
  const { t } = useI18n()
  useSyncExternalStore(subscribeInstall, () => Boolean(installPrompt) || installed)
  const install = async () => {
    if (installed) {
      toast.info(t('pwa.alreadyInstalled'))
      return
    }
    if (!installPrompt) {
      toast.info(t('pwa.browserInstall'))
      return
    }
    await installPrompt.prompt()
    const choice = await installPrompt.userChoice
    if (choice.outcome === 'accepted') {
      installed = true
      installPrompt = null
      notifyInstallState()
      toast.success(t('pwa.installSuccess'))
    }
  }
  return { canInstall: Boolean(installPrompt), installed, install }
}

export function InstallAppButton({ compact = false, className = '' }: { compact?: boolean; className?: string }) {
  const { t } = useI18n()
  const { installed: isInstalled, install } = useInstallApp()
  return <button type="button" className={cn('btn btn-secondary', compact && 'min-h-9 px-3', className)} onClick={() => void install()}>
    <img src="/icon-192.png" alt="" aria-hidden="true" className="size-7 rounded-md" />
    <span className={compact ? 'sr-only' : ''}>{isInstalled ? t('pwa.installed') : t('pwa.install')}</span>
  </button>
}

function Banner({ tone, children }: { tone: 'brand' | 'warn'; children: React.ReactNode }) {
  const colors = tone === 'warn'
    ? { bg: 'var(--color-warn-soft)', fg: 'var(--color-warn)', border: 'var(--color-warn)' }
    : { bg: 'var(--color-brand-soft)', fg: 'var(--color-brand-ink)', border: 'var(--color-brand)' }
  return <div role="status" className="fixed inset-x-0 z-50 mx-auto max-w-2xl px-3" style={{ bottom: 'calc(env(safe-area-inset-bottom, 0px) + 76px)' }}>
    <div className="card flex flex-wrap items-center gap-3 p-3 shadow-lg" style={{ background: colors.bg, borderColor: colors.border, color: colors.fg }}>{children}</div>
  </div>
}

export function PwaPrompts() {
  const { t } = useI18n()
  const { needRefresh: [needRefresh, setNeedRefresh], updateServiceWorker } = useRegisterSW({
    onRegisterError(error) { console.warn('Service worker registration failed', error) },
  })
  const [offline, setOffline] = useState(!navigator.onLine)

  useEffect(() => {
    const onBeforeInstall = (event: Event) => {
      event.preventDefault()
      installPrompt = event as InstallPromptEvent
      notifyInstallState()
    }
    const onInstalled = () => {
      installed = true
      installPrompt = null
      notifyInstallState()
    }
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

  if (offline) return <Banner tone="warn"><WifiOff size={18} aria-hidden="true" /><span className="flex-1 text-sm">{t('pwa.offline')}</span></Banner>
  if (needRefresh) return <Banner tone="brand"><RefreshCw size={18} aria-hidden="true" /><span className="flex-1 text-sm">{t('pwa.updateReady')}</span><button type="button" className="btn btn-primary min-h-9" onClick={() => updateServiceWorker(true)}>{t('pwa.reload')}</button><button type="button" className="btn btn-ghost min-h-9" onClick={() => setNeedRefresh(false)}>{t('common.cancel')}</button></Banner>
  return null
}
