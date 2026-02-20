# EvoEval Comparison Report: Original vs Optimized

**Generated**: 2026-02-20 17:40:01

## Configuration

- Test Iterations: 10
- Test Warmup Iterations: 3
- Test Seed: 42
- Timeout: 60s
- Original Code: `evoeval_benchmark`
- Optimized Code: `evoeval_results_20260219_225745`

## Summary

- **Total Problems**: 9
- **Successful Comparisons**: 9
- **Average Time Improvement**: 0.17%
- **Best Time Improvement**: 1.58%
- **Worst Time Improvement**: -0.38%
- **Average Energy Improvement**: 0.35%
- **Best Energy Improvement**: 2.44%
- **Worst Energy Improvement**: -0.70%

## Detailed Results

| Problem | Status | Time Imp. | Energy Imp. | Speedup | Time Saved | Energy Saved |
|---------|--------|-----------|-------------|---------|------------|-------------|
| EvoEval_difficult_16 | ✅ | 1.58% | 2.11% | 1.02x | 0.1815s | 16.25J |
| EvoEval_difficult_4 | ✅ | 0.10% | 0.45% | 1.00x | 0.0052s | 0.70J |
| EvoEval_difficult_52 | ✅ | 0.20% | -0.70% | 1.00x | 0.0099s | -1.10J |
| EvoEval_difficult_53 | ✅ | -0.06% | -0.49% | 1.00x | -0.0028s | -0.76J |
| EvoEval_difficult_61 | ✅ | 0.24% | 2.44% | 1.00x | 0.0123s | 3.89J |
| EvoEval_difficult_63 | ✅ | 0.02% | 0.02% | 1.00x | 0.0010s | 0.04J |
| EvoEval_difficult_66 | ✅ | -0.38% | -0.49% | 1.00x | -0.0197s | -0.79J |
| EvoEval_difficult_79 | ✅ | 0.02% | 0.19% | 1.00x | 0.0009s | 0.30J |
| EvoEval_difficult_90 | ✅ | -0.16% | -0.41% | 1.00x | -0.0082s | -0.65J |

## Problem-by-Problem Analysis

### EvoEval_difficult_16

**Original Code:**
- Duration: 11.476225 seconds
- Energy: 771.568442 joules
- Emissions: 0.000152908 kg CO₂

**Optimized Code:**
- Duration: 11.294721 seconds
- Energy: 755.317607 joules
- Emissions: 0.000149687 kg CO₂

**Improvements:**
- Time: 1.58% (1.02x speedup)
- Energy: 2.11%
- Emissions: 2.11%

---

### EvoEval_difficult_4

**Original Code:**
- Duration: 5.055221 seconds
- Energy: 156.399615 joules
- Emissions: 0.000030995 kg CO₂

**Optimized Code:**
- Duration: 5.049999 seconds
- Energy: 155.699803 joules
- Emissions: 0.000030856 kg CO₂

**Improvements:**
- Time: 0.10% (1.00x speedup)
- Energy: 0.45%
- Emissions: 0.45%

---

### EvoEval_difficult_52

**Original Code:**
- Duration: 5.072953 seconds
- Energy: 155.891396 joules
- Emissions: 0.000030894 kg CO₂

**Optimized Code:**
- Duration: 5.063054 seconds
- Energy: 156.987737 joules
- Emissions: 0.000031112 kg CO₂

**Improvements:**
- Time: 0.20% (1.00x speedup)
- Energy: -0.70%
- Emissions: -0.70%

---

### EvoEval_difficult_53

**Original Code:**
- Duration: 5.046767 seconds
- Energy: 155.865320 joules
- Emissions: 0.000030889 kg CO₂

**Optimized Code:**
- Duration: 5.049609 seconds
- Energy: 156.623307 joules
- Emissions: 0.000031039 kg CO₂

**Improvements:**
- Time: -0.06% (1.00x speedup)
- Energy: -0.49%
- Emissions: -0.49%

---

### EvoEval_difficult_61

**Original Code:**
- Duration: 5.061648 seconds
- Energy: 159.492842 joules
- Emissions: 0.000031608 kg CO₂

**Optimized Code:**
- Duration: 5.049367 seconds
- Energy: 155.602237 joules
- Emissions: 0.000030837 kg CO₂

**Improvements:**
- Time: 0.24% (1.00x speedup)
- Energy: 2.44%
- Emissions: 2.44%

---

### EvoEval_difficult_63

**Original Code:**
- Duration: 5.052534 seconds
- Energy: 155.661487 joules
- Emissions: 0.000030849 kg CO₂

**Optimized Code:**
- Duration: 5.051534 seconds
- Energy: 155.623291 joules
- Emissions: 0.000030841 kg CO₂

**Improvements:**
- Time: 0.02% (1.00x speedup)
- Energy: 0.02%
- Emissions: 0.02%

---

### EvoEval_difficult_66

**Original Code:**
- Duration: 5.212490 seconds
- Energy: 160.865045 joules
- Emissions: 0.000031880 kg CO₂

**Optimized Code:**
- Duration: 5.232197 seconds
- Energy: 161.656934 joules
- Emissions: 0.000032037 kg CO₂

**Improvements:**
- Time: -0.38% (1.00x speedup)
- Energy: -0.49%
- Emissions: -0.49%

---

### EvoEval_difficult_79

**Original Code:**
- Duration: 5.052000 seconds
- Energy: 155.891958 joules
- Emissions: 0.000030894 kg CO₂

**Optimized Code:**
- Duration: 5.051066 seconds
- Energy: 155.596732 joules
- Emissions: 0.000030836 kg CO₂

**Improvements:**
- Time: 0.02% (1.00x speedup)
- Energy: 0.19%
- Emissions: 0.19%

---

### EvoEval_difficult_90

**Original Code:**
- Duration: 5.049473 seconds
- Energy: 155.736582 joules
- Emissions: 0.000030864 kg CO₂

**Optimized Code:**
- Duration: 5.057690 seconds
- Energy: 156.382093 joules
- Emissions: 0.000030991 kg CO₂

**Improvements:**
- Time: -0.16% (1.00x speedup)
- Energy: -0.41%
- Emissions: -0.41%

---

## Methodology

This comparison uses HEDGE's exact measurement infrastructure:

- **Runner**: GreenGymRunner (subprocess isolation)
- **Energy Measurement**: CodeCarbon EmissionsTracker
- **Timing**: `time.perf_counter()` for high-precision wall-clock measurement
- **Test Iterations**: 10 measured iterations per solution
- **Warmup**: 3 warmup runs before measurement
- **Seed Management**: Base seed 42, incremented per iteration
- **Aggregation**: SUM of all iteration metrics (HEDGE's standard approach)

All measurements are performed in isolated subprocesses with identical test conditions.

---

*Generated by EvoEval Comparison Script*
