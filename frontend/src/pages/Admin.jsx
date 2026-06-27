import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import { getMetrics, getTraces } from '../api/client'
import { useAuth } from '../context/AuthContext'

function MetricCard({ label, value, sub }) {
  return (
    <div className="card text-center">
      <p className="text-3xl font-bold text-emerald-400">{value}</p>
      <p className="text-sm font-medium mt-1">{label}</p>
      {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
    </div>
  )
}

function statusBadge(success) {
  return success
    ? <span className="text-xs bg-emerald-900/40 text-emerald-400 px-2 py-0.5 rounded-full">ok</span>
    : <span className="text-xs bg-red-900/40 text-red-400 px-2 py-0.5 rounded-full">fail</span>
}

function feedbackIcon(feedback) {
  if (feedback === 1)  return <span className="text-emerald-400">👍</span>
  if (feedback === -1) return <span className="text-red-400">👎</span>
  return <span className="text-gray-600">—</span>
}

export default function Admin() {
  const { user } = useAuth()
  const navigate  = useNavigate()
  const [metrics, setMetrics] = useState(null)
  const [traces,  setTraces]  = useState([])
  const [page,    setPage]    = useState(0)
  const PAGE = 20

  useEffect(() => {
    if (user && user.role !== 'admin') navigate('/')
  }, [user])

  useEffect(() => {
    getMetrics().then(r => setMetrics(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    getTraces(PAGE, page * PAGE).then(r => setTraces(r.data)).catch(() => {})
  }, [page])

  if (!metrics) return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 flex items-center justify-center text-gray-400">Loading…</main>
    </div>
  )

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-6 overflow-y-auto">
        <h1 className="text-2xl font-bold mb-6">Eval Dashboard</h1>

        {/* Metric cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <MetricCard label="Total requests"    value={metrics.total_traces} />
          <MetricCard label="Success rate"      value={`${metrics.success_rate}%`} />
          <MetricCard label="Avg latency"       value={`${metrics.avg_latency_ms}ms`} />
          <MetricCard label="Users"             value={metrics.total_users} sub={`${metrics.total_conversations} convos`} />
          <MetricCard label="Thumbs up"         value={metrics.thumbs_up}   sub="positive feedback" />
          <MetricCard label="Thumbs down"       value={metrics.thumbs_down} sub="negative feedback" />
          <MetricCard label="Satisfaction"
            value={
              (metrics.thumbs_up + metrics.thumbs_down) > 0
                ? `${Math.round(metrics.thumbs_up / (metrics.thumbs_up + metrics.thumbs_down) * 100)}%`
                : '—'
            }
            sub="of rated responses"
          />
        </div>

        {/* Traces table */}
        <div className="card p-0 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-800">
            <h2 className="font-semibold">Recent traces</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-gray-400 text-xs">
                  <th className="text-left px-4 py-2">ID</th>
                  <th className="text-left px-4 py-2">User</th>
                  <th className="text-left px-4 py-2">Input</th>
                  <th className="text-left px-4 py-2">Output</th>
                  <th className="text-left px-4 py-2">Latency</th>
                  <th className="text-left px-4 py-2">Status</th>
                  <th className="text-left px-4 py-2">Feedback</th>
                  <th className="text-left px-4 py-2">Time</th>
                </tr>
              </thead>
              <tbody>
                {traces.map(t => (
                  <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
                    <td className="px-4 py-2 text-gray-500">{t.id}</td>
                    <td className="px-4 py-2 text-gray-400">{t.user_id}</td>
                    <td className="px-4 py-2 text-gray-300 max-w-[200px] truncate">{t.input}</td>
                    <td className="px-4 py-2 text-gray-400 max-w-[200px] truncate">{t.output}</td>
                    <td className="px-4 py-2 text-gray-400">{t.latency_ms ? `${t.latency_ms}ms` : '—'}</td>
                    <td className="px-4 py-2">{statusBadge(t.success)}</td>
                    <td className="px-4 py-2">{feedbackIcon(t.feedback)}</td>
                    <td className="px-4 py-2 text-gray-500 whitespace-nowrap">
                      {new Date(t.created_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                    </td>
                  </tr>
                ))}
                {traces.length === 0 && (
                  <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-500">No traces yet</td></tr>
                )}
              </tbody>
            </table>
          </div>
          {/* Pagination */}
          <div className="px-4 py-3 border-t border-gray-800 flex gap-2">
            <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} className="btn-ghost text-sm py-1 px-3 disabled:opacity-30">← Prev</button>
            <span className="text-gray-500 text-sm py-1">Page {page + 1}</span>
            <button onClick={() => setPage(p => p + 1)} disabled={traces.length < PAGE} className="btn-ghost text-sm py-1 px-3 disabled:opacity-30">Next →</button>
          </div>
        </div>
      </main>
    </div>
  )
}
