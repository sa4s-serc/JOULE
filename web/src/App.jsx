
import React, { useState } from 'react';
import { Sprout, Github, BookOpen } from 'lucide-react';
import OptimizationForm from './components/OptimizationForm';
import Dashboard from './components/Dashboard';
import { config } from './config';

function App() {
  const [task, setTask] = useState(null);
  const [error, setError] = useState(null);

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto', paddingBottom: '4rem' }}>
      <nav className="header">
        <div className="logo">
          <Sprout size={28} className="logo-icon" />
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ lineHeight: 1 }}>HEDGE</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--primary)', fontWeight: 600, letterSpacing: '0.1em' }}>EVOLUTIONARY OPTIMIZER</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
          <a href={`${config.API_BASE_URL}/docs`} target="_blank" rel="noopener noreferrer" className="btn-small" style={{ textDecoration: 'none', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <BookOpen size={16} /> API Docs
          </a>
          <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="btn-small" style={{ textDecoration: 'none', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Github size={16} /> GitHub
          </a>
          {task && (
            <button onClick={() => setTask(null)} className="btn-small" style={{ borderColor: 'var(--primary)', color: 'var(--primary)' }}>
              New Task
            </button>
          )}
        </div>
      </nav>

      <div style={{ padding: '0 2rem' }}>
        {error && (
          <div className="card glass" style={{ borderColor: 'var(--danger)', color: 'var(--danger)', marginBottom: '2rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>Error: {error}</span>
            <button onClick={() => setError(null)} className="btn-small">Dismiss</button>
          </div>
        )}

        {!task ? (
          <>
            <div className="hero-section">
              <h1 className="hero-title">Evolve Your Code</h1>
              <p className="hero-subtitle">
                Advanced genetic algorithms meet large language models to optimize Python code for energy efficiency and performance.
              </p>
            </div>
            <div style={{ maxWidth: '900px', margin: '0 auto' }}>
              <OptimizationForm
                onStart={setTask}
                onError={setError}
              />
            </div>
          </>
        ) : (
          <Dashboard task={task} />
        )}
      </div>
    </div>
  );
}

export default App;
