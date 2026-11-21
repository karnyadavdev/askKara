import { useRef, useState } from 'react'
import { useUpdateProfileMutation, useUploadAvatarMutation } from '../features/authApi'
import { avatarErrorMessage } from '../features/avatarErrors'

type Props = {
  email: string
  name: string | null
  avatarUrl: string | null
  onClose: () => void
  onSignOut: () => void
}

export default function ProfileModal({ email, name, avatarUrl, onClose, onSignOut }: Props) {
  const [draft, setDraft] = useState(name ?? '')
  const [status, setStatus] = useState('')
  const [saveProfile, saveState] = useUpdateProfileMutation()
  const [uploadAvatar, uploadState] = useUploadAvatarMutation()
  const fileRef = useRef<HTMLInputElement>(null)
  const busy = saveState.isLoading || uploadState.isLoading
  const initial = (name || email || '?').charAt(0).toUpperCase()
  const dirty = draft.trim() !== (name ?? '')

  async function save() {
    const trimmed = draft.trim()
    if (!trimmed || busy) return
    setStatus('')
    try {
      await saveProfile(trimmed).unwrap()
      setStatus('Name saved.')
    } catch {
      setStatus('Could not save that name.')
    }
  }

  async function pickPicture(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setStatus('')
    const form = new FormData()
    form.append('file', file)
    try {
      await uploadAvatar(form).unwrap()
      setStatus('Picture updated.')
    } catch (error) {
      setStatus(avatarErrorMessage(error))
    }
  }

  return (
    <div className="auth-overlay" onClick={onClose}>
      <div className="auth-modal profile" onClick={(event) => event.stopPropagation()}>
        <button
          type="button"
          className="avatar-lg avatar-pick"
          onClick={() => fileRef.current?.click()}
          aria-label="Change picture"
          title="Change picture"
        >
          {avatarUrl ? <img src={avatarUrl} alt="" /> : initial}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="avatar-file"
          onChange={pickPicture}
        />
        <h3>{name || 'Account'}</h3>
        <p className="profile-email">{email}</p>
        <div className="profile-name-row">
          <input
            type="text"
            maxLength={100}
            placeholder="Your name"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') save()
            }}
          />
          <button
            type="button"
            className="auth-submit profile-save"
            onClick={save}
            disabled={busy || !dirty || !draft.trim()}
          >
            {busy ? 'Saving...' : 'Save'}
          </button>
        </div>
        {status ? <p className="auth-hint">{status}</p> : null}
        <button type="button" className="auth-submit" onClick={onSignOut}>
          Sign out
        </button>
        <button type="button" className="auth-switch" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  )
}
