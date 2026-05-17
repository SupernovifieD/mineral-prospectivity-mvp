"""Build repeated spatial train/validation/holdout split masks for v5.

This generator implements:
1) deterministic zone-diverse holdout selection,
2) unique holdout candidate IDs across original splits,
3) cross-zone validation partner preference,
4) 10 km train-buffer exclusion around eval regions,
5) strict+fallback acceptance rules with transparent candidate logs.

Mask encoding:
- 1 = train region
- 2 = validation region
- 3 = holdout region
- 0 = outside NT OR buffer-excluded
"""

import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from scipy.ndimage import binary_dilation


def load_config():
    """Import ``00_config.py`` dynamically and return it as a module object."""
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load config from {config_path}")
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


def block_slices(height, width, side, step):
    """Yield moving square windows across the raster grid."""
    for row0 in range(0, max(1, height - side + 1), step):
        for col0 in range(0, max(1, width - side + 1), step):
            yield row0, col0, row0 + side, col0 + side


def make_block_mask(shape, window):
    """Convert a window tuple into a boolean mask."""
    row0, col0, row1, col1 = window
    block = np.zeros(shape, dtype=bool)
    block[row0:row1, col0:col1] = True
    return block


def summarize_region(name, region, valid, labels):
    """Count valid pixels and positives for one split region."""
    valid_region = region & valid
    return {
        f"{name}_pixels": int(valid_region.sum()),
        f"{name}_positives": int((labels[valid_region] == 1).sum()),
    }


def evaluate_candidate(area_share, positives, strict_area, strict_min_pos, cfg):
    """Return eligibility and rule type for holdout/validation role checks."""
    strict = (
        abs(area_share - strict_area) <= cfg.STRICT_AREA_TOLERANCE
        and positives >= strict_min_pos
    )
    fallback = (
        cfg.FALLBACK_AREA_MIN <= area_share <= cfg.FALLBACK_AREA_MAX
        and positives >= cfg.FALLBACK_MIN_POSITIVES
    )

    if strict:
        return True, "strict", ""
    if fallback:
        return True, "fallback", ""

    reason = (
        f"area_share={area_share:.4f}, positives={positives}, "
        f"strict_area={strict_area:.4f}, strict_min_pos={strict_min_pos}, "
        f"fallback_area=[{cfg.FALLBACK_AREA_MIN:.4f},{cfg.FALLBACK_AREA_MAX:.4f}], "
        f"fallback_min_pos={cfg.FALLBACK_MIN_POSITIVES}"
    )
    return False, "ineligible", reason


def zone_breakpoints_from_valid(valid, n_zones):
    """Build row-based zone boundaries from valid NT rows."""
    valid_rows, _ = np.where(valid)
    row_min = int(valid_rows.min())
    row_max = int(valid_rows.max())
    row_span = row_max - row_min

    breaks = [row_min + int(row_span * k / n_zones) for k in range(n_zones + 1)]
    breaks[-1] = row_max + 1
    return breaks


def assign_zone(centroid_row, breaks):
    """Assign a centroid row to a zone index based on breakpoints."""
    for zone in range(len(breaks) - 1):
        if centroid_row < breaks[zone + 1]:
            return zone
    return len(breaks) - 2


def zone_name(zone_index, n_zones):
    """Return human-readable names for common 3-zone splits."""
    if n_zones == 3:
        mapping = {0: "northern", 1: "central", 2: "southern"}
        return mapping.get(zone_index, f"zone_{zone_index}")
    return f"zone_{zone_index}"


def build_split_mask(valid, holdout_block, validation_block, use_buffer, buffer_structure):
    """Create encoded split mask and train-region mask."""
    eval_region = holdout_block | validation_block

    if use_buffer:
        excluded = binary_dilation(eval_region, structure=buffer_structure) & valid
    else:
        excluded = eval_region

    train_region = valid & ~excluded

    split_mask = np.zeros(valid.shape, dtype="uint8")
    split_mask[train_region] = 1
    split_mask[validation_block] = 2
    split_mask[holdout_block] = 3

    return split_mask, train_region


cfg = load_config()
cfg.ensure_directories()

if not cfg.NT_MASK_500M.exists() or not cfg.MVT_LABELS_500M.exists():
    raise FileNotFoundError("Missing NT mask or MVT labels. Run scripts 01 and 05 first.")

with rasterio.open(cfg.NT_MASK_500M) as src:
    nt_mask = src.read(1)
    profile = src.profile.copy()

with rasterio.open(cfg.MVT_LABELS_500M) as src:
    labels = src.read(1)

valid = nt_mask == 1
valid_pixels = int(valid.sum())
total_positives = int((labels[valid] == 1).sum())

if total_positives == 0:
    raise ValueError("No positive pixels found in label raster.")

height, width = valid.shape
target_block_pixels = max(1, int(valid_pixels * cfg.STRICT_HOLDOUT_AREA))
side = int(round(math.sqrt(target_block_pixels)))
side = max(8, min(side, height, width))
step = max(1, side // 3)

buffer_pixels = int(math.ceil(cfg.BUFFER_DISTANCE_M / cfg.PIXEL_SIZE))
buffer_window = 2 * buffer_pixels + 1
buffer_structure = np.ones((buffer_window, buffer_window), dtype=bool)

print("Valid pixels:", valid_pixels)
print("Positive pixels:", total_positives)
print("Candidate square side in pixels:", side)
print("Candidate step in pixels:", step)
print("Spatial buffer enabled:", cfg.USE_SPATIAL_BUFFER)
print("Buffer distance (m):", cfg.BUFFER_DISTANCE_M)
print("Buffer distance (pixels):", buffer_pixels)

zone_breaks = zone_breakpoints_from_valid(valid, cfg.SPLIT_N_GEOGRAPHIC_ZONES)
print("Zone breakpoints (row index):", zone_breaks)

candidates = []
for idx, window in enumerate(block_slices(height, width, side, step)):
    block = make_block_mask(valid.shape, window)
    block_valid = block & valid
    valid_count = int(block_valid.sum())
    if valid_count == 0:
        continue

    area_share = valid_count / valid_pixels
    positives = int((labels[block_valid] == 1).sum())

    row0, col0, row1, col1 = window
    centroid_row = (row0 + row1) / 2.0
    centroid_col = (col0 + col1) / 2.0
    zone = assign_zone(centroid_row, zone_breaks)

    holdout_ok, holdout_rule, holdout_reason = evaluate_candidate(
        area_share,
        positives,
        cfg.STRICT_HOLDOUT_AREA,
        cfg.STRICT_MIN_HOLDOUT_POSITIVES,
        cfg,
    )
    validation_ok, validation_rule, validation_reason = evaluate_candidate(
        area_share,
        positives,
        cfg.STRICT_VALIDATION_AREA,
        cfg.STRICT_MIN_VALIDATION_POSITIVES,
        cfg,
    )

    candidates.append(
        {
            "candidate_id": idx,
            "window": window,
            "row0": row0,
            "col0": col0,
            "row1": row1,
            "col1": col1,
            "centroid_row": centroid_row,
            "centroid_col": centroid_col,
            "zone": zone,
            "zone_name": zone_name(zone, cfg.SPLIT_N_GEOGRAPHIC_ZONES),
            "area_share": float(area_share),
            "positives": positives,
            "holdout_eligible": holdout_ok,
            "holdout_rule": holdout_rule,
            "holdout_reason": holdout_reason,
            "validation_eligible": validation_ok,
            "validation_rule": validation_rule,
            "validation_reason": validation_reason,
            "selected_as_holdout": False,
            "selected_as_validation": False,
            "final_status": "unused",
        }
    )

print("Candidate blocks:", len(candidates))

holdout_candidates = [c for c in candidates if c["holdout_eligible"]]
validation_candidates = [c for c in candidates if c["validation_eligible"]]

print("Holdout-eligible candidates:", len(holdout_candidates))
print("Validation-eligible candidates:", len(validation_candidates))

holdout_by_zone = {zone: [] for zone in range(cfg.SPLIT_N_GEOGRAPHIC_ZONES)}
for candidate in holdout_candidates:
    holdout_by_zone[candidate["zone"]].append(candidate)
for zone in holdout_by_zone:
    holdout_by_zone[zone] = sorted(holdout_by_zone[zone], key=lambda c: c["candidate_id"])

zone_cycle = [zone for zone in range(cfg.SPLIT_N_GEOGRAPHIC_ZONES) if holdout_by_zone[zone]]
zone_cursor = {zone: 0 for zone in range(cfg.SPLIT_N_GEOGRAPHIC_ZONES)}
used_as_holdout = set()
accepted_rows = []
split_id = 1

while len(accepted_rows) < cfg.TARGET_ACCEPTED_SPLITS and zone_cycle:
    made_progress = False

    for zone in zone_cycle:
        if len(accepted_rows) >= cfg.TARGET_ACCEPTED_SPLITS:
            break

        accepted_in_zone = False

        # Keep trying holdout candidates in this zone until one forms a valid pair.
        while (
            not accepted_in_zone
            and zone_cursor[zone] < len(holdout_by_zone[zone])
            and len(accepted_rows) < cfg.TARGET_ACCEPTED_SPLITS
        ):
            holdout = holdout_by_zone[zone][zone_cursor[zone]]
            zone_cursor[zone] += 1
            if holdout["candidate_id"] in used_as_holdout:
                continue

            holdout_block = make_block_mask(valid.shape, holdout["window"]) & valid

            if cfg.SPLIT_PREFER_CROSS_ZONE_VALIDATION:
                validation_pool = sorted(
                    [
                        c
                        for c in validation_candidates
                        if c["candidate_id"] != holdout["candidate_id"]
                    ],
                    key=lambda c: (int(c["zone"] == holdout["zone"]), c["candidate_id"]),
                )
            else:
                validation_pool = sorted(
                    [
                        c
                        for c in validation_candidates
                        if c["candidate_id"] != holdout["candidate_id"]
                    ],
                    key=lambda c: c["candidate_id"],
                )

            partner = None
            partner_split_mask = None

            for validation in validation_pool:
                validation_block = make_block_mask(valid.shape, validation["window"]) & valid
                if np.any(validation_block & holdout_block):
                    continue

                split_mask, train_region = build_split_mask(
                    valid,
                    holdout_block,
                    validation_block,
                    cfg.USE_SPATIAL_BUFFER,
                    buffer_structure,
                )
                train_positives = int((labels[train_region] == 1).sum())
                if train_positives < cfg.STRICT_MIN_TRAIN_POSITIVES:
                    continue

                partner = validation
                partner_split_mask = split_mask
                break

            if partner is None:
                holdout["final_status"] = "holdout_rejected_no_validation_partner"
                continue

            used_as_holdout.add(holdout["candidate_id"])
            holdout["selected_as_holdout"] = True
            holdout["final_status"] = "selected_as_holdout"
            partner["selected_as_validation"] = True
            if partner["final_status"] == "unused":
                partner["final_status"] = "selected_as_validation"

            split_name = f"{cfg.SPLIT_MASK_PREFIX}_{split_id:03d}_mask.tif"
            split_path = cfg.SPLITS_DIR / split_name
            split_relpath = cfg.to_relative_project_path(split_path)

            out_profile = profile.copy()
            out_profile.update(dtype="uint8", nodata=0, count=1, compress="lzw")
            with rasterio.open(split_path, "w", **out_profile) as dst:
                dst.write(partner_split_mask, 1)

            row = {
                "split_id": split_id,
                "split_type": "original",
                "paired_split_id": "",
                "split_mask": split_relpath,
                "holdout_candidate_id": holdout["candidate_id"],
                "validation_candidate_id": partner["candidate_id"],
                "holdout_zone": holdout["zone"],
                "validation_zone": partner["zone"],
                "holdout_zone_name": holdout["zone_name"],
                "validation_zone_name": partner["zone_name"],
                "holdout_rule": holdout["holdout_rule"],
                "validation_rule": partner["validation_rule"],
                "uses_buffer": bool(cfg.USE_SPATIAL_BUFFER),
                "buffer_distance_m": int(cfg.BUFFER_DISTANCE_M),
            }
            row.update(summarize_region("train", partner_split_mask == 1, valid, labels))
            row.update(summarize_region("validation", partner_split_mask == 2, valid, labels))
            row.update(summarize_region("holdout", partner_split_mask == 3, valid, labels))
            accepted_rows.append(row)

            print(
                "Accepted split",
                split_id,
                "holdout",
                holdout["candidate_id"],
                f"({holdout['zone_name']})",
                "validation",
                partner["candidate_id"],
                f"({partner['zone_name']})",
            )

            split_id += 1
            made_progress = True
            accepted_in_zone = True

    if not made_progress:
        print("No additional valid splits can be formed under current constraints.")
        break

for candidate in candidates:
    if candidate["final_status"] == "unused":
        if candidate["holdout_eligible"]:
            candidate["final_status"] = "holdout_eligible_not_selected"
        else:
            candidate["final_status"] = "holdout_ineligible"

summary_columns = [
    "split_id",
    "split_type",
    "paired_split_id",
    "split_mask",
    "holdout_candidate_id",
    "validation_candidate_id",
    "holdout_zone",
    "validation_zone",
    "holdout_zone_name",
    "validation_zone_name",
    "holdout_rule",
    "validation_rule",
    "uses_buffer",
    "buffer_distance_m",
    "train_pixels",
    "train_positives",
    "validation_pixels",
    "validation_positives",
    "holdout_pixels",
    "holdout_positives",
]
split_summary = pd.DataFrame(accepted_rows, columns=summary_columns)
split_summary.to_csv(cfg.SPLIT_SUMMARY, index=False)
print("Wrote:", cfg.SPLIT_SUMMARY)
print("Accepted splits:", len(split_summary))

candidate_columns = [
    "candidate_id",
    "row0",
    "col0",
    "row1",
    "col1",
    "centroid_row",
    "centroid_col",
    "zone",
    "zone_name",
    "area_share",
    "positives",
    "holdout_eligible",
    "holdout_rule",
    "holdout_reason",
    "validation_eligible",
    "validation_rule",
    "validation_reason",
    "selected_as_holdout",
    "selected_as_validation",
    "final_status",
]
candidate_table = pd.DataFrame(candidates)[candidate_columns]
candidate_table.to_csv(cfg.CANDIDATE_BLOCKS_SUMMARY, index=False)
print("Wrote:", cfg.CANDIDATE_BLOCKS_SUMMARY)

if not split_summary.empty:
    holdout_zone_count = int(split_summary["holdout_zone"].nunique())
    print("Holdout zone count:", holdout_zone_count)
    if holdout_zone_count < cfg.SPLIT_REQUIRE_MIN_ZONE_COUNT:
        print(
            "WARNING: holdout zones covered =",
            holdout_zone_count,
            "which is below required minimum",
            cfg.SPLIT_REQUIRE_MIN_ZONE_COUNT,
        )

if len(split_summary) < cfg.MIN_ACCEPTED_SPLITS_FOR_NON_EXPLORATORY:
    print(
        "WARNING: fewer than",
        cfg.MIN_ACCEPTED_SPLITS_FOR_NON_EXPLORATORY,
        "splits accepted. Treat v5 evaluation as exploratory.",
    )
