import { useEffect, useState } from 'react'
import { getParticipantDetail } from '../api/client'
import { AdversarialStatusBadge } from './AdversarialStatusBadge'
import { AudioPlayer } from './AudioPlayer'

interface TrialEnrollment {
  trial_id: string
  pipeline_status: string
  eligibility_status: string
}

interface ConversationSummary {
  conversation_id: string
  channel: string
  direction: string
  status: string
  started_at: string
  audio_gcs_path: string | null
}

interface AppointmentSummary {
  appointment_id: string
  trial_id: string
  visit_type: string
  scheduled_at: string
  status: string
  site_name: string | null
}

interface ParticipantData {
  participant_id: string
  first_name: string
  last_name: string
  phone: string
  identity_status: string
  created_at: string
  trials: TrialEnrollment[]
  conversations: ConversationSummary[]
  appointments: AppointmentSummary[]
}

interface Props {
  participantId: string
  onClose: () => void
}

function identityBadge(status: string): string {
  if (status === 'verified') return 'bg-emerald-900/50 text-emerald-300'
  if (status === 'wrong_person') return 'bg-red-900/50 text-red-300'
  return 'bg-yellow-900/50 text-yellow-300'
}

function pipelineBadge(status: string): string {
  if (status === 'completed' || status === 'confirmed') return 'text-emerald-400'
  if (status === 'ineligible' || status === 'cancelled') return 'text-red-400'
  return 'text-blue-400'
}

/** Modal-style detail view for a single participant. */
export function ParticipantDetail({ participantId, onClose }: Props) {
  const [data, setData] = useState<ParticipantData | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getParticipantDetail(participantId)
      .then((result) => {
        if ('error' in result) {
          setError(result.error as string)
        } else {
          setData(result as unknown as ParticipantData)
        }
      })
      .catch(() => setError('Failed to load participant'))
  }, [participantId])

  if (error) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-6">
          <p className="text-red-400">{error}</p>
          <button onClick={onClose} className="mt-4 text-sm text-gray-400 hover:text-gray-200">
            Close
          </button>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
        <div className="rounded-xl border border-gray-800 bg-gray-900 p-6">
          <p className="text-gray-400">Loading...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="max-h-[80vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-gray-800 bg-gray-900 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-6 flex items-start justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-100">
              {data.first_name} {data.last_name}
            </h2>
            <p className="text-sm text-gray-500">{data.phone}</p>
          </div>
          <div className="flex items-center gap-3">
            <span className={`rounded-full px-3 py-1 text-xs font-medium ${identityBadge(data.identity_status)}`}>
              {data.identity_status}
            </span>
            <AdversarialStatusBadge participantId={participantId} />
            <button onClick={onClose} className="text-gray-500 hover:text-gray-300">
              X
            </button>
          </div>
        </div>

        {/* Trial Enrollments */}
        <div className="mb-5">
          <h3 className="mb-2 text-sm font-semibold uppercase text-gray-500">Trial Enrollments</h3>
          {data.trials.length === 0 && <p className="text-xs text-gray-600">None</p>}
          <div className="space-y-2">
            {data.trials.map((t) => (
              <div key={t.trial_id} className="flex items-center justify-between rounded border border-gray-800 bg-gray-950 px-3 py-2">
                <span className="text-sm text-gray-300">{t.trial_id}</span>
                <div className="flex gap-3 text-xs">
                  <span className={pipelineBadge(t.pipeline_status)}>{t.pipeline_status}</span>
                  <span className="text-gray-500">{t.eligibility_status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Upcoming Appointments */}
        <div className="mb-5">
          <h3 className="mb-2 text-sm font-semibold uppercase text-gray-500">Upcoming Appointments</h3>
          {data.appointments.length === 0 && <p className="text-xs text-gray-600">None</p>}
          <div className="space-y-2">
            {data.appointments.map((a) => (
              <div key={a.appointment_id} className="flex items-center justify-between rounded border border-gray-800 bg-gray-950 px-3 py-2">
                <div>
                  <span className="text-sm text-gray-300">{a.visit_type}</span>
                  {a.site_name && <span className="ml-2 text-xs text-gray-500">@ {a.site_name}</span>}
                </div>
                <div className="text-xs text-gray-400">{new Date(a.scheduled_at).toLocaleString()}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Conversations */}
        <div>
          <h3 className="mb-2 text-sm font-semibold uppercase text-gray-500">Recent Conversations</h3>
          {data.conversations.length === 0 && <p className="text-xs text-gray-600">None</p>}
          <div className="space-y-2">
            {data.conversations.map((c) => (
              <div key={c.conversation_id} className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
                <div className="flex items-center justify-between">
                  <div className="flex gap-2 text-xs">
                    <span className="text-gray-400">{c.channel}</span>
                    <span className="text-gray-600">{c.direction}</span>
                  </div>
                  <div className="flex gap-2 text-xs">
                    <span className="text-gray-500">{c.status}</span>
                    <span className="text-gray-600">{new Date(c.started_at).toLocaleString()}</span>
                  </div>
                </div>
                {c.audio_gcs_path && (
                  <div className="mt-1">
                    <AudioPlayer gcsPath={c.audio_gcs_path} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
