import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Activity, Play, Settings, BarChart3, Clock, AlertCircle, CheckCircle } from 'lucide-react'
import { apiClient } from '../utils/api'

interface BaselineConfig {
  target: string
  workloads: string[]
  backend: string
  repetitions: number
  hotspots: boolean
  hotspot_limit: number
  cache: boolean
}

export default function Baseline() {
  const location = useLocation()
  const navigate = useNavigate()
  const initialTarget = (location.state as any)?.target || ''

  const [config, setConfig] = useState<BaselineConfig>({
    target: initialTarget,
    workloads: [],
    backend: 'mock',
    repetitions: 5,
    hotspots: true,
    hotspot_limit: 12,
    cache: true,
  })

  const [targets, setTargets] = useState<string[]>([])
  const [backends, setBackends] = useState<{name: string; description: string}[]>([
    { name: 'mock', description: 'Mock backend for testing' },
    { name: 'rapl', description: 'Intel RAPL energy measurement' },
  ])
  const [isRunning, setIsRunning] = useState(false)
  const [runResult, setRunResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  // Fetch targets from discovery
  useEffect(() => {
    const fetchTargets = async () => {
      try {
        const projects = await apiClient.getProjects()
        if (projects.length > 0) {
          const discovered = await apiClient.discoverTargets(projects[0].path)
          setTargets(discovered.map((t: any) => t.qualname))

          // Pull default backend from the project config
          if (projects[0].config?.default_backend) {
            setConfig(c => ({ ...c, backend: projects[0].config.default_backend }))
          }
        }
      } catch {
        // Fallback – keep empty
      }
    }
    fetchTargets()
  }, [])

  const handleStartBaseline = async () => {
    setIsRunning(true)
    setError(null)
    setRunResult(null)
    try {
      const projects = await apiClient.getProjects()
      const projectPath = projects[0]?.path || '.'
      const result = await apiClient.runBaseline(projectPath, config)
      setRunResult(result)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to start baseline')
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-joule-ink">Baseline Measurement</h1>
        <p className="text-joule-muted mt-2">
          Measure baseline performance for your target function
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Configuration Panel */}
        <div className="joule-panel">
          <h2 className="text-xl font-semibold text-joule-ink mb-6">Configuration</h2>

          <div className="space-y-6">
            {/* Target Selection */}
            <div>
              <label className="block text-sm font-medium text-joule-ink mb-2">
                Target Function
              </label>
              <select
                value={config.target}
                onChange={(e) => setConfig({ ...config, target: e.target.value })}
                className="w-full px-3 py-2 border border-joule-border rounded-lg focus:outline-none focus:ring-2 focus:ring-joule-accent"
              >
                <option value="">Select a target...</option>
                {targets.map((target) => (
                  <option key={target} value={target}>
                    {target}
                  </option>
                ))}
              </select>
              {targets.length === 0 && (
                <p className="text-xs text-joule-muted mt-1">
                  No targets discovered – run Discovery first, or type a qualname manually.
                </p>
              )}
            </div>

            {/* Backend Selection */}
            <div>
              <label className="block text-sm font-medium text-joule-ink mb-2">
                Energy Backend
              </label>
              <div className="space-y-2">
                {backends.map((backend) => (
                  <label
                    key={backend.name}
                    className="flex items-center p-3 border border-joule-border rounded-lg cursor-pointer hover:bg-joule-bg"
                  >
                    <input
                      type="radio"
                      name="backend"
                      value={backend.name}
                      checked={config.backend === backend.name}
                      onChange={(e) => setConfig({ ...config, backend: e.target.value })}
                      className="mr-3"
                    />
                    <div>
                      <div className="font-medium text-joule-ink">{backend.name}</div>
                      <div className="text-sm text-joule-muted">{backend.description}</div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Repetitions */}
            <div>
              <label className="block text-sm font-medium text-joule-ink mb-2">
                Repetitions: {config.repetitions}
              </label>
              <input
                type="range" min="1" max="20"
                value={config.repetitions}
                onChange={(e) => setConfig({ ...config, repetitions: parseInt(e.target.value) })}
                className="w-full"
              />
            </div>

            {/* Hotspots */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <label className="text-sm font-medium text-joule-ink">Hotspot Analysis</label>
                <button
                  type="button"
                  onClick={() => setConfig({ ...config, hotspots: !config.hotspots })}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    config.hotspots ? 'bg-joule-accent' : 'bg-joule-border'
                  }`}
                >
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    config.hotspots ? 'translate-x-6' : 'translate-x-1'
                  }`} />
                </button>
              </div>

              {config.hotspots && (
                <div>
                  <label className="block text-sm text-joule-muted mb-2">
                    Hotspot Limit: {config.hotspot_limit}
                  </label>
                  <input
                    type="range" min="5" max="50"
                    value={config.hotspot_limit}
                    onChange={(e) => setConfig({ ...config, hotspot_limit: parseInt(e.target.value) })}
                    className="w-full"
                  />
                </div>
              )}
            </div>

            {/* Cache */}
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-joule-ink">Use Cache</label>
              <button
                type="button"
                onClick={() => setConfig({ ...config, cache: !config.cache })}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  config.cache ? 'bg-joule-accent' : 'bg-joule-border'
                }`}
              >
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  config.cache ? 'translate-x-6' : 'translate-x-1'
                }`} />
              </button>
            </div>
          </div>

          {/* Action Button */}
          <button
            onClick={handleStartBaseline}
            disabled={!config.target || isRunning}
            className="w-full mt-6 joule-button joule-button-primary flex items-center justify-center"
          >
            {isRunning ? (
              <><Activity className="w-4 h-4 mr-2 animate-spin" /> Running Baseline…</>
            ) : (
              <><Play className="w-4 h-4 mr-2" /> Start Baseline</>
            )}
          </button>
        </div>

        {/* Right Panel */}
        <div className="space-y-6">
          {/* Error */}
          {error && (
            <div className="joule-panel border-red-200 bg-red-50">
              <div className="flex items-center text-red-700">
                <AlertCircle className="w-5 h-5 mr-2" />
                <span>{error}</span>
              </div>
            </div>
          )}

          {/* Run Result */}
          {runResult && (
            <div className="joule-panel border-green-200 bg-green-50">
              <div className="flex items-center text-green-700 mb-3">
                <CheckCircle className="w-5 h-5 mr-2" />
                <span className="font-medium">Baseline started!</span>
              </div>
              <div className="text-sm text-green-800 space-y-1">
                <p>Run ID: <span className="font-mono">{runResult.run_id}</span></p>
                <p>Status: {runResult.status}</p>
              </div>
              <button
                className="mt-3 joule-button joule-button-secondary text-sm"
                onClick={() => navigate('/results')}
              >
                View in Results →
              </button>
            </div>
          )}

          {/* Configuration Summary */}
          <div className="joule-panel">
            <h3 className="text-lg font-semibold text-joule-ink mb-4 flex items-center">
              <Settings className="w-5 h-5 mr-2" />
              Configuration Summary
            </h3>
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-joule-muted">Target:</span>
                <span className="font-mono">{config.target || 'Not selected'}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-joule-muted">Backend:</span>
                <span>{config.backend}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-joule-muted">Repetitions:</span>
                <span>{config.repetitions}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-joule-muted">Hotspots:</span>
                <span>{config.hotspots ? `Enabled (limit: ${config.hotspot_limit})` : 'Disabled'}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-joule-muted">Cache:</span>
                <span>{config.cache ? 'Enabled' : 'Disabled'}</span>
              </div>
            </div>
          </div>

          {/* Expected Metrics */}
          <div className="joule-panel">
            <h3 className="text-lg font-semibold text-joule-ink mb-4 flex items-center">
              <BarChart3 className="w-5 h-5 mr-2" />
              Measured Metrics
            </h3>
            <div className="space-y-3">
              <div className="p-3 bg-joule-bg rounded-lg">
                <div className="text-sm text-joule-muted">Energy Consumption</div>
                <div className="text-lg font-semibold text-joule-ink">Run baseline to measure</div>
              </div>
              <div className="p-3 bg-joule-bg rounded-lg">
                <div className="text-sm text-joule-muted">Execution Time</div>
                <div className="text-lg font-semibold text-joule-ink">Run baseline to measure</div>
              </div>
              <div className="p-3 bg-joule-bg rounded-lg">
                <div className="text-sm text-joule-muted">Peak Memory</div>
                <div className="text-lg font-semibold text-joule-ink">Run baseline to measure</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
