import { useEffect, useState } from 'react'
import { getAdversarialStatus } from '../api/client'

interface Props {
  participantId: string
}

interface AdversarialData {
  check_status: string
  discrepancies?: string[]
  confidence?: number
}

function badgeClasses(status: string): string {
  if (status === 'complete') return 'bg-emerald-900/50 text-emerald-300'
  if (status === 'pending' || status === 'running') return 'bg-yellow-900/50 text-yellow-300'
  return 'bg-gray-800 text-gray-400'
}

function hasDiscrepancies(data: AdversarialData): boolean {
  return data.check_status === 'complete' && (data.discrepancies?.length ?? 0) > 0
}

function badgeLabel(data: AdversarialData): string {
  if (data.check_status === 'pending' || data.check_status === 'running') return 'Pending'
  if (hasDiscrepancies(data)) return 'Discrepancies Found'
  if (data.check_status === 'complete') return 'Clear'
  return data.check_status
}

/** Badge showing adversarial check status with hover details. */
export function AdversarialStatusBadge({ participantId }: Props) {
  const [data, setData] = useState<AdversarialData | null>(null)
  const [showDetails, setShowDetails] = useState(false)

  useEffect(() => {
    getAdversarialStatus(participantId)
      .then((result) => setData(result as unknown as AdversarialData))
      .catch(() => setData({ check_status: 'failed' }))
  }, [participantId])

  if (!data) return <span className="text-xs text-gray-500">Loading...</span>

  const isDiscrepant = hasDiscrepancies(data)
  const classes = isDiscrepant ? 'bg-red-900/50 text-red-300' : badgeClasses(data.check_status)

  return (
    <div className="relative inline-block">
      <button
        onClick={() => setShowDetails(!showDetails)}
        className={`rounded-full px-3 py-1 text-xs font-medium ${classes}`}
      >
        {badgeLabel(data)}
      </button>
      {showDetails && isDiscrepant && (
        <div className="absolute left-0 top-full z-10 mt-1 w-64 rounded-lg border border-gray-700 bg-gray-800 p-3 text-sm shadow-lg">
          <p className="mb-1 font-medium text-red-300">Discrepancies</p>
          <ul className="space-y-1 text-gray-300">
            {data.discrepancies?.map((d, i) => (
              <li key={i} className="border-l-2 border-red-600 pl-2">{d}</li>
            ))}
          </ul>
          {data.confidence !== undefined && (
            <p className="mt-2 text-xs text-gray-400">
              Confidence: {(data.confidence * 100).toFixed(0)}%
            </p>
          )}
        </div>
      )}
    </div>
  )
}
