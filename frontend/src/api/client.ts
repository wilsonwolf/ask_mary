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
