import { useEffect, useState } from 'react'
import { getAudioSignedUrl } from '../api/client'

interface AudioPlayerProps {
  gcsPath: string
}

export function AudioPlayer({ gcsPath }: AudioPlayerProps) {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    setError(null)
    getAudioSignedUrl(gcsPath)
      .then((data) => setUrl(data.url))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [gcsPath])

  if (loading) return <span style={{ color: '#888', fontSize: '0.85em' }}>Loading audio...</span>
  if (error) return <span style={{ color: '#c00', fontSize: '0.85em' }}>Audio unavailable</span>
  if (!url) return null

  return (
    <audio controls preload="none" style={{ height: 32, maxWidth: 280 }}>
      <source src={url} type="audio/webm" />
    </audio>
  )
}
