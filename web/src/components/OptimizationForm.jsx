
import React, { useState } from 'react';
import { Play, Code, FileCode, Sliders, Dna } from 'lucide-react';
import axios from 'axios';

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
    const [loading, setLoading] = useState(false);
    const [activeTemplate, setActiveTemplate] = useState('fib');

    const loadTemplate = (key) => {
        setTargetCode(TEMPLATES[key].target);
        setTestCode(TEMPLATES[key].test);
        setActiveTemplate(key);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            const response = await axios.post('http://localhost:8000/optimize', {
                target_code: targetCode,
                test_code: testCode,
                config: config
            });
            onStart({ ...response.data, original_code: targetCode });
        } catch (err) {
            onError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="card glass">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', borderBottom: '1px solid var(--border)', paddingBottom: '1rem' }}>
                <hgroup>
                    <h2 style={{ color: 'var(--text-main)', margin: 0, fontSize: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <Dna size={24} color="var(--primary)" /> New Optimization Task
                    </h2>
                    <p style={{ margin: '0.4rem 0 0 2rem', fontSize: '0.9rem', color: 'var(--text-muted)' }}>Configure parameters and input code to evolve</p>
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
                                style={{ width: '100px' }}
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
                                style={{ width: '100px' }}
                            />
                        </div>
                        <div className="input-field">
                            <label>Optimization Level</label>
                            <select
                                value={config.level}
                                onChange={(e) => setConfig({ ...config, level: e.target.value })}
                                style={{
                                    border: config.level === 'advanced' ? '1px solid var(--primary)' : '1px solid var(--border)',
                                    color: config.level === 'advanced' ? 'var(--primary)' : 'inherit'
                                }}
                            >
                                <option value="micro">Micro (Fast)</option>
                                <option value="standard">Standard (Balanced)</option>
                                <option value="advanced">Advanced (AI-Powered)</option>
                            </select>
                        </div>
                        <div className="level-info" style={{ maxWidth: '250px' }}>
                            {LEVEL_DESCS[config.level]}
                        </div>
                    </div>

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
            </form>
        </div>
    );
};

export default OptimizationForm;
