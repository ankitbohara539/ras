import { useEffect, useId, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode } from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import * as TooltipPrimitive from '@radix-ui/react-tooltip'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { AlertCircle, CheckCircle2, ChevronLeft, ChevronRight, Eye, EyeOff, LoaderCircle, Volume2, VolumeX, X } from 'lucide-react'
import { useI18n } from '../lib/i18n'
import { usePrefs } from '../lib/prefs'
import { cn } from '../lib/utils'
import type { AlertSeverity, TicketPriority, TicketStatus } from '../lib/types'

const buttonVariants = cva('btn', {
  variants: {
    variant: {
      primary: 'btn-primary',
      secondary: 'btn-secondary',
      danger: 'btn-danger',
      ghost: 'btn-ghost',
    },
    size: {
      default: '',
      sm: 'min-h-9 px-3',
      icon: 'h-10 min-h-10 w-10 p-0',
    },
  },
  defaultVariants: { variant: 'primary', size: 'default' },
})

export function Button({ variant, size, className, children, asChild = false, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Component = asChild ? Slot : 'button'
  return (
    <Component className={cn(buttonVariants({ variant, size }), className)} {...rest}>
      {children}
    </Component>
  )
}

export function Card({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return <div className={cn('card p-4', className)}>{children}</div>
}

export function PageTitle({
  title,
  subtitle,
  action,
}: {
  title: string
  subtitle?: string
  action?: ReactNode
}) {
  return (
    <header className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1
          className="font-bold tracking-tight"
          style={{ fontSize: 'var(--step-xl)', color: 'var(--color-ink)' }}
        >
          {title}
        </h1>
        {subtitle && (
          <p className="mt-1 max-w-2xl hint">{subtitle}</p>
        )}
      </div>
      {action}
    </header>
  )
}

export function Spinner({ label }: { label?: string }) {
  const { t } = useI18n()
  return (
    <div
      className="flex items-center justify-center gap-3 py-10 hint"
      role="status"
      aria-live="polite"
    >
      <LoaderCircle className="h-5 w-5 animate-spin" aria-hidden="true" />
      {label ?? t('common.loading')}
    </div>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="card p-3"
      style={{
        background: 'var(--color-danger-soft)',
        borderColor: 'var(--color-danger)',
        color: 'var(--color-danger)',
        fontSize: 'var(--step-sm)',
      }}
    >
      <AlertCircle className="mr-2 inline h-4 w-4" aria-hidden="true" />{message}
    </div>
  )
}

export function SuccessNote({ children }: { children: ReactNode }) {
  return (
    <div
      role="status"
      className="card p-3"
      style={{
        background: 'var(--color-good-soft)',
        borderColor: 'var(--color-good)',
        color: 'var(--color-good)',
        fontSize: 'var(--step-sm)',
      }}
    >
      <CheckCircle2 className="mr-2 inline h-4 w-4" aria-hidden="true" />{children}
    </div>
  )
}

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string
  hint?: string
  action?: ReactNode
}) {
  return (
    <div className="card p-8 text-center">
      <p className="font-semibold" style={{ fontSize: 'var(--step-md)' }}>
        {title}
      </p>
      {hint && <p className="mt-1 hint">{hint}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  )
}

const STATUS_STYLE: Record<TicketStatus, { bg: string; fg: string }> = {
  reported: { bg: 'var(--color-info-soft)', fg: 'var(--color-info)' },
  verified: { bg: 'var(--color-brand-soft)', fg: 'var(--color-brand-ink)' },
  in_progress: { bg: 'var(--color-warn-soft)', fg: 'var(--color-warn)' },
  resolved: { bg: 'var(--color-good-soft)', fg: 'var(--color-good)' },
  rejected: { bg: 'var(--color-danger-soft)', fg: 'var(--color-danger)' },
  merged: { bg: 'var(--color-canvas)', fg: 'var(--color-ink-soft)' },
}

export function StatusBadge({ status }: { status: TicketStatus }) {
  const { t } = useI18n()
  const style = STATUS_STYLE[status]

  return (
    <span
      className="chip"
      style={{ background: style.bg, color: style.fg, borderColor: style.fg }}
    >
      {t(`ticket.${status}` as never)}
    </span>
  )
}

const PRIORITY_STYLE: Record<TicketPriority, string> = {
  low: 'var(--color-ink-faint)',
  medium: 'var(--color-info)',
  high: 'var(--color-warn)',
  critical: 'var(--color-danger)',
}

export function PriorityBadge({ priority }: { priority: TicketPriority }) {
  const { t } = useI18n()
  return (
    <span
      className="chip"
      style={{
        borderColor: PRIORITY_STYLE[priority],
        color: PRIORITY_STYLE[priority],
      }}
    >
      {t(`ticket.${priority}` as never)}
    </span>
  )
}

export function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  const { t } = useI18n()
  const map: Record<AlertSeverity, { bg: string; fg: string }> = {
    info: { bg: 'var(--color-info-soft)', fg: 'var(--color-info)' },
    warning: { bg: 'var(--color-warn-soft)', fg: 'var(--color-warn)' },
    critical: { bg: 'var(--color-danger-soft)', fg: 'var(--color-danger)' },
  }
  const style = map[severity]

  return (
    <span
      className="chip"
      style={{ background: style.bg, color: style.fg, borderColor: style.fg }}
    >
      {t(`alerts.${severity}` as never)}
    </span>
  )
}

/**
 * Reads content aloud. Rendered only where the browser supports speech, so
 * nobody taps a button that does nothing.
 */
export function SpeakButton({ text }: { text: string }) {
  const { t, language } = useI18n()
  const { speak, stopSpeaking, speakingId, speechIssue, speechSupported } = usePrefs()
  // Each button has its own identity, so tapping one does not flip every
  // other speaker icon on the page to "stop".
  const id = useId()
  const speaking = speakingId === id
  const issue = speechIssue?.id === id ? speechIssue.message : null

  // Leaving the page should not leave it talking.
  useEffect(() => () => stopSpeaking(id), [id, stopSpeaking])

  if (!speechSupported) return null

  return (
    <span className="inline-flex flex-col items-end">
      <button
        type="button"
        onClick={() => (speaking ? stopSpeaking(id) : speak(text, id, language))}
        className="btn btn-ghost"
        style={{ minHeight: 'auto', padding: '0.25rem 0.6rem' }}
        aria-label={speaking ? t('a11y.stop') : t('a11y.listen')}
        aria-pressed={speaking}
      >
        {speaking ? <VolumeX size={16} aria-hidden="true" /> : <Volume2 size={16} aria-hidden="true" />}
        <span style={{ fontSize: 'var(--step-xs)' }}>
          {speaking ? t('a11y.stop') : t('a11y.listen')}
        </span>
      </button>
      {issue && (
        <span role="status" className="hint" style={{ fontSize: 'var(--step-xs)' }}>
          {issue}
        </span>
      )}
    </span>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden="true" className={cn('animate-pulse rounded-lg bg-mint/25', className)} />
}

export function DashboardSkeleton() {
  return <div role="status" aria-label="Loading dashboard" className="space-y-5">
    <span className="sr-only">Loading dashboard</span>
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-28" />)}</div>
    <div className="grid gap-5 lg:grid-cols-[1.6fr_1fr]"><Skeleton className="h-80" /><Skeleton className="h-80" /></div>
  </div>
}

export function Pagination({
  page,
  totalPages,
  onPageChange,
}: {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
}) {
  const { language } = useI18n()
  if (totalPages <= 1) return null
  const label = language === 'ne' ? `पृष्ठ ${page + 1} / ${totalPages}` : `Page ${page + 1} of ${totalPages}`
  return (
    <nav className="mt-5 flex items-center justify-center gap-3" aria-label={language === 'ne' ? 'पृष्ठहरू' : 'Pagination'}>
      <Button type="button" variant="secondary" size="icon" disabled={page === 0} onClick={() => onPageChange(page - 1)} aria-label={language === 'ne' ? 'अघिल्लो पृष्ठ' : 'Previous page'}>
        <ChevronLeft size={18} />
      </Button>
      <span className="min-w-28 text-center text-sm font-medium tabular-nums">{label}</span>
      <Button type="button" variant="secondary" size="icon" disabled={page >= totalPages - 1} onClick={() => onPageChange(page + 1)} aria-label={language === 'ne' ? 'अर्को पृष्ठ' : 'Next page'}>
        <ChevronRight size={18} />
      </Button>
    </nav>
  )
}

export function PasswordInput({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  const [visible, setVisible] = useState(false)
  const { language } = useI18n()
  const label = visible
    ? language === 'ne' ? 'पासवर्ड लुकाउनुहोस्' : 'Hide password'
    : language === 'ne' ? 'पासवर्ड देखाउनुहोस्' : 'Show password'
  return <span className="relative block">
    <input {...props} type={visible ? 'text' : 'password'} className={cn('field pr-12', className)} />
    <button type="button" className="absolute right-1 top-1 flex h-10 w-10 items-center justify-center rounded-md text-ink-soft transition hover:bg-brand-soft hover:text-ink" onClick={() => setVisible(value => !value)} aria-label={label} aria-pressed={visible}>
      {visible ? <EyeOff size={18} /> : <Eye size={18} />}
    </button>
  </span>
}

export function Tooltip({ content, children }: { content: ReactNode; children: ReactNode }) {
  return <TooltipPrimitive.Root>
    <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content sideOffset={7} className="z-[80] rounded-md bg-navy px-2.5 py-1.5 text-xs text-white shadow-lg">
        {content}<TooltipPrimitive.Arrow className="fill-navy" />
      </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  </TooltipPrimitive.Root>
}

export const TooltipProvider = TooltipPrimitive.Provider

export function ConfirmDialog({ trigger, title, description, confirmLabel, onConfirm, destructive = false }: { trigger: ReactNode; title: string; description: string; confirmLabel: string; onConfirm: () => void | Promise<void>; destructive?: boolean }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const confirm = async () => {
    setBusy(true)
    try { await onConfirm(); setOpen(false) } finally { setBusy(false) }
  }
  return <DialogPrimitive.Root open={open} onOpenChange={setOpen}>
    <DialogPrimitive.Trigger asChild>{trigger}</DialogPrimitive.Trigger>
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-[70] bg-navy/45 backdrop-blur-[2px]" />
      <DialogPrimitive.Content className="fixed left-1/2 top-1/2 z-[71] w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl border border-line bg-surface p-6 shadow-2xl focus:outline-none">
        <div className="flex items-start justify-between gap-4"><div><DialogPrimitive.Title className="text-lg font-semibold">{title}</DialogPrimitive.Title><DialogPrimitive.Description className="mt-2 text-sm text-ink-soft">{description}</DialogPrimitive.Description></div><DialogPrimitive.Close className="rounded-md p-1.5 text-ink-soft hover:bg-canvas" aria-label={t('common.cancel')}><X size={18} /></DialogPrimitive.Close></div>
        <div className="mt-6 flex justify-end gap-2"><DialogPrimitive.Close className="btn btn-secondary">{t('common.cancel')}</DialogPrimitive.Close><Button type="button" variant={destructive ? 'danger' : 'primary'} disabled={busy} onClick={() => void confirm()}>{busy && <LoaderCircle size={16} className="animate-spin" />}{confirmLabel}</Button></div>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  </DialogPrimitive.Root>
}

export function Field({
  label,
  hint,
  children,
  required,
}: {
  label: string
  hint?: string
  children: ReactNode
  required?: boolean
}) {
  return (
    <label className="block">
      <span className="label">
        {label}
        {required && (
          <span aria-hidden="true" style={{ color: 'var(--color-danger)' }}>
            {' '}
            *
          </span>
        )}
      </span>
      {children}
      {hint && <span className="mt-1 block hint">{hint}</span>}
    </label>
  )
}

export function Stat({
  label,
  value,
  tone = 'ink',
  icon,
  className,
}: {
  label: string
  value: number | string
  tone?: 'ink' | 'warn' | 'danger' | 'good'
  icon?: ReactNode
  className?: string
}) {
  const colors = {
    ink: 'var(--color-ink)',
    warn: 'var(--color-warn)',
    danger: 'var(--color-danger)',
    good: 'var(--color-good)',
  }

  return (
    <div className={cn('dashboard-stat card p-5', className)}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-ink-soft">{label}</p>
        {icon && (
          <span
            className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-brand-soft"
            style={{ color: colors[tone] }}
            aria-hidden="true"
          >
            {icon}
          </span>
        )}
      </div>
      <p
        className="mt-3 font-semibold tabular-nums tracking-tight"
        style={{ fontSize: 'var(--step-2xl)', color: colors[tone], lineHeight: 1.1 }}
      >
        {value}
      </p>
    </div>
  )
}
