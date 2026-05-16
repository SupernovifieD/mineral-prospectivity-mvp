# Python Workflow V4: Northern Territory MVT Prospectivity at 500 m

This document is the v4 workflow for the Northern Territory MVT mineral prospectivity project.

It builds on:

- `archive/v3/PROJECT_WORKFLOW_NT_MVT_500M_V3.md`
- `DECISIONS_TO_MAKE_V4.md`
- `SPATIAL_SPLIT_FIX_PLAN.md`
- `ROADMAP_REVIEW_AND_GAP_ANALYSIS.md`

V4 focus:

```text
Fix spatial evaluation design first.
Keep modeling simple and reproducible.
Produce a screening map only after split evidence is trustworthy.
```

## 1. V4 Decisions Used In This Workflow

These decisions come from `DECISIONS_TO_MAKE_V4.md` (user-filled choices).

| Topic | V4 decision |
| --- | --- |
| Scientific objective | Exploratory learning run + screening benchmark (`G1: A and B`) |
| Study area and grid | NT only, 500 m, `EPSG:3577` (`G2: A`) |
| Label definition | All Australian MVT points inside NT (`G3: A`) |
| Split strategy | Zone-diverse deterministic split selection (`G4: B`) |
| Holdout diversity | Each original split uses a unique holdout candidate (`G5: B`) |
| Zone coverage | At least 2 holdout zones (`G6: B`) |
| Validation partner rule | Prefer cross-zone validation partner (`G7: B`) |
| Paired swaps | Disabled (`G8: A`) |
| Aggregate policy | Aggregate only original splits (`G9: B`) |
| Spatial buffer | 10 km buffer (`G10: D`) |
| Split positive thresholds | Lowered to `3 / 3 / 30` (holdout / validation / train) (`G11`) |
| Background sampling plan | Fixed 50:1 spatially stratified background sampling (`G12: A`) |
| Lithology encoding | One-hot lithology features (`G13: B`) |
| LAB depth | Keep feature in v4 (`G14: A`) |
| Model family | Random Forest only (`G15: A`) |
| Feature scaling | Keep forced scaler+RF pipeline (`G16: A`) |
| Primary evaluation | AP + top-k recall/enrichment + per-location reporting (`G17: B`) |
| Gap protocol | Mandatory validation-holdout gap diagnostic report (`G18: B`) |
| Reproducibility artifacts | Add manifests/checksums/relative paths (`G19: B`) |
| Feature importance | RF impurity importance only in v4 (`G20: A`) |
| Uncertainty map | No uncertainty map in v4 (`G21: A`) |
| Calibration | Deferred (`G22: B`) |
| Multi-resolution | Deferred (`G23: B`) |

## 2. What V4 Builds

V4 creates this chain:

```text
Raw GIS data
  -> Python ROI mask for Northern Territory
  -> Python 500 m template raster
  -> Python predictor rasters (including one-hot lithology)
  -> Python label raster from known MVT points
  -> YAML run-config load and validation
  -> Python raster stack and leakage checks
  -> Python zone-diverse spatial split masks with 10 km buffer
  -> Python split training samples (50:1 background-per-positive)
  -> Python fixed Random Forest evaluation across accepted original splits
  -> Python per-location and aggregate metrics + mandatory gap diagnostics
  -> Python final Random Forest screening model
  -> Python final prospectivity map and top-k maps
  -> Reproducibility manifest + archive-ready artifacts
```

Most important v4 rules:

```text
No repeated holdout candidate IDs in original splits.
Require >=2 holdout zones for non-exploratory claims.
Keep swapped splits disabled for v4.
Do not use holdout evidence from the final production model.
```

## 3. Active V4 Layout

Use this active-run layout in project root:

```text
configs/
  v4_run_config.yml
scripts/
  00_config.py
  01_make_roi_and_template.py
  02_process_continuous_rasters.py
  03_process_vector_predictors.py
  04_check_raster_stack.py
  05_make_mvt_labels.py
  06_make_spatial_splits.py
  07_build_split_training_samples.py
  08_evaluate_random_forest_splits.py
  09_train_final_random_forest.py
  10_predict_final_prospectivity.py
  11_summarize_v4_outputs.py
  12_write_run_manifest.py
data/
  raw/
  interim/
  processed/
outputs/
  maps/
  tables/
archive/
  v1/
  v2/
  v3/
```

At run end, archive to:

```text
archive/v4/
  configs/
  scripts/
  PROJECT_WORKFLOW_NT_MVT_500M_V4.md
  data/processed/
  outputs/
  run manifest + README summary
```

## 4. Preserve V3 Code Where Possible

Keep `01-05`, `07`, `09`, and `10` close to v3 unless a decision requires changes.

Start from:

- `pipeline/core_scripts/00_config.py`
- `pipeline/core_scripts/01_make_roi_and_template.py`
- `pipeline/core_scripts/02_process_continuous_rasters.py`
- `pipeline/core_scripts/03_process_vector_predictors.py`
- `pipeline/core_scripts/04_check_raster_stack.py`
- `archive/v3/scripts/05_make_mvt_labels.py`
- `archive/v3/scripts/07_build_split_training_samples.py`
- `archive/v3/scripts/09_train_final_random_forest.py`
- `archive/v3/scripts/10_predict_final_prospectivity.py`

Rewrite or materially extend:

- `06_make_spatial_splits.py` (zone-diverse deterministic + 10 km buffer)
- `08_evaluate_random_forest_splits.py` (per-location reporting + gap diagnostics outputs)
- `11_summarize_v4_outputs.py` (v4 report sections + original-only aggregate logic)
- `12_write_run_manifest.py` (reproducibility artifacts)

## 5. Script Overview

Run from project root:

```bash
python scripts/01_make_roi_and_template.py
python scripts/02_process_continuous_rasters.py
python scripts/03_process_vector_predictors.py
python scripts/04_check_raster_stack.py
python scripts/05_make_mvt_labels.py
python scripts/06_make_spatial_splits.py
python scripts/07_build_split_training_samples.py --config configs/v4_run_config.yml
python scripts/08_evaluate_random_forest_splits.py --config configs/v4_run_config.yml
python scripts/09_train_final_random_forest.py --config configs/v4_run_config.yml
python scripts/10_predict_final_prospectivity.py --config configs/v4_run_config.yml
python scripts/11_summarize_v4_outputs.py --config configs/v4_run_config.yml
python scripts/12_write_run_manifest.py --config configs/v4_run_config.yml
```

If CLI `--config` is not implemented yet, use one config filename at a time and keep filenames explicit.

## 6. Script 00: Shared Config + YAML Contract

V4 `00_config.py` should read runtime settings from YAML, not hardcoded script constants.

Required YAML sections:

```yaml
run:
  name: nt_mvt_v4_500m
  random_state: 42
  crs: EPSG:3577
  pixel_size_m: 500
  top_k_pcts: [1, 5, 10]

data_roles:
  label_column: label
  feature_columns: [...]
  identifier_columns: [...]
  forbidden_feature_patterns: [...]

scaling:
  enabled: true
  method: standard
  with_mean: true
  with_std: true

sampling:
  background_per_positive: 50
  use_spatially_stratified_background: true
  background_block_size_pixels: 100

prediction:
  chunk_size_pixels: 200000

split:
  strategy: zone_diverse_deterministic
  n_geographic_zones: 3
  require_min_zone_count: 2
  prefer_cross_zone_validation: true
  allow_swapped_pairs: false
  target_accepted_splits: 10
  min_accepted_splits_for_non_exploratory: 5
  use_spatial_buffer: true
  buffer_distance_m: 10000

  strict_holdout_area: 0.10
  strict_validation_area: 0.10
  strict_min_holdout_positives: 3
  strict_min_validation_positives: 3
  strict_min_train_positives: 30

  fallback_area_min: 0.08
  fallback_area_max: 0.20
  fallback_min_positives: 3

model:
  type: random_forest
  n_estimators: 500
  min_samples_leaf: 2
  class_weight: balanced
  n_jobs: -1
```

## 7. Script-Level V4 Requirements

### 01_make_roi_and_template.py

- Same as v3.
- Output NT mask and dissolved boundary in EPSG:3577 at 500 m.

### 02_process_continuous_rasters.py

- Same as v3.
- Keep consistent masking and NoData semantics.

### 03_process_vector_predictors.py

- Keep carbonate and fault-distance outputs.
- Replace single ordinal `lithology_code` feature with one-hot rasters (binary bands), for example:
  - `lithology_carbonate`
  - `lithology_chemical`
  - `lithology_evaporite`
  - `lithology_siliciclastic`
  - `lithology_unconsolidated`
  - `lithology_igneous`
  - `lithology_metamorphic`
  - `lithology_unknown`
- Update feature list in v4 YAML accordingly.

### 04_check_raster_stack.py

- Keep alignment + leakage checks.
- Validate all one-hot lithology rasters are present and aligned.

### 05_make_mvt_labels.py

- Same as v3, including unique positive-pixel counting.

### 06_make_spatial_splits.py (major v4 change)

Must implement:

1. deterministic zone-diverse holdout selection (`G4`, `G6`)
2. unique holdout candidate IDs across original splits (`G5`)
3. cross-zone validation preference (`G7`)
4. swapped pairs disabled (`G8: A`)
5. 10 km spatial buffer around validation and holdout regions (`G10`)
6. split thresholds `3/3/30` with fallback support (`G11`)

Output requirements:

- `split_summary.csv` with at least:
  - `split_id`
  - `split_mask` (prefer relative path)
  - `split_type` (`original` only in v4)
  - `holdout_candidate_id`
  - `validation_candidate_id`
  - `holdout_zone`
  - `validation_zone`
  - `uses_buffer` (true)
  - `buffer_distance_m` (10000)
- `candidate_blocks.csv` with eligibility and rejection reasons.

### 07_build_split_training_samples.py

- Reuse v3 logic.
- Run with fixed v4 sampling settings from config (`background_per_positive: 50`).

### 08_evaluate_random_forest_splits.py

- Reuse v3 RF evaluation core.
- Add explicit per-location reporting columns:
  - `holdout_candidate_id`
  - `holdout_zone`
  - `split_type`
- Write:
  - `metrics_by_split.csv`
  - `aggregate_metrics.csv` (original splits only)
  - `metrics_by_holdout_candidate.csv`
  - `validation_holdout_gap_diagnostic.csv`

### 09_train_final_random_forest.py

- Same as v3 with fixed v4 sampling settings from config.
- Keep warning that this is map-production model, not holdout evidence.

### 10_predict_final_prospectivity.py

- Same as v3.
- Keep chunk size from YAML.

### 11_summarize_v4_outputs.py

- Produce top-k maps and score summary.
- Write `v4_model_review.txt` with:
  - split coverage by zone
  - accepted split count
  - holdout performance by candidate
  - validation-vs-holdout gap summary
  - claim limits

### 12_write_run_manifest.py

Add reproducibility artifact:

- run timestamp
- git commit hash
- active config path + full copied YAML
- checksums for key inputs/outputs
- relative paths for key artifacts

## 8. Background Sampling Plan (G12)

Use one fixed setting in v4:

1. `background_per_positive = 50`
2. `use_spatially_stratified_background = true`
3. keep split masks unchanged for all model/evaluation runs

If you run a future sensitivity test, do it as a separate run label and never mix metrics from different sampling ratios in one aggregate table.

## 9. Non-Goals in V4

Do not add these in v4:

- probability calibration (`G22`)
- uncertainty map (`G21`)
- multi-resolution modeling (`G23`)
- comparator model families (`G15`)
- permutation importance (`G20`)

## 10. V4 Success Criteria

V4 is considered successful when:

1. original splits have unique holdout candidate IDs
2. original splits cover at least 2 holdout zones
3. buffer distance is 10 km in split artifacts
4. split counts meet non-exploratory threshold, or run is clearly labeled exploratory
5. gap diagnostics are reported automatically every run
6. background sampling ratio is fixed at 50 and documented in config + review report
7. all artifacts are reproducible using manifest + relative paths

## 11. Claims Language (Mandatory)

Use this language in all v4 outputs:

```text
Scores are relative prospectivity rankings, not calibrated deposit probabilities.
Holdout evidence comes from split evaluation, not from the final production model.
```
