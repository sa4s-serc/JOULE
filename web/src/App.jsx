
import React, { useState } from 'react';
import { Sprout } from 'lucide-react';
import OptimizationForm from './components/OptimizationForm';
import Dashboard from './components/Dashboard';

function App() {
  const [task, setTask] = useState(null);
  const [error, setError] = useState(null);

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', paddingBottom: '2rem' }}>
      <nav className="header">
        <div className="logo">
          <Sprout size={32} />
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ lineHeight: 1 }}>HEDGE</span>
            <span style={{ fontSize: '0.75rem', color: '#64748B', fontWeight: 400 }}>Evolutionary Optimizer</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <a href="http://localhost:8000/docs" target="_blank" style={{ color: 'var(--text-muted)', fontSize: '0.9rem', textDecoration: 'none' }}>API Docs</a>
          {task && (
            <button onClick={() => setTask(null)} style={{ background: 'transparent', border: '1px solid var(--border)' }}>
              New Task
            </button>
          )}
        </div>
      </nav>

      <div style={{ padding: '2rem' }}>
        {error && (
          <div className="card" style={{ borderColor: 'var(--danger)', color: 'var(--danger)' }}>
            {error}
            <button onClick={() => setError(null)} style={{ marginLeft: '1rem', padding: '0.2rem 0.5rem', fontSize: '0.8rem' }}>Dismiss</button>
          </div>
        )}

        {!task ? (
          <OptimizationForm
            onStart={setTask}
            onError={setError}
          />
        ) : (
          <Dashboard task={task} />
        )}
      </div>
    </div>
  );
}

export default App;
