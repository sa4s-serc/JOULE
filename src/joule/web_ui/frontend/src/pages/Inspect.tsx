import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { Eye, Code, TrendingUp, AlertCircle, Download, ChevronRight } from 'lucide-react'

interface RunDetails {
  run_id: string
  run_type: 'baseline' | 'optimize' | 'resume'
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  target_qualname: string
  backend: string
  created_at: string
  completed_at?: string
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
  hotspots?: {
    signal_quality: {
      low_signal: boolean
      project_share: number
      target_share: number
    }
    recommendations: string[]
    overall_hotspots: Array<{
      file: string
      function: string
      share: number
    }>
  }
}

export default function Inspect() {
  const { runId } = useParams<{ runId: string }>()
  const [runDetails, setRunDetails] = useState<RunDetails | null>(null)
  const [selectedCandidate, setSelectedCandidate] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'candidates' | 'hotspots' | 'artifacts'>('overview')

  useEffect(() => {
    // TODO: Fetch run details from API
    const mockRunDetails: RunDetails = {
      run_id: runId || 'run_20240423_001',
      run_type: 'optimize',
      status: 'completed',
      target_qualname: 'example.process_data',
      backend: 'mock',
      created_at: '2024-04-23T10:30:00Z',
      completed_at: '2024-04-23T10:45:00Z',
      baseline: {
        energy_j: 125.5,
        wall_time_s: 2.34,
        cpu_time_s: 2.12,
        peak_memory_bytes: 52428800,
      },
      candidates: [
        {
          candidate_id: 'candidate_001',
          operator_name: 'loop_membership_set_cache',
          operator_tier: 'tier_1',
          status: 'accepted',
          measurements: {
            energy_j: 108.2,
            wall_time_s: 2.01,
            cpu_time_s: 1.89,
            peak_memory_bytes: 49152000,
          },
          improvements: {
            energy_ratio: 0.86,
            time_ratio: 0.86,
            memory_ratio: 0.94,
          },
          explanation: 'Optimized loop membership checks using set cache',
        },
        {
          candidate_id: 'candidate_002',
          operator_name: 'list_comprehension_transform',
          operator_tier: 'tier_2',
          status: 'rejected',
          measurements: {
            energy_j: 132.1,
            wall_time_s: 2.45,
            cpu_time_s: 2.28,
            peak_memory_bytes: 55050240,
          },
          rejection_reason: 'No significant improvement, slight regression in memory',
        },
      ],
      hotspots: {
        signal_quality: {
          low_signal: false,
          project_share: 0.85,
          target_share: 0.92,
        },
        recommendations: [
          'Focus on optimizing the main processing loop',
          'Consider memory-efficient data structures',
          'Profile I/O operations for potential gains',
        ],
        overall_hotspots: [
          { file: 'example/main.py', function: 'process_data', share: 0.45 },
          { file: 'example/main.py', function: 'validate_input', share: 0.23 },
          { file: 'utils/helpers.py', function: 'format_output', share: 0.12 },
        ],
      },
    }
    setRunDetails(mockRunDetails)
  }, [runId])

  if (!runDetails) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-joule-muted">Loading run details...</div>
      </div>
    )
  }

  const formatBytes = (bytes: number) => {
    const mb = bytes / (1024 * 1024)
    return `${mb.toFixed(1)} MB`
  }

  const formatImprovement = (ratio: number) => {
    const improvement = (1 - ratio) * 100
    const sign = improvement > 0 ? '-' : '+'
    return `${sign}${Math.abs(improvement).toFixed(1)}%`
  }

  const tabs = [
    { id: 'overview', label: 'Overview', icon: Eye },
    { id: 'candidates', label: 'Candidates', icon: Code },
    { id: 'hotspots', label: 'Hotspots', icon: TrendingUp },
    { id: 'artifacts', label: 'Artifacts', icon: Download },
  ]

  if (!runDetails) {
    return (
      <div className="space-y-8">
        <div>
          <h1 className="text-3xl font-bold text-joule-ink">Inspect Run</h1>
          <p className="text-joule-muted mt-2">Loading run details...</p>
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

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-joule-ink">Inspect Run</h1>
        <p className="text-joule-muted mt-2">
          Detailed analysis of <span className="font-mono">{runDetails.run_id}</span>
        </p>
      </div>

      {/* Run Info */}
      <div className="joule-panel">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <div className="text-sm text-joule-muted">Type</div>
            <div className="font-medium">{runDetails.run_type}</div>
          </div>
          <div>
            <div className="text-sm text-joule-muted">Status</div>
            <span className={`joule-status-badge joule-status-${runDetails.status}`}>
              {runDetails.status}
            </span>
          </div>
          <div>
            <div className="text-sm text-joule-muted">Target</div>
            <div className="font-mono text-sm">{runDetails.target_qualname}</div>
          </div>
          <div>
            <div className="text-sm text-joule-muted">Backend</div>
            <div>{runDetails.backend}</div>
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
                onClick={() => setActiveTab(tab.id as any)}
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
                  <div className="p-3 bg-joule-bg rounded-lg">
                    <div className="text-sm text-joule-muted">Energy</div>
                    <div className="text-lg font-semibold">{runDetails.baseline.energy_j.toFixed(1)} J</div>
                  </div>
                  <div className="p-3 bg-joule-bg rounded-lg">
                    <div className="text-sm text-joule-muted">Wall Time</div>
                    <div className="text-lg font-semibold">{runDetails.baseline.wall_time_s.toFixed(2)} s</div>
                  </div>
                  <div className="p-3 bg-joule-bg rounded-lg">
                    <div className="text-sm text-joule-muted">CPU Time</div>
                    <div className="text-lg font-semibold">{runDetails.baseline.cpu_time_s.toFixed(2)} s</div>
                  </div>
                  <div className="p-3 bg-joule-bg rounded-lg">
                    <div className="text-sm text-joule-muted">Peak Memory</div>
                    <div className="text-lg font-semibold">{formatBytes(runDetails.baseline.peak_memory_bytes)}</div>
                  </div>
                </div>
              </div>
            )}

            {/* Summary */}
            <div className="joule-panel">
              <h3 className="text-lg font-semibold text-joule-ink mb-4">Optimization Summary</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-joule-muted">Total Candidates Generated:</span>
                  <span className="font-medium">{runDetails.candidates?.length || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-joule-muted">Accepted Candidates:</span>
                  <span className="font-medium text-green-600">
                    {runDetails.candidates?.filter(c => c.status === 'accepted').length || 0}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-joule-muted">Rejected Candidates:</span>
                  <span className="font-medium text-red-600">
                    {runDetails.candidates?.filter(c => c.status === 'rejected').length || 0}
                  </span>
                </div>
                {runDetails.candidates && runDetails.candidates.filter(c => c.status === 'accepted').length > 0 && (
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
              </div>
            </div>
          </div>
        )}

        {activeTab === 'candidates' && (
          <div className="space-y-4">
            {runDetails.candidates?.map((candidate) => (
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
                    <div>
                      <h4 className="font-medium text-joule-ink">{candidate.candidate_id}</h4>
                      <p className="text-sm text-joule-muted">
                        {candidate.operator_name} • {candidate.operator_tier}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-3">
                    <span className={`joule-status-badge joule-status-${candidate.status}`}>
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
                          <div>
                            <span className="text-joule-muted">Energy:</span>
                            <span className="ml-2 font-medium">{candidate.measurements.energy_j.toFixed(1)} J</span>
                          </div>
                          <div>
                            <span className="text-joule-muted">Wall Time:</span>
                            <span className="ml-2 font-medium">{candidate.measurements.wall_time_s.toFixed(2)} s</span>
                          </div>
                          <div>
                            <span className="text-joule-muted">CPU Time:</span>
                            <span className="ml-2 font-medium">{candidate.measurements.cpu_time_s.toFixed(2)} s</span>
                          </div>
                          <div>
                            <span className="text-joule-muted">Memory:</span>
                            <span className="ml-2 font-medium">{formatBytes(candidate.measurements.peak_memory_bytes)}</span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Improvements */}
                    {candidate.improvements && (
                      <div>
                        <h5 className="font-medium text-joule-ink mb-2">Improvements</h5>
                        <div className="grid grid-cols-3 gap-3 text-sm">
                          <div>
                            <span className="text-joule-muted">Energy:</span>
                            <span className={`ml-2 font-medium ${
                              candidate.improvements.energy_ratio < 1 ? 'text-green-600' : 'text-red-600'
                            }`}>
                              {formatImprovement(candidate.improvements.energy_ratio)}
                            </span>
                          </div>
                          <div>
                            <span className="text-joule-muted">Time:</span>
                            <span className={`ml-2 font-medium ${
                              candidate.improvements.time_ratio < 1 ? 'text-green-600' : 'text-red-600'
                            }`}>
                              {formatImprovement(candidate.improvements.time_ratio)}
                            </span>
                          </div>
                          <div>
                            <span className="text-joule-muted">Memory:</span>
                            <span className={`ml-2 font-medium ${
                              candidate.improvements.memory_ratio < 1 ? 'text-green-600' : 'text-red-600'
                            }`}>
                              {formatImprovement(candidate.improvements.memory_ratio)}
                            </span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Explanation */}
                    {candidate.explanation && (
                      <div>
                        <h5 className="font-medium text-joule-ink mb-2">Explanation</h5>
                        <p className="text-sm text-joule-muted">{candidate.explanation}</p>
                      </div>
                    )}

                    {/* Rejection Reason */}
                    {candidate.rejection_reason && (
                      <div>
                        <h5 className="font-medium text-joule-ink mb-2 flex items-center">
                          <AlertCircle className="w-4 h-4 mr-2 text-red-600" />
                          Rejection Reason
                        </h5>
                        <p className="text-sm text-red-600">{candidate.rejection_reason}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {activeTab === 'hotspots' && runDetails.hotspots && (
          <div className="space-y-6">
            {/* Signal Quality */}
            {runDetails.hotspots.signal_quality && (
              <div className="joule-panel">
                <h3 className="text-lg font-semibold text-joule-ink mb-4">Signal Quality</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="p-3 bg-joule-bg rounded-lg">
                    <div className="text-sm text-joule-muted">Project Share</div>
                    <div className="text-lg font-semibold">{((runDetails.hotspots.signal_quality.project_share || 0) * 100).toFixed(1)}%</div>
                  </div>
                  <div className="p-3 bg-joule-bg rounded-lg">
                    <div className="text-sm text-joule-muted">Target Share</div>
                    <div className="text-lg font-semibold">{((runDetails.hotspots.signal_quality.target_share || 0) * 100).toFixed(1)}%</div>
                  </div>
                  <div className="p-3 bg-joule-bg rounded-lg">
                    <div className="text-sm text-joule-muted">Low Signal</div>
                    <div className="text-lg font-semibold">
                      {runDetails.hotspots.signal_quality.low_signal ? 'Yes' : 'No'}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Hotspot Functions */}
            <div className="joule-panel">
              <h3 className="text-lg font-semibold text-joule-ink mb-4">Hotspot Functions</h3>
              <div className="space-y-2">
                {runDetails.hotspots.overall_hotspots.map((hotspot, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-joule-bg rounded-lg">
                    <div>
                      <div className="font-medium text-joule-ink">{hotspot.function}</div>
                      <div className="text-sm text-joule-muted">{hotspot.file}</div>
                    </div>
                    <div className="text-sm font-medium">
                      {(hotspot.share * 100).toFixed(1)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Recommendations */}
            <div className="joule-panel">
              <h3 className="text-lg font-semibold text-joule-ink mb-4">Recommendations</h3>
              <ul className="space-y-2">
                {runDetails.hotspots.recommendations.map((recommendation, index) => (
                  <li key={index} className="flex items-start">
                    <ChevronRight className="w-4 h-4 text-joule-accent mr-2 mt-0.5 flex-shrink-0" />
                    <span className="text-sm text-joule-muted">{recommendation}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {activeTab === 'artifacts' && (
          <div className="joule-panel">
            <h3 className="text-lg font-semibold text-joule-ink mb-4">Run Artifacts</h3>
            <div className="space-y-3">
              {[
                { name: 'run_summary.json', description: 'High-level run summary' },
                { name: 'baseline.json', description: 'Baseline measurement data' },
                { name: 'optimization_analysis.json', description: 'Detailed optimization analysis' },
                { name: 'events.jsonl', description: 'Structured event timeline' },
                { name: 'best.patch', description: 'Patch for best candidate' },
                { name: 'dashboard.html', description: 'Static dashboard snapshot' },
              ].map((artifact) => (
                <div key={artifact.name} className="flex items-center justify-between p-3 border border-joule-border rounded-lg hover:bg-joule-bg">
                  <div>
                    <div className="font-medium text-joule-ink">{artifact.name}</div>
                    <div className="text-sm text-joule-muted">{artifact.description}</div>
                  </div>
                  <button className="joule-button joule-button-secondary text-sm">
                    <Download className="w-4 h-4 mr-2" />
                    Download
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
