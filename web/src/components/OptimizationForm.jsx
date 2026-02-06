import React, { useState, useEffect } from 'react';
import { Play, Code, FileCode, Sliders, Dna, ChevronDown, ChevronUp, Cpu, Sparkles, AlertCircle, Wifi, WifiOff } from 'lucide-react';
import { config } from '../config';
import { startOptimization, testConnection } from '../utils/api';
import { validatePythonCode, validateTestCode, validateOptimizationConfig, validateAllowedImports } from '../utils/validation';

const TEMPLATES = {
    fib: {
        name: 'Fibonacci',
        target: 'def fib(n):\n    if n <= 1: return n\n    return fib(n-1) + fib(n-2)\n',
        test: 'def test_fib():\n    assert fib(10) == 55\n'
    },
    matrix: {
        name: 'Matrix Multiply',
        target: 'def matmul(A, B):\n    C = [[0 for _ in range(len(B[0]))] for _ in range(len(A))]\n    for i in range(len(A)):\n        for j in range(len(B[0])):\n            for k in range(len(B)):\n                C[i][j] += A[i][k] * B[k][j]\n    return C\n',
        test: 'def test_matmul():\n    A = [[1, 2], [3, 4]]\n    B = [[5, 6], [7, 8]]\n    assert matmul(A, B) == [[19, 22], [43, 50]]\n'
    },
    search: {
        name: 'Binary Search',
        target: 'def search(arr, x):\n    l, r = 0, len(arr) - 1\n    while l <= r:\n        mid = (l + r) // 2\n        if arr[mid] < x:\n            l = mid + 1\n        elif arr[mid] > x:\n            r = mid - 1\n        else:\n            return mid\n    return -1\n',
        test: 'def test_search():\n    assert search([1, 2, 3, 4, 5], 3) == 2\n'
    }
};

const LEVEL_DESCS = {
    micro: 'Basic peephole and micro-optimizations (loops, constants). Safe for all code.',
    standard: 'Algorithmic improvements and common performance patterns. Recommended balance.',
    advanced: 'LLM-powered semantic optimization and advanced algorithmic rewriting. Maximizes gains.'
};

const OptimizationForm = ({ onStart, onError }) => {
    const [targetCode, setTargetCode] = useState(TEMPLATES.fib.target);
    const [testCode, setTestCode] = useState(TEMPLATES.fib.test);
    const [config, setConfig] = useState({
        generations: 10,
        population_size: 10,
        level: 'standard'
    });
    const [llmSettings, setLlmSettings] = useState({
        provider: 'gemini',
        model: 'gemini-2.5-flash'
    });
    const [mutatorLayers, setMutatorLayers] = useState({
        micro: true,
        algorithmic: true,
        syntactic: true,
        semantic: true
    });
    const [allowedImports, setAllowedImports] = useState('');
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [loading, setLoading] = useState(false);
    const [activeTemplate, setActiveTemplate] = useState('fib');
    const [validationErrors, setValidationErrors] = useState([]);
    const [connectionStatus, setConnectionStatus] = useState({ connected: null, message: '' });

    // Test API connection on component mount
    useEffect(() => {
        const checkConnection = async () => {
            const status = await testConnection();
            setConnectionStatus(status);
        };
        checkConnection();
    }, []);

    const loadTemplate = (key) => {
        setTargetCode(TEMPLATES[key].target);
        setTestCode(TEMPLATES[key].test);
        setActiveTemplate(key);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setValidationErrors([]);
        
        try {
            // Validate inputs
            const targetValidation = validatePythonCode(targetCode);
            const testValidation = validateTestCode(testCode);
            const configValidation = validateOptimizationConfig(config);
            const importsValidation = validateAllowedImports(allowedImports);
            
            const allErrors = [
                ...targetValidation.errors.map(e => `Target code: ${e}`),
                ...testValidation.errors.map(e => `Test code: ${e}`),
                ...configValidation.errors.map(e => `Configuration: ${e}`),
                ...importsValidation.errors.map(e => `Imports: ${e}`)
            ];
            
            if (allErrors.length > 0) {
                setValidationErrors(allErrors);
                return;
            }
            
            const payload = {
                target_code: targetCode,
                test_code: testCode,
                generations: config.generations,
                population_size: config.population_size,
                level: config.level,
                llm: llmSettings,
                mutators: {
                    layers: Object.keys(mutatorLayers).filter(l => mutatorLayers[l])
                },
                allowed_imports: allowedImports.split(',').map(i => i.trim()).filter(i => i)
            };
            const response = await startOptimization(payload);
            onStart({ ...response.data, original_code: targetCode });
        } catch (err) {
            const errorMessage = err.response?.data?.detail || err.message || 'Unknown error occurred';
            console.error('Optimization request failed:', err);
            onError(errorMessage);
        } finally {
            setLoading(false);
        }
    };

    const toggleLayer = (layer) => {
        setMutatorLayers(prev => ({ ...prev, [layer]: !prev[layer] }));
    };

    return (
        <div className="card glass">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', borderBottom: '1px solid var(--border)', paddingBottom: '1rem' }}>
                <hgroup>
                    <h2 style={{ color: 'var(--text-main)', margin: 0, fontSize: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <Dna size={24} color="var(--primary)" /> New Optimization Task
                        {connectionStatus.connected !== null && (
                            <span style={{ 
                                display: 'flex', 
                                alignItems: 'center', 
                                gap: '0.3rem', 
                                fontSize: '0.8rem',
                                color: connectionStatus.connected ? 'var(--success)' : 'var(--danger)',
                                marginLeft: '1rem'
                            }}>
                                {connectionStatus.connected ? <Wifi size={16} /> : <WifiOff size={16} />}
                                {connectionStatus.connected ? 'API Connected' : 'API Disconnected'}
                            </span>
                        )}
                    </h2>
                    <p style={{ margin: '0.4rem 0 0 2rem', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
                        Configure parameters and input code to evolve
                        {!connectionStatus.connected && connectionStatus.message && (
                            <span style={{ color: 'var(--danger)', display: 'block', marginTop: '0.2rem' }}>
                                {connectionStatus.message}
                            </span>
                        )}
                    </p>
                </hgroup>
                <div style={{ display: 'flex', gap: '0.5rem', background: 'rgba(0,0,0,0.2)', padding: '0.3rem', borderRadius: '8px' }}>
                    {Object.keys(TEMPLATES).map(key => (
                        <button
                            key={key}
                            onClick={() => loadTemplate(key)}
                            type="button"
                            className="btn-small"
                            style={{
                                background: activeTemplate === key ? 'var(--glass-hover)' : 'transparent',
                                color: activeTemplate === key ? 'var(--primary)' : 'var(--text-muted)',
                                border: 'none'
                            }}
                        >
                            {TEMPLATES[key].name}
                        </button>
                    ))}
                </div>
            </div>

            <form onSubmit={handleSubmit}>
                <div className="grid cols-2">
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <Code size={16} color="var(--primary)" /> Target Code <span className="label-hint">(Code to be optimized)</span>
                        </label>
                        <textarea
                            value={targetCode}
                            onChange={(e) => setTargetCode(e.target.value)}
                            rows={15}
                            className="code-editor"
                            spellCheck="false"
                        />
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <FileCode size={16} color="var(--secondary)" /> Test Code <span className="label-hint">(Validation harness)</span>
                        </label>
                        <textarea
                            value={testCode}
                            onChange={(e) => setTestCode(e.target.value)}
                            rows={15}
                            className="code-editor"
                            spellCheck="false"
                        />
                    </div>
                </div>

                <div style={{ marginTop: '2rem' }}>
                    <div className="advanced-config-toggle" onClick={() => setShowAdvanced(!showAdvanced)}>
                        {showAdvanced ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                        Advanced Configuration
                    </div>

                    {showAdvanced && (
                        <div className="advanced-config-panel">
                            <div className="grid cols-2" style={{ gap: '2rem' }}>
                                <div className="config-group" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                                        <Sparkles size={16} /> <span style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase' }}>LLM Settings</span>
                                    </div>
                                    <div className="grid cols-2" style={{ gap: '1rem', width: '100%' }}>
                                        <div className="input-field">
                                            <label>Provider</label>
                                            <select
                                                value={llmSettings.provider}
                                                onChange={(e) => setLlmSettings({ ...llmSettings, provider: e.target.value })}
                                            >
                                                <option value="gemini">Gemini</option>
                                                <option value="openai">OpenAI</option>
                                            </select>
                                        </div>
                                        <div className="input-field">
                                            <label>Model</label>
                                            <input
                                                type="text"
                                                value={llmSettings.model}
                                                onChange={(e) => setLlmSettings({ ...llmSettings, model: e.target.value })}
                                            />
                                        </div>
                                    </div>
                                </div>

                                <div className="config-group" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                                        <Code size={16} /> <span style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase' }}>Allowed Imports</span>
                                    </div>
                                    <div className="input-field" style={{ width: '100%' }}>
                                        <label>Module names (comma-separated)</label>
                                        <input
                                            type="text"
                                            placeholder="numpy, pandas, torch..."
                                            value={allowedImports}
                                            onChange={(e) => setAllowedImports(e.target.value)}
                                        />
                                        <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>
                                            Standard library imports are always allowed.
                                        </p>
                                    </div>
                                </div>

                                <div className="config-group" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
                                        <Cpu size={16} /> <span style={{ fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase' }}>Mutator Layers</span>
                                    </div>
                                    <div className="mutator-layers-grid">
                                        {Object.entries({
                                            semantic: {
                                                name: 'Semantic',
                                                description: 'LLM-powered algorithmic transformations and intent optimization',
                                                strategies: ['Algorithm Intent', 'Program Intent', 'Semantic Patterns'],
                                                color: '#ff6b6b'
                                            },
                                            algorithmic: {
                                                name: 'Algorithmic', 
                                                description: 'Data structure optimization and complexity improvements',
                                                strategies: ['Data Structure Optimizer', 'Complexity Reducer', 'Algorithm Selector'],
                                                color: '#4ecdc4'
                                            },
                                            syntactic: {
                                                name: 'Syntactic',
                                                description: 'Pythonic idioms and code pattern improvements',
                                                strategies: ['Pythonic Idioms', 'Code Patterns', 'Style Optimizer'],
                                                color: '#45b7d1'
                                            },
                                            micro: {
                                                name: 'Micro',
                                                description: 'Low-level optimizations like loop unrolling and constant folding',
                                                strategies: ['Constant Optimizer', 'Dead Code Eliminator', 'Loop Micro Optimizer'],
                                                color: '#96ceb4'
                                            }
                                        }).map(([layer, info]) => (
                                            <div key={layer} className="mutator-layer-card" style={{
                                                border: `1px solid ${mutatorLayers[layer] ? info.color : 'var(--border)'}`,
                                                background: mutatorLayers[layer] ? `${info.color}15` : 'transparent'
                                            }}>
                                                <label className="mutator-layer-header">
                                                    <input
                                                        type="checkbox"
                                                        checked={mutatorLayers[layer]}
                                                        onChange={() => toggleLayer(layer)}
                                                        style={{ accentColor: info.color }}
                                                    />
                                                    <div>
                                                        <span style={{ 
                                                            fontWeight: 600, 
                                                            color: mutatorLayers[layer] ? info.color : 'var(--text-main)',
                                                            fontSize: '0.9rem'
                                                        }}>
                                                            {info.name}
                                                        </span>
                                                        <p style={{ 
                                                            fontSize: '0.75rem', 
                                                            color: 'var(--text-muted)', 
                                                            margin: '0.2rem 0 0.5rem 0',
                                                            lineHeight: 1.3
                                                        }}>
                                                            {info.description}
                                                        </p>
                                                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.3rem' }}>
                                                            {info.strategies.map(strategy => (
                                                                <span key={strategy} style={{
                                                                    fontSize: '0.65rem',
                                                                    padding: '0.2rem 0.4rem',
                                                                    background: mutatorLayers[layer] ? `${info.color}25` : 'var(--glass)',
                                                                    color: mutatorLayers[layer] ? info.color : 'var(--text-muted)',
                                                                    borderRadius: '4px',
                                                                    border: `1px solid ${mutatorLayers[layer] ? info.color : 'var(--border)'}`
                                                                }}>
                                                                    {strategy}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    </div>
                                                </label>
                                            </div>
                                        ))}
                                    </div>
                                    <div style={{ 
                                        marginTop: '1rem', 
                                        padding: '0.8rem', 
                                        background: 'var(--glass)', 
                                        borderRadius: '6px',
                                        fontSize: '0.75rem',
                                        color: 'var(--text-muted)',
                                        lineHeight: 1.4
                                    }}>
                                        <strong>Layer Processing Order:</strong> Semantic → Algorithmic → Syntactic → Micro<br/>
                                        Higher layers make broader changes, lower layers make focused optimizations.
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                <div className="form-footer">
                    <div className="config-group">
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginRight: '1rem', color: 'var(--text-muted)' }}>
                            <Sliders size={18} /> <span style={{ fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.1rem', fontWeight: 600 }}>Parameters</span>
                        </div>

                        <div className="input-field">
                            <label>Generations</label>
                            <input
                                type="number"
                                value={config.generations}
                                min="1"
                                max="100"
                                onChange={(e) => setConfig({ ...config, generations: parseInt(e.target.value) })}
                                style={{ width: '80px' }}
                            />
                        </div>
                        <div className="input-field">
                            <label>Population</label>
                            <input
                                type="number"
                                value={config.population_size}
                                min="2"
                                max="50"
                                onChange={(e) => setConfig({ ...config, population_size: parseInt(e.target.value) })}
                                style={{ width: '80px' }}
                            />
                        </div>
                        <div className="input-field">
                            <label>Optimization Level</label>
                            <select
                                value={config.level}
                                onChange={(e) => setConfig({ ...config, level: e.target.value })}
                                style={{
                                    border: config.level === 'advanced' ? '1px solid var(--primary)' : '1px solid var(--border)',
                                    color: config.level === 'advanced' ? 'var(--primary)' : 'inherit',
                                    width: '150px'
                                }}
                            >
                                <option value="micro">Micro (Fast)</option>
                                <option value="standard">Standard (Balanced)</option>
                                <option value="advanced">Advanced (AI-Powered)</option>
                            </select>
                        </div>
                        <div className="level-info" style={{ maxWidth: '200px', fontSize: '0.75rem' }}>
                            {LEVEL_DESCS[config.level]}
                        </div>
                    </div>

                    {validationErrors.length > 0 && (
                        <div className="card glass" style={{ 
                            borderColor: 'var(--danger)', 
                            backgroundColor: 'rgba(255, 77, 77, 0.1)', 
                            marginBottom: '1rem' 
                        }}>
                            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.5rem' }}>
                                <AlertCircle size={20} color="var(--danger)" style={{ marginTop: '0.1rem', flexShrink: 0 }} />
                                <div>
                                    <h4 style={{ color: 'var(--danger)', margin: '0 0 0.5rem 0' }}>Validation Errors</h4>
                                    <ul style={{ margin: 0, paddingLeft: '1rem', color: 'var(--danger)' }}>
                                        {validationErrors.map((error, index) => (
                                            <li key={index} style={{ marginBottom: '0.25rem' }}>{error}</li>
                                        ))}
                                    </ul>
                                </div>
                            </div>
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={loading}
                        className="btn-primary"
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.75rem',
                            padding: '0.8rem 1.5rem',
                            fontSize: '1rem'
                        }}
                    >
                        {loading ? (
                            <>Starting Evolution...</>
                        ) : (
                            <>Start Optimization <Play size={20} fill="currentColor" /></>
                        )}
                    </button>
                </div>
            </form >
        </div >
    );
};

export default OptimizationForm;
