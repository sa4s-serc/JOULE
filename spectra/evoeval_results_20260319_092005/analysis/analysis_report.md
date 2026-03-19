# EvoEval Benchmark Analysis

- Results root: `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260319_092005`
- Total runs: **9**
- Successful runs (`status=ok`): **9**
- Non-ok runs: **0**

## Best Variant (By Mean Improvement)
- `main` with mean improvement `4.4432%`

## Best Single Run
- `main` on `EvoEval_difficult_4` (`weighted_mean_absolute_deviation`): `14.4800%` improvement

## Output Files
- `analysis/enriched_run_summary.csv`
- `analysis/variant_summary.csv`
- `analysis/problem_variant_summary.csv`
- `analysis/operator_summary.csv`
- `analysis/tier_summary.csv`
- `analysis/funnel_summary.csv`
- Plot files:
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260319_092005/analysis/plots/candidate_funnel_by_variant.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260319_092005/analysis/plots/improvement_heatmap.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260319_092005/analysis/plots/improvement_vs_co2_scatter.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260319_092005/analysis/plots/operator_effectiveness.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260319_092005/analysis/plots/problem_trajectories/EvoEval_difficult_16_trajectory.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260319_092005/analysis/plots/problem_trajectories/EvoEval_difficult_4_trajectory.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260319_092005/analysis/plots/problem_trajectories/EvoEval_difficult_52_trajectory.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260319_092005/analysis/plots/problem_trajectories/EvoEval_difficult_53_trajectory.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260319_092005/analysis/plots/problem_trajectories/EvoEval_difficult_61_trajectory.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260319_092005/analysis/plots/problem_trajectories/EvoEval_difficult_63_trajectory.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260319_092005/analysis/plots/problem_trajectories/EvoEval_difficult_66_trajectory.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260319_092005/analysis/plots/problem_trajectories/EvoEval_difficult_79_trajectory.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260319_092005/analysis/plots/problem_trajectories/EvoEval_difficult_90_trajectory.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260319_092005/analysis/plots/tier_outcomes.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260319_092005/analysis/plots/variant_improvement_boxplot.png`
  - `/home/prakhar/dev/prakhar479/HEDGE/spectra/evoeval_results_20260319_092005/analysis/plots/variant_summary_bars.png`

## Notes
- `operator_summary.csv` and `tier_summary.csv` aggregate candidate-level signals from metrics JSON.
- Funnel stages use SPECTRA iteration/candidate traces (generated -> correctness -> screened -> F1/F2/F3 -> confirmed).
- Per-problem trajectories plot `improvement_over_baseline_pct` over optimization iterations.
