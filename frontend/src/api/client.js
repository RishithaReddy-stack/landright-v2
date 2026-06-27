import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// Attach JWT on every request
api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// Auto-logout on 401
api.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ── Auth ───────────────────────────────────────────────────────────────────────
export const signup  = (email, password) => api.post('/auth/signup',  { email, password })
export const login   = (email, password) => api.post('/auth/login',   { email, password })
export const getMe   = ()                => api.get('/auth/me')

// ── Profile ───────────────────────────────────────────────────────────────────
export const getProfile    = ()      => api.get('/profile')
export const updateProfile = (data)  => api.put('/profile', data)

// ── Chat ──────────────────────────────────────────────────────────────────────
export const sendMessage       = (message, conversation_id) => api.post('/chat', { message, conversation_id })
export const getConversations  = ()                          => api.get('/chat/conversations')
export const getMessages       = (id)                        => api.get(`/chat/conversations/${id}/messages`)

// ── Tasks ─────────────────────────────────────────────────────────────────────
export const getTasks      = ()   => api.get('/tasks')
export const completeTask  = (id) => api.put(`/tasks/${id}/complete`)

// ── Notifications ─────────────────────────────────────────────────────────────
export const getNotifications = (unread_only = false) =>
  api.get('/notifications', { params: { unread_only } })
export const markRead    = (id) => api.put(`/notifications/${id}/read`)
export const markAllRead = ()   => api.put('/notifications/read-all')

// ── Admin / Eval ──────────────────────────────────────────────────────────────
export const getMetrics      = ()            => api.get('/admin/metrics')
export const getTraces       = (limit, offset) => api.get('/admin/traces', { params: { limit, offset } })
export const submitFeedback  = (traceId, value) => api.post(`/admin/traces/${traceId}/feedback`, { value })

// ── Documents ─────────────────────────────────────────────────────────────────
export const uploadI20 = (file) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/documents/upload-i20', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const uploadDocument = (file) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/documents/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const listDocuments  = ()         => api.get('/documents')
export const deleteDocument = (filename) => api.delete(`/documents/${encodeURIComponent(filename)}`)
