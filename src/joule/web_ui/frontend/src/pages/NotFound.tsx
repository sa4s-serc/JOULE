import { useNavigate } from 'react-router-dom'
import { FileQuestion, Home, ArrowLeft } from 'lucide-react'

export default function NotFound() {
  const navigate = useNavigate()

  return (
    <div className="min-h-[60vh] flex items-center justify-center">
      <div className="joule-panel max-w-md w-full text-center">
        <FileQuestion className="w-16 h-16 text-joule-muted mx-auto mb-4" />
        <h1 className="text-4xl font-bold text-joule-ink mb-2">404</h1>
        <h2 className="text-xl font-semibold text-joule-ink mb-4">
          Page Not Found
        </h2>
        <p className="text-joule-muted mb-6">
          The page you're looking for doesn't exist or has been moved.
        </p>
        <div className="flex gap-3 justify-center">
          <button
            onClick={() => navigate(-1)}
            className="joule-button joule-button-secondary flex items-center gap-2"
          >
            <ArrowLeft className="w-4 h-4" />
            Go Back
          </button>
          <button
            onClick={() => navigate('/')}
            className="joule-button joule-button-primary flex items-center gap-2"
          >
            <Home className="w-4 h-4" />
            Dashboard
          </button>
        </div>
      </div>
    </div>
  )
}
