import { useEffect, useState } from 'react'
import { getAnalyticsSummary } from '../api/client'

interface Stats {
  total_participants: number
  total_appointments: number
  open_handoffs: number
}

const REFRESH_INTERVAL_MS = 30_000

export function AnalyticsSummary() {
  const [stats, setStats] = useState<Stats | null>(null)

  useEffect(() => {
    const load = () => {
      getAnalyticsSummary()
        .then((data) => setStats(data as unknown as Stats))
        .catch(() => setStats(null))
    }
    load()
    const interval = setInterval(load, REFRESH_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [])

  const cards: { label: string; key: keyof Stats; alert?: boolean }[] = [
    { label: 'Participants', key: 'total_participants' },
    { label: 'Appointments', key: 'total_appointments' },
    { label: 'Open Handoffs', key: 'open_handoffs', alert: true },
  ]

  return (
    <div style={{ display: 'flex', gap: 16, marginBottom: 20 }}>
      {cards.map(({ label, key, alert }) => {
        const value = stats?.[key]
        const isAlert = alert && value !== undefined && value > 0
        return (
          <div
            key={key}
            style={{
              flex: 1,
              padding: '12px 16px',
              borderRadius: 8,
              backgroundColor: isAlert ? '#fff3e0' : '#f5f5f5',
              border: isAlert ? '1px solid #ff9800' : '1px solid #e0e0e0',
            }}
          >
            <div style={{ fontSize: '0.8em', color: '#666', marginBottom: 4 }}>
              {label}
            </div>
            <div
              style={{
                fontSize: '1.5em',
                fontWeight: 700,
                color: isAlert ? '#e65100' : '#212121',
              }}
            >
              {value !== undefined ? value : '\u2014'}
            </div>
          </div>
        )
      })}
    </div>
  )
}
