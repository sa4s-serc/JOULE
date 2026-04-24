import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Activity, Zap, TrendingUp, AlertCircle } from 'lucide-react'
import { apiClient } from '../utils/api'

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
  const navigate = useNavigate()
  const [stats, setStats] = useState<DashboardStats>({
    totalRuns: 0,
    runningRuns: 0,
    completedRuns: 0,
    failedRuns: 0,
    recentRuns: [],
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const runs = await apiClient.getRuns()
        const totalRuns = runs.length
        const runningRuns = runs.filter((r: any) => r.status === 'running').length
        const completedRuns = runs.filter((r: any) => r.status === 'completed').length
        const failedRuns = runs.filter((r: any) => r.status === 'failed').length

        setStats({
          totalRuns,
          runningRuns,
          completedRuns,
          failedRuns,
          recentRuns: runs.slice(0, 5).map((r: any) => ({
            run_id: r.run_id,
            run_type: r.run_type,
            status: r.status,
            target_qualname: r.target_qualname || 'unknown',
            created_at: r.created_at,
          })),
        })
      } catch (err) {
        // API not reachable – show empty state
        console.warn('Failed to fetch dashboard stats:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchStats()
    const interval = setInterval(fetchStats, 10000) // Poll every 10s
    return () => clearInterval(interval)
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
                    {loading ? '—' : stat.value}
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
          {loading ? (
            <div className="animate-pulse space-y-3">
              {[1,2,3].map(i => (
                <div key={i} className="h-12 bg-joule-chip rounded-lg" />
              ))}
            </div>
          ) : stats.recentRuns.length === 0 ? (
            <p className="text-joule-muted">No runs yet. Start a baseline or optimization to see results here.</p>
          ) : (
            stats.recentRuns.map((run) => (
              <div
                key={run.run_id}
                className="flex items-center justify-between p-3 bg-joule-bg rounded-lg cursor-pointer hover:bg-joule-chip transition-colors"
                onClick={() => navigate(`/inspect/${run.run_id}`)}
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
          <button
            className="joule-button joule-button-primary"
            onClick={() => navigate('/baseline')}
          >
            Start New Baseline
          </button>
          <button
            className="joule-button joule-button-primary"
            onClick={() => navigate('/optimize')}
          >
            Run Optimization
          </button>
          <button
            className="joule-button joule-button-secondary"
            onClick={() => navigate('/discover')}
          >
            Discover Targets
          </button>
        </div>
      </div>
    </div>
  )
}
