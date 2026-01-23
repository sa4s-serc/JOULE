
import React, { useState } from 'react';
import { Play } from 'lucide-react';
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
    micro: 'Basic peephole and micro-optimizations (loops, constants).',
    standard: 'Algorithmic improvements and common performance patterns.',
    advanced: 'LLM-powered semantic optimization and advanced algorithmic rewriting.'
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

    const loadTemplate = (key) => {
        setTargetCode(TEMPLATES[key].target);
        setTestCode(TEMPLATES[key].test);
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
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <hgroup>
                    <h2 style={{ color: 'var(--primary-light)', margin: 0 }}>New Optimization Task</h2>
                    <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>Configure your evolution parameters</p>
                </hgroup>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    {Object.keys(TEMPLATES).map(key => (
                        <button
                            key={key}
                            onClick={() => loadTemplate(key)}
                            type="button"
                            className="btn-small"
                        >
                            {TEMPLATES[key].name}
                        </button>
                    ))}
                </div>
            </div>

            <form onSubmit={handleSubmit}>
                <div className="grid cols-2">
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <label>Target Code <span className="label-hint">(Code to be optimized)</span></label>
                        <textarea
                            value={targetCode}
                            onChange={(e) => setTargetCode(e.target.value)}
                            rows={15}
                            className="code-editor"
                        />
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <label>Test Code <span className="label-hint">(Validation harness)</span></label>
                        <textarea
                            value={testCode}
                            onChange={(e) => setTestCode(e.target.value)}
                            rows={15}
                            className="code-editor"
                        />
                    </div>
                </div>

                <div className="form-footer">
                    <div className="config-group">
                        <div className="input-field">
                            <label>Generations</label>
                            <input
                                type="number"
                                value={config.generations}
                                onChange={(e) => setConfig({ ...config, generations: parseInt(e.target.value) })}
                            />
                        </div>
                        <div className="input-field">
                            <label>Population</label>
                            <input
                                type="number"
                                value={config.population_size}
                                onChange={(e) => setConfig({ ...config, population_size: parseInt(e.target.value) })}
                            />
                        </div>
                        <div className="input-field">
                            <label>Level</label>
                            <select
                                value={config.level}
                                onChange={(e) => setConfig({ ...config, level: e.target.value })}
                            >
                                <option value="micro">Micro</option>
                                <option value="standard">Standard</option>
                                <option value="advanced">Advanced</option>
                            </select>
                        </div>
                        <div className="level-info">
                            {LEVEL_DESCS[config.level]}
                        </div>
                    </div>

                    <button type="submit" disabled={loading} className="btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <Play size={18} />
                        {loading ? 'Starting...' : 'Start Optimization'}
                    </button>
                </div>
            </form>
        </div>
    );
};

export default OptimizationForm;
