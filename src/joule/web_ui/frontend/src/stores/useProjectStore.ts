import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import { Project, TargetSpec, WorkloadSpec } from '../types'
import { apiClient } from '../utils/api'

interface ProjectState {
  // State
  projects: Project[]
  currentProject: Project | null
  targets: TargetSpec[]
  workloads: WorkloadSpec[]
  selectedTarget: TargetSpec | null
  selectedWorkloads: string[]
  loading: boolean
  error: string | null

  // Actions
  loadProjects: () => Promise<void>
  setCurrentProject: (project: Project) => void
  loadTargets: (projectPath: string) => Promise<void>
  loadWorkloads: (projectPath: string, targetQualname: string) => Promise<void>
  setSelectedTarget: (target: TargetSpec | null) => void
  toggleWorkload: (workloadId: string) => void
  clearSelection: () => void
  runDoctor: (projectPath: string) => Promise<void>
}

export const useProjectStore = create<ProjectState>()(
  devtools(
    (set, get) => ({
      // Initial state
      projects: [],
      currentProject: null,
      targets: [],
      workloads: [],
      selectedTarget: null,
      selectedWorkloads: [],
      loading: false,
      error: null,

      // Actions
      loadProjects: async () => {
        set({ loading: true, error: null })
        try {
          const projects = await apiClient.getProjects()
          set({ projects, loading: false })
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to load projects',
            loading: false 
          })
        }
      },

      setCurrentProject: (project) => {
        set({ 
          currentProject: project,
          selectedTarget: null,
          selectedWorkloads: [],
          targets: [],
          workloads: [],
          error: null 
        })
      },

      loadTargets: async (projectPath) => {
        set({ loading: true, error: null })
        try {
          const targets = await apiClient.discoverTargets(projectPath)
          set({ targets, loading: false })
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to load targets',
            loading: false 
          })
        }
      },

      loadWorkloads: async (projectPath, targetQualname) => {
        set({ loading: true, error: null })
        try {
          const workloads = await apiClient.discoverWorkloads(projectPath, targetQualname)
          set({ workloads, loading: false })
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Failed to load workloads',
            loading: false 
          })
        }
      },

      setSelectedTarget: (target) => {
        set({ 
          selectedTarget: target,
          selectedWorkloads: [],
          workloads: [] 
        })
      },

      toggleWorkload: (workloadId) => {
        const { selectedWorkloads } = get()
        const newSelection = new Set(selectedWorkloads)
        
        if (newSelection.has(workloadId)) {
          newSelection.delete(workloadId)
        } else {
          newSelection.add(workloadId)
        }
        
        set({ selectedWorkloads: Array.from(newSelection) })
      },

      clearSelection: () => {
        set({ 
          selectedTarget: null,
          selectedWorkloads: [],
          workloads: [] 
        })
      },

      runDoctor: async (projectPath) => {
        set({ loading: true, error: null })
        try {
          const result = await apiClient.runProjectDoctor(projectPath)
          
          // Update project health if we have the current project
          const { currentProject } = get()
          if (currentProject && currentProject.path === projectPath) {
            set({
              currentProject: {
                ...currentProject,
                health: result.checks
              }
            })
          }
          
          set({ loading: false })
          return result
        } catch (error) {
          set({ 
            error: error instanceof Error ? error.message : 'Doctor check failed',
            loading: false 
          })
          throw error
        }
      },
    }),
    {
      name: 'project-store',
    }
  )
)
