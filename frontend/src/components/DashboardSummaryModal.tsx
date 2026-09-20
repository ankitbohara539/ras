import { Fragment, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, streamDashboardSummary } from '../lib/api'
import { formatDate } from '../lib/geo'
import { useI18n } from '../lib/i18n'
import type { DashboardIssue, DashboardSummary } from '../lib/types'
import { Button, ErrorNote, Modal, PriorityBadge } from './ui'

// Mirrors the backend's own per-person cooldown (dashboard_summary_regenerate_
// cooldown_s in config.py). Only cosmetic -- it just avoids a guaranteed 429
// round trip; the server enforces the real limit regardless of this.
const REGENERATE_COOLDOWN_MS = 60_000

// The model's pieces arrive in bursts (a whole word, then three letters, then
// half a sentence), so they are shown through a small smoother rather than
// dumped as they land: a few characters every tick, faster when a backlog
// builds up, so the text flows at an even pace like a chat reply does.
const TYPE_TICK_MS = 24
const TYPE_MIN_STEP = 3
const TYPE_CATCH_UP = 45

// Once the sentence is written, the rest of the answer -- stat tiles, the
// table header, each row, the queue chips -- is laid down one piece per tick.
const BUILD_FIRST_MS = 220
const BUILD_TICK_MS = 120

// Never stop a reveal between a letter and its vowel sign (Devanagari) or
// inside an emoji.
function joinsPrevious(ch: string): boolean {
  const code = ch.charCodeAt(0)
  const lowSurrogate = code >= 0xdc00 && code <= 0xdfff
  const joiner = code === 0x200c || code === 0x200d || code === 0xfe0f
  return lowSurrogate || joiner || /\p{M}/u.test(ch)
}

function nextShown(text: string, shown: number, instant: boolean): number {
  if (instant) return text.length
  let next = Math.min(text.length, shown + Math.max(TYPE_MIN_STEP, Math.ceil((text.length - shown) / TYPE_CATCH_UP)))
  while (next < text.length && joinsPrevious(text[next])) next++
  return next
}

/**
 * Bold (**...**) inline. An opener with no closer yet -- the model is
 * mid-way through a bold phrase -- bolds what has arrived so far rather than
 * flashing raw asterisks.
 */
function inline(text: string): ReactNode[] {
  return text.split('**').map((part, i) =>
    !part ? null : i % 2 === 1 ? <strong key={i}>{part}</strong> : <Fragment key={i}>{part}</Fragment>,
  )
}

const BULLET = /^\s*(?:[-*•]|\d+[.)])(?:\s+|$)/
const HEADING = /^\s*#{1,6}\s+/

/**
 * The small slice of Markdown the model is asked to write: paragraphs,
 * bullet lists and bold. Built from React elements, never innerHTML, so
 * nothing the model (or a report title it quotes) writes can inject markup.
 * `tail` (the typing dot) is placed at the end of the last block.
 */
function MarkdownLite({ text, tail }: { text: string; tail?: ReactNode }) {
  type Block = { kind: 'p'; lines: string[] } | { kind: 'ul'; items: string[] }
  const blocks: Block[] = []
  let current: Block | null = null
  for (const raw of text.replace(/\*+$/, '').split('\n')) {
    const line = raw.trimEnd()
    if (!line.trim()) {
      current = null
      continue
    }
    if (BULLET.test(line)) {
      if (current?.kind !== 'ul') blocks.push((current = { kind: 'ul', items: [] }))
      current.items.push(line.replace(BULLET, ''))
    } else {
      const content = line.replace(HEADING, '')
      if (current?.kind !== 'p') blocks.push((current = { kind: 'p', lines: [] }))
      current.lines.push(content)
    }
  }

  return (
    <div className="space-y-2">
      {blocks.map((block, b) => {
        const last = b === blocks.length - 1
        if (block.kind === 'ul') {
          return (
            <ul key={b} className="list-disc space-y-1 pl-5">
              {block.items.map((item, i) => (
                <li key={i}>
                  {inline(item)}
                  {last && i === block.items.length - 1 && tail}
                </li>
              ))}
            </ul>
          )
        }
        return (
          <p key={b}>
            {inline(block.lines.join(' '))}
            {last && tail}
          </p>
        )
      })}
      {blocks.length === 0 && tail}
    </div>
  )
}

function StatTile({ value, label }: { value: number | string; label: string }) {
  return (
    <div className="card reveal-block p-2 text-center">
      <p className="font-bold tabular-nums" style={{ fontSize: 'var(--step-lg)' }}>
        {value}
      </p>
      <p className="hint" style={{ fontSize: 'var(--step-xs)' }}>
        {label}
      </p>
    </div>
  )
}

/** One row of the issue table -- real ticket data, not AI text. */
function IssueRow({ issue, onClose }: { issue: DashboardIssue; onClose: () => void }) {
  return (
    <tr className="reveal-block">
      <td>
        <Link to={`/tickets/${issue.id}`} onClick={onClose} className="block min-w-0">
          <span className="block truncate font-semibold">{issue.title}</span>
          <span className="hint font-mono" style={{ fontSize: 'var(--step-xs)' }}>
            {issue.code}
          </span>
        </Link>
      </td>
      <td>
        <PriorityBadge priority={issue.priority} />
      </td>
      <td className="text-right tabular-nums">{issue.reporters}</td>
      <td className="text-right tabular-nums">{issue.age_days}d</td>
    </tr>
  )
}

/**
 * The dashboard "briefing" popup, answered like a chat model answers: an AI
 * icon beside one reply bubble that starts with "thinking" dots, then the
 * sentence written out live as the model streams it (a real token stream
 * from the backend, not a pre-recorded animation), then the numbers and the
 * issue table built up piece by piece underneath. Nothing to type -- the
 * answer starts the moment the popup opens.
 *
 * Same component for both audiences -- the backend decides which one this
 * is and which fields to send; a citizen sees their ward's most-reported
 * open issues, an officer/admin their own highest-priority open tickets.
 */
export function DashboardSummaryModal({ onClose }: { onClose: () => void }) {
  const { t, language } = useI18n()
  const instant = useMemo(
    () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false,
    [],
  )

  const [run, setRun] = useState({ id: 0, refresh: false })
  const [busy, setBusy] = useState(true)
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [target, setTarget] = useState('')
  const [shown, setShown] = useState(0)
  const [streamDone, setStreamDone] = useState(false)
  const [buildStep, setBuildStep] = useState(0)
  const [loadError, setLoadError] = useState<Error | null>(null)
  const [regenError, setRegenError] = useState<Error | null>(null)
  const [regenLocked, setRegenLocked] = useState(false)

  // Only the run a Regenerate tap created asks for a refresh; a language
  // switch re-running the same run must not (it would hit the cooldown).
  const refreshedRun = useRef(-1)

  useEffect(() => {
    const controller = new AbortController()
    const refresh = run.refresh && refreshedRun.current !== run.id
    refreshedRun.current = run.id
    streamDashboardSummary(
      refresh,
      language,
      (event) => {
        switch (event.type) {
          case 'meta':
            setSummary(event.summary)
            setTarget('')
            setShown(0)
            setStreamDone(false)
            setBuildStep(0)
            break
          case 'delta':
            setTarget((text) => text + event.text)
            break
          case 'reset':
            setTarget('')
            setShown(0)
            break
          case 'done':
            setSummary(event.summary)
            setStreamDone(true)
            break
        }
      },
      controller.signal,
    )
      .catch((err: unknown) => {
        if (controller.signal.aborted) return
        const error = err instanceof Error ? err : new Error(String(err))
        if (refresh) setRegenError(error)
        else setLoadError(error)
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false)
      })
    return () => controller.abort()
    // `language`: switching the app's language mid-answer restarts it in
    // the new one (a cached answer in that language, if there is one).
  }, [run, language])

  useEffect(() => {
    if (shown >= target.length) return
    const id = window.setTimeout(() => setShown((s) => nextShown(target, s, instant)), TYPE_TICK_MS)
    return () => window.clearTimeout(id)
  }, [shown, target, instant])

  const textSettled = streamDone && shown >= target.length

  const isCitizen = summary?.audience === 'citizen'
  const issues = summary?.issues ?? []
  const hasChips =
    !isCitizen &&
    ((summary?.pending_duplicates ?? 0) > 0 ||
      (summary?.open_sos ?? 0) > 0 ||
      (summary?.pending_civic ?? 0) > 0)
  const tableStep = 3
  const firstRowStep = tableStep + 1
  const chipsStep = issues.length > 0 ? firstRowStep + issues.length : tableStep
  const buildTotal = chipsStep + (hasChips ? 1 : 0) + 1

  useEffect(() => {
    if (!textSettled || buildStep >= buildTotal) return
    const delay = instant ? 0 : buildStep === 0 ? BUILD_FIRST_MS : BUILD_TICK_MS
    const id = window.setTimeout(() => setBuildStep((s) => s + 1), delay)
    return () => window.clearTimeout(id)
  }, [textSettled, buildStep, buildTotal, instant])

  const answerComplete = textSettled && buildStep >= buildTotal

  const regenerate = () => {
    setRegenError(null)
    setBusy(true)
    setRegenLocked(true)
    window.setTimeout(() => setRegenLocked(false), REGENERATE_COOLDOWN_MS)
    setRun((r) => ({ id: r.id + 1, refresh: true }))
  }

  const stats: { value: number | string; label: string }[] = summary
    ? isCitizen
      ? [
          { value: summary.open_reports ?? 0, label: t('summary.yourOpen') },
          { value: summary.total_reports ?? 0, label: t('summary.yourTotal') },
          { value: summary.ward_open_reports ?? 0, label: t('summary.wardOpen') },
        ]
      : [
          { value: summary.open_reports_officer ?? 0, label: t('dashboard.open') },
          { value: summary.needs_attention ?? 0, label: t('summary.needsAttention') },
          {
            value:
              summary.oldest_open_days !== null
                ? `${summary.oldest_open_days} ${t('summary.days')}`
                : '—',
            label: t('summary.oldestOpen'),
          },
        ]
    : []

  return (
    <Modal title={t('summary.title')} onClose={onClose}>
      {loadError && !summary ? (
        <ErrorNote message={loadError.message || t('common.error')} />
      ) : (
        <div className="space-y-3">
          <div className="flex items-start gap-3">
            <span
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full"
              style={{ background: 'var(--color-brand-soft)', fontSize: '1.1rem' }}
              aria-hidden="true"
            >
              ✨
            </span>

            <div
              className="min-w-0 flex-1 space-y-3 rounded-2xl p-4"
              style={{ background: 'var(--color-canvas)' }}
              aria-busy={!answerComplete}
            >
              {summary && (summary.scope_label || (textSettled && summary.ai_generated)) && (
                <div className="flex flex-wrap items-center gap-2">
                  {summary.scope_label && (
                    <span className="chip" style={{ background: 'var(--color-surface)' }}>
                      {summary.scope_label}
                    </span>
                  )}
                  {textSettled && summary.ai_generated && (
                    <span
                      className="chip reveal-block"
                      style={{
                        background: 'var(--color-brand-soft)',
                        color: 'var(--color-brand-ink)',
                        borderColor: 'var(--color-brand)',
                      }}
                    >
                      ✨ {t('summary.aiWritten')}
                    </span>
                  )}
                </div>
              )}

              {shown === 0 && !textSettled ? (
                <p className="flex items-center gap-2 hint" style={{ fontSize: 'var(--step-sm)' }}>
                  <span className="thinking-dots" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </span>
                  {t('summary.thinking')}
                </p>
              ) : (
                // Screen readers get the finished answer once (below), not
                // every letter as it streams.
                <div aria-hidden="true" style={{ fontSize: 'var(--step-md)', lineHeight: 1.6 }}>
                  <MarkdownLite
                    text={target.slice(0, shown)}
                    tail={!textSettled ? <span className="stream-caret" /> : undefined}
                  />
                </div>
              )}
              <div className="sr-only" aria-live="polite">
                {textSettled && <MarkdownLite text={target} />}
              </div>

              {buildStep > 0 && (
                <div className="grid grid-cols-3 gap-2">
                  {stats.slice(0, buildStep).map((stat) => (
                    <StatTile key={stat.label} value={stat.value} label={stat.label} />
                  ))}
                </div>
              )}

              {issues.length > 0 && buildStep > tableStep && (
                <div className="reveal-block">
                  <p className="label mb-1.5">
                    {isCitizen ? t('summary.wardIssuesTitle') : t('summary.attentionIssuesTitle')}
                  </p>
                  {/* overflow-x-auto: a safety net on very narrow screens, not
                      the expectation -- four columns fit the bubble's own width. */}
                  <div className="overflow-x-auto">
                    <table className="data-table" style={{ background: 'var(--color-surface)' }}>
                      <thead>
                        <tr>
                          <th>{t('summary.colReport')}</th>
                          <th>{t('ticket.priority')}</th>
                          <th className="text-right">{t('summary.colReporters')}</th>
                          <th className="text-right">{t('summary.colAge')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {issues.slice(0, Math.max(0, buildStep - firstRowStep)).map((issue) => (
                          <IssueRow key={issue.id} issue={issue} onClose={onClose} />
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {summary && hasChips && buildStep > chipsStep && (
                <div className="reveal-block flex flex-wrap gap-2">
                  {(summary.pending_duplicates ?? 0) > 0 && (
                    <Link
                      to="/authority/duplicates"
                      onClick={onClose}
                      className="chip"
                      style={{
                        background: 'var(--color-surface)',
                        color: 'var(--color-brand-ink)',
                        borderColor: 'var(--color-brand)',
                      }}
                    >
                      🔗 {summary.pending_duplicates} {t('summary.pendingDuplicates')}
                    </Link>
                  )}
                  {(summary.open_sos ?? 0) > 0 && (
                    <Link
                      to="/authority/emergencies"
                      onClick={onClose}
                      className="chip"
                      style={{
                        background: 'var(--color-surface)',
                        color: 'var(--color-danger)',
                        borderColor: 'var(--color-danger)',
                      }}
                    >
                      🆘 {summary.open_sos} {t('summary.openSos')}
                    </Link>
                  )}
                  {(summary.pending_civic ?? 0) > 0 && (
                    <Link
                      to="/authority/civic"
                      onClick={onClose}
                      className="chip"
                      style={{
                        background: 'var(--color-surface)',
                        color: 'var(--color-warn)',
                        borderColor: 'var(--color-warn)',
                      }}
                    >
                      🚯 {summary.pending_civic} {t('summary.pendingCivic')}
                    </Link>
                  )}
                </div>
              )}
            </div>
          </div>

          {regenError && (
            <ErrorNote
              message={
                regenError instanceof ApiError && regenError.status === 429
                  ? t('summary.tooSoon')
                  : regenError.message || t('common.error')
              }
            />
          )}

          {/* Outside the bubble, like a message's action row: it appears once
              the answer is finished, not while it is still being written. */}
          {summary && answerComplete && (
            <div className="reveal-block flex flex-wrap items-center justify-between gap-2 pl-12">
              <Button variant="secondary" disabled={busy || regenLocked} onClick={regenerate}>
                🔄 {busy ? t('summary.regenerating') : t('summary.regenerate')}
              </Button>
              <span className="hint" style={{ fontSize: 'var(--step-xs)' }}>
                {formatDate(summary.generated_at, language)}
              </span>
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}
