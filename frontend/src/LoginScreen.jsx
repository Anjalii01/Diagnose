import React, { useState } from 'react'
import { useAuth } from './AuthContext.jsx'

export default function LoginScreen() {
  const { login, signup, verifyEmail, resendVerification } = useAuth()

  // 'login' | 'signup' | 'verify'
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [loading, setLoading] = useState(false)
  const [resending, setResending] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setInfo('')
    setLoading(true)
    try {
      if (mode === 'login') {
        await login(email, password)
      } else if (mode === 'signup') {
        await signup(email, password)
        // Backend does NOT log the user in on signup -- an email must be
        // verified first. Move to the "enter verification code" step.
        setMode('verify')
        setInfo(
          'Account created. Check your inbox for a 6-digit code (or the backend ' +
            'terminal, if SMTP is not configured yet) and enter it below.'
        )
      } else if (mode === 'verify') {
        await verifyEmail(email, code)
        // verifyEmail persists the token on success, so the app will now
        // switch to the logged-in view automatically.
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleResend = async () => {
    setError('')
    setInfo('')
    setResending(true)
    try {
      const data = await resendVerification(email)
      setInfo(data.message || 'If that account exists, a new code has been sent.')
    } catch (err) {
      setError(err.message)
    } finally {
      setResending(false)
    }
  }

  return (
    <div className="auth-screen">
      <div className="scanlines" />
      <div className="auth-card">
        <p className="brand-eyebrow">symptom analysis terminal</p>
        <h1 className="brand-title">
          diagnose<span className="blink" />
        </h1>
        <p className="auth-sub">
          {mode === 'login' && 'log in to view your diagnosis history'}
          {mode === 'signup' && 'create an account to get started'}
          {mode === 'verify' && `enter the 6-digit code sent to ${email}`}
        </p>

        <form onSubmit={submit}>
          {mode !== 'verify' && (
            <>
              <label className="auth-label">
                email
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                />
              </label>
              <label className="auth-label">
                password
                <input
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === 'signup' ? 'min 8 characters, 1 letter, 1 number' : '••••••••'}
                />
              </label>
            </>
          )}

          {mode === 'verify' && (
            <label className="auth-label">
              verification code
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                required
                autoFocus
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="123456"
              />
            </label>
          )}

          {error && <p className="error-msg">{error}</p>}
          {info && !error && <p className="auth-sub" style={{ color: 'var(--accent, #6cf)' }}>{info}</p>}

          <button className="run-btn" type="submit" disabled={loading}>
            {loading ? (
              <>
                <span className="spinner" />
                {mode === 'login' && 'logging in...'}
                {mode === 'signup' && 'creating account...'}
                {mode === 'verify' && 'verifying...'}
              </>
            ) : (
              <>
                {mode === 'login' && 'log in'}
                {mode === 'signup' && 'sign up'}
                {mode === 'verify' && 'verify & log in'}
              </>
            )}
          </button>
        </form>

        {mode === 'verify' && (
          <p className="auth-switch">
            didn't get a code?{' '}
            <button type="button" onClick={handleResend} disabled={resending}>
              {resending ? 'sending...' : 'resend code'}
            </button>
          </p>
        )}

        {mode !== 'verify' && (
          <p className="auth-switch">
            {mode === 'login' ? "don't have an account?" : 'already have an account?'}{' '}
            <button
              type="button"
              onClick={() => {
                setMode(mode === 'login' ? 'signup' : 'login')
                setError('')
                setInfo('')
              }}
            >
              {mode === 'login' ? 'sign up' : 'log in'}
            </button>
          </p>
        )}

        {mode === 'verify' && (
          <p className="auth-switch">
            <button
              type="button"
              onClick={() => {
                setMode('login')
                setError('')
                setInfo('')
                setCode('')
              }}
            >
              back to log in
            </button>
          </p>
        )}
      </div>
    </div>
  )
}
