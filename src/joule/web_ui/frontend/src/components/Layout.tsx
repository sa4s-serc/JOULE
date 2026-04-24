import { useState, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import { 
  LayoutDashboard, 
  FolderOpen, 
  Search, 
  Activity, 
  Zap, 
  List, 
  CheckCircle 
} from 'lucide-react'
import { useUIStore } from '@/stores'

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Projects', href: '/projects', icon: FolderOpen },
  { name: 'Discover', href: '/discover', icon: Search },
  { name: 'Baseline', href: '/baseline', icon: Activity },
  { name: 'Optimize', href: '/optimize', icon: Zap },
  { name: 'Results', href: '/results', icon: List },
  { name: 'Apply', href: '/apply', icon: CheckCircle },
]

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const { isSidebarOpen, setSidebarOpen } = useUIStore()

  return (
    <div className="min-h-screen bg-gradient-to-b from-joule-bg to-joule-chip">
      <div className="flex">
        {/* Sidebar */}
        <div className={`${isSidebarOpen ? 'w-64' : 'w-16'} min-h-screen bg-joule-panel border-r border-joule-border transition-all duration-300`}>
          <div className="p-6">
            <h1 className={`text-2xl font-bold text-joule-ink ${!isSidebarOpen && 'hidden'}`}>JOULE</h1>
            <p className={`text-sm text-joule-muted mt-1 ${!isSidebarOpen && 'hidden'}`}>Optimization Toolkit</p>
            <button
              onClick={() => setSidebarOpen(!isSidebarOpen)}
              className="mt-4 p-2 hover:bg-joule-chip rounded-lg transition-colors"
              title={isSidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
            >
              <svg className="w-4 h-4 text-joule-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {isSidebarOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
                )}
              </svg>
            </button>
          </div>

          <nav className="px-4 pb-6">
            <ul className="space-y-2">
              {navigation.map((item) => {
                const Icon = item.icon
                return (
                  <li key={item.name}>
                    <NavLink
                      to={item.href}
                      className={({ isActive }) =>
                        `flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-200 ${
                          isActive
                            ? 'bg-joule-accent text-white'
                            : 'text-joule-muted hover:text-joule-ink hover:bg-joule-chip'
                        } ${!isSidebarOpen && 'justify-center px-2'}`
                      }
                      title={!isSidebarOpen ? item.name : undefined}
                    >
                      <Icon className="w-4 h-4" />
                      {isSidebarOpen && <span className="ml-3">{item.name}</span>}
                    </NavLink>
                  </li>
                )
              })}
            </ul>
          </nav>
        </div>

        {/* Main Content */}
        <div className="flex-1">
          {/* Header */}
          <header className="bg-joule-panel border-b border-joule-border px-8 py-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-joule-ink">
                Web Interface
              </h2>
              <div className="flex items-center space-x-4">
                <span className="joule-chip">v0.1.0</span>
                <ConnectionStatus />
              </div>
            </div>
          </header>

          {/* Page Content */}
          <main className="p-8">
            {children}
          </main>
        </div>
      </div>
    </div>
  )
}

// Connection status component with real health check
function ConnectionStatus() {
  const [isConnected, setIsConnected] = useState(false)

  useEffect(() => {
    const checkConnection = async () => {
      try {
        const response = await fetch('/api/health')
        setIsConnected(response.ok)
      } catch {
        setIsConnected(false)
      }
    }

    checkConnection()
    const interval = setInterval(checkConnection, 30000) // Check every 30s
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="flex items-center space-x-2">
      <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
      <span className="text-sm text-joule-muted">
        {isConnected ? 'Connected' : 'Disconnected'}
      </span>
    </div>
  )
}
