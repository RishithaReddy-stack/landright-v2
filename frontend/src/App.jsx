import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Login      from './pages/Login'
import Signup     from './pages/Signup'
import Onboarding from './pages/Onboarding'
import Dashboard  from './pages/Dashboard'
import Chat       from './pages/Chat'

function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="min-h-screen flex items-center justify-center text-gray-400">Loading…</div>
  return user ? children : <Navigate to="/login" replace />
}

function PublicRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return null
  return user ? <Navigate to="/" replace /> : children
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login"      element={<PublicRoute><Login /></PublicRoute>} />
        <Route path="/signup"     element={<PublicRoute><Signup /></PublicRoute>} />
        <Route path="/onboarding" element={<PrivateRoute><Onboarding /></PrivateRoute>} />
        <Route path="/"           element={<PrivateRoute><Dashboard /></PrivateRoute>} />
        <Route path="/chat"       element={<PrivateRoute><Chat /></PrivateRoute>} />
        <Route path="/chat/:id"   element={<PrivateRoute><Chat /></PrivateRoute>} />
        <Route path="*"           element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
