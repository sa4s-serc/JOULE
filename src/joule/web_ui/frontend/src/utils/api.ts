/**
 * JOULE Web UI – API Client & WebSocket Client
 *
 * Centralises all backend communication so every React page/hook
 * imports from a single place.
 */

import axios, { AxiosInstance } from 'axios'

// ---------------------------------------------------------------------------
//  Axios instance
// ---------------------------------------------------------------------------

const API_BASE_URL = '/api'

const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120_000, // 2 min for long-running discovery
  headers: { 'Content-Type': 'application/json' },
})

// ---------------------------------------------------------------------------
//  API Client
// ---------------------------------------------------------------------------

export const apiClient = {
  // ---- Projects ----
  async getProjects(): Promise<any[]> {
    const { data } = await api.get('/projects')
    return data
  },

  async getProject(projectPath: string): Promise<any> {
    const { data } = await api.get(`/projects/${encodeURIComponent(projectPath)}`)
    return data
  },

  async runProjectDoctor(projectPath: string): Promise<any> {
    const { data } = await api.post(`/projects/${encodeURIComponent(projectPath)}/doctor`)
    return data
  },

  // ---- Discovery ----
  async discoverTargets(projectPath: string): Promise<any[]> {
    const { data } = await api.get(`/projects/${encodeURIComponent(projectPath)}/discover/targets`)
    return data
  },

  async discoverWorkloads(projectPath: string, targetQualname: string): Promise<any[]> {
    const { data } = await api.get(
      `/projects/${encodeURIComponent(projectPath)}/discover/workloads/${encodeURIComponent(targetQualname)}`
    )
    return data
  },

  // ---- Runs ----
  async getRuns(): Promise<any[]> {
    const { data } = await api.get('/runs')
    return data
  },

  async getRun(runId: string): Promise<any> {
    const { data } = await api.get(`/runs/${runId}`)
    return data
  },

  async getActiveRuns(): Promise<any> {
    const { data } = await api.get('/runs/active')
    return data
  },

  async getRunArtifacts(runId: string): Promise<any[]> {
    const { data } = await api.get(`/runs/${runId}/artifacts`)
    return data
  },

  // ---- Baseline ----
  async runBaseline(projectPath: string, config: any): Promise<any> {
    const { data } = await api.post(
      `/projects/${encodeURIComponent(projectPath)}/baseline`,
      config,
    )
    return data
  },

  // ---- Optimization ----
  async runOptimization(projectPath: string, config: any): Promise<any> {
    const { data } = await api.post(
      `/projects/${encodeURIComponent(projectPath)}/optimize`,
      config,
    )
    return data
  },

  // ---- Apply ----
  async applyCandidate(runId: string, config: any): Promise<any> {
    const { data } = await api.post(`/runs/${runId}/apply`, config)
    return data
  },
}

// ---------------------------------------------------------------------------
//  WebSocket Client
// ---------------------------------------------------------------------------

type WebSocketMessageHandler = (message: any) => void

class WebSocketClient {
  private ws: WebSocket | null = null
  private subscribers: Map<string, Set<WebSocketMessageHandler>> = new Map()
  private globalSubscribers: Set<WebSocketMessageHandler> = new Set()
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private pingTimer: ReturnType<typeof setInterval> | null = null

  constructor() {}


  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return

    try {
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${wsProtocol}//${window.location.host}/ws`
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        console.log('[WS] Connected')
        this.startPing()
      }

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          this.dispatch(message)
        } catch {
          console.warn('[WS] Failed to parse message', event.data)
        }
      }

      this.ws.onclose = () => {
        console.log('[WS] Disconnected')
        this.stopPing()
        this.scheduleReconnect()
      }

      this.ws.onerror = (error) => {
        console.error('[WS] Error', error)
      }
    } catch (error) {
      console.error('[WS] Connection failed', error)
      this.scheduleReconnect()
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.stopPing()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  send(message: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    }
  }

  subscribeRun(runId: string, handler: WebSocketMessageHandler): () => void {
    if (!this.subscribers.has(runId)) {
      this.subscribers.set(runId, new Set())
    }
    this.subscribers.get(runId)!.add(handler)

    // Ask the server to subscribe us
    this.send({ type: 'subscribe_run', run_id: runId })

    return () => {
      const subs = this.subscribers.get(runId)
      if (subs) {
        subs.delete(handler)
        if (subs.size === 0) {
          this.subscribers.delete(runId)
          this.send({ type: 'unsubscribe_run', run_id: runId })
        }
      }
    }
  }

  onMessage(handler: WebSocketMessageHandler): () => void {
    this.globalSubscribers.add(handler)
    return () => { this.globalSubscribers.delete(handler) }
  }

  // ---- Private ----

  private dispatch(message: any): void {
    // Global handlers
    for (const handler of this.globalSubscribers) {
      try { handler(message) } catch { /* ignore */ }
    }

    // Run-specific handlers
    if (message.run_id) {
      const subs = this.subscribers.get(message.run_id)
      if (subs) {
        for (const handler of subs) {
          try { handler(message) } catch { /* ignore */ }
        }
      }
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
    }, 3000)
  }

  private startPing(): void {
    this.pingTimer = setInterval(() => {
      this.send({ type: 'ping', timestamp: Date.now() })
    }, 30_000)
  }

  private stopPing(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer)
      this.pingTimer = null
    }
  }
}

export const wsClient = new WebSocketClient()

// Auto-connect on module load
if (typeof window !== 'undefined') {
  wsClient.connect()
}

// ---------------------------------------------------------------------------
//  Utility helpers
// ---------------------------------------------------------------------------

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const k = 1024
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${units[i]}`
}

export function formatImprovement(ratio: number): string {
  const improvement = (1 - ratio) * 100
  const sign = improvement > 0 ? '-' : '+'
  return `${sign}${Math.abs(improvement).toFixed(1)}%`
}

export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}m ${secs.toFixed(0)}s`
}

export default api
