# EvoEval Benchmark Analysis

- Results root: `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260317_110348`
- Total runs: **9**
- Successful runs (`status=ok`): **9**
- Non-ok runs: **0**

## Best Variant (By Mean Improvement)
- `main` with mean improvement `23.3684%`

## Best Single Run
- `main` on `EvoEval_difficult_66` (`advancedDigitSum`): `99.4600%` improvement

## Output Files
- `analysis/enriched_run_summary.csv`
- `analysis/variant_summary.csv`
- `analysis/problem_variant_summary.csv`
- `analysis/operator_summary.csv`
- `analysis/tier_summary.csv`
- `analysis/funnel_summary.csv`
- Plot files:
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260317_110348/analysis/plots/improvement_heatmap.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260317_110348/analysis/plots/improvement_vs_co2_scatter.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260317_110348/analysis/plots/variant_improvement_boxplot.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260317_110348/analysis/plots/variant_summary_bars.png`

## Notes
- `operator_summary.csv` and `tier_summary.csv` aggregate candidate-level signals from metrics JSON.
- Funnel stages use SPECTRA iteration/candidate traces (generated -> correctness -> screened -> F1/F2/F3 -> confirmed).
- Per-problem trajectories plot `improvement_over_baseline_pct` over optimization iterations.
