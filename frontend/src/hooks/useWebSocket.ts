import { useEffect, useRef, useCallback, useState } from 'react'
import type { WsMessage } from '../types/events'
import { getEvents } from '../api/client'

const RECONNECT_MS = 1000

/**
 * Auto-reconnecting WebSocket hook for real-time event streaming.
 * Replays historical events from the REST API on every connect (including
 * first load) so the dashboard always shows events that happened before
 * the page was opened or after a Cloud Run restart.
 */
export function useWebSocket(onMessage: (msg: WsMessage) => void) {
  const wsRef = useRef<WebSocket | null>(null)
  const [connected, setConnected] = useState(false)
  const onMessageRef = useRef(onMessage)
  onMessageRef.current = onMessage

  const replayEvents = useCallback(async () => {
    try {
      const events = await getEvents()
      for (const evt of events) {
        const msg: WsMessage = {
          type: 'event',
          data: evt as unknown as WsMessage['data'],
        }
        onMessageRef.current(msg)
      }
    } catch {
      // API unavailable — events will arrive via WebSocket
    }
  }, [])

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/events`
    const ws = new WebSocket(url)

    ws.onopen = () => {
      setConnected(true)
      // Always replay on connect — catches events from before the page
      // opened and after a server restart.
      void replayEvents()
    }

    ws.onmessage = (ev: MessageEvent) => {
      try {
        const msg = JSON.parse(ev.data as string) as WsMessage
        onMessageRef.current(msg)
      } catch {
        // ignore malformed messages
      }
    }

    ws.onclose = () => {
      setConnected(false)
      setTimeout(connect, RECONNECT_MS)
    }

    ws.onerror = () => ws.close()

    wsRef.current = ws
  }, [replayEvents])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])

  return { connected }
}
