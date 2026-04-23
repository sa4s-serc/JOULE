import { useState } from 'react'
import { FolderOpen, Plus, Settings, CheckCircle, XCircle } from 'lucide-react'

interface Project {
  path: string
  name: string
  health: {
    backend_available: boolean
    dependencies_ok: boolean
    artifact_dir_exists: boolean
    issues: string[]
  }
  last_activity?: string
}

export default function Projects() {
  const [projects, setProjects] = useState<Project[]>([
    {
      path: '/home/prakhar/dev/prakhar479/hedge',
      name: 'hedge',
      health: {
        backend_available: true,
        dependencies_ok: true,
        artifact_dir_exists: true,
        issues: [],
      },
      last_activity: '2024-04-23T10:30:00Z',
    },
  ])

  const healthStatus = (health: Project['health']) => {
    if (health.issues.length === 0) {
      return {
        icon: CheckCircle,
        text: 'Healthy',
        className: 'text-green-600',
      }
    }
    return {
      icon: XCircle,
      text: 'Issues Found',
      className: 'text-red-600',
    }
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
        <button className="joule-button joule-button-primary flex items-center">
          <Plus className="w-4 h-4 mr-2" />
          Add Project
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
                <button className="p-2 hover:bg-joule-chip rounded-lg">
                  <Settings className="w-4 h-4 text-joule-muted" />
                </button>
              </div>

              {/* Health Status */}
              <div className="flex items-center mb-4">
                <StatusIcon className={`w-4 h-4 mr-2 ${status.className}`} />
                <span className={`text-sm font-medium ${status.className}`}>
                  {status.text}
                </span>
              </div>

              {/* Health Details */}
              <div className="space-y-2 mb-4">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-joule-muted">Backend</span>
                  <span className={project.health.backend_available ? 'text-green-600' : 'text-red-600'}>
                    {project.health.backend_available ? 'Available' : 'Not Available'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-joule-muted">Dependencies</span>
                  <span className={project.health.dependencies_ok ? 'text-green-600' : 'text-red-600'}>
                    {project.health.dependencies_ok ? 'OK' : 'Issues'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-joule-muted">Artifacts</span>
                  <span className={project.health.artifact_dir_exists ? 'text-green-600' : 'text-red-600'}>
                    {project.health.artifact_dir_exists ? 'Exists' : 'Missing'}
                  </span>
                </div>
              </div>

              {/* Issues */}
              {project.health.issues.length > 0 && (
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

              {/* Actions */}
              <div className="flex space-x-2">
                <button className="joule-button joule-button-primary text-sm">
                  Open Project
                </button>
                <button className="joule-button joule-button-secondary text-sm">
                  Run Doctor
                </button>
              </div>

              {/* Last Activity */}
              {project.last_activity && (
                <div className="mt-4 pt-4 border-t border-joule-border">
                  <p className="text-xs text-joule-muted">
                    Last activity: {new Date(project.last_activity).toLocaleString()}
                  </p>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Empty State */}
      {projects.length === 0 && (
        <div className="joule-panel text-center py-12">
          <FolderOpen className="w-12 h-12 text-joule-muted mx-auto mb-4" />
          <h3 className="text-lg font-medium text-joule-ink mb-2">
            No projects yet
          </h3>
          <p className="text-joule-muted mb-4">
            Add your first JOULE project to get started
          </p>
          <button className="joule-button joule-button-primary">
            <Plus className="w-4 h-4 mr-2" />
            Add Project
          </button>
        </div>
      )}
    </div>
  )
}
