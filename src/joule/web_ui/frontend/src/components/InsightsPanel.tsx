import { AlertTriangle, Flame, Info, Lightbulb, Zap } from 'lucide-react'
import type { InsightRecord } from '../types'

interface InsightsPanelProps {
  insights: InsightRecord[]
}

const severityConfig = {
  critical: {
    icon: Flame,
    className: 'bg-red-50 border-red-200 text-red-800',
    badgeClass: 'bg-red-100 text-red-700',
    label: 'Critical',
  },
  warning: {
    icon: AlertTriangle,
    className: 'bg-amber-50 border-amber-200 text-amber-800',
    badgeClass: 'bg-amber-100 text-amber-700',
    label: 'Warning',
  },
  info: {
    icon: Info,
    className: 'bg-blue-50 border-blue-200 text-blue-800',
    badgeClass: 'bg-blue-100 text-blue-700',
    label: 'Info',
  },
}

const kindConfig: Record<string, { icon: typeof Lightbulb; label: string; color: string }> = {
  critical_hotspot: { icon: Flame, label: 'Critical Hotspot', color: 'text-red-600' },
  hotspot: { icon: Zap, label: 'Hotspot', color: 'text-amber-600' },
  loop_dominant: { icon: Zap, label: 'Loop Dominant', color: 'text-blue-600' },
  high_complexity: { icon: AlertTriangle, label: 'High Complexity', color: 'text-orange-600' },
  deep_nesting: { icon: Info, label: 'Deep Nesting', color: 'text-purple-600' },
  comprehension_usage: { icon: Lightbulb, label: 'Comprehension', color: 'text-green-600' },
  memory_hotspot: { icon: Flame, label: 'Memory Hotspot', color: 'text-red-600' },
  high_allocation_rate: { icon: AlertTriangle, label: 'High Allocation', color: 'text-orange-600' },
  memory_intensive: { icon: Info, label: 'Memory Intensive', color: 'text-blue-600' },
}

function formatEvidence(evidence: Record<string, any> | undefined): string | null {
  if (!evidence) return null

  const parts: string[] = []

  if (evidence.share_of_function !== undefined) {
    parts.push(`Share: ${(evidence.share_of_function * 100).toFixed(1)}%`)
  }
  if (evidence.time_s !== undefined) {
    parts.push(`Time: ${evidence.time_s.toFixed(3)}s`)
  }
  if (evidence.hits !== undefined) {
    parts.push(`Hits: ${evidence.hits.toLocaleString()}`)
  }
  if (evidence.peak_memory_bytes !== undefined) {
    const mib = evidence.peak_memory_bytes / (1024 * 1024)
    parts.push(`Memory: ${mib.toFixed(2)} MiB`)
  }
  if (evidence.allocation_count !== undefined) {
    parts.push(`Allocations: ${evidence.allocation_count.toLocaleString()}`)
  }
  if (evidence.loop_share !== undefined) {
    parts.push(`Loop Share: ${(evidence.loop_share * 100).toFixed(1)}%`)
  }
  if (evidence.count !== undefined) {
    parts.push(`Count: ${evidence.count}`)
  }

  return parts.join(' • ') || null
}

export function InsightsPanel({ insights }: InsightsPanelProps) {
  if (!insights || insights.length === 0) {
    return (
      <div className="text-center py-8 text-joule-muted">
        <Lightbulb className="w-10 h-10 mx-auto mb-3 opacity-50" />
        <p>No insights available for this analysis.</p>
      </div>
    )
  }

  // Sort by severity: critical first, then warning, then info
  const sortedInsights = [...insights].sort((a, b) => {
    const severityOrder = { critical: 0, warning: 1, info: 2 }
    return severityOrder[a.severity] - severityOrder[b.severity]
  })

  const criticalCount = insights.filter(i => i.severity === 'critical').length
  const warningCount = insights.filter(i => i.severity === 'warning').length

  return (
    <div className="space-y-4">
      {/* Summary Header */}
      <div className="flex items-center gap-4">
        {criticalCount > 0 && (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-red-100 text-red-700 rounded-full text-sm font-medium">
            <Flame className="w-4 h-4" />
            {criticalCount} Critical
          </div>
        )}
        {warningCount > 0 && (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-amber-100 text-amber-700 rounded-full text-sm font-medium">
            <AlertTriangle className="w-4 h-4" />
            {warningCount} Warning
          </div>
        )}
        <div className="text-sm text-joule-muted">
          {insights.length} total insight{insights.length !== 1 ? 's' : ''}
        </div>
      </div>

      {/* Insights List */}
      <div className="space-y-3">
        {sortedInsights.map((insight, index) => {
          const config = severityConfig[insight.severity]
          const Icon = config.icon
          const kindInfo = kindConfig[insight.kind] || { icon: Lightbulb, label: insight.kind, color: 'text-gray-600' }
          const KindIcon = kindInfo.icon
          const evidence = formatEvidence(insight.evidence)

          return (
            <div
              key={index}
              className={`p-4 rounded-lg border ${config.className} transition-all hover:shadow-sm`}
            >
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 mt-0.5">
                  <Icon className="w-5 h-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded ${config.badgeClass}`}>
                      {config.label}
                    </span>
                    <span className={`text-xs flex items-center gap-1 ${kindInfo.color}`}>
                      <KindIcon className="w-3 h-3" />
                      {kindInfo.label}
                    </span>
                    {insight.line_range && (
                      <span className="text-xs text-joule-muted font-mono">
                        Lines {insight.line_range[0]}:{insight.line_range[1]}
                      </span>
                    )}
                  </div>
                  <p className="mt-2 text-sm font-medium">{insight.message}</p>
                  {evidence && (
                    <p className="mt-1.5 text-xs opacity-80 font-mono">{evidence}</p>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
