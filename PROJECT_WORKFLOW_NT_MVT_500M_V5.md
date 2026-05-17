# Python Workflow V5: Northern Territory MVT Feature Ablation at 500 m

This document is the **active v5 workflow** for the Northern Territory MVT mineral prospectivity project.

It is intentionally scoped to **feature ablation only**.

It builds on:

- `archive/v4/PROJECT_WORKFLOW_NT_MVT_500M_V4.md`
- `archive/v4/DECISIONS_TO_MAKE_V4.md`
- `archive/v4/ROADMAP_REVIEW_AND_GAP_ANALYSIS.md`
- `archive/v4/SPATIAL_SPLIT_FIX_PLAN.md`
- `archive/v4/VALIDATION_HOLDOUT_GAP_DIAGNOSIS.md`

V5 focus:

```text
Keep V4 conditions fixed.
Change only feature subsets.
Measure split-level holdout behavior under controlled ablation experiments.
```

## 1. V5 Scientific Objective

V5 is an **ablation study**, not a new prospectivity model design.

Its purpose is to identify which **existing v4 feature groups** contribute to or hurt spatial holdout performance under fixed v4 conditions.

The primary evidence in v5 **must** come from split-based validation/holdout evaluation. The final production model (if produced) is secondary continuity output and **must not** be used as the main scientific evidence.

## 2. Fixed V4 Baseline Conditions (Must Stay Stable)

V5 must keep the following conditions fixed:

| Control axis | V5 requirement |
| --- | --- |
| Study area | Northern Territory only |
| Grid | 500 m |
| CRS | `EPSG:3577` |
| Label definition | Same MVT label logic as v4 |
| Predictor inventory | Same existing v4 predictor rasters |
| Split strategy | Same deterministic zone-diverse split generator as v4 |
| Buffer | 10 km |
| Split thresholds | Same as v4 (unless existing frozen config explicitly differs) |
| Background sampling | 50:1 background-per-positive, spatially stratified |
| Model family | Random Forest only |
| Scaling | Forced `StandardScaler + RandomForest` pipeline, same as v4 |
| Evaluation regions | Validation + holdout |
| Aggregate policy | Original splits only |
| Main metrics | AP, ROC AUC, top 1/5/10 recall/precision/enrichment, AP skill vs baseline |
| Claims policy | Relative ranking only (not calibrated deposit probability) |

## 3. What V5 Builds

V5 creates this chain:

```text
Raw GIS data (unchanged)
  -> Existing v4 predictor rasters and labels (reused)
  -> Existing v4 deterministic buffered split design (reused)
  -> Existing v4 split training samples (reused)
  -> YAML v5 run config with ablation experiments
  -> Split-level RF evaluation for each feature subset experiment
  -> Aggregate + per-holdout + gap + delta-vs-baseline + ranking outputs
  -> v5 ablation review report
  -> Reproducibility manifest for all ablation artifacts
```

Most important v5 scientific rule:

```text
The only factor that changes across experiments is the feature subset.
```

## 4. Active V5 Layout

Use this active-run layout in project root:

```text
configs/
  v5_run_config.yml

scripts/
  00_config.py
  01_make_roi_and_template.py
  02_process_continuous_rasters.py
  03_process_vector_predictors.py
  04_check_raster_stack.py
  05_make_mvt_labels.py
  06_make_spatial_splits.py
  07_build_split_training_samples.py
  08_run_feature_ablation_splits.py
  09_train_final_random_forest.py
  10_predict_final_prospectivity.py
  11_summarize_v5_outputs.py
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
  v4/
```

At run end, archive to:

```text
archive/v5/
  configs/
  scripts/
  PROJECT_WORKFLOW_NT_MVT_500M_V5.md
  data/processed/
  outputs/
```

## 5. Preserve V4 Mechanics Unless V5 Requires Change

### Reuse unchanged or near-unchanged

- `01_make_roi_and_template.py`
- `02_process_continuous_rasters.py`
- `03_process_vector_predictors.py`
- `04_check_raster_stack.py`
- `05_make_mvt_labels.py`
- `06_make_spatial_splits.py`
- `07_build_split_training_samples.py`
- `09_train_final_random_forest.py`
- `10_predict_final_prospectivity.py`
- `12_write_run_manifest.py` (same behavior pattern as v4, but v5 artifact names)

### Modify or add

- `00_config.py` (v5 config path, v5 artifact names, ablation config parsing/validation)
- `configs/v5_run_config.yml` (copied from v4 and extended with ablation section)
- `08_run_feature_ablation_splits.py` (new v5 core evaluation script)
- `11_summarize_v5_outputs.py` (v5 report + ablation ranking summary)

## 6. Script Overview (Execution Order)

Run from project root:

```bash
python scripts/01_make_roi_and_template.py
python scripts/02_process_continuous_rasters.py
python scripts/03_process_vector_predictors.py
python scripts/04_check_raster_stack.py
python scripts/05_make_mvt_labels.py
python scripts/06_make_spatial_splits.py
python scripts/07_build_split_training_samples.py
python scripts/08_run_feature_ablation_splits.py
python scripts/09_train_final_random_forest.py
python scripts/10_predict_final_prospectivity.py
python scripts/11_summarize_v5_outputs.py
python scripts/12_write_run_manifest.py
```

Notes:

- Scripts `09` and `10` are optional continuity outputs in v5.
- Scientific conclusions for v5 **must** come from script `08` outputs.

## 7. V5 Feature Set and Default Ablation Experiments

V4 full feature set (fixed inventory for v5):

- `carbonate_host`
- `lithology_carbonate`
- `lithology_chemical`
- `lithology_evaporite`
- `lithology_siliciclastic`
- `lithology_unconsolidated`
- `lithology_igneous`
- `lithology_metamorphic`
- `lithology_unknown`
- `dist_faults`
- `moho_depth`
- `lab_depth`
- `gravity`
- `gravity_hgm`
- `mag_rtp`
- `mag_hgm`
- `shape_index`

V5 default ablation experiment groups (proposed defaults; editable in config before freeze):

| Experiment ID | Feature logic | Purpose |
| --- | --- | --- |
| `full_baseline` | all v4 features | reference baseline |
| `no_lab_depth` | drop `lab_depth` | test LAB contribution |
| `no_deep_lithosphere` | drop `moho_depth`, `lab_depth` | test deep-earth proxy impact |
| `geology_only` | carbonate + one-hot lithology + `dist_faults` | test vector/geology-only signal |
| `geophysics_only` | moho/lab/gravity/magnetics/shape | test geophysics-only signal |
| `no_magnetics` | drop `mag_rtp`, `mag_hgm` | test magnetic predictor value |
| `no_gravity` | drop `gravity`, `gravity_hgm`, `shape_index` | test gravity-family predictor value |
| `no_lithology_onehot` | drop all one-hot lithology classes, keep `carbonate_host` | test one-hot value beyond carbonate flag |
| `carbonate_fault_only` | include `carbonate_host`, `dist_faults` | simple mineral-system baseline |

## 8. Script 00: Shared Config + YAML Contract (V5)

V5 `00_config.py` should keep the v4 contract and add an `ablation` section.

### Required core YAML sections (carry from v4)

- `run`
- `data_roles`
- `scaling`
- `sampling`
- `prediction`
- `split`
- `model`

### Required v5 changes

- `run.name` **must** be `nt_mvt_v5_feature_ablation_500m`
- Config file path **must** be `configs/v5_run_config.yml`
- Artifact names **must** be v5 names

### Required ablation section

```yaml
ablation:
  enabled: true
  baseline_experiment: full_baseline
  aggregate_reference_region: holdout
  ranking_metric: average_precision
  ranking_secondary_metrics:
    - top5_recall
    - top10_recall
    - ap_skill_vs_baseline
  experiments:
    - id: full_baseline
      label: Full V4 feature set
      mode: include
      features:
        - carbonate_host
        - lithology_carbonate
        - lithology_chemical
        - lithology_evaporite
        - lithology_siliciclastic
        - lithology_unconsolidated
        - lithology_igneous
        - lithology_metamorphic
        - lithology_unknown
        - dist_faults
        - moho_depth
        - lab_depth
        - gravity
        - gravity_hgm
        - mag_rtp
        - mag_hgm
        - shape_index

    - id: no_lab_depth
      label: Drop LAB depth
      mode: drop
      drop_features:
        - lab_depth

    - id: no_deep_lithosphere
      label: Drop Moho and LAB
      mode: drop
      drop_features:
        - moho_depth
        - lab_depth

    - id: geology_only
      label: Geology and faults only
      mode: include
      features:
        - carbonate_host
        - lithology_carbonate
        - lithology_chemical
        - lithology_evaporite
        - lithology_siliciclastic
        - lithology_unconsolidated
        - lithology_igneous
        - lithology_metamorphic
        - lithology_unknown
        - dist_faults

    - id: geophysics_only
      label: Geophysics only
      mode: include
      features:
        - moho_depth
        - lab_depth
        - gravity
        - gravity_hgm
        - mag_rtp
        - mag_hgm
        - shape_index

    - id: no_magnetics
      label: Drop magnetic predictors
      mode: drop
      drop_features:
        - mag_rtp
        - mag_hgm

    - id: no_gravity
      label: Drop gravity-related predictors
      mode: drop
      drop_features:
        - gravity
        - gravity_hgm
        - shape_index

    - id: no_lithology_onehot
      label: Drop detailed one-hot lithology
      mode: drop
      drop_features:
        - lithology_carbonate
        - lithology_chemical
        - lithology_evaporite
        - lithology_siliciclastic
        - lithology_unconsolidated
        - lithology_igneous
        - lithology_metamorphic
        - lithology_unknown

    - id: carbonate_fault_only
      label: Carbonate host plus fault distance only
      mode: include
      features:
        - carbonate_host
        - dist_faults
```

### Mode semantics (must)

- `mode: include` **must** use exactly the listed features.
- `mode: drop` **must** start from full v4 feature list and remove `drop_features`.

### Ablation validation rules (must)

- Experiment IDs are unique.
- Baseline experiment exists.
- Every experiment resolves to a non-empty feature list.
- Every experiment feature exists in `data_roles.feature_columns`.
- No forbidden feature patterns appear in experiment feature lists.
- Coordinates, rows, cols, split IDs, and sample role fields are never model features.
- Baseline should equal the full v4 feature set unless intentionally documented otherwise.

### Required 00_config.py additions (describe only, do not implement here)

- `ABLATION_CFG`
- `ABLATION_ENABLED`
- `ABLATION_BASELINE_EXPERIMENT`
- `ABLATION_EXPERIMENTS`
- `ABLATION_RANKING_METRIC`

Required v5 path/name updates:

- `RUN_CONFIG_PATH = configs/v5_run_config.yml`
- `RUN_NAME = nt_mvt_v5_feature_ablation_500m` default
- `FINAL_PROSPECTIVITY_MAP = mvt_prospectivity_rf_v5_500m.tif` (if used)
- `FINAL_SCORE_SUMMARY = final_score_summary_v5.csv`
- `MODEL_REVIEW_REPORT = v5_model_review.txt`
- `RUN_CONFIG_SNAPSHOT = v5_run_config_snapshot.yml`
- `RUN_MANIFEST_JSON = run_manifest_v5.json`

Required new ablation artifact paths:

- `FEATURE_ABLATION_METRICS_BY_SPLIT`
- `FEATURE_ABLATION_AGGREGATE_METRICS`
- `FEATURE_ABLATION_BY_HOLDOUT_CANDIDATE`
- `FEATURE_ABLATION_DELTA_VS_BASELINE`
- `FEATURE_ABLATION_VALIDATION_HOLDOUT_GAP`
- `FEATURE_ABLATION_RANKED_SUMMARY`

## 9. Script-Level V5 Requirements

### 01_make_roi_and_template.py

- Same behavior as v4.

### 02_process_continuous_rasters.py

- Same behavior as v4.

### 03_process_vector_predictors.py

- Same behavior as v4.
- No new geological predictors in v5.

### 04_check_raster_stack.py

- Same behavior as v4.

### 05_make_mvt_labels.py

- Same behavior as v4.

### 06_make_spatial_splits.py

- Same deterministic zone-diverse buffered split logic as v4.
- Split masks must remain unchanged across experiments.

### 07_build_split_training_samples.py

- Same behavior as v4.
- Sampled background rows must remain unchanged across experiments.

### 08_run_feature_ablation_splits.py (new v5 core script)

This script replaces the single-feature-set split evaluation role in v5.

It must:

1. Load v5 config.
2. Load `split_summary.csv`.
3. Load `split_training_samples.csv`.
4. Load NT mask and MVT labels.
5. Load all predictor rasters for full v4 feature inventory.
6. For each ablation experiment:
   - resolve experiment feature list,
   - for each accepted original split:
     - use the same v4-style training samples,
     - subset `X_train` to experiment features,
     - fit `StandardScaler + RandomForestClassifier` with fixed v4 hyperparameters,
     - score validation region,
     - score holdout region,
     - compute v4 metrics.
7. Save outputs with experiment metadata.

Scientific controls (must):

- Background samples must not be re-sampled per experiment.
- Split masks must not be regenerated per experiment.
- Model hyperparameters must not change per experiment.
- The only changing factor is feature subset.

Required row columns in `feature_ablation_metrics_by_split.csv`:

- `experiment_id`
- `experiment_label`
- `feature_mode`
- `feature_count`
- `included_features`
- `dropped_features`
- `split_id`
- `split_type`
- `holdout_candidate_id`
- `validation_candidate_id`
- `holdout_zone`
- `validation_zone`
- `holdout_zone_name`
- `validation_zone_name`
- `region`
- `region_zone_name`
- `pixels`
- `positives`
- `baseline_prevalence`
- `roc_auc`
- `average_precision`
- `ap_skill_vs_baseline`
- `top1_selected_pixels`
- `top1_captured_positives`
- `top1_recall`
- `top1_precision`
- `top1_enrichment`
- `top5_selected_pixels`
- `top5_captured_positives`
- `top5_recall`
- `top5_precision`
- `top5_enrichment`
- `top10_selected_pixels`
- `top10_captured_positives`
- `top10_recall`
- `top10_precision`
- `top10_enrichment`

Required aggregate files:

1. `feature_ablation_aggregate_metrics.csv`

Group by:
- `experiment_id`
- `experiment_label`
- `region`
- `metric`

Include:
- `split_count`
- `mean`
- `median`
- `std`
- `worst_min`
- `best_max`

2. `feature_ablation_by_holdout_candidate.csv`

Group by:
- `experiment_id`
- `holdout_candidate_id`
- `holdout_zone`
- `holdout_zone_name`

Include:
- `split_count`
- `mean_pixels`
- `mean_positives`
- `mean_baseline_prevalence`
- `mean_average_precision`
- `median_average_precision`
- `min_average_precision`
- `max_average_precision`
- `mean_roc_auc`
- `median_roc_auc`
- `mean_ap_skill_vs_baseline`
- `mean_top1_recall`
- `mean_top5_recall`
- `mean_top10_recall`
- `mean_top1_enrichment`
- `mean_top5_enrichment`
- `mean_top10_enrichment`

3. `feature_ablation_delta_vs_baseline.csv`

For each non-baseline experiment versus `full_baseline`.

Include:
- `experiment_id`
- `experiment_label`
- `region`
- `metric`
- `baseline_mean`
- `experiment_mean`
- `delta_mean`
- `pct_delta_mean` (where meaningful)
- `interpretation_flag`

Interpretation flags:
- `improved_vs_baseline`
- `worse_than_baseline`
- `approximately_equal`
- `unstable_or_nan`

4. `feature_ablation_validation_holdout_gap.csv`

Per experiment and split, include:
- `experiment_id`
- `split_id`
- `average_precision_validation`
- `average_precision_holdout`
- `ap_gap_difference`
- `ap_gap_ratio`
- `ap_skill_vs_baseline_validation`
- `ap_skill_vs_baseline_holdout`
- `skill_gap_difference`
- `skill_gap_ratio`

5. `feature_ablation_ranked_summary.csv`

Rank experiments by holdout performance.

Suggested columns:
- `rank_by_holdout_average_precision`
- `experiment_id`
- `experiment_label`
- `feature_count`
- `mean_holdout_average_precision`
- `mean_holdout_ap_skill_vs_baseline`
- `mean_holdout_top1_recall`
- `mean_holdout_top5_recall`
- `mean_holdout_top10_recall`
- `delta_holdout_ap_vs_full_baseline`
- `delta_holdout_top5_recall_vs_full_baseline`
- `notes`

### 09_train_final_random_forest.py

- Keep available for continuity.
- In v5, this is optional and should usually use full baseline feature set unless a pre-declared rule says otherwise.

### 10_predict_final_prospectivity.py

- Keep available for continuity.
- Any final map in v5 is optional and not primary evidence.

### 11_summarize_v5_outputs.py

Must produce:

- `final_score_summary_v5.csv` (if final map exists)
- `v5_model_review.txt`
- `feature_ablation_ranked_summary.csv` if not already produced by script `08`
- optional Markdown/text ranking table for human reading

`v5_model_review.txt` must include:

1. Run identity:
- run name
- objective = feature ablation study
- model family = RF only
- pixel size + CRS
- spatial buffer
- background sampling
- number of ablation experiments

2. Fixed-condition statement:
- same study area
- same labels
- same predictor inventory
- same split design
- same background sampling
- same model family
- same hyperparameters

3. Ablation experiment table:
- `experiment_id`
- included/dropped groups
- `feature_count`
- scientific question tested

4. Main ranking:
- holdout AP ranking
- holdout AP skill
- top 5% recall
- top 10% recall
- validation/holdout gap context

5. Delta vs baseline summary:
- improved / worse / approximately equal per experiment

6. Interpretation guidance:
- small improvements may be non-meaningful under high split variance,
- one metric alone should not drive feature removal,
- prefer changes that improve holdout AP and top-k recall without worsening gap,
- validation-up but holdout-down should be treated as possible geography-specific overfitting.

7. Mandatory claim limits (exact text required; see Section 14).

### 12_write_run_manifest.py

Keep v4 reproducibility mechanics (checksums + relative paths), and include all v5 ablation artifacts in `run_manifest_v5.json`.

Required v5 manifest artifacts:

- `v5_run_config.yml`
- `v5_run_config_snapshot.yml`
- `feature_ablation_metrics_by_split.csv`
- `feature_ablation_aggregate_metrics.csv`
- `feature_ablation_by_holdout_candidate.csv`
- `feature_ablation_delta_vs_baseline.csv`
- `feature_ablation_validation_holdout_gap.csv`
- `feature_ablation_ranked_summary.csv`
- `v5_model_review.txt`

## 10. Final Model and Final Map Policy (V5)

V5 is primarily an evaluation/ablation run, not a production-map redesign.

Policy:

- Final production model and final map are optional in v5.
- If produced, they should use `full_baseline` unless a different subset is chosen by a pre-declared rule before run freeze.
- Final map output must not be used as evidence that ablation improved generalization.
- Holdout evidence must come from split-level ablation outputs.

## 11. Non-Goals in V5

V5 non-goals:

- No new geological predictors.
- No new raster/vector processing beyond existing v4 predictors.
- No new model family.
- No XGBoost / LightGBM / neural network.
- No hyperparameter tuning.
- No probability calibration.
- No uncertainty map.
- No multi-resolution run.
- No change to spatial split design.
- No change to background sampling ratio.
- No new final prospectivity map for every ablation experiment.
- No claim that a higher ablation score is decision-grade exploration evidence.

## 12. V5 Success Criteria

V5 is successful when:

1. `full_baseline` reproduces the v4 reference feature set behavior.
2. All experiments use the same split masks.
3. All experiments use the same sampled background rows.
4. All experiments use the same RF hyperparameters.
5. The only changing factor is feature subset.
6. Outputs include per-split, aggregate, per-holdout-candidate, gap, delta-vs-baseline, and ranked-summary tables.
7. `v5_model_review.txt` clearly identifies which groups helped, hurt, or were unstable.
8. `run_manifest_v5.json` records all v5 ablation artifacts with relative paths and checksums.
9. Repository is ready for a concise README archive line after v5 is finished.

## 13. Implementation Guidance (Beginner-Friendly)

Recommended order:

1. Copy v4 config to `v5_run_config.yml` and add `ablation` section.
2. Update `00_config.py` path names and ablation validation.
3. Implement script `08` first because it is the core v5 scientific output.
4. Implement script `11` report and ranking logic.
5. Extend script `12` manifest artifact list.
6. Keep all other scripts unchanged unless a strict compatibility fix is needed.

Why this order:

- V5 evidence is produced by script `08` tables.
- Script `11` explains the evidence.
- Script `12` makes the evidence reproducible and auditable.

## 14. Mandatory Claims Language (Use Exact Text)

All v5 summary/report outputs must include exactly:

```text
Scores are relative prospectivity rankings, not calibrated deposit probabilities.
Holdout evidence comes from split evaluation, not from the final production model.
V5 compares feature subsets under fixed V4 conditions; it does not prove geological causality.
Ablation results are screening evidence only and should be interpreted with geological judgment.
```

## 15. Suggested README Archive Entry Template (For Later)

```text
- YYYY-MM-DD HH:MM:SS +0330 - Archived `v5` in `archive/v5/`: feature ablation run using the v4 spatial evaluation framework. Baseline feature set = V4 full feature set. Ablation experiments = [N]. Best/worst feature subsets by holdout AP/top-k recall summarized in `feature_ablation_ranked_summary.csv`. Major limitations: no new geological features, no probability calibration, no uncertainty map; scores are relative prospectivity rankings, not deposit probabilities.
```
