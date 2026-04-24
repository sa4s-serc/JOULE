import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Eye, Code, TrendingUp, AlertCircle, Download, ChevronRight, RefreshCw } from 'lucide-react'
import { apiClient, formatBytes, formatImprovement } from '../utils/api'
import { HotspotsView } from '../components/HotspotsView'

interface RunDetails {
  run_id: string
  run_type: 'baseline' | 'optimize' | 'resume'
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  target_qualname: string
  backend: string
  created_at: string
  completed_at?: string
  metadata?: Record<string, any>
  baseline?: {
    energy_j: number
    wall_time_s: number
    cpu_time_s: number
    peak_memory_bytes: number
  }
  candidates?: Array<{
    candidate_id: string
    operator_name: string
    operator_tier: string
    status: 'accepted' | 'rejected' | 'pending'
    measurements?: {
      energy_j: number
      wall_time_s: number
      cpu_time_s: number
      peak_memory_bytes: number
    }
    improvements?: {
      energy_ratio: number
      time_ratio: number
      memory_ratio: number
    }
    explanation?: string
    rejection_reason?: string
  }>
  hotspots?: Record<string, any>
}

interface Artifact {
  name: string
  path?: string
  kind?: string
  size: number
  created_at?: string
}

export default function Inspect() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const [runDetails, setRunDetails] = useState<RunDetails | null>(null)
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [selectedCandidate, setSelectedCandidate] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'candidates' | 'hotspots' | 'artifacts'>('overview')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchRunDetails = async () => {
    if (!runId) return
    setLoading(true)
    try {
      const data = await apiClient.getRun(runId)
      setRunDetails(data)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load run details')
    } finally {
      setLoading(false)
    }
  }

  const fetchArtifacts = async () => {
    if (!runId) return
    try {
      const data = await apiClient.getRunArtifacts(runId)
      setArtifacts(data)
    } catch {
      // optional
    }
  }

  useEffect(() => {
    fetchRunDetails()
    fetchArtifacts()

    // If running, poll for updates
    const interval = setInterval(() => {
      if (runDetails?.status === 'running') {
        fetchRunDetails()
      }
    }, 5000)
    return () => clearInterval(interval)
  }, [runId])

  const tabs = [
    { id: 'overview', label: 'Overview', icon: Eye },
    { id: 'candidates', label: 'Candidates', icon: Code },
    { id: 'hotspots', label: 'Hotspots', icon: TrendingUp },
    { id: 'artifacts', label: 'Artifacts', icon: Download },
  ] as const

  if (loading && !runDetails) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold text-joule-ink">Inspect Run</h1>
          <p className="text-joule-muted mt-2">Loading run details…</p>
        </div>
        <div className="joule-panel p-8 text-center">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-joule-chip rounded w-1/3 mx-auto"></div>
            <div className="h-3 bg-joule-chip rounded w-1/2 mx-auto"></div>
            <div className="h-3 bg-joule-chip rounded w-1/4 mx-auto"></div>
          </div>
        </div>
      </div>
    )
  }

  if (error || !runDetails) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold text-joule-ink">Inspect Run</h1>
          <p className="text-joule-muted mt-2">Run <span className="font-mono">{runId}</span></p>
        </div>
        <div className="joule-panel border-red-200 bg-red-50 text-center py-8">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <p className="text-red-700">{error || 'Run not found'}</p>
          <button className="mt-4 joule-button joule-button-secondary" onClick={() => navigate('/results')}>
            ← Back to Results
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-joule-ink">Inspect Run</h1>
          <p className="text-joule-muted mt-2 break-all">
            Detailed analysis of <span className="font-mono">{runDetails.run_id}</span>
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button className="joule-button joule-button-secondary flex items-center" onClick={fetchRunDetails}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </button>
          {runDetails.run_type === 'optimize' && runDetails.candidates?.some(c => c.status === 'accepted') && (
            <button
              className="joule-button joule-button-primary"
              onClick={() => navigate('/apply', { state: { run_id: runDetails.run_id } })}
            >
              Apply Best Candidate →
            </button>
          )}
        </div>
      </div>

      {/* Run Info */}
      <div className="joule-panel">
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div>
            <div className="text-sm text-joule-muted">Type</div>
            <div className="font-medium">{runDetails.run_type}</div>
          </div>
          <div>
            <div className="text-sm text-joule-muted">Status</div>
            <span className={`joule-status-badge joule-status-${runDetails.status}`}>{runDetails.status}</span>
          </div>
          <div className="min-w-0">
            <div className="text-sm text-joule-muted">Target</div>
            <div className="font-mono text-sm truncate" title={runDetails.target_qualname}>{runDetails.target_qualname}</div>
          </div>
          <div>
            <div className="text-sm text-joule-muted">Backend</div>
            <div>{runDetails.backend}</div>
          </div>
          <div>
            <div className="text-sm text-joule-muted">Created</div>
            <div className="text-sm">{new Date(runDetails.created_at).toLocaleString()}</div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-joule-border">
        <nav className="flex space-x-8">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center py-2 px-1 border-b-2 transition-colors duration-200 ${
                  activeTab === tab.id
                    ? 'border-joule-accent text-joule-accent'
                    : 'border-transparent text-joule-muted hover:text-joule-ink'
                }`}
              >
                <Icon className="w-4 h-4 mr-2" />
                {tab.label}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div>
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Baseline Metrics */}
            {runDetails.baseline && (
              <div className="joule-panel">
                <h3 className="text-lg font-semibold text-joule-ink mb-4">Baseline Metrics</h3>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  {[
                    { label: 'Energy', value: `${runDetails.baseline.energy_j.toFixed(1)} J` },
                    { label: 'Wall Time', value: `${runDetails.baseline.wall_time_s.toFixed(2)} s` },
                    { label: 'CPU Time', value: `${runDetails.baseline.cpu_time_s.toFixed(2)} s` },
                    { label: 'Peak Memory', value: formatBytes(runDetails.baseline.peak_memory_bytes) },
                  ].map(({ label, value }) => (
                    <div key={label} className="p-3 bg-joule-bg rounded-lg">
                      <div className="text-sm text-joule-muted">{label}</div>
                      <div className="text-lg font-semibold">{value}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Optimization Summary */}
            <div className="joule-panel">
              <h3 className="text-lg font-semibold text-joule-ink mb-4">
                {runDetails.run_type === 'baseline' ? 'Baseline Summary' : 'Optimization Summary'}
              </h3>
              <div className="space-y-3">
                {runDetails.candidates && (
                  <>
                    <div className="flex justify-between">
                      <span className="text-joule-muted">Total Candidates Generated:</span>
                      <span className="font-medium">{runDetails.candidates.length}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-joule-muted">Accepted Candidates:</span>
                      <span className="font-medium text-green-600">
                        {runDetails.candidates.filter(c => c.status === 'accepted').length}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-joule-muted">Rejected Candidates:</span>
                      <span className="font-medium text-red-600">
                        {runDetails.candidates.filter(c => c.status !== 'accepted').length}
                      </span>
                    </div>
                    {runDetails.candidates.filter(c => c.status === 'accepted' && c.improvements).length > 0 && (
                      <div className="flex justify-between">
                        <span className="text-joule-muted">Best Energy Improvement:</span>
                        <span className="font-medium text-green-600">
                          {formatImprovement(Math.min(...runDetails.candidates
                            .filter((c): c is typeof c & { improvements: NonNullable<typeof c.improvements> } =>
                              c.status === 'accepted' && !!c.improvements)
                            .map(c => c.improvements.energy_ratio)))}
                        </span>
                      </div>
                    )}
                  </>
                )}
                {!runDetails.candidates?.length && runDetails.run_type === 'baseline' && (
                  <p className="text-joule-muted">Baseline run completed. No candidates generated in baseline mode.</p>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'candidates' && (
          <div className="space-y-4">
            {(!runDetails.candidates || runDetails.candidates.length === 0) ? (
              <div className="joule-panel text-center py-8">
                <Code className="w-12 h-12 text-joule-muted mx-auto mb-3" />
                <p className="text-joule-muted">No candidates for this run.</p>
              </div>
            ) : (
              runDetails.candidates.map((candidate) => (
                <div
                  key={candidate.candidate_id}
                  className="joule-panel cursor-pointer hover:bg-joule-bg"
                  onClick={() => setSelectedCandidate(
                    selectedCandidate === candidate.candidate_id ? null : candidate.candidate_id
                  )}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <ChevronRight
                        className={`w-4 h-4 transition-transform ${
                          selectedCandidate === candidate.candidate_id ? 'rotate-90' : ''
                        }`}
                      />
                      <div className="min-w-0 flex-1 pr-4">
                        <h4 className="font-medium text-joule-ink truncate" title={candidate.candidate_id}>{candidate.candidate_id}</h4>
                        <p className="text-sm text-joule-muted truncate" title={`${candidate.operator_name} • ${candidate.operator_tier}`}>
                          {candidate.operator_name} • {candidate.operator_tier}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-3">
                      <span className={`joule-status-badge joule-status-${candidate.status === 'accepted' ? 'completed' : 'failed'}`}>
                        {candidate.status}
                      </span>
                      {candidate.improvements && (
                        <div className="text-sm">
                          <span className="text-green-600">
                            {formatImprovement(candidate.improvements.energy_ratio)} energy
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {selectedCandidate === candidate.candidate_id && (
                    <div className="mt-4 pt-4 border-t border-joule-border space-y-4">
                      {/* Measurements */}
                      {candidate.measurements && (
                        <div>
                          <h5 className="font-medium text-joule-ink mb-2">Measurements</h5>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                            {[
                              { label: 'Energy', value: `${candidate.measurements.energy_j.toFixed(1)} J` },
                              { label: 'Wall Time', value: `${candidate.measurements.wall_time_s.toFixed(2)} s` },
                              { label: 'CPU Time', value: `${candidate.measurements.cpu_time_s.toFixed(2)} s` },
                              { label: 'Memory', value: formatBytes(candidate.measurements.peak_memory_bytes) },
                            ].map(({ label, value }) => (
                              <div key={label}>
                                <span className="text-joule-muted">{label}:</span>
                                <span className="ml-2 font-medium">{value}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Improvements */}
                      {candidate.improvements && (
                        <div>
                          <h5 className="font-medium text-joule-ink mb-2">Improvements</h5>
                          <div className="grid grid-cols-3 gap-3 text-sm">
                            {[
                              { label: 'Energy', ratio: candidate.improvements.energy_ratio },
                              { label: 'Time', ratio: candidate.improvements.time_ratio },
                              { label: 'Memory', ratio: candidate.improvements.memory_ratio },
                            ].map(({ label, ratio }) => (
                              <div key={label}>
                                <span className="text-joule-muted">{label}:</span>
                                <span className={`ml-2 font-medium ${ratio < 1 ? 'text-green-600' : 'text-red-600'}`}>
                                  {formatImprovement(ratio)}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {candidate.explanation && (
                        <div>
                          <h5 className="font-medium text-joule-ink mb-2">Explanation</h5>
                          <p className="text-sm text-joule-muted break-all">{candidate.explanation}</p>
                        </div>
                      )}

                      {candidate.rejection_reason && (
                        <div>
                          <h5 className="font-medium text-joule-ink mb-2 flex items-center">
                            <AlertCircle className="w-4 h-4 mr-2 text-red-600" />
                            Rejection Reason
                          </h5>
                          <p className="text-sm text-red-600 break-all">{candidate.rejection_reason}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'hotspots' && (
          <div className="space-y-6">
            {runDetails.hotspots ? (
              <HotspotsView hotspots={runDetails.hotspots} />
            ) : (
              <div className="joule-panel text-center py-8">
                <TrendingUp className="w-12 h-12 text-joule-muted mx-auto mb-3" />
                <p className="text-joule-muted">No hotspot data available for this run.</p>
              </div>
            )}
          </div>
        )}

        {activeTab === 'artifacts' && (
          <div className="joule-panel">
            <h3 className="text-lg font-semibold text-joule-ink mb-4">Run Artifacts</h3>
            {artifacts.length === 0 ? (
              <div className="text-center py-8 text-joule-muted">
                <Download className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>No artifacts found for this run.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {artifacts.map((artifact) => (
                  <div key={artifact.name} className="flex items-center justify-between p-3 border border-joule-border rounded-lg hover:bg-joule-bg">
                    <div className="min-w-0 flex-1 pr-4">
                      <div className="font-medium text-joule-ink truncate" title={artifact.name}>{artifact.name}</div>
                      <div className="text-sm text-joule-muted truncate">
                        {formatBytes(artifact.size)}
                        {artifact.created_at && ` • ${new Date(artifact.created_at).toLocaleString()}`}
                      </div>
                    </div>
                    <a
                      href={`/api/runs/${runDetails.run_id}/artifacts/${artifact.name}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="joule-button joule-button-secondary text-sm flex items-center"
                    >
                      <Download className="w-4 h-4 mr-2" />
                      Download
                    </a>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

