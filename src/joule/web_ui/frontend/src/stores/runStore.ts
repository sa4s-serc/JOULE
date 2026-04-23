import { create } from 'zustand'
import type { Run, Candidate, BaselineResult, OptimizationResult } from '@/types'

export type RunStatus = 'idle' | 'starting' | 'running' | 'completed' | 'failed' | 'cancelled'

interface RunState {
  // Run lists
  runs: Run[]
  currentRun: Run | null
  currentRunStatus: RunStatus
  currentRunProgress: number

  // Run details
  baselineResult: BaselineResult | null
  optimizationResult: OptimizationResult | null
  candidates: Candidate[]

  // Real-time updates
  wsConnected: boolean
  wsError: string | null

  // Loading states
  isLoadingRuns: boolean
  isLoadingRunDetails: boolean
  isStartingRun: boolean

  // Errors
  runsError: string | null
  runDetailsError: string | null
  startRunError: string | null

  // Actions
  setRuns: (runs: Run[]) => void
  setCurrentRun: (run: Run | null) => void
  setCurrentRunStatus: (status: RunStatus) => void
  setCurrentRunProgress: (progress: number) => void
  setBaselineResult: (result: BaselineResult | null) => void
  setOptimizationResult: (result: OptimizationResult | null) => void
  setCandidates: (candidates: Candidate[]) => void
  addCandidate: (candidate: Candidate) => void
  updateCandidate: (candidateId: string, updates: Partial<Candidate>) => void

  // WebSocket actions
  setWsConnected: (connected: boolean) => void
  setWsError: (error: string | null) => void

  // Loading setters
  setLoadingRuns: (loading: boolean) => void
  setLoadingRunDetails: (loading: boolean) => void
  setStartingRun: (starting: boolean) => void

  // Error setters
  setRunsError: (error: string | null) => void
  setRunDetailsError: (error: string | null) => void
  setStartRunError: (error: string | null) => void

  // Async actions
  loadRuns: (projectPath?: string) => Promise<void>
  loadRunDetails: (runId: string, projectPath?: string) => Promise<void>
  startBaseline: (projectPath: string, config: Record<string, unknown>) => Promise<string | null>
  startOptimization: (projectPath: string, config: Record<string, unknown>) => Promise<string | null>
  applyCandidate: (runId: string, config: Record<string, unknown>, projectPath?: string) => Promise<boolean>
}

export const useRunStore = create<RunState>((set) => ({
  // Initial state
  runs: [],
  currentRun: null,
  currentRunStatus: 'idle',
  currentRunProgress: 0,
  baselineResult: null,
  optimizationResult: null,
  candidates: [],
  wsConnected: false,
  wsError: null,
  isLoadingRuns: false,
  isLoadingRunDetails: false,
  isStartingRun: false,
  runsError: null,
  runDetailsError: null,
  startRunError: null,

  // Actions
  setRuns: (runs) => set({ runs }),
  setCurrentRun: (run) => set({ currentRun: run }),
  setCurrentRunStatus: (status) => set({ currentRunStatus: status }),
  setCurrentRunProgress: (progress) => set({ currentRunProgress: progress }),
  setBaselineResult: (result) => set({ baselineResult: result }),
  setOptimizationResult: (result) => set({ optimizationResult: result }),
  setCandidates: (candidates) => set({ candidates }),
  addCandidate: (candidate) => set((state) => ({
    candidates: [...state.candidates, candidate],
  })),
  updateCandidate: (candidateId, updates) => set((state) => ({
    candidates: state.candidates.map((c) =>
      c.candidate_id === candidateId ? { ...c, ...updates } : c
    ),
  })),

  // WebSocket actions
  setWsConnected: (connected) => set({ wsConnected: connected }),
  setWsError: (error) => set({ wsError: error }),

  // Loading setters
  setLoadingRuns: (loading) => set({ isLoadingRuns: loading }),
  setLoadingRunDetails: (loading) => set({ isLoadingRunDetails: loading }),
  setStartingRun: (starting) => set({ isStartingRun: starting }),

  // Error setters
  setRunsError: (error) => set({ runsError: error }),
  setRunDetailsError: (error) => set({ runDetailsError: error }),
  setStartRunError: (error) => set({ startRunError: error }),

  // Async actions
  loadRuns: async (projectPath = '.') => {
    set({ isLoadingRuns: true, runsError: null })
    try {
      const response = await fetch(`/api/runs?project_path=${encodeURIComponent(projectPath)}`)
      if (!response.ok) throw new Error('Failed to load runs')
      const runs = await response.json()
      set({ runs, isLoadingRuns: false })
    } catch (error) {
      set({
        runsError: error instanceof Error ? error.message : 'Unknown error',
        isLoadingRuns: false,
      })
    }
  },

  loadRunDetails: async (runId: string, projectPath = '.') => {
    set({ isLoadingRunDetails: true, runDetailsError: null })
    try {
      const response = await fetch(
        `/api/runs/${encodeURIComponent(runId)}?project_path=${encodeURIComponent(projectPath)}`
      )
      if (!response.ok) throw new Error('Failed to load run details')
      const details = await response.json()

      set({
        currentRun: details,
        candidates: details.candidates || [],
        baselineResult: details.baseline || null,
        optimizationResult: details.optimization_analysis || null,
        isLoadingRunDetails: false,
      })
    } catch (error) {
      set({
        runDetailsError: error instanceof Error ? error.message : 'Unknown error',
        isLoadingRunDetails: false,
      })
    }
  },

  startBaseline: async (projectPath: string, config: Record<string, unknown>) => {
    set({ isStartingRun: true, startRunError: null, currentRunStatus: 'starting' })
    try {
      const response = await fetch(
        `/api/projects/${encodeURIComponent(projectPath)}/baseline`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(config),
        }
      )
      if (!response.ok) throw new Error('Failed to start baseline')
      const result = await response.json()

      set({
        isStartingRun: false,
        currentRunStatus: 'running',
        currentRun: { ...result, run_type: 'baseline', status: 'running' } as Run,
      })
      return result.run_id as string
    } catch (error) {
      set({
        startRunError: error instanceof Error ? error.message : 'Unknown error',
        isStartingRun: false,
        currentRunStatus: 'failed',
      })
      return null
    }
  },

  startOptimization: async (projectPath: string, config: Record<string, unknown>) => {
    set({ isStartingRun: true, startRunError: null, currentRunStatus: 'starting' })
    try {
      const response = await fetch(
        `/api/projects/${encodeURIComponent(projectPath)}/optimize`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(config),
        }
      )
      if (!response.ok) throw new Error('Failed to start optimization')
      const result = await response.json()

      set({
        isStartingRun: false,
        currentRunStatus: 'running',
        currentRun: { ...result, run_type: 'optimize', status: 'running' } as Run,
      })
      return result.run_id as string
    } catch (error) {
      set({
        startRunError: error instanceof Error ? error.message : 'Unknown error',
        isStartingRun: false,
        currentRunStatus: 'failed',
      })
      return null
    }
  },

  applyCandidate: async (runId: string, config: Record<string, unknown>, projectPath = '.') => {
    try {
      const response = await fetch(
        `/api/runs/${encodeURIComponent(runId)}/apply?project_path=${encodeURIComponent(projectPath)}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(config),
        }
      )
      if (!response.ok) throw new Error('Failed to apply candidate')
      return true
    } catch (error) {
      console.error('Apply candidate error:', error)
      return false
    }
  },
}))
