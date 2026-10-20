type Props = {
  email: string
  onClose: () => void
  onSignOut: () => void
}

export default function ProfileModal({ email, onClose, onSignOut }: Props) {
  return (
    <div className="auth-overlay" onClick={onClose}>
      <div className="auth-modal profile" onClick={(event) => event.stopPropagation()}>
        <div className="avatar-lg">{email.charAt(0).toUpperCase()}</div>
        <h3>Account</h3>
        <p className="profile-email">{email}</p>
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
