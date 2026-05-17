# Roadmap Review and Gap Analysis

**Repository**: NT MVT Mineral Prospectivity  
**Reviewed**: `DECISIONS_TO_MAKE_V4.md`, `ML_REVIEW_REPORT.md`, `VALIDATION_HOLDOUT_GAP_DIAGNOSIS.md`, `SPATIAL_SPLIT_FIX_PLAN.md`, `research/V3_LOGIC_TO_SCRIPTS_AND_V4_IMPROVEMENTS.md`, `archive/v3/` artifacts, `pipeline/core_scripts/`  
**Date**: 2026-05-16

---

## 1. Executive Summary

The `DECISIONS_TO_MAKE_V4.md` decision table covers the right territory. The prioritization of split diversity as the foundational problem is correct. The sequencing of calibration and multi-resolution as deferred work is correct. Most individual gate choices are defensible.

However, three decisions — G10 (5 km spatial buffer), G11 (raise holdout minimum to ≥8 positives), and G6 (require ≥2 geographic zones) — interact in a way that may make v4 completely infeasible with NT data. These three gates were not analyzed jointly. With only 70 NT positive pixels, raising the holdout minimum to 8 eliminates the NW holdout cluster (5 positives), leaving only the NE cluster as holdout — a single zone, which immediately violates G6. Adding a 5 km buffer compounds the problem by reducing effective positive counts near block boundaries. This is the most important hidden risk in the entire roadmap and it needs a feasibility check before any gate is frozen.

Four additional issues require attention before coding begins: G4 is unfilled, G8's swap logic requires validation candidate uniqueness that is not stated in the decision table, G12 is empty while the underlying parameter stays hardcoded, and the V3_LOGIC document's priority ordering puts uncertainty maps before spatial buffer, which is backwards.

---

## 2. What the Roadmap Gets Right

**Correct foundational prioritization.** G4–G9 treat the split generator as the prerequisite for everything else. This is scientifically correct: aggregate metrics computed on 3 holdout locations are not yet meaningful enough to use as a baseline for feature or model comparisons. Fixing the splits before adding new features or model families is the right call.

**Correct deferrals.** G22 (calibration) and G23 (multi-resolution) are both correctly deferred. Calibration requires a stable evaluation framework first; multi-resolution requires a working single-resolution pipeline. Keeping these out of v4 is disciplined.

**RF baseline only (G15=A).** Choosing not to add a comparator model in v4 is correct. The current variance across splits is too high (holdout ROC-AUC std = 0.258 in v3) to reliably compare models. Adding XGBoost now would produce meaningless comparisons.

**Per-location holdout reporting (G17=B, G18=B).** The decision to report holdout results per geographic location rather than as a single mean directly addresses the most misleading aspect of the v2/v3 aggregate metrics. This is exactly right.

**One-hot lithology (G13=B).** The ordinal encoding issue was correctly identified as a methodological defect and correctly resolved.

**LAB ablation before deciding (G14=C).** Rather than removing LAB depth or keeping it on faith, an ablation test is the right approach.

**Core_scripts baseline concept.** Separating stable preprocessing scripts (00-04) from version-specific modeling scripts is a good reproducibility improvement. The copy-into-run-directory pattern is appropriate.

**G19 (reproducibility artifacts).** Recognizing that run artifacts need manifests, checksums, and relative paths is correct. The v3 split_summary.csv has absolute machine-specific paths (`/Users/yasin/...`) that make script 08 non-portable; G19 addresses this.

---

## 3. Critical Gaps

### Gap 1: G4 is unfilled — the most critical gate

The `Your Choice` column for G4 (split generator strategy) is blank: `[ ]`. G4 is the parent decision for G5, G6, G7, G8, and G9. All of those downstream gates have been filled, which implicitly selects G4=B — but it is not formally acknowledged.

The "Minimum Required Decisions Before Any V4 Run" list names G4 first. The freeze record cannot be signed with G4 empty. Fill it explicitly before any code is written.

**Required action:** Fill G4 = B. Note that G5–G9 have already been selected under the implicit assumption that G4=B.

---

### Gap 2: G10, G11, and G6 interact — joint feasibility not checked

This is the most dangerous risk in the roadmap. Each of the three decisions looks reasonable in isolation. Jointly they may produce zero valid v4 splits.

The current NT data has 70 positive pixels. Their geographic distribution (from the diagnostic analysis):

- NW cluster (holdout candidate 1 in v2/v3): 5 positives
- NE cluster (holdout candidates 2 and 3 in v2/v3): 12 positives
- Central NT (the majority of positives): ~40 positives spread across validation candidates 20, 21, 23, 24, 29

The three decisions interact as follows:

**G11=C (raise holdout minimum to ≥8):** The NW cluster has 5 positives. It fails the new minimum. It is now ineligible as a holdout candidate. The only remaining holdout-eligible cluster is the NE cluster (12 positives). That is one geographic location, one zone (northern NT).

**G6=B (require ≥2 geographic zones):** With only the NE cluster as holdout-eligible, all accepted splits use the same holdout zone. G6 is immediately violated. The run cannot produce ≥2 holdout zones.

**G10=C (5 km spatial buffer):** At 500m pixels, a 5 km buffer removes 10 pixel rows/columns from the training region adjacent to each holdout and validation block. For a block with 12 positives near its edges, some may become unavailable for training after the buffer exclusion. This does not reduce the holdout positive count directly, but it further restricts which candidate blocks pass constraints — because the buffer removes training positives and may push some candidates below the G11 minimum.

**The net scenario:** If G10, G11, and G6 are all frozen as specified, v4's split generator may accept zero original splits, or one split from a single zone. The run would be labeled exploratory — a regression from v3's non-exploratory classification.

**Required action before freezing any of G10, G11, or G6:** Run a feasibility analysis. This is not a modeling run — it is a 5-minute data analysis. Load the NT mask raster and MVT label raster from v3. Apply the G10 buffer (remove pixels within 5 km of any candidate block boundary). Count holdout-eligible candidates per zone at each positive-minimum threshold (5, 6, 8, 10). Report the result. Freeze G11 and G10 at values that leave at least 2 zones with eligible candidates.

A suggested approach: G11 can raise the minimum for candidates that are NOT the only representative of their zone. Candidates that are the only holdout-eligible block in their zone could be allowed a lower threshold (the current fallback minimum) to preserve zone coverage. The SPATIAL_SPLIT_FIX_PLAN.md already describes exactly this policy in Risk 1.

---

### Gap 3: G8 (paired swaps) requires validation candidate uniqueness — not stated

The decision table approves swapped pairs (G8=B) without acknowledging a constraint that makes swaps valid. The SPATIAL_SPLIT_FIX_PLAN.md (Section 12, Risk 4) identifies this explicitly:

> If original splits 1 and 2 both have validation_candidate = 20, then swapped splits 1-swap and 2-swap would both have holdout_candidate = 20. This would reuse holdout candidate 20 twice in the swap set, violating the diversity principle.

For swapped pairs to be valid, the original splits must also use unique validation candidates. This means the v4 split generator needs two uniqueness constraints, not one: `used_as_holdout` (already in the plan) and `used_as_validation` (only required when swaps are enabled). Without this, G8=B and G5=B are inconsistent — you can have unique holdout candidates in original splits but reused holdout candidates in swapped splits.

**Required action:** Add to the decision table under G8: "When G8=B (swaps enabled), validation candidates across original splits must also be unique to ensure swapped pairs have unique holdout locations." This is not a new decision — it follows logically from G5 applied to the swap set — but it needs to be stated explicitly so the implementation doesn't miss it.

---

### Gap 4: G12 is empty; the underlying parameter stays hardcoded regardless

G12 covers the background sampling ratio comparison. But there is a separate issue that G12 does not address: `BACKGROUND_PER_POSITIVE = 50` is hardcoded in `00_config.py` line 75, outside the YAML run config. This means that even if G12 chooses a different ratio, the parameter will need to be changed in Python source code, not in the YAML. That is the reproducibility gap that `ML_REVIEW_REPORT.md` identified.

G19 (reproducibility artifacts) addresses manifests and checksums but does not explicitly cover "move hardcoded parameters into YAML config." The two issues — which ratio to use, and where the parameter lives — are orthogonal.

**Required action:** Add a sub-gate under G12: "Move `BACKGROUND_PER_POSITIVE` into `v4_run_config.yml` as `sampling.background_per_positive`." This should be done regardless of which ratio value is chosen. Fill G12 with a specific ratio decision. At minimum, commit to testing 25:1 alongside the current 50:1 within the same v4 split masks so the comparison is controlled.

---

## 4. Priority Disagreements

### Disagreement 1: Uncertainty map before spatial buffer in V3_LOGIC_TO_SCRIPTS priority order

`research/V3_LOGIC_TO_SCRIPTS_AND_V4_IMPROVEMENTS.md` recommends this v4 priority order:

```
1. Add uncertainty map from split-model prediction variance
2. Add spatial buffer experiments in split generation
3. Add nested spatial hyperparameter tuning
4. Add feature ablation study
5. Add calibration diagnostics
```

This ordering is scientifically backwards for item 1 and 2.

The uncertainty map is built from the standard deviation of per-pixel predictions across the 10 split models. If those splits have no buffer and geographic bias (holdout always northern NT, validation always central NT), the uncertainty map will show high uncertainty in northern NT simply because holdout and validation model predictions differ there due to different training exposures — not because that region is geologically uncertain. This is a split-geometry artifact masquerading as geographic uncertainty.

**The correct order:** Fix splits first (G4–G9), add buffer (G10), confirm split feasibility, run v4 evaluation — then build the uncertainty map on clean, geographically diverse splits. An uncertainty map built on v3-equivalent splits provides false precision.

**Recommended priority revision:**
```
1. Fix split generator (G4-G9: zone-diverse + unique holdout + swaps)
2. Add spatial buffer (G10)
3. Verify feasibility of G11+G6 after buffer
4. Run v4 evaluation with fixed splits
5. Build uncertainty map from v4 split models
6. Feature ablation (G14: LAB depth + others)
7. Calibration diagnostics (G22: still deferred)
```

---

### Disagreement 2: G6 weakened from C to B without geological justification

The recommendation in `DECISIONS_TO_MAKE_V4.md` (column "Recommended Default") is C: "target 3 zones, require ≥2." The user's choice is B: require ≥2 zones. This weakening is a legitimate pragmatic choice given NT's limited positive count, but it should be documented with an explicit reason.

The `VALIDATION_HOLDOUT_GAP_DIAGNOSIS.md` specifically identified southern NT (y < −2,000K) as geologically distinct from both northern and central NT — potentially McArthur River-type basin stratigraphy. If v4 produces splits from only northern and central NT (which is likely given G11 raising positive minimums), southern NT remains unrepresented in holdout evaluation for the entire v4 run.

The correct choice may still be B, given NT data constraints. But "B because C is infeasible with the positive count" is a different scientific statement from "B because we don't care about southern NT." The freeze record should name the reason explicitly.

**Required action:** In the freeze record notes, document: "G6=B chosen over C because [feasibility analysis shows / positive count is insufficient to / ...]. Southern NT geological domain is not represented in holdout evaluation."

---

### Disagreement 3: Nested hyperparameter tuning too early in the V3_LOGIC priority list

`V3_LOGIC_TO_SCRIPTS_AND_V4_IMPROVEMENTS.md` lists nested spatial hyperparameter tuning as priority 3. This is too early.

Nested tuning requires that the spatial splits are trustworthy enough that model parameters optimized inside training folds generalize meaningfully to validation folds. If the splits are not yet geographically diverse, inner-fold tuning will optimize for the same geographic domain as outer-fold validation, producing parameter estimates that are accurate for central NT but wrong for northern NT holdout.

Nested tuning also significantly increases compute time. At the v4 stage, the more urgent question is "do the splits work?" not "are the hyperparameters optimal?" The current fixed hyperparameters (500 trees, min_samples_leaf=2, balanced weights) are already reasonable for RF.

**Required action:** Move nested tuning to v5 or later. Do not implement it in v4.

---

## 5. Potential Hidden Risks

### Risk 1: V3 split 8 holdout anomaly is unexamined

`archive/v3/data/processed/models/metrics_by_split.csv` shows split 8 with holdout candidate 2 (NE cluster, 12 positives) achieving AP=0.000714. The baseline for that region is 12/378,338 = 0.0000317, giving skill ≈ 22.5×. This is 7× higher than the average skill for holdout candidate 2 across all other splits (0.9×, 1.8×, 3.1× in splits 6, 9, 7 respectively).

The anomaly coincides with split 8 using validation candidate 23 (8 ALL-carbonate, high-fault-proximity pixels). Removing those 8 archetypal pixels from the training region may cause the model to rely more on other signals (gravity, shape index) that happen to discriminate the NE cluster better for that particular model draw.

If v4 uses v3 holdout AP = 0.000256 as a comparison baseline (which is how aggregate statistics work), this anomalous split inflates the baseline by ~15%. More importantly, this split shows that NE holdout skill is not stably near-random — it can reach 22.5× under a different training composition, which means the NE cluster's difficulty is highly sensitive to which pixels are excluded from training. That is itself a scientific finding worth reporting, but the v3_model_review.txt does not mention it.

**Required action:** Before running v4, analyze why split 8 holdout behaves anomalously. Check whether the 8 ALL-carbonate val cand 23 pixels share geographic features with NE holdout pixels that, when excluded from training, force the model to generalize differently. Report this as part of the mandatory gap protocol (G18).

### Risk 2: The `scripts/` directory is empty — v4 has no starting point for scripts 05–11

After the pull, `scripts/` is gone. `pipeline/core_scripts/` provides 00–04. There is no analogous canonical baseline for scripts 05–11 (splits, sampling, evaluation, final model, prediction, summary). The v3 archived versions in `archive/v3/scripts/` are the closest starting point, but they contain v3-specific constants and paths.

The `pipeline/core_scripts/README.md` says to copy into new run directories. But there is no documented policy for which scripts are stable enough to be core scripts and which need version-specific rewrites. Script 06 in particular is being completely restructured for v4.

**Required action:** Before writing v4 scripts, decide: does v4 live in `scripts/` (current working directory pattern), or does it live in `runs/v4/scripts/` (the pattern suggested by core_scripts README)? This directory structure decision affects all downstream documentation and import paths (`00_config.py` uses `Path(__file__).resolve().parents[1]` to find PROJECT_ROOT — the level count depends on where the script lives).

### Risk 3: Absolute paths in v3 split_summary.csv persist the portability problem

`archive/v3/data/processed/splits/split_summary.csv` contains paths `/Users/yasin/mineral-prospectivity-mvp/data/processed/splits/split_001_mask.tif`. These paths will not resolve on any other machine.

G19 targets v4 artifact portability. But if v4 evaluation ever references v3 split masks for comparison (which is possible if a reviewer wants to verify v3 results), those paths will silently fail. The v3 archive is now committed to the repo — the paths are frozen.

**Required action:** Either (a) document explicitly that v3 split masks cannot be reproduced from the repo without re-running script 06 on the correct machine, or (b) store split masks relative to the archive directory and update the archived split_summary.csv to use relative paths. Option (a) is lower effort and honest.

### Risk 4: G21 (uncertainty map) may produce a geographically misleading artifact

With 10 splits over 3 holdout locations (v3), the per-pixel prediction variance across split models is dominated by inter-holdout-location variance, not geological uncertainty. Pixels in northern NT — where holdout blocks appear — will show high variance because some splits (using holdout cand 1 as holdout) trained without NW training data and others (using holdout cand 2) trained without NE training data. The variance pattern reflects "which pixels were in holdout" more than "which pixels are geologically uncertain."

This persists even in v4 with improved splits, unless the split count is large enough to average out the holdout-location variance. With 70 positives and NT's geographic constraints, the number of genuinely distinct splits is bounded. A spatial uncertainty map built on ≤15 splits with NT data should be presented with a strong caveat: uncertainty at each pixel reflects that pixel's exposure to holdout exclusion across splits, not its inherent geological ambiguity.

**Required action:** If G21 is implemented in v4, add a specific limitation note to the uncertainty map GeoTIFF metadata and the review report: "This map shows prediction variance across split models, not calibrated geological uncertainty. Regions systematically placed in holdout blocks will show inflated variance."

### Risk 5: Permutation importance region is unspecified (G20)

G20 says "add permutation importance on eval regions" but does not specify which eval region. Permutation importance computed on validation regions (central NT, carbonate-rich geology) will rank features differently than permutation importance on holdout regions (northern NT, high-gravity terrain). The two rankings may disagree on gravity and carbonate_host — the features most relevant to the distribution shift problem.

Computing permutation importance only on validation essentially measures "which features matter for the easy geology." Computing on holdout measures "which features matter for the hard geology." Both are scientifically valid questions, but they are different questions.

**Required action:** Specify that permutation importance should be computed separately on validation and holdout regions, with both rankings reported side by side. This directly informs the geological interpretation of the distribution shift.

---

## 6. Issues Previously Classified Critical — Correctly Addressed?

Going through the ML review's critical findings:

| Finding from ML_REVIEW_REPORT.md | Decision table response | Assessment |
|---|---|---|
| Only 3 holdout locations across 10 splits | G4=B, G5=B, G6=B | **Addressed** (pending G4 being filled) |
| Greedy row-major generator bias | G4=B (zone-diverse selection) | **Addressed** |
| 21× validation-holdout AP gap | G18=B (mandatory diagnostic per run) | **Addressed** |
| No spatial buffer | G10=C (5 km) | **Addressed** — but G11 interaction is a risk |
| Ordinal lithology encoding | G13=B (one-hot) | **Addressed** |
| `BACKGROUND_PER_POSITIVE` hardcoded outside YAML | G12 (compare ratios) | **Partially** — moving the parameter to YAML is still missing (see Gap 4) |
| Archived split paths machine-specific | G19=B (relative paths) | **Addressed for v4** — v3 archive remains broken |
| LAB depth geological justification | G14=C (ablation) | **Addressed** |
| Impurity-based importance biased | G20=B (add permutation) | **Addressed** — eval region unspecified (see Risk 5) |
| No uncertainty map | G21=B (split-variance map) | **Addressed** — but ordering risk (see Priority 1 above) |

Two items from the original review are not addressed by any gate:

**Missing item A: Minimum 5 holdout positives is too low for stable AP measurement** — already partially addressed by G11, but note that the ML review also raised concerns about the *variance* introduced by tiny positive counts (the 2466× validation outlier in v2 came from 4 positives). G11 addresses the threshold but not the interpretation policy: when the top-k enrichment metric is computed on 5 positives in top-1% area (0–1 positives captured), the enrichment jumps between 0 and 20×. This discrete-jump behavior is not acknowledged anywhere in the decision table. **The correct response is: for holdout regions with <10 positives, report top-k metrics with confidence notation (e.g. "n=5, one additional captured positive changes recall by 20 percentage points").**

**Missing item B: `StandardScaler` fit on sampled training data, not all training pixels** — the ML review flagged that the scaler's mean/std are computed from the sampled training table (positives + sampled background), not from all training-region pixels. For RF this is inconsequential, but if v4 adds any distance-based or linear model as a comparator (G15=A keeps RF only, so this is deferred correctly), the sampling-biased scaler would introduce subtle scale errors. No gate addresses this explicitly. Since G15=A keeps RF only, this is acceptably deferred — but the note should appear in the v4 review report's limitations section.

---

## 7. Anything Tackled Too Early or Unnecessarily

**G20 (permutation importance) before split diversity confirmed:** Permutation importance on validation regions contaminated by geographic bias produces misleading feature rankings. G20 should only be implemented after G4–G9 are confirmed working. It is not explicitly sequenced in the decision table. Make this dependency explicit.

**G21 (uncertainty map) in v4:** This is a significant implementation effort. Before implementing it, the split diversity needs to be working (G4–G9 implemented and tested), the buffer needs to be confirmed feasible (G10 + G11 feasibility check), and v4 needs to have run at least once with the new splits. Building the uncertainty map infrastructure before any of those are in place risks building a map that misrepresents what it measures. A safer approach: implement uncertainty map as the last v4 deliverable, after all split-fixing work is confirmed.

**Feature ablation (G14: LAB depth) in v4:** This is scientifically valuable but relatively independent of the split diversity work. It should wait until the new splits are confirmed working, so the ablation results are measured against a reliable evaluation framework. It is fine to implement it in v4, but it should be scheduled after the split diversity changes are confirmed — not in the same coding sprint.

---

## 8. Internal Coherence Check

These gate pairs have direct implementation dependencies. All look coherent with one exception noted:

| Gate pair | Interaction | Coherent? |
|---|---|---|
| G4=B + G5=B | Zone-diverse selection requires unique holdout candidates — the algorithm and constraint align | Yes |
| G5=B + G8=B | Unique holdout for originals + paired swaps — requires validation uniqueness (see Gap 3) | **Partially** |
| G8=B + G9=B | Swaps generated + excluded from aggregates — correct and coherent | Yes |
| G10=C + G11=C | 5 km buffer + holdout min ≥8 — feasibility not checked jointly (see Gap 2) | **Risk** |
| G11=C + G6=B | Raise positive minimums + ≥2 zones — may be jointly infeasible (see Gap 2) | **Risk** |
| G13=B + G16=A | One-hot lithology + force scaling — scaling dummy-encoded binary columns inflates the dimensionality slightly but is harmless for RF | Yes |
| G14=C + G15=A | LAB ablation + RF only — ablation on RF is straightforward and correct | Yes |
| G17=B + G18=B | Per-location metrics + mandatory gap diagnostic — both require holdout results to be disaggregated by holdout_candidate_id, which the new split_summary schema supports | Yes |
| G21=B + G22=B | Uncertainty map + no calibration — producing a variance map without calibrated probabilities is explicitly allowed and correctly documented as a limitation | Yes |

---

## 9. Recommended Sequencing Adjustments

The following is a concrete recommended order for v4 work. Items that are currently mis-sequenced or unsequenced are marked.

**Phase 1 — Pre-implementation (do before writing any v4 script):**
1. Fill G4 = B formally in the freeze record.
2. Fill G12 = [specific ratio, e.g. 25:1 and 50:1 comparison].
3. Add sub-gate to G12: "Move `BACKGROUND_PER_POSITIVE` to YAML."
4. Run the G10+G11+G6 feasibility analysis on v3 raster data. Adjust at least one of {G10 buffer distance, G11 positive minimum, G6 zone requirement} based on what NT data actually supports.
5. Specify eval region for G20 permutation importance (validation + holdout separately).
6. Decide v4 directory structure (scripts/ vs runs/v4/scripts/) before writing config.
7. Sign freeze record.

**Phase 2 — Core split work (scripts 06, then 07, then 08):**
1. Implement zone-diverse split generator (G4=B, G5=B, G6, G7).
2. Implement spatial buffer in split masks (G10).
3. Implement swapped pairs with validation uniqueness constraint (G8, enforcing Gap 3 fix).
4. Run split generator. Verify: unique holdout candidate IDs, ≥2 zones covered, swapped pairs have correct inversion.
5. Run sample builder (script 07) — no changes needed, but re-run on new splits.
6. Run evaluation (script 08) — add split_type passthrough columns.
7. Confirm G18: generate per-location holdout skill breakdown as part of metrics output.

**Phase 3 — Evaluation framework improvements (script 11 and config):**
1. Update aggregate metrics to filter original splits only (G9).
2. Add permutation importance on validation AND holdout separately (G20).
3. Add one-hot lithology encoding (G13) — this requires changes to script 03 and reprocessing vector predictors.
4. Add background ratio comparison (G12).
5. Add reproducibility manifest (G19).

**Phase 4 — Uncertainty and interpretation (after Phase 2-3 confirmed working):**
1. Build split-variance uncertainty map (G21) — only after splits are confirmed diverse.
2. Run LAB depth ablation (G14).
3. Update final model and prediction scripts (scripts 09-10).
4. Generate v4 model review report with all required components.

**Phase 5 — Deferred (not v4):**
1. Nested hyperparameter tuning.
2. Comparator model.
3. Probability calibration (G22=B: deferred).
4. Multi-resolution (G23=B: deferred).

---

## 10. Final Assessment of Roadmap Maturity

The roadmap is directionally correct but is not ready to freeze in its current state. Specific blockers:

1. **G4 is blank.** This must be filled before the freeze record can be signed. — **Blocker.**

2. **G10, G11, G6 feasibility is unknown.** These three decisions may jointly produce zero valid v4 splits. A 5-minute analysis against actual NT raster data would resolve this. — **Blocker.**

3. **G8 validation uniqueness constraint is missing.** If swaps are enabled without this, the holdout diversity guarantee breaks down in the swap set. — **Blocker.**

4. **G12 is empty.** — **Should-fix before freeze.**

5. **V3_LOGIC priority ordering puts uncertainty before buffer.** If that document is used as an implementation guide, the ordering will be followed in the wrong sequence. — **Should-fix before freeze.**

The remaining gaps (G20 region unspecified, split 8 anomaly unexamined, absolute paths in v3 archive, v4 directory structure, LAB importance vs causal relevance) are important but do not block implementation. They should be resolved in Phase 1 and documented in the freeze record.

If the five blockers above are resolved, the roadmap will be coherent and the v4 split generator can be implemented safely. The project would then be one well-executed v4 run away from having a scientifically defensible spatial evaluation of NT MVT prospectivity for the first time.

---

*All findings derived from direct inspection of `DECISIONS_TO_MAKE_V4.md`, `archive/v3/data/processed/models/metrics_by_split.csv`, `archive/v3/data/processed/splits/split_summary.csv`, `archive/v3/outputs/tables/v3_model_review.txt`, `research/V3_LOGIC_TO_SCRIPTS_AND_V4_IMPROVEMENTS.md`, `pipeline/core_scripts/00_config.py`, `ML_REVIEW_REPORT.md`, `VALIDATION_HOLDOUT_GAP_DIAGNOSIS.md`, `SPATIAL_SPLIT_FIX_PLAN.md`. No findings are derived from README or workflow documents alone.*
