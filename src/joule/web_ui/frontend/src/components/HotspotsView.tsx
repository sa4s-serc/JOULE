import { useState } from 'react'
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  ChevronRight,
  FileCode,
  Flame,
  Layers,
  Lightbulb,
  Signal,
  Target,
  TrendingUp,
  Zap,
} from 'lucide-react'
import type { HotspotAnalysis } from '../types'
import { InsightsPanel } from './InsightsPanel'
import { SignalQualityPanel } from './SignalQualityPanel'
import { GranularAnalysisView } from './GranularAnalysisView'

interface HotspotsViewProps {
  hotspots: HotspotAnalysis | any
}

type TabId = 'overview' | 'functions' | 'insights' | 'granular' | 'workloads'

export function HotspotsView({ hotspots }: HotspotsViewProps) {
  const [activeTab, setActiveTab] = useState<TabId>('overview')

  // Normalize the hotspot data (handle both v2 schema and legacy formats)
  const profile = hotspots?.profile || hotspots

  // Check if we have the enhanced schema v2 data
  const hasSignalQuality = !!profile?.signal_quality
  const hasGranularAnalysis = !!profile?.granular_analysis
  const hasWorkloadSignals = !!profile?.by_workload && profile.by_workload.length > 0
  const hasInsights = (profile?.granular_analysis?.insights?.length || 0) > 0

  // Legacy/basic data
  const topFunctions = profile?.top_functions || profile?.stats || []
  const ownership = profile?.ownership || []
  const recommendations = profile?.recommendations || []

  // Check if we have any valid data
  if (!hasSignalQuality && topFunctions.length === 0) {
    return (
      <div className="text-center py-8">
        <TrendingUp className="w-12 h-12 text-joule-muted mx-auto mb-3" />
        <p className="text-joule-muted">Invalid hotspot format or no data available.</p>
      </div>
    )
  }

  const tabs: { id: TabId; label: string; icon: typeof Activity; badge?: number; show: boolean }[] = [
    { id: 'overview', label: 'Overview', icon: Activity, show: true },
    { id: 'functions', label: 'Functions', icon: FileCode, badge: topFunctions.length, show: topFunctions.length > 0 },
    { id: 'insights', label: 'Insights', icon: Lightbulb, badge: profile?.granular_analysis?.insights?.length, show: hasInsights },
    { id: 'granular', label: 'Granular', icon: Target, show: hasGranularAnalysis },
    { id: 'workloads', label: 'Workloads', icon: Layers, badge: profile?.by_workload?.length, show: hasWorkloadSignals },
  ]

  const visibleTabs = tabs.filter(t => t.show)

  return (
    <div className="space-y-4 text-left">
      {/* Tabs Navigation */}
      {visibleTabs.length > 1 && (
        <div className="border-b border-joule-border">
          <div className="flex flex-wrap gap-1">
            {visibleTabs.map((tab) => {
              const Icon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                    isActive
                      ? 'border-joule-accent text-joule-accent'
                      : 'border-transparent text-joule-muted hover:text-joule-ink'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                  {tab.badge !== undefined && tab.badge > 0 && (
                    <span className={`ml-1 px-1.5 py-0.5 text-xs rounded-full ${
                      isActive ? 'bg-joule-accent text-white' : 'bg-joule-chip text-joule-muted'
                    }`}>
                      {tab.badge}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Tab Content */}
      <div className="min-h-[300px]">
        {activeTab === 'overview' && (
          <OverviewTab
            profile={profile}
            topFunctions={topFunctions}
            ownership={ownership}
            recommendations={recommendations}
            hasGranularAnalysis={hasGranularAnalysis}
          />
        )}

        {activeTab === 'functions' && (
          <FunctionsTab topFunctions={topFunctions} />
        )}

        {activeTab === 'insights' && hasInsights && (
          <div className="py-2">
            <InsightsPanel insights={profile.granular_analysis.insights} />
          </div>
        )}

        {activeTab === 'granular' && hasGranularAnalysis && (
          <div className="py-2">
            <GranularAnalysisView analysis={profile.granular_analysis} />
          </div>
        )}

        {activeTab === 'workloads' && hasWorkloadSignals && (
          <div className="py-2">
            <SignalQualityPanel
              signalQuality={profile.signal_quality}
              workloadSignals={profile.by_workload}
            />
          </div>
        )}
      </div>
    </div>
  )
}

// Sub-components

function OverviewTab({
  profile,
  topFunctions,
  ownership,
  recommendations,
  hasGranularAnalysis,
}: {
  profile: any
  topFunctions: any[]
  ownership: any[]
  recommendations: string[]
  hasGranularAnalysis: boolean
}) {
  const signalQuality = profile?.signal_quality
  const hasSignalQuality = !!signalQuality

  return (
    <div className="space-y-6">
      {/* Signal Quality Summary */}
      {hasSignalQuality && (
        <div className={`p-4 rounded-lg border ${signalQuality.low_signal ? 'bg-amber-50 border-amber-200' : 'bg-green-50 border-green-200'}`}>
          <div className="flex items-center gap-3">
            {signalQuality.low_signal ? (
              <AlertTriangle className="w-5 h-5 text-amber-600" />
            ) : (
              <CheckCircle className="w-5 h-5 text-green-600" />
            )}
            <div className="flex-1">
              <h4 className={`font-medium ${signalQuality.low_signal ? 'text-amber-800' : 'text-green-800'}`}>
                Signal Quality: {signalQuality.low_signal ? 'Low' : 'Good'}
              </h4>
              <p className={`text-sm ${signalQuality.low_signal ? 'text-amber-700' : 'text-green-700'}`}>
                Project: {(signalQuality.project_share * 100).toFixed(1)}% •
                Target: {(signalQuality.target_share * 100).toFixed(1)}%
              </p>
            </div>
            {signalQuality.total_cumulative_time_s > 0 && (
              <div className="text-right">
                <div className="text-sm font-medium text-joule-ink">
                  {signalQuality.total_cumulative_time_s.toFixed(3)}s
                </div>
                <div className="text-xs text-joule-muted">Total time</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Ownership Summary */}
      {ownership.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-joule-muted uppercase tracking-wide mb-3">Time by Ownership</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {ownership.map((o: any) => (
              <div
                key={o.bucket}
                className={`p-3 rounded-lg border ${getOwnershipColor(o.bucket)} bg-opacity-30`}
              >
                <div className="text-xs font-medium opacity-80 uppercase tracking-wide">{o.bucket.replace(/-/g, ' ')}</div>
                <div className="text-lg font-bold mt-1">{o.cumulative_time_s.toFixed(3)}<span className="text-xs ml-1 opacity-70 font-normal">s</span></div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard
          icon={FileCode}
          label="Functions Profiled"
          value={topFunctions.length.toString()}
          color="text-blue-600"
        />
        {profile?.workload_kind_counts && (
          <StatCard
            icon={Layers}
            label="Workload Types"
            value={Object.keys(profile.workload_kind_counts).length.toString()}
            color="text-purple-600"
          />
        )}
        {hasGranularAnalysis && (
          <StatCard
            icon={Target}
            label="Code Blocks"
            value={profile.granular_analysis.code_blocks?.length?.toString() || '0'}
            color="text-green-600"
          />
        )}
        {profile?.insights?.profiled_workload_count !== undefined && (
          <StatCard
            icon={Signal}
            label="Workloads"
            value={profile.insights.profiled_workload_count.toString()}
            color="text-amber-600"
          />
        )}
      </div>

      {/* Recommendations */}
      {recommendations.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-joule-muted uppercase tracking-wide mb-3">Recommendations</h4>
          <div className="space-y-2">
            {recommendations.slice(0, 5).map((rec, idx) => (
              <div key={idx} className="flex items-start gap-2 text-sm">
                <ChevronRight className="w-4 h-4 text-joule-accent mt-0.5 flex-shrink-0" />
                <span className="text-joule-ink">{rec}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Granular Preview */}
      {hasGranularAnalysis && profile.granular_analysis.insights && profile.granular_analysis.insights.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-joule-muted uppercase tracking-wide mb-3">Top Insights</h4>
          <div className="space-y-2">
            {profile.granular_analysis.insights.slice(0, 3).map((insight: any, idx: number) => (
              <div
                key={idx}
                className={`p-3 rounded-lg border ${getInsightColor(insight.severity)}`}
              >
                <div className="flex items-center gap-2">
                  {getInsightIcon(insight.kind, insight.severity)}
                  <span className="text-sm font-medium">{insight.message}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function FunctionsTab({ topFunctions }: { topFunctions: any[] }) {
  const [filter, setFilter] = useState<'all' | 'project' | 'external'>('all')

  const filteredFunctions = topFunctions.filter((fn: any) => {
    if (filter === 'all') return true
    if (filter === 'project') return fn.ownership === 'project' || fn.ownership === 'candidate-overlay'
    if (filter === 'external') return fn.ownership !== 'project' && fn.ownership !== 'candidate-overlay'
    return true
  })

  return (
    <div className="space-y-4">
      {/* Filter */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-joule-muted">Filter:</span>
        {(['all', 'project', 'external'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 text-sm rounded-full transition-colors ${
              filter === f
                ? 'bg-joule-accent text-white'
                : 'bg-joule-chip text-joule-muted hover:text-joule-ink'
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Functions Table */}
      <div className="joule-panel p-0 overflow-hidden border border-joule-border shadow-sm">
        <div className="overflow-x-auto max-h-[500px]">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="bg-joule-bg sticky top-0 border-b border-joule-border z-10">
              <tr>
                <th className="px-4 py-3 font-medium text-joule-muted">Function</th>
                <th className="px-4 py-3 font-medium text-joule-muted">File</th>
                <th className="px-4 py-3 font-medium text-joule-muted text-right">Cum. (s)</th>
                <th className="px-4 py-3 font-medium text-joule-muted text-right">Self (s)</th>
                <th className="px-4 py-3 font-medium text-joule-muted text-right">Calls</th>
                <th className="px-4 py-3 font-medium text-joule-muted text-right">Share</th>
                <th className="px-4 py-3 font-medium text-joule-muted">Type</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-joule-border">
              {filteredFunctions.map((stat: any, i: number) => (
                <tr key={i} className="hover:bg-joule-chip transition-colors">
                  <td className="px-4 py-3 font-medium text-joule-ink break-all max-w-[200px] whitespace-normal" title={stat.function}>
                    {stat.function}
                  </td>
                  <td className="px-4 py-3 text-joule-muted font-mono text-xs max-w-[250px] whitespace-normal break-all">
                    {stat.file?.length > 40 ? '...' + stat.file.slice(-37) : stat.file}:{stat.line}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-joule-ink font-semibold">
                    {stat.cumulative_time_s?.toFixed(4)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-joule-muted">
                    {stat.total_time_s?.toFixed(4) || '—'}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-joule-muted">
                    {stat.total_calls?.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className={`font-mono font-medium ${
                      (stat.share || 0) > 0.3 ? 'text-red-600' : (stat.share || 0) > 0.1 ? 'text-amber-600' : 'text-joule-ink'
                    }`}>
                      {((stat.share || 0) * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded text-xs border bg-opacity-20 ${getOwnershipColor(stat.ownership)}`}>
                      {stat.ownership}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filteredFunctions.length === 0 && (
          <div className="p-8 text-center text-joule-muted">
            No functions match the selected filter.
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ icon: Icon, label, value, color }: { icon: typeof Activity; label: string; value: string; color: string }) {
  return (
    <div className="bg-joule-bg p-4 rounded-lg border border-joule-border">
      <div className={`flex items-center gap-2 ${color} mb-1`}>
        <Icon className="w-4 h-4" />
        <span className="text-2xl font-bold">{value}</span>
      </div>
      <div className="text-xs text-joule-muted">{label}</div>
    </div>
  )
}

function getOwnershipColor(bucket: string): string {
  switch (bucket) {
    case 'project': return 'bg-blue-100 text-blue-800 border-blue-200'
    case 'candidate-overlay': return 'bg-purple-100 text-purple-800 border-purple-200'
    case 'external': return 'bg-amber-100 text-amber-800 border-amber-200'
    case 'builtin': return 'bg-gray-100 text-gray-800 border-gray-200'
    case 'stdlib-or-site': return 'bg-emerald-100 text-emerald-800 border-emerald-200'
    default: return 'bg-gray-100 text-gray-800 border-gray-200'
  }
}

function getInsightColor(severity: string): string {
  switch (severity) {
    case 'critical': return 'bg-red-50 border-red-200 text-red-800'
    case 'warning': return 'bg-amber-50 border-amber-200 text-amber-800'
    case 'info': return 'bg-blue-50 border-blue-200 text-blue-800'
    default: return 'bg-gray-50 border-gray-200 text-gray-800'
  }
}

function getInsightIcon(kind: string, severity: string) {
  const className = `w-4 h-4 ${
    severity === 'critical' ? 'text-red-600' :
    severity === 'warning' ? 'text-amber-600' :
    'text-blue-600'
  }`

  switch (kind) {
    case 'critical_hotspot':
    case 'memory_hotspot':
      return <Flame className={className} />
    case 'hotspot':
    case 'loop_dominant':
      return <Zap className={className} />
    case 'high_complexity':
    case 'high_allocation_rate':
      return <AlertTriangle className={className} />
    case 'deep_nesting':
    case 'comprehension_usage':
    case 'memory_intensive':
    default:
      return <Lightbulb className={className} />
  }
}
