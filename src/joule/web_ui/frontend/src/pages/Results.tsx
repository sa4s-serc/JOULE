import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search,
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
  RefreshCw,
} from 'lucide-react'
import { apiClient, formatBytes, formatImprovement } from '../utils/api'
import { HotspotsView } from '../components/HotspotsView'

interface Run {
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

export default function Results() {
  const navigate = useNavigate()
  const [runs, setRuns] = useState<Run[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [expandedRun, setExpandedRun] = useState<string | null>(null)
  const [expandedRunData, setExpandedRunData] = useState<Run | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'candidates' | 'hotspots' | 'artifacts'>('overview')

  const fetchRuns = async () => {
    setLoading(true)
    try {
      const data = await apiClient.getRuns()
      setRuns(data)
    } catch (err) {
      console.warn('Failed to fetch runs:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchRuns()
    const interval = setInterval(fetchRuns, 15000) // Poll
    return () => clearInterval(interval)
  }, [])

  const filteredRuns = runs.filter((run) => {
    const matchesSearch = run.run_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         (run.target_qualname || '').toLowerCase().includes(searchTerm.toLowerCase())
    const matchesStatus = statusFilter === 'all' || run.status === statusFilter
    const matchesType = typeFilter === 'all' || run.run_type === typeFilter
    return matchesSearch && matchesStatus && matchesType
  })

  const getStatusIcon = (status: Run['status']) => {
    switch (status) {
      case 'completed': return <TrendingUp className="w-4 h-4 text-green-600" />
      case 'running': return <BarChart3 className="w-4 h-4 text-yellow-600 animate-pulse" />
      case 'failed': return <TrendingDown className="w-4 h-4 text-red-600" />
      case 'cancelled': return <Minus className="w-4 h-4 text-gray-600" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'joule-status-completed'
      case 'running': return 'joule-status-running'
      case 'failed': return 'joule-status-failed'
      default: return 'joule-status-failed'
    }
  }

  const toggleExpand = async (runId: string) => {
    if (expandedRun === runId) {
      setExpandedRun(null)
      setExpandedRunData(null)
    } else {
      setExpandedRun(runId)
      setActiveTab('overview')
      try {
        const detail = await apiClient.getRun(runId)
        setExpandedRunData(detail)
      } catch {
        setExpandedRunData(null)
      }
    }
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-joule-ink">Results</h1>
          <p className="text-joule-muted mt-2">Browse and analyze your optimization runs</p>
        </div>
        <button className="joule-button joule-button-secondary flex items-center" onClick={fetchRuns}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="joule-panel">
        <div className="flex flex-col lg:flex-row gap-4">
          <div className="flex-1">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 transform -translate-y-1/2 text-joule-muted" />
              <input type="text" placeholder="Search runs…" value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-joule-border rounded-lg focus:outline-none focus:ring-2 focus:ring-joule-accent"
              />
            </div>
          </div>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 border border-joule-border rounded-lg focus:outline-none focus:ring-2 focus:ring-joule-accent">
            <option value="all">All Status</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-2 border border-joule-border rounded-lg focus:outline-none focus:ring-2 focus:ring-joule-accent">
            <option value="all">All Types</option>
            <option value="baseline">Baseline</option>
            <option value="optimize">Optimize</option>
          </select>
        </div>
      </div>

      {/* Runs Table */}
      <div className="joule-panel">
        {loading && runs.length === 0 ? (
          <div className="animate-pulse space-y-3">
            {[1,2,3].map(i => <div key={i} className="h-14 bg-joule-chip rounded-lg" />)}
          </div>
        ) : filteredRuns.length === 0 ? (
          <div className="text-center py-12 text-joule-muted">
            {runs.length === 0
              ? 'No runs yet. Start a baseline or optimization from the sidebar.'
              : 'No runs match your filters.'}
          </div>
        ) : (
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
                  <th className="text-left py-3 px-4 text-sm font-medium text-joule-ink">Created</th>
                </tr>
              </thead>
              <tbody>
                {filteredRuns.map((run) => (
                  <>
                    <tr key={run.run_id}
                      className={`border-b border-joule-border cursor-pointer transition-colors ${
                        expandedRun === run.run_id ? 'bg-joule-chip' : 'hover:bg-joule-bg'
                      }`}
                      onClick={() => toggleExpand(run.run_id)}
                    >
                      <td className="py-3 px-4">
                        <div className="text-joule-accent">
                          {expandedRun === run.run_id
                            ? <ChevronDown className="w-5 h-5" />
                            : <ChevronRight className="w-5 h-5" />}
                        </div>
                      </td>
                      <td className="py-3 px-4 max-w-[150px]">
                        <div className="font-mono text-sm truncate" title={run.run_id}>{run.run_id}</div>
                      </td>
                      <td className="py-3 px-4"><span className="joule-chip">{run.run_type}</span></td>
                      <td className="py-3 px-4">
                        <div className="flex items-center">
                          {getStatusIcon(run.status)}
                          <span className={`ml-2 joule-status-badge ${getStatusColor(run.status)}`}>{run.status}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 max-w-[200px]">
                        <div className="font-mono text-sm truncate" title={run.target_qualname || ''}>{run.target_qualname || '—'}</div>
                      </td>
                      <td className="py-3 px-4"><span className="joule-chip">{run.backend || '—'}</span></td>
                      <td className="py-3 px-4 text-sm">{new Date(run.created_at).toLocaleString()}</td>
                    </tr>

                    {expandedRun === run.run_id && expandedRunData && (
                      <tr key={`${run.run_id}-detail`}>
                        <td colSpan={7} className="p-0">
                          <RunDetailView
                            run={expandedRunData}
                            activeTab={activeTab}
                            setActiveTab={setActiveTab}
                            onClose={() => { setExpandedRun(null); setExpandedRunData(null) }}
                            onNavigateInspect={() => navigate(`/inspect/${run.run_id}`)}
                          />
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {[
          { label: 'Completed', value: runs.filter(r => r.status === 'completed').length },
          { label: 'Running', value: runs.filter(r => r.status === 'running').length },
          { label: 'Optimizations', value: runs.filter(r => r.run_type === 'optimize').length },
          { label: 'Baselines', value: runs.filter(r => r.run_type === 'baseline').length },
        ].map(({ label, value }) => (
          <div key={label} className="joule-panel">
            <div className="text-center">
              <div className="text-2xl font-bold text-joule-ink">{loading ? '—' : value}</div>
              <div className="text-sm text-joule-muted">{label}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}


// Sub-component
interface RunDetailViewProps {
  run: Run
  activeTab: 'overview' | 'candidates' | 'hotspots' | 'artifacts'
  setActiveTab: (tab: any) => void
  onClose: () => void
  onNavigateInspect: () => void
}

function RunDetailView({ run, activeTab, setActiveTab, onClose, onNavigateInspect }: RunDetailViewProps) {
  const tabs = [
    { id: 'overview', label: 'Overview', icon: Activity },
    { id: 'candidates', label: 'Candidates', icon: Code },
    { id: 'hotspots', label: 'Hotspots', icon: Zap },
    { id: 'artifacts', label: 'Artifacts', icon: Eye },
  ] as const

  return (
    <div className="bg-joule-bg border-t border-joule-border">
      <div className="px-6 py-4 border-b border-joule-border flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-joule-accent font-medium">Run Analysis</span>
          <span className="text-joule-muted">•</span>
          <span className="font-mono text-sm text-joule-ink truncate max-w-[200px]" title={run.run_id}>{run.run_id}</span>
        </div>
        <div className="flex items-center space-x-2">
          <button onClick={onNavigateInspect} className="joule-button joule-button-secondary text-sm">
            Full Inspect →
          </button>
          <button onClick={onClose} className="p-1 hover:bg-joule-chip rounded transition-colors">
            <X className="w-4 h-4 text-joule-muted" />
          </button>
        </div>
      </div>

      <div className="px-6 border-b border-joule-border">
        <div className="flex space-x-6">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button key={tab.id} onClick={() => setActiveTab(tab.id)}
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

      <div className="p-6">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {run.baseline && (
              <div>
                <h4 className="text-sm font-medium text-joule-ink mb-3">Baseline Metrics</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {[
                    { label: 'Energy', value: `${run.baseline.energy_j.toFixed(1)} J` },
                    { label: 'Wall Time', value: `${run.baseline.wall_time_s.toFixed(2)} s` },
                    { label: 'CPU Time', value: `${run.baseline.cpu_time_s.toFixed(2)} s` },
                    { label: 'Peak Memory', value: formatBytes(run.baseline.peak_memory_bytes) },
                  ].map(({ label, value }) => (
                    <div key={label} className="bg-white p-3 rounded-lg">
                      <div className="text-xs text-joule-muted">{label}</div>
                      <div className="text-lg font-semibold">{value}</div>
                    </div>
                  ))}
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
                    <span className="text-green-600">{run.candidates.filter(c => c.status === 'accepted').length}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-joule-muted">Rejected:</span>
                    <span className="text-red-600">{run.candidates.filter(c => c.status !== 'accepted').length}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'candidates' && (
          <div className="space-y-3">
            {(!run.candidates || run.candidates.length === 0) ? (
              <p className="text-joule-muted text-center py-6">No candidates generated for this run.</p>
            ) : (
              run.candidates.map((candidate) => (
                <div key={candidate.candidate_id} className="bg-white p-4 rounded-lg">
                  <div className="flex items-start justify-between mb-3">
                    <div className="min-w-0 flex-1 mr-4">
                      <h4 className="font-medium text-joule-ink truncate" title={candidate.candidate_id}>{candidate.candidate_id}</h4>
                      <p className="text-sm text-joule-muted truncate" title={`${candidate.operator_name} • ${candidate.operator_tier}`}>{candidate.operator_name} • {candidate.operator_tier}</p>
                    </div>
                    <span className={`joule-status-badge joule-status-${candidate.status === 'accepted' ? 'completed' : 'failed'}`}>
                      {candidate.status}
                    </span>
                  </div>
                  {candidate.improvements && (
                    <div className="grid grid-cols-3 gap-2 text-sm mb-3">
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
                  {candidate.explanation && <p className="text-sm text-joule-muted">{candidate.explanation}</p>}
                  {candidate.rejection_reason && (
                    <p className="text-sm text-red-600 mt-1">{candidate.rejection_reason}</p>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'hotspots' && (
          <div className="text-center py-8 text-joule-muted">
            {run.hotspots && Object.keys(run.hotspots).length > 0 ? (
              <HotspotsView hotspots={run.hotspots} />
            ) : (
              <p>No hotspot data available for this run.</p>
            )}
          </div>
        )}

        {activeTab === 'artifacts' && (
          <div className="text-center py-8 text-joule-muted">
            <Eye className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>Use the Full Inspect view for artifact downloads.</p>
          </div>
        )}
      </div>
    </div>
  )
}
