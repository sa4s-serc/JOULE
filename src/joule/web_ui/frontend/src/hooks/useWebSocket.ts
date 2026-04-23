import { useEffect, useRef, useState } from 'react'
import { wsClient } from '../utils/api'

interface UseWebSocketReturn {
  isConnected: boolean
  error: string | null
  send: (message: any) => void
  subscribe: (runId: string, callback: (data: any) => void) => void
  unsubscribe: (runId: string, callback?: (data: any) => void) => void
}

export const useWebSocket = (): UseWebSocketReturn => {
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const subscriptionsRef = useRef<Map<string, Set<(data: any) => void>>>(new Map())

  useEffect(() => {
    // Connect to WebSocket on mount
    const connect = async () => {
      try {
        await wsClient.connect()
        setIsConnected(true)
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to connect')
        setIsConnected(false)
      }
    }

    connect()

    // Set up connection status monitoring
    const checkConnection = setInterval(() => {
      setIsConnected(wsClient.isConnected())
    }, 1000)

    return () => {
      clearInterval(checkConnection)
      wsClient.disconnect()
    }
  }, [])

  const send = (message: any) => {
    try {
      wsClient.send(message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message')
    }
  }

  const subscribe = (runId: string, callback: (data: any) => void) => {
    // Add to local tracking
    if (!subscriptionsRef.current.has(runId)) {
      subscriptionsRef.current.set(runId, new Set())
    }
    subscriptionsRef.current.get(runId)!.add(callback)

    // Subscribe to WebSocket
    wsClient.subscribeToRun(runId, callback)
  }

  const unsubscribe = (runId: string, callback?: (data: any) => void) => {
    // Remove from local tracking
    const subscriptions = subscriptionsRef.current.get(runId)
    if (subscriptions) {
      if (callback) {
        subscriptions.delete(callback)
        if (subscriptions.size === 0) {
          subscriptionsRef.current.delete(runId)
        }
      } else {
        subscriptionsRef.current.delete(runId)
      }
    }

    // Unsubscribe from WebSocket
    wsClient.unsubscribeFromRun(runId, callback)
  }

  return {
    isConnected,
    error,
    send,
    subscribe,
    unsubscribe,
  }
}

// Hook for subscribing to run updates
export const useRunSubscription = (runId: string | null, callback: (data: any) => void) => {
  const { subscribe, unsubscribe } = useWebSocket()
  const callbackRef = useRef(callback)

  // Update callback ref when callback changes
  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  useEffect(() => {
    if (!runId) return

    const wrappedCallback = (data: any) => {
      callbackRef.current(data)
    }

    subscribe(runId, wrappedCallback)

    return () => {
      unsubscribe(runId, wrappedCallback)
    }
  }, [runId, subscribe, unsubscribe])
}
