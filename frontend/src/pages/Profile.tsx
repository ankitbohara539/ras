import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Camera, Trash2, UserRound } from 'lucide-react'
import { Button, Card, ConfirmDialog, ErrorNote, Field, PageTitle, Spinner, SuccessNote } from '../components/ui'
import { ProfileAvatar } from '../components/ProfileAvatar'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import type { MunicipalityDetail, Ward } from '../lib/types'

export function ProfilePage() {
  const { profile, refresh } = useAuth()
  const input = useRef<HTMLInputElement>(null)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [municipalityId, setMunicipalityId] = useState<string>('')
  const [wardId, setWardId] = useState<string>('')
  const [municipalities, setMunicipalities] = useState<{ id: string; name_en: string }[]>([])
  const [municipality, setMunicipality] = useState<MunicipalityDetail | null>(null)
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!profile) return
    setName(profile.full_name ?? '')
    setEmail(profile.email)
    setMunicipalityId(profile.municipality_id ?? '')
    setWardId(profile.ward_id ?? '')
    void api.municipalities().then(setMunicipalities).catch(() => setMunicipalities([]))
    void api.myAvatar().then((result) => setAvatarUrl(result.url)).catch(() => setAvatarUrl(null))
  }, [profile])

  useEffect(() => {
    if (!municipalityId) {
      setMunicipality(null)
      return
    }
    let cancelled = false
    void api.municipality(municipalityId).then((result) => {
      if (!cancelled) setMunicipality(result)
    }).catch(() => {
      if (!cancelled) setMunicipality(null)
    })
    return () => { cancelled = true }
  }, [municipalityId])

  if (!profile) return <Spinner />
  const canChooseWard = profile.role === 'citizen'

  const save = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setMessage(null)
    if (name.trim().length < 2) {
      setError('Enter a name with at least two characters.')
      return
    }
    if (!email.includes('@')) {
      setError('Enter a valid email address.')
      return
    }
    setBusy(true)
    try {
      await api.updateMe({
        full_name: name.trim(),
        email: email.trim(),
        ...(canChooseWard ? { ward_id: wardId || null } : {}),
      })
      await refresh()
      setMessage('Profile updated successfully.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not update your profile.')
    } finally {
      setBusy(false)
    }
  }

  const upload = async (file: File | undefined) => {
    if (!file) return
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      await api.updateAvatar(file)
      const next = await api.myAvatar()
      setAvatarUrl(next.url)
      await refresh()
      setMessage('Profile photo updated successfully.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not upload the profile photo.')
    } finally {
      setBusy(false)
    }
  }

  const removeAvatar = async () => {
    setBusy(true)
    setError(null)
    try {
      await api.deleteAvatar()
      setAvatarUrl(null)
      await refresh()
      setMessage('Profile photo removed.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not remove the profile photo.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <PageTitle title="My profile" subtitle="Keep your contact details and home ward accurate." />
      {error && <ErrorNote message={error} />}
      {message && <SuccessNote>{message}</SuccessNote>}

      <Card>
        <div className="flex flex-wrap items-center gap-4">
          <ProfileAvatar name={profile.full_name} email={profile.email} url={avatarUrl} size="lg" />
          <div className="min-w-0 flex-1">
            <p className="font-semibold">Profile photo</p>
            <p className="hint">JPG, PNG, WebP, or HEIC up to 8 MB.</p>
            <input ref={input} className="sr-only" type="file" accept="image/jpeg,image/png,image/webp,image/heic" onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ''; void upload(file) }} />
            <div className="mt-3 flex flex-wrap gap-2">
              <Button type="button" variant="secondary" disabled={busy} onClick={() => input.current?.click()}><Camera size={16} /> Change photo</Button>
              {avatarUrl && <ConfirmDialog destructive trigger={<Button type="button" variant="danger" disabled={busy}><Trash2 size={16} /> Remove</Button>} title="Remove profile photo?" description="Your current photo will be permanently removed." confirmLabel="Remove photo" onConfirm={removeAvatar} />}
            </div>
          </div>
        </div>
      </Card>

      <form onSubmit={save} className="space-y-4">
        <Card className="space-y-4">
          <div className="flex items-center gap-2"><UserRound size={18} className="text-brand" /><h2 className="font-semibold">Account details</h2></div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Full name" required><input className="field" value={name} minLength={2} maxLength={160} onChange={(event) => setName(event.target.value)} required /></Field>
            <Field label="Email address" hint="Changing it may require verification through your email provider." required><input className="field" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></Field>
          </div>
        </Card>

        <Card className="space-y-4">
          <h2 className="font-semibold">Home ward</h2>
          {canChooseWard ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Municipality"><select className="field" value={municipalityId} onChange={(event) => { setMunicipalityId(event.target.value); setWardId('') }}><option value="">Choose municipality</option>{municipalities.map((item) => <option key={item.id} value={item.id}>{item.name_en}</option>)}</select></Field>
              <Field label="Ward"><select className="field" value={wardId} disabled={!municipality} onChange={(event) => setWardId(event.target.value)}><option value="">Choose ward</option>{municipality?.wards.map((ward: Ward) => <option key={ward.id} value={ward.id}>Ward {ward.number}{ward.name_en ? ` — ${ward.name_en}` : ''}</option>)}</select></Field>
            </div>
          ) : <p className="hint">Your authority ward controls access to municipal data. Ask an administrator to update it.</p>}
        </Card>
        <Button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save changes'}</Button>
      </form>
    </div>
  )
}
