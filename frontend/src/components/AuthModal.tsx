import { useState } from 'react'
import { useLoginMutation, useRegisterMutation } from '../features/authApi'

type Props = {
  onClose: () => void
  onAuth: (token: string) => void
}

export default function AuthModal({ onClose, onAuth }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [login, loginState] = useLoginMutation()
  const [register, registerState] = useRegisterMutation()
  const busy = loginState.isLoading || registerState.isLoading

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setError('')
    try {
      const mutation = mode === 'login' ? login : register
      const result = await mutation({ email, password }).unwrap()
      onAuth(result.access_token)
    } catch {
      setError(mode === 'login' ? 'Invalid email or password' : 'Could not register that email')
    }
  }

  return (
    <div className="auth-overlay" onClick={onClose}>
      <form className="auth-modal" onClick={(event) => event.stopPropagation()} onSubmit={submit}>
        <h3>{mode === 'login' ? 'Sign in' : 'Create account'}</h3>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
        {error ? <p className="auth-error">{error}</p> : null}
        <button type="submit" className="auth-submit" disabled={busy}>
          {busy ? 'Working...' : mode === 'login' ? 'Sign in' : 'Register'}
        </button>
        <button type="button" className="auth-switch" onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
          {mode === 'login' ? 'New user?' : 'Existing user?'}
        </button>
      </form>
    </div>
  )
}
