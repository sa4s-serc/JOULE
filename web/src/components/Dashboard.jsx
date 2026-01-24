import React, { useEffect, useState, useRef } from 'react';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    ScatterChart, Scatter, Legend
} from 'recharts';
import { Terminal, Activity, Zap, Clock, Save, ArrowRight, TrendingDown } from 'lucide-react';

const Dashboard = ({ task }) => {
    const [status, setStatus] = useState(task);
    const [logs, setLogs] = useState([]);
    const [metricsHistory, setMetricsHistory] = useState([]);
    const [paretoData, setParetoData] = useState([]);
    const [mutatorStats, setMutatorStats] = useState({});
    const [bestCode, setBestCode] = useState(task.best_code || '');
    const wsRef = useRef(null);
    const logEndRef = useRef(null);

    const [isConnected, setIsConnected] = useState(false);

    useEffect(() => {
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
            updateMutatorStats(payload.mutator, 'attempt');
        } else if (type === 'mutation_result') {
            if (payload.success) {
                addLog("Mutator", `Success: ${payload.strategy}`, "success");
                updateMutatorStats(payload.mutator, 'success');
            } else {
                addLog("Mutator", `Failed: ${payload.error || payload.strategy}`, "error");
                updateMutatorStats(payload.mutator, 'failure');
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
                },
                improvement: payload.improvement
            }));
        } else if (type === 'pareto_update') {
            setParetoData(payload.solutions);
        } else if (type === 'evaluation_failure') {
            addLog("System", `Evaluation Failed for ${payload.mutation}: ${payload.error}`, "error");
        } else if (type === 'error') {
            addLog("System", `Critical Error: ${payload.message}`, "error");
            setStatus(prev => ({ ...prev, status: 'failed' }));
        } else if (type === 'optimization_complete') {
            addLog("System", "Optimization Completed!", "success");
            setStatus(prev => ({ ...prev, status: 'completed' }));
            if (payload.best_code) setBestCode(payload.best_code);
        }
    };

    const updateMutatorStats = (mutatorName, type) => {
        setMutatorStats(prev => {
            const current = prev[mutatorName] || { attempts: 0, successes: 0 };
            return {
                ...prev,
                [mutatorName]: {
                    attempts: type === 'attempt' ? current.attempts + 1 : current.attempts,
                    successes: type === 'success' ? current.successes + 1 : current.successes
                }
            };
        });
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
                        background: 'linear-gradient(90deg, var(--primary), var(--secondary))',
                        boxShadow: '0 0 10px var(--primary)',
                        transition: 'width 0.5s ease-out'
                    }} />
                </div>
            )}

            {/* Metrics Cards */}
            <div className="grid cols-4">
                <div className="card glass">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)' }}>
                        <Activity size={18} /> Status
                        {isConnected && <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--success)', marginLeft: 'auto', boxShadow: '0 0 5px var(--success)' }} title="Connected" />}
                    </div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold', marginTop: '0.5rem', textTransform: 'capitalize', color: 'var(--text-main)' }}>
                        {status.status}
                    </div>
                    <div className="status-badge" style={{ marginTop: '0.75rem' }}>
                        Gen {status.current_generation} / {status.total_generations}
                    </div>
                </div>

                <div className="card glass">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)' }}>
                        <Zap size={18} /> Energy
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'end' }}>
                        <div style={{ fontSize: '1.5rem', fontWeight: 'bold', marginTop: '0.5rem', color: 'var(--primary)' }}>
                            {status.best_metrics?.energy_joules
                                ? `${status.best_metrics.energy_joules.toExponential(4)} J`
                                : '-'}
                        </div>
                        {status.improvement?.energy_percent > 0 && (
                            <div style={{ color: 'var(--success)', fontSize: '0.9rem', display: 'flex', alignItems: 'center' }}>
                                <TrendingDown size={14} style={{ marginRight: '4px' }} />
                                {status.improvement.energy_percent.toFixed(1)}%
                            </div>
                        )}
                    </div>
                </div>

                <div className="card glass">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)' }}>
                        <Clock size={18} /> Duration
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'end' }}>
                        <div style={{ fontSize: '1.5rem', fontWeight: 'bold', marginTop: '0.5rem', color: 'var(--secondary)' }}>
                            {status.best_metrics?.duration_seconds
                                ? `${(status.best_metrics.duration_seconds * 1000).toFixed(2)} ms`
                                : '-'}
                        </div>
                        {status.improvement?.time_percent > 0 && (
                            <div style={{ color: 'var(--secondary)', fontSize: '0.9rem', display: 'flex', alignItems: 'center' }}>
                                <TrendingDown size={14} style={{ marginRight: '4px' }} />
                                {status.improvement.time_percent.toFixed(1)}%
                            </div>
                        )}
                    </div>
                </div>

                <div className="card glass">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)' }}>
                        <Save size={18} /> Best Solution
                    </div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold', marginTop: '0.5rem', color: 'var(--text-main)' }}>
                        {status.best_metrics ? 'Optimized' : 'None yet'}
                    </div>
                    {status.best_metrics && <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>Updated just now</div>}
                </div>
            </div>

            <div className="grid cols-2">
                {/* Convergence Chart */}
                <div className="card glass" style={{ height: '400px' }}>
                    <h3 style={{ marginBottom: '1.5rem', fontSize: '1.1rem', fontWeight: 600 }}>Convergence History</h3>
                    <ResponsiveContainer width="100%" height="85%">
                        <LineChart data={metricsHistory}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                            <XAxis
                                dataKey="generation"
                                stroke="var(--text-muted)"
                                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                                tickLine={false}
                                axisLine={false}
                            />
                            <YAxis
                                stroke="var(--text-muted)"
                                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                                tickLine={false}
                                axisLine={false}
                            />
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: 'rgba(13, 17, 26, 0.95)',
                                    border: '1px solid var(--border)',
                                    borderRadius: '8px',
                                    boxShadow: '0 4px 6px rgba(0,0,0,0.3)'
                                }}
                                itemStyle={{ color: '#F1F5F9' }}
                                labelStyle={{ color: 'var(--text-muted)', marginBottom: '0.5rem' }}
                            />
                            <Legend />
                            <Line
                                type="monotone"
                                dataKey="energy"
                                name="Energy (J)"
                                stroke="#00ff9d"
                                strokeWidth={3}
                                dot={{ r: 4, fill: '#00ff9d', strokeWidth: 0 }}
                                activeDot={{ r: 6, stroke: '#fff', strokeWidth: 2 }}
                            />
                            <Line
                                type="monotone"
                                dataKey="time"
                                name="Time (s)"
                                stroke="#00b8ff"
                                strokeWidth={3}
                                dot={{ r: 4, fill: '#00b8ff', strokeWidth: 0 }}
                                activeDot={{ r: 6, stroke: '#fff', strokeWidth: 2 }}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>

                {/* Pareto Frontier Chart */}
                <div className="card glass" style={{ height: '400px' }}>
                    <h3 style={{ marginBottom: '1.5rem', fontSize: '1.1rem', fontWeight: 600 }}>Pareto Frontier (Trade-offs)</h3>
                    <ResponsiveContainer width="100%" height="85%">
                        <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                            <XAxis
                                type="number"
                                dataKey="time"
                                name="Time"
                                unit="s"
                                stroke="var(--text-muted)"
                                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                                tickLine={false}
                                axisLine={false}
                                label={{ value: 'Execution Time (s)', position: 'bottom', fill: 'var(--text-muted)', fontSize: 12 }}
                            />
                            <YAxis
                                type="number"
                                dataKey="energy"
                                name="Energy"
                                unit="J"
                                stroke="var(--text-muted)"
                                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                                tickLine={false}
                                axisLine={false}
                                label={{ value: 'Energy (J)', angle: -90, position: 'left', fill: 'var(--text-muted)', fontSize: 12 }}
                            />
                            <Tooltip
                                cursor={{ strokeDasharray: '3 3' }}
                                contentStyle={{
                                    backgroundColor: 'rgba(13, 17, 26, 0.95)',
                                    border: '1px solid var(--border)',
                                    borderRadius: '8px'
                                }}
                            />
                            <Scatter name="Solutions" data={paretoData} fill="var(--primary)" />
                        </ScatterChart>
                    </ResponsiveContainer>
                </div>
            </div>

            <div className="grid cols-2">
                {/* Mutator Stats & Logs */}
                <div className="card glass" style={{ height: '500px', display: 'flex', flexDirection: 'column' }}>
                    {/* Tabs or Header for Logs/Stats. For now simple separation */}
                    <div style={{ paddingBottom: '1rem', borderBottom: '1px solid var(--border)', marginBottom: '1rem' }}>
                        <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Active Mutators</h3>
                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
                            {Object.entries(mutatorStats).map(([name, stats]) => (
                                <div key={name} className="status-badge" style={{ display: 'flex', gap: '0.5rem' }}>
                                    <span>{name}</span>
                                    <span style={{ color: 'var(--text-muted)' }}>{stats.successes}/{stats.attempts}</span>
                                </div>
                            ))}
                            {Object.keys(mutatorStats).length === 0 && <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>No data yet</span>}
                        </div>
                    </div>

                    <div style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.1rem', fontWeight: 600 }}>
                            <Terminal size={18} /> Event Log
                        </h3>
                        <button onClick={() => setLogs([])} className="btn-small" style={{ border: 'none' }}>
                            Clear
                        </button>
                    </div>
                    <div className="log-container" style={{ flex: 1 }}>
                        {logs.length === 0 && <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>Waiting for events...</div>}
                        {logs.map((log, i) => (
                            <div key={i} className={`log-entry`} style={{
                                borderLeft: `2px solid ${log.type === 'error' ? 'var(--danger)' :
                                    log.type === 'success' ? 'var(--success)' :
                                        log.type === 'system' ? 'var(--secondary)' : 'var(--text-muted)'
                                    }`,
                                paddingLeft: '0.75rem',
                                color: log.type === 'error' ? '#fca5a5' : 'inherit'
                            }}>
                                <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginRight: '0.75rem', minWidth: '60px', display: 'inline-block' }}>
                                    [{log.time.toLocaleTimeString([], { hour12: false })}]
                                </span>
                                <span style={{ fontWeight: 600, marginRight: '0.5rem', color: 'var(--text-main)' }}>
                                    {log.source}:
                                </span>
                                {log.message}
                            </div>
                        ))}
                        <div ref={logEndRef} />
                    </div>
                </div>

                {/* Code Diff */}
                {(bestCode || status.original_code) && (
                    <div className="card glass">
                        <h3 style={{ marginBottom: '1.5rem', fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            Code Evolution <ArrowRight size={16} color="var(--text-muted)" />
                        </h3>
                        <div style={{ display: 'flex', flexDirection: 'column', height: '90%' }}>
                            <div style={{ flex: 1, marginBottom: '1rem', display: 'flex', flexDirection: 'column' }}>
                                <label className="label-hint" style={{ marginBottom: '0.5rem' }}>Original Code</label>
                                <pre style={{
                                    padding: '1rem',
                                    background: '#050505',
                                    borderRadius: '8px',
                                    overflow: 'auto',
                                    fontSize: '0.8rem',
                                    border: '1px solid var(--border)',
                                    flex: 1,
                                    color: 'var(--text-muted)',
                                    lineHeight: '1.5'
                                }}>
                                    {status.original_code}
                                </pre>
                            </div>
                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                                <label className="label-hint" style={{ marginBottom: '0.5rem', color: 'var(--primary)' }}>Optimized Code</label>
                                <pre style={{
                                    padding: '1rem',
                                    background: '#050505',
                                    borderRadius: '8px',
                                    overflow: 'auto',
                                    fontSize: '0.8rem',
                                    border: '1px solid var(--primary)',
                                    flex: 1,
                                    color: 'var(--text-code)',
                                    lineHeight: '1.5',
                                    boxShadow: '0 0 20px rgba(0, 255, 157, 0.05)'
                                }}>
                                    {bestCode || 'Waiting for first improvement...'}
                                </pre>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
export default Dashboard;
