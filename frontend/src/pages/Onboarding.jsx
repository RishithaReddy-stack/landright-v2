import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { updateProfile, uploadI20 } from '../api/client'

const STAGES = [
  { value: 'pre_arrival', label: 'Pre-arrival',  desc: 'Preparing to move to the US' },
  { value: 'day_0',       label: 'Just arrived', desc: 'First week in the US' },
  { value: 'week_1',      label: 'Settling in',  desc: 'Week 1 onwards' },
  { value: 'month_1',     label: 'Month 1+',     desc: 'Getting established' },
  { value: 'ongoing',     label: 'Ongoing',      desc: 'OPT / CPT planning' },
]

export default function Onboarding() {
  const navigate  = useNavigate()
  const [step, setStep] = useState(0)
  const [form, setForm] = useState({
    university: '', visa_type: 'F1', major: '',
    program_end_date: '', current_stage: '',
  })
  const [i20File, setI20File]   = useState(null)
  const [i20Result, setI20Result] = useState(null)
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleI20Upload = async () => {
    if (!i20File) return
    setLoading(true); setError('')
    try {
      const res = await uploadI20(i20File)
      setI20Result(res.data)
      if (res.data.extracted.program_end_date)
        set('program_end_date', res.data.extracted.program_end_date.slice(0, 10))
      if (res.data.extracted.school_name && !form.university)
        set('university', res.data.extracted.school_name)
    } catch {
      setError('Could not parse I-20 — fill in manually below.')
    } finally {
      setLoading(false)
    }
  }

  const handleFinish = async () => {
    setLoading(true); setError('')
    try {
      const payload = { ...form }
      if (payload.program_end_date) payload.program_end_date = payload.program_end_date + 'T00:00:00'
      await updateProfile(payload)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save profile')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-lg">
        {/* Progress */}
        <div className="flex items-center gap-2 mb-8">
          {[0, 1, 2].map(i => (
            <div key={i} className={`h-1 flex-1 rounded-full transition-colors ${i <= step ? 'bg-emerald-500' : 'bg-gray-700'}`} />
          ))}
        </div>

        {/* Step 0: Basic info */}
        {step === 0 && (
          <div className="card space-y-4">
            <h2 className="text-xl font-bold">Tell us about yourself</h2>
            <p className="text-gray-400 text-sm">This helps LandRight give you personalised advice.</p>

            <div>
              <label className="text-sm text-gray-400 mb-1 block">University</label>
              <input className="input" placeholder="University of Arizona"
                value={form.university} onChange={e => set('university', e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm text-gray-400 mb-1 block">Visa type</label>
                <select className="input" value={form.visa_type} onChange={e => set('visa_type', e.target.value)}>
                  <option value="F1">F-1</option>
                  <option value="J1">J-1</option>
                </select>
              </div>
              <div>
                <label className="text-sm text-gray-400 mb-1 block">Major</label>
                <input className="input" placeholder="Computer Science"
                  value={form.major} onChange={e => set('major', e.target.value)} />
              </div>
            </div>
            <div>
              <label className="text-sm text-gray-400 mb-1 block">Program end date</label>
              <input className="input" type="date"
                value={form.program_end_date} onChange={e => set('program_end_date', e.target.value)} />
            </div>

            <button className="btn-primary w-full" onClick={() => setStep(1)}
              disabled={!form.university || !form.major}>
              Continue →
            </button>
          </div>
        )}

        {/* Step 1: Stage */}
        {step === 1 && (
          <div className="card space-y-4">
            <h2 className="text-xl font-bold">Where are you right now?</h2>
            <p className="text-gray-400 text-sm">We'll show you the right tasks for your situation.</p>

            <div className="space-y-2">
              {STAGES.map(s => (
                <button key={s.value}
                  onClick={() => set('current_stage', s.value)}
                  className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${
                    form.current_stage === s.value
                      ? 'border-emerald-500 bg-emerald-900/20 text-emerald-300'
                      : 'border-gray-700 hover:border-gray-500'
                  }`}>
                  <div className="font-medium">{s.label}</div>
                  <div className="text-sm text-gray-400">{s.desc}</div>
                </button>
              ))}
            </div>

            <div className="flex gap-2">
              <button className="btn-ghost flex-1" onClick={() => setStep(0)}>← Back</button>
              <button className="btn-primary flex-1" onClick={() => setStep(2)} disabled={!form.current_stage}>
                Continue →
              </button>
            </div>
          </div>
        )}

        {/* Step 2: I-20 upload (optional) */}
        {step === 2 && (
          <div className="card space-y-4">
            <h2 className="text-xl font-bold">Upload your I-20 (optional)</h2>
            <p className="text-gray-400 text-sm">
              We'll auto-extract your program end date. Your document is stored securely.
            </p>

            {i20Result ? (
              <div className="bg-emerald-900/20 border border-emerald-800 rounded-lg p-3 text-sm">
                <p className="text-emerald-400 font-medium mb-1">✓ I-20 parsed</p>
                {i20Result.extracted.program_end_date && <p className="text-gray-300">Program end: {i20Result.extracted.program_end_date?.slice(0, 10)}</p>}
                {i20Result.extracted.sevis_id        && <p className="text-gray-300">SEVIS ID: {i20Result.extracted.sevis_id}</p>}
                {i20Result.dev_note                  && <p className="text-gray-500 mt-1 text-xs">{i20Result.dev_note}</p>}
              </div>
            ) : (
              <div>
                <label className="block border-2 border-dashed border-gray-700 hover:border-emerald-600 rounded-xl p-8 text-center cursor-pointer transition-colors">
                  <input type="file" accept=".pdf" className="hidden" onChange={e => setI20File(e.target.files[0])} />
                  <p className="text-gray-400">{i20File ? i20File.name : 'Click to select I-20 PDF'}</p>
                  <p className="text-gray-600 text-xs mt-1">Max 10 MB</p>
                </label>
                {i20File && (
                  <button className="btn-primary w-full mt-2" onClick={handleI20Upload} disabled={loading}>
                    {loading ? 'Parsing…' : 'Upload & Parse'}
                  </button>
                )}
              </div>
            )}

            {error && <p className="text-amber-400 text-sm">{error}</p>}

            <div className="flex gap-2">
              <button className="btn-ghost flex-1" onClick={() => setStep(1)}>← Back</button>
              <button className="btn-primary flex-1" onClick={handleFinish} disabled={loading}>
                {loading ? 'Saving…' : "Let's go →"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
