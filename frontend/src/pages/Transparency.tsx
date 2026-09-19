import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, ErrorNote, PageTitle, Spinner, Stat } from '../components/ui'
import { api } from '../lib/api'
import { formatDate } from '../lib/geo'
import { useI18n } from '../lib/i18n'
import type { CategoryStat, PublicStats, WardStat } from '../lib/types'

/**
 * The public accountability page: no login, and deliberately no per-ticket
 * data. Counts, medians and ward/category breakdowns only -- an anonymous
 * visitor can see that ward 5 has a backlog without reading what any one
 * citizen wrote or where they live. See docs/GUIDE.md for the boundary.
 */

function formatDuration(hours: number | null, language: 'en' | 'ne'): string {
  if (hours === null) return language === 'ne' ? '—' : '—'
  if (hours < 24) {
    const rounded = Math.round(hours * 10) / 10
    return language === 'ne' ? `${rounded} घण्टा` : `${rounded}h`
  }
  const days = Math.round((hours / 24) * 10) / 10
  return language === 'ne' ? `${days} दिन` : `${days}d`
}

function Bar({ label, value, max, tone }: { label: string; value: number; max: number; tone: string }) {
  const width = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className="flex items-center gap-2">
      <span className="w-24 shrink-0 truncate" style={{ fontSize: 'var(--step-sm)' }}>
        {label}
      </span>
      <div
        className="h-3 flex-1 overflow-hidden rounded-full"
        style={{ background: 'var(--color-canvas)' }}
      >
        <div className="h-full rounded-full" style={{ width: `${width}%`, background: tone }} />
      </div>
      <span className="w-8 shrink-0 text-right tabular-nums hint">{value}</span>
    </div>
  )
}

function WardRow({ ward, max, language }: { ward: WardStat; max: number; language: 'en' | 'ne' }) {
  const { t } = useI18n()
  const label =
    (language === 'ne' ? ward.name_ne : ward.name_en) ?? `${t('auth.ward')} ${ward.number}`
  return (
    <div className="space-y-1">
      <Bar label={label} value={ward.total} max={max} tone="var(--color-brand)" />
      <p className="pl-[6.5rem] hint">
        {ward.open} {t('transparency.open').toLowerCase()} · {ward.resolved}{' '}
        {t('transparency.resolved').toLowerCase()}
        {ward.median_resolution_hours !== null &&
          ` · ${t('transparency.median')} ${formatDuration(ward.median_resolution_hours, language)}`}
      </p>
    </div>
  )
}

function CategoryRow({ category, max, language }: { category: CategoryStat; max: number; language: 'en' | 'ne' }) {
  const { t } = useI18n()
  const label = language === 'ne' ? category.name_ne : category.name_en
  return (
    <div className="space-y-1">
      <Bar label={label} value={category.total} max={max} tone="var(--color-info)" />
      <p className="pl-[6.5rem] hint">
        {category.resolved} {t('transparency.resolved').toLowerCase()}
        {category.median_resolution_hours !== null &&
          ` · ${t('transparency.median')} ${formatDuration(category.median_resolution_hours, language)}`}
      </p>
    </div>
  )
}

export function Transparency() {
  const { t, language } = useI18n()
  const [stats, setStats] = useState<PublicStats | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    api
      .publicStats()
      .then((result) => {
        if (!cancelled) setStats(result)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : t('common.error'))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (loading) return <Spinner />
  if (error || !stats) return <ErrorNote message={error ?? t('common.error')} />

  const maxWard = Math.max(1, ...stats.by_ward.map((w) => w.total))
  const maxCategory = Math.max(1, ...stats.by_category.map((c) => c.total))

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4">
      <PageTitle
        title={t('transparency.title')}
        subtitle={`${language === 'ne' ? stats.municipality_name_ne : stats.municipality_name_en} · ${t('transparency.hint')}`}
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label={t('transparency.total')} value={stats.total_tickets} />
        <Stat label={t('transparency.open')} value={stats.open_tickets} tone="warn" />
        <Stat label={t('transparency.resolved')} value={stats.resolved_tickets} tone="good" />
        <Stat label={t('transparency.resolvedThisMonth')} value={stats.resolved_this_month} tone="good" />
      </div>

      <Card>
        <p className="label">{t('transparency.medianOverall')}</p>
        <p className="mt-1 font-bold" style={{ fontSize: 'var(--step-xl)' }}>
          {formatDuration(stats.median_resolution_hours, language)}
        </p>
        <p className="mt-1 hint">{t('transparency.medianHint')}</p>
      </Card>

      <Card>
        <h2 className="font-bold" style={{ fontSize: 'var(--step-md)' }}>
          {t('transparency.byWard')}
        </h2>
        <div className="mt-3 space-y-3">
          {stats.by_ward.map((ward) => (
            <WardRow key={ward.number} ward={ward} max={maxWard} language={language} />
          ))}
        </div>
      </Card>

      <Card>
        <h2 className="font-bold" style={{ fontSize: 'var(--step-md)' }}>
          {t('transparency.byCategory')}
        </h2>
        <div className="mt-3 space-y-3">
          {stats.by_category.map((category) => (
            <CategoryRow key={category.key} category={category} max={maxCategory} language={language} />
          ))}
        </div>
      </Card>

      <p className="text-center hint">
        {t('transparency.generatedAt')} {formatDate(stats.generated_at, language)}
      </p>

      <p className="text-center">
        <Link to="/login" className="font-semibold underline" style={{ color: 'var(--color-brand)' }}>
          {t('transparency.backToLogin')}
        </Link>
      </p>
    </div>
  )
}
