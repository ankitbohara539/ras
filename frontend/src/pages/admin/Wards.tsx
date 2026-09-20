import { useCallback, useEffect, useState } from 'react'
import { MapPinned, Pencil, Plus, Search, Trash2, Users } from 'lucide-react'
import { Button, Card, ConfirmDialog, EmptyState, ErrorNote, Field, Modal, PageTitle, Spinner, SuccessNote } from '../../components/ui'
import { api } from '../../lib/api'
import type { ManagedWard, Municipality, WardDetail } from '../../lib/types'

type WardForm = { municipality_id: string; number: string; name_en: string; name_ne: string; centroid_lat: string; centroid_lon: string }
const blank: WardForm = { municipality_id: '', number: '', name_en: '', name_ne: '', centroid_lat: '', centroid_lon: '' }

export function WardManagement() {
  const [wards, setWards] = useState<ManagedWard[]>([])
  const [municipalities, setMunicipalities] = useState<Municipality[]>([])
  const [search, setSearch] = useState('')
  const [municipalityId, setMunicipalityId] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [form, setForm] = useState<WardForm | null>(null)
  const [selected, setSelected] = useState<WardDetail | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [rows, municipalities] = await Promise.all([api.wards({ municipality_id: municipalityId || undefined, search: search.trim() || undefined }), api.municipalities()])
      setWards(rows)
      setMunicipalities(municipalities)
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not load wards.') } finally { setLoading(false) }
  }, [municipalityId, search])
  useEffect(() => { void load() }, [load])

  const openDetail = async (id: string) => {
    setError(null)
    try { setSelected(await api.ward(id)) } catch (err) { setError(err instanceof Error ? err.message : 'Could not load ward details.') }
  }
  const startEdit = (ward: ManagedWard) => setForm({ municipality_id: ward.municipality_id, number: String(ward.number), name_en: ward.name_en ?? '', name_ne: ward.name_ne ?? '', centroid_lat: String(ward.centroid_lat), centroid_lon: String(ward.centroid_lon) })
  const updateForm = (key: keyof WardForm, value: string) => setForm((current) => current ? { ...current, [key]: value } : current)
  const valid = form && form.municipality_id && Number(form.number) > 0 && Number.isFinite(Number(form.centroid_lat)) && Number.isFinite(Number(form.centroid_lon))

  const save = async () => {
    if (!form || !valid) return
    setBusy(true); setError(null)
    const payload = { municipality_id: form.municipality_id, number: Number(form.number), name_en: form.name_en.trim() || null, name_ne: form.name_ne.trim() || null, centroid_lat: Number(form.centroid_lat), centroid_lon: Number(form.centroid_lon) }
    try {
      const existing = selected && selected.id
      if (existing) await api.updateWard(existing, { number: payload.number, name_en: payload.name_en, name_ne: payload.name_ne, centroid_lat: payload.centroid_lat, centroid_lon: payload.centroid_lon })
      else await api.createWard(payload)
      setForm(null); setSelected(null); setNotice(existing ? 'Ward updated successfully.' : 'Ward created successfully.'); await load()
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not save the ward.') } finally { setBusy(false) }
  }
  const remove = async (ward: ManagedWard | WardDetail) => {
    setBusy(true); setError(null)
    try { await api.deleteWard(ward.id); setSelected(null); setNotice('Ward deleted.'); await load() } catch (err) { setError(err instanceof Error ? err.message : 'Could not delete the ward.') } finally { setBusy(false) }
  }

  return <div className="space-y-5">
    <PageTitle title="Ward management" subtitle="Maintain ward records and see the civilians, authorities, and reports assigned to each ward." action={<Button type="button" onClick={() => { setSelected(null); setForm(blank) }}><Plus size={16} /> Add ward</Button>} />
    {error && <ErrorNote message={error} />}{notice && <SuccessNote>{notice}</SuccessNote>}
    <Card><div className="grid gap-3 md:grid-cols-[1fr_240px_auto]"><label className="relative"><Search size={17} className="absolute left-3 top-3.5 text-ink-faint" /><input className="field pl-10" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search ward name or number…" /></label><select className="field" value={municipalityId} onChange={(event) => setMunicipalityId(event.target.value)}><option value="">All municipalities</option>{municipalities.map((item) => <option key={item.id} value={item.id}>{item.name_en}</option>)}</select><Button type="button" variant="secondary" onClick={() => void load()}>Search</Button></div></Card>
    {loading ? <Spinner /> : wards.length === 0 ? <EmptyState title="No wards match these filters." /> : <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{wards.map((ward) => <Card key={ward.id} className="space-y-3"><div className="flex items-start justify-between gap-2"><div><p className="font-semibold">Ward {ward.number}</p><p className="hint">{ward.name_en || 'Unnamed ward'}</p></div><MapPinned className="text-brand" size={20} /></div><div className="grid grid-cols-3 gap-2 text-center text-sm"><span><b>{ward.civilian_count}</b><br /><small className="hint">citizens</small></span><span><b>{ward.authority_count}</b><br /><small className="hint">authorities</small></span><span><b>{ward.report_count}</b><br /><small className="hint">reports</small></span></div><Button type="button" variant="secondary" className="w-full" onClick={() => void openDetail(ward.id)}>View ward</Button></Card>)}</div>}
    {form && <WardEditor form={form} municipalities={municipalities} busy={busy} isEditing={Boolean(selected)} onChange={updateForm} onClose={() => setForm(null)} onSave={() => void save()} />}
    {selected && !form && <WardDetailPanel ward={selected} busy={busy} onClose={() => setSelected(null)} onEdit={() => startEdit(selected)} onDelete={() => remove(selected)} />}
  </div>
}

function WardEditor({ form, municipalities, busy, isEditing, onChange, onClose, onSave }: { form: WardForm; municipalities: Municipality[]; busy: boolean; isEditing: boolean; onChange: (key: keyof WardForm, value: string) => void; onClose: () => void; onSave: () => void }) {
  const valid = form.municipality_id && Number(form.number) > 0 && Number.isFinite(Number(form.centroid_lat)) && Number.isFinite(Number(form.centroid_lon))
  return <Modal title={isEditing ? 'Edit ward' : 'Add ward'} onClose={onClose} footer={<><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="button" disabled={busy || !valid} onClick={onSave}>{busy ? 'Saving…' : 'Save ward'}</Button></>}><div className="grid gap-3 sm:grid-cols-2"><Field label="Municipality" required><select className="field" value={form.municipality_id} disabled={isEditing} onChange={(event) => onChange('municipality_id', event.target.value)}><option value="">Choose municipality</option>{municipalities.map((item) => <option key={item.id} value={item.id}>{item.name_en}</option>)}</select></Field><Field label="Ward number" required><input className="field" type="number" min="1" value={form.number} onChange={(event) => onChange('number', event.target.value)} /></Field><Field label="Name (English)"><input className="field" maxLength={120} value={form.name_en} onChange={(event) => onChange('name_en', event.target.value)} /></Field><Field label="Name (Nepali)"><input className="field" maxLength={120} value={form.name_ne} onChange={(event) => onChange('name_ne', event.target.value)} /></Field><Field label="Centroid latitude" required><input className="field" type="number" step="any" value={form.centroid_lat} onChange={(event) => onChange('centroid_lat', event.target.value)} /></Field><Field label="Centroid longitude" required><input className="field" type="number" step="any" value={form.centroid_lon} onChange={(event) => onChange('centroid_lon', event.target.value)} /></Field></div></Modal>
}

function WardDetailPanel({ ward, busy, onClose, onEdit, onDelete }: { ward: WardDetail; busy: boolean; onClose: () => void; onEdit: () => void; onDelete: () => void }) {
  return <Modal title={`Ward ${ward.number}`} onClose={onClose} footer={<><Button type="button" variant="secondary" onClick={onClose}>Close</Button><Button type="button" variant="secondary" onClick={onEdit}><Pencil size={16} /> Edit</Button><ConfirmDialog destructive trigger={<Button type="button" variant="danger" disabled={busy}><Trash2 size={16} /> Delete</Button>} title="Delete this ward?" description="Deletion is allowed only after all users and content are moved elsewhere." confirmLabel="Delete ward" onConfirm={onDelete} /></>}><div className="space-y-4"><div className="grid grid-cols-3 gap-3 text-center"><Card><b>{ward.civilian_count}</b><p className="hint">Citizens</p></Card><Card><b>{ward.authority_count}</b><p className="hint">Authorities</p></Card><Card><b>{ward.report_count}</b><p className="hint">Reports</p></Card></div><div><h3 className="flex items-center gap-2 font-semibold"><Users size={17} /> Assigned civilians</h3>{ward.civilians.length ? <div className="mt-2 space-y-2">{ward.civilians.map((person) => <div key={person.id} className="rounded-lg bg-canvas p-3"><p className="font-medium">{person.full_name || 'Unnamed user'}</p><p className="hint">{person.email}</p></div>)}</div> : <p className="mt-2 hint">No civilians are assigned to this ward.</p>}</div></div></Modal>
}
