import { useState } from 'react'
import { Zap, Play, Settings, BarChart3, TrendingUp, AlertCircle } from 'lucide-react'

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
  const [config, setConfig] = useState<OptimizationConfig>({
    target: '',
    workloads: [],
    backend: 'mock',
    budget: 6,
    analysis: true,
    cache: true,
    fresh_surrogate: false,
    parallel: 1,
    improvement_threshold: 0.05,
  })
  
  const [isRunning, setIsRunning] = useState(false)
  const [progress, setProgress] = useState(0)
  const [currentPhase, setCurrentPhase] = useState('')

  const mockTargets = [
    'example.process_data',
    'ExampleClass.analyze',
    'utils.async_transform',
  ]

  const mockBackends = [
    { name: 'mock', description: 'Mock backend for testing' },
    { name: 'rapl', description: 'Intel RAPL energy measurement' },
  ]

  const optimizationPhases = [
    'Initializing optimization...',
    'Running baseline measurement...',
    'Building surrogate model...',
    'Generating candidates...',
    'Evaluating candidates...',
    'Updating surrogate model...',
    'Finalizing results...',
  ]

  const handleStartOptimization = () => {
    setIsRunning(true)
    setProgress(0)
    
    let phaseIndex = 0
    const phaseProgress = 100 / optimizationPhases.length
    
    const interval = setInterval(() => {
      setProgress((prev) => {
        const newProgress = prev + phaseProgress / 10
        if (newProgress >= (phaseIndex + 1) * phaseProgress && phaseIndex < optimizationPhases.length - 1) {
          phaseIndex++
          setCurrentPhase(optimizationPhases[phaseIndex])
        }
        
        if (newProgress >= 100) {
          clearInterval(interval)
          setIsRunning(false)
          setCurrentPhase('Optimization complete!')
          return 100
        }
        return newProgress
      })
    }, 200)
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
              <label className="block text-sm font-medium text-joule-ink mb-2">
                Target Function
              </label>
              <select
                value={config.target}
                onChange={(e) => setConfig({ ...config, target: e.target.value })}
                className="w-full px-3 py-2 border border-joule-border rounded-lg focus:outline-none focus:ring-2 focus:ring-joule-accent"
              >
                <option value="">Select a target...</option>
                {mockTargets.map((target) => (
                  <option key={target} value={target}>
                    {target}
                  </option>
                ))}
              </select>
            </div>

            {/* Backend Selection */}
            <div>
              <label className="block text-sm font-medium text-joule-ink mb-2">
                Energy Backend
              </label>
              <div className="space-y-2">
                {mockBackends.map((backend) => (
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
                      <div className="font-medium text-joule-ink">
                        {backend.name}
                      </div>
                      <div className="text-sm text-joule-muted">
                        {backend.description}
                      </div>
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
              <input
                type="range"
                min="1"
                max="20"
                value={config.budget}
                onChange={(e) => setConfig({ ...config, budget: parseInt(e.target.value) })}
                className="w-full"
              />
              <p className="text-xs text-joule-muted mt-1">
                Maximum number of candidates to evaluate
              </p>
            </div>

            {/* Parallel Workers */}
            <div>
              <label className="block text-sm font-medium text-joule-ink mb-2">
                Parallel Workers: {config.parallel}
              </label>
              <input
                type="range"
                min="1"
                max="8"
                value={config.parallel}
                onChange={(e) => setConfig({ ...config, parallel: parseInt(e.target.value) })}
                className="w-full"
              />
            </div>

            {/* Improvement Threshold */}
            <div>
              <label className="block text-sm font-medium text-joule-ink mb-2">
                Improvement Threshold: {(config.improvement_threshold * 100).toFixed(1)}%
              </label>
              <input
                type="range"
                min="0"
                max="20"
                value={config.improvement_threshold * 100}
                onChange={(e) => setConfig({ ...config, improvement_threshold: parseInt(e.target.value) / 100 })}
                className="w-full"
              />
              <p className="text-xs text-joule-muted mt-1">
                Minimum improvement required for candidate acceptance
              </p>
            </div>

            {/* Options */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-joule-ink">
                  Deep Analysis
                </label>
                <button
                  type="button"
                  onClick={() => setConfig({ ...config, analysis: !config.analysis })}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    config.analysis ? 'bg-joule-accent' : 'bg-joule-border'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      config.analysis ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>

              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-joule-ink">
                  Use Cache
                </label>
                <button
                  type="button"
                  onClick={() => setConfig({ ...config, cache: !config.cache })}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    config.cache ? 'bg-joule-accent' : 'bg-joule-border'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      config.cache ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>

              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-joule-ink">
                  Fresh Surrogate
                </label>
                <button
                  type="button"
                  onClick={() => setConfig({ ...config, fresh_surrogate: !config.fresh_surrogate })}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                    config.fresh_surrogate ? 'bg-joule-accent' : 'bg-joule-border'
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      config.fresh_surrogate ? 'translate-x-6' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            </div>
          </div>

          {/* Action Button */}
          <button
            onClick={handleStartOptimization}
            disabled={!config.target || isRunning}
            className="w-full mt-6 joule-button joule-button-primary flex items-center justify-center"
          >
            {isRunning ? (
              <>
                <Zap className="w-4 h-4 mr-2 animate-pulse" />
                Optimizing...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                Start Optimization
              </>
            )}
          </button>
        </div>

        {/* Progress & Results Panel */}
        <div className="space-y-6">
          {/* Progress */}
          {isRunning && (
            <div className="joule-panel">
              <h3 className="text-lg font-semibold text-joule-ink mb-4">Progress</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-joule-muted">Completion</span>
                  <span className="font-medium">{Math.round(progress)}%</span>
                </div>
                <div className="w-full bg-joule-border rounded-full h-2">
                  <div
                    className="bg-joule-accent h-2 rounded-full transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
                <div className="text-sm text-joule-italic text-joule-accent">
                  {currentPhase}
                </div>
              </div>
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
                <span className="text-joule-muted">Budget:</span>
                <span>{config.budget} candidates</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-joule-muted">Parallel:</span>
                <span>{config.parallel} workers</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-joule-muted">Threshold:</span>
                <span>{(config.improvement_threshold * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-joule-muted">Analysis:</span>
                <span>{config.analysis ? 'Enabled' : 'Disabled'}</span>
              </div>
            </div>
          </div>

          {/* Expected Outcomes */}
          <div className="joule-panel">
            <h3 className="text-lg font-semibold text-joule-ink mb-4 flex items-center">
              <TrendingUp className="w-5 h-5 mr-2" />
              Expected Outcomes
            </h3>
            <div className="space-y-3">
              <div className="p-3 bg-joule-bg rounded-lg">
                <div className="text-sm text-joule-muted">Candidates Generated</div>
                <div className="text-lg font-semibold text-joule-ink">{config.budget}</div>
              </div>
              <div className="p-3 bg-joule-bg rounded-lg">
                <div className="text-sm text-joule-muted">Expected Improvements</div>
                <div className="text-lg font-semibold text-joule-ink">2-4 candidates</div>
              </div>
              <div className="p-3 bg-joule-bg rounded-lg">
                <div className="text-sm text-joule-muted">Est. Duration</div>
                <div className="text-lg font-semibold text-joule-ink">
                  {~(config.budget * 2 / config.parallel)} min
                </div>
              </div>
            </div>
          </div>

          {/* Optimization Tips */}
          <div className="joule-panel">
            <h3 className="text-lg font-semibold text-joule-ink mb-4 flex items-center">
              <AlertCircle className="w-5 h-5 mr-2" />
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
