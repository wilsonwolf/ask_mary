import { useState, useEffect } from 'react'
import { startDemoCall, getDemoConfig } from '../api/client'

interface DemoConfig {
  participant_id: string
  trial_id: string
  participant_name: string
  phone: string
}

interface Props {
  onCallStarted: () => void
}

/** "Start Demo Call" button that triggers an outbound ElevenLabs call. */
export function DemoButton({ onCallStarted }: Props) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [config, setConfig] = useState<DemoConfig | null>(null)

  useEffect(() => {
    getDemoConfig()
      .then((data) => {
        if ('error' in data) {
          setError(data.error as string)
        } else {
          setConfig(data as unknown as DemoConfig)
        }
      })
      .catch(() => setError('Failed to load demo config'))
  }, [])

  async function handleClick() {
    if (!config) return
    setLoading(true)
    setError('')
    try {
      await startDemoCall(config.participant_id, config.trial_id)
      onCallStarted()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start call')
    } finally {
      setLoading(false)
    }
  }

  const label = config
    ? `Call ${config.participant_name}`
    : 'Start Demo Call'

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={handleClick}
        disabled={loading || !config}
        className="rounded-lg bg-emerald-600 px-6 py-3 font-semibold text-white transition hover:bg-emerald-500 disabled:opacity-50"
      >
        {loading ? 'Starting...' : label}
      </button>
      {error && <span className="text-sm text-red-400">{error}</span>}
    </div>
  )
}
