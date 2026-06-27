import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { login } from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const { saveToken, setUser } = useAuth()
  const navigate = useNavigate()
  const [form, setForm]     = useState({ email: '', password: '' })
  const [error, setError]   = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      const res = await login(form.email, form.password)
      saveToken(res.data.access_token)
      // fetch user info
      const { getMe } = await import('../api/client')
      const me = await getMe()
      setUser(me.data)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <span className="text-4xl">🌱</span>
          <h1 className="text-2xl font-bold mt-2">LandRight</h1>
          <p className="text-gray-400 text-sm mt-1">AI Copilot for International Students</p>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Sign in</h2>
          {error && <p className="text-red-400 text-sm mb-3 bg-red-900/20 border border-red-800 rounded-lg px-3 py-2">{error}</p>}

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="text-sm text-gray-400 mb-1 block">Email</label>
              <input className="input" type="email" placeholder="you@university.edu"
                value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} required />
            </div>
            <div>
              <label className="text-sm text-gray-400 mb-1 block">Password</label>
              <input className="input" type="password" placeholder="••••••••"
                value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} required />
            </div>
            <button className="btn-primary w-full mt-2" type="submit" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>

        <p className="text-center text-gray-400 text-sm mt-4">
          No account?{' '}
          <Link to="/signup" className="text-emerald-400 hover:text-emerald-300">Create one</Link>
        </p>
      </div>
    </div>
  )
}
