import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


def load_config():
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load config from {config_path}")
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


cfg = load_config()
cfg.ensure_directories()

if not cfg.FINAL_PROSPECTIVITY_MAP.exists():
    raise FileNotFoundError(f"Missing final prospectivity map. Run script 10 first: {cfg.FINAL_PROSPECTIVITY_MAP}")
if not cfg.AGGREGATE_METRICS.exists():
    raise FileNotFoundError(f"Missing aggregate metrics. Run script 08 first: {cfg.AGGREGATE_METRICS}")

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
    "valid_pixels": int(valid_scores.size),
    "min": float(np.min(valid_scores)),
    "max": float(np.max(valid_scores)),
    "mean": float(np.mean(valid_scores)),
    "p50": float(np.percentile(valid_scores, 50)),
    "p90": float(np.percentile(valid_scores, 90)),
    "p95": float(np.percentile(valid_scores, 95)),
    "p99": float(np.percentile(valid_scores, 99)),
}

summary_path = cfg.TABLES_DIR / "final_score_summary_v2.csv"
pd.DataFrame([summary]).to_csv(summary_path, index=False)
print("Wrote:", summary_path)

profile.update(dtype="uint8", nodata=0, count=1, compress="lzw")

for pct in cfg.TOP_K_PCTS:
    threshold = float(np.percentile(valid_scores, 100 - pct))
    top = np.zeros(scores.shape, dtype="uint8")
    top[valid & (scores >= threshold)] = 1

    top_path = cfg.MAPS_DIR / f"mvt_top_{pct}_percent_rf_v2_500m.tif"
    with rasterio.open(top_path, "w", **profile) as dst:
        dst.write(top, 1)

    print(f"Top {pct}% threshold:", threshold)
    print("Wrote:", top_path)

aggregate_metrics = pd.read_csv(cfg.AGGREGATE_METRICS)
split_summary = pd.read_csv(cfg.SPLIT_SUMMARY) if cfg.SPLIT_SUMMARY.exists() else pd.DataFrame()

report_path = cfg.TABLES_DIR / "v2_model_review.txt"
with open(report_path, "w", encoding="utf-8") as f:
    f.write("Run: NT MVT v2 Random Forest baseline\n")
    f.write("Primary goal: scientific benchmark\n")
    f.write("Secondary output: screening prospectivity map\n")
    f.write("Pixel size: 500 m\n")
    f.write("CRS: EPSG:3577\n")
    f.write("Model: fixed Random Forest\n")
    f.write("Predictors: v1 predictor set\n")
    f.write("Coordinates used as predictors: no\n")
    f.write("Probability calibration: no\n")
    f.write("Spatial buffer: no\n")
    f.write("Background sampling: spatially stratified\n")
    f.write(f"Accepted split count: {len(split_summary)}\n")
    f.write("\nImportant limitations:\n")
    f.write("- Final map scores are relative prospectivity rankings, not deposit probabilities.\n")
    f.write("- No uncertainty map was produced in v2.\n")
    f.write("- Holdout evidence comes from repeated split evaluation, not the final map itself.\n")
    f.write("\nAggregate metrics:\n")
    f.write(aggregate_metrics.to_string(index=False))
    f.write("\n")

print("Wrote:", report_path)
