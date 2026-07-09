import React, { useEffect, useState, useCallback } from 'react'
import { useAuth } from './AuthContext.jsx'

const PAGE_SIZE = 10

export default function AdminPanel() {
  const { authFetch } = useAuth()
  const [stats, setStats] = useState(null)
  const [view, setView] = useState('users') // 'users' | 'predictions'

  const [users, setUsers] = useState([])
  const [usersTotal, setUsersTotal] = useState(0)
  const [usersPage, setUsersPage] = useState(0)
  const [userSearch, setUserSearch] = useState('')

  const [preds, setPreds] = useState([])
  const [predsTotal, setPredsTotal] = useState(0)
  const [predsPage, setPredsPage] = useState(0)
  const [predSearch, setPredSearch] = useState('')
  const [predUserFilter, setPredUserFilter] = useState('')

  const [loading, setLoading] = useState(false)

  useEffect(() => {
    authFetch('/admin/stats')
      .then((r) => r.json())
      .then(setStats)
      .catch(() => {})
  }, [authFetch])

  const loadUsers = useCallback(
    (page) => {
      setLoading(true)
      const params = new URLSearchParams()
      if (userSearch.trim()) params.set('search', userSearch.trim())
      params.set('skip', page * PAGE_SIZE)
      params.set('limit', PAGE_SIZE)
      authFetch(`/admin/users?${params.toString()}`)
        .then((r) => r.json())
        .then((data) => {
          setUsers(data.items || [])
          setUsersTotal(data.total || 0)
          setUsersPage(page)
        })
        .finally(() => setLoading(false))
    },
    [authFetch, userSearch]
  )

  const loadPreds = useCallback(
    (page) => {
      setLoading(true)
      const params = new URLSearchParams()
      if (predSearch.trim()) params.set('search', predSearch.trim())
      if (predUserFilter.trim()) params.set('user_email', predUserFilter.trim())
      params.set('skip', page * PAGE_SIZE)
      params.set('limit', PAGE_SIZE)
      authFetch(`/admin/predictions?${params.toString()}`)
        .then((r) => r.json())
        .then((data) => {
          setPreds(data.items || [])
          setPredsTotal(data.total || 0)
          setPredsPage(page)
        })
        .finally(() => setLoading(false))
    },
    [authFetch, predSearch, predUserFilter]
  )

  useEffect(() => {
    if (view === 'users') loadUsers(0)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, userSearch])

  useEffect(() => {
    if (view === 'predictions') loadPreds(0)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, predSearch, predUserFilter])

  const usersTotalPages = Math.max(1, Math.ceil(usersTotal / PAGE_SIZE))
  const predsTotalPages = Math.max(1, Math.ceil(predsTotal / PAGE_SIZE))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {stats && (
        <div className="stat-grid">
          <div className="stat-card">
            <p className="stat-label">total users</p>
            <p className="stat-value">{stats.total_users}</p>
            <p className="stat-sub">+{stats.new_users_last_7_days} this week</p>
          </div>
          <div className="stat-card">
            <p className="stat-label">total diagnoses run</p>
            <p className="stat-value">{stats.total_predictions}</p>
            <p className="stat-sub">+{stats.predictions_last_7_days} this week</p>
          </div>
          <div className="stat-card wide">
            <p className="stat-label">most predicted conditions</p>
            <div className="top-disease-list">
              {stats.top_diseases.map((d) => (
                <div className="top-disease-row" key={d.disease}>
                  <span>{d.disease}</span>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{
                        width: `${(d.count / stats.top_diseases[0].count) * 100}%`,
                      }}
                    />
                  </div>
                  <span className="bar-count">{d.count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="panel">
        <div className="panel-head">
          <h2>admin dashboard</h2>
        </div>
        <div className="panel-body">
          <div className="tab-bar" style={{ marginBottom: 18 }}>
            <button className={view === 'users' ? 'active' : ''} onClick={() => setView('users')}>
              users
            </button>
            <button className={view === 'predictions' ? 'active' : ''} onClick={() => setView('predictions')}>
              all diagnoses
            </button>
          </div>

          {view === 'users' && (
            <>
              <div className="search-box" style={{ marginBottom: 16 }}>
                <input
                  placeholder="search by email..."
                  value={userSearch}
                  onChange={(e) => setUserSearch(e.target.value)}
                />
              </div>
              <div className="history-table">
                {loading && <p className="empty-state">loading...</p>}
                {!loading && users.length === 0 && (
                  <p className="empty-state">no users match.</p>
                )}
                {!loading &&
                  users.map((u) => (
                    <div className="history-row" key={u.id}>
                      <div>
                        <div className="history-disease">
                          {u.email}
                          {u.is_admin && <span className="confidence-badge">admin</span>}
                        </div>
                        <div className="history-meta">
                          {u.prediction_count} diagnoses · joined {new Date(u.created_at).toLocaleDateString()}
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
              {usersTotalPages > 1 && (
                <div className="pagination">
                  <button disabled={usersPage === 0} onClick={() => loadUsers(usersPage - 1)}>
                    prev
                  </button>
                  <span>
                    page {usersPage + 1} / {usersTotalPages}
                  </span>
                  <button disabled={usersPage >= usersTotalPages - 1} onClick={() => loadUsers(usersPage + 1)}>
                    next
                  </button>
                </div>
              )}
            </>
          )}

          {view === 'predictions' && (
            <>
              <div className="history-toolbar" style={{ borderBottom: 'none', marginBottom: 0 }}>
                <div className="search-box" style={{ margin: 0 }}>
                  <input
                    placeholder="search by disease..."
                    value={predSearch}
                    onChange={(e) => setPredSearch(e.target.value)}
                  />
                </div>
                <div className="search-box" style={{ margin: 0 }}>
                  <input
                    placeholder="filter by user email..."
                    value={predUserFilter}
                    onChange={(e) => setPredUserFilter(e.target.value)}
                  />
                </div>
              </div>
              <div className="history-table" style={{ marginTop: 16 }}>
                {loading && <p className="empty-state">loading...</p>}
                {!loading && preds.length === 0 && (
                  <p className="empty-state">no diagnoses match.</p>
                )}
                {!loading &&
                  preds.map((p) => (
                    <div className="history-row" key={p.id}>
                      <div>
                        <div className="history-disease">
                          {p.predicted_disease}
                          {p.confidence != null && <span className="confidence-badge">{p.confidence}%</span>}
                        </div>
                        <div className="history-meta">{p.user_email}</div>
                        <div className="history-meta">
                          {p.symptoms_submitted.map((s) => s.replaceAll('_', ' ')).join(', ')}
                        </div>
                        <div className="history-meta">{new Date(p.created_at).toLocaleString()}</div>
                      </div>
                    </div>
                  ))}
              </div>
              {predsTotalPages > 1 && (
                <div className="pagination">
                  <button disabled={predsPage === 0} onClick={() => loadPreds(predsPage - 1)}>
                    prev
                  </button>
                  <span>
                    page {predsPage + 1} / {predsTotalPages}
                  </span>
                  <button disabled={predsPage >= predsTotalPages - 1} onClick={() => loadPreds(predsPage + 1)}>
                    next
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
