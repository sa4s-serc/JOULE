import React, { useState, useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend } from 'recharts';
import { TrendingUp, Target, Zap, Clock, Activity, AlertCircle } from 'lucide-react';
import EvolutionTree from './EvolutionTree';
import CodeProposalViewer from './CodeProposalViewer';

const DeepAnalysis = ({ 
    mutatorStats, 
    evaluationHistory, 
    paretoData, 
    metricsHistory,
    originalCode,
    bestCode,
    status
}) => {
    const [selectedNode, setSelectedNode] = useState(null);
    const [selectedProposal, setSelectedProposal] = useState(null);

    // Calculate advanced statistics
    const stats = useMemo(() => {
        const totalAttempts = Object.values(mutatorStats).reduce((sum, stat) => sum + stat.attempts, 0);
        const totalSuccesses = Object.values(mutatorStats).reduce((sum, stat) => sum + stat.successes, 0);
        const overallSuccessRate = totalAttempts > 0 ? (totalSuccesses / totalAttempts) * 100 : 0;

        // Mutator efficiency ranking
        const mutatorEfficiency = Object.entries(mutatorStats)
            .map(([name, stat]) => ({
                name,
                successRate: stat.attempts > 0 ? (stat.successes / stat.attempts) * 100 : 0,
                attempts: stat.attempts,
                successes: stat.successes
            }))
            .sort((a, b) => b.successRate - a.successRate);

        // Generation statistics
        const generationStats = evaluationHistory.reduce((acc, ev) => {
            const gen = ev.generation || 0;
            if (!acc[gen]) {
                acc[gen] = { generation: gen, total: 0, successful: 0, failed: 0 };
            }
            acc[gen].total++;
            if (ev.success) acc[gen].successful++;
            else acc[gen].failed++;
            return acc;
        }, {});

        const generationData = Object.values(generationStats).sort((a, b) => a.generation - b.generation);

        // Performance improvement over time
        const improvements = metricsHistory.map((m, idx) => {
            if (idx === 0) return { generation: m.generation, improvement: 0 };
            const prev = metricsHistory[idx - 1];
            const energyImprovement = ((prev.energy - m.energy) / prev.energy) * 100;
            return { generation: m.generation, improvement: energyImprovement };
        });

        // Radar chart data for mutator categories
        const radarData = mutatorEfficiency.slice(0, 6).map(m => ({
            mutator: m.name.length > 15 ? m.name.substring(0, 12) + '...' : m.name,
            performance: m.successRate,
            usage: (m.attempts / totalAttempts) * 100
        }));

        return {
            totalAttempts,
            totalSuccesses,
            overallSuccessRate,
            mutatorEfficiency,
            generationData,
            improvements,
            radarData
        };
    }, [mutatorStats, evaluationHistory, metricsHistory]);

    const handleNodeClick = (node) => {
        setSelectedNode(node);
        
        // Use the code from the node if available, otherwise search in evaluation history
        let codeToDisplay = node.code;
        let fullData = node.fullData;
        
        if (!codeToDisplay) {
            // Fallback: Find the full evaluation data
            fullData = evaluationHistory.find(ev => 
                (ev.variant_id && ev.variant_id === node.id) || 
                (ev.id && ev.id === node.id)
            );
            codeToDisplay = fullData?.code;
        }
        
        if (codeToDisplay) {
            setSelectedProposal({
                code: codeToDisplay,
                metadata: {
                    mutation: node.mutation || fullData?.mutation,
                    energy: node.metrics?.energy_joules || fullData?.metrics?.energy_joules,
                    time: node.metrics?.duration_seconds || fullData?.metrics?.duration_seconds,
                    generation: node.generation || fullData?.generation,
                    isParetoOptimal: node.isParetoOptimal,
                    success: node.success
                }
            });
        } else {
            // If no code available, show a message
            setSelectedProposal({
                code: '// Code not available for this variant\n// This may be a failed mutation or the code was not stored',
                metadata: {
                    mutation: node.mutation,
                    energy: node.metrics?.energy_joules,
                    time: node.metrics?.duration_seconds,
                    generation: node.generation,
                    isParetoOptimal: node.isParetoOptimal,
                    success: node.success
                }
            });
        }
    };

    const COLORS = ['#00ff9d', '#00b8ff', '#7d00ff', '#ffbf00', '#ff4d4d', '#5effc2'];

    return (
        <div className="deep-analysis-view">
            {/* Summary Cards */}
            <div className="grid cols-4" style={{ marginBottom: '2rem' }}>
                <div className="card glass">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                        <Target size={16} /> Overall Success Rate
                    </div>
                    <div style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--primary)' }}>
                        {stats.overallSuccessRate.toFixed(1)}%
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
                        {stats.totalSuccesses} / {stats.totalAttempts} attempts
                    </div>
                </div>

                <div className="card glass">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                        <Activity size={16} /> Active Mutators
                    </div>
                    <div style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--secondary)' }}>
                        {Object.keys(mutatorStats).length}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
                        {stats.mutatorEfficiency.filter(m => m.successes > 0).length} effective
                    </div>
                </div>

                <div className="card glass">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                        <TrendingUp size={16} /> Pareto Solutions
                    </div>
                    <div style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--accent)' }}>
                        {paretoData.length}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
                        Optimal variants found
                    </div>
                </div>

                <div className="card glass">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                        <AlertCircle size={16} /> Failure Rate
                    </div>
                    <div style={{ fontSize: '2rem', fontWeight: 'bold', color: 'var(--danger)' }}>
                        {(100 - stats.overallSuccessRate).toFixed(1)}%
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
                        {stats.totalAttempts - stats.totalSuccesses} failed attempts
                    </div>
                </div>
            </div>

            {/* Evolutionary Tree */}
            <div style={{ marginBottom: '2rem' }}>
                <EvolutionTree 
                    paretoData={paretoData}
                    evaluationHistory={evaluationHistory}
                    onNodeClick={handleNodeClick}
                />
            </div>

            {/* Code Proposal Viewer */}
            {selectedProposal && (
                <div style={{ marginBottom: '2rem' }}>
                    <CodeProposalViewer
                        originalCode={originalCode}
                        proposedCode={selectedProposal.code}
                        metadata={selectedProposal.metadata}
                    />
                </div>
            )}

            {/* Best Solution Viewer (if no proposal selected) */}
            {!selectedProposal && bestCode && (
                <div style={{ marginBottom: '2rem' }}>
                    <CodeProposalViewer
                        originalCode={originalCode}
                        proposedCode={bestCode}
                        metadata={{
                            mutation: 'Best Solution',
                            energy: status.best_metrics?.energy_joules,
                            time: status.best_metrics?.duration_seconds,
                            improvement: status.improvement
                        }}
                    />
                </div>
            )}

            {/* Advanced Analytics */}
            <div className="grid cols-2" style={{ marginBottom: '2rem' }}>
                {/* Mutator Performance Breakdown */}
                <div className="card glass" style={{ height: '400px' }}>
                    <h3 style={{ marginBottom: '1rem', fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <Zap size={18} /> Mutator Performance Breakdown
                    </h3>
                    <ResponsiveContainer width="100%" height="85%">
                        <BarChart data={stats.mutatorEfficiency.slice(0, 10)}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                            <XAxis 
                                dataKey="name" 
                                stroke="var(--text-muted)"
                                tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                                angle={-45}
                                textAnchor="end"
                                height={80}
                            />
                            <YAxis 
                                stroke="var(--text-muted)"
                                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                                label={{ value: 'Success Rate (%)', angle: -90, position: 'insideLeft', fill: 'var(--text-muted)' }}
                            />
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: 'rgba(13, 17, 26, 0.95)',
                                    border: '1px solid var(--border)',
                                    borderRadius: '8px'
                                }}
                            />
                            <Bar dataKey="successRate" fill="var(--primary)" radius={[8, 8, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                {/* Generation Success Distribution */}
                <div className="card glass" style={{ height: '400px' }}>
                    <h3 style={{ marginBottom: '1rem', fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <Activity size={18} /> Generation Success Distribution
                    </h3>
                    <ResponsiveContainer width="100%" height="85%">
                        <BarChart data={stats.generationData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                            <XAxis 
                                dataKey="generation" 
                                stroke="var(--text-muted)"
                                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                                label={{ value: 'Generation', position: 'insideBottom', offset: -5, fill: 'var(--text-muted)' }}
                            />
                            <YAxis 
                                stroke="var(--text-muted)"
                                tick={{ fill: 'var(--text-muted)', fontSize: 12 }}
                            />
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: 'rgba(13, 17, 26, 0.95)',
                                    border: '1px solid var(--border)',
                                    borderRadius: '8px'
                                }}
                            />
                            <Legend />
                            <Bar dataKey="successful" stackId="a" fill="var(--success)" name="Successful" radius={[8, 8, 0, 0]} />
                            <Bar dataKey="failed" stackId="a" fill="var(--danger)" name="Failed" radius={[8, 8, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            </div>

            {/* Mutator Radar & Improvement Trend */}
            <div className="grid cols-2">
                {/* Mutator Performance Radar */}
                {stats.radarData.length > 0 && (
                    <div className="card glass" style={{ height: '400px' }}>
                        <h3 style={{ marginBottom: '1rem', fontSize: '1.1rem', fontWeight: 600 }}>
                            Mutator Performance Radar
                        </h3>
                        <ResponsiveContainer width="100%" height="85%">
                            <RadarChart data={stats.radarData}>
                                <PolarGrid stroke="rgba(255,255,255,0.1)" />
                                <PolarAngleAxis 
                                    dataKey="mutator" 
                                    tick={{ fill: 'var(--text-muted)', fontSize: 11 }}
                                />
                                <PolarRadiusAxis 
                                    angle={90} 
                                    domain={[0, 100]}
                                    tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                                />
                                <Radar 
                                    name="Performance" 
                                    dataKey="performance" 
                                    stroke="var(--primary)" 
                                    fill="var(--primary)" 
                                    fillOpacity={0.3}
                                    strokeWidth={2}
                                />
                                <Radar 
                                    name="Usage" 
                                    dataKey="usage" 
                                    stroke="var(--secondary)" 
                                    fill="var(--secondary)" 
                                    fillOpacity={0.2}
                                    strokeWidth={2}
                                />
                                <Legend />
                                <Tooltip
                                    contentStyle={{
                                        backgroundColor: 'rgba(13, 17, 26, 0.95)',
                                        border: '1px solid var(--border)',
                                        borderRadius: '8px'
                                    }}
                                />
                            </RadarChart>
                        </ResponsiveContainer>
                    </div>
                )}

                {/* Detailed Mutator Table */}
                <div className="card glass" style={{ height: '400px', display: 'flex', flexDirection: 'column' }}>
                    <h3 style={{ marginBottom: '1rem', fontSize: '1.1rem', fontWeight: 600 }}>
                        Detailed Mutator Statistics
                    </h3>
                    <div style={{ flex: 1, overflow: 'auto' }}>
                        <table style={{ width: '100%', fontSize: '0.85rem', borderCollapse: 'collapse' }}>
                            <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-card)', zIndex: 1 }}>
                                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                    <th style={{ padding: '0.75rem', textAlign: 'left', color: 'var(--text-muted)' }}>Mutator</th>
                                    <th style={{ padding: '0.75rem', textAlign: 'center', color: 'var(--text-muted)' }}>Attempts</th>
                                    <th style={{ padding: '0.75rem', textAlign: 'center', color: 'var(--text-muted)' }}>Success</th>
                                    <th style={{ padding: '0.75rem', textAlign: 'center', color: 'var(--text-muted)' }}>Rate</th>
                                </tr>
                            </thead>
                            <tbody>
                                {stats.mutatorEfficiency.map((m, idx) => (
                                    <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                                        <td style={{ padding: '0.75rem', color: 'var(--text-main)' }}>{m.name}</td>
                                        <td style={{ padding: '0.75rem', textAlign: 'center', color: 'var(--text-muted)' }}>{m.attempts}</td>
                                        <td style={{ padding: '0.75rem', textAlign: 'center', color: m.successes > 0 ? 'var(--success)' : 'var(--text-muted)' }}>
                                            {m.successes}
                                        </td>
                                        <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                                            <span style={{ 
                                                color: m.successRate > 50 ? 'var(--success)' : m.successRate > 20 ? 'var(--warning)' : 'var(--danger)',
                                                fontWeight: 'bold'
                                            }}>
                                                {m.successRate.toFixed(1)}%
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default DeepAnalysis;
