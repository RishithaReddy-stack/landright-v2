import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Sidebar from '../components/Sidebar'
import {
  sendMessage, getConversations, getMessages, submitFeedback,
  uploadDocument, listDocuments, deleteDocument,
} from '../api/client'

// ── Message bubble ─────────────────────────────────────────────────────────────

function Message({ role, content, traceId }) {
  const isUser = role === 'user'
  const [feedback, setFeedback] = useState(null)

  const handleFeedback = async (value) => {
    if (!traceId || feedback === value) return
    try { await submitFeedback(traceId, value); setFeedback(value) }
    catch { /* best-effort */ }
  }

  return (
    <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
      <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
        isUser ? 'bg-emerald-700 text-white rounded-br-sm' : 'bg-gray-800 text-gray-100 rounded-bl-sm'
      }`}>
        {content}
      </div>
      {!isUser && traceId && (
        <div className="flex gap-1 mt-1 ml-1">
          <button onClick={() => handleFeedback(1)}
            className={`text-xs px-1.5 py-0.5 rounded transition-colors ${feedback === 1 ? 'text-emerald-400' : 'text-gray-600 hover:text-gray-400'}`}>
            👍
          </button>
          <button onClick={() => handleFeedback(-1)}
            className={`text-xs px-1.5 py-0.5 rounded transition-colors ${feedback === -1 ? 'text-red-400' : 'text-gray-600 hover:text-gray-400'}`}>
            👎
          </button>
        </div>
      )}
    </div>
  )
}

// ── Documents panel ────────────────────────────────────────────────────────────

function DocumentsPanel({ onClose }) {
  const fileRef = useRef(null)
  const [docs, setDocs]         = useState([])
  const [uploading, setUploading] = useState(false)
  const [status, setStatus]     = useState(null) // { type: 'success'|'error', msg }

  useEffect(() => { fetchDocs() }, [])

  const fetchDocs = async () => {
    try {
      const r = await listDocuments()
      setDocs(r.data.documents)
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Could not load documents.'
      setStatus({ type: 'error', msg })
    }
  }

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''

    setUploading(true)
    setStatus(null)
    try {
      const r = await uploadDocument(file)
      setStatus({ type: 'success', msg: `"${r.data.filename}" indexed (${r.data.chunks_stored} chunks)` })
      fetchDocs()
    } catch (err) {
      const msg = err.response?.data?.detail || 'Upload failed.'
      setStatus({ type: 'error', msg })
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (filename) => {
    try {
      await deleteDocument(filename)
      setDocs(d => d.filter(f => f !== filename))
    } catch { /* ignore */ }
  }

  return (
    <div className="w-72 shrink-0 bg-gray-900 border-l border-gray-800 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <span className="text-sm font-medium text-gray-200">My Documents</span>
        <button onClick={onClose} className="text-gray-500 hover:text-gray-300 text-lg leading-none">×</button>
      </div>

      {/* Upload area */}
      <div className="p-4 border-b border-gray-800">
        <p className="text-xs text-gray-500 mb-3">
          Upload PDFs, Word docs, or text files. The AI will reference them when answering your questions.
        </p>
        <input
          ref={fileRef}
          type="file"
          accept=".pdf,.docx,.txt"
          className="hidden"
          onChange={handleFileChange}
        />
        <button
          onClick={() => fileRef.current?.click()}
          disabled={uploading}
          className="btn-primary w-full text-sm py-2 disabled:opacity-50"
        >
          {uploading ? 'Uploading…' : '+ Upload document'}
        </button>
        {status && (
          <p className={`text-xs mt-2 ${status.type === 'success' ? 'text-emerald-400' : 'text-red-400'}`}>
            {status.msg}
          </p>
        )}
      </div>

      {/* Document list */}
      <div className="flex-1 overflow-y-auto p-4">
        {docs.length === 0 ? (
          <p className="text-xs text-gray-600 text-center py-6">
            No documents yet.<br />Upload your I-20, offer letter, or DSO instructions.
          </p>
        ) : (
          <ul className="space-y-2">
            {docs.map(filename => (
              <li key={filename}
                className="flex items-center justify-between gap-2 bg-gray-800 rounded-lg px-3 py-2">
                <span className="text-xs text-gray-300 truncate" title={filename}>
                  📄 {filename}
                </span>
                <button
                  onClick={() => handleDelete(filename)}
                  className="text-gray-600 hover:text-red-400 text-xs shrink-0 transition-colors"
                  title="Remove"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

// ── Main chat page ─────────────────────────────────────────────────────────────

export default function Chat() {
  const { id }    = useParams()
  const navigate  = useNavigate()
  const bottomRef = useRef(null)
  const fileRef   = useRef(null)

  const [conversations, setConversations] = useState([])
  const [messages, setMessages]           = useState([])
  const [input, setInput]                 = useState('')
  const [sending, setSending]             = useState(false)
  const [convId, setConvId]               = useState(id ? parseInt(id) : null)
  const [showDocs, setShowDocs]           = useState(false)
  const [uploading, setUploading]         = useState(false)
  const [uploadMsg, setUploadMsg]         = useState(null)

  useEffect(() => {
    getConversations().then(r => setConversations(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    if (!convId) { setMessages([]); return }
    getMessages(convId).then(r => setMessages(r.data)).catch(() => {})
  }, [convId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || sending) return
    setInput(''); setSending(true)
    setMessages(ms => [...ms, { role: 'user', content: text }])

    try {
      const res = await sendMessage(text, convId)
      const newConvId = res.data.conversation_id
      if (!convId) {
        setConvId(newConvId)
        navigate(`/chat/${newConvId}`, { replace: true })
        setConversations(cs => [{ id: newConvId, created_at: new Date().toISOString(), summary: null }, ...cs])
      }
      setMessages(ms => [...ms, { role: 'assistant', content: res.data.answer, traceId: res.data.trace_id }])
    } catch {
      setMessages(ms => [...ms, { role: 'assistant', content: 'Something went wrong. Please try again.' }])
    } finally {
      setSending(false)
    }
  }

  // Quick upload from the paperclip button in the input bar
  const handleQuickUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    e.target.value = ''
    setUploading(true)
    setUploadMsg(null)

    try {
      const r = await uploadDocument(file)
      setUploadMsg({ type: 'success', msg: `✓ "${r.data.filename}" uploaded and indexed` })
    } catch (err) {
      const msg = err.response?.data?.detail || 'Upload failed.'
      setUploadMsg({ type: 'error', msg })
    } finally {
      setUploading(false)
      setTimeout(() => setUploadMsg(null), 4000)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const startNew = () => {
    setConvId(null); setMessages([])
    navigate('/chat', { replace: true })
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      {/* Conversation list */}
      <div className="w-52 shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="p-3 border-b border-gray-800 space-y-2">
          <button onClick={startNew} className="btn-primary w-full text-sm py-1.5">+ New chat</button>
          <button
            onClick={() => setShowDocs(d => !d)}
            className={`w-full text-sm py-1.5 rounded-lg border transition-colors font-medium ${
              showDocs
                ? 'border-emerald-500 text-emerald-300 bg-emerald-900/30'
                : 'border-gray-600 text-gray-200 bg-gray-800 hover:border-emerald-500 hover:text-emerald-300'
            }`}
          >
            📁 My Docs
          </button>
        </div>
        <div className="flex-1 overflow-y-auto py-2">
          {conversations.length === 0 ? (
            <p className="text-xs text-gray-600 px-3 py-4">No conversations yet</p>
          ) : (
            conversations.map(c => (
              <button key={c.id}
                onClick={() => { setConvId(c.id); navigate(`/chat/${c.id}`) }}
                className={`w-full text-left px-3 py-2 text-xs transition-colors ${
                  convId === c.id ? 'bg-gray-800 text-gray-100' : 'text-gray-400 hover:bg-gray-800 hover:text-gray-100'
                }`}>
                <p className="truncate">{c.summary || 'Conversation'}</p>
                <p className="text-gray-600 mt-0.5">
                  {new Date(c.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </p>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 && !sending && (
            <div className="h-full flex flex-col items-center justify-center text-center text-gray-500">
              <span className="text-5xl mb-4">🌱</span>
              <p className="text-lg font-medium text-gray-300">Hi! I'm LandRight.</p>
              <p className="text-sm mt-1 max-w-sm">
                Ask me about OPT timelines, banking, housing, taxes, or anything else about life as an international student.
              </p>
              <div className="grid grid-cols-2 gap-2 mt-6 w-full max-w-sm">
                {[
                  'What are my OPT deadlines?',
                  'What tasks do I still need to do?',
                  'How do I open a bank account?',
                  'When should I apply for SSN?',
                ].map(q => (
                  <button key={q} onClick={() => setInput(q)}
                    className="text-left text-xs text-gray-400 border border-gray-700 hover:border-emerald-600 hover:text-gray-200 rounded-lg px-3 py-2 transition-colors">
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m, i) => <Message key={i} {...m} />)}

          {sending && (
            <div className="flex justify-start">
              <div className="bg-gray-800 rounded-2xl rounded-bl-sm px-4 py-3 text-gray-400 text-sm">
                <span className="animate-pulse">LandRight is thinking…</span>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Upload status toast */}
        {uploadMsg && (
          <div className={`mx-4 mb-0 px-4 py-2 rounded-lg text-xs ${
            uploadMsg.type === 'success' ? 'bg-emerald-900/40 text-emerald-400' : 'bg-red-900/40 text-red-400'
          }`}>
            {uploadMsg.msg}
          </div>
        )}

        {/* Input bar */}
        <div className="p-4 border-t border-gray-800">
          <div className="flex gap-2 items-end">
            {/* Paperclip upload button */}
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.docx,.txt"
              className="hidden"
              onChange={handleQuickUpload}
            />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              title="Upload a document"
              className="shrink-0 w-10 h-10 flex items-center justify-center rounded-lg border border-gray-700 text-gray-400 hover:border-emerald-600 hover:text-emerald-400 transition-colors disabled:opacity-40"
            >
              {uploading ? (
                <span className="text-xs animate-pulse">…</span>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                </svg>
              )}
            </button>

            <textarea
              className="input flex-1 resize-none min-h-[44px] max-h-32"
              rows={1}
              placeholder="Ask anything about your international student journey…"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <button onClick={handleSend} disabled={sending || !input.trim()}
              className="btn-primary px-4 py-2.5 shrink-0 h-10">
              {sending ? '…' : '↑'}
            </button>
          </div>
          <p className="text-xs text-gray-600 mt-1.5">Enter to send · Shift+Enter for new line · 📎 to upload a doc</p>
        </div>
      </div>

      {/* Documents side panel */}
      {showDocs && <DocumentsPanel onClose={() => setShowDocs(false)} />}
    </div>
  )
}
