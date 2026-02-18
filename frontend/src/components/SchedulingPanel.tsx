interface Props {
  availabilityChecking: boolean
  slots: string[]
  appointmentStatus: string
}

function statusBadge(status: string): string {
  if (status === 'HELD') return 'bg-yellow-900/60 text-yellow-300'
  if (status === 'BOOKED') return 'bg-blue-900/60 text-blue-300'
  if (status === 'CONFIRMED') return 'bg-emerald-900/60 text-emerald-300'
  return 'bg-gray-800 text-gray-400'
}

/** Panel 3: Availability spinner, offered slots, appointment status. */
export function SchedulingPanel({ availabilityChecking, slots, appointmentStatus }: Props) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <h2 className="mb-4 text-lg font-semibold text-purple-400">Scheduling</h2>
      {availabilityChecking && (
        <div className="mb-3 flex items-center gap-2 text-sm text-gray-400">
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-purple-400 border-t-transparent" />
          Checking availability...
        </div>
      )}
      {slots.length > 0 && (
        <div className="mb-3">
          <p className="mb-1 text-xs font-medium uppercase text-gray-500">Available Slots</p>
          <ul className="space-y-1 text-sm text-gray-300">
            {slots.map((s, i) => (
              <li key={i} className="rounded bg-gray-800 px-2 py-1">{s}</li>
            ))}
          </ul>
        </div>
      )}
      {appointmentStatus && (
        <span className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${statusBadge(appointmentStatus)}`}>
          {appointmentStatus}
        </span>
      )}
      {!availabilityChecking && slots.length === 0 && !appointmentStatus && (
        <p className="text-sm text-gray-500">Awaiting scheduling...</p>
      )}
    </div>
  )
}
