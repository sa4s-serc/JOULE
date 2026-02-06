import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    ScatterChart, Scatter, Legend, Cell
} from 'recharts';
import { Terminal, Activity, Zap, Clock, Save, ArrowRight, TrendingDown, Eye, BarChart2, Info, Wifi, WifiOff } from 'lucide-react';
import axios from 'axios';
import { config } from '../config';
import { useWebSocket } from '../hooks/useWebSocket';
import { safeToLocaleTimeString } from '../utils/dateUtils';
import DeepAnalysis from './DeepAnalysis';

const Dashboard = ({ task }) => {
    const [status, setStatus] = useState(task);
    const [logs, setLogs] = useState([]);
    const [metricsHistory, setMetricsHistory] = useState([]);
    const [paretoData, setParetoData] = useState([]);
    const [mutatorStats, setMutatorStats] = useState({});
    const [bestCode, setBestCode] = useState(task.best_code || '');
    const [inspectedSolution, setInspectedSolution] = useState(null);
    const [evaluationHistory, setEvaluationHistory] = useState([]);
    const [activeTab, setActiveTab] = useState('overview');
    const logEndRef = useRef(null);

    // Limit log entries to prevent memory issues
    const addLog = useCallback((source, message, level = "info") => {
        try {
            let timestamp = '--:--:--';
            try {
                timestamp = safeToLocaleTimeString();
            } catch (timeError) {
                console.warn('Error getting timestamp:', timeError);
                timestamp = new Date().toLocaleTimeString();
            }
            setLogs(prev => {
                const newLogs = [...prev, { timestamp, source, message, level }];
                // Keep only the last N entries
                return newLogs.slice(-config.LOG_MAX_ENTRIES);
            });
        } catch (error) {
            console.error('Error adding log:', error);
            // Fallback without timestamp
            setLogs(prev => {
                const newLogs = [...prev, { timestamp: '--:--:--', source, message, level }];
                return newLogs.slice(-config.LOG_MAX_ENTRIES);
            });
        }
    }, []);

    // Helper function to normalize mutator names
    const normalizeMutatorName = useCallback((name) => {
        if (!name || typeof name !== 'string') {
            return 'Unknown';
        }
        
        // Remove common prefixes and suffixes
        let normalized = name
            .replace(/Mutator$/, '')
            .replace(/^.*\./, '') // Remove module path
            .replace(/([A-Z])/g, ' $1') // Add spaces before capitals
            .trim();
        
        // Handle specific cases
        const mappings = {
            'Loop Unroller': 'Loop Unroll',
            'Constant Folder': 'Constant Fold',
            'Dead Code Eliminator': 'Dead Code',
            'Variable Renamer': 'Rename Vars',
            'Function Inliner': 'Inline Funcs',
            'Algorithmic Optimizer': 'Algorithm',
            'Semantic Optimizer': 'Semantic',
            'Syntactic Optimizer': 'Syntactic',
            'Micro Optimizer': 'Micro'
        };
        
        return mappings[normalized] || normalized || 'Unknown';
    }, []);

    // Update mutator statistics
    const updateMutatorStats = useCallback((mutatorName, type) => {
        const normalizedName = normalizeMutatorName(mutatorName);
        
        // Debug logging for unknown mutators
        if (normalizedName === 'Unknown' || mutatorName === 'Unknown') {
            console.warn('Unknown mutator detected:', {
                original: mutatorName,
                normalized: normalizedName,
                type: type,
                timestamp: new Date().toISOString()
            });
        }
        
        setMutatorStats(prev => {
            const current = prev[normalizedName] || { attempts: 0, successes: 0 };
            return {
                ...prev,
                [normalizedName]: {
                    attempts: type === 'attempt' ? current.attempts + 1 : current.attempts,
                    successes: type === 'success' ? current.successes + 1 : current.successes
                }
            };
        });
    }, [normalizeMutatorName]);

    const handleMessage = useCallback((msg) => {
        const { type, payload } = msg;

        // Debug logging for mutation events
        if (type === 'mutation_attempt' || type === 'mutation_result') {
            console.debug('Mutation event received:', {
                type,
                mutator: payload?.mutator,
                mutator_display: payload?.mutator_display,
                strategy: payload?.strategy,
                success: payload?.success
            });
        }

        // Validate payload structure
        if (!payload) {
            console.warn('Received message with empty payload:', msg);
            return;
        }

        if (type === 'mutation_attempt') {
            const mutatorName = payload.mutator || 'Unknown';
            const displayName = payload.mutator_display || mutatorName;
            const strategy = payload.strategy || 'Unknown Strategy';
            addLog("Mutator", `Trying ${strategy} using ${displayName}...`, "info");
            updateMutatorStats(mutatorName, 'attempt');
        } else if (type === 'mutation_result') {
            const mutatorName = payload.mutator || 'Unknown';
            const displayName = payload.mutator_display || mutatorName;
            const strategy = payload.strategy || 'Unknown Strategy';
            
            if (payload.success) {
                addLog("Mutator", `Success: ${strategy}`, "success");
                updateMutatorStats(mutatorName, 'success');
            } else {
                const errorMsg = payload.error || payload.message || 'Unknown error';
                addLog("Mutator", `Failed: ${strategy} - ${errorMsg}`, "error");
                updateMutatorStats(mutatorName, 'failure');
            }
        } else if (type === 'generation_start') {
            const generation = payload.generation ?? 0;
            const totalGenerations = payload.total_generations ?? status.total_generations;
            addLog("System", `Starting Generation ${generation + 1}/${totalGenerations}`, "system");
            setStatus(prev => ({ ...prev, current_generation: generation + 1 }));
        } else if (type === 'generation_complete') {
            const generation = payload.generation ?? 0;
            const improvedCount = payload.improved_count ?? 0;
            addLog("System", `Generation ${generation + 1} complete. Improved: ${improvedCount}`, "system");
            
            if (payload.best_metrics) {
                setStatus(prev => ({ ...prev, best_metrics: payload.best_metrics }));
                setMetricsHistory(prev => [...prev, {
                    generation: generation,
                    energy: payload.best_metrics.energy_joules,
                    time: payload.best_metrics.duration_seconds
                }]);
            }
        } else if (type === 'new_best_solution') {
            const energy = payload.energy;
            const energyStr = energy ? energy.toExponential(2) : 'Unknown';
            addLog("System", `New Best Solution! Energy: ${energyStr}J`, "success");
            
            if (payload.code) {
                setBestCode(payload.code);
            }
            
            setStatus(prev => ({
                ...prev,
                best_metrics: {
                    energy_joules: payload.energy,
                    duration_seconds: payload.time
                },
                improvement: payload.improvement
            }));
        } else if (type === 'pareto_update') {
            const solutions = payload.solutions || [];
            setParetoData(solutions);
        } else if (type === 'evaluation_failure') {
            const mutation = payload.mutation || 'Unknown';
            const error = payload.error || 'Unknown error';
            addLog("System", `Evaluation Failed for ${mutation}: ${error}`, "error");
        } else if (type === 'error') {
            addLog("System", `Critical Error: ${payload.message}`, "error");
            setStatus(prev => ({ ...prev, status: 'failed' }));
        } else if (type === 'evaluation_start') {
            // Optional: highlight that something is being evaluated
        } else if (type === 'evaluation_result') {
            setEvaluationHistory(prev => [{
                ...payload,
                time: new Date(),
                id: Math.random().toString(36).substr(2, 9),
                code: payload.code || null,
                generation: status.current_generation || 0
            }, ...prev.slice(0, 49)]);

            if (payload.success) {
                // If it was very successful (improved pareto), maybe add a special log
            } else {
                addLog("Evaluator", `Failed: ${payload.mutation} - ${payload.output?.split('\n')[0]}`, "error");
            }
        } else if (type === 'optimization_complete') {
            addLog("System", "Optimization Completed!", "success");
            setStatus(prev => ({ ...prev, status: 'completed' }));
            if (payload.best_code) setBestCode(payload.best_code);
        }
    }, [addLog, updateMutatorStats, status.total_generations]);

    // WebSocket message handler
    const handleWebSocketMessage = useCallback((message) => {
        handleMessage(message);
    }, [handleMessage]);

    // WebSocket error handler
    const handleWebSocketError = useCallback((error) => {
        console.error('WebSocket error:', error);
        addLog("System", `Connection error: ${error}`, "error");
    }, [addLog]);

    // Use custom WebSocket hook
    const { isConnected, connectionStatus, reconnect } = useWebSocket(
        task.task_id,
        handleWebSocketMessage,
        handleWebSocketError
    );

    // Auto-scroll logs to bottom
    useEffect(() => {
        logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    const handleParetoClick = (data) => {
        // Recharts Scatter click data can be the payload itself or have a payload property
        const solution = data?.payload || data;
        if (solution && solution.variant_id) {
            setInspectedSolution(solution);
        }
    };

    // Helper function to get display name for mutators
    const getMutatorDisplayName = useCallback((name) => {
        // Use the normalized name or return as-is
        return normalizeMutatorName(name);
    }, [normalizeMutatorName]);

    const progress = (status.current_generation / status.total_generations) * 100;

    const displayedCode = inspectedSolution ? inspectedSolution.code : bestCode;
    const displayedMetrics = inspectedSolution ? { energy: inspectedSolution.energy, time: inspectedSolution.time } :
        status.best_metrics ? { energy: status.best_metrics.energy_joules, time: status.best_metrics.duration_seconds } : null;

    return (
        <div className="dashboard-container">
            <div className="dashboard-tabs" style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
                <button
                    className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`}
                    onClick={() => setActiveTab('overview')}
                >
                    Overview
                </button>
                <button
                    className={`tab-btn ${activeTab === 'analysis' ? 'active' : ''}`}
                    onClick={() => setActiveTab('analysis')}
                >
                    Deep Analysis
                </button>
            </div>

            {activeTab === 'overview' ? (
                <div className="grid">
                    {/* Progress Bar */}
                    {status.status === 'running' && (
                        <div style={{ width: '100%', height: '4px', background: 'var(--glass)', borderRadius: '2px', overflow: 'hidden', position: 'fixed', top: 0, left: 0, zIndex: 1000 }}>
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
                                <Zap size={18} /> Energy Efficiency
                            </div>
                            <div style={{ fontSize: '1.5rem', fontWeight: 'bold', marginTop: '0.5rem', color: 'var(--primary)' }}>
                                {displayedMetrics?.energy ? `${displayedMetrics.energy.toExponential(2)}J` : 'Pending...'}
                            </div>
                            {status.improvement && (
                                <div style={{ fontSize: '0.8rem', color: 'var(--success)', marginTop: '0.5rem' }}>
                                    {status.improvement > 0 ? '↓' : '↑'} {Math.abs(status.improvement * 100).toFixed(1)}%
                                </div>
                            )}
                        </div>

                        <div className="card glass">
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)' }}>
                                <Clock size={18} /> Execution Time
                            </div>
                            <div style={{ fontSize: '1.5rem', fontWeight: 'bold', marginTop: '0.5rem', color: 'var(--secondary)' }}>
                                {displayedMetrics?.time ? `${(displayedMetrics.time * 1000).toFixed(2)}ms` : 'Pending...'}
                            </div>
                        </div>

                        <div className="card glass">
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)' }}>
                                <BarChart2 size={18} /> Active Mutators
                            </div>
                            <div style={{ fontSize: '1.5rem', fontWeight: 'bold', marginTop: '0.5rem', color: 'var(--accent)' }}>
                                {Object.keys(mutatorStats).length}
                            </div>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
                                {Object.values(mutatorStats).reduce((sum, stat) => sum + stat.successes, 0)} successes
                            </div>
                        </div>
                    </div>

                    {/* Debug Information Panel (only show if there are issues) */}
                    {(Object.keys(mutatorStats).some(name => name === 'Unknown' || name.includes('undefined')) || 
                      logs.some(log => log.message.includes('Unknown'))) && (
                        <div className="card glass" style={{ borderColor: 'var(--warning)', marginBottom: '1rem' }}>
                            <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--warning)' }}>
                                ⚠️ Debug Information
                            </h3>
                            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                                <p>Detected potential issues with mutator identification:</p>
                                <ul style={{ marginLeft: '1rem', marginTop: '0.5rem' }}>
                                    {Object.keys(mutatorStats).filter(name => name === 'Unknown' || name.includes('undefined')).map(name => (
                                        <li key={name}>Unknown mutator: {name}</li>
                                    ))}
                                    {logs.filter(log => log.message.includes('Unknown')).slice(-3).map((log, idx) => (
                                        <li key={idx}>Recent log: {log.message}</li>
                                    ))}
                                </ul>
                                <p style={{ marginTop: '0.5rem', fontStyle: 'italic' }}>
                                    This information helps developers identify and fix mutator naming issues.
                                </p>
                            </div>
                        </div>
                    )}

                    {/* Mutator Performance Overview */}
                    {Object.keys(mutatorStats).length > 0 && (
                        <div className="card glass">
                            <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                                <Info size={20} /> Mutator Performance
                            </h3>
                            <div className="mutator-stats-grid">
                                {Object.entries(mutatorStats)
                                    .sort(([,a], [,b]) => (b.successes / Math.max(b.attempts, 1)) - (a.successes / Math.max(a.attempts, 1)))
                                    .map(([name, stats]) => {
                                        const successRate = stats.attempts > 0 ? (stats.successes / stats.attempts) * 100 : 0;
                                        const color = successRate > 50 ? 'var(--success)' : successRate > 20 ? 'var(--warning)' : 'var(--danger)';
                                        const displayName = getMutatorDisplayName(name);
                                        
                                        return (
                                            <div key={name} className="mutator-stat-card">
                                                <div className="mutator-stat-header">
                                                    <span className="mutator-name" title={`Original: ${name}`}>
                                                        {displayName}
                                                    </span>
                                                    <span className="success-rate" style={{ color }}>
                                                        {successRate.toFixed(0)}%
                                                    </span>
                                                </div>
                                                <div className="mutator-stat-bar">
                                                    <div 
                                                        className="mutator-stat-fill" 
                                                        style={{ 
                                                            width: `${successRate}%`, 
                                                            background: color 
                                                        }}
                                                    />
                                                </div>
                                                <div className="mutator-stat-details">
                                                    {stats.successes}/{stats.attempts} attempts
                                                    {stats.attempts === 0 && (
                                                        <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', marginLeft: '0.5rem' }}>
                                                            (Not used yet)
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                    })}
                            </div>
                        </div>
                    )}

                    <div className="grid cols-2">
                        {/* Convergence Chart */}
                        <div className="card glass" style={{ height: '400px' }}>
                            <h3 style={{ marginBottom: '1.5rem', fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                <TrendingDown size={18} /> Convergence History
                            </h3>
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
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                                <h3 style={{ fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <Activity size={18} /> Pareto Frontier
                                </h3>
                                <div className="label-hint" style={{ fontSize: '0.7rem' }}>Click points to inspect</div>
                            </div>
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
                                    <Scatter
                                        name="Solutions"
                                        data={paretoData}
                                        onClick={(data) => handleParetoClick(data)}
                                        style={{ cursor: 'pointer' }}
                                    >
                                        {paretoData.map((entry, index) => (
                                            <Cell
                                                key={`cell-${index}`}
                                                fill={inspectedSolution?.variant_id === entry.variant_id ? 'var(--secondary)' : 'var(--primary)'}
                                                stroke={inspectedSolution?.variant_id === entry.variant_id ? '#fff' : 'none'}
                                                strokeWidth={2}
                                            />
                                        ))}
                                    </Scatter>
                                </ScatterChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    <div className="grid cols-2">
                        {/* Mutator Stats & Logs */}
                        <div className="card glass" style={{ height: '550px', display: 'flex', flexDirection: 'column' }}>
                            <div style={{ paddingBottom: '1rem', borderBottom: '1px solid var(--border)', marginBottom: '1rem' }}>
                                <h3 style={{ fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <Zap size={18} color="var(--primary)" /> Mutator Effectiveness
                                </h3>
                                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.75rem' }}>
                                    {Object.entries(mutatorStats).map(([name, stats]) => (
                                        <div key={name} className="status-badge" style={{
                                            display: 'flex',
                                            gap: '0.5rem',
                                            background: stats.successes > 0 ? 'rgba(0, 255, 157, 0.1)' : 'rgba(255, 255, 255, 0.05)',
                                            borderColor: stats.successes > 0 ? 'rgba(0, 255, 157, 0.3)' : 'var(--border)'
                                        }}>
                                            <span style={{ color: stats.successes > 0 ? 'var(--primary)' : 'var(--text-muted)' }}>{name}</span>
                                            <span style={{ fontWeight: 'bold' }}>{(stats.successes / (stats.attempts || 1) * 100).toFixed(0)}%</span>
                                        </div>
                                    ))}
                                    {Object.keys(mutatorStats).length === 0 && <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>No mutation data available yet...</span>}
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
                                {logs.length === 0 && <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>Waiting for evolution events...</div>}
                                {logs.map((log, i) => (
                                    <div key={i} className={`log-entry`} style={{
                                        borderLeft: `2px solid ${log.level === 'error' ? 'var(--danger)' :
                                            log.level === 'success' ? 'var(--success)' :
                                                log.level === 'system' ? 'var(--secondary)' : 'var(--text-muted)'
                                            }`,
                                        paddingLeft: '0.75rem',
                                        color: log.level === 'error' ? '#fca5a5' : 'inherit'
                                    }}>
                                        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginRight: '0.75rem', minWidth: '60px', display: 'inline-block' }}>
                                            [{log.timestamp}]
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
                            <div className="card glass" style={{ display: 'flex', flexDirection: 'column' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                                    <h3 style={{ fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        <Eye size={18} /> {inspectedSolution ? 'Inspecting Variant' : 'Current Best Evolution'}
                                    </h3>
                                    {inspectedSolution && (
                                        <button className="btn-small" onClick={() => setInspectedSolution(null)} style={{ color: 'var(--primary)', borderColor: 'var(--glass-border)' }}>
                                            Back to Best
                                        </button>
                                    )}
                                </div>

                                {displayedMetrics && (
                                    <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '1rem', padding: '0.75rem', background: 'rgba(0,0,0,0.2)', borderRadius: '8px' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem' }}>
                                            <Zap size={14} color="var(--primary)" /> {displayedMetrics.energy.toExponential(4)} J
                                        </div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem' }}>
                                            <Clock size={14} color="var(--secondary)" /> {(displayedMetrics.time * 1000).toFixed(2)} ms
                                        </div>
                                        {inspectedSolution && (
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                                                <Info size={14} /> {inspectedSolution.mutation}
                                            </div>
                                        )}
                                    </div>
                                )}

                                <div className="diff-container">
                                    <div className="diff-pane">
                                        <div className="diff-header">Original Code</div>
                                        <pre className="diff-code">
                                            {status.original_code}
                                        </pre>
                                    </div>
                                    <div className="diff-pane">
                                        <div className="diff-header" style={{ color: 'var(--primary)' }}>
                                            {inspectedSolution ? 'Selected Solution' : 'Optimized Code'}
                                        </div>
                                        <pre className="diff-code optimized">
                                            {displayedCode || 'Waiting for first improvement...'}
                                        </pre>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            ) : (
                <DeepAnalysis
                    mutatorStats={mutatorStats}
                    evaluationHistory={evaluationHistory}
                    paretoData={paretoData}
                    metricsHistory={metricsHistory}
                    originalCode={status.original_code}
                    bestCode={bestCode}
                    status={status}
                />
            )}
        </div>
    );
};

export default Dashboard;
