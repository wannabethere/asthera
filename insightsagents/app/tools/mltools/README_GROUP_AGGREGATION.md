### Specialized Functions

| Function | Description | Example Usage |
|----------|-------------|---------------|
| `unique_count` | Count unique values across all groups | `moving_apply_by_group('product_id', 'category', unique_count, window=30)` |
| `mode` | Find most frequent value across all groups | `moving_apply_by_group('status', 'priority', mode, window=14)` |
| `weighted_average` | Calculate weighted average across all groups | `moving_apply_by_group('price', 'category', weighted_average, window=21)` |
| `geometric_mean` | Calculate geometric mean across all groups | `moving_apply_by_group('growth_rate', 'sector', geometric_mean, window=45)` |
| `harmonic_mean` | Calculate harmonic mean across all groups | `moving_apply_by_group('speed', 'vehicle_type', harmonic_mean, window=30)` |
| `interquartile_range` | Calculate IQR (Q3 - Q1) across all groups | `moving_apply_by_group('salary', 'job_level', interquartile_range, window=60)` |
| `mad` | Calculate mean absolute deviation across all groups | `moving_apply_by_group('returns', 'asset', mad, window=30)` |

### Operations Tool Functions

| Function | Description | Example Usage |
|----------|-------------|---------------|
| `percent_change` | Calculate percent change across all groups | `moving_apply_by_group('value', 'category', percent_change, window=7)` |
| `absolute_change` | Calculate absolute change across all groups | `moving_apply_by_group('value', 'category', absolute_change, window=7)` |
| `mantel_haenszel_estimate` | Calculate Mantel-Haenszel estimate across all groups | `moving_apply_by_group('value', 'category', mantel_haenszel_estimate, window=7)` |
| `cuped_adjustment` | Calculate CUPED-adjusted value across all groups | `moving_apply_by_group('value', 'category', cuped_adjustment, window=7)` |
| `prepost_adjustment` | Calculate PrePost-adjusted value across all groups | `moving_apply_by_group('value', 'category', prepost_adjustment, window=7)` |
| `power_analysis` | Calculate power analysis metrics across all groups | `moving_apply_by_group('value', 'category', power_analysis, window=7)` |
| `stratified_summary` | Calculate stratified summary statistics across all groups | `moving_apply_by_group('value', 'category', stratified_summary, window=7)` |
| `bootstrap_confidence_interval` | Calculate bootstrap confidence interval across all groups | `moving_apply_by_group('value', 'category', bootstrap_confidence_interval, window=7)` |
| `multi_comparison_adjustment` | Calculate multi-comparison adjusted value across all groups | `moving_apply_by_group('value', 'category', multi_comparison_adjustment, window=7)` |
| `effect_size` | Calculate effect size (Cohen's d) across all groups | `moving_apply_by_group('value', 'category', effect_size, window=7)` |
| `z_score` | Calculate z-score across all groups | `moving_apply_by_group('value', 'category', z_score, window=7)` |
| `relative_risk` | Calculate relative risk across all groups | `moving_apply_by_group('value', 'category', relative_risk, window=7)` |
| `odds_ratio` | Calculate odds ratio across all groups | `moving_apply_by_group('value', 'category', odds_ratio, window=7)` |
