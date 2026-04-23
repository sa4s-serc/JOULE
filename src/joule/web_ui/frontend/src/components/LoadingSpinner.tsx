import { Activity } from 'lucide-react'

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
  message?: string
}

const sizeClasses = {
  sm: 'w-4 h-4',
  md: 'w-8 h-8',
  lg: 'w-12 h-12',
}

export function LoadingSpinner({
  size = 'md',
  className = '',
  message,
}: LoadingSpinnerProps) {
  return (
    <div className={`flex flex-col items-center justify-center ${className}`}>
      <Activity className={`${sizeClasses[size]} text-joule-accent animate-spin`} />
      {message && (
        <p className="mt-2 text-sm text-joule-muted">{message}</p>
      )}
    </div>
  )
}

interface LoadingOverlayProps {
  isLoading: boolean
  message?: string
  children: React.ReactNode
}

export function LoadingOverlay({
  isLoading,
  message = 'Loading...',
  children,
}: LoadingOverlayProps) {
  if (!isLoading) return <>{children}</>

  return (
    <div className="relative">
      {children}
      <div className="absolute inset-0 bg-joule-bg/80 flex items-center justify-center z-10">
        <LoadingSpinner size="lg" message={message} />
      </div>
    </div>
  )
}

export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className="joule-panel animate-pulse">
      <div className="h-4 bg-joule-chip rounded w-1/3 mb-4"></div>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-3 bg-joule-chip rounded mb-2"
          style={{ width: `${Math.random() * 40 + 60}%` }}
        ></div>
      ))}
    </div>
  )
}

export function SkeletonTable({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="joule-panel animate-pulse">
      <div className="h-4 bg-joule-chip rounded w-1/4 mb-4"></div>
      <div className="space-y-2">
        {Array.from({ length: rows }).map((_, rowIdx) => (
          <div key={rowIdx} className="flex gap-2">
            {Array.from({ length: cols }).map((_, colIdx) => (
              <div
                key={colIdx}
                className="h-3 bg-joule-chip rounded flex-1"
              ></div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

export default LoadingSpinner
