import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Zap, Play, Settings, TrendingUp, AlertCircle, CheckCircle } from 'lucide-react'
import { apiClient } from '../utils/api'

interface OptimizationConfig {
  target: string
  workloads: string[]
  backend: string
  budget: number
  analysis: boolean
  cache: boolean
  fresh_surrogate: boolean
  parallel: number
  improvement_threshold: number
}

export default function Optimize() {
  const location = useLocation()
  const navigate = useNavigate()
  const initialTarget = (location.state as any)?.target || ''

  const [config, setConfig] = useState<OptimizationConfig>({
    target: initialTarget,
    workloads: [],
    backend: 'mock',
    budget: 6,
    analysis: true,
    cache: true,
    fresh_surrogate: false,
    parallel: 1,
    improvement_threshold: 0.05,
  })

  const [surrogateModel, setSurrogateModel] = useState<string>('hist_gbdt')

  const [targets, setTargets] = useState<string[]>([])
  const [backends] = useState([
    { name: 'mock', description: 'Mock backend for testing' },
    { name: 'rapl', description: 'Intel RAPL energy measurement' },
  ])
  const [isRunning, setIsRunning] = useState(false)
  const [runResult, setRunResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchTargets = async () => {
      try {
        const projects = await apiClient.getProjects()
        if (projects.length > 0) {
          const discovered = await apiClient.discoverTargets(projects[0].path)
          setTargets(discovered.map((t: any) => t.qualname))
          if (projects[0].config?.default_backend) {
            setConfig(c => ({ ...c, backend: projects[0].config.default_backend }))
          }
          if (projects[0].config?.optimization_budget) {
            setConfig(c => ({ ...c, budget: projects[0].config.optimization_budget }))
          }
          if (projects[0].config?.surrogate?.model) {
            setSurrogateModel(projects[0].config.surrogate.model)
          }
        }
      } catch { /* ignore */ }
    }
    fetchTargets()
  }, [])

  const handleStartOptimization = async () => {
    setIsRunning(true)
    setError(null)
    setRunResult(null)
    try {
      const projects = await apiClient.getProjects()
      const projectPath = projects[0]?.path || '.'
      const result = await apiClient.runOptimization(projectPath, config)
      setRunResult(result)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to start optimization')
    } finally {
      setIsRunning(false)
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-joule-ink">Optimization</h1>
        <p className="text-joule-muted mt-2">
          Run full optimization to find performance improvements
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Configuration Panel */}
        <div className="joule-panel">
          <h2 className="text-xl font-semibold text-joule-ink mb-6">Configuration</h2>

          <div className="space-y-6">
            {/* Target Selection */}
            <div>
              <label className="block text-sm font-medium text-joule-ink mb-2">Target Function</label>
              <select
                value={config.target}
                onChange={(e) => setConfig({ ...config, target: e.target.value })}
                className="w-full px-3 py-2 border border-joule-border rounded-lg focus:outline-none focus:ring-2 focus:ring-joule-accent"
              >
                <option value="">Select a target...</option>
                {targets.map((target) => (
                  <option key={target} value={target}>{target}</option>
                ))}
              </select>
            </div>

            {/* Backend Selection */}
            <div>
              <label className="block text-sm font-medium text-joule-ink mb-2">Energy Backend</label>
              <div className="space-y-2">
                {backends.map((backend) => (
                  <label key={backend.name} className="flex items-center p-3 border border-joule-border rounded-lg cursor-pointer hover:bg-joule-bg">
                    <input type="radio" name="backend" value={backend.name}
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

            {/* Budget */}
            <div>
              <label className="block text-sm font-medium text-joule-ink mb-2">
                Candidate Budget: {config.budget}
              </label>
              <input type="range" min="1" max="20" value={config.budget}
                onChange={(e) => setConfig({ ...config, budget: parseInt(e.target.value) })}
                className="w-full"
              />
              <p className="text-xs text-joule-muted mt-1">Maximum number of candidates to evaluate</p>
            </div>

            {/* Parallel Workers */}
            <div>
              <label className="block text-sm font-medium text-joule-ink mb-2">
                Parallel Workers: {config.parallel}
              </label>
              <input type="range" min="1" max="8" value={config.parallel}
                onChange={(e) => setConfig({ ...config, parallel: parseInt(e.target.value) })}
                className="w-full"
              />
            </div>

            {/* Improvement Threshold */}
            <div>
              <label className="block text-sm font-medium text-joule-ink mb-2">
                Improvement Threshold: {(config.improvement_threshold * 100).toFixed(1)}%
              </label>
              <input type="range" min="0" max="20"
                value={config.improvement_threshold * 100}
                onChange={(e) => setConfig({ ...config, improvement_threshold: parseInt(e.target.value) / 100 })}
                className="w-full"
              />
              <p className="text-xs text-joule-muted mt-1">Minimum improvement required for candidate acceptance</p>
            </div>

            {/* Toggle Options */}
            <div className="space-y-3">
              {[
                { label: 'Deep Analysis', key: 'analysis' as const },
                { label: 'Use Cache', key: 'cache' as const },
                { label: 'Fresh Surrogate', key: 'fresh_surrogate' as const },
              ].map(({ label, key }) => (
                <div key={key} className="flex items-center justify-between">
                  <label className="text-sm font-medium text-joule-ink">{label}</label>
                  <button type="button"
                    onClick={() => setConfig({ ...config, [key]: !config[key] })}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      config[key] ? 'bg-joule-accent' : 'bg-joule-border'
                    }`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      config[key] ? 'translate-x-6' : 'translate-x-1'
                    }`} />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Action Button */}
          <button onClick={handleStartOptimization}
            disabled={!config.target || isRunning}
            className="w-full mt-6 joule-button joule-button-primary flex items-center justify-center"
          >
            {isRunning ? (
              <><Zap className="w-4 h-4 mr-2 animate-pulse" /> Starting Optimization…</>
            ) : (
              <><Play className="w-4 h-4 mr-2" /> Start Optimization</>
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
                <span className="font-medium">Optimization started!</span>
              </div>
              <div className="text-sm text-green-800 space-y-1">
                <p>Run ID: <span className="font-mono">{runResult.run_id}</span></p>
                <p>Status: {runResult.status}</p>
              </div>
              <button className="mt-3 joule-button joule-button-secondary text-sm"
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
              {[
                ['Target', config.target || 'Not selected'],
                ['Backend', config.backend],
                ['Surrogate', surrogateModel],
                ['Budget', `${config.budget} candidates`],
                ['Parallel', `${config.parallel} workers`],
                ['Threshold', `${(config.improvement_threshold * 100).toFixed(1)}%`],
                ['Analysis', config.analysis ? 'Enabled' : 'Disabled'],
              ].map(([label, value]) => (
                <div key={label as string} className="flex justify-between text-sm">
                  <span className="text-joule-muted">{label}:</span>
                  <span>{value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Optimization Tips */}
          <div className="joule-panel">
            <h3 className="text-lg font-semibold text-joule-ink mb-4 flex items-center">
              <TrendingUp className="w-5 h-5 mr-2" />
              Optimization Tips
            </h3>
            <ul className="space-y-2 text-sm text-joule-muted">
              <li>• Higher budgets explore more optimization opportunities</li>
              <li>• Enable deep analysis for detailed candidate insights</li>
              <li>• Use parallel workers to speed up evaluation</li>
              <li>• Adjust threshold based on your improvement needs</li>
              <li>• Fresh surrogate ignores previous optimization data</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
