# V3 Logic-to-Script Map and V4 Improvement Guide

This document maps your ML-for-MPM logic to the actual v3 implementation in this repo, then suggests practical v4 improvements for each step.

## Is Your Logic Good?

Yes. Your logic is strong and follows a standard, defensible MPM workflow:

`study area + deposit model -> evidence layers -> preprocessing/alignment -> labels -> spatial splits -> sampling -> training -> evaluation -> final model -> map -> interpretation/uncertainty`

The main improvement is to make the uncertainty part explicit in code outputs (not just narrative), which is currently a known gap in v3.

## Step-by-Step Mapping

## 1) Study area + deposit model

### Related v3 files

- `archive/v3/scripts/00_config.py`
- `archive/v3/scripts/01_make_roi_and_template.py`
- `archive/v3/scripts/05_make_mvt_labels.py`
- `archive/v3/configs/v3_run_config.yml`
- `archive/v3/PROJECT_WORKFLOW_NT_MVT_500M_V3.md`

### What v3 does now

- Defines NT as the study area and EPSG:3577 / 500 m grid.
- Filters occurrences to Australian MVT records.
- Builds NT boundary and template mask.

### V4 improvements

- Add a machine-readable "deposit model criteria" section in config (commodities, deposit keywords, certainty filters).
- Save a label provenance table (which source rows were kept or excluded, and why).
- Version-pin raw inputs with checksums for reproducibility.

## 2) Evidence-layer selection

### Related v3 files

- `archive/v3/configs/v3_run_config.yml`
- `archive/v3/scripts/00_config.py`
- `archive/v3/scripts/02_process_continuous_rasters.py`
- `archive/v3/scripts/03_process_vector_predictors.py`
- `archive/v3/scripts/04_check_raster_stack.py`

### What v3 does now

- Uses fixed v1 predictor set.
- Stores active feature list in YAML.
- Applies leakage keyword checks and stack alignment checks.

### V4 improvements

- Add a feature registry CSV with geological rationale per layer.
- Add ablation tests (drop-one-feature-group) to measure marginal value.
- Add explicit leakage tests beyond name checks (data lineage checks).

## 3) Spatial preprocessing/alignment

### Related v3 files

- `archive/v3/scripts/01_make_roi_and_template.py`
- `archive/v3/scripts/02_process_continuous_rasters.py`
- `archive/v3/scripts/03_process_vector_predictors.py`
- `archive/v3/scripts/04_check_raster_stack.py`

### What v3 does now

- Builds one template grid and aligns all rasters to it.
- Converts vectors to rasters and creates distance-to-faults.
- Enforces shared CRS/transform/shape before modeling.

### V4 improvements

- Add automated QA report per raster (coverage %, NoData %, min/max, histogram sketch).
- Add sensitivity checks for rasterization choices (`all_touched=True/False`).
- Add optional preprocessing variants (normalization, clipping, transforms) tracked in config.

## 4) Label construction

### Related v3 files

- `archive/v3/scripts/05_make_mvt_labels.py`

### What v3 does now

- Creates binary pixel labels from NT MVT points.
- Collapses multiple nearby points into single positive pixels.

### V4 improvements

- Add label-quality flags (producer/prospect/showing confidence tiers if available).
- Add experiments with soft labels or buffered positives.
- Add exclusion rules for uncertain or duplicate records.

## 5) Spatial train/validation/holdout design

### Related v3 files

- `archive/v3/scripts/06_make_spatial_splits.py`
- `archive/v3/data/processed/splits/split_summary.csv`

### What v3 does now

- Creates repeated non-overlapping spatial blocks.
- Enforces strict/fallback area and positive-count constraints.
- Produces accepted split masks and split summary table.

### V4 improvements

- Add spatial buffer option between train/validation/holdout.
- Add alternative split families (leave-one-subregion-out, larger blocks, rotated grids).
- Add randomized candidate ordering to reduce structural bias in accepted splits.

## 6) Sampling/background strategy

### Related v3 files

- `archive/v3/scripts/07_build_split_training_samples.py`
- `archive/v3/scripts/09_train_final_random_forest.py`
- `archive/v3/scripts/00_config.py` (ratio settings)

### What v3 does now

- Uses stratified background sampling by coarse spatial blocks.
- Uses fixed background-per-positive ratio.

### V4 improvements

- Compare multiple class-balance ratios with split-based model selection.
- Add target-group background strategy (exclude geologically impossible areas if justified).
- Add "hard negative" refresh strategy from high-scoring false positives.

## 7) Model training

### Related v3 files

- `archive/v3/scripts/08_evaluate_random_forest_splits.py`
- `archive/v3/scripts/09_train_final_random_forest.py`
- `archive/v3/configs/v3_run_config.yml`

### What v3 does now

- Uses fixed scaler + RandomForest pipeline.
- Trains one model per split for evaluation and one final model for mapping.

### V4 improvements

- Add nested spatial tuning (inside training only) to avoid leakage.
- Compare at least one additional baseline (for example, XGBoost/LightGBM with same split logic).
- Add probability calibration stage trained only on validation partitions.

## 8) Spatial evaluation

### Related v3 files

- `archive/v3/scripts/08_evaluate_random_forest_splits.py`
- `archive/v3/data/processed/models/metrics_by_split.csv`
- `archive/v3/data/processed/models/aggregate_metrics.csv`

### What v3 does now

- Reports validation and holdout ROC-AUC, PR-AUC, top-k recall/precision/enrichment.
- Aggregates across splits with mean/median/std/min/max.

### V4 improvements

- Add confidence intervals (bootstrap over splits and/or positives).
- Add threshold curves and calibration curves.
- Add formal baseline comparison tests across identical split masks.

## 9) Final model

### Related v3 files

- `archive/v3/scripts/09_train_final_random_forest.py`
- `archive/v3/data/processed/models/final_random_forest_mvt.joblib`
- `archive/v3/data/processed/models/final_feature_importance.csv`

### What v3 does now

- Trains final map-production model on all usable positives + sampled background.
- Exports feature importances.

### V4 improvements

- Consider split-ensemble final model (average predictions from multiple fitted models).
- Export a model card with frozen config, data counts, and intended use.
- Add reproducibility manifest (seed, commit hash, input checksums).

## 10) Prospectivity prediction map

### Related v3 files

- `archive/v3/scripts/10_predict_final_prospectivity.py`
- `archive/v3/scripts/11_summarize_v3_outputs.py`
- `archive/v3/outputs/maps/`

### What v3 does now

- Predicts pixelwise prospectivity scores on NT.
- Produces top 1/5/10% binary selection maps.

### V4 improvements

- Add map post-processing products: quantile classes, ranked target polygons, optional smoothing test.
- Add per-pixel support masks (where features were missing or extrapolation risk is high).
- If calibration is added, publish both rank score and calibrated probability products.

## 11) Interpretation/uncertainty

### Related v3 files

- `archive/v3/scripts/11_summarize_v3_outputs.py`
- `archive/v3/outputs/tables/v3_model_review.txt`

### What v3 does now

- Produces textual interpretation summary and key limitations.
- Does not produce a spatial uncertainty map.

### V4 improvements

- Build split-variance uncertainty raster (prediction variability across split models).
- Add confidence classes combining score + uncertainty.
- Add explicit decision guidance: what "high score, high uncertainty" vs "high score, low uncertainty" means operationally.

## Recommended V4 Priority Order

1. Add uncertainty map from split-model prediction variance.
2. Add spatial buffer experiments in split generation.
3. Add nested spatial hyperparameter tuning.
4. Add feature ablation study.
5. Add calibration diagnostics and optional calibrated output.

