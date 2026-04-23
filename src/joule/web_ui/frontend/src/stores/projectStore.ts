import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Project, TargetSpec, WorkloadSpec } from '@/types'

interface ProjectState {
  // Current selection
  currentProject: Project | null
  selectedTarget: TargetSpec | null
  selectedWorkloads: Set<string>

  // Available data
  projects: Project[]
  targets: TargetSpec[]
  workloads: WorkloadSpec[]

  // Loading states
  isLoadingProjects: boolean
  isLoadingTargets: boolean
  isLoadingWorkloads: boolean

  // Errors
  projectError: string | null
  targetError: string | null
  workloadError: string | null

  // Actions
  setCurrentProject: (project: Project | null) => void
  setProjects: (projects: Project[]) => void
  setSelectedTarget: (target: TargetSpec | null) => void
  setSelectedWorkloads: (workloads: Set<string>) => void
  toggleWorkload: (workloadId: string) => void
  setTargets: (targets: TargetSpec[]) => void
  setWorkloads: (workloads: WorkloadSpec[]) => void

  // Loading setters
  setLoadingProjects: (loading: boolean) => void
  setLoadingTargets: (loading: boolean) => void
  setLoadingWorkloads: (loading: boolean) => void

  // Error setters
  setProjectError: (error: string | null) => void
  setTargetError: (error: string | null) => void
  setWorkloadError: (error: string | null) => void

  // Async actions
  loadProjects: () => Promise<void>
  loadTargets: (projectPath: string) => Promise<void>
  loadWorkloads: (projectPath: string, targetQualname: string) => Promise<void>
}

export const useProjectStore = create<ProjectState>()(
  persist(
    (set, get) => ({
      // Initial state
      currentProject: null,
      selectedTarget: null,
      selectedWorkloads: new Set(),
      projects: [],
      targets: [],
      workloads: [],
      isLoadingProjects: false,
      isLoadingTargets: false,
      isLoadingWorkloads: false,
      projectError: null,
      targetError: null,
      workloadError: null,

      // Actions
      setCurrentProject: (project) => set({ currentProject: project }),
      setProjects: (projects) => set({ projects }),
      setSelectedTarget: (target) => set({ selectedTarget: target }),
      setSelectedWorkloads: (workloads) => set({ selectedWorkloads: workloads }),
      toggleWorkload: (workloadId) => {
        const current = new Set(get().selectedWorkloads)
        if (current.has(workloadId)) {
          current.delete(workloadId)
        } else {
          current.add(workloadId)
        }
        set({ selectedWorkloads: current })
      },
      setTargets: (targets) => set({ targets }),
      setWorkloads: (workloads) => set({ workloads }),

      // Loading setters
      setLoadingProjects: (loading) => set({ isLoadingProjects: loading }),
      setLoadingTargets: (loading) => set({ isLoadingTargets: loading }),
      setLoadingWorkloads: (loading) => set({ isLoadingWorkloads: loading }),

      // Error setters
      setProjectError: (error) => set({ projectError: error }),
      setTargetError: (error) => set({ targetError: error }),
      setWorkloadError: (error) => set({ workloadError: error }),

      // Async actions
      loadProjects: async () => {
        set({ isLoadingProjects: true, projectError: null })
        try {
          const response = await fetch('/api/projects')
          if (!response.ok) throw new Error('Failed to load projects')
          const projects = await response.json()
          set({ projects, isLoadingProjects: false })
        } catch (error) {
          set({
            projectError: error instanceof Error ? error.message : 'Unknown error',
            isLoadingProjects: false,
          })
        }
      },

      loadTargets: async (projectPath: string) => {
        set({ isLoadingTargets: true, targetError: null })
        try {
          const response = await fetch(`/api/projects/${encodeURIComponent(projectPath)}/discover/targets`)
          if (!response.ok) throw new Error('Failed to load targets')
          const targets = await response.json()
          set({ targets, isLoadingTargets: false })
        } catch (error) {
          set({
            targetError: error instanceof Error ? error.message : 'Unknown error',
            isLoadingTargets: false,
          })
        }
      },

      loadWorkloads: async (projectPath: string, targetQualname: string) => {
        set({ isLoadingWorkloads: true, workloadError: null })
        try {
          const response = await fetch(
            `/api/projects/${encodeURIComponent(projectPath)}/discover/workloads/${encodeURIComponent(targetQualname)}`
          )
          if (!response.ok) throw new Error('Failed to load workloads')
          const workloads = await response.json()
          set({ workloads, isLoadingWorkloads: false })
        } catch (error) {
          set({
            workloadError: error instanceof Error ? error.message : 'Unknown error',
            isLoadingWorkloads: false,
          })
        }
      },
    }),
    {
      name: 'joule-project-storage',
      partialize: (state) => ({
        currentProject: state.currentProject,
        selectedWorkloads: Array.from(state.selectedWorkloads),
      }),
      onRehydrateStorage: () => (state) => {
        // Convert selectedWorkloads back to Set after rehydration
        if (state && Array.isArray(state.selectedWorkloads)) {
          state.selectedWorkloads = new Set(state.selectedWorkloads)
        }
      },
    }
  )
)
