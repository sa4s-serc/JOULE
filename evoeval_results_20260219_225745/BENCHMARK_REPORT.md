# HEDGE EvoEval Benchmark Study Report

**Generated**: 2026-02-20 07:52:59

**Configuration**:
- Optimization Level: `aggressive`
- Generations: 15
- Population Size: 10
- LLM Provider: gemini
- Test Iterations: 10
- Test Warmup Iterations: 3
- Test Seed: 42

## Executive Summary

- **Total Problems**: 9
- **Successful**: 9
- **Failed**: 0
- **Total Time**: 32114.46 seconds

## Detailed Results

| Problem | Status | Improvement | Baseline (ms) | Best (ms) | Pareto Solutions | Time (s) |
|---------|--------|-------------|---------------|-----------|------------------|----------|
| EvoEval_difficult_4 | success | N/A | N/A | N/A | 1 | 2590.14 |
| EvoEval_difficult_16 | success | N/A | N/A | N/A | 1 | 2580.68 |
| EvoEval_difficult_52 | success | N/A | N/A | N/A | 1 | 2572.77 |
| EvoEval_difficult_53 | success | N/A | N/A | N/A | 1 | 4538.61 |
| EvoEval_difficult_61 | success | N/A | N/A | N/A | 2 | 3255.64 |
| EvoEval_difficult_63 | success | N/A | N/A | N/A | 1 | 2590.03 |
| EvoEval_difficult_66 | success | N/A | N/A | N/A | 1 | 8584.05 |
| EvoEval_difficult_79 | success | N/A | N/A | N/A | 1 | 2703.36 |
| EvoEval_difficult_90 | success | N/A | N/A | N/A | 1 | 2699.17 |

## Problem-Specific Analysis

### EvoEval_difficult_4

**Status**: ✅ Success

**Optimization Statistics**:
- Total Mutations: 0
- Successful Mutations: 1
- Success Rate: N/A

**Artifacts**:
- Optimized Code: `evoeval_results_20260219_225745/EvoEval_difficult_4/optimized.py`
- Pareto Results: `evoeval_results_20260219_225745/EvoEval_difficult_4/pareto_results.json`
- Visualization: `evoeval_results_20260219_225745/EvoEval_difficult_4/report.html`

---

### EvoEval_difficult_16

**Status**: ✅ Success

**Optimization Statistics**:
- Total Mutations: 0
- Successful Mutations: 1
- Success Rate: N/A

**Artifacts**:
- Optimized Code: `evoeval_results_20260219_225745/EvoEval_difficult_16/optimized.py`
- Pareto Results: `evoeval_results_20260219_225745/EvoEval_difficult_16/pareto_results.json`
- Visualization: `evoeval_results_20260219_225745/EvoEval_difficult_16/report.html`

---

### EvoEval_difficult_52

**Status**: ✅ Success

**Optimization Statistics**:
- Total Mutations: 0
- Successful Mutations: 1
- Success Rate: N/A

**Artifacts**:
- Optimized Code: `evoeval_results_20260219_225745/EvoEval_difficult_52/optimized.py`
- Pareto Results: `evoeval_results_20260219_225745/EvoEval_difficult_52/pareto_results.json`
- Visualization: `evoeval_results_20260219_225745/EvoEval_difficult_52/report.html`

---

### EvoEval_difficult_53

**Status**: ✅ Success

**Optimization Statistics**:
- Total Mutations: 0
- Successful Mutations: 1
- Success Rate: N/A

**Artifacts**:
- Optimized Code: `evoeval_results_20260219_225745/EvoEval_difficult_53/optimized.py`
- Pareto Results: `evoeval_results_20260219_225745/EvoEval_difficult_53/pareto_results.json`
- Visualization: `evoeval_results_20260219_225745/EvoEval_difficult_53/report.html`

---

### EvoEval_difficult_61

**Status**: ✅ Success

**Optimization Statistics**:
- Total Mutations: 0
- Successful Mutations: 2
- Success Rate: N/A

**Artifacts**:
- Optimized Code: `evoeval_results_20260219_225745/EvoEval_difficult_61/optimized.py`
- Pareto Results: `evoeval_results_20260219_225745/EvoEval_difficult_61/pareto_results.json`
- Visualization: `evoeval_results_20260219_225745/EvoEval_difficult_61/report.html`

---

### EvoEval_difficult_63

**Status**: ✅ Success

**Optimization Statistics**:
- Total Mutations: 0
- Successful Mutations: 1
- Success Rate: N/A

**Artifacts**:
- Optimized Code: `evoeval_results_20260219_225745/EvoEval_difficult_63/optimized.py`
- Pareto Results: `evoeval_results_20260219_225745/EvoEval_difficult_63/pareto_results.json`
- Visualization: `evoeval_results_20260219_225745/EvoEval_difficult_63/report.html`

---

### EvoEval_difficult_66

**Status**: ✅ Success

**Optimization Statistics**:
- Total Mutations: 0
- Successful Mutations: 1
- Success Rate: N/A

**Artifacts**:
- Optimized Code: `evoeval_results_20260219_225745/EvoEval_difficult_66/optimized.py`
- Pareto Results: `evoeval_results_20260219_225745/EvoEval_difficult_66/pareto_results.json`
- Visualization: `evoeval_results_20260219_225745/EvoEval_difficult_66/report.html`

---

### EvoEval_difficult_79

**Status**: ✅ Success

**Optimization Statistics**:
- Total Mutations: 0
- Successful Mutations: 1
- Success Rate: N/A

**Artifacts**:
- Optimized Code: `evoeval_results_20260219_225745/EvoEval_difficult_79/optimized.py`
- Pareto Results: `evoeval_results_20260219_225745/EvoEval_difficult_79/pareto_results.json`
- Visualization: `evoeval_results_20260219_225745/EvoEval_difficult_79/report.html`

---

### EvoEval_difficult_90

**Status**: ✅ Success

**Optimization Statistics**:
- Total Mutations: 0
- Successful Mutations: 1
- Success Rate: N/A

**Artifacts**:
- Optimized Code: `evoeval_results_20260219_225745/EvoEval_difficult_90/optimized.py`
- Pareto Results: `evoeval_results_20260219_225745/EvoEval_difficult_90/pareto_results.json`
- Visualization: `evoeval_results_20260219_225745/EvoEval_difficult_90/report.html`

---

## Visualization

Individual problem visualizations are available in each problem's subdirectory.

To view a specific problem's results:
```bash
# Open HTML report
open evoeval_results_20260219_225745/[problem_name]/report.html
```

## Conclusion

✅ All problems were successfully optimized!

---

*Generated by HEDGE EvoEval Benchmark Runner*
