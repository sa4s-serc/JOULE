import { useState, useEffect } from 'react'
import { Activity, Zap, TrendingUp, AlertCircle } from 'lucide-react'

interface DashboardStats {
  totalRuns: number
  runningRuns: number
  completedRuns: number
  failedRuns: number
  recentRuns: Array<{
    run_id: string
    run_type: string
    status: string
    target_qualname: string
    created_at: string
  }>
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats>({
    totalRuns: 0,
    runningRuns: 0,
    completedRuns: 0,
    failedRuns: 0,
    recentRuns: [],
  })

  useEffect(() => {
    // TODO: Fetch dashboard stats from API
    const mockStats: DashboardStats = {
      totalRuns: 12,
      runningRuns: 1,
      completedRuns: 10,
      failedRuns: 1,
      recentRuns: [
        {
          run_id: 'run_20240423_001',
          run_type: 'optimize',
          status: 'running',
          target_qualname: 'example.process_data',
          created_at: '2024-04-23T10:30:00Z',
        },
        {
          run_id: 'run_20240423_000',
          run_type: 'baseline',
          status: 'completed',
          target_qualname: 'example.process_data',
          created_at: '2024-04-23T09:15:00Z',
        },
      ],
    }
    setStats(mockStats)
  }, [])

  const statCards = [
    {
      title: 'Total Runs',
      value: stats.totalRuns,
      icon: Activity,
      color: 'text-blue-600',
    },
    {
      title: 'Running',
      value: stats.runningRuns,
      icon: Zap,
      color: 'text-yellow-600',
    },
    {
      title: 'Completed',
      value: stats.completedRuns,
      icon: TrendingUp,
      color: 'text-green-600',
    },
    {
      title: 'Failed',
      value: stats.failedRuns,
      icon: AlertCircle,
      color: 'text-red-600',
    },
  ]

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-joule-ink">Dashboard</h1>
        <p className="text-joule-muted mt-2">
          Overview of your JOULE optimization activities
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((stat) => {
          const Icon = stat.icon
          return (
            <div key={stat.title} className="joule-panel">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-joule-muted">
                    {stat.title}
                  </p>
                  <p className="text-2xl font-bold text-joule-ink mt-1">
                    {stat.value}
                  </p>
                </div>
                <Icon className={`w-8 h-8 ${stat.color}`} />
              </div>
            </div>
          )
        })}
      </div>

      {/* Recent Runs */}
      <div className="joule-panel">
        <h2 className="text-xl font-semibold text-joule-ink mb-4">
          Recent Runs
        </h2>
        <div className="space-y-3">
          {stats.recentRuns.length === 0 ? (
            <p className="text-joule-muted">No runs found</p>
          ) : (
            stats.recentRuns.map((run) => (
              <div
                key={run.run_id}
                className="flex items-center justify-between p-3 bg-joule-bg rounded-lg"
              >
                <div>
                  <p className="font-medium text-joule-ink">
                    {run.run_id}
                  </p>
                  <p className="text-sm text-joule-muted">
                    {run.target_qualname} • {run.run_type}
                  </p>
                </div>
                <div className="flex items-center space-x-3">
                  <span
                    className={`joule-status-badge joule-status-${run.status}`}
                  >
                    {run.status}
                  </span>
                  <span className="text-sm text-joule-muted">
                    {new Date(run.created_at).toLocaleTimeString()}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div className="joule-panel">
        <h2 className="text-xl font-semibold text-joule-ink mb-4">
          Quick Actions
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button className="joule-button joule-button-primary">
            Start New Baseline
          </button>
          <button className="joule-button joule-button-primary">
            Run Optimization
          </button>
          <button className="joule-button joule-button-secondary">
            Discover Targets
          </button>
        </div>
      </div>
    </div>
  )
}
