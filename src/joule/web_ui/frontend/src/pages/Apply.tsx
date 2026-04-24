import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { CheckCircle, AlertCircle, GitBranch, Save, RefreshCw } from 'lucide-react'
import { apiClient, formatImprovement } from '../utils/api'

interface Candidate {
  candidate_id: string
  operator_name: string
  operator_tier: string
  status: string
  improvements?: {
    energy_ratio: number
    time_ratio: number
    memory_ratio: number
  }
  explanation?: string
}

interface RunOption {
  run_id: string
  target_qualname: string
  candidates: Candidate[]
}

export default function Apply() {
  const location = useLocation()
  const navigate = useNavigate()
  const initialRunId = (location.state as any)?.run_id || ''

  const [runs, setRuns] = useState<RunOption[]>([])
  const [selectedRun, setSelectedRun] = useState<string>(initialRunId)
  const [selectedCandidate, setSelectedCandidate] = useState<string>('')
  const [applyConfig, setApplyConfig] = useState({
    branch: true,
    commit: false,
  })
  const [isApplying, setIsApplying] = useState(false)
  const [applyResult, setApplyResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchRuns = async () => {
    try {
      const allRuns = await apiClient.getRuns()
      // Only show completed optimization runs that might have accepted candidates
      const optimizeRuns = allRuns.filter((r: any) =>
        r.run_type === 'optimize' && r.status === 'completed'
      )

      // Fetch details for each to get candidates
      const runOptions: RunOption[] = []
      for (const run of optimizeRuns) {
        try {
          const detail = await apiClient.getRun(run.run_id)
          const acceptedCandidates = (detail.candidates || []).filter(
            (c: any) => c.status === 'accepted' || c.status === 'frontier_active'
          )
          if (acceptedCandidates.length > 0) {
            runOptions.push({
              run_id: run.run_id,
              target_qualname: detail.target_qualname || 'unknown',
              candidates: acceptedCandidates,
            })
          }
        } catch {
          // Skip broken runs
        }
      }

      setRuns(runOptions)

      // Auto-select the first candidate if a run is pre-selected
      if (initialRunId) {
        const matching = runOptions.find(r => r.run_id === initialRunId)
        if (matching && matching.candidates.length > 0) {
          setSelectedCandidate(matching.candidates[0].candidate_id)
        }
      }
    } catch (err) {
      console.warn('Failed to fetch runs for apply:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchRuns()
  }, [])

  const selectedRunData = runs.find(r => r.run_id === selectedRun)

  const handleApply = async () => {
    if (!selectedRun || !selectedCandidate) return
    setIsApplying(true)
    setError(null)
    setApplyResult(null)
    try {
      const result = await apiClient.applyCandidate(selectedRun, {
        run_id: selectedRun,
        candidate_id: selectedCandidate,
        branch: applyConfig.branch,
        commit_changes: applyConfig.commit,
      })
      setApplyResult(result)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to apply candidate')
    } finally {
      setIsApplying(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold text-joule-ink">Apply Optimization</h1>
          <p className="text-joule-muted mt-2">Loading available candidates…</p>
        </div>
        <div className="animate-pulse joule-panel h-48" />
      </div>
    )
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-joule-ink">Apply Optimization</h1>
          <p className="text-joule-muted mt-2">
            Apply accepted candidates to your source code
          </p>
        </div>
        <button className="joule-button joule-button-secondary flex items-center" onClick={fetchRuns}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </button>
      </div>

      {runs.length === 0 ? (
        <div className="joule-panel text-center py-12">
          <CheckCircle className="w-12 h-12 text-joule-muted mx-auto mb-4" />
          <h3 className="text-lg font-medium text-joule-ink mb-2">No candidates to apply</h3>
          <p className="text-joule-muted mb-4">
            Run an optimization first to generate candidates that can be applied.
          </p>
          <button className="joule-button joule-button-primary" onClick={() => navigate('/optimize')}>
            Start Optimization
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Selection Panel */}
          <div className="space-y-6">
            {/* Run Selection */}
            <div className="joule-panel">
              <h2 className="text-xl font-semibold text-joule-ink mb-4">Select Run</h2>
              <select
                value={selectedRun}
                onChange={(e) => {
                  setSelectedRun(e.target.value)
                  setSelectedCandidate('')
                  setApplyResult(null)
                }}
                className="w-full px-3 py-2 border border-joule-border rounded-lg focus:outline-none focus:ring-2 focus:ring-joule-accent"
              >
                <option value="">Select a run...</option>
                {runs.map((run) => (
                  <option key={run.run_id} value={run.run_id}>
                    {run.run_id.substring(0, 8)}... — {run.target_qualname.length > 30 ? run.target_qualname.substring(0, 30) + '...' : run.target_qualname} ({run.candidates.length} accepted)
                  </option>
                ))}
              </select>
            </div>

            {/* Candidate Selection */}
            {selectedRunData && (
              <div className="joule-panel">
                <h2 className="text-xl font-semibold text-joule-ink mb-4">Select Candidate</h2>
                <div className="space-y-3">
                  {selectedRunData.candidates.map((candidate) => (
                    <div
                      key={candidate.candidate_id}
                      onClick={() => {
                        setSelectedCandidate(candidate.candidate_id)
                        setApplyResult(null)
                      }}
                      className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                        selectedCandidate === candidate.candidate_id
                          ? 'border-joule-accent bg-joule-chip'
                          : 'border-joule-border hover:bg-joule-bg'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="min-w-0 flex-1 pr-4">
                          <h4 className="font-medium text-joule-ink truncate" title={candidate.candidate_id}>{candidate.candidate_id}</h4>
                          <p className="text-sm text-joule-muted truncate" title={candidate.operator_name}>{candidate.operator_name}</p>
                        </div>
                        <span className="joule-chip">{candidate.operator_tier}</span>
                      </div>

                      {candidate.improvements && (
                        <div className="grid grid-cols-3 gap-2 text-sm">
                          {[
                            { label: 'Energy', ratio: candidate.improvements.energy_ratio },
                            { label: 'Time', ratio: candidate.improvements.time_ratio },
                            { label: 'Memory', ratio: candidate.improvements.memory_ratio },
                          ].map(({ label, ratio }) => (
                            <div key={label} className={`p-2 rounded text-center ${ratio < 1 ? 'bg-green-50' : 'bg-red-50'}`}>
                              <div className={`font-medium ${ratio < 1 ? 'text-green-600' : 'text-red-600'}`}>
                                {formatImprovement(ratio)}
                              </div>
                              <div className="text-xs text-joule-muted">{label}</div>
                            </div>
                          ))}
                        </div>
                      )}

                      {candidate.explanation && (
                        <p className="text-sm text-joule-muted mt-2">{candidate.explanation}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Apply Configuration + Result Panel */}
          <div className="space-y-6">
            {/* Error */}
            {error && (
              <div className="joule-panel border-red-200 bg-red-50">
                <div className="flex items-center text-red-700">
                  <AlertCircle className="w-5 h-5 mr-2" />
                  <span className="break-all">{error}</span>
                </div>
              </div>
            )}

            {/* Apply Result */}
            {applyResult && (
              <div className="joule-panel border-green-200 bg-green-50">
                <div className="flex items-center text-green-700 mb-3">
                  <CheckCircle className="w-5 h-5 mr-2" />
                  <span className="font-medium">Candidate applied successfully!</span>
                </div>
                <div className="text-sm text-green-800 space-y-1">
                  <p>Run ID: <span className="font-mono break-all">{applyResult.run_id}</span></p>
                  <p>Candidate: <span className="font-mono break-all">{applyResult.candidate_id}</span></p>
                  {applyResult.branch_created && <p>Git branch created</p>}
                  {applyResult.commit_created && <p>Git commit created</p>}
                </div>
              </div>
            )}

            {/* Apply Options */}
            <div className="joule-panel">
              <h2 className="text-xl font-semibold text-joule-ink mb-4">Apply Options</h2>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm font-medium text-joule-ink flex items-center">
                      <GitBranch className="w-4 h-4 mr-2" />
                      Create Git Branch
                    </label>
                    <p className="text-xs text-joule-muted mt-1">Creates a new branch for the changes</p>
                  </div>
                  <button type="button"
                    onClick={() => setApplyConfig({ ...applyConfig, branch: !applyConfig.branch })}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      applyConfig.branch ? 'bg-joule-accent' : 'bg-joule-border'
                    }`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      applyConfig.branch ? 'translate-x-6' : 'translate-x-1'
                    }`} />
                  </button>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm font-medium text-joule-ink flex items-center">
                      <Save className="w-4 h-4 mr-2" />
                      Auto Commit
                    </label>
                    <p className="text-xs text-joule-muted mt-1">Automatically commits the applied changes</p>
                  </div>
                  <button type="button"
                    onClick={() => setApplyConfig({ ...applyConfig, commit: !applyConfig.commit })}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      applyConfig.commit ? 'bg-joule-accent' : 'bg-joule-border'
                    }`}
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      applyConfig.commit ? 'translate-x-6' : 'translate-x-1'
                    }`} />
                  </button>
                </div>
              </div>
            </div>

            {/* Apply Button */}
            <button
              onClick={handleApply}
              disabled={!selectedRun || !selectedCandidate || isApplying}
              className="w-full joule-button joule-button-primary flex items-center justify-center"
            >
              {isApplying ? (
                <><RefreshCw className="w-4 h-4 mr-2 animate-spin" /> Applying…</>
              ) : (
                <><CheckCircle className="w-4 h-4 mr-2" /> Apply Selected Candidate</>
              )}
            </button>

            {/* Warning */}
            <div className="joule-panel border-yellow-200 bg-yellow-50">
              <div className="flex items-start text-yellow-800">
                <AlertCircle className="w-5 h-5 mr-2 flex-shrink-0 mt-0.5" />
                <div className="text-sm">
                  <p className="font-medium">Important</p>
                  <p className="mt-1">Applying a candidate will modify your source files. Make sure you have committed or stashed any uncommitted changes first.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
