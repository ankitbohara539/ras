import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowDownToLine,
  ArrowRight,
  Building2,
  ChartNoAxesCombined,
  CheckCheck,
  ChevronDown,
  ChevronUp,
  Clock3,
  FileText,
  Search,
  ShieldCheck,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Brand, DisplayControls } from '../components/Brand'
import { InstallAppButton } from '../components/PwaPrompts'
import { DashboardSkeleton, EmptyState, ErrorNote } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useQuery } from '../lib/cache'
import { formatDate } from '../lib/geo'
import { useI18n } from '../lib/i18n'

const COLORS = ['#1D293D', '#526176', '#087F75']
const TABLE_BATCH_SIZE = 5
const tooltipStyle = {
  border: '1px solid var(--color-line)',
  borderRadius: 10,
  background: 'var(--color-surface)',
  color: 'var(--color-ink)',
  fontSize: 12,
}
const percentage = (value: number, total: number) =>
  total ? Math.round((value / total) * 100) : 0

export function Transparency() {
  const { t, language } = useI18n()
  const { profile, isAuthority } = useAuth()
  const text = (en: string, ne: string) => (language === 'ne' ? ne : en)
  const {
    data: stats,
    error,
    loading,
  } = useQuery('public:stats', () => api.publicStats(), {
    refetchIntervalMs: 60_000,
  })
  const [breakdown, setBreakdown] = useState<'wards' | 'categories'>('wards')
  const [search, setSearch] = useState('')
  const [sort, setSort] = useState<'total' | 'rate'>('total')
  const [visibleRowCount, setVisibleRowCount] = useState(TABLE_BATCH_SIZE)
  const duration = (hours: number | null) =>
    hours === null
      ? '—'
      : hours < 24
        ? `${Math.round(hours * 10) / 10} ${text('hrs', 'घण्टा')}`
        : `${Math.round((hours / 24) * 10) / 10} ${text('days', 'दिन')}`
  const rate = stats
    ? percentage(stats.resolved_tickets, stats.total_tickets)
    : 0
  const wardData =
    stats?.by_ward.map((w) => ({
      name: `${t('auth.ward')} ${w.number}`,
      detail: (language === 'ne' ? w.name_ne : w.name_en) ?? '',
      total: w.total,
      resolved: w.resolved,
      open: w.open,
      median: w.median_resolution_hours,
      rate: percentage(w.resolved, w.total),
    })) ?? []
  const categoryData =
    stats?.by_category.map((c) => ({
      name: language === 'ne' ? c.name_ne : c.name_en,
      detail: '',
      total: c.total,
      resolved: c.resolved,
      median: c.median_resolution_hours,
      rate: percentage(c.resolved, c.total),
    })) ?? []
  const rows = (breakdown === 'wards' ? wardData : categoryData)
    .filter((r) =>
      `${r.name} ${r.detail}`.toLowerCase().includes(search.toLowerCase()),
    )
    .sort((a, b) => b[sort] - a[sort])
  const displayedRows = rows.slice(0, visibleRowCount)
  const topWards = [...wardData]
    .sort((a, b) => b.total - a.total)
    .filter((ward) => ward.total > 0)
    .slice(0, 6)
  const statuses = stats
    ? [
        { name: t('transparency.resolved'), value: stats.resolved_tickets },
        { name: t('transparency.open'), value: stats.open_tickets },
        {
          name: text('Other statuses', 'अन्य स्थिति'),
          value: Math.max(
            0,
            stats.total_tickets - stats.resolved_tickets - stats.open_tickets,
          ),
        },
      ]
    : []
  const exportCsv = () => {
    const safeCell = (value: unknown) => {
      let cell = String(value ?? '')
      if (/^[=+@\-\t\r]/.test(cell)) cell = "'" + cell
      return '"' + cell.replace(/"/g, '""') + '"'
    }
    const data = [
      [
        text('Area / category', 'क्षेत्र / श्रेणी'),
        t('transparency.total'),
        t('transparency.resolved'),
        text('Resolution %', 'समाधान %'),
        text('Median hours', 'मध्यक घण्टा'),
      ],
      ...rows.map((r) => [r.name, r.total, r.resolved, r.rate, r.median]),
    ]
    const url = URL.createObjectURL(
      new Blob(
        ['\uFEFF' + data.map((r) => r.map(safeCell).join(',')).join('\r\n')],
        { type: 'text/csv;charset=utf-8;' },
      ),
    )
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `sahayatri-${stats?.municipality_code ?? 'public'}-${breakdown}.csv`
    anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return (
    <div className="min-h-screen">
      <a
        href="#public-main"
        className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:bg-surface focus:p-3"
      >
        {text('Skip to content', 'मुख्य सामग्रीमा जानुहोस्')}
      </a>
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-[1320px] flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <Brand to="/public-dashboard" />
          <nav
            className="flex items-center gap-2"
            aria-label={text('Account', 'खाता')}
          >
            <div className="hidden md:block">
              <DisplayControls />
            </div>
            {profile ? (
              <Link
                to={isAuthority ? '/authority' : '/'}
                className="btn btn-primary"
              >
                {t('nav.dashboard')}
                <ArrowRight size={16} />
              </Link>
            ) : (
              <>
                <Link to="/login" className="btn btn-secondary">
                  {t('auth.login')}
                </Link>
                <Link to="/register" className="btn btn-primary">
                  {t('auth.register')}
                </Link>
              </>
            )}
          </nav>
        </div>
        <div className="mx-auto flex max-w-[1320px] justify-end border-t border-line px-4 py-2 sm:px-6 md:hidden">
          <div>
            <DisplayControls />
          </div>
        </div>
      </header>
      <main
        id="public-main"
        className="dashboard-page mx-auto max-w-[1320px] space-y-6 px-4 py-7 sm:px-6 lg:px-8 lg:py-10"
      >
        
        {!!error && (
          <ErrorNote
            message={error instanceof Error ? error.message : t('common.error')}
          />
        )}
        {loading && <DashboardSkeleton />}
        {stats && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-ink-soft">
              <span className="flex items-center gap-2">
                <Building2 size={16} />
                <strong className="text-ink">
                  {language === 'ne'
                    ? stats.municipality_name_ne
                    : stats.municipality_name_en}
                </strong>
                <span className="rounded-md border border-line bg-surface px-2 py-1">
                  {text('All-time overview', 'हालसम्मको विवरण')}
                </span>
              </span>
              <span>
                {t('transparency.generatedAt')}{' '}
                {formatDate(stats.generated_at, language)}
              </span>
            </div>
            <section
              aria-label={text('Community statistics', 'समुदायको तथ्याङ्क')}
              className="dashboard-grid grid grid-cols-2 gap-3 lg:grid-cols-4"
            >
              {[
                {
                  label: text('Total civic reports', 'कुल नागरिक उजुरी'),
                  value: stats.total_tickets.toLocaleString(language),
                  hint: text(
                    'Reports received across wards',
                    'सबै वडाबाट प्राप्त उजुरी',
                  ),
                  icon: FileText,
                },
                {
                  label: text('Open civic reports', 'खुला नागरिक उजुरी'),
                  value: stats.open_tickets.toLocaleString(language),
                  hint: text(
                    'Awaiting action or in progress',
                    'कारबाहीको प्रतीक्षामा वा प्रक्रियामा',
                  ),
                  icon: Clock3,
                },
                {
                  label: text('Resolved civic reports', 'समाधान भएका नागरिक उजुरी'),
                  value: stats.resolved_tickets.toLocaleString(language),
                  hint: text(
                    `${stats.resolved_this_month} resolved this month`,
                    `यो महिना ${stats.resolved_this_month} समाधान`,
                  ),
                  icon: CheckCheck,
                },
                {
                  label: text('Civic report resolution rate', 'नागरिक उजुरी समाधान दर'),
                  value: stats.total_tickets ? `${rate}%` : '—',
                  hint: text(
                    'Resolved / all reports',
                    'समाधान भएका / सबै उजुरी',
                  ),
                  icon: ChartNoAxesCombined,
                },
              ].map(({ icon: Icon, ...item }) => (
                <article key={item.label} className="card p-4 sm:p-5">
                  <div className="flex items-center justify-between gap-2">
                    <h2 className="text-sm font-medium text-ink-soft">
                      {item.label}
                    </h2>
                    <Icon size={17} className="shrink-0 text-ink-faint" />
                  </div>
                  <p className="my-3 text-3xl font-semibold tracking-tight tabular-nums sm:text-4xl">
                    {item.value}
                  </p>
                  <p className="hint">{item.hint}</p>
                </article>
              ))}
            </section>
            {stats.total_tickets === 0 && (
              <EmptyState
                title={text(
                  'Your community story starts here',
                  'समुदायको यात्रा यहाँबाट सुरु हुन्छ',
                )}
                hint={text(
                  'No reports have been recorded yet. Charts will appear as reports arrive.',
                  'अहिलेसम्म उजुरी छैन। उजुरी आएपछि चार्ट देखिनेछ।',
                )}
                action={
                  <Link
                    to={profile ? '/report' : '/register'}
                    className="btn btn-primary"
                  >
                    {t('nav.report')}
                    <ArrowRight size={16} />
                  </Link>
                }
              />
            )}
            <div className="dashboard-grid grid gap-5 lg:grid-cols-[1.7fr_1fr]">
              <section
                className="card chart-panel p-5 sm:p-6"
                aria-labelledby="category-chart-title"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h2
                      id="category-chart-title"
                      className="text-base font-semibold"
                    >
                      {text(
                        'Where attention is needed',
                        'ध्यान दिनुपर्ने क्षेत्र',
                      )}
                    </h2>
                    <p className="mt-1 hint">
                      {text(
                        'Top 6 wards by total reports • all time',
                        'कुल उजुरीका आधारमा शीर्ष ६ वडा • हालसम्म',
                      )}
                    </p>
                  </div>
                  <span className="icon-tile">
                    <ChartNoAxesCombined />
                  </span>
                </div>
                {topWards.length ? (
                  <div className="mt-6 h-[280px] w-full">
                    <ResponsiveContainer
                      width="100%"
                      height="100%"
                      minWidth={0}
                    >
                      <BarChart
                        data={topWards}
                        layout="vertical"
                        margin={{ left: 0, right: 20, bottom: 0 }}
                        accessibilityLayer
                      >
                        <CartesianGrid
                          horizontal={false}
                          stroke="var(--color-line)"
                          strokeDasharray="3 3"
                        />
                        <XAxis
                          type="number"
                          allowDecimals={false}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          type="category"
                          dataKey="name"
                          width={115}
                          tick={{ fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          contentStyle={tooltipStyle}
                          cursor={{ fill: 'var(--color-brand-soft)' }}
                          content={({ active, payload }) => {
                            const ward = payload?.[0]?.payload as
                              | (typeof topWards)[number]
                              | undefined
                            if (!active || !ward) return null
                            return (
                              <div
                                className="rounded-lg border border-line bg-surface p-3 shadow-lg"
                                data-testid="ward-chart-tooltip"
                              >
                                <p className="font-semibold text-ink">{ward.name}</p>
                                {ward.detail && (
                                  <p className="mt-0.5 text-xs text-ink-soft">{ward.detail}</p>
                                )}
                                <p className="mt-2 text-xs text-ink-soft">
                                  {t('transparency.total')}: {' '}
                                  <strong className="text-ink tabular-nums">
                                    {ward.total.toLocaleString(language)}
                                  </strong>
                                </p>
                              </div>
                            )
                          }}
                        />
                        <Bar
                          name={t('transparency.total')}
                          dataKey="total"
                          fill="#1D293D"
                          radius={[0, 4, 4, 0]}
                          maxBarSize={24}
                          isAnimationActive={false}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <p className="py-24 text-center hint">
                    {text(
                      'No ward data yet',
                      'वडाको तथ्याङ्क उपलब्ध छैन',
                    )}
                  </p>
                )}
                <p className="mt-3 border-t border-line pt-4 hint">
                  {text(
                    'Report volume shows community demand; it does not measure severity.',
                    'उजुरीको सङ्ख्याले समुदायको माग देखाउँछ, गम्भीरता मापन गर्दैन।',
                  )}
                </p>
              </section>
              <section
                className="card chart-panel p-5 sm:p-6"
                aria-labelledby="status-chart-title"
              >
                <h2 id="status-chart-title" className="text-base font-semibold">
                  {text('From reports to resolutions', 'उजुरीदेखि समाधानसम्म')}
                </h2>
                <p className="mt-1 hint">
                  {text(
                    'Current status of all reports',
                    'सबै उजुरीको हालको स्थिति',
                  )}
                </p>
                <div className="relative h-[220px]">
                  {stats.total_tickets > 0 && (
                    <ResponsiveContainer
                      width="100%"
                      height="100%"
                      minWidth={0}
                    >
                      <PieChart accessibilityLayer>
                        <Pie
                          data={statuses}
                          dataKey="value"
                          nameKey="name"
                          innerRadius={68}
                          outerRadius={88}
                          paddingAngle={3}
                          stroke="var(--color-surface)"
                          isAnimationActive={false}
                        >
                          {statuses.map((s, i) => (
                            <Cell key={s.name} fill={COLORS[i]} />
                          ))}
                        </Pie>
                        <Tooltip contentStyle={tooltipStyle} />
                      </PieChart>
                    </ResponsiveContainer>
                  )}
                  <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-3xl font-semibold tracking-tight">
                      {stats.total_tickets ? `${rate}%` : '—'}
                    </span>
                    <span className="hint">{t('transparency.resolved')}</span>
                  </div>
                </div>
                <ul className="space-y-2">
                  {statuses.map((s, i) => (
                    <li
                      key={s.name}
                      className="flex items-center justify-between text-sm"
                    >
                      <span className="flex items-center gap-2">
                        <span
                          className="h-2.5 w-2.5 rounded-full"
                          style={{ background: COLORS[i] }}
                        />
                        {s.name}
                      </span>
                      <strong className="font-medium tabular-nums">
                        {s.value.toLocaleString(language)}
                      </strong>
                    </li>
                  ))}
                </ul>
                <div className="mt-4 flex items-center justify-between gap-2 border-t border-line pt-4">
                  <span className="hint">
                    {t('transparency.medianOverall')}
                  </span>
                  <strong className="text-sm">
                    {duration(stats.median_resolution_hours)}
                  </strong>
                </div>
              </section>
            </div>
            <section
              className="card overflow-hidden"
              aria-labelledby="breakdown-title"
            >
              <div className="flex flex-wrap items-center justify-between gap-3 p-4 sm:px-5">
                <h2 id="breakdown-title" className="font-semibold">
                  {text(
                    'Explore the numbers',
                    'तथ्याङ्क विस्तारमा हेर्नुहोस्',
                  )}
                </h2>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={exportCsv}
                  disabled={!rows.length}
                >
                  <ArrowDownToLine size={16} />
                  {text('Export CSV', 'CSV डाउनलोड')}
                </button>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-3 border-y border-line bg-canvas/50 px-4 py-2.5 sm:px-5">
                <div
                  className="flex rounded-lg border border-line bg-surface p-1"
                  role="group"
                  aria-label={text('Breakdown', 'विवरण')}
                >
                  {(['wards', 'categories'] as const).map((value) => (
                    <button
                      type="button"
                      key={value}
                      aria-pressed={breakdown === value}
                      onClick={() => {
                        setBreakdown(value)
                        setSearch('')
                        setVisibleRowCount(TABLE_BATCH_SIZE)
                      }}
                      className={`btn px-3 ${breakdown === value ? 'btn-primary' : 'btn-ghost'}`}
                    >
                      {value === 'wards'
                        ? t('transparency.byWard')
                        : t('transparency.byCategory')}
                    </button>
                  ))}
                </div>
                <div className="flex w-full flex-wrap gap-2 sm:w-auto">
                  <label className="relative min-w-0 flex-1">
                    <Search
                      size={15}
                      className="absolute left-3 top-3.5 text-ink-faint"
                    />
                    <input
                      className="field pl-9"
                      value={search}
                      onChange={(e) => {
                        setSearch(e.target.value)
                        setVisibleRowCount(TABLE_BATCH_SIZE)
                      }}
                      placeholder={text(
                        'Search breakdown…',
                        'विवरण खोज्नुहोस्…',
                      )}
                      aria-label={text('Search breakdown', 'विवरण खोज्नुहोस्')}
                    />
                  </label>
                  <select
                    className="field w-auto"
                    value={sort}
                    onChange={(e) => {
                      setSort(e.target.value as 'total' | 'rate')
                      setVisibleRowCount(TABLE_BATCH_SIZE)
                    }}
                    aria-label={text(
                      'Sort breakdown',
                      'विवरण क्रमबद्ध गर्नुहोस्',
                    )}
                  >
                    <option value="total">
                      {text('Most reports', 'धेरै उजुरी')}
                    </option>
                    <option value="rate">
                      {text('Highest resolution', 'उच्च समाधान दर')}
                    </option>
                  </select>
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="data-table data-table-compact">
                  <caption className="sr-only">
                    {text(
                      'Public report counts and resolution metrics',
                      'सार्वजनिक उजुरी तथा समाधान तथ्याङ्क',
                    )}
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">
                        {breakdown === 'wards'
                          ? t('auth.ward')
                          : text('Category', 'श्रेणी')}
                      </th>
                      <th scope="col">{t('transparency.total')}</th>
                      <th scope="col">{t('transparency.resolved')}</th>
                      <th scope="col">
                        {text('Resolution rate', 'समाधान दर')}
                      </th>
                      <th scope="col">{text('Median time', 'मध्यक समय')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayedRows.map((row) => (
                      <tr key={row.name}>
                        <th
                          scope="row"
                          className="!bg-transparent !font-medium !text-ink"
                        >
                          {row.name}
                          {row.detail && (
                            <span className="mt-0.5 block font-normal hint">
                              {row.detail}
                            </span>
                          )}
                        </th>
                        <td className="tabular-nums">{row.total}</td>
                        <td className="tabular-nums">{row.resolved}</td>
                        <td>
                          <div className="flex min-w-28 items-center gap-3">
                            <div
                              className="h-1.5 w-16 overflow-hidden rounded-full bg-line"
                              aria-hidden="true"
                            >
                              <div
                                className="h-full rounded-full bg-brand"
                                style={{ width: `${row.rate}%` }}
                              />
                            </div>
                            <span className="tabular-nums">
                              {row.total ? `${row.rate}%` : '—'}
                            </span>
                          </div>
                        </td>
                        <td className="whitespace-nowrap tabular-nums">
                          {duration(row.median)}
                        </td>
                      </tr>
                    ))}
                    {!rows.length && (
                      <tr>
                        <td
                          colSpan={5}
                          className="py-8 text-center text-ink-soft"
                        >
                          {text('No matching results', 'मिल्दो नतिजा भेटिएन')}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
              {!!rows.length && (
                <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line px-4 py-2.5 text-xs text-ink-soft sm:px-5">
                  <span>
                    {text('Showing', 'देखाइएको')} {Math.min(visibleRowCount, rows.length)} {text('of', 'मध्ये')} {rows.length}
                  </span>
                  <div className="flex items-center gap-1">
                    {visibleRowCount > TABLE_BATCH_SIZE && (
                      <button
                        type="button"
                        className="btn btn-ghost min-h-9 px-3"
                        onClick={() => setVisibleRowCount(TABLE_BATCH_SIZE)}
                      >
                        <ChevronUp size={15} />
                        {text('Show less', 'कम देखाउनुहोस्')}
                      </button>
                    )}
                    {visibleRowCount < rows.length && (
                      <button
                        type="button"
                        className="btn btn-secondary min-h-9 px-3"
                        onClick={() => setVisibleRowCount((count) => count + TABLE_BATCH_SIZE)}
                      >
                        {text('Show more', 'थप देखाउनुहोस्')}
                        <ChevronDown size={15} />
                      </button>
                    )}
                  </div>
                </div>
              )}
              <p className="border-t border-line px-5 py-4 hint">
                {text(
                  'Resolution rate = resolved ÷ total reports. Median time includes resolved reports with timestamps. Linked duplicates are excluded; other statuses include rejected reports.',
                  'समाधान दर = समाधान भएका ÷ कुल उजुरी। मध्यक समयमा समयसहितका समाधान भएका उजुरी पर्छन्। गाभिएका उजुरी समावेश छैनन्; अन्य स्थितिमा अस्वीकृत उजुरी पर्छन्।',
                )}
              </p>
            </section>
          </>
        )}
        <section className="flex flex-wrap items-center justify-between gap-5 rounded-xl bg-ink p-6 text-white sm:p-8">
          <div>
            <p className="max-w-xl text-base font-semibold text-mint sm:text-lg">
              {text(
                'Report an issue, follow its progress, and help local teams take action.',
                'समस्या दर्ता गर्नुहोस्, प्रगति हेर्नुहोस् र स्थानीय टोलीलाई सहयोग गर्नुहोस्।',
              )}
            </p>
          </div>
          <Link
            to={profile ? '/report' : '/register'}
            className="btn border-white/20 bg-white text-ink"
          >
            {profile ? t('nav.report') : t('auth.register')}
            <ArrowRight size={16} />
          </Link>
        </section>
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line py-4 hint">
          <span>
            © {new Date().getFullYear()} {t('app.name')}
          </span>
          <span className="flex flex-wrap items-center gap-2">
            <ShieldCheck size={14} />
            {text(
              'Public totals only. Personal report details stay private.',
              'सार्वजनिक तथ्याङ्क मात्र। व्यक्तिगत विवरण गोप्य रहन्छ।',
            )}
            <span aria-hidden="true">·</span>
            <InstallAppButton />
          </span>
        </footer>
      </main>
    </div>
  )
}
