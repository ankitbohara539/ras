import { useCallback, useEffect, useMemo, useState } from 'react'
import { Eye, Pencil, Search, ShieldAlert, Trash2 } from 'lucide-react'
import { Button, Card, ConfirmDialog, EmptyState, ErrorNote, Field, Modal, PageTitle, Spinner, SuccessNote } from '../../components/ui'
import { ProfileAvatar } from '../../components/ProfileAvatar'
import { api } from '../../lib/api'
import type { AdminProfileDetail, Profile, UserRole } from '../../lib/types'

const ROLES: UserRole[] = ['citizen', 'authority', 'admin']
const STATUSES: Profile['account_status'][] = ['active', 'pending', 'rejected', 'suspended']

export function UserManagement() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [wards, setWards] = useState<{ id: string; number: number; name_en: string | null }[]>([])
  const [search, setSearch] = useState('')
  const [role, setRole] = useState('')
  const [accountStatus, setAccountStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [selected, setSelected] = useState<AdminProfileDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [editing, setEditing] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [users, wardRows] = await Promise.all([
        api.allProfiles({ role: role || undefined, account_status: accountStatus || undefined, search: search.trim() || undefined }),
        api.wards(),
      ])
      setProfiles(users.items)
      setWards(wardRows)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load users.')
    } finally {
      setLoading(false)
    }
  }, [accountStatus, role, search])

  useEffect(() => { void load() }, [load])

  const wardName = useMemo(() => new Map(wards.map((ward) => [ward.id, `Ward ${ward.number}${ward.name_en ? ` — ${ward.name_en}` : ''}`])), [wards])
  const openDetail = async (id: string) => {
    setDetailLoading(true)
    setError(null)
    try { setSelected(await api.adminProfile(id)) } catch (err) { setError(err instanceof Error ? err.message : 'Could not load this user.') } finally { setDetailLoading(false) }
  }

  const save = async (profile: Profile, patch: Partial<Profile>) => {
    setBusy(profile.id)
    setError(null)
    try {
      const updated = await api.updateProfile(profile.id, patch)
      setSelected((current) => current ? { ...current, profile: updated } : current)
      setEditing(false)
      setNotice('User updated successfully.')
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update the user.')
    } finally { setBusy(null) }
  }

  const remove = async (profile: Profile) => {
    setBusy(profile.id)
    setError(null)
    try {
      await api.deleteProfile(profile.id)
      setSelected(null)
      setNotice('User account deleted.')
      await load()
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not delete the user.') } finally { setBusy(null) }
  }

  return (
    <div className="space-y-5">
      <PageTitle title="User management" subtitle="Search, review, and safely manage every account and its submitted content." />
      {error && <ErrorNote message={error} />}
      {notice && <SuccessNote>{notice}</SuccessNote>}
      <Card>
        <div className="grid gap-3 md:grid-cols-[1fr_180px_180px_auto]">
          <label className="relative"><Search size={17} className="absolute left-3 top-3.5 text-ink-faint" /><input className="field pl-10" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search name, email, or ward…" /></label>
          <select className="field" value={role} onChange={(event) => setRole(event.target.value)}><option value="">All roles</option>{ROLES.map((value) => <option key={value} value={value}>{value}</option>)}</select>
          <select className="field" value={accountStatus} onChange={(event) => setAccountStatus(event.target.value)}><option value="">All statuses</option>{STATUSES.map((value) => <option key={value} value={value}>{value}</option>)}</select>
          <Button type="button" variant="secondary" onClick={() => void load()}>Search</Button>
        </div>
      </Card>

      {loading ? <Spinner /> : profiles.length === 0 ? <EmptyState title="No users match these filters." /> : (
        <div className="overflow-hidden rounded-xl border border-line bg-surface">
          <div className="hidden grid-cols-[minmax(0,1.4fr)_160px_150px_170px_100px] gap-3 border-b border-line bg-canvas px-4 py-3 text-xs font-semibold uppercase tracking-wide text-ink-soft lg:grid"><span>User</span><span>Role</span><span>Status</span><span>Ward</span><span>Actions</span></div>
          {profiles.map((profile) => (
            <div key={profile.id} className="grid gap-3 border-b border-line px-4 py-4 last:border-0 lg:grid-cols-[minmax(0,1.4fr)_160px_150px_170px_100px] lg:items-center">
              <div className="flex min-w-0 items-center gap-3">
                <ProfileAvatar name={profile.full_name} email={profile.email} url={profile.avatar_url} size="sm" />
                <div className="min-w-0"><p className="truncate font-semibold">{profile.full_name || 'Unnamed user'}</p><p className="truncate hint">{profile.email}</p></div>
              </div>
              <span className="chip w-fit border-line bg-canvas capitalize">{profile.role}</span>
              <span className={`chip w-fit capitalize ${profile.account_status === 'active' ? 'border-good bg-good-soft text-good' : profile.account_status === 'suspended' ? 'border-danger bg-danger-soft text-danger' : 'border-warn bg-warn-soft text-warn'}`}>{profile.account_status}</span>
              <span className="hint">{profile.ward_id ? wardName.get(profile.ward_id) ?? 'Assigned ward' : 'Not assigned'}</span>
              <Button type="button" size="sm" variant="secondary" onClick={() => void openDetail(profile.id)}><Eye size={15} /> View</Button>
            </div>
          ))}
        </div>
      )}

      {detailLoading && <Spinner label="Loading user details…" />}
      {selected && <UserDetail detail={selected} wards={wards} busy={busy === selected.profile.id} editing={editing} onClose={() => { setSelected(null); setEditing(false) }} onEdit={() => setEditing(true)} onSave={save} onDeactivate={() => void save(selected.profile, { account_status: selected.profile.account_status === 'active' ? 'suspended' : 'active' })} onDelete={() => remove(selected.profile)} />}
    </div>
  )
}

function UserDetail({ detail, wards, busy, editing, onClose, onEdit, onSave, onDeactivate, onDelete }: { detail: AdminProfileDetail; wards: { id: string; number: number; name_en: string | null }[]; busy: boolean; editing: boolean; onClose: () => void; onEdit: () => void; onSave: (profile: Profile, patch: Partial<Profile>) => Promise<void>; onDeactivate: () => void; onDelete: () => void }) {
  const profile = detail.profile
  const [name, setName] = useState(profile.full_name ?? '')
  const [email, setEmail] = useState(profile.email)
  const [role, setRole] = useState<Profile['role']>(profile.role)
  const [status, setStatus] = useState<Profile['account_status']>(profile.account_status)
  const [wardId, setWardId] = useState(profile.ward_id ?? '')
  const ward = wards.find((item) => item.id === profile.ward_id)
  const wardLabel = ward ? `Ward ${ward.number}${ward.name_en ? ` — ${ward.name_en}` : ''}` : 'Not assigned'
  const submit = async () => {
    if (name.trim().length < 2 || !email.includes('@')) return
    await onSave(profile, { full_name: name.trim(), email: email.trim(), role, account_status: status, ward_id: wardId || null })
  }
  return <Modal title="User profile" onClose={onClose} footer={<><Button type="button" variant="secondary" onClick={onClose}>Close</Button>{editing ? <Button type="button" disabled={busy || name.trim().length < 2 || !email.includes('@')} onClick={() => void submit()}>{busy ? 'Saving…' : 'Save changes'}</Button> : <Button type="button" onClick={onEdit}><Pencil size={16} /> Edit user</Button>}</>}>
    <div className="space-y-4">
      {editing ? <div className="grid gap-3 sm:grid-cols-2"><Field label="Name" required><input className="field" value={name} onChange={(event) => setName(event.target.value)} /></Field><Field label="Email" required><input className="field" type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></Field><Field label="Role"><select className="field" value={role} onChange={(event) => setRole(event.target.value as Profile['role'])}>{ROLES.map((value) => <option key={value} value={value}>{value}</option>)}</select></Field><Field label="Account status"><select className="field" value={status} onChange={(event) => setStatus(event.target.value as Profile['account_status'])}>{STATUSES.map((value) => <option key={value} value={value}>{value}</option>)}</select></Field><Field label="Assigned ward"><select className="field" value={wardId} onChange={(event) => setWardId(event.target.value)}><option value="">Municipality-wide / none</option>{wards.map((ward) => <option key={ward.id} value={ward.id}>Ward {ward.number}{ward.name_en ? ` — ${ward.name_en}` : ''}</option>)}</select></Field></div> : <><div className="rounded-xl border border-line bg-canvas p-4"><div className="flex items-center gap-4"><ProfileAvatar name={profile.full_name} email={profile.email} url={profile.avatar_url} size="lg" /><div className="min-w-0 flex-1"><p className="truncate text-lg font-semibold">{profile.full_name || 'Unnamed user'}</p><p className="truncate hint">{profile.email}</p><div className="mt-2 flex flex-wrap gap-2"><span className="chip border-line bg-surface capitalize">{profile.role}</span><span className={`chip capitalize ${profile.account_status === 'active' ? 'border-good bg-good-soft text-good' : profile.account_status === 'suspended' ? 'border-danger bg-danger-soft text-danger' : 'border-warn bg-warn-soft text-warn'}`}>{profile.account_status}</span></div></div></div></div><div className="grid gap-3 text-sm sm:grid-cols-2"><p><span className="hint">Assigned ward</span><br /><span className="font-medium">{wardLabel}</span></p><p><span className="hint">Phone</span><br /><span className="font-medium">{profile.phone || 'Not provided'}</span></p></div></>}
      <div><h3 className="font-semibold">Submitted reports ({detail.reports.length})</h3>{detail.reports.length ? <div className="mt-2 space-y-2">{detail.reports.map((item) => <div key={item.id} className="rounded-lg bg-canvas p-3 text-sm"><span className="font-mono font-semibold">{item.code}</span><p>{item.title}</p><p className="hint">{item.status} · {new Date(item.created_at).toLocaleDateString()}</p></div>)}</div> : <p className="mt-1 hint">No reports submitted.</p>}</div>
      <div><h3 className="font-semibold">Civic-sense content ({detail.civic_complaints.length})</h3>{detail.civic_complaints.length ? <div className="mt-2 space-y-2">{detail.civic_complaints.map((item) => <div key={item.id} className="rounded-lg bg-canvas p-3 text-sm"><span className="font-mono font-semibold">{item.code}</span><p>{item.description}</p><p className="hint">{item.status} · {new Date(item.created_at).toLocaleDateString()}</p></div>)}</div> : <p className="mt-1 hint">No civic-sense content submitted.</p>}</div>
      {!editing && <div className="flex flex-wrap gap-2 border-t border-line pt-4"><ConfirmDialog trigger={<Button type="button" variant="secondary" disabled={busy}><ShieldAlert size={16} /> {profile.account_status === 'active' ? 'Deactivate' : 'Activate'}</Button>} title={`${profile.account_status === 'active' ? 'Deactivate' : 'Activate'} this account?`} description="The user will immediately gain or lose sign-in access." confirmLabel={profile.account_status === 'active' ? 'Deactivate account' : 'Activate account'} onConfirm={onDeactivate} /><ConfirmDialog destructive trigger={<Button type="button" variant="danger" disabled={busy}><Trash2 size={16} /> Delete account</Button>} title="Delete this account?" description="This permanently deletes the account and its submitted content." confirmLabel="Delete account" onConfirm={onDelete} /></div>}
    </div>
  </Modal>
}
