import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import { getProfile, getTasks, completeTask, getNotifications, markRead, markAllRead } from '../api/client'

function kindColor(kind) {
  if (kind === 'urgent')  return 'text-red-400 bg-red-900/20 border-red-800'
  if (kind === 'warning') return 'text-amber-400 bg-amber-900/20 border-amber-800'
  return 'text-blue-400 bg-blue-900/20 border-blue-800'
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [profile, setProfile]               = useState(null)
  const [tasks, setTasks]                   = useState([])
  const [notifications, setNotifications]   = useState([])
  const [loadingTask, setLoadingTask]       = useState(null)
  const [showAllNotifs, setShowAllNotifs]   = useState(false)

  useEffect(() => {
    getProfile().then(r => setProfile(r.data)).catch(() => {})
    getTasks().then(r => setTasks(r.data)).catch(() => {})
    getNotifications().then(r => setNotifications(r.data)).catch(() => {})
  }, [])

  const handleComplete = async (taskId) => {
    setLoadingTask(taskId)
    try {
      await completeTask(taskId)
      setTasks(ts => ts.map(t => t.id === taskId ? { ...t, is_complete: true } : t))
    } finally {
      setLoadingTask(null)
    }
  }

  const handleMarkRead = async (id) => {
    await markRead(id)
    setNotifications(ns => ns.filter(n => n.id !== id))
  }

  const handleMarkAllRead = async () => {
    await markAllRead()
    setNotifications(ns => ns.map(n => ({ ...n, is_read: true })))
  }

  const pending   = tasks.filter(t => !t.is_complete)
  const completed = tasks.filter(t =>  t.is_complete)
  const unread    = notifications.filter(n => !n.is_read)
  const visibleNotifs = showAllNotifs ? notifications : notifications.slice(0, 3)

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="flex-1 p-6 overflow-y-auto">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">Dashboard</h1>
            {profile && (
              <p className="text-gray-400 text-sm mt-1">
                {profile.university} · {profile.visa_type} · {profile.major}
              </p>
            )}
          </div>
          <button onClick={() => navigate('/chat')}
            className="btn-primary flex items-center gap-2">
            <span>💬</span> Ask LandRight
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Tasks — left 2/3 */}
          <div className="lg:col-span-2 space-y-4">

            {/* Pending tasks */}
            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-semibold">
                  Pending tasks
                  {pending.length > 0 && (
                    <span className="ml-2 text-xs bg-emerald-900/40 text-emerald-400 px-2 py-0.5 rounded-full">
                      {pending.length}
                    </span>
                  )}
                </h2>
                <span className="text-xs text-gray-500 capitalize">{profile?.current_stage?.replace('_', ' ')}</span>
              </div>

              {pending.length === 0 ? (
                <p className="text-gray-500 text-sm py-4 text-center">All caught up! 🎉</p>
              ) : (
                <ul className="space-y-2">
                  {pending.map(t => (
                    <li key={t.id} className="flex items-center gap-3 group">
                      <button
                        onClick={() => handleComplete(t.id)}
                        disabled={loadingTask === t.id}
                        className="w-5 h-5 rounded border border-gray-600 flex-shrink-0 hover:border-emerald-500 hover:bg-emerald-900/30 transition-colors flex items-center justify-center">
                        {loadingTask === t.id && <span className="text-xs text-gray-400">…</span>}
                      </button>
                      <span className="text-sm text-gray-200">{t.title}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Completed tasks */}
            {completed.length > 0 && (
              <div className="card opacity-60">
                <h2 className="font-semibold mb-3 text-gray-400">Completed</h2>
                <ul className="space-y-2">
                  {completed.map(t => (
                    <li key={t.id} className="flex items-center gap-3">
                      <span className="w-5 h-5 rounded bg-emerald-800/40 flex items-center justify-center text-emerald-500 text-xs flex-shrink-0">✓</span>
                      <span className="text-sm text-gray-500 line-through">{t.title}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Notifications — right 1/3 */}
          <div className="space-y-4">
            <div className="card">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-semibold">
                  Notifications
                  {unread.length > 0 && (
                    <span className="ml-2 text-xs bg-red-900/40 text-red-400 px-2 py-0.5 rounded-full">
                      {unread.length}
                    </span>
                  )}
                </h2>
                {unread.length > 0 && (
                  <button onClick={handleMarkAllRead}
                    className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
                    Mark all read
                  </button>
                )}
              </div>

              {notifications.length === 0 ? (
                <p className="text-gray-500 text-sm py-4 text-center">No notifications yet</p>
              ) : (
                <ul className="space-y-2">
                  {visibleNotifs.map(n => (
                    <li key={n.id}
                      className={`rounded-lg border px-3 py-2 text-sm ${kindColor(n.kind)} ${n.is_read ? 'opacity-50' : ''}`}>
                      <div className="flex items-start justify-between gap-2">
                        <p className="font-medium leading-snug">{n.title}</p>
                        {!n.is_read && (
                          <button onClick={() => handleMarkRead(n.id)}
                            className="text-xs opacity-70 hover:opacity-100 shrink-0 mt-0.5">✕</button>
                        )}
                      </div>
                      <p className="text-xs mt-1 opacity-80 leading-relaxed">{n.body}</p>
                    </li>
                  ))}
                </ul>
              )}

              {notifications.length > 3 && (
                <button onClick={() => setShowAllNotifs(v => !v)}
                  className="text-xs text-gray-500 hover:text-gray-300 mt-2 transition-colors">
                  {showAllNotifs ? 'Show less' : `Show ${notifications.length - 3} more`}
                </button>
              )}
            </div>

            {/* Quick profile card */}
            {profile && (
              <div className="card text-sm space-y-2">
                <h2 className="font-semibold mb-1">Your profile</h2>
                <div className="text-gray-400 space-y-1">
                  <p>🎓 {profile.university}</p>
                  <p>📋 {profile.visa_type} · {profile.major}</p>
                  {profile.program_end_date && (
                    <p>📅 Graduation: {new Date(profile.program_end_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
