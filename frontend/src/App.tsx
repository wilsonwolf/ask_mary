import { useCallback, useState } from 'react'
import { AnalyticsSummary } from './components/AnalyticsSummary'
import { CallPanel } from './components/CallPanel'
import { CoordinatorConfig } from './components/CoordinatorConfig'
import { DemoButton } from './components/DemoButton'
import { EligibilityPanel } from './components/EligibilityPanel'
import { EventsFeed } from './components/EventsFeed'
import { HandoffManagement } from './components/HandoffManagement'
import { ParticipantDetail } from './components/ParticipantDetail'
import { SchedulingPanel } from './components/SchedulingPanel'
import { TransportPanel } from './components/TransportPanel'
import { useDemoState } from './hooks/useDemoState'
import { useWebSocket } from './hooks/useWebSocket'
import type { WsMessage } from './types/events'

export default function App() {
  const [state, dispatch] = useDemoState()
  const [selectedParticipantId, setSelectedParticipantId] = useState<string | null>(null)

  const handleWsMessage = useCallback(
    (msg: WsMessage) => {
      if (msg.type === 'event') {
        dispatch({ type: 'EVENT_RECEIVED', event: msg.data })
      }
    },
    [dispatch],
  )

  const { connected } = useWebSocket(handleWsMessage)

  return (
    <div className="min-h-screen bg-gray-950 p-6">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-100">Ask Mary</h1>
          <p className="text-sm text-gray-500">AI Clinical Trial Scheduling Agent</p>
        </div>
        <div className="flex items-center gap-4">
          <CoordinatorConfig />
          <span className="flex items-center gap-1.5 text-xs">
            <span
              className={`inline-block h-2 w-2 rounded-full ${connected ? 'bg-emerald-400' : 'bg-red-400'}`}
            />
            {connected ? 'Connected' : 'Disconnected'}
          </span>
          <DemoButton onCallStarted={() => dispatch({ type: 'CALL_STARTED' })} />
        </div>
      </div>

      {/* Analytics Summary */}
      <AnalyticsSummary />

      {/* 2x2 Panel Grid */}
      <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
        <CallPanel
          callActive={state.callActive}
          disclosureGiven={state.disclosureGiven}
          consentCaptured={state.consentCaptured}
          identityVerified={state.identityVerified}
          dncBlocked={state.dncBlocked}
        />
        <EligibilityPanel
          trialName={state.trialName}
          screeningQuestions={state.screeningQuestions}
          eligibilityStatus={state.eligibilityStatus}
        />
        <SchedulingPanel
          availabilityChecking={state.availabilityChecking}
          slots={state.slots}
          appointmentStatus={state.appointmentStatus}
        />
        <TransportPanel
          pickupZip={state.pickupZip}
          pickupAddress={state.pickupAddress}
          transportStatus={state.transportStatus}
          transportEta={state.transportEta}
          rideId={state.rideId}
        />
      </div>

      {/* Handoff Management */}
      <div className="mb-6">
        <HandoffManagement />
      </div>

      {/* Events Feed */}
      <EventsFeed events={state.events} />

      {/* Participant Detail Modal */}
      {selectedParticipantId && (
        <ParticipantDetail
          participantId={selectedParticipantId}
          onClose={() => setSelectedParticipantId(null)}
        />
      )}
    </div>
  )
}
