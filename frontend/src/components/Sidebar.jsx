import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const links = [
  { to: '/',      label: 'Dashboard', icon: '⬡' },
  { to: '/chat',  label: 'Chat',      icon: '💬' },
  { to: '/admin', label: 'Eval',      icon: '📊', adminOnly: true },
]

export default function Sidebar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => { logout(); navigate('/login') }

  return (
    <aside className="w-56 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <span className="text-xl">🌱</span>
          <span className="font-bold text-lg">LandRight</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-2 py-4 space-y-1">
        {links.filter(l => !l.adminOnly || user?.role === 'admin').map(l => (
          <NavLink key={l.to} to={l.to} end={l.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? 'bg-emerald-900/30 text-emerald-400 font-medium'
                  : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800'
              }`
            }>
            <span>{l.icon}</span>
            {l.label}
          </NavLink>
        ))}
      </nav>

      {/* User */}
      <div className="px-4 py-4 border-t border-gray-800">
        <p className="text-xs text-gray-500 truncate mb-2">{user?.email}</p>
        <button onClick={handleLogout} className="text-xs text-gray-500 hover:text-gray-300 transition-colors">
          Sign out
        </button>
      </div>
    </aside>
  )
}
