import { useEffect, useRef, useState } from 'react'
import { useUpdateProfileMutation, useUploadAvatarMutation } from '../features/authApi'
import { avatarErrorMessage } from '../features/avatarErrors'

type Props = {
  email: string
  name: string | null
  avatarUrl: string | null
  onClose: () => void
  onSignOut: () => void
}

const pencil = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
  </svg>
)

export default function ProfileModal({ email, name, avatarUrl, onClose, onSignOut }: Props) {
  const [draft, setDraft] = useState(name ?? '')
  const [editing, setEditing] = useState(false)
  const [status, setStatus] = useState('')
  const [saveProfile, saveState] = useUpdateProfileMutation()
  const [uploadAvatar, uploadState] = useUploadAvatarMutation()
  const fileRef = useRef<HTMLInputElement>(null)
  const nameRef = useRef<HTMLInputElement>(null)
  const busy = saveState.isLoading || uploadState.isLoading
  const initial = (name || email || '?').charAt(0).toUpperCase()

  useEffect(() => {
    if (editing) nameRef.current?.select()
  }, [editing])

  async function save() {
    const trimmed = draft.trim()
    if (!trimmed || busy) return
    setStatus('')
    try {
      await saveProfile(trimmed).unwrap()
      setEditing(false)
      setStatus('Name saved.')
    } catch {
      setStatus('Could not save that name.')
    }
  }

  function cancel() {
    setDraft(name ?? '')
    setEditing(false)
    setStatus('')
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
          <span className="avatar-edit-icon" aria-hidden="true">{pencil}</span>
        </button>
        <input
          ref={fileRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="avatar-file"
          onChange={pickPicture}
        />
        {editing ? (
          <div className="profile-name-edit-row">
            <input
              ref={nameRef}
              type="text"
              maxLength={100}
              placeholder="Your name"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void save()
                if (event.key === 'Escape') cancel()
              }}
            />
            <button
              type="button"
              className="profile-name-confirm"
              onClick={() => void save()}
              disabled={busy || !draft.trim()}
            >
              Save
            </button>
          </div>
        ) : (
          <h3 className="profile-name-display">
            <span>{name || 'Account'}</span>
            <button
              type="button"
              className="profile-name-edit"
              aria-label="Edit name"
              title="Edit name"
              onClick={() => setEditing(true)}
            >
              {pencil}
            </button>
          </h3>
        )}
        <p className="profile-email">{email}</p>
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
