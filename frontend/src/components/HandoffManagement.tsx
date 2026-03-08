import { useEffect, useState } from 'react'
import { assignHandoff, getHandoffQueue, resolveHandoff } from '../api/client'

interface Handoff {
  handoff_id: string
  participant_id: string
  reason: string
  severity: string
  status: string
  summary: string | null
  assigned_to: string | null
  created_at: string
}

function severityBadge(severity: string): string {
  if (severity === 'HANDOFF_NOW') return 'bg-red-900/50 text-red-300'
  if (severity === 'CALLBACK_TICKET') return 'bg-yellow-900/50 text-yellow-300'
  return 'bg-gray-800 text-gray-400'
}

function HandoffRow({ handoff, onUpdate }: { handoff: Handoff; onUpdate: () => void }) {
  const [assigning, setAssigning] = useState(false)
  const [resolving, setResolving] = useState(false)
  const [assignee, setAssignee] = useState('')
  const [resolution, setResolution] = useState('')
  const [resolver, setResolver] = useState('')

  async function handleAssign() {
    if (!assignee.trim()) return
    await assignHandoff(handoff.handoff_id, assignee)
    setAssigning(false)
    onUpdate()
  }

  async function handleResolve() {
    if (!resolution.trim() || !resolver.trim()) return
    await resolveHandoff(handoff.handoff_id, resolution, resolver)
    setResolving(false)
    onUpdate()
  }

  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${severityBadge(handoff.severity)}`}>
            {handoff.severity}
          </span>
          <span className="text-xs text-gray-500">{handoff.status}</span>
        </div>
        <span className="text-xs text-gray-600">{new Date(handoff.created_at).toLocaleString()}</span>
      </div>
      <p className="mb-1 text-sm text-gray-300">{handoff.reason.replace(/_/g, ' ')}</p>
      {handoff.summary && <p className="mb-2 text-xs text-gray-500">{handoff.summary}</p>}
      {handoff.assigned_to && (
        <p className="mb-2 text-xs text-blue-400">Assigned to: {handoff.assigned_to}</p>
      )}

      {handoff.status !== 'resolved' && (
        <div className="flex gap-2">
          {!assigning && !resolving && (
            <>
              <button
                onClick={() => setAssigning(true)}
                className="rounded bg-blue-800 px-3 py-1 text-xs text-blue-200 hover:bg-blue-700"
              >
                Assign
              </button>
              <button
                onClick={() => setResolving(true)}
                className="rounded bg-emerald-800 px-3 py-1 text-xs text-emerald-200 hover:bg-emerald-700"
              >
                Resolve
              </button>
            </>
          )}
          {assigning && (
            <div className="flex gap-2">
              <input
                value={assignee}
                onChange={(e) => setAssignee(e.target.value)}
                placeholder="Coordinator name"
                className="rounded border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-gray-200"
              />
              <button onClick={handleAssign} className="rounded bg-blue-700 px-2 py-1 text-xs text-white">
                Confirm
              </button>
              <button onClick={() => setAssigning(false)} className="text-xs text-gray-500">
                Cancel
              </button>
            </div>
          )}
          {resolving && (
            <div className="flex flex-col gap-2">
              <input
                value={resolution}
                onChange={(e) => setResolution(e.target.value)}
                placeholder="Resolution notes"
                className="rounded border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-gray-200"
              />
              <div className="flex gap-2">
                <input
                  value={resolver}
                  onChange={(e) => setResolver(e.target.value)}
                  placeholder="Resolved by"
                  className="rounded border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-gray-200"
                />
                <button onClick={handleResolve} className="rounded bg-emerald-700 px-2 py-1 text-xs text-white">
                  Confirm
                </button>
                <button onClick={() => setResolving(false)} className="text-xs text-gray-500">
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/** Panel showing handoff queue with assign and resolve actions. */
export function HandoffManagement() {
  const [handoffs, setHandoffs] = useState<Handoff[]>([])
  const [loading, setLoading] = useState(true)

  function loadHandoffs() {
    setLoading(true)
    getHandoffQueue()
      .then((data) => setHandoffs(data as unknown as Handoff[]))
      .catch(() => setHandoffs([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadHandoffs()
  }, [])

  const openHandoffs = handoffs.filter((h) => h.status !== 'resolved')

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-orange-400">Handoff Queue</h2>
        <span className="text-xs text-gray-500">{openHandoffs.length} open</span>
      </div>
      {loading && <p className="text-sm text-gray-500">Loading...</p>}
      {!loading && openHandoffs.length === 0 && (
        <p className="text-sm text-gray-500">No open handoffs</p>
      )}
      <div className="space-y-3">
        {openHandoffs.map((h) => (
          <HandoffRow key={h.handoff_id} handoff={h} onUpdate={loadHandoffs} />
        ))}
      </div>
    </div>
  )
}
