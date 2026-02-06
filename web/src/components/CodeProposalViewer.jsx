import React, { useState, useMemo } from 'react';
import { Code, Copy, Check, Download, Eye, EyeOff, BarChart3, TrendingDown } from 'lucide-react';
import { diffLines } from 'diff';

const CodeProposalViewer = ({ originalCode, proposedCode, metadata }) => {
    const [viewMode, setViewMode] = useState('split'); // 'split', 'unified', 'diff'
    const [copied, setCopied] = useState(false);
    const [showLineNumbers, setShowLineNumbers] = useState(true);
    const [showMetrics, setShowMetrics] = useState(true);

    // Calculate diff
    const diff = useMemo(() => {
        if (!originalCode || !proposedCode) return [];
        return diffLines(originalCode, proposedCode);
    }, [originalCode, proposedCode]);

    // Calculate code metrics
    const codeMetrics = useMemo(() => {
        const calculateMetrics = (code) => {
            if (!code) return null;
            
            const lines = code.split('\n');
            const nonEmptyLines = lines.filter(line => line.trim().length > 0);
            const codeLines = nonEmptyLines.filter(line => {
                const trimmed = line.trim();
                return !trimmed.startsWith('#') && !trimmed.startsWith('"""') && !trimmed.startsWith("'''");
            });
            
            // Count functions
            const functionCount = (code.match(/\bdef\s+\w+/g) || []).length;
            
            // Count loops
            const loopCount = (code.match(/\b(for|while)\s+/g) || []).length;
            
            // Count conditionals
            const conditionalCount = (code.match(/\bif\s+/g) || []).length;
            
            // Estimate cyclomatic complexity (simplified)
            const cyclomaticComplexity = 1 + conditionalCount + loopCount + 
                (code.match(/\belif\s+/g) || []).length +
                (code.match(/\bexcept\s+/g) || []).length;
            
            // Count imports
            const importCount = (code.match(/^(import|from)\s+/gm) || []).length;
            
            // Calculate average line length
            const avgLineLength = codeLines.length > 0 
                ? Math.round(codeLines.reduce((sum, line) => sum + line.length, 0) / codeLines.length)
                : 0;
            
            // Estimate nesting depth
            const maxNesting = Math.max(...lines.map(line => {
                const match = line.match(/^(\s*)/);
                return match ? Math.floor(match[1].length / 4) : 0;
            }));
            
            return {
                totalLines: lines.length,
                codeLines: codeLines.length,
                emptyLines: lines.length - nonEmptyLines.length,
                functionCount,
                loopCount,
                conditionalCount,
                cyclomaticComplexity,
                importCount,
                avgLineLength,
                maxNesting
            };
        };

        return {
            original: calculateMetrics(originalCode),
            proposed: calculateMetrics(proposedCode)
        };
    }, [originalCode, proposedCode]);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(proposedCode);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error('Failed to copy:', err);
        }
    };

    const handleDownload = () => {
        const blob = new Blob([proposedCode], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `optimized_${Date.now()}.py`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const renderLineNumbers = (lines) => {
        return lines.map((_, idx) => (
            <div key={idx} style={{ 
                textAlign: 'right', 
                paddingRight: '0.5rem',
                color: 'var(--text-dim)',
                userSelect: 'none',
                minWidth: '2.5rem'
            }}>
                {idx + 1}
            </div>
        ));
    };

    const renderSplitView = () => {
        const originalLines = originalCode?.split('\n') || [];
        const proposedLines = proposedCode?.split('\n') || [];

        return (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', height: '100%' }}>
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <div style={{ 
                        fontSize: '0.75rem', 
                        textTransform: 'uppercase', 
                        color: 'var(--text-muted)', 
                        marginBottom: '0.5rem',
                        fontWeight: 'bold'
                    }}>
                        Original Code
                    </div>
                    <div style={{ 
                        flex: 1,
                        background: '#050505', 
                        border: '1px solid var(--border)', 
                        borderRadius: '8px',
                        overflow: 'auto',
                        display: 'flex'
                    }}>
                        {showLineNumbers && (
                            <div style={{ 
                                background: 'rgba(0, 0, 0, 0.3)',
                                padding: '1rem 0.5rem',
                                borderRight: '1px solid var(--border)'
                            }}>
                                {renderLineNumbers(originalLines)}
                            </div>
                        )}
                        <pre style={{ 
                            flex: 1,
                            margin: 0,
                            padding: '1rem',
                            fontFamily: 'Fira Code, monospace',
                            fontSize: '0.8rem',
                            lineHeight: '1.5',
                            color: 'var(--text-code)',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                            overflowWrap: 'break-word'
                        }}>
                            {originalCode}
                        </pre>
                    </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <div style={{ 
                        fontSize: '0.75rem', 
                        textTransform: 'uppercase', 
                        color: 'var(--primary)', 
                        marginBottom: '0.5rem',
                        fontWeight: 'bold'
                    }}>
                        Proposed Code
                    </div>
                    <div style={{ 
                        flex: 1,
                        background: '#050505', 
                        border: '1px solid var(--primary)', 
                        borderRadius: '8px',
                        overflow: 'auto',
                        boxShadow: '0 0 20px rgba(0, 255, 157, 0.1)',
                        display: 'flex'
                    }}>
                        {showLineNumbers && (
                            <div style={{ 
                                background: 'rgba(0, 0, 0, 0.3)',
                                padding: '1rem 0.5rem',
                                borderRight: '1px solid var(--border)'
                            }}>
                                {renderLineNumbers(proposedLines)}
                            </div>
                        )}
                        <pre style={{ 
                            flex: 1,
                            margin: 0,
                            padding: '1rem',
                            fontFamily: 'Fira Code, monospace',
                            fontSize: '0.8rem',
                            lineHeight: '1.5',
                            color: 'var(--text-code)',
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                            overflowWrap: 'break-word'
                        }}>
                            {proposedCode}
                        </pre>
                    </div>
                </div>
            </div>
        );
    };

    const renderDiffView = () => {
        return (
            <div style={{ 
                background: '#050505', 
                border: '1px solid var(--border)', 
                borderRadius: '8px',
                overflow: 'auto',
                padding: '1rem',
                fontFamily: 'Fira Code, monospace',
                fontSize: '0.8rem',
                lineHeight: '1.5'
            }}>
                {diff.map((part, idx) => {
                    const bgColor = part.added ? 'rgba(0, 255, 157, 0.1)' : 
                                   part.removed ? 'rgba(255, 77, 77, 0.1)' : 
                                   'transparent';
                    const borderColor = part.added ? 'var(--primary)' : 
                                       part.removed ? 'var(--danger)' : 
                                       'transparent';
                    const prefix = part.added ? '+ ' : part.removed ? '- ' : '  ';
                    
                    return (
                        <div 
                            key={idx}
                            style={{ 
                                background: bgColor,
                                borderLeft: `3px solid ${borderColor}`,
                                paddingLeft: '0.5rem',
                                marginBottom: '2px'
                            }}
                        >
                            {part.value.split('\n').map((line, lineIdx) => (
                                line && <div key={lineIdx}>{prefix}{line}</div>
                            ))}
                        </div>
                    );
                })}
            </div>
        );
    };

    const renderUnifiedView = () => {
        return (
            <div style={{ 
                background: '#050505', 
                border: '1px solid var(--primary)', 
                borderRadius: '8px',
                overflow: 'auto',
                display: 'flex',
                boxShadow: '0 0 20px rgba(0, 255, 157, 0.1)'
            }}>
                {showLineNumbers && (
                    <div style={{ 
                        background: 'rgba(0, 0, 0, 0.3)',
                        padding: '1rem 0.5rem',
                        borderRight: '1px solid var(--border)'
                    }}>
                        {renderLineNumbers(proposedCode?.split('\n') || [])}
                    </div>
                )}
                <pre style={{ 
                    flex: 1,
                    margin: 0,
                    padding: '1rem',
                    fontFamily: 'Fira Code, monospace',
                    fontSize: '0.8rem',
                    lineHeight: '1.5',
                    color: 'var(--text-code)'
                }}>
                    {proposedCode}
                </pre>
            </div>
        );
    };

    return (
        <div className="card glass" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center', 
                marginBottom: '1rem',
                flexWrap: 'wrap',
                gap: '1rem'
            }}>
                <h3 style={{ 
                    fontSize: '1.1rem', 
                    fontWeight: 600, 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '0.5rem' 
                }}>
                    <Code size={18} /> Code Proposal
                </h3>

                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                    <div style={{ display: 'flex', gap: '0.25rem', background: 'var(--glass)', borderRadius: '6px', padding: '0.25rem' }}>
                        <button
                            className="btn-small"
                            onClick={() => setViewMode('split')}
                            style={{
                                background: viewMode === 'split' ? 'var(--primary)' : 'transparent',
                                color: viewMode === 'split' ? '#000' : 'var(--text-muted)',
                                border: 'none'
                            }}
                        >
                            Split
                        </button>
                        <button
                            className="btn-small"
                            onClick={() => setViewMode('unified')}
                            style={{
                                background: viewMode === 'unified' ? 'var(--primary)' : 'transparent',
                                color: viewMode === 'unified' ? '#000' : 'var(--text-muted)',
                                border: 'none'
                            }}
                        >
                            Unified
                        </button>
                        <button
                            className="btn-small"
                            onClick={() => setViewMode('diff')}
                            style={{
                                background: viewMode === 'diff' ? 'var(--primary)' : 'transparent',
                                color: viewMode === 'diff' ? '#000' : 'var(--text-muted)',
                                border: 'none'
                            }}
                        >
                            Diff
                        </button>
                    </div>

                    <button
                        className="btn-small"
                        onClick={() => setShowLineNumbers(!showLineNumbers)}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                    >
                        {showLineNumbers ? <EyeOff size={14} /> : <Eye size={14} />}
                        Lines
                    </button>

                    <button
                        className="btn-small"
                        onClick={() => setShowMetrics(!showMetrics)}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                    >
                        <BarChart3 size={14} />
                        Metrics
                    </button>

                    <button
                        className="btn-small"
                        onClick={handleCopy}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                    >
                        {copied ? <Check size={14} /> : <Copy size={14} />}
                        {copied ? 'Copied!' : 'Copy'}
                    </button>

                    <button
                        className="btn-small"
                        onClick={handleDownload}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
                    >
                        <Download size={14} />
                        Download
                    </button>
                </div>
            </div>

            {metadata && (
                <div style={{ 
                    display: 'flex', 
                    gap: '1rem', 
                    marginBottom: '1rem', 
                    padding: '0.75rem', 
                    background: 'rgba(0,0,0,0.2)', 
                    borderRadius: '8px',
                    fontSize: '0.8rem',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                    overflow: 'hidden'
                }}>
                    {metadata.isParetoOptimal && (
                        <div style={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            gap: '0.5rem',
                            padding: '0.4rem 0.8rem',
                            background: 'rgba(0, 255, 157, 0.15)',
                            borderRadius: '6px',
                            border: '1px solid rgba(0, 255, 157, 0.3)',
                            flexShrink: 0
                        }}>
                            <span style={{ fontSize: '1rem' }}>★</span>
                            <span style={{ color: '#00ff9d', fontWeight: 'bold', whiteSpace: 'nowrap' }}>PARETO OPTIMAL</span>
                        </div>
                    )}
                    {metadata.success !== undefined && (
                        <div style={{ 
                            display: 'flex', 
                            alignItems: 'center', 
                            gap: '0.5rem',
                            padding: '0.4rem 0.8rem',
                            background: metadata.success ? 'rgba(0, 255, 157, 0.1)' : 'rgba(255, 77, 77, 0.1)',
                            borderRadius: '6px',
                            border: `1px solid ${metadata.success ? 'rgba(0, 255, 157, 0.2)' : 'rgba(255, 77, 77, 0.2)'}`,
                            flexShrink: 0
                        }}>
                            <span style={{ color: metadata.success ? 'var(--success)' : 'var(--danger)', fontWeight: 'bold', whiteSpace: 'nowrap' }}>
                                {metadata.success ? '✓ Valid' : '✗ Failed'}
                            </span>
                        </div>
                    )}
                    {metadata.generation !== undefined && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                            <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>Generation:</span>
                            <span style={{ color: 'var(--text-main)', fontWeight: 'bold' }}>{metadata.generation}</span>
                        </div>
                    )}
                    {metadata.mutation && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0, maxWidth: '300px' }}>
                            <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>Mutation:</span>
                            <span style={{ 
                                color: 'var(--primary)', 
                                fontWeight: 'bold',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap'
                            }} title={metadata.mutation}>
                                {metadata.mutation}
                            </span>
                        </div>
                    )}
                    {metadata.energy && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                            <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>Energy:</span>
                            <span style={{ color: 'var(--primary)', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                                {metadata.energy.toExponential(4)} J
                            </span>
                        </div>
                    )}
                    {metadata.time && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                            <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>Time:</span>
                            <span style={{ color: 'var(--secondary)', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                                {(metadata.time * 1000).toFixed(2)} ms
                            </span>
                        </div>
                    )}
                    {metadata.improvement !== undefined && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', minWidth: 0 }}>
                            <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>Improvement:</span>
                            <span style={{ color: 'var(--success)', whiteSpace: 'nowrap' }}>
                                {metadata.improvement > 0 ? '↓' : '↑'} {Math.abs(metadata.improvement * 100).toFixed(1)}%
                            </span>
                        </div>
                    )}
                </div>
            )}

            {/* Code Metrics Comparison */}
            {showMetrics && codeMetrics.original && codeMetrics.proposed && (
                <div style={{ 
                    marginBottom: '1rem',
                    padding: '1rem',
                    background: 'rgba(0,0,0,0.2)',
                    borderRadius: '8px',
                    border: '1px solid var(--border)'
                }}>
                    <div style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '0.5rem', 
                        marginBottom: '1rem',
                        fontSize: '0.9rem',
                        fontWeight: 'bold'
                    }}>
                        <BarChart3 size={16} />
                        Code Metrics Comparison
                    </div>
                    
                    <div style={{ 
                        display: 'grid', 
                        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                        gap: '1rem'
                    }}>
                        {/* Lines of Code */}
                        <div style={{ 
                            padding: '0.75rem', 
                            background: 'rgba(0,0,0,0.3)', 
                            borderRadius: '6px',
                            border: '1px solid rgba(255,255,255,0.05)'
                        }}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                                Lines of Code
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Original</div>
                                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{codeMetrics.original.codeLines}</div>
                                </div>
                                <TrendingDown size={16} style={{ 
                                    color: codeMetrics.proposed.codeLines < codeMetrics.original.codeLines ? 'var(--success)' : 'var(--text-muted)' 
                                }} />
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Proposed</div>
                                    <div style={{ 
                                        fontSize: '1.2rem', 
                                        fontWeight: 'bold',
                                        color: codeMetrics.proposed.codeLines < codeMetrics.original.codeLines ? 'var(--success)' : 'var(--text-main)'
                                    }}>
                                        {codeMetrics.proposed.codeLines}
                                    </div>
                                </div>
                            </div>
                            {codeMetrics.proposed.codeLines !== codeMetrics.original.codeLines && (
                                <div style={{ 
                                    marginTop: '0.5rem', 
                                    fontSize: '0.7rem',
                                    color: codeMetrics.proposed.codeLines < codeMetrics.original.codeLines ? 'var(--success)' : 'var(--warning)'
                                }}>
                                    {codeMetrics.proposed.codeLines < codeMetrics.original.codeLines ? '↓' : '↑'} 
                                    {' '}{Math.abs(codeMetrics.proposed.codeLines - codeMetrics.original.codeLines)} lines
                                </div>
                            )}
                        </div>

                        {/* Cyclomatic Complexity */}
                        <div style={{ 
                            padding: '0.75rem', 
                            background: 'rgba(0,0,0,0.3)', 
                            borderRadius: '6px',
                            border: '1px solid rgba(255,255,255,0.05)'
                        }}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                                Cyclomatic Complexity
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Original</div>
                                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{codeMetrics.original.cyclomaticComplexity}</div>
                                </div>
                                <TrendingDown size={16} style={{ 
                                    color: codeMetrics.proposed.cyclomaticComplexity < codeMetrics.original.cyclomaticComplexity ? 'var(--success)' : 'var(--text-muted)' 
                                }} />
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Proposed</div>
                                    <div style={{ 
                                        fontSize: '1.2rem', 
                                        fontWeight: 'bold',
                                        color: codeMetrics.proposed.cyclomaticComplexity < codeMetrics.original.cyclomaticComplexity ? 'var(--success)' : 'var(--text-main)'
                                    }}>
                                        {codeMetrics.proposed.cyclomaticComplexity}
                                    </div>
                                </div>
                            </div>
                            {codeMetrics.proposed.cyclomaticComplexity !== codeMetrics.original.cyclomaticComplexity && (
                                <div style={{ 
                                    marginTop: '0.5rem', 
                                    fontSize: '0.7rem',
                                    color: codeMetrics.proposed.cyclomaticComplexity < codeMetrics.original.cyclomaticComplexity ? 'var(--success)' : 'var(--warning)'
                                }}>
                                    {codeMetrics.proposed.cyclomaticComplexity < codeMetrics.original.cyclomaticComplexity ? '↓' : '↑'} 
                                    {' '}{Math.abs(codeMetrics.proposed.cyclomaticComplexity - codeMetrics.original.cyclomaticComplexity)}
                                </div>
                            )}
                        </div>

                        {/* Functions */}
                        <div style={{ 
                            padding: '0.75rem', 
                            background: 'rgba(0,0,0,0.3)', 
                            borderRadius: '6px',
                            border: '1px solid rgba(255,255,255,0.05)'
                        }}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                                Functions
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Original</div>
                                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{codeMetrics.original.functionCount}</div>
                                </div>
                                <div style={{ fontSize: '1.5rem', color: 'var(--text-dim)' }}>→</div>
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Proposed</div>
                                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{codeMetrics.proposed.functionCount}</div>
                                </div>
                            </div>
                        </div>

                        {/* Loops */}
                        <div style={{ 
                            padding: '0.75rem', 
                            background: 'rgba(0,0,0,0.3)', 
                            borderRadius: '6px',
                            border: '1px solid rgba(255,255,255,0.05)'
                        }}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                                Loops
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Original</div>
                                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{codeMetrics.original.loopCount}</div>
                                </div>
                                <TrendingDown size={16} style={{ 
                                    color: codeMetrics.proposed.loopCount < codeMetrics.original.loopCount ? 'var(--success)' : 'var(--text-muted)' 
                                }} />
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Proposed</div>
                                    <div style={{ 
                                        fontSize: '1.2rem', 
                                        fontWeight: 'bold',
                                        color: codeMetrics.proposed.loopCount < codeMetrics.original.loopCount ? 'var(--success)' : 'var(--text-main)'
                                    }}>
                                        {codeMetrics.proposed.loopCount}
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Conditionals */}
                        <div style={{ 
                            padding: '0.75rem', 
                            background: 'rgba(0,0,0,0.3)', 
                            borderRadius: '6px',
                            border: '1px solid rgba(255,255,255,0.05)'
                        }}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                                Conditionals
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Original</div>
                                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{codeMetrics.original.conditionalCount}</div>
                                </div>
                                <TrendingDown size={16} style={{ 
                                    color: codeMetrics.proposed.conditionalCount < codeMetrics.original.conditionalCount ? 'var(--success)' : 'var(--text-muted)' 
                                }} />
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Proposed</div>
                                    <div style={{ 
                                        fontSize: '1.2rem', 
                                        fontWeight: 'bold',
                                        color: codeMetrics.proposed.conditionalCount < codeMetrics.original.conditionalCount ? 'var(--success)' : 'var(--text-main)'
                                    }}>
                                        {codeMetrics.proposed.conditionalCount}
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Max Nesting Depth */}
                        <div style={{ 
                            padding: '0.75rem', 
                            background: 'rgba(0,0,0,0.3)', 
                            borderRadius: '6px',
                            border: '1px solid rgba(255,255,255,0.05)'
                        }}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                                Max Nesting Depth
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Original</div>
                                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>{codeMetrics.original.maxNesting}</div>
                                </div>
                                <TrendingDown size={16} style={{ 
                                    color: codeMetrics.proposed.maxNesting < codeMetrics.original.maxNesting ? 'var(--success)' : 'var(--text-muted)' 
                                }} />
                                <div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Proposed</div>
                                    <div style={{ 
                                        fontSize: '1.2rem', 
                                        fontWeight: 'bold',
                                        color: codeMetrics.proposed.maxNesting < codeMetrics.original.maxNesting ? 'var(--success)' : 'var(--text-main)'
                                    }}>
                                        {codeMetrics.proposed.maxNesting}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <div style={{ flex: 1, minHeight: 0 }}>
                {viewMode === 'split' && renderSplitView()}
                {viewMode === 'unified' && renderUnifiedView()}
                {viewMode === 'diff' && renderDiffView()}
            </div>
        </div>
    );
};

export default CodeProposalViewer;
