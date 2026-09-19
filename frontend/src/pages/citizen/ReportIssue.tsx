import { useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button, Card, ErrorNote, PageTitle, StatusBadge } from '../../components/ui'
import { api } from '../../lib/api'
import { useQuery } from '../../lib/cache'
import { formatDistance } from '../../lib/geo'
import { useI18n } from '../../lib/i18n'
import type { Category, TicketCreateResponse } from '../../lib/types'
import { EMPTY_DRAFT, ReportDraft, type DraftValue } from './ReportDraft'

// Enough for "three problems on one street"; more than this in one sitting
// is better as separate visits than one very long form.
const MAX_REPORTS = 5

type Slot = { key: number; startAt: DraftValue['coords'] }

export function ReportIssue() {
  const { t, language } = useI18n()

  // Reference data ("ref:" survives writes): the category list is the same
  // for everyone and changes only on reseed, so it is reused for 10 minutes.
  const categoriesQuery = useQuery('ref:categories', () => api.categories(), {
    freshMs: 10 * 60_000,
  })
  const categories: Category[] = categoriesQuery.data ?? []
  const [slots, setSlots] = useState<Slot[]>([{ key: 0, startAt: null }])
  // Latest values reported by each draft, by slot key. A ref, not state: the
  // drafts report on every keystroke and nothing here renders from it.
  const values = useRef<Record<number, DraftValue>>({})
  const nextKey = useRef(1)

  const [error, setError] = useState<string | null>(null)
  const [failures, setFailures] = useState<Record<number, string>>({})
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState(0)
  const [results, setResults] = useState<TicketCreateResponse[]>([])
  const [done, setDone] = useState(false)

  const addReport = () => {
    const last = slots[slots.length - 1]
    const lastCoords = last ? values.current[last.key]?.coords ?? null : null
    const key = nextKey.current++
    setSlots((current) => [...current, { key, startAt: lastCoords }])
    // Bring the new, empty report into view.
    window.setTimeout(() => {
      document.getElementById(`report-${key}`)?.scrollIntoView({ behavior: 'smooth' })
    }, 50)
  }

  const removeReport = (key: number) => {
    setSlots((current) => current.filter((slot) => slot.key !== key))
    delete values.current[key]
    setFailures((current) => {
      const next = { ...current }
      delete next[key]
      return next
    })
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setFailures({})

    const pending = slots.map((slot) => ({
      slot,
      value: values.current[slot.key] ?? EMPTY_DRAFT,
    }))

    const unlocated = pending.findIndex(({ value }) => value.coords === null)
    if (unlocated !== -1) {
      setError(
        pending.length > 1
          ? `${t('report.reportN')} ${unlocated + 1}: ${t('report.locationNeeded')}`
          : t('report.locationNeeded'),
      )
      return
    }

    setBusy(true)
    setProgress(0)
    const created: TicketCreateResponse[] = []
    const failed: Record<number, string> = {}

    // One at a time, not in parallel: two reports of the same spot sent
    // together could each miss the other in duplicate matching, and a
    // failure is easier to pin to the report that caused it.
    for (const { slot, value } of pending) {
      try {
        const response = await api.createTicket(
          {
            description: value.description,
            latitude: value.coords!.latitude,
            longitude: value.coords!.longitude,
            category_id: value.categoryId || undefined,
            address_text: value.address || undefined,
            description_lang: language,
          },
          value.photos,
        )
        created.push(response)
      } catch (err) {
        failed[slot.key] = err instanceof Error ? err.message : t('common.error')
      }
      setProgress((count) => count + 1)
    }

    setBusy(false)
    setResults((current) => [...current, ...created])

    if (Object.keys(failed).length === 0) {
      setDone(true)
      window.scrollTo({ top: 0 })
      return
    }

    // Keep only the reports that failed in the form, with their errors, so
    // nothing already filed gets submitted twice.
    setSlots((current) => current.filter((slot) => slot.key in failed))
    setFailures(failed)
    setError(t('report.someFailed'))
    window.scrollTo({ top: 0 })
  }

  if (done) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <div
          className="card p-5 text-center"
          style={{ background: 'var(--color-good-soft)', borderColor: 'var(--color-good)' }}
        >
          <p aria-hidden="true" style={{ fontSize: '2.5rem' }}>
            ✅
          </p>
          <h1 className="font-bold" style={{ fontSize: 'var(--step-lg)', color: 'var(--color-good)' }}>
            {results.length > 1 ? t('report.submittedMany') : t('report.submitted')}
          </h1>
          {results.length > 1 && <p className="mt-1 hint">{results.length}</p>}
        </div>

        {results.map((result) => (
          <ResultCard key={result.ticket.id} result={result} />
        ))}

        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => {
              setResults([])
              setDone(false)
              values.current = {}
              setSlots([{ key: nextKey.current++, startAt: null }])
            }}
          >
            ➕ {t('report.reportAnother')}
          </Button>
          <Link to="/" className="btn btn-secondary">
            {t('nav.home')}
          </Link>
        </div>
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-2xl space-y-4">
      <PageTitle title={t('report.title')} />

      {error && <ErrorNote message={error} />}

      {results.length > 0 && (
        <Card>
          <p className="font-semibold" style={{ color: 'var(--color-good)' }}>
            ✅ {t('report.alreadyFiled')}
          </p>
          <ul className="mt-1">
            {results.map((result) => (
              <li key={result.ticket.id} className="font-mono">
                {result.ticket.public_code}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {slots.map((slot, index) => (
        <div key={slot.key} id={`report-${slot.key}`} className="space-y-2">
          {failures[slot.key] && <ErrorNote message={failures[slot.key]} />}
          <ReportDraft
            index={index}
            total={slots.length}
            categories={categories}
            startAt={slot.startAt}
            onChange={(value) => {
              values.current[slot.key] = value
            }}
            onRemove={slots.length > 1 ? () => removeReport(slot.key) : undefined}
          />
        </div>
      ))}

      {slots.length < MAX_REPORTS && (
        <Button type="button" variant="secondary" className="w-full" onClick={addReport} disabled={busy}>
          ➕ {t('report.addAnother')}
        </Button>
      )}
      <p className="hint">{t('report.addAnotherHint')}</p>

      <Button type="submit" disabled={busy} className="w-full">
        {busy
          ? `${t('report.submitting')} ${progress}/${slots.length}`
          : slots.length > 1
            ? `${t('report.submitAll')} (${slots.length})`
            : t('report.submit')}
      </Button>
    </form>
  )
}

/** What happened to one submitted report: its code, ward, and any duplicate. */
function ResultCard({ result }: { result: TicketCreateResponse }) {
  const { t } = useI18n()
  const navigate = useNavigate()
  const { ticket, possible_duplicates: duplicates } = result
  const mergedInto = result.auto_merged_into

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono font-bold" style={{ fontSize: 'var(--step-md)' }}>
          {ticket.public_code}
        </span>
        <StatusBadge status={ticket.status} />
      </div>
      <p className="mt-1" style={{ fontSize: 'var(--step-sm)' }}>
        {ticket.title}
      </p>
      {ticket.ward_number !== null && (
        <p className="mt-1 hint">
          {t('report.goesToWard')}: {t('auth.ward')} {ticket.ward_number}
          {ticket.ward_name ? ` — ${ticket.ward_name}` : ''}
        </p>
      )}

      {mergedInto && (
        <div className="mt-3 rounded-lg border p-3" style={{ borderColor: 'var(--color-brand)' }}>
          <p className="font-semibold">🔗 {t('report.autoMerged')}</p>
          <p className="hint">{t('report.autoMergedNote')}</p>
          <p className="mt-1">
            <span className="font-mono font-semibold">{mergedInto.public_code}</span>{' '}
            {result.auto_merge_score !== null && (
              <span className="chip">{Math.round(result.auto_merge_score * 100)}%</span>
            )}{' '}
            <span className="hint">
              👥 {mergedInto.child_count + 1} {t('ticket.reporters')}
            </span>
          </p>
        </div>
      )}

      {!mergedInto && duplicates.length > 0 && (
        <div className="mt-3">
          <p className="font-semibold">{t('report.possibleDuplicates')}</p>
          <p className="hint">{t('report.duplicateNote')}</p>
          <ul className="mt-2 space-y-1">
            {duplicates.map((candidate) => (
              <li key={candidate.id} className="flex flex-wrap items-center gap-2">
                <span className="font-mono">{candidate.candidate?.public_code}</span>
                <span className="hint">
                  {formatDistance(candidate.distance_m)} {t('common.away')}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <Button
        variant="secondary"
        className="mt-3"
        onClick={() => navigate(`/tickets/${mergedInto?.id ?? ticket.id}`)}
      >
        {mergedInto ? t('report.viewMain') : t('report.viewReport')}
      </Button>
    </Card>
  )
}
