# mineral-prospectivity-mvp

The data for this project comes from the following source:

https://www.sciencebase.gov/catalog/item/6193e9f3d34eb622f68f13a5

The initial goal is to perform machine learning on Australian portion of this data on MVT deposits in the Northern Territory region.

## Run Archive

- 2026-05-14 19:38:05 +0330 - Archived `v3` in `archive/v3/`: accepted splits = 10 (non-exploratory). Holdout aggregate PR-AUC (average precision, mean across splits) = 0.000256. Holdout top-area capture (mean recall across splits): top 1% = 0.0533, top 5% = 0.4500, top 10% = 0.6000. Feature scaling method: StandardScaler. Major limitations: no spatial buffer, no probability calibration, no uncertainty map; scores are relative prospectivity rankings, not deposit probabilities.

- 2026-05-13 22:01:54 +0330 - Archived `v2` in `archive/v2/`: accepted splits = 10 (non-exploratory). Holdout aggregate PR-AUC (average precision, mean across splits) = 0.000132. Holdout top-area capture (mean recall across splits): top 1% = 0.0167, top 5% = 0.3500, top 10% = 0.5500. Major limitations: no spatial buffer, no probability calibration, no uncertainty map; scores are relative prospectivity rankings, not deposit probabilities.

- 2026-05-10 21:43:39 +0330 - Archived `v1` in `archive/v1/`: first end-to-end Northern Territory MVT 500 m workflow with aligned predictors, labels, training table, Random Forest model, prospectivity map, and top-5% map. Test ROC AUC was 0.8900 and average precision was 0.0647, but positive-class recall was 0.00, so this is a baseline run rather than a validated discovery model.

## How Each Run Actually Executed

### V3 (newest run, config-and-scaling workflow)

```text
01_make_roi_and_template.py
  -> Built NT boundary and 500 m template mask in EPSG:3577.
02_process_continuous_rasters.py
  -> Aligned continuous geophysics rasters to the template.
03_process_vector_predictors.py
  -> Built vector-derived predictors (carbonate host, lithology code, distance to faults).
04_check_raster_stack.py
  -> Verified predictor alignment and leakage checks before modeling.
05_make_mvt_labels.py
  -> Built MVT point layer and raster labels.
06_make_spatial_splits.py
  -> Generated repeated spatial train/validation/holdout split masks.
07_build_split_training_samples.py
  -> Built per-split training samples from train regions only.
08_evaluate_random_forest_splits.py
  -> Loaded v3 YAML run-config, enforced coordinate exclusion + StandardScaler, trained one RF per split, and scored validation/holdout.
09_train_final_random_forest.py
  -> Trained one final RF pipeline (same v3 config and scaling rules) for map production.
10_predict_final_prospectivity.py
  -> Predicted final NT prospectivity raster with the final RF pipeline.
11_summarize_v3_outputs.py
  -> Created top 1/5/10% maps and v3 review/output summary tables.
```

### V2 (evaluation-first workflow)

```text
01_make_roi_and_template.py
  -> Built NT boundary and 500 m template mask in EPSG:3577.
02_process_continuous_rasters.py
  -> Aligned continuous geophysics rasters to the template.
03_process_vector_predictors.py
  -> Built vector-derived predictors (carbonate host, lithology code, distance to faults).
04_check_raster_stack.py
  -> Verified predictor alignment and leakage checks before modeling.
05_make_mvt_labels.py
  -> Built MVT point layer and raster labels.
06_make_spatial_splits.py
  -> Generated repeated spatial train/validation/holdout split masks.
07_build_split_training_samples.py
  -> Built per-split training samples from train regions only.
08_evaluate_random_forest_splits.py
  -> Trained one RF per split and scored validation/holdout; wrote per-split and aggregate metrics.
09_train_final_random_forest.py
  -> Trained one final RF on the frozen v2 recipe for map production.
10_predict_final_prospectivity.py
  -> Predicted final NT prospectivity raster with the final RF.
11_summarize_v2_outputs.py
  -> Created top 1/5/10% maps and v2 review/output summary tables.
```

### V1 (baseline run)

```text
01_make_roi_and_template.py
  -> Built NT boundary and 500 m template mask.
02_process_continuous_rasters.py
  -> Aligned continuous geophysics rasters to the template.
03_process_vector_predictors.py
  -> Built vector-derived predictors.
04_check_raster_stack.py
  -> Verified all predictor rasters matched the template.
05_make_mvt_labels.py
  -> Built MVT point layer and raster labels.
06_build_training_table.py
  -> Built one training table with positives + sampled background.
07_train_random_forest.py
  -> Performed one spatial train/test split and trained/evaluated RF.
08_predict_prospectivity.py
  -> Predicted NT prospectivity raster.
09_summarize_outputs.py
  -> Created top-5% map and output summary tables.
```

In short: V1 was a single-split baseline flow; V2 kept most preprocessing but replaced the single model evaluation with repeated spatial split evaluation, then trained one final model for the screening map; V3 kept that evaluation-first structure and added a centralized YAML run-config plus mandatory feature scaling and explicit coordinate exclusion.
