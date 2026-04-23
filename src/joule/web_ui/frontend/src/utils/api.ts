import axios, { AxiosInstance, AxiosResponse } from 'axios'
import { 
  Project, 
  TargetSpec, 
  WorkloadSpec, 
  Run, 
  BaselineConfig,
  OptimizationConfig,
  ApplyConfig,
  WebSocketMessage 
} from '../types'

// API base configuration
const API_BASE_URL = 'http://localhost:8000'

class ApiClient {
  private client: AxiosInstance

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    })

    // Request interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        console.error('API Error:', error.response?.data || error.message)
        throw error
      }
    )
  }

  // Projects API
  async getProjects(): Promise<Project[]> {
    const response: AxiosResponse<Project[]> = await this.client.get('/api/projects')
    return response.data
  }

  async getProject(projectPath: string): Promise<Project> {
    const response: AxiosResponse<Project> = await this.client.get(`/api/projects/${encodeURIComponent(projectPath)}`)
    return response.data
  }

  async runProjectDoctor(projectPath: string): Promise<any> {
    const response: AxiosResponse<any> = await this.client.post(`/api/projects/${encodeURIComponent(projectPath)}/doctor`)
    return response.data
  }

  // Discovery API
  async discoverTargets(projectPath: string): Promise<TargetSpec[]> {
    const response: AxiosResponse<TargetSpec[]> = await this.client.get(
      `/api/projects/${encodeURIComponent(projectPath)}/discover/targets`
    )
    return response.data
  }

  async discoverWorkloads(projectPath: string, targetQualname: string): Promise<WorkloadSpec[]> {
    const response: AxiosResponse<WorkloadSpec[]> = await this.client.get(
      `/api/projects/${encodeURIComponent(projectPath)}/discover/workloads/${encodeURIComponent(targetQualname)}`
    )
    return response.data
  }

  // Baseline API
  async runBaseline(projectPath: string, config: BaselineConfig): Promise<any> {
    const response: AxiosResponse<any> = await this.client.post(
      `/api/projects/${encodeURIComponent(projectPath)}/baseline`,
      config
    )
    return response.data
  }

  // Optimization API
  async runOptimization(projectPath: string, config: OptimizationConfig): Promise<any> {
    const response: AxiosResponse<any> = await this.client.post(
      `/api/projects/${encodeURIComponent(projectPath)}/optimize`,
      config
    )
    return response.data
  }

  // Runs API
  async getRuns(projectPath: string = '.'): Promise<Run[]> {
    const response: AxiosResponse<Run[]> = await this.client.get('/api/runs', {
      params: { project_path: projectPath }
    })
    return response.data
  }

  async getRun(runId: string, projectPath: string = '.'): Promise<any> {
    const response: AxiosResponse<any> = await this.client.get(`/api/runs/${runId}`, {
      params: { project_path: projectPath }
    })
    return response.data
  }

  async applyCandidate(runId: string, config: ApplyConfig, projectPath: string = '.'): Promise<any> {
    const response: AxiosResponse<any> = await this.client.post(
      `/api/runs/${runId}/apply`,
      config,
      { params: { project_path: projectPath } }
    )
    return response.data
  }

  async getRunArtifacts(runId: string, projectPath: string = '.'): Promise<any[]> {
    const response: AxiosResponse<any[]> = await this.client.get(
      `/api/runs/${runId}/artifacts`,
      { params: { project_path: projectPath } }
    )
    return response.data
  }

  async downloadArtifact(runId: string, artifactName: string, projectPath: string = '.'): Promise<Blob> {
    const response: AxiosResponse<Blob> = await this.client.get(
      `/api/runs/${runId}/artifacts/${artifactName}`,
      { 
        params: { project_path: projectPath },
        responseType: 'blob'
      }
    )
    return response.data
  }
}

// Create singleton instance
export const apiClient = new ApiClient()

// WebSocket client for real-time updates
export class WebSocketClient {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private subscriptions: Set<string> = new Set()
  private messageHandlers: Map<string, ((data: any) => void)[]> = new Map()

  constructor(private url: string = 'ws://localhost:8000/ws') {}

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url)

        this.ws.onopen = () => {
          console.log('WebSocket connected')
          this.reconnectAttempts = 0
          resolve()
        }

        this.ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data)
            this.handleMessage(message)
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error)
          }
        }

        this.ws.onclose = () => {
          console.log('WebSocket disconnected')
          this.attemptReconnect()
        }

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error)
          reject(error)
        }
      } catch (error) {
        reject(error)
      }
    })
  }

  disconnect() {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  subscribeToRun(runId: string, callback: (data: any) => void) {
    this.subscriptions.add(runId)
    
    // Add callback for this run
    if (!this.messageHandlers.has(runId)) {
      this.messageHandlers.set(runId, [])
    }
    this.messageHandlers.get(runId)!.push(callback)

    // Send subscription message
    this.send({
      type: 'subscribe_run',
      run_id: runId
    })
  }

  unsubscribeFromRun(runId: string, callback?: (data: any) => void) {
    this.subscriptions.delete(runId)
    
    if (callback) {
      const handlers = this.messageHandlers.get(runId)
      if (handlers) {
        const index = handlers.indexOf(callback)
        if (index > -1) {
          handlers.splice(index, 1)
        }
      }
    } else {
      this.messageHandlers.delete(runId)
    }

    // Send unsubscription message
    this.send({
      type: 'unsubscribe_run',
      run_id: runId
    })
  }

  send(message: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message))
    }
  }

  private handleMessage(message: WebSocketMessage) {
    const { type, run_id, data } = message
    
    if (type === 'run_update' && run_id) {
      const handlers = this.messageHandlers.get(run_id)
      if (handlers) {
        handlers.forEach(callback => callback(data))
      }
    }
  }

  private attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`)
      
      setTimeout(() => {
        this.connect().catch(() => {
          // Reconnect failed, will try again
        })
      }, this.reconnectDelay * this.reconnectAttempts)
    }
  }

  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN
  }
}

// Create singleton WebSocket client
export const wsClient = new WebSocketClient()

// Utility functions
export const formatBytes = (bytes: number): string => {
  const mb = bytes / (1024 * 1024)
  return `${mb.toFixed(1)} MB`
}

export const formatImprovement = (ratio: number): string => {
  const improvement = (1 - ratio) * 100
  const sign = improvement > 0 ? '-' : '+'
  return `${sign}${Math.abs(improvement).toFixed(1)}%`
}

export const formatDuration = (start: string, end?: string): string => {
  if (!end) return 'Running...'
  const duration = new Date(end).getTime() - new Date(start).getTime()
  const minutes = Math.floor(duration / 60000)
  const seconds = Math.floor((duration % 60000) / 1000)
  return `${minutes}m ${seconds}s`
}

export const getStatusColor = (status: string): string => {
  switch (status) {
    case 'completed': return 'joule-status-completed'
    case 'running': return 'joule-status-running'
    case 'failed': return 'joule-status-failed'
    case 'cancelled': return 'joule-status-failed'
    default: return ''
  }
}
