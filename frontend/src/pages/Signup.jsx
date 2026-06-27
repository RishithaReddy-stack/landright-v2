import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { signup, getMe } from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function Signup() {
  const { saveToken, setUser } = useAuth()
  const navigate = useNavigate()
  const [form, setForm]       = useState({ email: '', password: '', confirm: '' })
  const [error, setError]     = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (form.password !== form.confirm) { setError('Passwords do not match'); return }
    if (form.password.length < 8)       { setError('Password must be at least 8 characters'); return }
    setError(''); setLoading(true)
    try {
      const res = await signup(form.email, form.password)
      saveToken(res.data.access_token)
      const me = await getMe()
      setUser(me.data)
      navigate('/onboarding')
    } catch (err) {
      setError(err.response?.data?.detail || 'Signup failed')
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
          <p className="text-gray-400 text-sm mt-1">Set up your account to get started</p>
        </div>

        <div className="card">
          <h2 className="text-lg font-semibold mb-4">Create account</h2>
          {error && <p className="text-red-400 text-sm mb-3 bg-red-900/20 border border-red-800 rounded-lg px-3 py-2">{error}</p>}

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="text-sm text-gray-400 mb-1 block">Email</label>
              <input className="input" type="email" placeholder="you@university.edu"
                value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} required />
            </div>
            <div>
              <label className="text-sm text-gray-400 mb-1 block">Password</label>
              <input className="input" type="password" placeholder="Min. 8 characters"
                value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} required />
            </div>
            <div>
              <label className="text-sm text-gray-400 mb-1 block">Confirm password</label>
              <input className="input" type="password" placeholder="••••••••"
                value={form.confirm} onChange={e => setForm(f => ({ ...f, confirm: e.target.value }))} required />
            </div>
            <button className="btn-primary w-full mt-2" type="submit" disabled={loading}>
              {loading ? 'Creating account…' : 'Create account'}
            </button>
          </form>
        </div>

        <p className="text-center text-gray-400 text-sm mt-4">
          Already have an account?{' '}
          <Link to="/login" className="text-emerald-400 hover:text-emerald-300">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
