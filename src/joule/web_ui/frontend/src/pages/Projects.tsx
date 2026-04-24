import { useState, useEffect } from 'react'
import { FolderOpen, Plus, Settings, CheckCircle, XCircle, RefreshCw } from 'lucide-react'
import { apiClient } from '../utils/api'

interface ProjectData {
  path: string
  name: string
  config?: Record<string, any>
  health?: {
    backend_available: boolean
    backend_name?: string
    python_version?: string
    dependencies_ok: boolean
    artifact_dir_exists: boolean
    db_accessible: boolean
    issues: string[]
  }
}

export default function Projects() {
  const [projects, setProjects] = useState<ProjectData[]>([])
  const [loading, setLoading] = useState(true)
  const [doctorRunning, setDoctorRunning] = useState<string | null>(null)

  const fetchProjects = async () => {
    try {
      const data = await apiClient.getProjects()
      setProjects(data)
    } catch (err) {
      console.warn('Failed to fetch projects:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProjects()
  }, [])

  const handleRunDoctor = async (projectPath: string) => {
    setDoctorRunning(projectPath)
    try {
      await apiClient.runProjectDoctor(projectPath)
      await fetchProjects()
    } catch (err) {
      console.error('Doctor failed:', err)
    } finally {
      setDoctorRunning(null)
    }
  }

  const healthStatus = (health: ProjectData['health']) => {
    if (!health || health.issues.length === 0) {
      return {
        icon: CheckCircle,
        text: 'Healthy',
        className: 'text-green-600',
      }
    }
    return {
      icon: XCircle,
      text: `${health.issues.length} Issue${health.issues.length > 1 ? 's' : ''} Found`,
      className: 'text-red-600',
    }
  }

  if (loading) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold text-joule-ink">Projects</h1>
          <p className="text-joule-muted mt-2">Loading projects…</p>
        </div>
        <div className="animate-pulse joule-panel h-48" />
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-joule-ink">Projects</h1>
          <p className="text-joule-muted mt-2">
            Manage your JOULE projects and configurations
          </p>
        </div>
        <button
          className="joule-button joule-button-secondary flex items-center"
          onClick={fetchProjects}
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </button>
      </div>

      {/* Projects Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {projects.map((project) => {
          const status = healthStatus(project.health)
          const StatusIcon = status.icon

          return (
            <div key={project.path} className="joule-panel">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center">
                  <FolderOpen className="w-5 h-5 text-joule-accent mr-3" />
                  <div>
                    <h3 className="font-semibold text-joule-ink">
                      {project.name}
                    </h3>
                    <p className="text-sm text-joule-muted font-mono">
                      {project.path}
                    </p>
                  </div>
                </div>
              </div>

              {/* Health Status */}
              <div className="flex items-center mb-4">
                <StatusIcon className={`w-4 h-4 mr-2 ${status.className}`} />
                <span className={`text-sm font-medium ${status.className}`}>
                  {status.text}
                </span>
              </div>

              {/* Health Details */}
              {project.health && (
                <div className="space-y-2 mb-4">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-joule-muted">Backend</span>
                    <span className={project.health.backend_available ? 'text-green-600' : 'text-red-600'}>
                      {project.health.backend_available
                        ? `${project.health.backend_name || 'Available'}`
                        : 'Not Available'}
                    </span>
                  </div>
                  {project.health.python_version && (
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-joule-muted">Python</span>
                      <span className="font-mono text-joule-ink">{project.health.python_version}</span>
                    </div>
                  )}
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-joule-muted">Dependencies</span>
                    <span className={project.health.dependencies_ok ? 'text-green-600' : 'text-red-600'}>
                      {project.health.dependencies_ok ? 'OK' : 'Issues'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-joule-muted">Artifacts</span>
                    <span className={project.health.artifact_dir_exists ? 'text-green-600' : 'text-red-600'}>
                      {project.health.artifact_dir_exists ? 'Exists' : 'Not initialized'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-joule-muted">Database</span>
                    <span className={project.health.db_accessible ? 'text-green-600' : 'text-red-600'}>
                      {project.health.db_accessible ? 'Accessible' : 'Not accessible'}
                    </span>
                  </div>
                </div>
              )}

              {/* Issues */}
              {project.health && project.health.issues.length > 0 && (
                <div className="mb-4">
                  <h4 className="text-sm font-medium text-joule-ink mb-2">Issues:</h4>
                  <ul className="space-y-1">
                    {project.health.issues.map((issue, index) => (
                      <li key={index} className="text-sm text-red-600">
                        • {issue}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Config highlights */}
              {project.config && (
                <div className="mb-4 p-3 bg-joule-bg rounded-lg">
                  <h4 className="text-xs font-medium text-joule-muted mb-2 uppercase tracking-wide">Configuration</h4>
                  <div className="grid grid-cols-2 gap-1 text-xs">
                    <span className="text-joule-muted">Profile:</span>
                    <span className="font-mono">{project.config.profile || 'standard'}</span>
                    <span className="text-joule-muted">Backend:</span>
                    <span className="font-mono">{project.config.default_backend || 'mock'}</span>
                    <span className="text-joule-muted">Budget:</span>
                    <span>{project.config.optimization_budget || 6} candidates</span>
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex space-x-2">
                <button
                  className="joule-button joule-button-secondary text-sm flex items-center"
                  onClick={() => handleRunDoctor(project.path)}
                  disabled={doctorRunning === project.path}
                >
                  {doctorRunning === project.path ? (
                    <><RefreshCw className="w-3 h-3 mr-1 animate-spin" /> Running…</>
                  ) : (
                    'Run Doctor'
                  )}
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {/* Empty State */}
      {projects.length === 0 && (
        <div className="joule-panel text-center py-12">
          <FolderOpen className="w-12 h-12 text-joule-muted mx-auto mb-4" />
          <h3 className="text-lg font-medium text-joule-ink mb-2">
            No project detected
          </h3>
          <p className="text-joule-muted mb-4">
            Make sure you started the UI with a valid project path containing a pyproject.toml with [tool.joule] config.
          </p>
        </div>
      )}
    </div>
  )
}
