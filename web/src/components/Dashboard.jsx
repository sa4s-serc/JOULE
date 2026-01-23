
import React, { useEffect, useState, useRef } from 'react';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import { Terminal, Activity, Zap, Clock, Save } from 'lucide-react';

const Dashboard = ({ task }) => {
    const [status, setStatus] = useState(task);
    const [logs, setLogs] = useState([]);
    const [metricsHistory, setMetricsHistory] = useState([]);
    const [bestCode, setBestCode] = useState(task.best_code || '');
    const wsRef = useRef(null);
    const logEndRef = useRef(null);

    const [isConnected, setIsConnected] = useState(false);

    useEffect(() => {
        // Connect to WebSocket
        const ws = new WebSocket(`ws://localhost:8000/ws/${task.task_id}`);
        wsRef.current = ws;

        ws.onopen = () => {
            setIsConnected(true);
            addLog("System", "Connected to live stream", "success");
        };

        ws.onclose = () => {
            setIsConnected(false);
            addLog("System", "Disconnected from live stream", "error");
        };

        ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            handleMessage(message);
        };

        ws.onerror = (err) => {
            console.error("WebSocket error:", err);
            addLog("System", "WebSocket connection failed", "error");
        };

        return () => {
            if (ws.readyState === 1) ws.close();
        };
    }, [task.task_id]);

    useEffect(() => {
        logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    const handleMessage = (msg) => {
        const { type, payload } = msg;

        if (type === 'mutation_attempt') {
            addLog("Mutator", `Trying ${payload.strategy} using ${payload.mutator}...`, "info");
        } else if (type === 'mutation_result') {
            if (payload.success) {
                addLog("Mutator", `Success: ${payload.strategy}`, "success");
            } else {
                addLog("Mutator", `Failed: ${payload.error || payload.strategy}`, "error");
            }
        } else if (type === 'generation_start') {
            addLog("System", `Starting Generation ${payload.generation + 1}/${payload.total_generations}`, "system");
            setStatus(prev => ({ ...prev, current_generation: payload.generation + 1 }));
        } else if (type === 'generation_complete') {
            addLog("System", `Generation ${payload.generation + 1} complete. Improved: ${payload.improved_count}`, "system");
            if (payload.best_metrics) {
                setStatus(prev => ({ ...prev, best_metrics: payload.best_metrics }));
                setMetricsHistory(prev => [...prev, {
                    generation: payload.generation,
                    energy: payload.best_metrics.energy_joules,
                    time: payload.best_metrics.duration_seconds
                }]);
            }
        } else if (type === 'new_best_solution') {
            addLog("System", `New Best Solution! Energy: ${payload.energy?.toExponential(2)}J`, "success");
            setBestCode(payload.code);
            setStatus(prev => ({
                ...prev,
                best_metrics: {
                    energy_joules: payload.energy,
                    duration_seconds: payload.time
                }
            }));
        } else if (type === 'optimization_complete') {
            addLog("System", "Optimization Completed!", "success");
            setStatus(prev => ({ ...prev, status: 'completed' }));
            if (payload.best_code) setBestCode(payload.best_code);
        }
    };

    const addLog = (source, message, type = 'info') => {
        setLogs(prev => [...prev.slice(-199), { source, message, type, time: new Date() }]);
    };

    const progress = (status.current_generation / status.total_generations) * 100;

    return (
        <div className="grid">
            {/* Progress Bar */}
            {status.status === 'running' && (
                <div style={{ width: '100%', height: '4px', background: 'var(--glass)', borderRadius: '2px', overflow: 'hidden' }}>
                    <div style={{
                        width: `${progress}%`,
                        height: '100%',
                        background: 'var(--primary)',
                        transition: 'width 0.5s ease-out'
                    }} />
                </div>
            )}

            {/* Metrics Cards */}
            <div className="grid cols-4" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
                <div className="card glass">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)' }}>
                        <Activity size={20} /> Status
                        {isConnected && <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#10B981', marginLeft: 'auto' }} title="Connected" />}
                    </div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold', marginTop: '0.5rem', textTransform: 'capitalize' }}>
                        {status.status}
                    </div>
                    <div className="status-badge" style={{ display: 'inline-block', marginTop: '0.5rem' }}>
                        Gen {status.current_generation} / {status.total_generations}
                    </div>
                </div>

                <div className="card glass">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)' }}>
                        <Zap size={20} /> Energy
                    </div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold', marginTop: '0.5rem' }}>
                        {status.best_metrics?.energy_joules
                            ? `${status.best_metrics.energy_joules.toExponential(4)} J`
                            : '-'}
                    </div>
                </div>

                <div className="card glass">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)' }}>
                        <Clock size={20} /> Duration
                    </div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold', marginTop: '0.5rem' }}>
                        {status.best_metrics?.duration_seconds
                            ? `${(status.best_metrics.duration_seconds * 1000).toFixed(2)} ms`
                            : '-'}
                    </div>
                </div>

                <div className="card glass">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)' }}>
                        <Save size={20} /> Best
                    </div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold', marginTop: '0.5rem' }}>
                        {status.best_metrics ? 'Optimized' : 'None yet'}
                    </div>
                </div>
            </div>

            <div className="grid cols-2">
                {/* Chart */}
                <div className="card glass" style={{ height: '400px' }}>
                    <h3 style={{ marginBottom: '1rem' }}>Convergence History</h3>
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={metricsHistory}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                            <XAxis dataKey="generation" stroke="#94A3B8" />
                            <YAxis stroke="#94A3B8" />
                            <Tooltip
                                contentStyle={{ backgroundColor: '#1E293B', border: '1px solid #334155' }}
                                itemStyle={{ color: '#F1F5F9' }}
                            />
                            <Line type="monotone" dataKey="energy" stroke="#10B981" strokeWidth={2} dot={false} />
                            <Line type="monotone" dataKey="time" stroke="#38BDF8" strokeWidth={2} dot={false} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>

                {/* Live Logs */}
                <div className="card glass" style={{ height: '400px', display: 'flex', flexDirection: 'column' }}>
                    <div style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <Terminal size={20} /> Live Activity
                        </h3>
                        <button onClick={() => setLogs([])} className="btn-small">
                            Clear
                        </button>
                    </div>
                    <div className="log-container" style={{ flex: 1 }}>
                        {logs.map((log, i) => (
                            <div key={i} className={`log-entry ${log.type}`} style={{
                                color: log.type === 'error' ? 'var(--danger)' :
                                    log.type === 'success' ? 'var(--primary-light)' :
                                        log.type === 'system' ? '#60A5FA' : 'inherit'
                            }}>
                                <span style={{ color: '#64748B', marginRight: '0.5rem' }}>
                                    [{log.time.toLocaleTimeString()}]
                                </span>
                                <span style={{ fontWeight: 500, marginRight: '0.5rem' }}>
                                    {log.source}:
                                </span>
                                {log.message}
                            </div>
                        ))}
                        <div ref={logEndRef} />
                    </div>
                </div>
            </div>

            {/* Code Diff Section */}
            {(bestCode || status.original_code) && (
                <div className="card glass">
                    <h3 style={{ marginBottom: '1.5rem' }}>Code Evolution</h3>
                    <div className="grid cols-2">
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                            <label className="label-hint">Original Code</label>
                            <pre style={{
                                padding: '1.5rem',
                                background: '#000',
                                borderRadius: '12px',
                                overflow: 'auto',
                                fontSize: '0.85rem',
                                border: '1px solid var(--border)',
                                height: '400px',
                                color: '#94A3B8'
                            }}>
                                {status.original_code}
                            </pre>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                            <label className="label-hint">Optimized Code</label>
                            <pre style={{
                                padding: '1.5rem',
                                background: '#000',
                                borderRadius: '12px',
                                overflow: 'auto',
                                fontSize: '0.85rem',
                                border: '1px solid var(--primary)',
                                height: '400px',
                                color: '#10B981'
                            }}>
                                {bestCode || 'Waiting for first improvement...'}
                            </pre>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Dashboard;
