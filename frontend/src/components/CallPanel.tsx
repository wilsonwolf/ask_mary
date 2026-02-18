interface Props {
  callActive: boolean
  disclosureGiven: boolean
  consentCaptured: boolean
  identityVerified: boolean
  dncBlocked: boolean
}

function StatusDot({ active, label }: { active: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span
        className={`inline-block h-3 w-3 rounded-full ${active ? 'bg-emerald-400' : 'bg-gray-600'}`}
      />
      <span className={active ? 'text-gray-100' : 'text-gray-500'}>{label}</span>
    </div>
  )
}

/** Panel 1: Call status, disclosure, consent, identity, DNC. */
export function CallPanel({ callActive, disclosureGiven, consentCaptured, identityVerified, dncBlocked }: Props) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <h2 className="mb-4 text-lg font-semibold text-emerald-400">Call Status</h2>
      <div className="space-y-2">
        <StatusDot active={callActive} label={callActive ? 'Call Active' : 'No Active Call'} />
        <StatusDot active={disclosureGiven} label="AI Disclosure Given" />
        <StatusDot active={consentCaptured} label="Consent Captured" />
        <StatusDot active={identityVerified} label="Identity Verified" />
        {dncBlocked && (
          <div className="mt-2 rounded bg-red-900/50 px-3 py-1 text-sm text-red-300">
            DNC — Contact Blocked
          </div>
        )}
      </div>
    </div>
  )
}
