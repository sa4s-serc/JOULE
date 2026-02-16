# HEDGE EvoEval Benchmark Study Report

**Generated**: 2026-02-11 21:54:48

**Configuration**:
- Optimization Level: `aggressive`
- Generations: 5
- Population Size: 15
- LLM Provider: gemini
- Test Iterations: 5
- Test Warmup Iterations: 5
- Test Seed: 42

## Executive Summary

- **Total Problems**: 9
- **Successful**: 8
- **Failed**: 1
- **Total Time**: 10142.27 seconds

## Detailed Results

| Problem | Status | Improvement | Baseline (ms) | Best (ms) | Pareto Solutions | Time (s) |
|---------|--------|-------------|---------------|-----------|------------------|----------|
| EvoEval_difficult_4 | success | N/A | N/A | N/A | 1 | 931.55 |
| EvoEval_difficult_16 | success | N/A | N/A | N/A | 2 | 1302.14 |
| EvoEval_difficult_52 | success | N/A | N/A | N/A | 2 | 1047.93 |
| EvoEval_difficult_53 | success | N/A | N/A | N/A | 1 | 780.80 |
| EvoEval_difficult_61 | timeout | N/A | N/A | N/A | 0 | 0.00 |
| EvoEval_difficult_63 | success | N/A | N/A | N/A | 1 | 835.97 |
| EvoEval_difficult_66 | success | N/A | N/A | N/A | 1 | 654.23 |
| EvoEval_difficult_79 | success | N/A | N/A | N/A | 2 | 808.03 |
| EvoEval_difficult_90 | success | N/A | N/A | N/A | 1 | 1081.51 |

## Problem-Specific Analysis

### EvoEval_difficult_4

**Status**: ✅ Success

**Optimization Statistics**:
- Total Mutations: 0
- Successful Mutations: 1
- Success Rate: N/A

**Artifacts**:
- Optimized Code: `evoeval_results_20260211_190545/EvoEval_difficult_4/optimized.py`
- Pareto Results: `evoeval_results_20260211_190545/EvoEval_difficult_4/pareto_results.json`
- Visualization: `evoeval_results_20260211_190545/EvoEval_difficult_4/report.html`

---

### EvoEval_difficult_16

**Status**: ✅ Success

**Optimization Statistics**:
- Total Mutations: 0
- Successful Mutations: 2
- Success Rate: N/A

**Artifacts**:
- Optimized Code: `evoeval_results_20260211_190545/EvoEval_difficult_16/optimized.py`
- Pareto Results: `evoeval_results_20260211_190545/EvoEval_difficult_16/pareto_results.json`
- Visualization: `evoeval_results_20260211_190545/EvoEval_difficult_16/report.html`

---

### EvoEval_difficult_52

**Status**: ✅ Success

**Optimization Statistics**:
- Total Mutations: 0
- Successful Mutations: 2
- Success Rate: N/A

**Artifacts**:
- Optimized Code: `evoeval_results_20260211_190545/EvoEval_difficult_52/optimized.py`
- Pareto Results: `evoeval_results_20260211_190545/EvoEval_difficult_52/pareto_results.json`
- Visualization: `evoeval_results_20260211_190545/EvoEval_difficult_52/report.html`

---

### EvoEval_difficult_53

**Status**: ✅ Success

**Optimization Statistics**:
- Total Mutations: 0
- Successful Mutations: 1
- Success Rate: N/A

**Artifacts**:
- Optimized Code: `evoeval_results_20260211_190545/EvoEval_difficult_53/optimized.py`
- Pareto Results: `evoeval_results_20260211_190545/EvoEval_difficult_53/pareto_results.json`
- Visualization: `evoeval_results_20260211_190545/EvoEval_difficult_53/report.html`

---

### EvoEval_difficult_61

**Status**: ❌ timeout

**Error**: Execution exceeded 45 minutes

---

### EvoEval_difficult_63

**Status**: ✅ Success

**Optimization Statistics**:
- Total Mutations: 0
- Successful Mutations: 1
- Success Rate: N/A

**Artifacts**:
- Optimized Code: `evoeval_results_20260211_190545/EvoEval_difficult_63/optimized.py`
- Pareto Results: `evoeval_results_20260211_190545/EvoEval_difficult_63/pareto_results.json`
- Visualization: `evoeval_results_20260211_190545/EvoEval_difficult_63/report.html`

---

### EvoEval_difficult_66

**Status**: ✅ Success

**Optimization Statistics**:
- Total Mutations: 0
- Successful Mutations: 1
- Success Rate: N/A

**Artifacts**:
- Optimized Code: `evoeval_results_20260211_190545/EvoEval_difficult_66/optimized.py`
- Pareto Results: `evoeval_results_20260211_190545/EvoEval_difficult_66/pareto_results.json`
- Visualization: `evoeval_results_20260211_190545/EvoEval_difficult_66/report.html`

---

### EvoEval_difficult_79

**Status**: ✅ Success

**Optimization Statistics**:
- Total Mutations: 0
- Successful Mutations: 2
- Success Rate: N/A

**Artifacts**:
- Optimized Code: `evoeval_results_20260211_190545/EvoEval_difficult_79/optimized.py`
- Pareto Results: `evoeval_results_20260211_190545/EvoEval_difficult_79/pareto_results.json`
- Visualization: `evoeval_results_20260211_190545/EvoEval_difficult_79/report.html`

---

### EvoEval_difficult_90

**Status**: ✅ Success

**Optimization Statistics**:
- Total Mutations: 0
- Successful Mutations: 1
- Success Rate: N/A

**Artifacts**:
- Optimized Code: `evoeval_results_20260211_190545/EvoEval_difficult_90/optimized.py`
- Pareto Results: `evoeval_results_20260211_190545/EvoEval_difficult_90/pareto_results.json`
- Visualization: `evoeval_results_20260211_190545/EvoEval_difficult_90/report.html`

---

## Visualization

Individual problem visualizations are available in each problem's subdirectory.

To view a specific problem's results:
```bash
# Open HTML report
open evoeval_results_20260211_190545/[problem_name]/report.html
```

## Conclusion

⚠️ 8 out of 9 problems were successfully optimized.

---

*Generated by HEDGE EvoEval Benchmark Runner*
