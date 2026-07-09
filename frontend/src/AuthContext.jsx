import React, { createContext, useContext, useState, useCallback } from 'react'

const AuthContext = createContext(null)

const TOKEN_KEY = 'diagnose_token'
const USER_KEY = 'diagnose_user'

export function AuthProvider({ apiBase, children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  })

  const persist = (newToken, newUser) => {
    setToken(newToken)
    setUser(newUser)
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem(USER_KEY, JSON.stringify(newUser))
  }

  const signup = useCallback(
    async (email, password) => {
      const res = await fetch(`${apiBase}/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) {
        const message = Array.isArray(data.detail)
          ? data.detail.map((d) => d.msg).join(' ')
          : data.detail || 'Signup failed.'
        throw new Error(message)
      }
      persist(data.access_token, data.user)
    },
    [apiBase]
  )

  const login = useCallback(
    async (email, password) => {
      const res = await fetch(`${apiBase}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || 'Login failed.')
      }
      persist(data.access_token, data.user)
    },
    [apiBase]
  )

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  }, [])

  const authHeaders = useCallback(() => {
    return token ? { Authorization: `Bearer ${token}` } : {}
  }, [token])

  // If a protected request comes back 401, the token's invalid/expired — log out.
  const authFetch = useCallback(
    async (path, options = {}) => {
      const res = await fetch(`${apiBase}${path}`, {
        ...options,
        headers: { ...(options.headers || {}), ...authHeaders() },
      })
      if (res.status === 401) {
        logout()
      }
      return res
    },
    [apiBase, authHeaders, logout]
  )

  return (
    <AuthContext.Provider value={{ token, user, signup, login, logout, authHeaders, authFetch }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
