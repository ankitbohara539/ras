import { useCallback, useEffect, useState } from 'react'
import { ClipboardList, Eye, Search, UsersRound } from 'lucide-react'
import { Button, Card, EmptyState, ErrorNote, Modal, PageTitle, Spinner, StatusBadge } from '../../components/ui'
import { api } from '../../lib/api'
import type { Profile, TicketSummary } from '../../lib/types'

export function WardPeople() {
  const [people, setPeople] = useState<Profile[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Profile | null>(null)
  const [reports, setReports] = useState<TicketSummary[] | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try { setPeople((await api.wardCivilians({ search: search.trim() || undefined, limit: 200 })).items) } catch (err) { setError(err instanceof Error ? err.message : 'Could not load civilians.') } finally { setLoading(false) }
  }, [search])
  useEffect(() => { const timer = window.setTimeout(() => void load(), 250); return () => window.clearTimeout(timer) }, [load])
  const view = async (person: Profile) => {
    setSelected(person); setReports(null)
    try { setReports((await api.tickets({ reporter_id: person.id, limit: 100, parents_only: false })).items) } catch (err) { setError(err instanceof Error ? err.message : 'Could not load the civilian reports.'); setReports([]) }
  }
  return <div className="space-y-5">
    <PageTitle title="Ward civilians" subtitle="Profiles and reports are limited to your assigned ward. You cannot access residents from another ward." />
    {error && <ErrorNote message={error} />}
    <Card><label className="relative block"><Search size={17} className="absolute left-3 top-3.5 text-ink-faint" /><input className="field pl-10" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search civilian name or email…" /></label></Card>
    {loading ? <Spinner /> : people.length === 0 ? <EmptyState title="No civilians found in your assigned ward." /> : <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{people.map((person) => <Card key={person.id} className="space-y-3"><div className="flex items-center gap-3"><span className="icon-tile"><UsersRound size={17} /></span><div className="min-w-0"><p className="truncate font-semibold">{person.full_name || 'Unnamed resident'}</p><p className="truncate hint">{person.email}</p></div></div><Button type="button" variant="secondary" className="w-full" onClick={() => void view(person)}><Eye size={16} /> View reports</Button></Card>)}</div>}
    {selected && <Modal title={selected.full_name || selected.email} onClose={() => { setSelected(null); setReports(null) }} footer={<Button type="button" variant="secondary" onClick={() => { setSelected(null); setReports(null) }}>Close</Button>}><p className="hint">{selected.email}</p><h3 className="mt-4 flex items-center gap-2 font-semibold"><ClipboardList size={17} /> Ward reports</h3>{reports === null ? <Spinner label="Loading reports…" /> : reports.length === 0 ? <p className="mt-2 hint">This resident has not submitted a report in your ward.</p> : <div className="mt-3 space-y-2">{reports.map((report) => <div key={report.id} className="rounded-lg bg-canvas p-3"><div className="flex flex-wrap items-center gap-2"><span className="font-mono text-sm font-semibold">{report.public_code}</span><StatusBadge status={report.status} /></div><p className="mt-1 font-medium">{report.title}</p><p className="line-clamp-2 hint">{report.description}</p></div>)}</div>}</Modal>}
  </div>
}
