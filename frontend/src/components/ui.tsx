import { useEffect, useId, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { useI18n } from '../lib/i18n'
import { usePrefs } from '../lib/prefs'
import type { AlertSeverity, TicketPriority, TicketStatus } from '../lib/types'

export function Button({
  variant = 'primary',
  className = '',
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
}) {
  return (
    <button className={`btn btn-${variant} ${className}`} {...rest}>
      {children}
    </button>
  )
}

export function Card({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return <div className={`card p-4 ${className}`}>{children}</div>
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
      <span
        className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
        aria-hidden="true"
      />
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
      {message}
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
      {children}
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
        <span aria-hidden="true">{speaking ? '⏹' : '\u{1F50A}'}</span>
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
}: {
  label: string
  value: number | string
  tone?: 'ink' | 'warn' | 'danger' | 'good'
}) {
  const colors = {
    ink: 'var(--color-ink)',
    warn: 'var(--color-warn)',
    danger: 'var(--color-danger)',
    good: 'var(--color-good)',
  }

  return (
    <div className="card p-4">
      <p
        className="font-bold tabular-nums"
        style={{ fontSize: 'var(--step-2xl)', color: colors[tone], lineHeight: 1.1 }}
      >
        {value}
      </p>
      <p className="mt-1 hint">{label}</p>
    </div>
  )
}
