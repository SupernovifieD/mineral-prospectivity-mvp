# Decisions To Make For V4 (NT MVT Prospectivity)

Created: 2026-05-16

This is the v4 decision-gates document, built from:

- `ML_REVIEW_REPORT.md`
- `VALIDATION_HOLDOUT_GAP_DIAGNOSIS.md`
- `SPATIAL_SPLIT_FIX_PLAN.md`

Use this before implementing v4 scripts. Fill the `Your choice` column and freeze the decisions.

## Evidence Tags

- `MR` = `ML_REVIEW_REPORT.md`
- `VG` = `VALIDATION_HOLDOUT_GAP_DIAGNOSIS.md`
- `SF` = `SPATIAL_SPLIT_FIX_PLAN.md`

## Decision Table (V4)

| Gate | Topic | Why This Is Needed (from reviews) | Options | Recommended Default | Your Choice (fill) |
|---|---|---|---|---|---|
| G1 | Scientific objective and allowed claims | v2/v3 evaluation is not yet benchmark-grade; claims must be controlled (`MR`) | A) exploratory learning run B) screening benchmark C) decision-grade targeting | B + explicit "screening only" language | `[ A and B ]` |
| G2 | Study area and grid | Keep one axis stable while fixing evaluation flaws (`MR`) | A) NT 500 m B) change resolution C) expand ROI | A (NT, EPSG:3577, 500 m) | `[ A ]` |
| G3 | Label definition and quality policy | low positive count and mixed confidence can destabilize results (`MR`, `VG`) | A) all MVT points B) high-confidence subset C) weighted labels by confidence | A for main run + optional B sensitivity run | `[ A ]` |
| G4 | Split generator strategy | current greedy row-major selection caused only 3 holdout locations (`MR`, `VG`, `SF`) | A) keep greedy B) zone-diverse deterministic selection | B | `[ B ]` |
| G5 | Holdout diversity rule | repeated holdout locations invalidate aggregate interpretation (`MR`, `SF`) | A) allow repeats B) max 1 use per holdout candidate | B (strict uniqueness for original splits) | `[ B ]` |
| G6 | Geographic zone coverage target | ensure holdouts represent more than one NT geography (`SF`) | A) no zone rule B) >=2 zones C) target 3 zones | C, fallback to B with logged reason | `[ B ]` |
| G7 | Validation partner policy | validation currently too easy and geography-biased (`VG`, `SF`) | A) first valid partner B) prefer cross-zone partner | B | `[ B ]` |
| G8 | Paired swap splits | separates region difficulty from role assignment effects (`SF`) | A) disabled B) enabled and flagged as paired | B (if enough valid candidates) | `[ A ]` |
| G9 | Aggregation policy for swapped splits | swapped are not independent and must not enter main aggregates (`SF`) | A) aggregate all splits B) aggregate originals only | B | `[ B ]` |
| G10 | Spatial buffer between train and eval | no buffer likely over-optimistic near boundaries (`MR`, `VG`) | A) no buffer B) 2 km C) 5 km D) 10 km | C (5 km) initial; test D in sensitivity | `[ D ]` |
| G11 | Split acceptance thresholds | current minimum positives too low for stable metrics (`MR`, `VG`) | A) keep 5/5/40 B) raise holdout min C) raise both val+holdout mins | B or C (target holdout >= 8) | `[ Lower to 3/3/30 ]` |
| G12 | Background sampling design | class imbalance and sampling policy affect robustness (`MR`) | A) 50:1 stratified B) 25:1 C) 100:1 D) compare multiple | D (compare at least two ratios) | `[ A ]` |
| G13 | Lithology encoding | ordinal lithology code may create false ordering (`MR`) | A) keep ordinal `lithology_code` B) one-hot lithology classes | B | `[ B ]` |
| G14 | LAB depth feature policy | geological relevance is uncertain for shallow MVT processes (`MR`) | A) keep as-is B) remove C) run ablation and decide | C | `[ A ]` |
| G15 | Model family for v4 | avoid complexity before evaluation is fixed (`MR`) | A) RF only B) RF + one comparator model | B (RF baseline + one comparator) | `[ A ]` |
| G16 | Scaling policy with RF | scaler is not needed for RF but useful for model portability (`MR`) | A) force scaling B) model-dependent scaling | B | `[ A ]` |
| G17 | Primary success metrics | AP alone can be unstable with tiny positives (`MR`, `VG`) | A) AP only B) AP + top-k recall/enrichment + per-location reporting | B | `[ B ]` |
| G18 | Validation-holdout gap protocol | 21x gap must be diagnosed before claim-making (`MR`, `VG`) | A) ignore gap B) mandatory diagnostic report each run | B | `[ B ]` |
| G19 | Reproducibility artifacts | current artifacts have portability and audit gaps (`MR`) | A) keep current B) add manifest/checksums/relative paths | B | `[ B ]` |
| G20 | Feature importance reporting | impurity importance alone is weak evidence (`MR`) | A) impurity only B) add permutation importance on eval regions | B | `[ A ]` |
| G21 | Uncertainty deliverable | v3 has no uncertainty map (`MR`) | A) no uncertainty B) split-variance uncertainty map | B | `[ A ]` |
| G22 | Calibration policy | calibration is premature without stable evaluation (`MR`) | A) calibrate now B) postpone until split design is stable | B | `[ B ]` |
| G23 | Multi-resolution strategy | premature before single-resolution stability (`MR`) | A) add multi-resolution now B) defer | B | `[ B ]` |

---

## Freeze Record (fill before coding starts)

- Freeze date: `[YYYY-MM-DD]`
- Version tag: `[v4-plan-locked-01]`
- Locked by: `[name]`
- Notes on unresolved gates: `[text]`

---



