import React, { useEffect, useState, useMemo } from 'react'
import HistoryPanel from './HistoryPanel.jsx'
import AdminPanel from './AdminPanel.jsx'
import LoginScreen from './LoginScreen.jsx'
import { AuthProvider, useAuth } from './AuthContext.jsx'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function MainApp() {
  const { user, logout, authFetch } = useAuth()
  const [tab, setTab] = useState('diagnose') // 'diagnose' | 'history'

  const [symptoms, setSymptoms] = useState([])
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState([])
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [apiOnline, setApiOnline] = useState(false)
  const [historyRefreshSignal, setHistoryRefreshSignal] = useState(0)

  const [freeText, setFreeText] = useState('')
  const [matchLoading, setMatchLoading] = useState(false)
  const [matchError, setMatchError] = useState('')
  const [lastMatches, setLastMatches] = useState([])

  useEffect(() => {
    fetch(`${API_BASE}/`)
      .then((r) => r.ok && setApiOnline(true))
      .catch(() => setApiOnline(false))

    fetch(`${API_BASE}/symptoms`)
      .then((r) => r.json())
      .then(setSymptoms)
      .catch(() => setError('Could not load symptom list. Is the backend running?'))
  }, [])

  const filteredSymptoms = useMemo(() => {
    const q = query.trim().toLowerCase().replace(/\s+/g, '_')
    return symptoms.filter((s) => s.name.toLowerCase().includes(q)).slice(0, 40)
  }, [symptoms, query])

  const toggleSymptom = (name) => {
    setSelected((prev) =>
      prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name]
    )
  }

  const findSymptomsFromText = async () => {
    if (freeText.trim().length < 3) return
    setMatchLoading(true)
    setMatchError('')
    try {
      const res = await fetch(`${API_BASE}/symptoms/match`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: freeText }),
      })
      const data = await res.json()
      if (!res.ok) {
        const message = Array.isArray(data.detail)
          ? data.detail.map((d) => d.msg).join(' ')
          : data.detail || 'Could not match symptoms.'
        throw new Error(message)
      }
      setLastMatches(data.matches)
      // Pre-select matched symptoms (merge with anything already selected, no duplicates)
      setSelected((prev) => {
        const names = data.matches.map((m) => m.name)
        return [...new Set([...prev, ...names])]
      })
    } catch (e) {
      setMatchError(e.message)
    } finally {
      setMatchLoading(false)
    }
  }

  const runDiagnosis = async () => {
    if (selected.length === 0) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await authFetch(`/predict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symptoms: selected }),
      })
      const data = await res.json()
      if (!res.ok) {
        const message = Array.isArray(data.detail)
          ? data.detail.map((d) => d.msg).join(' ')
          : data.detail || 'Prediction failed.'
        throw new Error(message)
      }
      setResult(data)
      setHistoryRefreshSignal((n) => n + 1)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <div className="scanlines" />
      <div className="app">
        <header className="header">
          <div>
            <p className="brand-eyebrow">symptom analysis terminal</p>
            <h1 className="brand-title">
              diagnose<span className="blink" />
            </h1>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div className="status-pill">
              <span className={`dot ${apiOnline ? '' : 'off'}`} />
              {apiOnline ? 'backend connected' : 'backend offline'}
            </div>
            <div className="status-pill">
              {user?.email}
              <button className="logout-link" onClick={logout}>
                log out
              </button>
            </div>
          </div>
        </header>

        <div className="tab-bar">
          <button className={tab === 'diagnose' ? 'active' : ''} onClick={() => setTab('diagnose')}>
            01 / diagnose
          </button>
          <button className={tab === 'history' ? 'active' : ''} onClick={() => setTab('history')}>
            02 / history
          </button>
          {user?.is_admin && (
            <button className={tab === 'admin' ? 'active' : ''} onClick={() => setTab('admin')}>
              03 / admin
            </button>
          )}
        </div>

        {tab === 'diagnose' && (
          <div className="grid">
            <div className="panel">
              <div className="panel-head">
                <h2>select symptoms</h2>
                <span className="count">{selected.length} selected</span>
              </div>
              <div className="panel-body">
                <div className="freetext-box" style={{ marginBottom: 14 }}>
                  <textarea
                    placeholder="describe your symptoms in your own words, e.g. 'tez bukhar hai, khansi aur badan dard bhi hai'"
                    value={freeText}
                    onChange={(e) => setFreeText(e.target.value)}
                    rows={3}
                    style={{
                      width: '100%',
                      resize: 'vertical',
                      background: 'var(--panel-bg, #111)',
                      color: 'inherit',
                      border: '1px solid var(--border, #333)',
                      borderRadius: 6,
                      padding: 10,
                      fontFamily: 'inherit',
                      fontSize: 14,
                    }}
                  />
                  <button
                    className="run-btn"
                    disabled={freeText.trim().length < 3 || matchLoading}
                    onClick={findSymptomsFromText}
                    style={{ marginTop: 8 }}
                  >
                    {matchLoading ? (
                      <>
                        <span className="spinner" />
                        finding symptoms...
                      </>
                    ) : (
                      'find matching symptoms'
                    )}
                  </button>
                  {matchError && <p className="error-msg">{matchError}</p>}
                  {lastMatches.length > 0 && !matchLoading && (
                    <p style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 6 }}>
                      matched {lastMatches.length} symptom(s) from your description — review the
                      selections below and untick anything that doesn't apply before running
                      diagnosis.
                    </p>
                  )}
                  {lastMatches.length === 0 && matchError === '' && !matchLoading && freeText.trim().length >= 3 && (
                    <span />
                  )}
                </div>

                <div className="search-box">
                  <input
                    placeholder="or search/select symptoms manually, e.g. fatigue, headache..."
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </div>

                <div className="symptom-list">
                  {filteredSymptoms.length === 0 && (
                    <div className="symptom-row">
                      <span className="symptom-name" style={{ color: 'var(--text-dim)' }}>
                        no matches
                      </span>
                    </div>
                  )}
                  {filteredSymptoms.map((s) => (
                    <div
                      key={s.name}
                      className={`symptom-row ${selected.includes(s.name) ? 'selected' : ''}`}
                      onClick={() => toggleSymptom(s.name)}
                    >
                      <span className="symptom-name">{s.name.replaceAll('_', ' ')}</span>
                      <span className="weight-tag">sev {s.weight}</span>
                    </div>
                  ))}
                </div>

                {selected.length > 0 && (
                  <div className="chips">
                    {selected.map((s) => (
                      <span className="chip" key={s}>
                        {s.replaceAll('_', ' ')}
                        <button onClick={() => toggleSymptom(s)}>&times;</button>
                      </span>
                    ))}
                  </div>
                )}

                <button
                  className="run-btn"
                  disabled={selected.length === 0 || loading}
                  onClick={runDiagnosis}
                  style={{ marginTop: selected.length > 0 ? 0 : 14 }}
                >
                  {loading ? (
                    <>
                      <span className="spinner" />
                      analyzing...
                    </>
                  ) : (
                    'run diagnosis'
                  )}
                </button>
                {error && <p className="error-msg">{error}</p>}
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <h2>result</h2>
              </div>
              <div className="panel-body">
                {!result && !loading && (
                  <p className="empty-state">
                    <span className="prompt">{'>'}</span> waiting for symptom input. select
                    one or more symptoms on the left, then run diagnosis.
                  </p>
                )}
                {loading && (
                  <p className="empty-state">
                    <span className="prompt">{'>'}</span> running symptom vector through
                    classifier...
                  </p>
                )}
                {result && (
                  <div>
                    <div className="result-head-row">
                      <h3 className="result-disease">{result.disease}</h3>
                      <span className="confidence-pill">{result.confidence}% confidence</span>
                    </div>
                    <p className="result-desc">{result.description}</p>

                    {result.top_predictions.length > 1 && (
                      <>
                        <p className="section-label">other possibilities considered</p>
                        <div className="tag-list">
                          {result.top_predictions.slice(1).map((p, i) => (
                            <span className="tag" key={i}>
                              {p.disease} — {p.confidence}%
                            </span>
                          ))}
                        </div>
                      </>
                    )}

                    {result.precautions.length > 0 && (
                      <>
                        <p className="section-label">precautions</p>
                        <ul className="plain">
                          {result.precautions.map((p, i) => (
                            <li key={i}>{p}</li>
                          ))}
                        </ul>
                      </>
                    )}

                    {result.medications.length > 0 && (
                      <>
                        <p className="section-label">medications</p>
                        <div className="tag-list">
                          {result.medications.map((m, i) => (
                            <span className="tag" key={i}>{m}</span>
                          ))}
                        </div>
                      </>
                    )}

                    {result.diet.length > 0 && (
                      <>
                        <p className="section-label">recommended diet</p>
                        <div className="tag-list">
                          {result.diet.map((d, i) => (
                            <span className="tag" key={i}>{d}</span>
                          ))}
                        </div>
                      </>
                    )}

                    {result.workout.length > 0 && (
                      <>
                        <p className="section-label">workout guidance</p>
                        <ul className="plain">
                          {result.workout.map((w, i) => (
                            <li key={i}>{w}</li>
                          ))}
                        </ul>
                      </>
                    )}

                    <p className="disclaimer">
                      This prediction is generated by a machine learning model for
                      educational purposes only and is not a medical diagnosis. The
                      confidence score is an approximation of model certainty, not a
                      calibrated clinical probability. Consult a licensed physician for
                      any health concerns.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {tab === 'history' && <HistoryPanel apiBase={API_BASE} refreshSignal={historyRefreshSignal} />}

        {tab === 'admin' && user?.is_admin && <AdminPanel />}
      </div>
    </>
  )
}

function Gate() {
  const { token } = useAuth()
  return token ? <MainApp /> : <LoginScreen />
}

export default function App() {
  return (
    <AuthProvider apiBase={API_BASE}>
      <Gate />
    </AuthProvider>
  )
}
