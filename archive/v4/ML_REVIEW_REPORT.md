# ML Technical Review: NT MVT Mineral Prospectivity Pipeline (v3)

**Reviewer role**: Skeptical ML reviewer with geospatial ML and scientific evaluation focus  
**Date of review**: 2026-05-14  
**Codebase reviewed**: Active scripts (`scripts/`), configs (`configs/`), planning documents, and archived run artifacts (`archive/v2/`)  
**Primary commit examined**: HEAD (main branch), v3 scaffold + v2 execution artifacts

---

## 1. Executive Summary

This project is a regional mineral prospectivity mapping pipeline for MVT deposits in the Northern Territory of Australia. It uses rasterized geophysical and geological predictor layers, Random Forest classification, and spatial train/validation/holdout splits to produce a relative prospectivity score map.

The pipeline is methodologically aware and better-designed than most first-generation prospectivity pipelines. Key controls are in place: coordinate exclusion, leakage name-checking, split-first evaluation, correct train/holdout separation for the final map, and honest language around "prospectivity scores not probabilities."

However, several structural problems undermine the scientific defensibility of the evaluation. The most critical: the 10 "repeated spatial splits" actually use only **3 distinct holdout geographic locations**, making the repeated evaluation far less informative than it appears. There is also **no spatial buffer** between train and holdout, tiny holdout positive counts (5–12 per split), and an alarming **21× performance gap** between validation and holdout average precision in v2 results.

The project is best described as a **methodologically-aware exploratory pipeline** — well past naive baseline, but not yet a scientifically defensible benchmark. It is exactly where it should be at this stage, and the right next steps are clear.

---

## 2. Pipeline Trace

Data flows through the following stages. All paths were traced through actual code, not documentation alone.

### Stage 1: ROI and Template (`01_make_roi_and_template.py`)
- Reads GADM Australia boundary, filters to Northern Territory, dissolves, reprojects to EPSG:3577.
- Creates a raster template from the bounding box of the NT geometry, rounded to 500m pixel boundaries.
- Rasterizes the NT polygon to produce a binary mask (1 = inside NT, 0 = outside).
- **Assumption entered**: "inside NT" is the valid domain. Pixels touching the NT boundary at exactly 1 include edge slivers. No concern raised here.

### Stage 2: Continuous Raster Processing (`02_process_continuous_rasters.py`)
- Reads 7 continuous raster sources (moho, lab, gravity, gravity_hgm, mag_rtp, mag_hgm, shape_index).
- Reprojects each onto the exact template using **bilinear interpolation**.
- Masks to NT interior.
- **Bilinear interpolation is a global GIS operation** — no label information is used. No leakage here, but it introduces spatial smoothing that increases autocorrelation across the mask boundary.

### Stage 3: Vector Predictor Processing (`03_process_vector_predictors.py`)
- Geology → `carbonate_host` binary raster (1 if CMMI_Class = "Sedimentary_Chemical_Carbonate").
- Geology → `lithology_code` raster via a hardcoded mapping function (categories 1–7, 99 for unknown).
- Faults → binary raster, then `dist_faults` via `scipy.ndimage.distance_transform_edt`.
- **The `all_touched=True` flag** in rasterization means polygons touching a pixel edge are marked. This is appropriate for continuous geology but may slightly over-mark thin fault traces. No leakage.

### Stage 4: Raster Stack Check + Leakage Check (`04_check_raster_stack.py`)
- Verifies CRS, transform, and shape match for all feature rasters.
- Runs a string-based leakage check on predictor names and paths for forbidden terms ("mvt_label", "lawley", "occurrence", etc.).

### Stage 5: Label Rasterization (`05_make_mvt_labels.py`)
- Reads occurrence CSV, filters to Australian MVT records, reprojects to EPSG:3577, clips to NT.
- Maps each point to the pixel at its center using `rasterio.transform.rowcol`.
- Marks that pixel as 1; if multiple points fall in the same pixel, it is still marked 1 only once (correct deduplication).
- **Assumption entered**: label resolution = one 500m pixel per occurrence location. Multiple nearby deposits in the same pixel count as one positive. This is correctly documented.

### Stage 6: Spatial Split Generation (`06_make_spatial_splits.py`)
- Computes square block candidates from the NT raster grid at a fixed side length derived from `sqrt(10% × valid_pixels)`.
- Iterates in raster row-major order. For each candidate holdout block, iterates through all other candidates for a non-overlapping validation block.
- Accepts a split when holdout and validation pass area and positive-count thresholds. Records a split mask (0=outside, 1=train, 2=validation, 3=holdout) and stops after `TARGET_ACCEPTED_SPLITS=10`.
- **Critical flaw detailed in Section 4.**

### Stage 7: Training Sample Construction (`07_build_split_training_samples.py`)
- For each accepted split, samples ALL positive pixels in the training region + up to `50 × n_positive` background pixels using spatial stratification (100-pixel block grouping).
- **Training region is correctly restricted** — validation and holdout pixels are never sampled for training.
- Background sampling seeds differ per split (`RANDOM_STATE + split_id`). Reproducible.

### Stage 8: Split Evaluation (`08_evaluate_random_forest_splits.py`)
- Trains a `Pipeline([StandardScaler, RandomForestClassifier])` per split using only training samples from that split.
- Scores ALL usable pixels in the validation region AND holdout region (not just sampled ones).
- Computes ROC-AUC, PR-AUC (average_precision), and top-1/5/10% recall, precision, enrichment.
- **The scaler is fit on training samples only.** No leakage here.
- Aggregate statistics (mean, median, std, worst, best) are written to `aggregate_metrics.csv`.

### Stage 9: Final Model Training (`09_train_final_random_forest.py`)
- Trains one final RF on ALL eligible NT pixels (all regions, no split constraint).
- **Correctly flagged**: "This model is for map production. It is not evaluation evidence."
- Feature importance is reported from the final model only.

### Stage 10: Prospectivity Map Production (`10_predict_final_prospectivity.py`)
- Predicts prospectivity scores for all usable pixels in chunks of 200,000.
- Writes a float32 GeoTIFF with -9999 NoData outside NT.

### Stage 11: Top-k Map Generation (`11_summarize_v3_outputs.py`)
- Computes top-k% thresholds from the final map score distribution (`np.percentile(valid_scores, 100 - pct)`).
- Writes binary top-1%, top-5%, top-10% maps.
- **Note**: these thresholds are derived from the final model output, not from the per-split holdout evidence.

---

## 3. Leakage Analysis

### What Is Currently Safe

| Check | Status | Detail |
|---|---|---|
| Coordinates excluded from features | Safe | `forbidden_feature_patterns` enforced in config validation; `x`, `y`, `row`, `col` are identifier columns only |
| Lawley MVT model excluded | Safe | Only referenced in `required_input_paths` as "for_comparison_only"; string-based leakage check in script 04 catches "lawley" in predictor paths |
| Occurrence CSV not used as predictor | Safe | Used only to create label raster; no distance-to-occurrence predictor present |
| Training samples from training region only | Safe | Split mask value 1 strictly enforces training region in script 07 |
| Scaler fit on training data only | Safe | `Pipeline` ensures scaler is fit on `X_train` before `predict_proba` on validation/holdout |
| Distance-to-faults is a GIS preprocessing step | Safe | Derived purely from fault geometry, no label information used |
| Label rasterization does not use any predictor | Safe | Script 05 uses only occurrence coordinates and the NT mask |
| Background pixels are labeled `sample_role="background"` | Safe | No masking out of known negatives; correctly treated as unlabeled |

### What Is Risky

**Bilinear resampling creates smooth boundaries at split edges.**  
Continuous rasters (gravity, magnetics, etc.) are globally resampled with bilinear interpolation before any split is applied. Values at training-region pixels adjacent to holdout pixels will be interpolated from a mix of training and holdout raw data. Without a spatial buffer, the model may learn feature values that "bleed across" the split boundary. This is not label leakage, but it is feature autocorrelation leakage — it inflates evaluation optimism particularly for models that use spatial structure.

**Background sampling usability mask is computed globally.**  
In script 07, `usable = np.ones(..., dtype=bool)` accumulates NaN flags from ALL valid NT predictor pixels before split assignment. The `usable` mask is then used to filter background candidates within the training region. This is not leakage — it doesn't use label information — but it means that background eligibility is determined using information from validation and holdout predictor values. In practice this has negligible effect since NaN patterns in geophysical rasters are spatially consistent.

**StandardScaler fit on sampled training data (positives + background), not all training pixels.**  
The scaler's mean and standard deviation are computed from the sampled training table, not from all pixels in the training region. If background sampling underrepresents certain feature ranges present in the training area, prediction on validation/holdout (which includes all pixels) may apply slightly miscalibrated scaling. This is very minor for Random Forest (scaling has no effect on RF predictions), but would matter for distance-based or linear models.

### What Is Unclear

**Whether the Lawley model was ever accidentally loaded as a predictor in any intermediate step.**  
The string-based leakage check guards against name-based inclusion, but cannot detect if the Lawley raster was loaded, transformed, and added under a neutral name. Code inspection shows no such pattern, but this cannot be fully verified without data access.

**Fault dataset completeness and spatial biases.**  
The `dist_faults` predictor reflects documented faults in the geological dataset. In Australia, fault mapping completeness varies by jurisdiction and decade. If MVT deposit locations cluster near well-mapped fault systems, and unmapped areas coincidentally have fewer occurrences in the dataset, the model may learn "proximity to mapped faults" rather than "proximity to actual fault control."

### What Should Be Changed

1. **Add a spatial buffer** (minimum 2–5 km, ideally 10+ km) between training and evaluation regions to reduce feature autocorrelation across boundaries. At 500m pixels, this is 4–20 pixels. This is the single most impactful leakage control not yet implemented.

2. **Investigate bilinear vs. nearest-neighbor resampling tradeoffs** for predictors where spatial smoothing is not geologically justified (e.g., categorical geology already uses discrete coding).

---

## 4. Spatial Evaluation Validity

This is the most critical weakness in the current design.

### The Fundamental Problem: Only 3 Holdout Locations

Examining the v2 `split_summary.csv` (the only completed run):

```
holdout_candidate_id: 1, 1, 1, 1, 1, 2, 2, 2, 2, 3
validation_candidate_id: 20, 21, 23, 24, 29, 20, 21, 23, 29, 20
```

The 10 "repeated spatial splits" use only **3 distinct holdout geographic blocks**. This is because the split generator iterates in row-major raster order and accepts the first 10 valid (holdout, validation) pairs it finds. Since holdout candidate 1 passes the area and positive-count thresholds and can be paired with many validation blocks, it gets selected 5 times before the generator moves to candidate 2.

**This is not repeated independent spatial evaluation.** It is 3 holdout locations evaluated multiple times with different validation companions. The aggregate mean and standard deviation across 10 splits conflate:
- True spatial generalization variance (how much performance varies by holdout location)
- Within-location variance (how much validation-companion choice affects a fixed holdout score)

The reported aggregate statistics are therefore misleading. The effective number of independent spatial evaluations is closer to 3, not 10.

### Square Blocks and NT Boundary Effects

Square blocks are defined in raster row-column space. The NT has an irregular boundary. A block near the NT boundary may contain very few valid pixels (the rest are masked out). The code correctly measures area as valid pixels inside the ROI, not raw square area — this is the right approach. However, a square block straddling the NT boundary will have an irregular actual shape, which may produce geometrically incoherent holdout regions that are hard to interpret geologically.

### No Buffer — Immediate Adjacency Across Splits

With `USE_SPATIAL_BUFFER = False`, train and holdout pixels may be directly adjacent (one raster cell apart = 500m). Geophysical rasters have spatial autocorrelation at scales of kilometers to hundreds of kilometers. The model trained on pixels at 500m distance from holdout pixels has access to essentially the same information as the holdout region through spatial autocorrelation of features. This is the strongest argument that current evaluation is optimistic.

### Minimum Positive Counts Are Too Low for Stable Metrics

With minimum 5 holdout positives (strict) or 4 (fallback), each individual metric is computed over a handful of events. In the v2 data:
- Holdout splits 1–5 have exactly 5 positives each
- Holdout splits 6–10 have 12 positives each (different holdout block)

With 5 positives, a recall measurement has granularity of 0.2 (= 1/5). One additional captured positive changes recall by 20 percentage points. The reported precision values are essentially noise at this scale.

### The Area Tolerance of ±3% Creates Correlated Blocks

The strict rule is `abs(area_share - 0.10) <= 0.03`, meaning holdout areas between 7% and 13% of valid pixels are accepted. At ~5M valid pixels, this means blocks of 350,000 to 650,000 pixels (174 to 323 km sides). Blocks of this size will often share similar geological settings within the NT, limiting the geographic diversity of evaluation.

### Proposed Repeated Split Framework Assessment

The design intent (repeated spatial splits with independent holdout blocks, aggregate statistics) is scientifically sound as a concept. The implementation runs into two execution-level problems:
1. The greedy selection algorithm concentrates on the same few holdout positions.
2. Positive count constraints make many geographic regions ineligible.

The solution is not to remove the framework, but to fix the selection algorithm to maximize holdout geographic diversity.

---

## 5. Metrics and Modeling Validity

### The Validation–Holdout Discrepancy Is Alarming

From v2 aggregate metrics:

| Metric | Validation (mean) | Holdout (mean) | Ratio |
|---|---|---|---|
| Average Precision (PR-AUC) | 0.00287 | 0.000132 | 21.7× |
| ROC-AUC | 0.898 | 0.695 | 1.29× |
| Top-5% Recall | 0.663 | 0.350 | 1.9× |

A 21× difference in PR-AUC between validation and holdout is not within normal variance. Possible explanations:

1. **Overfitting to validation region characteristics**: Since the same holdout candidate 1 appears 5 times, the validation regions that keep being tested may have favorable geological settings (carbonate outcrops near split training data) that inflate validation scores systematically.
2. **Holdout blocks are geographically harder**: The holdout blocks may represent geologically distinct areas where the model doesn't generalize.
3. **Small positive count amplification**: Validation regions have 4–24 positives (mean 12.4) while holdout regions have 5–12 (mean 8.5). Small counts create large variance.
4. **Genuine generalization failure**: The model may be learning geographic/geological features specific to the training region without real geological signal.

This discrepancy alone is sufficient reason to treat all v2 evaluation results as exploratory, not as scientific evidence.

### ROC-AUC Is Not Primary and Is Sometimes Below 0.5

Holdout ROC-AUC ranges from 0.342 to 0.975 across splits. Splits 6, 7, 8, and 9 have holdout ROC-AUC below 0.5 (0.39, 0.34, 0.45, 0.43), indicating worse-than-random ranking on those holdout regions. This is consistent with the model failing to generalize to geographic areas with fewer mapped MVT deposits.

The project correctly labels ROC-AUC as a secondary metric. PR-AUC is more appropriate for this severely imbalanced problem, and the top-k recall and enrichment metrics are the most operationally meaningful.

### Top-k Metrics: Reasonable But Unstable

- **Top-5% holdout recall (mean 0.35, enrichment 7.0)**: If you examine the top 5% of pixels, you capture 35% of known holdout MVT occurrences. This is 7× the base rate. For a screening tool, this is genuinely useful signal.
- **Worst case**: One split has top-5% holdout recall of 0.083 (8.3%), or 1.67× enrichment. Near-random.
- **Best case**: One split achieves 100% top-5% recall (all 5 holdout positives captured in top 5%).

The mean enrichment of 7× at top-5% is encouraging, but the worst-case near-random performance demonstrates that the model is not reliably useful on all geographic evaluation targets.

### Precision Values Are Meaninglessly Small

Top-5% holdout precision is around 0.000116 (≈ 0.012%), which is 6× the base rate. These numbers are uninterpretable in isolation. Report enrichment factors and capture counts instead of precision at this imbalance ratio.

### Ordinal Encoding of `lithology_code`

The lithology code uses integer values 1–7 and 99 ("Other or unknown"). This is fed as a continuous numeric feature to Random Forest. Random Forest uses threshold splits, so it will find thresholds like "code < 3.5" or "code < 50". The value 99 for unknown is particularly problematic: the model will create splits at "code < 50" or "code < 99" that may inadvertently treat unknown lithology as a category distinct from all known types. This is partially defensible for RF but is scientifically imprecise.

The Granek thesis (in `research/`) notes this exact issue: categorical geology should be converted to binary indicators to avoid false ordinal relationships. This was noted as a future improvement but is important enough to implement early.

### StandardScaler Is Unnecessary for Random Forest

The V3 design mandates StandardScaler via `validate_run_config()`, which raises a `ValueError` if `scaling.enabled` is not `True`. This is architecturally reasonable for pipeline portability (other models would need it), but the comment in DECISIONS_TO_MAKE.md correctly notes "RF usually does not need scaling." Scaling has no effect on RF predictions — the same split thresholds are found regardless of feature range. The mandatory scaler adds computational overhead and creates a false sense of preprocessing rigor without affecting the model.

This is a **harmless but misleading** design choice. The validation error preventing disabling scaling is overly rigid.

### Background-to-Positive Ratio of 50:1

The pipeline uses 50 background samples per positive. With ~70 training positives and 50:1 ratio, training tables have ~3,500 + 70 = 3,570 rows. With `class_weight="balanced"`, the RF internally reweights classes. The 50:1 ratio is reasonable for this problem but the interaction with `class_weight="balanced"` means the effective class ratio in the RF's loss function is approximately 1:1, regardless of the 50:1 sampling. This is correct behavior and is not a bug.

### Class Imbalance and Metric Instability

At ~5M valid NT pixels and ~70 positive pixels, the true class imbalance is approximately 70,000:1. Training at 50:1 with `class_weight="balanced"` handles this in the RF objective. However, evaluation on holdout (5–12 positives in ~370K pixels) means any reported metric is extremely sensitive to individual positive/negative misclassifications. This is an inherent limitation of the problem, not a coding error, and is honestly documented.

---

## 6. Geological and Geospatial Realism

### 500m Resolution Assessment

At 500m pixels, individual MVT deposit footprints (which can range from tens of meters to a few kilometers) are captured as 1–few pixels. Multiple nearby occurrences merge into the same pixel. This is appropriate for regional-scale screening. Finer resolution (100–250m) would be needed for drill-target generation, which is explicitly deferred. The 500m choice is scientifically defensible for the stated goal.

### Predictor Geological Justification

| Predictor | MVT Relevance | Assessment |
|---|---|---|
| `carbonate_host` | High — MVT deposits almost exclusively form in carbonate host rocks | Well-justified |
| `lithology_code` | High — captures rock type context | Justified but encoding is imprecise |
| `dist_faults` | High — faults are primary fluid pathways for MVT mineralisation | Well-justified |
| `gravity` / `gravity_hgm` | Moderate — reflects deep structure, basin geometry | Defensible |
| `moho_depth` | Low-Moderate — reflects crustal thickness, which influences tectonic setting | Speculative but common in regional prospectivity |
| `lab_depth` | Low — lithosphere-asthenosphere boundary depth (~100–200 km) is very far removed from shallow MVT processes | Geologically tenuous; requires explicit justification |
| `mag_rtp` / `mag_hgm` | Low-Moderate — magnetics primarily reflects igneous/mafic bodies; MVT in carbonates has weak magnetic signature | Less relevant than for porphyry systems; may capture structural trends indirectly |
| `shape_index` (satellite gravity) | Low — speculative connection to MVT | Requires geological justification |

**The inclusion of LAB depth as a direct predictor deserves scrutiny.** MVT deposits form in sedimentary basins at shallow crustal levels. The lithosphere-asthenosphere boundary at 100–200 km depth is a geological region far removed from MVT processes. While LAB depth captures regional tectonic context (cratons vs. mobile belts), using it as a pixel-level predictor is geologically speculative and may be fitting noise rather than signal.

This concern is echoed by the Granek thesis note that feature selection should be guided by the mineral system model, not just data availability.

### False Precision Risk

Producing a 500m prospectivity map with decimal-place scores creates an impression of precision that is not supported by the data. There are only ~70 known positive pixels in a domain of ~5M pixels. A model trained on 70 labeled examples cannot reliably distinguish prospectivity at 500m resolution across 1.25M km². The map is useful as a broad screening tool (top-10% zones, ~125,000 km²), but becomes scientifically indefensible if used at high zoom levels to prioritize specific drill targets.

The project correctly uses "relative prospectivity ranking" language. This precision concern should be explicitly stated in any map deliverable.

---

## 7. Reproducibility and Experiment Structure

### Strengths

- YAML run config captures the key hyperparameters and feature list for v3.
- Fixed random seeds with per-split variation (`RANDOM_STATE + split_id`).
- Split masks are written as separate GeoTIFFs, preserving exact geographic boundaries.
- Archived v2 metrics include per-split and aggregate tables.
- The training table and feature importance are archived.

### Weaknesses

**Critical: Archived split paths are machine-specific.**  
The v2 `split_summary.csv` contains absolute paths like `/Users/yasin/mineral-prospectivity-mvp/data/processed/splits/split_001_mask.tif`. These paths are non-portable. Anyone attempting to reproduce v2 evaluation on another machine would need to regenerate all splits from scratch. Since split generation is deterministic (given the same seed, mask, and threshold), this is recoverable — but only if the exact same input data is available.

**No data checksums.**  
The geological datasets (shapefiles, occurrence CSV, geophysical GeoTIFFs) are not included in the repository and no checksums are provided. There is no way to verify that the input data used for v2 or v3 matches any specific download. The science base URL in README.md links to a data catalog, not a specific versioned artifact.

**No git commit hash in evaluation artifacts.**  
Archived metrics CSVs and review text files contain no timestamp beyond the run archive date in README.md, and no git hash. Future auditing requires trusting the README timestamp.

**The final model is trained on all data including what was holdout in splits.**  
This is by design (script 09 is explicitly for map production, not evaluation), but the final model's feature importances should not be interpreted as holdout-validated. The current code does report feature importance from the final model only, without noting this limitation. Feature importance should eventually come from permutation importance computed on held-out data, not from the final model's built-in impurity importance.

**Feature importance from impurity, not permutation.**  
Built-in Random Forest importance (MDI) is known to be biased toward high-cardinality features and can be unreliable. The Granek thesis explicitly flags this for later improvement, and this project's DECISIONS_TO_MAKE.md also notes "Built-in RF importance is a quick diagnostic, not scientific evidence." This is correctly flagged but not yet addressed.

---

## 8. Research Maturity Assessment

| Dimension | Current Stage |
|---|---|
| End-to-end pipeline | Complete |
| Data processing | Solid with minor issues |
| Leakage control | Good for direct leakage; spatial autocorrelation leakage still present |
| Evaluation design | Structurally correct intent, implementation has critical flaw (3 distinct holdout locations) |
| Metric reporting | Appropriate metric selection, unstable due to positive count |
| Reproducibility | Partial (seeds frozen, paths not portable) |
| Scientific defensibility | Exploratory, not yet benchmark-grade |
| Production readiness | Not applicable at this stage |

**Overall**: This is a solid **early-stage ML research pipeline** with genuine methodological awareness. It is not a proof of concept (it has a real evaluation framework), but it is not yet a scientifically defensible benchmark. The right comparison is to a first-year PhD student's dissertation pilot study: the framing is correct, the methods are reasonable, but the evidence is not yet strong enough to support confident claims.

The planning documents (DECISIONS_TO_MAKE.md, PROJECT_WORKFLOW_V3.md) show excellent scientific judgment about what to build and in what order. The gap between design intent and implementation quality is the primary concern.

---

## 9. Multi-Resolution Idea Evaluation

### What the Idea Is

The research context (Granek thesis notes, planning documents) discusses coarse-to-fine prospectivity: train a coarse-resolution model (e.g., 5 km or 10 km pixels) to identify broad prospective terrains, then train a fine-resolution model within those terrains for detailed targeting.

### Scientific Soundness

The concept is scientifically motivated:
- Regional-scale controls (tectonic setting, basin type, crustal structure) are best captured at coarse resolution
- Local controls (specific carbonate units, proximity to mapped faults) are better captured at fine resolution
- Combining scales reduces false precision of single-resolution models

This is analogous to hierarchical classification in ecology and is used in some mineral prospectivity workflows.

### Risks and Requirements

**What would make it defensible**:
- Each resolution level requires independent evaluation (separate spatial holdout splits at that scale)
- The coarse model must be evaluated independently before being used to filter areas for the fine model
- Error propagation must be quantified: if the coarse model rejects a region, all true positives in that region are lost regardless of fine-model performance
- Label rasterization at different resolutions must be handled consistently (a deposit cluster may become 1 or 0 pixels at coarser resolution)

**What would make it invalid**:
- Using the fine model's performance to tune the coarse model's threshold (or vice versa)
- Computing holdout metrics only on the combined two-stage system without evaluating each stage independently
- Justifying resolution choice by post-hoc examination of results rather than geological reasoning

**When not to do this**:
Given that the current single-resolution pipeline has only ~70 known positive pixels and cannot produce reliable evaluation with 5–12 holdout positives per split, adding a second resolution with even fewer labeled positives per region would create uninterpretable results. **This is premature complexity that should not be attempted until the single-resolution evaluation is stable.**

---

## 10. Concrete Prioritized Recommendations

### Must Fix Now (Blockers for Any Scientific Claim)

**1. Fix the split generation algorithm to maximize holdout geographic diversity.**  
The current greedy algorithm produces 10 splits with only 3 distinct holdout locations. Rewrite to enumerate candidate holdout blocks and select a maximally geographically diverse set. Minimum requirement: each split should use a distinct holdout geographic location. Target: at least 5–8 distinct holdout blocks across accepted splits.

_Where to fix_: `scripts/06_make_spatial_splits.py`, the loop that stops after TARGET_ACCEPTED_SPLITS.

**2. Add a spatial buffer between train and evaluation regions.**  
Implement `USE_SPATIAL_BUFFER = True` with a minimum buffer of 5 km (10 pixels at 500m). The code already has `BUFFER_DISTANCE_M = 0` as a config variable; the split generation just needs to exclude buffer pixels from both training and evaluation regions (assign them to value 0 in the split mask).

_Where to fix_: `scripts/06_make_spatial_splits.py`, `train_region` computation.

**3. Do not claim the current evaluation is non-exploratory without addressing points 1 and 2.**  
The README's "non-exploratory" classification requires `MIN_ACCEPTED_SPLITS_FOR_NON_EXPLORATORY = 5`, but this threshold does not account for the diversity of holdout locations. 10 splits over 3 holdout locations is still exploratory.

**4. Investigate and explain the 21× validation-holdout performance gap.**  
Before reporting any metrics, run a diagnostic: plot the geographic location of the 3 holdout candidate blocks and 5–6 validation blocks on the NT map. Determine whether the discrepancy arises from (a) systematic over-optimism in validation due to split selection order, (b) genuine distribution shift between holdout regions, or (c) positive count instability. This diagnosis should precede any interpretation.

### Medium Priority (Important for Scientific Credibility)

**5. One-hot encode `lithology_code` instead of using ordinal integer codes.**  
Replace the single `lithology_code` feature with binary indicators for each category (carbonate, chemical sedimentary, evaporite, siliciclastic, unconsolidated, igneous, metamorphic, unknown). This avoids false ordinal relationships and is consistent with Granek's recommendations for categorical geology.

_Where to fix_: `scripts/03_process_vector_predictors.py` (create separate binary rasters) and `configs/v3_run_config.yml` (update `feature_columns`).

**6. Provide geological justification for `lab_depth` and magnetic predictors in an MVT mineral system model.**  
Either document the geological pathway from LAB depth to MVT deposit formation, or remove it and note why it was tested and removed. At minimum, compute permutation importance on validation data to determine whether `lab_depth` contributes measurable signal.

**7. Record a git commit hash in each evaluation artifact.**  
Add `subprocess.check_output(["git", "rev-parse", "HEAD"])` (with fallback) to the run config and include it in `aggregate_metrics.csv` and the review text file.

**8. Add input data checksums or hash verification.**  
Document MD5 or SHA256 hashes of the critical input files (occurrence CSV, geology shapefiles) in the run config or a separate data manifest. This is minimum reproducibility evidence.

**9. Improve split mask portability.**  
Store split mask filenames (not absolute paths) in `split_summary.csv`, and resolve them relative to `SPLITS_DIR` at runtime.

### Low Priority (Good Future Research, Not Now)

**10. Add permutation importance on holdout data for the final model.**  
After a geographically robust holdout split is established, compute permutation importance on holdout pixels to get an unbiased estimate of feature contribution. This replaces the built-in impurity importance.

**11. Produce a model uncertainty map using split-to-split variance.**  
Once the split diversity issue is fixed, compute the standard deviation of prospectivity scores across per-split models for each pixel. Pixels with high variance are less reliable targets regardless of their mean prospectivity score.

**12. Compare one-hot lithology vs. ordinal in a controlled experiment.**  
After point 5 is implemented, compare PR-AUC and top-k recall between the two encodings under the same spatial holdout framework.

**13. Consider adding distance-to-lithological-contacts as a predictor.**  
Contact zones between carbonates and other lithologies are known MVT trap settings. This is more geologically targeted than generic distance-to-faults and is supported by the Granek framework.

### What Should NOT Be Pursued Yet

**14. Do not add CNNs, gradient boosting, or new complex models.**  
The evaluation framework cannot yet produce reliable evidence about whether model A is better than model B. Adding model complexity before fixing the evaluation would produce uninterpretable comparisons.

**15. Do not attempt multi-resolution coarse-to-fine modeling.**  
With ~70 positive pixels at 500m, there are insufficient positives to support reliable evaluation at a second resolution. Premature.

**16. Do not calibrate output scores to probabilities.**  
Calibration requires a reliable validation holdout to fit and verify. The current holdout evidence is not sufficient. The current language ("relative prospectivity score") is appropriate.

**17. Do not add geochemical predictors without establishing data quality.**  
If regional geochemical data becomes available, it requires careful background correction for MVT (vs. porphyry systems). This is a future research direction, not a near-term addition.

---

## 11. Final Verdict

**Scientific defensibility**: The pipeline is not yet scientifically defensible as a quantitative benchmark. The central limitation is that the repeated spatial evaluation uses only 3 distinct holdout geographic locations, making the reported aggregate statistics misleading. The 21× validation-holdout performance gap confirms the evaluation is unreliable.

**Practical usefulness**: The final prospectivity map (v2, v3) likely contains genuine geological signal — the top-5% holdout enrichment of 7× (when it works) suggests the model is not random. It can be used as one screening input among many. It should not be the sole basis for exploration decisions.

**Design quality**: The design is excellent for an early-stage research pipeline. The decision log (DECISIONS_TO_MAKE.md) is thorough and honest. The separation of evaluation evidence from the final production map is correctly implemented. The claims language ("prospectivity score, not deposit probability") is appropriate. The planning documents show clear scientific thinking.

**The most important next action is Point 1**: fix the split generator to produce genuinely geographically diverse holdout locations. Everything else follows from having reliable evaluation evidence.

---

## Appendix: Code-Level Findings

### A. Scaler Fit Scope (Script 08)

The pipeline is:
```python
model = Pipeline([('scaler', StandardScaler(...)), ('rf', RandomForestClassifier(...))])
model.fit(X_train, y_train)
```
`X_train` comes from `training_samples[training_samples["split_id"] == split.split_id][feature_names]`. This is the sampled training table from script 07, which contains positives + background from the training region only. The scaler is fitted correctly on training data. No leakage.

### B. Validation vs Holdout in Script 08

```python
for region_name, region_value in [("validation", 2), ("holdout", 3)]:
    scores, y = score_region(model, split_mask, region_value, ...)
```
Both validation and holdout are scored with the same model. The model is not re-tuned or re-selected based on either. This is correct holdout discipline for the evaluation script.

### C. Final Model Scope (Script 09)

```python
positive_idx = np.where(usable & (flat_labels == 1))[0]
background_idx = np.where(usable & (flat_labels == 0))[0]
```
The final model uses ALL valid NT pixels, including what were holdout pixels in splits. This is explicitly labeled as a "screening map" model and is not reported as holdout evidence. This is correct.

### D. Top-k Enrichment Calculation

```python
enrichment = recall / (pct / 100.0) if total_pos else np.nan
```
Correct definition of enrichment factor (lift). If top-1% captures 8.33% of positives, enrichment = 8.33/0.01 = 833? No — `pct` is already expressed as a percentage, so `pct/100.0 = 0.01`, and enrichment = recall / 0.01. If recall = 0.0833, enrichment = 8.33. This is correct.

### E. Area Measurement Near NT Boundary

```python
area_share = valid_count / valid_pixels
```
Where `valid_count = int(block_valid.sum())` and `block_valid = block & valid`. Area is measured as NT-valid pixels inside the block. A block overlapping the NT boundary will have lower area share than its raw size suggests. This is the correct approach and is documented in the design.

### F. The `rule_type` Column

In v3's script 06, `rule_type` records "strict" vs "fallback". In v2's actual split_summary.csv, the values are "strict" and "fallback" (correctly), showing that splits 5 and 9 used the fallback threshold (validation had only 4 positives). In v3's code, the rule_type is saved as:
```python
rule_type = "strict" if strict_holdout_ok and strict_validation_ok else "fallback"
```
This is correct but note that "fallback" includes any case where either holdout OR validation uses the fallback rule.

### G. The `BACKGROUND_PER_POSITIVE = 50` Constant

This is hardcoded in `scripts/00_config.py` (line 75) outside the YAML run config:
```python
BACKGROUND_PER_POSITIVE = 50
```
This is a significant modeling decision that is NOT tracked in `v3_run_config.yml`. It should be moved to the YAML config to ensure it is frozen and auditable per run.

---

*Review conducted by static code inspection, artifact analysis (v2 metrics CSVs), and design document analysis. No model was executed during this review. All metric claims are sourced from `archive/v2/data/processed/models/`.*
