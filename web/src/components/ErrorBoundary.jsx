import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    // Log the error to console and potentially to a logging service
    console.error('Error caught by boundary:', error, errorInfo);
    this.setState({
      error: error,
      errorInfo: errorInfo
    });
  }

  handleReload = () => {
    window.location.reload();
  };

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ 
          padding: '2rem', 
          textAlign: 'center', 
          maxWidth: '600px', 
          margin: '2rem auto',
          backgroundColor: 'var(--bg-card)',
          borderRadius: '12px',
          border: '1px solid var(--danger)'
        }}>
          <AlertTriangle size={48} color="var(--danger)" style={{ marginBottom: '1rem' }} />
          <h2 style={{ color: 'var(--danger)', marginBottom: '1rem' }}>Something went wrong</h2>
          <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>
            An unexpected error occurred. This might be a temporary issue.
          </p>
          
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginBottom: '2rem' }}>
            <button onClick={this.handleReset} className="btn-primary">
              Try Again
            </button>
            <button onClick={this.handleReload} className="btn-secondary">
              <RefreshCw size={16} style={{ marginRight: '0.5rem' }} />
              Reload Page
            </button>
          </div>

          {process.env.NODE_ENV === 'development' && this.state.error && (
            <details style={{ 
              textAlign: 'left', 
              backgroundColor: 'var(--bg-dark)', 
              padding: '1rem', 
              borderRadius: '8px',
              marginTop: '1rem'
            }}>
              <summary style={{ cursor: 'pointer', color: 'var(--text-muted)' }}>
                Error Details (Development)
              </summary>
              <pre style={{ 
                fontSize: '0.8rem', 
                color: 'var(--danger)', 
                overflow: 'auto',
                marginTop: '0.5rem'
              }}>
                {this.state.error && this.state.error.toString()}
                {this.state.errorInfo.componentStack}
              </pre>
            </details>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;