import { TrendingUp } from 'lucide-react'

export function HotspotsView({ hotspots }: { hotspots: any }) {
  const profile = hotspots?.profile || hotspots

  const isV2 = !!profile?.top_functions
  const hasV1Stats = !!profile?.stats && profile.stats.length > 0

  if (!isV2 && !hasV1Stats) {
    return (
      <div className="text-center py-8">
        <TrendingUp className="w-12 h-12 text-joule-muted mx-auto mb-3" />
        <p className="text-joule-muted">Invalid hotspot format or no data available.</p>
      </div>
    )
  }

  const stats = profile.top_functions || profile.stats || []
  const ownership = profile.ownership || []

  const getOwnershipColor = (bucket: string) => {
    switch (bucket) {
      case 'project': return 'bg-blue-100 text-blue-800 border-blue-200'
      case 'external': return 'bg-purple-100 text-purple-800 border-purple-200'
      case 'builtin': return 'bg-gray-100 text-gray-800 border-gray-200'
      case 'stdlib-or-site': return 'bg-emerald-100 text-emerald-800 border-emerald-200'
      default: return 'bg-gray-100 text-gray-800 border-gray-200'
    }
  }

  return (
    <div className="space-y-6 text-left">
      {/* Ownership Summary */}
      {ownership.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {ownership.map((o: any) => (
            <div key={o.bucket} className={`p-4 rounded-lg border ${getOwnershipColor(o.bucket)} bg-opacity-50`}>
              <div className="text-sm font-medium opacity-80 uppercase tracking-wide">{o.bucket.replace(/-/g, ' ')}</div>
              <div className="text-xl font-bold mt-1">{o.cumulative_time_s.toFixed(3)}<span className="text-sm ml-1 opacity-70 font-normal">s</span></div>
            </div>
          ))}
        </div>
      )}

      {/* Top Functions Table */}
      <div className="joule-panel p-0 overflow-hidden border border-joule-border shadow-sm">
        <div className="p-4 border-b border-joule-border bg-joule-bg">
          <h3 className="font-semibold text-joule-ink">Top Functions by Time</h3>
        </div>
        <div className="overflow-x-auto max-h-[400px]">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="bg-joule-bg sticky top-0 border-b border-joule-border z-10">
              <tr>
                <th className="px-4 py-3 font-medium text-joule-muted">Function</th>
                <th className="px-4 py-3 font-medium text-joule-muted">File</th>
                <th className="px-4 py-3 font-medium text-joule-muted text-right">Cum. (s)</th>
                <th className="px-4 py-3 font-medium text-joule-muted text-right">Total (s)</th>
                <th className="px-4 py-3 font-medium text-joule-muted text-right">Calls</th>
                <th className="px-4 py-3 font-medium text-joule-muted">Type</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-joule-border">
              {stats.slice(0, 100).map((stat: any, i: number) => (
                <tr key={i} className="hover:bg-joule-chip transition-colors">
                  <td className="px-4 py-3 font-medium text-joule-ink break-all max-w-[200px] whitespace-normal" title={stat.function}>
                    {stat.function}
                  </td>
                  <td className="px-4 py-3 text-joule-muted font-mono text-xs max-w-[250px] whitespace-normal break-all">
                    {stat.file.length > 40 ? '...' + stat.file.slice(-37) : stat.file}:{stat.line}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-joule-ink font-semibold">
                    {stat.cumulative_time_s.toFixed(4)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-joule-muted">
                    {stat.total_time_s?.toFixed(4) || '—'}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-joule-muted">
                    {stat.total_calls}
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
      </div>
    </div>
  )
}
