import type { EventData } from '../types/events'

interface Props {
  events: EventData[]
}

function eventColor(eventType: string): string {
  if (eventType.includes('verified') || eventType.includes('confirmed') || eventType.includes('booked')) return 'border-emerald-600'
  if (eventType.includes('blocked') || eventType.includes('dnc') || eventType.includes('failed')) return 'border-red-600'
  if (eventType.includes('handoff')) return 'border-yellow-600'
  return 'border-gray-700'
}

/** Scrolling event log feed showing real-time events. */
export function EventsFeed({ events }: Props) {
  const sorted = [...events].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  )

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <h2 className="mb-4 text-lg font-semibold text-gray-300">Events Feed</h2>
      <div className="max-h-80 space-y-2 overflow-y-auto">
        {sorted.length === 0 && (
          <p className="text-sm text-gray-500">No events yet. Start a demo call.</p>
        )}
        {sorted.map((ev, idx) => (
          <div
            key={ev.event_id || `event-${idx}`}
            className={`border-l-2 ${eventColor(ev.event_type)} rounded-r bg-gray-800/50 px-3 py-2`}
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-gray-200">{ev.event_type}</span>
              <span className="text-xs text-gray-500">
                {new Date(ev.created_at).toLocaleTimeString()}
              </span>
            </div>
            {ev.trial_id && (
              <span className="text-xs text-gray-500">{ev.trial_id}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
