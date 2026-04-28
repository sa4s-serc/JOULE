import { Activity, AlertTriangle, CheckCircle, Target, TrendingUp, XCircle } from 'lucide-react'
import type { SignalQuality, WorkloadSignal } from '../types'

interface SignalQualityPanelProps {
  signalQuality: SignalQuality
  workloadSignals?: WorkloadSignal[]
}

export function SignalQualityPanel({ signalQuality, workloadSignals }: SignalQualityPanelProps) {
  const {
    project_share,
    target_share,
    low_signal,
    low_signal_reasons,
    dominant_ownership_bucket,
    total_cumulative_time_s,
    project_cumulative_time_s,
    target_cumulative_time_s,
  } = signalQuality

  const projectPercent = (project_share * 100).toFixed(1)
  const targetPercent = (target_share * 100).toFixed(1)

  return (
    <div className="space-y-6">
      {/* Signal Status Header */}
      <div className={`p-4 rounded-lg border ${low_signal ? 'bg-amber-50 border-amber-200' : 'bg-green-50 border-green-200'}`}>
        <div className="flex items-center gap-3">
          {low_signal ? (
            <AlertTriangle className="w-6 h-6 text-amber-600" />
          ) : (
            <CheckCircle className="w-6 h-6 text-green-600" />
          )}
          <div>
            <h4 className={`font-semibold ${low_signal ? 'text-amber-800' : 'text-green-800'}`}>
              {low_signal ? 'Low Signal Quality' : 'Good Signal Quality'}
            </h4>
            <p className={`text-sm ${low_signal ? 'text-amber-700' : 'text-green-700'}`}>
              {low_signal
                ? 'Target code represents less than 20% of total execution time'
                : 'Target code is well-represented in profiling samples'}
            </p>
          </div>
        </div>

        {low_signal && low_signal_reasons && low_signal_reasons.length > 0 && (
          <div className="mt-3 pt-3 border-t border-amber-200">
            <p className="text-xs font-medium text-amber-800 uppercase tracking-wide mb-2">Detected Issues</p>
            <ul className="space-y-1">
              {low_signal_reasons.map((reason, idx) => (
                <li key={idx} className="text-sm text-amber-700 flex items-center gap-2">
                  <XCircle className="w-3.5 h-3.5" />
                  {formatReason(reason)}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Share Metrics */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-joule-bg p-4 rounded-lg border border-joule-border">
          <div className="flex items-center gap-2 text-joule-muted mb-2">
            <Activity className="w-4 h-4" />
            <span className="text-xs font-medium uppercase tracking-wide">Total Time</span>
          </div>
          <div className="text-xl font-bold text-joule-ink">
            {total_cumulative_time_s.toFixed(3)}s
          </div>
        </div>

        <div className="bg-blue-50 p-4 rounded-lg border border-blue-200">
          <div className="flex items-center gap-2 text-blue-600 mb-2">
            <TrendingUp className="w-4 h-4" />
            <span className="text-xs font-medium uppercase tracking-wide">Project Share</span>
          </div>
          <div className="text-xl font-bold text-blue-700">
            {projectPercent}%
          </div>
          <div className="text-xs text-blue-600 mt-1">
            {project_cumulative_time_s.toFixed(3)}s
          </div>
        </div>

        <div className="bg-green-50 p-4 rounded-lg border border-green-200">
          <div className="flex items-center gap-2 text-green-600 mb-2">
            <Target className="w-4 h-4" />
            <span className="text-xs font-medium uppercase tracking-wide">Target Share</span>
          </div>
          <div className="text-xl font-bold text-green-700">
            {targetPercent}%
          </div>
          <div className="text-xs text-green-600 mt-1">
            {target_cumulative_time_s.toFixed(3)}s
          </div>
        </div>
      </div>

      {/* Dominant Bucket */}
      {dominant_ownership_bucket && (
        <div className="flex items-center gap-3 text-sm">
          <span className="text-joule-muted">Dominant ownership:</span>
          <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${getOwnershipColor(dominant_ownership_bucket)}`}>
            {dominant_ownership_bucket.replace(/-/g, ' ')}
          </span>
        </div>
      )}

      {/* Workload Breakdown */}
      {workloadSignals && workloadSignals.length > 0 && (
        <div className="border border-joule-border rounded-lg overflow-hidden">
          <div className="bg-joule-bg px-4 py-3 border-b border-joule-border">
            <h4 className="font-medium text-joule-ink">Workload Signal Breakdown</h4>
          </div>
          <div className="divide-y divide-joule-border">
            {workloadSignals.map((workload) => (
              <div key={workload.workload_id} className="px-4 py-3 hover:bg-joule-bg/50 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full ${workload.low_signal ? 'bg-amber-500' : 'bg-green-500'}`} />
                    <div>
                      <div className="font-medium text-sm text-joule-ink">
                        {workload.workload_label || workload.workload_id}
                      </div>
                      <div className="text-xs text-joule-muted">
                        {workload.workload_kind} • {workload.workload_selector}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium text-joule-ink">
                      {(workload.project_share * 100).toFixed(1)}% project
                    </div>
                    <div className="text-xs text-joule-muted">
                      {(workload.target_share * 100).toFixed(1)}% target
                    </div>
                  </div>
                </div>
                {!workload.success && workload.stderr && (
                  <div className="mt-2 text-xs text-red-600 bg-red-50 p-2 rounded">
                    {workload.stderr.substring(0, 100)}
                    {workload.stderr.length > 100 && '...'}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function formatReason(reason: string): string {
  const reasonMap: Record<string, string> = {
    'target_file_under_20pct': 'Target file contributes less than 20% of execution time',
    'non_project_dominant': 'Non-project code dominates execution time',
    'no_profile_samples': 'No profile samples collected',
    'low_target_coverage': 'Low target code coverage in samples',
  }
  return reasonMap[reason] || reason.replace(/_/g, ' ')
}

function getOwnershipColor(bucket: string): string {
  switch (bucket) {
    case 'project':
      return 'bg-blue-100 text-blue-700 border-blue-200'
    case 'candidate-overlay':
      return 'bg-purple-100 text-purple-700 border-purple-200'
    case 'external':
      return 'bg-amber-100 text-amber-700 border-amber-200'
    case 'builtin':
      return 'bg-gray-100 text-gray-700 border-gray-200'
    case 'stdlib-or-site':
      return 'bg-emerald-100 text-emerald-700 border-emerald-200'
    default:
      return 'bg-gray-100 text-gray-700 border-gray-200'
  }
}
