/** WebSocket event message from the backend. */
export interface WsMessage {
  type: 'event'
  data: EventData
}

/** Event payload streamed over WebSocket. */
export interface EventData {
  event_id: string
  event_type: string
  participant_id: string
  trial_id: string | null
  payload: Record<string, unknown>
  created_at: string
}

/** State tracked by the demo reducer. */
export interface DemoState {
  callActive: boolean
  disclosureGiven: boolean
  consentCaptured: boolean
  identityVerified: boolean
  dncBlocked: boolean
  trialName: string
  screeningQuestions: string[]
  eligibilityStatus: string
  availabilityChecking: boolean
  slots: string[]
  appointmentStatus: string
  pickupZip: string
  transportStatus: string
  transportEta: string
  rideId: string
  events: EventData[]
}

/** Actions dispatched by the demo reducer. */
export type DemoAction =
  | { type: 'CALL_STARTED' }
  | { type: 'CALL_ENDED' }
  | { type: 'EVENT_RECEIVED'; event: EventData }
  | { type: 'RESET' }
