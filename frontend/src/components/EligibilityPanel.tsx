interface Props {
  trialName: string
  screeningQuestions: string[]
  eligibilityStatus: string
}

function statusColor(status: string): string {
  if (status === 'eligible') return 'text-emerald-400'
  if (status === 'ineligible') return 'text-red-400'
  if (status === 'provisional') return 'text-yellow-400'
  return 'text-gray-400'
}

/** Panel 2: Trial name, screening Q&A, eligibility result. */
export function EligibilityPanel({ trialName, screeningQuestions, eligibilityStatus }: Props) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <h2 className="mb-4 text-lg font-semibold text-blue-400">Eligibility</h2>
      {trialName ? (
        <p className="mb-2 text-sm text-gray-300">
          Trial: <span className="font-medium text-gray-100">{trialName}</span>
        </p>
      ) : (
        <p className="text-sm text-gray-500">Awaiting screening...</p>
      )}
      {screeningQuestions.length > 0 && (
        <div className="mb-3">
          <p className="mb-1 text-xs font-medium uppercase text-gray-500">Screening Questions</p>
          <ul className="space-y-1 text-sm text-gray-300">
            {screeningQuestions.map((q, i) => (
              <li key={i} className="border-l-2 border-gray-700 pl-2">{q}</li>
            ))}
          </ul>
        </div>
      )}
      {eligibilityStatus && (
        <p className={`text-sm font-semibold ${statusColor(eligibilityStatus)}`}>
          {eligibilityStatus.toUpperCase()}
        </p>
      )}
    </div>
  )
}
