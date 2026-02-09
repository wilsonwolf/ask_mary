import { useState, useEffect } from 'react'
import { getDemoConfig, updateCoordinatorPhone } from '../api/client'

export function CoordinatorConfig() {
  const [trialId, setTrialId] = useState('')
  const [phone, setPhone] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    getDemoConfig()
      .then((data) => {
        if (data.trial_id) setTrialId(data.trial_id as string)
      })
      .catch(() => {})
  }, [])

  async function handleSave() {
    if (!phone.trim() || !trialId) return
    setSaving(true)
    setSaved(false)
    try {
      await updateCoordinatorPhone(trialId, phone.trim())
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } finally {
      setSaving(false)
    }
  }

  if (!trialId) return null

  return (
    <div className="flex items-center gap-2">
      <label className="text-xs text-gray-400" htmlFor="coord-phone">
        Coordinator:
      </label>
      <input
        id="coord-phone"
        type="tel"
        value={phone}
        onChange={(e) => setPhone(e.target.value)}
        placeholder="+1..."
        className="w-36 rounded bg-gray-800 px-2 py-1 text-xs text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      <button
        onClick={handleSave}
        disabled={saving || !phone.trim()}
        className="rounded bg-blue-600 px-2 py-1 text-xs text-white hover:bg-blue-500 disabled:opacity-50"
      >
        {saving ? '...' : 'Set'}
      </button>
      {saved && <span className="text-xs text-emerald-400">Saved</span>}
    </div>
  )
}
