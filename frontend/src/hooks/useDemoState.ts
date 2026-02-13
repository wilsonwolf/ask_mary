import { useReducer } from 'react'
import type { DemoState, DemoAction, EventData } from '../types/events'

const INITIAL_STATE: DemoState = {
  callActive: false,
  disclosureGiven: false,
  consentCaptured: false,
  identityVerified: false,
  dncBlocked: false,
  trialName: '',
  screeningQuestions: [],
  eligibilityStatus: '',
  availabilityChecking: false,
  slots: [],
  appointmentStatus: '',
  pickupZip: '',
  pickupAddress: '',
  transportStatus: '',
  transportEta: '',
  rideId: '',
  events: [],
}

function applyEvent(state: DemoState, event: EventData): DemoState {
  const base = { ...state, events: [...state.events, event] }
  switch (event.event_type) {
    case 'outbound_call_initiated':
      return { ...base, callActive: true }
    case 'outreach_attempt':
      return { ...base, callActive: true }
    case 'consent_captured':
      return { ...base, consentCaptured: true, disclosureGiven: true }
    case 'identity_verified':
      return { ...base, identityVerified: true }
    case 'identity_failed':
      return base
    case 'dnc_set':
    case 'dnc_applied':
      return { ...base, dncBlocked: true }
    case 'screening_response_recorded':
      return {
        ...base,
        screeningQuestions: [
          ...base.screeningQuestions,
          `${event.payload?.question_key}: ${event.payload?.answer}`,
        ],
      }
    case 'screening_completed':
      return {
        ...base,
        eligibilityStatus: (event.payload?.status as string) || 'unknown',
        trialName: (event.payload?.trial_name as string) || base.trialName || event.trial_id || '',
      }
    case 'availability_checked':
      return {
        ...base,
        availabilityChecking: false,
        slots: (event.payload?.slots as string[]) || [],
      }
    case 'slot_booked':
    case 'appointment_booked':
      return { ...base, appointmentStatus: 'BOOKED', availabilityChecking: false }
    case 'confirmation_sent':
      return { ...base, appointmentStatus: 'CONFIRMED' }
    case 'confirmation_received':
      return { ...base, appointmentStatus: 'CONFIRMED' }
    case 'transport_booked': {
      const pickupAddr = (event.payload?.pickup_address as string) || ''
      const zip = (event.payload?.zip as string) || (pickupAddr ? pickupAddr.split(' ').pop() || '' : '')
      return {
        ...base,
        transportStatus: 'CONFIRMED',
        transportEta: (event.payload?.eta as string) || '',
        rideId: (event.payload?.ride_id as string) || '',
        pickupZip: zip,
        pickupAddress: pickupAddr,
      }
    }
    case 'transport_failed':
      return { ...base, transportStatus: 'FAILED' }
    case 'handoff_created':
      return base
    default:
      return base
  }
}

function reducer(state: DemoState, action: DemoAction): DemoState {
  switch (action.type) {
    case 'CALL_STARTED':
      return { ...state, callActive: true }
    case 'CALL_ENDED':
      return { ...state, callActive: false }
    case 'EVENT_RECEIVED':
      return applyEvent(state, action.event)
    case 'RESET':
      return INITIAL_STATE
    default:
      return state
  }
}

export function useDemoState() {
  return useReducer(reducer, INITIAL_STATE)
}
