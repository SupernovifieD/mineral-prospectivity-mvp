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

Recommended v2 choice:

- Scientific benchmark plus screening map.

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

Recommended v2 choice:

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

Recommended v2 choice:

- Start with all NT MVT occurrence pixels, but produce a count of deposits vs prospects if the source fields support it.

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

Recommended v2 choice:

- Continue with background sampling, but document that background does not mean barren.

Additional decision:

- Should background sampling be spatially stratified?

Recommended v2 choice:

- Yes. Sample background across spatial blocks so one region does not dominate training.

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

Recommended v2 choice:

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

Recommended v2 choice:

- Start with loose but explicit rules, then report how many valid splits are found.

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

- Start with square or rectangular blocks because they are easiest to implement and audit.

Future option:

- Geological regions may be more meaningful once the basic evaluation system is stable.

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

Recommended v2 choice:

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

Recommended v2 choice:

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

Decision:

- Add no new predictors until the spatial evaluation framework works, or add a very small number of geologically justified predictors.

Recommended v2 choice:

- First implement evaluation using the v1 predictor set. Then add features one group at a time.

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

Recommended v2 choice:

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

Recommended v2 choice:

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

Recommended v2 choice:

- Keep Random Forest as the main baseline.
- Add a simple logistic regression baseline after split evaluation works.

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

Recommended v2 choice:

- Use fixed Random Forest parameters first. Add limited validation-only tuning later.

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

Recommended v2 choice:

- Do not calibrate initially. Report scores as relative prospectivity rankings.

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

- Produce both a final single-model map and a stability/consensus map.

Why:

- The single model is simple.
- The stability map shows which areas are robust across split choices.

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

Recommended v2 choice:

- Top-5% selection frequency plus score standard deviation.

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

Recommended v2 choice:

- Use permutation importance on validation first.
- Treat built-in RF importance as secondary.

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

Recommended v2 wording:

- "Prospectivity score" or "relative prospectivity ranking", not "probability of deposit".

Record:

- Claims made.
- Metrics supporting those claims.
- Known limitations.

### Gate 21: Archive And Reproducibility

Make this decision before each major run.

Decision: What should be archived?

Recommended archive contents:

- Scripts.
- Workflow document.
- Config.
- Split definitions.
- Metrics.
- Feature importance.
- Output tables.
- Maps if storage allows.
- README excerpt with date, time, and caveats.

Recommended v2 addition:

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
