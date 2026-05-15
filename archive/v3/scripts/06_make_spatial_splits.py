"""Build repeated spatial train/validation/holdout split masks.

This script searches candidate square blocks over the NT grid and assembles
non-overlapping validation/holdout pairs that satisfy v3 split constraints.

Mask encoding:
- 1 = train region
- 2 = validation region
- 3 = holdout region
- 0 = outside NT
"""

import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


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


def area_matches_strict(area_share, target):
    """Return True when candidate area is within strict tolerance."""
    return abs(area_share - target) <= 0.03


cfg = load_config()
cfg.ensure_directories()

if not cfg.NT_MASK_500M.exists() or not cfg.MVT_LABELS_500M.exists():
    raise FileNotFoundError("Missing NT mask or MVT labels. Run scripts 01 and 05 first.")

with rasterio.open(cfg.NT_MASK_500M) as src:
    nt_mask = src.read(1)
    profile = src.profile.copy()

with rasterio.open(cfg.MVT_LABELS_500M) as src:
    labels = src.read(1)

# Work only on valid NT pixels.
valid = nt_mask == 1
valid_pixels = int(valid.sum())
total_positives = int((labels[valid] == 1).sum())

if total_positives == 0:
    raise ValueError("No positive pixels found in label raster.")

height, width = valid.shape
target_block_pixels = max(1, int(valid_pixels * cfg.STRICT_HOLDOUT_AREA))
# Approximate a square whose area is close to target holdout share.
side = int(round(math.sqrt(target_block_pixels)))
side = max(8, min(side, height, width))
step = max(1, side // 3)

print("Valid pixels:", valid_pixels)
print("Positive pixels:", total_positives)
print("Candidate square side in pixels:", side)
print("Candidate step in pixels:", step)

candidate_blocks = []
# Scan many candidate windows and retain those intersecting the valid ROI.
for idx, window in enumerate(block_slices(height, width, side, step)):
    block = make_block_mask(valid.shape, window)
    block_valid = block & valid
    valid_count = int(block_valid.sum())
    if valid_count == 0:
        continue

    area_share = valid_count / valid_pixels
    positives = int((labels[block_valid] == 1).sum())
    candidate_blocks.append(
        {
            "candidate_id": idx,
            "window": window,
            "area_share": float(area_share),
            "positives": positives,
        }
    )

print("Candidate blocks:", len(candidate_blocks))

accepted = []
split_id = 1

# Pair one holdout block with one non-overlapping validation block.
for holdout in candidate_blocks:
    holdout_block = make_block_mask(valid.shape, holdout["window"]) & valid
    strict_holdout_ok = (
        area_matches_strict(holdout["area_share"], cfg.STRICT_HOLDOUT_AREA)
        and holdout["positives"] >= cfg.STRICT_MIN_HOLDOUT_POSITIVES
    )
    fallback_holdout_ok = (
        cfg.FALLBACK_AREA_MIN <= holdout["area_share"] <= cfg.FALLBACK_AREA_MAX
        and holdout["positives"] >= cfg.FALLBACK_MIN_POSITIVES
    )
    # Candidate must satisfy either strict rules or fallback rules.
    if not (strict_holdout_ok or fallback_holdout_ok):
        continue

    for validation in candidate_blocks:
        if validation["candidate_id"] == holdout["candidate_id"]:
            continue

        validation_block = make_block_mask(valid.shape, validation["window"]) & valid
        # Enforce spatial disjointness between validation and holdout areas.
        if np.any(validation_block & holdout_block):
            continue

        strict_validation_ok = (
            area_matches_strict(validation["area_share"], cfg.STRICT_VALIDATION_AREA)
            and validation["positives"] >= cfg.STRICT_MIN_VALIDATION_POSITIVES
        )
        fallback_validation_ok = (
            cfg.FALLBACK_AREA_MIN <= validation["area_share"] <= cfg.FALLBACK_AREA_MAX
            and validation["positives"] >= cfg.FALLBACK_MIN_POSITIVES
        )
        if not (strict_validation_ok or fallback_validation_ok):
            continue

        train_region = valid & ~validation_block & ~holdout_block
        train_positives = int((labels[train_region] == 1).sum())
        if train_positives < cfg.STRICT_MIN_TRAIN_POSITIVES:
            continue

        # Encode region roles in one compact mask raster.
        split_mask = np.zeros(valid.shape, dtype="uint8")
        split_mask[train_region] = 1
        split_mask[validation_block] = 2
        split_mask[holdout_block] = 3

        split_name = f"{cfg.SPLIT_MASK_PREFIX}_{split_id:03d}_mask.tif"
        split_path = cfg.SPLITS_DIR / split_name

        out_profile = profile.copy()
        out_profile.update(dtype="uint8", nodata=0, count=1, compress="lzw")
        with rasterio.open(split_path, "w", **out_profile) as dst:
            dst.write(split_mask, 1)

        rule_type = "strict" if strict_holdout_ok and strict_validation_ok else "fallback"
        row = {
            "split_id": split_id,
            "split_mask": str(split_path),
            "holdout_candidate_id": holdout["candidate_id"],
            "validation_candidate_id": validation["candidate_id"],
            "rule_type": rule_type,
            "uses_buffer": False,
            "buffer_distance_m": 0,
        }
        row.update(summarize_region("train", split_mask == 1, valid, labels))
        row.update(summarize_region("validation", split_mask == 2, valid, labels))
        row.update(summarize_region("holdout", split_mask == 3, valid, labels))
        accepted.append(row)

        print("Accepted split:", split_id, "rule:", rule_type)
        split_id += 1

        if len(accepted) >= cfg.TARGET_ACCEPTED_SPLITS:
            break

    if len(accepted) >= cfg.TARGET_ACCEPTED_SPLITS:
        break

summary = pd.DataFrame(accepted)
summary.to_csv(cfg.SPLIT_SUMMARY, index=False)
print("Wrote:", cfg.SPLIT_SUMMARY)
print("Accepted splits:", len(summary))

if len(summary) < cfg.MIN_ACCEPTED_SPLITS_FOR_NON_EXPLORATORY:
    print(
        "WARNING: fewer than",
        cfg.MIN_ACCEPTED_SPLITS_FOR_NON_EXPLORATORY,
        "splits accepted. Treat v3 evaluation as exploratory.",
    )
