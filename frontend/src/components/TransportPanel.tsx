interface Props {
  pickupZip: string
  pickupAddress: string
  transportStatus: string
  transportEta: string
  rideId: string
}

/** Panel 4: Transport / ride status, ETA, ride ID. */
export function TransportPanel({ pickupZip, pickupAddress, transportStatus, transportEta, rideId }: Props) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-5">
      <h2 className="mb-4 text-lg font-semibold text-orange-400">Transport</h2>
      {pickupZip || pickupAddress ? (
        <div className="space-y-2 text-sm">
          {pickupAddress && (
            <p className="text-gray-300">
              Pickup: <span className="text-gray-100">{pickupAddress}</span>
            </p>
          )}
          <p className="text-gray-300">
            Pickup ZIP: <span className="font-mono text-gray-100">{pickupZip}</span>
          </p>
          <p className="text-gray-300">
            Status:{' '}
            <span className={transportStatus === 'CONFIRMED' ? 'text-emerald-400' : 'text-yellow-400'}>
              {transportStatus}
            </span>
          </p>
          {transportEta && (
            <p className="text-gray-300">
              ETA: <span className="text-gray-100">{transportEta}</span>
            </p>
          )}
          {rideId && (
            <p className="text-gray-400">
              Ride: <span className="font-mono text-xs">{rideId}</span>
            </p>
          )}
        </div>
      ) : (
        <p className="text-sm text-gray-500">Awaiting transport request...</p>
      )}
    </div>
  )
}
