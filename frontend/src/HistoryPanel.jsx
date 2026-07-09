import React, { useEffect, useState, useCallback, useRef } from 'react'
import { useAuth } from './AuthContext.jsx'

const PAGE_SIZE = 10

export default function HistoryPanel({ apiBase, refreshSignal }) {
  const { authFetch, authHeaders } = useAuth()
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [search, setSearch] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [loading, setLoading] = useState(false)
  const [confirmClear, setConfirmClear] = useState(false)
  const [undoBanner, setUndoBanner] = useState(null) // { id, disease }
  const undoTimer = useRef(null)

  const buildParams = useCallback(
    (skip) => {
      const params = new URLSearchParams()
      if (search.trim()) params.set('search', search.trim())
      if (startDate) params.set('start_date', startDate)
      if (endDate) params.set('end_date', endDate)
      params.set('skip', skip)
      params.set('limit', PAGE_SIZE)
      return params
    },
    [search, startDate, endDate]
  )

  const loadPage = useCallback(
    (targetPage) => {
      setLoading(true)
      const params = buildParams(targetPage * PAGE_SIZE)
      authFetch(`/history?${params.toString()}`)
        .then((r) => r.json())
        .then((data) => {
          setItems(data.items || [])
          setTotal(data.total || 0)
          setPage(targetPage)
        })
        .catch(() => {})
        .finally(() => setLoading(false))
    },
    [authFetch, buildParams]
  )

  useEffect(() => {
    loadPage(0)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, startDate, endDate, refreshSignal])

  const deleteEntry = (entry) => {
    authFetch(`/history/${entry.id}`, { method: 'DELETE' }).then(() => {
      loadPage(page)
      setUndoBanner({ id: entry.id, disease: entry.predicted_disease })
      clearTimeout(undoTimer.current)
      undoTimer.current = setTimeout(() => setUndoBanner(null), 6000)
    })
  }

  const undoDelete = () => {
    if (!undoBanner) return
    authFetch(`/history/${undoBanner.id}/restore`, { method: 'POST' }).then(() => {
      setUndoBanner(null)
      clearTimeout(undoTimer.current)
      loadPage(page)
    })
  }

  const clearAll = () => {
    authFetch(`/history`, { method: 'DELETE' }).then(() => {
      setConfirmClear(false)
      loadPage(0)
    })
  }

  const exportAs = (format) => {
    const params = buildParams(0)
    params.delete('skip')
    params.delete('limit')
    params.set('format', format)
    // file downloads can't carry custom headers via window.open, so we fetch
    // with the auth header and trigger the download from a blob instead.
    authFetch(`/history/export?${params.toString()}`)
      .then((r) => r.blob())
      .then((blob) => {
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `diagnosis_history.${format}`
        document.body.appendChild(a)
        a.click()
        a.remove()
        window.URL.revokeObjectURL(url)
      })
      .catch(() => {})
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>diagnosis history</h2>
        <span className="count">{total} total</span>
      </div>
      <div className="panel-body">
        <div className="history-toolbar">
          <div className="search-box" style={{ margin: 0 }}>
            <input
              placeholder="search by disease name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <div className="date-row">
            <label>
              from
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </label>
            <label>
              to
              <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </label>
          </div>

          <div className="toolbar-actions">
            <button className="ghost-btn" onClick={() => exportAs('csv')}>
              export csv
            </button>
            <button className="ghost-btn" onClick={() => exportAs('pdf')}>
              export pdf
            </button>
            {!confirmClear ? (
              <button className="ghost-btn danger" onClick={() => setConfirmClear(true)}>
                clear all
              </button>
            ) : (
              <span className="confirm-clear">
                are you sure?
                <button className="ghost-btn danger" onClick={clearAll}>
                  yes, clear
                </button>
                <button className="ghost-btn" onClick={() => setConfirmClear(false)}>
                  cancel
                </button>
              </span>
            )}
          </div>
        </div>

        {undoBanner && (
          <div className="undo-banner">
            <span>deleted "{undoBanner.disease}"</span>
            <button onClick={undoDelete}>undo</button>
          </div>
        )}

        <div className="history-table">
          {loading && <p className="empty-state">loading...</p>}
          {!loading && items.length === 0 && (
            <p className="empty-state">
              <span className="prompt">{'>'}</span> no entries match these filters.
            </p>
          )}
          {!loading &&
            items.map((h) => (
              <div className="history-row" key={h.id}>
                <div>
                  <div className="history-disease">
                    {h.predicted_disease}
                    {h.confidence != null && <span className="confidence-badge">{h.confidence}%</span>}
                  </div>
                  <div className="history-meta">
                    {h.symptoms_submitted.map((s) => s.replaceAll('_', ' ')).join(', ')}
                  </div>
                  <div className="history-meta">{new Date(h.created_at).toLocaleString()}</div>
                </div>
                <button className="delete-btn" title="delete entry" onClick={() => deleteEntry(h)}>
                  &times;
                </button>
              </div>
            ))}
        </div>

        {totalPages > 1 && (
          <div className="pagination">
            <button disabled={page === 0} onClick={() => loadPage(page - 1)}>
              prev
            </button>
            <span>
              page {page + 1} / {totalPages}
            </span>
            <button disabled={page >= totalPages - 1} onClick={() => loadPage(page + 1)}>
              next
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
