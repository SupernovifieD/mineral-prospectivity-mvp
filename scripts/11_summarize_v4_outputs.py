"""Summarize v4 outputs into maps and review tables.

This script produces:
1) score distribution summary CSV,
2) binary top-k area rasters,
3) v4 model review text report with split/gap diagnostics.
"""

import importlib.util
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


def safe_read_csv(path):
    """Read a CSV if it exists, else return an empty DataFrame."""
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


cfg = load_config()
cfg.ensure_directories()

required_paths = [
    cfg.FINAL_PROSPECTIVITY_MAP,
    cfg.AGGREGATE_METRICS,
    cfg.SPLIT_SUMMARY,
    cfg.METRICS_BY_HOLDOUT_CANDIDATE,
    cfg.VALIDATION_HOLDOUT_GAP_DIAGNOSTIC,
]
for path in required_paths:
    if not path.exists():
        raise FileNotFoundError(f"Missing required input. Run prior scripts first: {path}")

with rasterio.open(cfg.FINAL_PROSPECTIVITY_MAP) as src:
    scores = src.read(1)
    profile = src.profile.copy()
    nodata = src.nodata

valid = np.isfinite(scores)
if nodata is not None:
    valid &= scores != nodata

valid_scores = scores[valid]
if valid_scores.size == 0:
    raise ValueError("Final prospectivity map contains no valid scores.")

summary = {
    "run_name": cfg.RUN_NAME,
    "valid_pixels": int(valid_scores.size),
    "min": float(np.min(valid_scores)),
    "max": float(np.max(valid_scores)),
    "mean": float(np.mean(valid_scores)),
    "p50": float(np.percentile(valid_scores, 50)),
    "p90": float(np.percentile(valid_scores, 90)),
    "p95": float(np.percentile(valid_scores, 95)),
    "p99": float(np.percentile(valid_scores, 99)),
}
pd.DataFrame([summary]).to_csv(cfg.FINAL_SCORE_SUMMARY, index=False)
print("Wrote:", cfg.FINAL_SCORE_SUMMARY)

profile.update(dtype="uint8", nodata=0, count=1, compress="lzw")
for pct in cfg.TOP_K_PCTS:
    threshold = float(np.percentile(valid_scores, 100 - pct))
    top = np.zeros(scores.shape, dtype="uint8")
    top[valid & (scores >= threshold)] = 1

    top_path = cfg.MAPS_DIR / f"mvt_top_{pct}_percent_rf_v4_500m.tif"
    with rasterio.open(top_path, "w", **profile) as dst:
        dst.write(top, 1)

    print(f"Top {pct}% threshold:", threshold)
    print("Wrote:", top_path)

aggregate_metrics = safe_read_csv(cfg.AGGREGATE_METRICS)
split_summary = safe_read_csv(cfg.SPLIT_SUMMARY)
metrics_by_holdout = safe_read_csv(cfg.METRICS_BY_HOLDOUT_CANDIDATE)
gap_diag = safe_read_csv(cfg.VALIDATION_HOLDOUT_GAP_DIAGNOSTIC)

original_splits = split_summary
if "split_type" in split_summary.columns:
    original_splits = split_summary[split_summary["split_type"] == "original"].copy()

accepted_count = int(len(original_splits))
holdout_zones = []
if "holdout_zone_name" in original_splits.columns and not original_splits.empty:
    holdout_zones = sorted(original_splits["holdout_zone_name"].astype(str).unique().tolist())
elif "holdout_zone" in original_splits.columns and not original_splits.empty:
    holdout_zones = sorted(original_splits["holdout_zone"].astype(str).unique().tolist())

zone_count = len(holdout_zones)

ap_val_mean = np.nan
ap_hold_mean = np.nan
if not aggregate_metrics.empty:
    val_row = aggregate_metrics[
        (aggregate_metrics["region"] == "validation")
        & (aggregate_metrics["metric"] == "average_precision")
    ]
    hold_row = aggregate_metrics[
        (aggregate_metrics["region"] == "holdout")
        & (aggregate_metrics["metric"] == "average_precision")
    ]
    if not val_row.empty:
        ap_val_mean = float(val_row.iloc[0]["mean"])
    if not hold_row.empty:
        ap_hold_mean = float(hold_row.iloc[0]["mean"])

gap_ratio_mean = np.nan
gap_ratio_median = np.nan
skill_ratio_mean = np.nan
if not gap_diag.empty:
    gap_ratio_mean = float(pd.to_numeric(gap_diag["ap_gap_ratio"], errors="coerce").mean())
    gap_ratio_median = float(pd.to_numeric(gap_diag["ap_gap_ratio"], errors="coerce").median())
    skill_ratio_mean = float(pd.to_numeric(gap_diag["skill_gap_ratio"], errors="coerce").mean())

with open(cfg.MODEL_REVIEW_REPORT, "w", encoding="utf-8") as handle:
    handle.write(f"Run: {cfg.RUN_NAME}\n")
    handle.write("Objective: exploratory learning run + screening benchmark\n")
    handle.write("Model family: Random Forest only\n")
    handle.write(f"Pixel size: {cfg.PIXEL_SIZE} m\n")
    handle.write(f"CRS: {cfg.PROJECT_CRS}\n")
    handle.write(f"Spatial buffer: enabled ({cfg.BUFFER_DISTANCE_M} m)\n")
    handle.write(
        f"Background sampling: {cfg.BACKGROUND_PER_POSITIVE}:1 "
        f"(spatially stratified={cfg.USE_SPATIALLY_STRATIFIED_BACKGROUND})\n"
    )
    handle.write("\n")

    handle.write("Split coverage:\n")
    handle.write(f"- Accepted original splits: {accepted_count}\n")
    handle.write(f"- Holdout zones covered ({zone_count}): {', '.join(holdout_zones) if holdout_zones else 'none'}\n")
    handle.write(
        f"- Non-exploratory minimum split target: {cfg.MIN_ACCEPTED_SPLITS_FOR_NON_EXPLORATORY}\n"
    )
    if accepted_count < cfg.MIN_ACCEPTED_SPLITS_FOR_NON_EXPLORATORY:
        handle.write(
            "- Status: exploratory only (accepted split count below non-exploratory threshold)\n"
        )
    else:
        handle.write("- Status: non-exploratory split count threshold met\n")
    handle.write("\n")

    handle.write("Holdout performance by candidate:\n")
    if metrics_by_holdout.empty:
        handle.write("- No holdout-candidate metrics found.\n")
    else:
        for row in metrics_by_holdout.sort_values("holdout_candidate_id").itertuples(index=False):
            handle.write(
                "- candidate "
                f"{int(row.holdout_candidate_id)} "
                f"({row.holdout_zone_name}): "
                f"splits={int(row.split_count)}, "
                f"mean_AP={row.mean_average_precision:.6f}, "
                f"mean_skill={row.mean_ap_skill_vs_baseline:.2f}x\n"
            )
    handle.write("\n")

    handle.write("Validation-vs-holdout gap summary:\n")
    handle.write(f"- Mean validation AP: {ap_val_mean:.6f}\n")
    handle.write(f"- Mean holdout AP: {ap_hold_mean:.6f}\n")
    handle.write(f"- Mean AP gap ratio (validation/holdout): {gap_ratio_mean:.2f}x\n")
    handle.write(f"- Median AP gap ratio (validation/holdout): {gap_ratio_median:.2f}x\n")
    handle.write(f"- Mean skill gap ratio (validation/holdout): {skill_ratio_mean:.2f}x\n")
    handle.write("\n")

    handle.write("Claim limits (mandatory):\n")
    handle.write("- Scores are relative prospectivity rankings, not calibrated deposit probabilities.\n")
    handle.write("- Holdout evidence comes from split evaluation, not from the final production model.\n")
    handle.write("\n")

    handle.write("Key outputs used in this review:\n")
    handle.write(f"- {cfg.to_relative_project_path(cfg.SPLIT_SUMMARY)}\n")
    handle.write(f"- {cfg.to_relative_project_path(cfg.METRICS_BY_SPLIT)}\n")
    handle.write(f"- {cfg.to_relative_project_path(cfg.AGGREGATE_METRICS)}\n")
    handle.write(f"- {cfg.to_relative_project_path(cfg.METRICS_BY_HOLDOUT_CANDIDATE)}\n")
    handle.write(f"- {cfg.to_relative_project_path(cfg.VALIDATION_HOLDOUT_GAP_DIAGNOSTIC)}\n")
    handle.write(f"- {cfg.to_relative_project_path(cfg.FINAL_PROSPECTIVITY_MAP)}\n")

print("Wrote:", cfg.MODEL_REVIEW_REPORT)
