/** Thin fetch wrapper for dashboard REST endpoints. */

const BASE = ''

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

export function getParticipants() {
  return fetchJson<Record<string, unknown>[]>('/api/participants')
}

export function getAppointments() {
  return fetchJson<Record<string, unknown>[]>('/api/appointments')
}

export function getHandoffQueue() {
  return fetchJson<Record<string, unknown>[]>('/api/handoff-queue')
}

export function getConversations() {
  return fetchJson<Record<string, unknown>[]>('/api/conversations')
}

export function getEvents() {
  return fetchJson<Record<string, unknown>[]>('/api/events')
}

export function getAnalyticsSummary() {
  return fetchJson<Record<string, unknown>>('/api/analytics/summary')
}

export function getDemoConfig() {
  return fetchJson<Record<string, unknown>>('/api/demo/config')
}

export function startDemoCall(participantId: string, trialId: string) {
  return fetchJson<Record<string, unknown>>('/api/demo/start-call', {
    method: 'POST',
    body: JSON.stringify({ participant_id: participantId, trial_id: trialId }),
  })
}

export function updateCoordinatorPhone(trialId: string, phone: string) {
  return fetchJson<Record<string, unknown>>(`/api/trials/${trialId}/coordinator`, {
    method: 'PATCH',
    body: JSON.stringify({ coordinator_phone: phone }),
  })
}

export function getParticipantDetail(participantId: string) {
  return fetchJson<Record<string, unknown>>(`/api/participants/${participantId}`)
}

export function getAdversarialStatus(participantId: string) {
  return fetchJson<Record<string, unknown>>(
    `/api/participants/${participantId}/adversarial-status`,
  )
}

export function resolveHandoff(handoffId: string, resolution: string, resolvedBy: string) {
  return fetchJson<Record<string, unknown>>(`/api/handoffs/${handoffId}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ resolution, resolved_by: resolvedBy }),
  })
}

export function assignHandoff(handoffId: string, assignedTo: string) {
  return fetchJson<Record<string, unknown>>(`/api/handoffs/${handoffId}/assign`, {
    method: 'POST',
    body: JSON.stringify({ assigned_to: assignedTo }),
  })
}

export function getAudioSignedUrl(gcsPath: string) {
  return fetchJson<{ url: string; ttl_seconds: number }>('/webhooks/audio/signed-url', {
    method: 'POST',
    body: JSON.stringify({ gcs_path: gcsPath }),
  })
}
