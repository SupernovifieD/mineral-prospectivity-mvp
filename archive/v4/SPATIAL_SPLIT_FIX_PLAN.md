# Spatial Split Generator Fix Plan

**Repository**: NT MVT Mineral Prospectivity v3  
**Scope**: `scripts/06_make_spatial_splits.py`, `scripts/00_config.py`, `configs/v3_run_config.yml`, downstream reporting  
**Prepared after**: `ML_REVIEW_REPORT.md` and `VALIDATION_HOLDOUT_GAP_DIAGNOSIS.md`  
**Date**: 2026-05-14

---

## 1. Executive Summary

The v2 spatial split generator produced 10 accepted splits that used only 3 distinct holdout geographic locations. This happened because the generator iterates through candidate blocks in raster row-major order and accepts the first valid (holdout, validation) pair it finds for each holdout candidate. Since holdout candidate 1 paired with 5 different validation partners before the generator ever moved to candidate 2, the aggregate evaluation statistics conflate genuine generalization variance with within-location repetition noise.

This plan fixes the generator in two parts:

**Part A — Geographic diversity enforcement.** Generate all valid candidates first, group them by geographic zone (northern / central / southern NT), and select holdout candidates via round-robin across zones. Prevent any holdout candidate from being reused across accepted splits. Prefer validation partners from a different geographic zone than the holdout.

**Part B — Paired validation/holdout swaps.** For every accepted original pair (holdout=A, validation=B), generate a swapped counterpart (holdout=B, validation=A) when B also meets holdout criteria. Paired splits use the same two geographic regions in reversed roles, which isolates "model generalization" from "region inherent difficulty." Paired splits are not independent and must never be aggregated as if they were.

The goal is not to produce 10 independent geographic evaluations — with 70 positive pixels spread across NT that is probably not achievable. The goal is to ensure that the distinct geographic locations actually evaluated are as diverse as the data allows, and that the per-location difficulty is measured symmetrically.

---

## 2. Current Flaw in Detail

### Code path

The acceptance loop in `scripts/06_make_spatial_splits.py` (lines 100–172) runs:

```python
for holdout in candidate_blocks:          # row-major order
    if not passes_holdout_criteria(holdout):
        continue
    for validation in candidate_blocks:   # row-major order
        if not passes_validation_criteria(validation):
            continue
        if overlaps(validation, holdout):
            continue
        ...
        accepted.append(...)
        split_id += 1
        if len(accepted) >= TARGET_ACCEPTED_SPLITS:
            break
    if len(accepted) >= TARGET_ACCEPTED_SPLITS:
        break
```

`candidate_blocks` is ordered by ascending `idx`, which is the raster row-major enumeration index. Row 0 = northernmost NT pixels. Blocks that pass area and positive-count thresholds first appear at the **top of the raster** — the northern NT, where two tight clusters of positive pixels happen to exist.

The outer loop reaches holdout candidate 1 (NW cluster, 5 positives), finds 5 valid validation partners in row-major order, exhausts the target of 10 accepted splits, and exits. It never reaches holdout candidate 4, 5, or any candidate in central or southern NT.

### What the v2 splits actually contain

From `archive/v2/data/processed/splits/split_summary.csv`:

```
holdout_candidate_id: 1, 1, 1, 1, 1, 2, 2, 2, 2, 3
```

Three holdout locations. Both candidates 2 and 3 cover the same NE NT cluster (confirmed by exact coordinate matching of their positive pixels). The effective number of geographically independent holdout evaluations is 2, not 10.

From `archive/v2/data/processed/models/metrics_by_split.csv`, reconstructed skill scores:

```
Holdout candidate 1 (NW, 5 pos): skill 8.7×, 11.5×, 13.9×, 19.2×, 22.9× across 5 splits
Holdout candidate 2 (NE, 12 pos): skill 1.0×, 0.9×, 3.1×, 1.8× across 4 splits
Holdout candidate 3 (NE, same cluster, 12 pos): skill 1.4× in 1 split
```

Every split uses a validation partner from central NT (candidates 20, 21, 23, 24, 29) where the majority of training positives also live. Every holdout is in northern NT (geographically extreme relative to the training distribution).

---

## 3. Why the Flaw Matters

### The aggregate statistics are wrong

When `08_evaluate_random_forest_splits.py` writes `aggregate_metrics.csv`, it computes mean, median, and standard deviation across 10 rows. Those 10 rows contain 5 repetitions of one holdout location and 4+1 repetitions of another. The mean is dominated by inter-location performance differences, not generalization variance. The standard deviation measures within-location noise on top of inter-location differences. Neither statistic means what it appears to mean.

### The evaluation is structurally optimistic

The greedy row-major algorithm guarantees that validation blocks land in the same geographic zone as the training majority (central NT, y ≈ −1,664K to −1,787K) and holdout blocks land at the geographic extreme (northern NT, y ≈ −1,421K to −1,476K). This is the opposite of what a scientifically neutral design would produce: it makes validation easy relative to training and makes holdout systematically harder. The measured 21× AP gap is partly a structural artifact of this assignment, not purely a generalization signal.

### Repeating a holdout location does not add information

Five splits using holdout candidate 1 do not give five independent measurements of geographic generalization. They measure how much the choice of validation partner affects the model when evaluated on the same fixed holdout region. That is useful for quantifying within-split variance, but it does not tell you how well the model generalizes to other NT geographies.

---

## 4. Desired Behavior

After this fix, the split generator must satisfy these properties:

1. **Unique holdout locations**: No two accepted original splits share the same `holdout_candidate_id`.

2. **Geographic zone coverage**: Accepted original splits collectively draw holdout blocks from at least 2 distinct geographic zones (northern / central / southern NT). Draw from 3 zones if enough eligible candidates exist in each zone.

3. **Zone-diverse validation partners**: For each accepted holdout, prefer a validation candidate from a different geographic zone than the holdout. Fall back to same-zone if no cross-zone partner is available.

4. **Rejection transparency**: Every candidate block that was evaluated but rejected records the specific reason (insufficient area, insufficient positives, no valid partner found, no more room in holdout zone quota).

5. **Paired swap generation (when enabled)**: For each accepted original pair (holdout=A, validation=B), generate a swapped pair (holdout=B, validation=A) if B meets holdout criteria and if A meets validation criteria.

6. **Paired splits clearly marked**: Every swapped split records `split_type="swapped"` and `paired_split_id` pointing to its original. Aggregate evaluation code separates original and swapped statistics.

7. **Full reproducibility**: Given the same raster inputs and config, the generator produces identical splits on every run. No randomness is introduced into the candidate selection or pairing process. Randomness in downstream scripts (training sample selection) is unchanged.

8. **Backward-compatible split mask format**: Split mask rasters continue to use 0=outside, 1=train, 2=validation, 3=holdout. Downstream scripts require no changes to their core training/evaluation logic.

---

## 5. Proposed Algorithm: Part A — Geographic Diversity Enforcement

### Phase 1: Generate all candidate blocks (unchanged)

Same logic as current code. Enumerate square windows across the raster in row-major order. For each window, compute `valid_count`, `area_share`, and `positives`. Discard windows with zero valid pixels.

Record a `candidate_rejection_log` list alongside `candidate_blocks`.

### Phase 2: Pre-filter to holdout-eligible and validation-eligible candidates

Before the acceptance loop, separate the two roles:

```python
def passes_holdout(c, cfg):
    strict = (
        abs(c["area_share"] - cfg.STRICT_HOLDOUT_AREA) <= 0.03
        and c["positives"] >= cfg.STRICT_MIN_HOLDOUT_POSITIVES
    )
    fallback = (
        cfg.FALLBACK_AREA_MIN <= c["area_share"] <= cfg.FALLBACK_AREA_MAX
        and c["positives"] >= cfg.FALLBACK_MIN_POSITIVES
    )
    if strict:
        return True, "strict"
    if fallback:
        return True, "fallback"
    return False, f"area={c['area_share']:.3f} pos={c['positives']}"

def passes_validation(c, cfg):
    strict = (
        abs(c["area_share"] - cfg.STRICT_VALIDATION_AREA) <= 0.03
        and c["positives"] >= cfg.STRICT_MIN_VALIDATION_POSITIVES
    )
    fallback = (
        cfg.FALLBACK_AREA_MIN <= c["area_share"] <= cfg.FALLBACK_AREA_MAX
        and c["positives"] >= cfg.FALLBACK_MIN_POSITIVES
    )
    if strict:
        return True, "strict"
    if fallback:
        return True, "fallback"
    return False, f"area={c['area_share']:.3f} pos={c['positives']}"
```

Apply to all candidates. Record `holdout_eligible`, `holdout_rule`, `validation_eligible`, `validation_rule` for every candidate in the rejection log.

### Phase 3: Assign geographic zones

Compute zone thresholds from the extent of all valid raster pixels, not from raw raster dimensions:

```python
def assign_zones(candidate_blocks, valid, n_zones):
    """
    Divides the vertical extent of the VALID region into n_zones equal-height bands.
    Each candidate is assigned the zone containing its block centroid row.
    Uses valid-pixel extent, not raw raster extent, to avoid biasing toward
    NT boundary slivers at the top of the raster.
    """
    valid_rows, _ = np.where(valid)
    row_min = int(valid_rows.min())
    row_max = int(valid_rows.max())
    row_span = row_max - row_min
    zone_breakpoints = [row_min + int(row_span * k / n_zones) for k in range(n_zones + 1)]

    for c in candidate_blocks:
        row0, col0, row1, col1 = c["window"]
        centroid_row = (row0 + row1) / 2
        zone = n_zones - 1  # default: southernmost zone
        for z in range(n_zones):
            if centroid_row < zone_breakpoints[z + 1]:
                zone = z
                break
        c["zone"] = zone
        # Zone 0 = northernmost, zone n_zones-1 = southernmost

    zone_names = {0: "northern", 1: "central", 2: "southern"}  # for n_zones=3
    for c in candidate_blocks:
        c["zone_name"] = zone_names.get(c["zone"], f"zone_{c['zone']}")

    return zone_breakpoints
```

Zone assignment is deterministic: no randomness, based only on the raster geometry.

### Phase 4: Build sorted holdout candidate lists by zone

```python
N_ZONES = cfg.SPLIT_N_GEOGRAPHIC_ZONES  # = 3

holdout_eligible_all = [c for c in candidate_blocks if c["holdout_eligible"]]
holdout_by_zone = {}
for z in range(N_ZONES):
    # Sort within each zone by candidate_id (ascending) for reproducibility.
    holdout_by_zone[z] = sorted(
        [c for c in holdout_eligible_all if c["zone"] == z],
        key=lambda x: x["candidate_id"],
    )

validation_eligible_all = [c for c in candidate_blocks if c["validation_eligible"]]
```

### Phase 5: Round-robin zone selection for holdout candidates

```python
used_as_holdout = set()   # candidate_ids used as holdout
used_as_val_in_swap = set()  # if generating swaps, track val candidates used
zone_cursors = {z: 0 for z in range(N_ZONES)}

original_pairs = []   # list of (holdout_candidate, validation_candidate, rule_type)

zones_with_candidates = [z for z in range(N_ZONES) if holdout_by_zone[z]]
zone_cycle = list(zones_with_candidates)  # deterministic: ascending zone index

while len(original_pairs) < cfg.TARGET_ACCEPTED_SPLITS:
    made_progress = False

    for zone in zone_cycle:
        # Find next unused holdout candidate in this zone.
        while zone_cursors[zone] < len(holdout_by_zone[zone]):
            holdout = holdout_by_zone[zone][zone_cursors[zone]]
            zone_cursors[zone] += 1

            if holdout["candidate_id"] in used_as_holdout:
                continue  # already used as holdout — skip

            holdout_block = make_block_mask(valid.shape, holdout["window"]) & valid

            # Find a valid validation partner.
            # Sort: candidates in a DIFFERENT zone come first (zone != holdout["zone"]),
            # then by ascending candidate_id. This makes the selection deterministic
            # and geographically balanced.
            sorted_val_candidates = sorted(
                [c for c in validation_eligible_all
                 if c["candidate_id"] != holdout["candidate_id"]],
                key=lambda c: (int(c["zone"] == holdout["zone"]), c["candidate_id"]),
            )

            partner = None
            partner_rule = None
            for val in sorted_val_candidates:
                val_block = make_block_mask(valid.shape, val["window"]) & valid
                if np.any(val_block & holdout_block):
                    continue  # overlap
                train_region = valid & ~val_block & ~holdout_block
                train_positives = int((labels[train_region] == 1).sum())
                if train_positives < cfg.STRICT_MIN_TRAIN_POSITIVES:
                    continue
                # Partner found.
                both_strict = holdout["holdout_rule"] == "strict" and val["validation_rule"] == "strict"
                partner_rule = "strict" if both_strict else "fallback"
                partner = val
                break

            if partner is None:
                # Log that this holdout candidate has no valid partner.
                continue

            original_pairs.append((holdout, partner, partner_rule))
            used_as_holdout.add(holdout["candidate_id"])
            made_progress = True
            break  # advance to next zone in the round-robin

        if len(original_pairs) >= cfg.TARGET_ACCEPTED_SPLITS:
            break

    if not made_progress:
        break  # no more valid pairs in any zone
```

**Key invariants enforced by this loop:**
- Each holdout candidate appears at most once in `original_pairs` (enforced by `used_as_holdout`).
- Holdout zones are selected in ascending zone order on each round, which distributes holdout blocks across zones before re-visiting any zone.
- If one zone runs out of eligible candidates, the loop continues with remaining zones. It does not fail.
- The validation candidate is chosen deterministically by (cross-zone preference, then candidate_id). The same inputs always produce the same output.

### Phase 6: Write original split masks

```python
split_id = 1
accepted_rows = []

for holdout, val, rule_type in original_pairs:
    holdout_block = make_block_mask(valid.shape, holdout["window"]) & valid
    val_block = make_block_mask(valid.shape, val["window"]) & valid
    train_region = valid & ~val_block & ~holdout_block

    split_mask = np.zeros(valid.shape, dtype="uint8")
    split_mask[train_region] = 1
    split_mask[val_block] = 2
    split_mask[holdout_block] = 3

    split_path = cfg.SPLITS_DIR / f"split_{split_id:03d}_mask.tif"
    # ... write GeoTIFF ...

    row = {
        "split_id": split_id,
        "split_mask": str(split_path),
        "split_type": "original",
        "paired_split_id": None,
        "holdout_candidate_id": holdout["candidate_id"],
        "validation_candidate_id": val["candidate_id"],
        "holdout_zone": holdout["zone_name"],
        "validation_zone": val["zone_name"],
        "rule_type": rule_type,
        "uses_buffer": False,
        "buffer_distance_m": 0,
    }
    row.update(summarize_region("train", split_mask == 1, valid, labels))
    row.update(summarize_region("validation", split_mask == 2, valid, labels))
    row.update(summarize_region("holdout", split_mask == 3, valid, labels))
    accepted_rows.append(row)

    print(f"Original split {split_id}: holdout={holdout['candidate_id']} "
          f"({holdout['zone_name']}), val={val['candidate_id']} ({val['zone_name']}), "
          f"rule={rule_type}")
    split_id += 1
```

---

## 6. Proposed Algorithm: Part B — Paired Validation/Holdout Swaps

### Motivation

After Part A, each original pair has holdout=A and validation=B. We know A performed as holdout with training data = NT∖A∖B. We do not know whether A is a hard holdout in general or whether it is hard only when B is the validation companion.

The swapped pair sets holdout=B, validation=A, and trains on NT∖B∖A — which is **the same training region** as the original (since NT∖A∖B = NT∖B∖A). This means:

- The training data pool is identical between original and swapped split.
- The model sees the same training geographic extent.
- The only difference is which block is evaluated as holdout and which as validation.
- Comparing the original holdout score on A against the swapped holdout score on A (which is the validation score in the swap) directly answers: "Is A's skill level stable when it moves from holdout role to validation role?"

This breaks the correlation: if A scores 15× as holdout in the original, and A also scores ~15× as validation in the swap, then A's difficulty is stable. If A scores 150× as validation in the swap, then A is being measured as a "soft" validation target even though its raw geology does not change — which indicates the model is generalizing to A differently depending on context, not just that A is easy.

### Swap eligibility check

A swap of pair (holdout=A, validation=B) is eligible when:
1. B passes the holdout criteria (area, positives) — because B becomes holdout in the swap.
2. A passes the validation criteria — because A becomes validation in the swap.
3. Training region (NT∖A∖B) has enough training positives — automatically satisfied if original was valid, since training region is identical.
4. The swap holdout candidate (B) has not already been used as holdout in another original split OR another swap.

Note on condition 4: if original split 1 uses validation=B, and original split 2 also uses validation=B (with a different holdout), then both swaps would try to use B as holdout. This would make B appear twice as holdout in the swap set, violating the diversity principle. To prevent this: enforce that no two original splits share the same validation_candidate_id if swapping is enabled. This requires a minor adjustment to the validation partner selection in Phase 5 — track `used_as_val_in_planned_swap` and avoid reusing validation candidates across originals.

### Implementation

```python
if cfg.SPLIT_GENERATE_SWAPPED_PAIRS:
    swap_pairs = []
    used_as_swap_holdout = set()

    for orig_idx, (holdout_orig, val_orig, _) in enumerate(original_pairs):
        orig_split_id = orig_idx + 1  # 1-based

        # Check swap eligibility.
        val_ok_as_holdout, _ = passes_holdout(val_orig, cfg)
        holdout_ok_as_val, _ = passes_validation(holdout_orig, cfg)

        if not val_ok_as_holdout:
            print(f"Split {orig_split_id}: swap skipped — val cand {val_orig['candidate_id']} "
                  f"does not meet holdout criteria.")
            continue
        if not holdout_ok_as_val:
            print(f"Split {orig_split_id}: swap skipped — holdout cand {holdout_orig['candidate_id']} "
                  f"does not meet validation criteria.")
            continue
        if val_orig["candidate_id"] in used_as_swap_holdout:
            print(f"Split {orig_split_id}: swap skipped — val cand {val_orig['candidate_id']} "
                  f"already used as swap holdout.")
            continue

        # Training region is identical to original (NT minus both blocks).
        holdout_block = make_block_mask(valid.shape, holdout_orig["window"]) & valid
        val_block = make_block_mask(valid.shape, val_orig["window"]) & valid
        train_region = valid & ~holdout_block & ~val_block
        train_positives = int((labels[train_region] == 1).sum())
        if train_positives < cfg.STRICT_MIN_TRAIN_POSITIVES:
            print(f"Split {orig_split_id}: swap skipped — insufficient training positives ({train_positives}).")
            continue

        swap_pairs.append((val_orig, holdout_orig, orig_split_id))
        used_as_swap_holdout.add(val_orig["candidate_id"])

    for swap_holdout, swap_val, paired_orig_split_id in swap_pairs:
        swap_holdout_block = make_block_mask(valid.shape, swap_holdout["window"]) & valid
        swap_val_block = make_block_mask(valid.shape, swap_val["window"]) & valid
        train_region = valid & ~swap_holdout_block & ~swap_val_block

        split_mask = np.zeros(valid.shape, dtype="uint8")
        split_mask[train_region] = 1
        split_mask[swap_val_block] = 2      # original holdout → now validation
        split_mask[swap_holdout_block] = 3  # original validation → now holdout

        split_path = cfg.SPLITS_DIR / f"split_{split_id:03d}_mask.tif"
        # ... write GeoTIFF ...

        row = {
            "split_id": split_id,
            "split_mask": str(split_path),
            "split_type": "swapped",
            "paired_split_id": paired_orig_split_id,
            "holdout_candidate_id": swap_holdout["candidate_id"],
            "validation_candidate_id": swap_val["candidate_id"],
            "holdout_zone": swap_holdout["zone_name"],
            "validation_zone": swap_val["zone_name"],
            "rule_type": "swap",
            "uses_buffer": False,
            "buffer_distance_m": 0,
        }
        row.update(summarize_region("train", split_mask == 1, valid, labels))
        row.update(summarize_region("validation", split_mask == 2, valid, labels))
        row.update(summarize_region("holdout", split_mask == 3, valid, labels))
        accepted_rows.append(row)

        print(f"Swapped split {split_id}: holdout={swap_holdout['candidate_id']} "
              f"({swap_holdout['zone_name']}), val={swap_val['candidate_id']} ({swap_val['zone_name']}), "
              f"paired_orig={paired_orig_split_id}")
        split_id += 1
```

---

## 7. How to Avoid Treating Paired Swaps as Independent

Swapped splits are **not** independent of their original partners. They share:
- The same two geographic blocks (A and B).
- The same training region (NT∖A∖B).
- The same training data pool (because the only difference is which block is holdout and which is validation, and training draws from neither).

**Do not include swapped splits in overall aggregate metrics.** The aggregate statistics in `aggregate_metrics.csv` should be computed from original splits only.

**Do produce a separate paired comparison table.** For each pair (original, swap), report:

```
paired_split_id | holdout_cand | holdout_zone | region | skill_in_original | skill_in_swap
```

This table answers: "For region A, does the holdout score change when A is the holdout vs when A is the validation role?" If it changes substantially, role assignment is inflating or deflating the measurement. If it is stable, the per-region difficulty estimate is reliable.

### Required changes to `08_evaluate_random_forest_splits.py`

The training/evaluation loop does not need to change. Every split (original or swapped) trains on `split_mask == 1` and evaluates on `split_mask == 2` (validation) and `split_mask == 3` (holdout). No code change is needed here — the masks encode all role information.

The only change: when reading `split_summary`, check whether the file contains the new columns (`split_type`, `paired_split_id`). If not present, treat all splits as original (backward compatibility). If present, pass them through to `metrics_by_split.csv` by adding those columns to the output.

```python
# In 08_evaluate_random_forest_splits.py, when building the output row:
meta_cols = ["split_type", "paired_split_id"] 
for col in meta_cols:
    if col in split_summary.columns:
        row[col] = getattr(split, col)
    else:
        row[col] = None
```

### Required changes to `11_summarize_v3_outputs.py`

When computing aggregate metrics, filter first:

```python
metrics_original = metrics[metrics["split_type"] == "original"]
# Use metrics_original for all aggregate statistics.
aggregate = compute_aggregate(metrics_original)
aggregate.to_csv(cfg.AGGREGATE_METRICS, index=False)

# Separately, produce paired comparison table if swapped splits exist.
if "paired_split_id" in metrics.columns:
    metrics_swapped = metrics[metrics["split_type"] == "swapped"]
    if not metrics_swapped.empty:
        produce_paired_comparison_table(metrics_original, metrics_swapped, cfg)
```

The paired comparison table function produces one row per (original_split_id, region):

```python
def produce_paired_comparison_table(metrics_orig, metrics_swap, cfg):
    rows = []
    for _, orig_row in metrics_orig.iterrows():
        orig_split_id = orig_row["split_id"]
        matching_swaps = metrics_swap[metrics_swap["paired_split_id"] == orig_split_id]
        for _, swap_row in matching_swaps.iterrows():
            # Find the same candidate's score in both roles.
            # Holdout candidate in original = validation candidate in swap.
            # Holdout candidate in swap = validation candidate in original.
            rows.append({
                "original_split_id": orig_split_id,
                "swap_split_id": swap_row["split_id"],
                "candidate_as_holdout_orig_ap": orig_row["average_precision"],  # original holdout score
                "candidate_as_holdout_swap_ap": swap_row["average_precision"],  # swap holdout score
                "original_holdout_region": orig_row["region"],
                "swap_holdout_region": swap_row["region"],
            })
    pd.DataFrame(rows).to_csv(cfg.TABLES_DIR / "paired_split_comparison.csv", index=False)
```

The report in `v3_model_review.txt` must include this statement:

> Swapped splits are paired evaluations. They share training data with their original partner. They are excluded from aggregate statistics. Per-pair results are in `paired_split_comparison.csv`.

---

## 8. Required Code Changes

### `scripts/06_make_spatial_splits.py` — major rewrite of acceptance loop

**Preserve unchanged:**
- `load_config()` function
- `block_slices()` function
- `make_block_mask()` function
- `summarize_region()` function
- `area_matches_strict()` function
- The raster loading block
- The candidate block enumeration loop

**Add new functions:**
- `passes_holdout(c, cfg) -> (bool, str)` — returns eligibility and rule name
- `passes_validation(c, cfg) -> (bool, str)` — same
- `assign_zones(candidate_blocks, valid, n_zones) -> zone_breakpoints` — as above
- `write_split_mask(valid, holdout_block, val_block, split_path, profile) -> None`
- `produce_paired_comparison_table(...)` — or move to script 11

**Replace** the double for-loop (lines 100–172) with:
- Phase 2: pre-filter candidates
- Phase 3: assign zones
- Phase 4: group holdout candidates by zone
- Phase 5: round-robin acceptance loop
- Phase 6: write original split masks
- Phase 7 (conditional): generate and write swapped pairs

**Write new output artifact:**
- `candidate_blocks.csv` — all candidates with zone, holdout_eligible, validation_eligible, holdout_rule, validation_rule

### `scripts/00_config.py` — add split diversity constants

Add after the existing split constraint constants (around line 81):

```python
# Split generator diversity settings.
SPLIT_N_GEOGRAPHIC_ZONES = 3
SPLIT_PREFER_DIVERSE_VALIDATION_ZONES = True
SPLIT_GENERATE_SWAPPED_PAIRS = True
# Each holdout candidate may appear as holdout in at most this many original splits.
# Set to 1 to enforce strict diversity (recommended).
SPLIT_MAX_HOLDOUT_CANDIDATE_REUSE = 1
```

These go in `00_config.py` because they are structural decisions, not model tuning parameters. They do not belong in `v3_run_config.yml` alongside feature names and RF hyperparameters.

### `configs/v3_run_config.yml` — no change required

The split diversity parameters are pipeline architecture decisions, not tunable scientific parameters. Adding them to YAML would invite accidental changes between runs. Keep them in `00_config.py` where they are visible alongside the existing split constraints (`STRICT_HOLDOUT_AREA`, etc.).

If the project evolves to support multiple run configs per version (e.g., a sensitivity analysis run with different zone counts), move them to YAML at that time.

### `scripts/08_evaluate_random_forest_splits.py` — minor additions

1. When reading split_summary, pass `split_type` and `paired_split_id` through to the output rows (see Section 7).
2. No change to training or evaluation logic.

### `scripts/11_summarize_v3_outputs.py` — aggregate filter + paired table

1. Filter to `split_type == "original"` before computing aggregate metrics.
2. Call `produce_paired_comparison_table()` if swapped splits exist.
3. Add to the review report: state that swapped splits are excluded from aggregates.

---

## 9. Required Output Artifacts

### Existing artifacts — updated schema

**`data/processed/splits/split_summary.csv`**

New columns added; old columns preserved:

| Column | Type | Description |
|---|---|---|
| `split_id` | int | Sequential identifier across originals and swaps |
| `split_mask` | str | Absolute path to split mask raster |
| `split_type` | str | `"original"` or `"swapped"` |
| `paired_split_id` | int or null | For swapped splits: the original split_id they pair with |
| `holdout_candidate_id` | int | Block candidate index |
| `validation_candidate_id` | int | Block candidate index |
| `holdout_zone` | str | `"northern"`, `"central"`, or `"southern"` |
| `validation_zone` | str | Same |
| `rule_type` | str | `"strict"`, `"fallback"`, or `"swap"` |
| `uses_buffer` | bool | False in v3 |
| `buffer_distance_m` | int | 0 in v3 |
| `train_pixels` | int | Valid pixels in training region |
| `train_positives` | int | Positive pixels in training region |
| `validation_pixels` | int | Valid pixels in validation region |
| `validation_positives` | int | Positive pixels in validation region |
| `holdout_pixels` | int | Valid pixels in holdout region |
| `holdout_positives` | int | Positive pixels in holdout region |

**`data/processed/models/metrics_by_split.csv`**

Add `split_type` and `paired_split_id` passthrough columns.

**`data/processed/models/aggregate_metrics.csv`**

No schema change. Content change: computed only from original splits.

### New artifacts

**`data/processed/splits/candidate_blocks.csv`**

One row per candidate block enumerated by the generator. Columns:

```
candidate_id, window_row0, window_col0, window_row1, window_col1,
area_share, positives, zone, zone_name,
holdout_eligible, holdout_rule,
validation_eligible, validation_rule
```

This artifact is for debugging only — it lets you inspect why certain blocks were rejected and what the zone distribution of all candidates looks like.

**`outputs/tables/paired_split_comparison.csv`**

One row per (original_split_id, region, candidate). Produced only when swapped splits exist. Columns:

```
original_split_id, swap_split_id,
holdout_candidate_id, holdout_zone,
validation_candidate_id, validation_zone,
original_holdout_ap, original_holdout_skill,
swap_holdout_ap, swap_holdout_skill,
original_val_ap, original_val_skill,
swap_val_ap, swap_val_skill
```

`skill` = AP / baseline, where baseline = positives / pixels in that region.

---

## 10. Acceptance Criteria

The fix is complete when all of the following pass:

1. `split_summary.csv` contains `split_type`, `paired_split_id`, `holdout_zone`, and `validation_zone` columns.

2. Among rows where `split_type == "original"`: all values in `holdout_candidate_id` are unique. No duplicate holdout locations.

3. Among rows where `split_type == "original"`: `holdout_zone` takes at least 2 distinct values (3 preferred). If only 2 are achieved, there must be a logged reason why the third zone had no eligible candidates.

4. At least `MIN_ACCEPTED_SPLITS_FOR_NON_EXPLORATORY` (=5) original splits were accepted. If fewer, the run is labeled exploratory in the summary report.

5. `aggregate_metrics.csv` was computed from original splits only. Verify by checking `split_count` = number of original splits, not total splits including swaps.

6. `candidate_blocks.csv` exists and contains all blocks enumerated by the generator.

7. For every swapped split, `paired_split_id` matches an existing original split_id.

8. For every swapped split, the `holdout_candidate_id` of the swap equals the `validation_candidate_id` of its original partner, and vice versa.

9. No `candidate_id` appears as `holdout_candidate_id` in more than one original split.

10. No `candidate_id` appears as `holdout_candidate_id` in more than one swapped split.

11. Running the script twice with the same inputs produces identical output (reproducibility).

---

## 11. Testing and Verification Checklist

Run these checks immediately after the first successful execution. Do not proceed to scripts 07–11 if any check fails.

### Checklist

- [ ] Print all `holdout_candidate_id` values from original splits. Confirm no duplicates:
  ```python
  df = pd.read_csv(cfg.SPLIT_SUMMARY)
  orig = df[df["split_type"] == "original"]
  assert orig["holdout_candidate_id"].nunique() == len(orig), "Holdout candidate IDs are not unique"
  ```

- [ ] Print all `holdout_zone` values from original splits. Confirm at least 2 distinct zones:
  ```python
  assert orig["holdout_zone"].nunique() >= 2, f"Only {orig['holdout_zone'].nunique()} zone(s) covered"
  ```

- [ ] Confirm swapped split holdout/validation inversion is correct:
  ```python
  swapped = df[df["split_type"] == "swapped"]
  for _, srow in swapped.iterrows():
      orig_row = orig[orig["split_id"] == srow["paired_split_id"]].iloc[0]
      assert srow["holdout_candidate_id"] == orig_row["validation_candidate_id"]
      assert srow["validation_candidate_id"] == orig_row["holdout_candidate_id"]
  ```

- [ ] Confirm aggregate metrics used only original splits. Check `split_count` in `aggregate_metrics.csv` equals `len(orig)`, not `len(df)`.

- [ ] Open `candidate_blocks.csv` and verify the zone distribution is plausible. Northern NT should have the fewest holdout-eligible candidates (sparse valid pixels near the boundary). Southern NT should have more.

- [ ] Run `06_make_spatial_splits.py` twice. Diff the output CSVs. Confirm identical content.

- [ ] For each split mask, load the raster and verify:
  - No pixel is simultaneously train (1) and validation (2) or holdout (3).
  - The total valid-pixel count matches `valid_pixels` from the script log.
  - `holdout_positives` in the summary matches the count of `labels == 1` within `split_mask == 3`.

- [ ] Load `candidate_blocks.csv` and confirm every candidate with `holdout_eligible=True` in a zone that was assigned to at least one original split was either used or has a logged reason for rejection (no valid partner found, zone quota full, etc.).

- [ ] If `SPLIT_GENERATE_SWAPPED_PAIRS = True` and no swapped splits were generated, confirm the script printed the reason for each skipped swap.

---

## 12. Risks and Caveats

### Risk 1: Not enough eligible holdout candidates in all zones

The NT has 70 positive pixels. Southern NT has the majority of positives (y < −2,000K, McArthur River group). Northern NT has 17 positives in two clusters. Central NT has ~40 positives. The square block size (≈10% of valid NT pixels, ≈10 km side) may not enclose 5+ positives in every sub-region of the NT.

**Expected behavior**: The round-robin loop skips zones that have no eligible candidates. If only northern and central NT have holdout-eligible blocks, the output will have `holdout_zone` = "northern" and "central" only, and the script will print a warning. The fix remains valuable even if only 2 zones are achieved — it still prevents reuse of the same holdout candidate.

**Mitigation**: If southern NT consistently produces zero holdout-eligible candidates, consider reducing `STRICT_MIN_HOLDOUT_POSITIVES` from 5 to 4 (using the fallback rule) for candidates in underrepresented zones. This is a policy decision to be made after seeing the candidate_blocks.csv output on actual data.

### Risk 2: Fewer than 10 original splits

With 3 geographic zones and a max-reuse-per-holdout of 1, the theoretical maximum of original splits is bounded by the number of distinct holdout-eligible candidates. If only 8 candidates exist across all zones, the maximum is 8 original splits. If only 3 exist, the maximum is 3.

**Expected behavior**: The script accepts as many as it can and prints the total. If fewer than `MIN_ACCEPTED_SPLITS_FOR_NON_EXPLORATORY=5`, the run is labeled exploratory. Do not lower this threshold to compensate for split diversity enforcement — doing so would hide the data limitation.

### Risk 3: Swapped pairs are mistakenly included in aggregates

The most likely operational error is a developer (or a future script version) computing aggregate metrics across all rows of `metrics_by_split.csv` without filtering by `split_type`. If this happens, the aggregate will be biased downward (because swapped splits using blocks selected as easy validation candidates will likely produce lower holdout scores when those blocks are evaluated as holdouts).

**Mitigation**: Add an assertion in `11_summarize_v3_outputs.py` before computing aggregates:

```python
assert (metrics["split_type"] == "original").any(), (
    "No original splits found in metrics. Did split generation run correctly?"
)
metrics_for_aggregate = metrics[metrics["split_type"] == "original"]
```

Add a comment in `08_evaluate_random_forest_splits.py` above the aggregation block:

```python
# IMPORTANT: Do not aggregate across all splits. Swapped splits are paired
# evaluations and must be excluded from aggregate statistics. See SPATIAL_SPLIT_FIX_PLAN.md.
```

### Risk 4: Validation candidate reuse across original splits

If two original splits share the same validation candidate, and swap generation is enabled, both swaps will try to use that validation candidate as holdout. The code above prevents this via `used_as_swap_holdout`. But if `SPLIT_GENERATE_SWAPPED_PAIRS = False`, validation candidates may still repeat across originals. This is acceptable when swaps are disabled — the only constraint on validation reuse is that the same block appearing as validation in multiple original splits produces correlated validation scores (the same region is assessed multiple times), which is harmless if aggregate statistics focus on holdout scores.

**Mitigation when swaps are enabled**: The inner loop in Phase 5 should additionally check whether a validation candidate is already used as validation in a prior accepted pair. Add `used_as_validation = set()` and exclude already-used validation candidates.

### Risk 5: Geographic zone thresholds may cut through positive pixel clusters

The zone boundaries are computed as equal-height row bands over the valid NT extent. A cluster of positives that straddles the northern/central boundary could be split between zones. Some of those positives would be in training (one zone) and some in holdout (another zone).

This is not a correctness issue — the same thing happened with v2 block boundaries. It is inherent to the square-block geometry. The zone assignment only determines which zone a CANDIDATE BLOCK is assigned to; the actual split boundaries are still defined by the block geometry, not the zone boundary.

---

## 13. Recommended Implementation Sequence

Follow this order. Run verification at each numbered step before proceeding.

**Step 1 — Add constants to `00_config.py`.**

Add `SPLIT_N_GEOGRAPHIC_ZONES = 3`, `SPLIT_MAX_HOLDOUT_CANDIDATE_REUSE = 1`, `SPLIT_PREFER_DIVERSE_VALIDATION_ZONES = True`, `SPLIT_GENERATE_SWAPPED_PAIRS = True`. No other file changes yet. Confirm `python scripts/00_config.py` imports without error.

**Step 2 — Rewrite `06_make_spatial_splits.py` — Part A only (diversity enforcement, no swaps).**

Implement Phases 1–6 as described. Set `SPLIT_GENERATE_SWAPPED_PAIRS = False` temporarily. Run on actual data and examine:
- `candidate_blocks.csv`: how many candidates per zone? Are there holdout-eligible candidates in all 3 zones?
- `split_summary.csv`: how many original splits were accepted? How many distinct holdout zones?
- Console output: were any zones skipped due to no eligible candidates?

Do NOT proceed to Part B until Part A produces an acceptable set of original splits.

**Step 3 — Run scripts 07 and 08 on the new original splits.**

Confirm `split_training_samples.csv` and `metrics_by_split.csv` write correctly. Confirm `metrics_by_split.csv` has the passthrough `split_type` and `paired_split_id` columns. Inspect holdout metrics per zone — confirm that different holdout zones produce meaningfully different skill scores.

**Step 4 — Enable Part B (swap generation).**

Set `SPLIT_GENERATE_SWAPPED_PAIRS = True`. Re-run `06_make_spatial_splits.py`. Examine:
- How many swapped splits were generated vs skipped? Print the reason for each skip.
- Verify the holdout/validation inversion in split_summary using the acceptance criteria check above.

**Step 5 — Re-run scripts 07 and 08 on all splits (originals + swaps).**

Confirm metrics are computed for all splits. Confirm `split_type` flows through to `metrics_by_split.csv`.

**Step 6 — Update `11_summarize_v3_outputs.py`.**

Add the original-split filter before aggregate computation. Add paired comparison table generation. Re-run and inspect `paired_split_comparison.csv`. Confirm the paired table makes geological sense: if region A is consistently harder as holdout than as validation, the table should show it clearly.

**Step 7 — Full pipeline run from script 07 through 11.**

Do not re-run scripts 01–05 unless rasters have changed. Re-run 06 → 07 → 08 → 09 → 10 → 11. Confirm all output files exist. Confirm `v3_model_review.txt` states the accepted split count, whether the run is exploratory, and that swapped splits are excluded from aggregates.

**Step 8 — Run the verification checklist (Section 11).**

All items must pass before reporting v3 results.

---

## 14. What This Fix Does Not Solve

For completeness, two problems identified in `VALIDATION_HOLDOUT_GAP_DIAGNOSIS.md` are not addressed by this fix:

**Distribution shift in the NE NT high-gravity terrain.** The NE cluster (holdout candidates 2 and 3 in v2) has gravity mean 207 vs training positive mean 82. This is a training data coverage problem. Improving split diversity will correctly expose this failure in the evaluation metrics — it will not make the model perform better on that terrain. A better geographic distribution of holdout locations makes the failure visible across more splits, which is scientifically correct even though it may lower the aggregate holdout score.

**No spatial buffer.** The current split design has no exclusion zone between training and evaluation regions. This allows spatial autocorrelation from bilinearly-resampled continuous rasters to bleed across split boundaries. This plan does not add a buffer — that is a separate decision that affects all splits, not just their geographic selection. If a buffer is added later, it must be added to both original and swapped splits consistently.

---

*Sources: `scripts/06_make_spatial_splits.py`, `scripts/00_config.py`, `configs/v3_run_config.yml`, `ML_REVIEW_REPORT.md` (sections 4, 8), `VALIDATION_HOLDOUT_GAP_DIAGNOSIS.md` (sections 3, 5, 8). All algorithm descriptions were derived from the actual code, not the workflow document.*
