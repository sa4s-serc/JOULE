import axios, { AxiosInstance } from 'axios'

const API_BASE_URL = '/api'

const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120_000,
  headers: { 'Content-Type': 'application/json' },
})

export const apiClient = {
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

  async runBaseline(projectPath: string, config: any): Promise<any> {
    const { data } = await api.post(
      `/projects/${encodeURIComponent(projectPath)}/baseline`,
      config,
    )
    return data
  },

  async runOptimization(projectPath: string, config: any): Promise<any> {
    const { data } = await api.post(
      `/projects/${encodeURIComponent(projectPath)}/optimize`,
      config,
    )
    return data
  },

  async applyCandidate(runId: string, config: any): Promise<any> {
    const { data } = await api.post(`/runs/${runId}/apply`, config)
    return data
  },
}

type WebSocketMessageHandler = (message: any) => void

class WebSocketClient {
  private ws: WebSocket | null = null
  private subscribers: Map<string, Set<WebSocketMessageHandler>> = new Map()
  private globalSubscribers: Set<WebSocketMessageHandler> = new Set()
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private pingTimer: ReturnType<typeof setInterval> | null = null
  private shouldReconnect = true

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      return
    }

    this.shouldReconnect = true

    try {
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${wsProtocol}//${window.location.host}/ws`
      this.ws = new WebSocket(wsUrl)

      this.ws.onopen = () => {
        this.startPing()
      }

      this.ws.onmessage = (event) => {
        try {
          this.dispatch(JSON.parse(event.data))
        } catch {
          return
        }
      }

      this.ws.onclose = () => {
        this.stopPing()
        this.ws = null
        if (this.shouldReconnect) {
          this.scheduleReconnect()
        }
      }

      this.ws.onerror = () => {
        this.stopPing()
      }
    } catch {
      this.scheduleReconnect()
    }
  }

  disconnect(): void {
    this.shouldReconnect = false
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
    this.send({ type: 'subscribe_run', run_id: runId })

    return () => {
      const subs = this.subscribers.get(runId)
      if (!subs) return
      subs.delete(handler)
      if (subs.size === 0) {
        this.subscribers.delete(runId)
        this.send({ type: 'unsubscribe_run', run_id: runId })
      }
    }
  }

  onMessage(handler: WebSocketMessageHandler): () => void {
    this.globalSubscribers.add(handler)
    return () => {
      this.globalSubscribers.delete(handler)
    }
  }

  private dispatch(message: any): void {
    for (const handler of this.globalSubscribers) {
      try {
        handler(message)
      } catch {
        continue
      }
    }

    if (message.run_id) {
      const subs = this.subscribers.get(message.run_id)
      if (!subs) return
      for (const handler of subs) {
        try {
          handler(message)
        } catch {
          continue
        }
      }
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer || !this.shouldReconnect) {
      return
    }
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      if (this.shouldReconnect) {
        this.connect()
      }
    }, 3000)
  }

  private startPing(): void {
    this.stopPing()
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

if (typeof window !== 'undefined') {
  wsClient.connect()
}

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
