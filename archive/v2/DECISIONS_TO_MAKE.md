# Decisions To Make For The Mineral Prospectivity Pipeline

Created: 2026-05-11

This document lists the decisions that should be made before and during the next versions of the Northern Territory MVT prospectivity workflow. It is based on the v1 run and the external review comments.

The key correction is this: v1 already had a spatial train/test split, but it did not have a full train/validation/holdout framework. The next version should focus on evaluation design before model complexity.

## Current V1 Baseline

V1 achieved an end-to-end pipeline:

- 500 m Northern Territory ROI and aligned predictor rasters.
- MVT label raster and sampled training table.
- Random Forest model.
- Prospectivity raster and top-5% raster.
- Archived run under `archive/v1/`.

V1 should be treated as a baseline only:

- ROC AUC was high enough to suggest some ranking signal.
- Average precision was low.
- Positive-class recall at the default classification threshold was 0.00.
- The default threshold of 0.5 is not meaningful for this rare-event problem.

## Decision Gates

### Gate 1: Scientific Objective

Make this decision before changing the pipeline.

Decision: What is the purpose of the next run?

Options:

- Learning workflow: optimize for clarity and repeatability.
- Screening map: identify broad prospective areas for review.
- Target generation: prioritize a limited number of areas for follow-up.
- Scientific benchmark: produce defensible model evaluation.

Choice:

- Learning Workflow, screening map, and scientific benchmark.

Why:

- The current weak point is not the Random Forest itself. The weak point is whether evaluation and thresholding are defensible.

Record:

- Primary goal.
- What output will count as success.
- What output must not be claimed.

### Gate 2: Study Area And Resolution

Make this decision before generating new rasters or splits.

Decision: Should v2 stay at Northern Territory and 500 m pixels?

Options:

- Keep NT at 500 m.
- Change pixel size.
- Expand beyond NT.
- Restrict to geological subregions inside NT.

Choice:

- Keep NT at 500 m.

Why:

- Changing geography or resolution before fixing evaluation makes results harder to interpret.

Record:

- ROI boundary.
- CRS.
- Pixel size.
- Mask rules.

### Gate 3: Label Definition

Make this decision before creating splits.

Decision: What counts as a positive MVT label?

Options:

- All Australian MVT points inside NT.
- Deposits only, excluding prospects.
- High-confidence records only.
- Buffered occurrence zones instead of one positive pixel per point.

Choice:

- All Australian MVT points inside NT

Important:

- Multiple points can fall in one 500 m pixel.
- Known occurrence locations are labels only, never predictors.

Record:

- Source fields used.
- Number of source rows.
- Number inside NT.
- Number of unique positive pixels.
- Any records excluded and why.

### Gate 4: Background Or Negative Sampling

Make this decision before building the training table.

Decision: How should unlabeled pixels be treated?

Options:

- Background sampling: unlabeled pixels are background, not proven negatives.
- Pseudo-absence sampling: sample pixels assumed unlikely to host deposits.
- Positive-unlabeled framing: explicitly treat unlabeled pixels as unknown.

Choice:

- Continue with background sampling, but document that background does not mean barren.

<!-- Additional decision:

- Should background sampling be spatially stratified?

Choice:

- Yes. Sample background across spatial blocks so one region does not dominate training. -->

Record:

- Background-to-positive ratio.
- Random seed.
- Whether background was spatially stratified.
- Whether background was sampled only from training regions.

### Gate 5: Spatial Split Strategy

Make this decision before training any v2 model.

Decision: What train/validation/holdout structure should be used?

Options:

- Single spatial train/test split.
- Train/validation/holdout split.
- Repeated train/validation/holdout splits.
- Leave-one-region-out evaluation.

Choice:

- Repeated spatial train/validation/holdout splits.

Why:

- One split can be lucky or unlucky.
- A validation set is needed for threshold and model decisions.
- A holdout set must remain untouched for final reporting.

Record:

- Split method.
- Number of candidate splits generated.
- Number of accepted splits.
- Reasons rejected splits were rejected.

### Gate 6: Split Constraints

Make this decision before writing the split generator.

Decision: What makes a split acceptable?

Candidate v2 rules:

- Holdout area: 10-20% of valid pixels.
- Validation area: 10-20% of valid pixels.
- Holdout positives: at least 5 positive pixels.
- Validation positives: at least 5 positive pixels.
- Training positives: at least 40 positive pixels.
- Validation and holdout do not overlap.
- Optional spatial buffer between train and validation/holdout.

Tradeoff:

- Stricter rules give cleaner evaluation but may produce too few valid splits.
- Looser rules give more splits but less reliable metrics.

Choice:

- Strict rules: 
    - Holdout area: 10% of valid pixels
    - Validation area: 10% of valid pixels.
    - Holdout positives: at least 5 positive pixels.
    - Validation positives: at least 5 positive pixels.
    - Training positives: at least 40 positive pixels.
    - Validation and holdout do not overlap.

Record:

- Area limits.
- Minimum positive counts.
- Buffer distance.
- Whether buffer pixels are removed or ignored during scoring.

### Gate 7: Split Geometry

Make this decision before implementation.

Decision: What shape should validation and holdout regions use?

Options:

- Square blocks.
- Rectangular blocks.
- Hexagonal tiles.
- Geological regions.
- Administrative/geographic regions.

Recommended v2 choice:

- Square blocks

<!-- Future option:

- Geological regions may be more meaningful once the basic evaluation system is stable. -->

Record:

- Shape type.
- Size or target area.
- How candidate blocks are generated.
- Whether blocks are allowed to touch the ROI edge.

### Gate 8: Holdout Discipline

Make this decision before looking at v2 holdout results.

Decision: What is allowed to influence modeling choices?

Rules:

- Training data can fit the model.
- Validation data can choose features, hyperparameters, model type, and threshold.
- Holdout data is used only for final reporting.

Not allowed:

- Choosing the split with the best holdout score.
- Changing features after seeing holdout failures.
- Changing threshold based on holdout performance.
- Repeatedly inspecting holdout maps to guide modeling decisions.

Choice:

- Freeze split rules before training and evaluate all accepted splits.

Record:

- Date split definitions were frozen.
- Any accidental holdout inspection.
- Any reason a split was removed after generation.

### Gate 9: Metrics

Make this decision before training v2.

Decision: Which metrics will be used to judge progress?

Do not rely on:

- Accuracy.
- Default-threshold classification report alone.

Recommended primary metrics:

- Average precision / PR-AUC.
- Recall in top 1%, 5%, and 10% of predicted area.
- Precision in top 1%, 5%, and 10% of predicted area.
- Lift or enrichment factor in top 1%, 5%, and 10%.
- Number of positive pixels captured in top 1%, 5%, and 10%.

Secondary metrics:

- ROC AUC.
- Calibration diagnostics.
- Feature stability.

Record:

- Primary metric.
- Secondary metrics.
- Why those metrics match the project objective.

### Gate 10: Thresholding

Make this decision after validation results, before holdout reporting.

Decision: How should high-prospectivity zones be selected?

Options:

- Top-k% area threshold.
- Threshold that reaches a target validation recall.
- Threshold that reaches a target validation precision.
- Budget-based threshold, such as top N square kilometers.
- No binary threshold, ranking map only.

Choice:

- Use top-k% area thresholds first: top 1%, top 5%, and top 10%.

Why:

- Mineral prospectivity is usually a prioritization problem, not a 0.5 binary classification problem.

Record:

- Thresholding method.
- Threshold selected from validation only.
- Area selected.
- Positives captured on validation and holdout.

### Gate 11: Predictor Set

Make this decision before each new model run.

Decision: Which predictors are allowed?

Allowed v1-style predictors:

- Lithology code.
- Carbonate host indicator.
- Distance to faults.
- Gravity and magnetic rasters.
- Moho and LAB depth.
- Shape index.

Forbidden predictors:

- Distance to known MVT occurrences.
- Existing Lawley MVT prospectivity model as a training predictor.
- Any raster created from labels.

Possible v2 additions:

- Distance to lithological contacts.
- Fault density.
- Contact density.
- Basin or carbonate basin indicators.
- Geophysical gradients.
- Local texture or window statistics.

Choice:

- Add no new predictors until the spatial evaluation framework works. Implement evaluation using the v1 predictor set.

Record:

- Predictor name.
- Source.
- Unit.
- Transformation.
- Missing-value handling.
- Geological reason for inclusion.

### Gate 12: Coordinate Use

Make this decision before model training.

Decision: Should raw `x` and `y` coordinates be used as model features?

Choice:

- Do not use coordinates as predictors in the main model.

Why:

- Coordinates can let the model memorize geography instead of learning geological relationships.

Allowed use:

- Coordinates are needed for spatial splits, maps, and reporting.

Optional experiment:

- Run a separate diagnostic model with coordinates and clearly label it as a leakage-risk comparison.

Record:

- Whether coordinates were used.
- If used, why.
- Results with and without coordinates.

### Gate 13: Preprocessing And Leakage

Make this decision before adding scaling, imputation, smoothing, or feature engineering.

Decision: Which operations are global GIS preprocessing and which are learned ML preprocessing?

Usually acceptable as global GIS preprocessing:

- Reprojecting.
- Resampling to template.
- Raster alignment.
- Clipping to ROI.
- Distance-to-fault raster creation from source faults.

Must be fit on training only if used:

- Scaling.
- Imputation from data statistics.
- Feature selection.
- Calibration.
- PCA or learned transformations.

Choice:

- Keep preprocessing simple and avoid learned transformations until the split framework is stable.

Record:

- Each preprocessing step.
- Whether it uses label information.
- Whether it is fit globally or on training only.

### Gate 14: Model Choice

Make this decision after the evaluation framework exists.

Decision: Which model families should be compared?

Options:

- Random Forest.
- Logistic regression.
- Shallow decision tree.
- Gradient boosting.
- Calibrated versions of the above.

Choice:

- Keep Random Forest as the main baseline.

Why:

- A simple baseline shows whether the complex model is adding value.

Record:

- Model type.
- Hyperparameters.
- Random seed.
- Training rows.
- Validation and holdout metrics.

### Gate 15: Hyperparameter Tuning

Make this decision after train/validation/holdout splits exist.

Decision: How much tuning is allowed?

Options:

- No tuning: fixed baseline parameters.
- Small manual grid.
- Automated search.

Choice:

- Use fixed Random Forest parameters.

Rule:

- Hyperparameters must never be chosen from holdout performance.

Record:

- Search space.
- Validation metric used.
- Selected parameters.
- Whether holdout was untouched.

### Gate 16: Calibration

Make this decision after ranking metrics are understood.

Decision: Should scores be calibrated?

Options:

- No calibration; interpret scores as relative ranking only.
- Platt calibration using validation.
- Isotonic calibration using validation.

Choice:

- If by calibrations you mean putting feature values within a range that can be compared later on, most certainly we need to do so.

Future option:

- Add calibration only if probability interpretation becomes important.

Record:

- Calibration method.
- Data used to fit calibration.
- Calibration curves.
- Whether ranking metrics improved or worsened.

### Gate 17: Final Map Strategy

Make this decision after repeated split evaluation.

Decision: What map should be presented as the final v2 output?

Options:

- Single model trained on all development data.
- Ensemble mean map from repeated split models.
- Stability map showing how often pixels appear in top-k%.
- Mean plus uncertainty maps.

Recommended v2 choice:

- Produce only a single model for now

Record:

- Final training data used.
- Whether a locked holdout was excluded.
- Number of models in ensemble or stability map.
- Top-k% consensus rule.

### Gate 18: Uncertainty

Make this decision after multiple split models exist.

Decision: How should uncertainty be shown?

Options:

- Standard deviation of prospectivity scores across split models.
- Frequency of top 5% selection across split models.
- Worst-case and best-case rank maps.
- No uncertainty map.

Choice:

- No uncertainty map for now.

Record:

- Number of models used.
- Uncertainty metric.
- Interpretation.

### Gate 19: Interpretation

Make this decision after holdout evaluation.

Decision: How should model drivers be explained?

Options:

- Built-in Random Forest impurity importance.
- Permutation importance on validation or holdout.
- SHAP values.
- Feature stability across splits.

Choice:

- I don't know. We go with Built-in RF now, and later on we adjust.

Why:

- Built-in RF importance can be biased and unstable.

Record:

- Importance method.
- Data used.
- Top features.
- Whether top features are geologically plausible.

### Gate 20: Reporting Language

Make this decision before updating README or sharing maps.

Decision: What claims are allowed?

Allowed:

- The model ranks areas by similarity to known MVT occurrences based on selected predictors.
- Top-k zones capture a stated number or percentage of known occurrences under spatial holdout evaluation.
- Results are screening outputs requiring geological review.

Not allowed:

- The model predicts true deposit probability unless calibrated and validated for that purpose.
- High score means an ore deposit exists.
- Background pixels are confirmed barren.

Choice:

- "Prospectivity score" or "relative prospectivity ranking", not "probability of deposit".

Record:

- Claims made.
- Metrics supporting those claims.
- Known limitations.

### Gate 21: Archive And Reproducibility

Make this decision before each major run.

Decision: What should be archived?

Choice:

- Scripts.
- Workflow document.
- Config.
- Split definitions.
- Metrics.
- Feature importance.
- Output tables.
- Final maps like V1.
- README excerpt with date, time, and caveats.
- A machine-readable run config file for CRS, pixel size, predictors, split rules, seeds, and model parameters.

Record:

- Run ID.
- Date and time.
- Commit hash if available.
- Input data version.
- Random seeds.
- Output paths.

## Suggested V2 Decision Sequence

1. Define the v2 objective.
2. Keep NT and 500 m unless there is a strong reason to change them.
3. Freeze the positive label definition.
4. Choose background sampling rules.
5. Define spatial split constraints.
6. Generate candidate train/validation/holdout splits.
7. Accept all splits that satisfy predefined rules.
8. Choose metrics before training.
9. Train v1-style Random Forest across accepted splits.
10. Select thresholds using validation only.
11. Report holdout metrics across all accepted splits.
12. Only then decide whether to add features or compare models.
13. Produce final map and stability map.
14. Archive v2 with metrics, scripts, configs, and caveats.

## Open Decisions For The Next Conversation

These should be answered before implementing v2:

- What is the v2 objective: benchmark, screening map, or target-prioritization tool?
- Should v2 keep NT at 500 m?
- What minimum positive count should validation and holdout regions require: 5, 7, or 10?
- Should candidate split blocks be square, rectangular, or geological regions?
- Should a buffer be used between train and validation/holdout regions? If yes, how many kilometers?
- Should background sampling be random across the training region or spatially stratified?
- Which top-area thresholds should be reported: top 1%, 5%, 10%, or a fixed area budget?
- Should v2 add any new predictors, or first evaluate the current predictor set honestly?
- Should the final output be a single model, an ensemble mean, a stability map, or all three?

## Decision Log Template

Use this template each time a decision is made:

```text
Date:
Run/version:
Decision:
Options considered:
Choice:
Reason:
Evidence used:
Risks:
What this decision affects:
Can this be changed later:
```

## Research Decision Table

Use this table as the compact checklist before starting v2.

### Your V2 Choices

| Gate | Question | Your decision | Status | Implementation note | Friend review note |
| ---: | --- | --- | --- | --- | --- |
| 1 | What is the purpose of the next run? | Learning workflow, screening map, and scientific benchmark. | Chosen | Treat scientific benchmark as the primary v2 goal and screening map as secondary. | Objective is slightly broad; make scientific benchmark primary. |
| 2 | Should v2 stay at Northern Territory and 500 m pixels? | Keep NT at 500 m. | Chosen | Keep `EPSG:3577` and the 500 m template unless a later run explicitly changes them. | Good v2 path: keep NT at 500 m. |
| 3 | What counts as a positive MVT label? | All Australian MVT points inside NT. | Chosen | Record source rows, NT rows, and unique positive pixels after rasterization. | Evaluation should count unique positive pixels, not duplicate occurrence points, unless weighting is intentional. |
| 4 | How should unlabeled pixels be treated? | Continue with background sampling; document that background does not mean barren. | Chosen | Background pixels are unlabeled comparison samples, not proven barren locations. | Good: unlabeled does not mean barren. |
| 4a | Should background sampling be spatially stratified? | Use spatially stratified background sampling. | Chosen | Sample background pixels across split/train spatial blocks so one region does not dominate training. | Good decision; reduces regional sampling bias. |
| 5 | What train/validation/holdout structure should be used? | Repeated spatial train/validation/holdout splits. | Chosen | Generate many candidate splits and evaluate every split that passes predefined rules. | Strong choice; freeze rules before training and evaluate all accepted splits. |
| 6 | What makes a split acceptable? | Strict rules: holdout 10%, validation 10%, at least 5 holdout positives, at least 5 validation positives, at least 40 training positives, no validation/holdout overlap, no buffer. | Chosen | If too few splits pass, use the predefined fallback policy before changing model choices. | Strict rules may produce too few valid splits; define fallback rules before modeling. |
| 6a | What fallback split policy applies if strict rules fail? | Not yet chosen. | Needs decision | Suggested fallback order: widen validation/holdout area range to 8-20%, then allow minimum positives 4-5, then revisit buffer/geometry only if needed. | Add fallback policy before modeling so split design is not performance-driven. |
| 6b | What minimum accepted split count is required? | Not yet chosen. | Needs decision | Suggested rule: target at least 10 accepted splits; if fewer than 5, label v2 evaluation exploratory. | Repeated evaluation only helps if enough valid splits exist. |
| 6c | How should candidate block area be measured near the NT boundary? | Not yet chosen. | Needs decision | Measure area by valid pixels inside the ROI, not raw square area. | Square blocks near irregular boundaries may otherwise have misleading area. |
| 7 | What shape should validation and holdout regions use? | Square blocks. | Chosen | Start with square blocks; geological regions can be a later experiment. | Acceptable; keep simple for v2. |
| 8 | What is allowed to influence modeling choices? | Freeze split rules before training and evaluate all accepted splits. | Chosen | Candidate splits may be selected by geography, area, and label balance only, never model score. | Worth emphasizing: split selection must not use model performance. |
| 9 | Which metrics will be used to judge progress? | Use the suggested default metrics. | Chosen | Use PR-AUC, top-k recall/precision, enrichment, captured positives, and ROC AUC as secondary. | Good; add median and worst-case across splits. |
| 9a | How should repeated split metrics be aggregated? | Not yet chosen. | Needs decision | Suggested reporting: mean, median, standard deviation, minimum/worst split, and split count. | Define aggregation clearly; do not report only mean performance. |
| 10 | How should high-prospectivity zones be selected? | Top-k area thresholds: top 1%, top 5%, and top 10%. | Chosen | Report fixed top-k values across all splits; do not optimize top-k using holdout. | Good; holdout must not be used for threshold optimization. |
| 11 | Which predictors are allowed? | Add no new predictors until the spatial evaluation framework works; use v1 predictors first. | Chosen | This is the right sequencing. Evaluate honestly before feature expansion. | Keep v2 focused on evaluation, not new predictors/models. |
| 11a | How will occurrence-point leakage be checked? | Not yet chosen. | Needs decision | Confirm no predictor raster is derived from MVT labels, known occurrence proximity, or existing MVT prospectivity outputs. | Important leakage check for mineral datasets. |
| 12 | Should raw x/y coordinates be model features? | Do not use coordinates in the main model. | Chosen | Coordinates remain allowed for splitting, sampling, and reporting. | Consistent with leakage control. |
| 13 | Which preprocessing is global GIS preprocessing vs learned ML preprocessing? | Keep preprocessing simple and avoid learned transformations until the split framework is stable. | Chosen | Alignment, clipping, and fixed GIS derivatives are acceptable globally; learned transforms must be train-only. | Good; keep leakage boundaries explicit. |
| 14 | Which model families should be compared? | Keep Random Forest as the main baseline. | Chosen | Do not add model comparison until the spatial evaluation engine works. | Strongest v2 path is fixed RF after evaluation design is frozen. |
| 15 | How much hyperparameter tuning is allowed? | Use fixed Random Forest parameters. | Chosen | This keeps v2 focused on evaluation rather than tuning. | Consistent with evaluation-first strategy. |
| 16 | Should scores be calibrated? | Do not calibrate scores for v2; use feature scaling only if the selected model requires it. | Chosen | Random Forest does not normally need feature scaling. Calibration means adjusting model scores to behave like probabilities; that is not a v2 goal. | Good final decision; RF usually does not need scaling. |
| 17 | What final map should be presented? | Produce only a single model for now. | Chosen | Use repeated spatial split models for evaluation only. After evaluation, train one final RF using the fixed v2 recipe to produce the v2 screening map. | This resolves the mild tension between repeated evaluation and one final map. |
| 17a | What is the final model training rule? | Not yet chosen. | Needs decision | Suggested rule: after evaluation, train final RF on all eligible NT data using the frozen v2 recipe; the final map is not itself holdout evidence. | Add a clean rule for the single final map. |
| 18 | How should uncertainty be shown? | No uncertainty map for now. | Chosen | Clearly document no uncertainty map as a v2 limitation. | Acceptable, but archive split-to-split variability in CSV. |
| 18a | Should split-to-split variability be archived? | Not yet chosen. | Needs decision | Suggested output: CSV with per-split metrics and aggregate mean/median/std/worst values. | Minimum useful uncertainty record even without uncertainty maps. |
| 19 | How should model drivers be explained? | Use built-in Random Forest importance for now; adjust later. | Chosen with caveat | Built-in RF importance is a quick diagnostic, not scientific evidence. | Later use permutation importance on validation/holdout. |
| 20 | What claims are allowed? | Use "prospectivity score" or "relative prospectiviy ranking", not "probability of deposit". | Chosen | This wording should be preserved everywhere. | Excellent; keep this wording in README, reports, and map descriptions. |
| 21 | What should be archived? | Scripts, workflow document, config, split definitions, metrics, feature importance, output tables, final maps, README excerpt, and machine-readable run config. | Chosen | Also archive split definitions, per-split metrics, fallback settings, and run caveats. | Good reproducibility target for v2. |
