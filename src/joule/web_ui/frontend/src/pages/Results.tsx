import { useState } from 'react'
import { 
  Search, 
  Download, 
  Eye, 
  BarChart3, 
  TrendingUp, 
  TrendingDown, 
  Minus,
  ChevronRight,
  ChevronDown,
  Code,
  X,
  Activity,
  Zap,
  CheckCircle,
  AlertCircle,
  Clock
} from 'lucide-react'

interface Run {
  run_id: string
  run_type: 'baseline' | 'optimize' | 'resume'
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  target_qualname: string
  backend: string
  created_at: string
  completed_at?: string
  metadata?: {
    total_candidates?: number
    accepted_count?: number
    best_improvement?: number
  }
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
    signal_quality?: {
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

export default function Results() {
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [expandedRun, setExpandedRun] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'candidates' | 'hotspots' | 'artifacts'>('overview')

  const mockRuns: Run[] = [
    {
      run_id: 'run_20240423_001',
      run_type: 'optimize',
      status: 'completed',
      target_qualname: 'example.process_data',
      backend: 'mock',
      created_at: '2024-04-23T10:30:00Z',
      completed_at: '2024-04-23T10:45:00Z',
      metadata: {
        total_candidates: 6,
        accepted_count: 2,
        best_improvement: 0.12,
      },
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
            energy_j: 108.0,
            wall_time_s: 2.01,
            cpu_time_s: 1.82,
            peak_memory_bytes: 51200000,
          },
          improvements: {
            energy_ratio: 0.86,
            time_ratio: 0.86,
            memory_ratio: 0.98,
          },
          explanation: 'Optimized loop membership checks using set cache',
        },
        {
          candidate_id: 'candidate_002',
          operator_name: 'list_comprehension_transform',
          operator_tier: 'tier_2',
          status: 'accepted',
          measurements: {
            energy_j: 115.5,
            wall_time_s: 2.08,
            cpu_time_s: 1.89,
            peak_memory_bytes: 53500000,
          },
          improvements: {
            energy_ratio: 0.92,
            time_ratio: 0.89,
            memory_ratio: 1.02,
          },
          explanation: 'Transformed nested loops to list comprehension',
        },
      ],
      hotspots: {
        signal_quality: {
          low_signal: false,
          project_share: 0.35,
          target_share: 0.78,
        },
        recommendations: [
          'Consider increasing workload repetitions for better signal',
          'Target function has good isolation for optimization',
        ],
        overall_hotspots: [
          { file: 'example/main.py', function: 'process_data', share: 0.78 },
          { file: 'example/utils.py', function: 'validate_input', share: 0.15 },
        ],
      },
    },
    {
      run_id: 'run_20240423_000',
      run_type: 'baseline',
      status: 'completed',
      target_qualname: 'example.process_data',
      backend: 'mock',
      created_at: '2024-04-23T09:15:00Z',
      completed_at: '2024-04-23T09:20:00Z',
      metadata: {},
      baseline: {
        energy_j: 125.5,
        wall_time_s: 2.34,
        cpu_time_s: 2.12,
        peak_memory_bytes: 52428800,
      },
    },
    {
      run_id: 'run_20240422_003',
      run_type: 'optimize',
      status: 'failed',
      target_qualname: 'utils.async_transform',
      backend: 'rapl',
      created_at: '2024-04-22T16:45:00Z',
      completed_at: '2024-04-22T16:50:00Z',
      metadata: {},
      baseline: {
        energy_j: 89.2,
        wall_time_s: 1.85,
        cpu_time_s: 1.62,
        peak_memory_bytes: 41943040,
      },
    },
    {
      run_id: 'run_20240422_002',
      run_type: 'optimize',
      status: 'running',
      target_qualname: 'ExampleClass.analyze',
      backend: 'mock',
      created_at: '2024-04-22T15:30:00Z',
      metadata: {
        total_candidates: 4,
        accepted_count: 0,
      },
      baseline: {
        energy_j: 156.0,
        wall_time_s: 3.1,
        cpu_time_s: 2.85,
        peak_memory_bytes: 67108864,
      },
    },
  ]

  const filteredRuns = mockRuns.filter((run) => {
    const matchesSearch = run.run_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         run.target_qualname.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesStatus = statusFilter === 'all' || run.status === statusFilter
    const matchesType = typeFilter === 'all' || run.run_type === typeFilter
    return matchesSearch && matchesStatus && matchesType
  })

  const getStatusIcon = (status: Run['status']) => {
    switch (status) {
      case 'completed':
        return <TrendingUp className="w-4 h-4 text-green-600" />
      case 'running':
        return <BarChart3 className="w-4 h-4 text-yellow-600 animate-pulse" />
      case 'failed':
        return <TrendingDown className="w-4 h-4 text-red-600" />
      case 'cancelled':
        return <Minus className="w-4 h-4 text-gray-600" />
    }
  }

  const getStatusColor = (status: Run['status']) => {
    switch (status) {
      case 'completed':
        return 'joule-status-completed'
      case 'running':
        return 'joule-status-running'
      case 'failed':
        return 'joule-status-failed'
      case 'cancelled':
        return 'joule-status-failed'
    }
  }

  const formatDuration = (start: string, end?: string) => {
    if (!end) return 'Running...'
    const duration = new Date(end).getTime() - new Date(start).getTime()
    const minutes = Math.floor(duration / 60000)
    const seconds = Math.floor((duration % 60000) / 1000)
    return `${minutes}m ${seconds}s`
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

  const toggleExpand = (runId: string) => {
    if (expandedRun === runId) {
      setExpandedRun(null)
    } else {
      setExpandedRun(runId)
      setActiveTab('overview')
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-joule-ink">Results</h1>
        <p className="text-joule-muted mt-2">
          Browse and analyze your optimization runs
        </p>
      </div>

      {/* Filters */}
      <div className="joule-panel">
        <div className="flex flex-col lg:flex-row gap-4">
          {/* Search */}
          <div className="flex-1">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-joule-muted" />
              <input
                type="text"
                placeholder="Search runs..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-joule-border rounded-lg focus:outline-none focus:ring-2 focus:ring-joule-accent"
              />
            </div>
          </div>

          {/* Status Filter */}
          <div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-joule-border rounded-lg focus:outline-none focus:ring-2 focus:ring-joule-accent"
            >
              <option value="all">All Status</option>
              <option value="running">Running</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          {/* Type Filter */}
          <div>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="px-3 py-2 border border-joule-border rounded-lg focus:outline-none focus:ring-2 focus:ring-joule-accent"
            >
              <option value="all">All Types</option>
              <option value="baseline">Baseline</option>
              <option value="optimize">Optimize</option>
              <option value="resume">Resume</option>
            </select>
          </div>
        </div>
      </div>

      {/* Runs Table with Expandable Inspection */}
      <div className="joule-panel">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-joule-border">
                <th className="text-left py-3 px-4 text-sm font-medium text-joule-ink w-8"></th>
                <th className="text-left py-3 px-4 text-sm font-medium text-joule-ink">Run ID</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-joule-ink">Type</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-joule-ink">Status</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-joule-ink">Target</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-joule-ink">Backend</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-joule-ink">Duration</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-joule-ink">Results</th>
              </tr>
            </thead>
            <tbody>
              {filteredRuns.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-8 text-joule-muted">
                    No runs found matching your criteria
                  </td>
                </tr>
              ) : (
                filteredRuns.map((run) => (
                  <>
                    {/* Main Row */}
                    <tr 
                      key={run.run_id} 
                      className={`border-b border-joule-border cursor-pointer transition-colors ${
                        expandedRun === run.run_id ? 'bg-joule-chip' : 'hover:bg-joule-bg'
                      }`}
                      onClick={() => toggleExpand(run.run_id)}
                    >
                      <td className="py-3 px-4">
                        <div className="text-joule-accent">
                          {expandedRun === run.run_id ? (
                            <ChevronDown className="w-5 h-5" />
                          ) : (
                            <ChevronRight className="w-5 h-5" />
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="font-mono text-sm">{run.run_id}</div>
                        <div className="text-xs text-joule-muted">
                          {new Date(run.created_at).toLocaleString()}
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="joule-chip">{run.run_type}</span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center">
                          {getStatusIcon(run.status)}
                          <span className={`ml-2 joule-status-badge ${getStatusColor(run.status)}`}>
                            {run.status}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="font-mono text-sm">{run.target_qualname}</div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="joule-chip">{run.backend}</span>
                      </td>
                      <td className="py-3 px-4 text-sm">
                        {formatDuration(run.created_at, run.completed_at)}
                      </td>
                      <td className="py-3 px-4">
                        {run.metadata?.total_candidates && (
                          <div className="text-sm">
                            <div>{run.metadata?.accepted_count || 0}/{run.metadata?.total_candidates} accepted</div>
                            {run.metadata?.best_improvement && (
                              <div className="text-green-600">
                                +{(run.metadata?.best_improvement * 100).toFixed(1)}%
                              </div>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                    
                    {/* Expanded Detail Row */}
                    {expandedRun === run.run_id && (
                      <tr>
                        <td colSpan={8} className="p-0">
                          <RunDetailView 
                            run={run} 
                            activeTab={activeTab} 
                            setActiveTab={setActiveTab}
                            formatBytes={formatBytes}
                            formatImprovement={formatImprovement}
                            onClose={() => setExpandedRun(null)}
                          />
                        </td>
                      </tr>
                    )}
                  </>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="joule-panel">
          <div className="text-center">
            <div className="text-2xl font-bold text-joule-ink">
              {mockRuns.filter(r => r.status === 'completed').length}
            </div>
            <div className="text-sm text-joule-muted">Completed</div>
          </div>
        </div>
        <div className="joule-panel">
          <div className="text-center">
            <div className="text-2xl font-bold text-joule-ink">
              {mockRuns.filter(r => r.status === 'running').length}
            </div>
            <div className="text-sm text-joule-muted">Running</div>
          </div>
        </div>
        <div className="joule-panel">
          <div className="text-center">
            <div className="text-2xl font-bold text-joule-ink">
              {mockRuns.filter(r => r.run_type === 'optimize' && r.metadata?.accepted_count && r.metadata.accepted_count > 0).length}
            </div>
            <div className="text-sm text-joule-muted">Successful Optimizations</div>
          </div>
        </div>
        <div className="joule-panel">
          <div className="text-center">
            <div className="text-2xl font-bold text-joule-ink">
              {mockRuns.reduce((acc, r) => acc + (r.metadata?.accepted_count || 0), 0)}
            </div>
            <div className="text-sm text-joule-muted">Total Improvements</div>
          </div>
        </div>
      </div>
    </div>
  )
}

// Sub-component for run detail view
interface RunDetailViewProps {
  run: Run
  activeTab: 'overview' | 'candidates' | 'hotspots' | 'artifacts'
  setActiveTab: (tab: 'overview' | 'candidates' | 'hotspots' | 'artifacts') => void
  formatBytes: (bytes: number) => string
  formatImprovement: (ratio: number) => string
  onClose: () => void
}

function RunDetailView({ run, activeTab, setActiveTab, formatBytes, formatImprovement, onClose }: RunDetailViewProps) {
  const tabs = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'candidates', label: 'Candidates', icon: Code },
    { id: 'hotspots', label: 'Hotspots', icon: Zap },
    { id: 'artifacts', label: 'Artifacts', icon: Eye },
  ] as const

  return (
    <div className="bg-joule-bg border-t border-joule-border">
      {/* Header */}
      <div className="px-6 py-4 border-b border-joule-border flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-joule-accent font-medium">Run Analysis</span>
          <span className="text-joule-muted">•</span>
          <span className="font-mono text-sm text-joule-ink">{run.run_id}</span>
        </div>
        <button 
          onClick={onClose}
          className="p-1 hover:bg-joule-chip rounded transition-colors"
        >
          <X className="w-4 h-4 text-joule-muted" />
        </button>
      </div>

      {/* Tabs */}
      <div className="px-6 border-b border-joule-border">
        <div className="flex space-x-6">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center py-3 px-1 border-b-2 transition-colors ${
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
        </div>
      </div>

      {/* Tab Content */}
      <div className="p-6">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {run.baseline && (
              <div>
                <h4 className="text-sm font-medium text-joule-ink mb-3">Baseline Metrics</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="bg-white p-3 rounded-lg">
                    <div className="text-xs text-joule-muted">Energy</div>
                    <div className="text-lg font-semibold">{run.baseline.energy_j.toFixed(1)} J</div>
                  </div>
                  <div className="bg-white p-3 rounded-lg">
                    <div className="text-xs text-joule-muted">Wall Time</div>
                    <div className="text-lg font-semibold">{run.baseline.wall_time_s.toFixed(2)} s</div>
                  </div>
                  <div className="bg-white p-3 rounded-lg">
                    <div className="text-xs text-joule-muted">CPU Time</div>
                    <div className="text-lg font-semibold">{run.baseline.cpu_time_s.toFixed(2)} s</div>
                  </div>
                  <div className="bg-white p-3 rounded-lg">
                    <div className="text-xs text-joule-muted">Peak Memory</div>
                    <div className="text-lg font-semibold">{formatBytes(run.baseline.peak_memory_bytes)}</div>
                  </div>
                </div>
              </div>
            )}

            {run.candidates && run.candidates.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-joule-ink mb-3">Optimization Summary</h4>
                <div className="bg-white p-4 rounded-lg space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-joule-muted">Total Candidates:</span>
                    <span>{run.candidates.length}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-joule-muted">Accepted:</span>
                    <span className="text-green-600">
                      {run.candidates.filter(c => c.status === 'accepted').length}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-joule-muted">Rejected:</span>
                    <span className="text-red-600">
                      {run.candidates.filter(c => c.status === 'rejected').length}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'candidates' && run.candidates && (
          <div className="space-y-3">
            {run.candidates.map((candidate) => (
              <div key={candidate.candidate_id} className="bg-white p-4 rounded-lg">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h4 className="font-medium text-joule-ink">{candidate.candidate_id}</h4>
                    <p className="text-sm text-joule-muted">{candidate.operator_name} • {candidate.operator_tier}</p>
                  </div>
                  <span className={`joule-status-badge joule-status-${candidate.status}`}>
                    {candidate.status}
                  </span>
                </div>
                
                {candidate.improvements && (
                  <div className="grid grid-cols-3 gap-2 text-sm mb-3">
                    <div className="bg-green-50 p-2 rounded text-center">
                      <div className="text-green-600 font-medium">
                        {formatImprovement(candidate.improvements.energy_ratio)}
                      </div>
                      <div className="text-xs text-joule-muted">Energy</div>
                    </div>
                    <div className="bg-green-50 p-2 rounded text-center">
                      <div className="text-green-600 font-medium">
                        {formatImprovement(candidate.improvements.time_ratio)}
                      </div>
                      <div className="text-xs text-joule-muted">Time</div>
                    </div>
                    <div className={`p-2 rounded text-center ${candidate.improvements.memory_ratio < 1 ? 'bg-green-50' : 'bg-red-50'}`}>
                      <div className={`font-medium ${candidate.improvements.memory_ratio < 1 ? 'text-green-600' : 'text-red-600'}`}>
                        {formatImprovement(candidate.improvements.memory_ratio)}
                      </div>
                      <div className="text-xs text-joule-muted">Memory</div>
                    </div>
                  </div>
                )}

                {candidate.explanation && (
                  <p className="text-sm text-joule-muted">{candidate.explanation}</p>
                )}
              </div>
            ))}
          </div>
        )}

        {activeTab === 'hotspots' && run.hotspots && (
          <div className="space-y-6">
            {run.hotspots.signal_quality && (
              <div>
                <h4 className="text-sm font-medium text-joule-ink mb-3">Signal Quality</h4>
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-white p-3 rounded-lg text-center">
                    <div className="text-lg font-semibold">
                      {(run.hotspots.signal_quality.project_share * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-joule-muted">Project Share</div>
                  </div>
                  <div className="bg-white p-3 rounded-lg text-center">
                    <div className="text-lg font-semibold">
                      {(run.hotspots.signal_quality.target_share * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-joule-muted">Target Share</div>
                  </div>
                  <div className="bg-white p-3 rounded-lg text-center">
                    <div className="text-lg font-semibold">
                      {run.hotspots.signal_quality.low_signal ? 'Yes' : 'No'}
                    </div>
                    <div className="text-xs text-joule-muted">Low Signal</div>
                  </div>
                </div>
              </div>
            )}

            {run.hotspots.overall_hotspots.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-joule-ink mb-3">Hotspot Functions</h4>
                <div className="space-y-2">
                  {run.hotspots.overall_hotspots.map((hotspot, idx) => (
                    <div key={idx} className="bg-white p-3 rounded-lg flex justify-between items-center">
                      <div>
                        <div className="font-medium text-joule-ink">{hotspot.function}</div>
                        <div className="text-xs text-joule-muted">{hotspot.file}</div>
                      </div>
                      <div className="text-sm font-medium">{(hotspot.share * 100).toFixed(1)}%</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {run.hotspots.recommendations.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-joule-ink mb-3">Recommendations</h4>
                <ul className="space-y-2">
                  {run.hotspots.recommendations.map((rec, idx) => (
                    <li key={idx} className="bg-white p-3 rounded-lg text-sm text-joule-muted flex items-start">
                      <CheckCircle className="w-4 h-4 text-joule-accent mr-2 flex-shrink-0 mt-0.5" />
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {activeTab === 'artifacts' && (
          <div className="text-center py-8 text-joule-muted">
            <Eye className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>Artifacts will be available here once the backend integration is complete.</p>
          </div>
        )}
      </div>
    </div>
  )
}
