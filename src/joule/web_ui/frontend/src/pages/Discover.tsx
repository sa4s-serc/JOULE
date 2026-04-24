import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Code, TestTube, Wrench, Play, RefreshCw, AlertCircle } from 'lucide-react'
import { apiClient } from '../utils/api'

interface Target {
  qualname: string
  file_path: string
  line_number: number
  function_type: 'function' | 'method' | 'async_function' | 'async_method'
  score?: number
  reasons?: string[]
  workloads?: Workload[]
}

interface Workload {
  id: string
  kind: 'test' | 'property' | 'harness' | 'default'
  description: string
  file_path?: string
  node_id?: string
}

export default function Discover() {
  const navigate = useNavigate()
  const [targets, setTargets] = useState<Target[]>([])
  const [selectedTarget, setSelectedTarget] = useState<Target | null>(null)
  const [selectedWorkloads, setSelectedWorkloads] = useState<Set<string>>(new Set())
  const [searchTerm, setSearchTerm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const discoverTargets = async () => {
    setLoading(true)
    setError(null)
    try {
      const projects = await apiClient.getProjects()
      if (projects.length === 0) {
        setError('No project found. Make sure the backend is running.')
        return
      }
      const projectPath = projects[0].path
      const data = await apiClient.discoverTargets(projectPath)
      setTargets(data)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to discover targets. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    discoverTargets()
  }, [])

  const filteredTargets = targets.filter(target =>
    target.qualname.toLowerCase().includes(searchTerm.toLowerCase()) ||
    target.file_path.toLowerCase().includes(searchTerm.toLowerCase())
  )

  // When the discovery returns nested workloads inline with targets, use those
  const currentWorkloads: Workload[] = selectedTarget?.workloads || []

  const toggleWorkload = (workloadId: string) => {
    const newSelection = new Set(selectedWorkloads)
    if (newSelection.has(workloadId)) {
      newSelection.delete(workloadId)
    } else {
      newSelection.add(workloadId)
    }
    setSelectedWorkloads(newSelection)
  }

  const getWorkloadIcon = (kind: Workload['kind']) => {
    switch (kind) {
      case 'test': return TestTube
      case 'property': return Code
      case 'harness': return Wrench
      default: return Play
    }
  }

  const getFunctionTypeColor = (type: Target['function_type']) => {
    switch (type) {
      case 'function': return 'text-blue-600'
      case 'method': return 'text-green-600'
      case 'async_function': return 'text-purple-600'
      case 'async_method': return 'text-pink-600'
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-joule-ink">Discover Targets</h1>
          <p className="text-joule-muted mt-2">
            Find optimization targets and select workloads for measurement
          </p>
        </div>
        <button
          className="joule-button joule-button-secondary flex items-center"
          onClick={discoverTargets}
          disabled={loading}
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          {loading ? 'Scanning…' : 'Re-scan Project'}
        </button>
      </div>

      {error && (
        <div className="joule-panel border-red-200 bg-red-50">
          <div className="flex items-center text-red-700">
            <AlertCircle className="w-5 h-5 mr-2" />
            <span>{error}</span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Targets Panel */}
        <div className="joule-panel">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-joule-ink">
              Targets
              {targets.length > 0 && (
                <span className="text-sm text-joule-muted font-normal ml-2">({targets.length})</span>
              )}
            </h2>
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-joule-muted" />
              <input
                type="text"
                placeholder="Search targets..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10 pr-4 py-2 border border-joule-border rounded-lg focus:outline-none focus:ring-2 focus:ring-joule-accent"
              />
            </div>
          </div>

          {loading ? (
            <div className="animate-pulse space-y-3">
              {[1,2,3].map(i => <div key={i} className="h-16 bg-joule-chip rounded-lg" />)}
            </div>
          ) : filteredTargets.length === 0 ? (
            <div className="text-center py-8">
              <Search className="w-10 h-10 text-joule-muted mx-auto mb-3" />
              <p className="text-joule-muted">
                {targets.length === 0
                  ? 'No targets discovered. Make sure your project has Python functions.'
                  : 'No targets match your search.'}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredTargets.map((target) => (
                <div
                  key={target.qualname}
                  onClick={() => {
                    setSelectedTarget(target)
                    setSelectedWorkloads(new Set())
                  }}
                  className={`p-4 rounded-lg border cursor-pointer transition-colors duration-200 ${
                    selectedTarget?.qualname === target.qualname
                      ? 'border-joule-accent bg-joule-chip'
                      : 'border-joule-border hover:bg-joule-bg'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h3 className="font-medium text-joule-ink break-all">
                        {target.qualname}
                      </h3>
                      <p className="text-sm text-joule-muted font-mono mt-1 break-all">
                        {target.file_path}:{target.line_number}
                      </p>
                      {target.score !== undefined && (
                        <p className="text-xs text-joule-accent mt-1">
                          Discovery score: {target.score.toFixed(2)}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-col items-end">
                      <span className={`text-xs font-medium ${getFunctionTypeColor(target.function_type)}`}>
                        {target.function_type.replace('_', ' ')}
                      </span>
                      {target.workloads && (
                        <span className="text-xs text-joule-muted mt-1">
                          {target.workloads.length} workload{target.workloads.length !== 1 ? 's' : ''}
                        </span>
                      )}
                    </div>
                  </div>
                  {target.reasons && target.reasons.length > 0 && (
                    <div className="mt-2 text-xs text-joule-muted">
                      {target.reasons.slice(0, 2).join(' • ')}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Workloads Panel */}
        <div className="joule-panel">
          <h2 className="text-xl font-semibold text-joule-ink mb-6">Workloads</h2>

          {!selectedTarget ? (
            <div className="text-center py-8">
              <Search className="w-12 h-12 text-joule-muted mx-auto mb-4" />
              <p className="text-joule-muted">
                Select a target to view available workloads
              </p>
            </div>
          ) : currentWorkloads.length === 0 ? (
            <div className="text-center py-8">
              <AlertCircle className="w-10 h-10 text-joule-muted mx-auto mb-3" />
              <p className="text-joule-muted">
                No workloads found for this target. JOULE will use automatic workload synthesis.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {currentWorkloads.map((workload) => {
                const Icon = getWorkloadIcon(workload.kind as any)
                const isSelected = selectedWorkloads.has(workload.id)

                return (
                  <div
                    key={workload.id}
                    onClick={() => toggleWorkload(workload.id)}
                    className={`p-4 rounded-lg border cursor-pointer transition-colors duration-200 ${
                      isSelected
                        ? 'border-joule-accent bg-joule-chip'
                        : 'border-joule-border hover:bg-joule-bg'
                    }`}
                  >
                    <div className="flex items-start">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {}}
                        className="mt-1 mr-3"
                      />
                      <div className="flex-1">
                        <div className="flex items-center">
                          <Icon className="w-4 h-4 text-joule-accent mr-2" />
                          <h3 className="font-medium text-joule-ink break-all">
                            {workload.id}
                          </h3>
                          <span className="ml-2 joule-chip text-xs">
                            {workload.kind}
                          </span>
                        </div>
                        <p className="text-sm text-joule-muted mt-1">
                          {workload.description}
                        </p>
                        {workload.file_path && (
                          <p className="text-xs text-joule-muted font-mono mt-1 break-all">
                            {workload.file_path}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      {selectedTarget && (
        <div className="joule-panel">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-joule-ink break-all">
                Selected Target: {selectedTarget.qualname}
              </h3>
              <p className="text-sm text-joule-muted">
                {selectedWorkloads.size > 0
                  ? `${selectedWorkloads.size} workload(s) selected`
                  : 'Using automatic workload discovery'}
              </p>
            </div>
            <div className="flex space-x-3">
              <button
                className="joule-button joule-button-secondary"
                onClick={() => navigate('/baseline', { state: { target: selectedTarget.qualname } })}
              >
                Run Baseline
              </button>
              <button
                className="joule-button joule-button-primary"
                onClick={() => navigate('/optimize', { state: { target: selectedTarget.qualname } })}
              >
                Start Optimization
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
