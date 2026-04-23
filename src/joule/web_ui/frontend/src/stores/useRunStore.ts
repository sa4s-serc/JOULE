import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import { Run, BaselineConfig, OptimizationConfig, ApplyConfig } from '../types'
import { apiClient, wsClient } from '../utils/api'

interface RunState {
  // State
  runs: Run[]
  currentRun: any | null
  loading: boolean
  error: string | null
  
  // Real-time updates
  runUpdates: Record<string, any>

  // Actions
  loadRuns: (projectPath?: string) => Promise<void>
  loadRun: (runId: string, projectPath?: string) => Promise<void>
  runBaseline: (projectPath: string, config: BaselineConfig) => Promise<string>
  runOptimization: (projectPath: string, config: OptimizationConfig) => Promise<string>
  applyCandidate: (runId: string, config: ApplyConfig, projectPath?: string) => Promise<void>
  subscribeToRun: (runId: string) => void
  unsubscribeFromRun: (runId: string) => void
  clearCurrentRun: () => void
}

export const useRunStore = create<RunState>()(
  devtools(
    (set, get) => ({
      // Initial state
      runs: [],
      currentRun: null,
      loading: false,
      error: null,
      runUpdates: {},

      // Actions
      loadRuns: async (projectPath = '.') => {
        set({ loading: true, error: null })
        try {
          const runs = await apiClient.getRuns(projectPath)
          set({ runs, loading: false })
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to load runs',
            loading: false 
          })
        }
      },

      loadRun: async (runId, projectPath = '.') => {
        set({ loading: true, error: null })
        try {
          const run = await apiClient.getRun(runId, projectPath)
          set({ currentRun: run, loading: false })
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to load run',
            loading: false 
          })
        }
      },

      runBaseline: async (projectPath, config) => {
        set({ loading: true, error: null })
        try {
          const result = await apiClient.runBaseline(projectPath, config)
          
          // Subscribe to real-time updates for this run
          get().subscribeToRun(result.run_id)
          
          set({ loading: false })
          return result.run_id
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to start baseline',
            loading: false 
          })
          throw error
        }
      },

      runOptimization: async (projectPath, config) => {
        set({ loading: true, error: null })
        try {
          const result = await apiClient.runOptimization(projectPath, config)
          
          // Subscribe to real-time updates for this run
          get().subscribeToRun(result.run_id)
          
          set({ loading: false })
          return result.run_id
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to start optimization',
            loading: false 
          })
          throw error
        }
      },

      applyCandidate: async (runId, config, projectPath = '.') => {
        set({ loading: true, error: null })
        try {
          const result = await apiClient.applyCandidate(runId, config, projectPath)
          set({ loading: false })
          return result
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to apply candidate',
            loading: false 
          })
          throw error
        }
      },

      subscribeToRun: (runId) => {
        // Connect WebSocket if not already connected
        if (!wsClient.isConnected()) {
          wsClient.connect().catch(console.error)
        }

        // Subscribe to run updates
        wsClient.subscribeToRun(runId, (data) => {
          const { runUpdates, currentRun } = get()
          
          // Store the update
          set({
            runUpdates: {
              ...runUpdates,
              [runId]: { ...runUpdates[runId], ...data }
            }
          })

          // Update current run if it matches
          if (currentRun && currentRun.run_id === runId) {
            set({
              currentRun: { ...currentRun, ...data }
            })
          }

          // Update run in list if it exists
          const { runs } = get()
          const updatedRuns = runs.map(run => 
            run.run_id === runId ? { ...run, ...data } : run
          )
          set({ runs: updatedRuns })
        })
      },

      unsubscribeFromRun: (runId) => {
        wsClient.unsubscribeFromRun(runId)
        
        // Clear stored updates for this run
        const { runUpdates } = get()
        const newUpdates = { ...runUpdates }
        delete newUpdates[runId]
        set({ runUpdates: newUpdates })
      },

      clearCurrentRun: () => {
        set({ currentRun: null, error: null })
      },
    }),
    {
      name: 'run-store',
    }
  )
)
