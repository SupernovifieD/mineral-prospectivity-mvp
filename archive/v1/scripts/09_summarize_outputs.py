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

if not cfg.PROSPECTIVITY_MAP.exists():
    raise FileNotFoundError(f"Missing prospectivity map. Run script 08 first: {cfg.PROSPECTIVITY_MAP}")

with rasterio.open(cfg.PROSPECTIVITY_MAP) as src:
    scores = src.read(1)
    profile = src.profile.copy()
    nodata = src.nodata

valid = np.isfinite(scores)
if nodata is not None:
    valid &= scores != nodata

valid_scores = scores[valid]
if valid_scores.size == 0:
    raise ValueError("Prospectivity map contains no valid scores.")

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

summary_path = cfg.TABLES_DIR / "prospectivity_score_summary.csv"
pd.DataFrame([summary]).to_csv(summary_path, index=False)
print("Wrote:", summary_path)

threshold = summary["p95"]
top5 = np.zeros(scores.shape, dtype="uint8")
top5[valid & (scores >= threshold)] = 1

profile.update(dtype="uint8", nodata=0, count=1, compress="lzw")
with rasterio.open(cfg.TOP_5_PERCENT_MAP, "w", **profile) as dst:
    dst.write(top5, 1)

print("Top 5 percent threshold:", threshold)
print("Top 5 percent pixels:", int(top5.sum()))
print("Wrote:", cfg.TOP_5_PERCENT_MAP)

report_path = cfg.TABLES_DIR / "model_review_template.txt"
with open(report_path, "w", encoding="utf-8") as f:
    f.write("Model run name: random_forest_mvt_500m\n")
    f.write("Pixel size: 500 m\n")
    f.write("CRS: EPSG:3577\n")
    f.write("Prospectivity map: outputs/maps/mvt_prospectivity_random_forest_500m.tif\n")
    f.write("Top 5 percent map: outputs/maps/mvt_top_5_percent_500m.tif\n")
    f.write(f"Top 5 percent threshold: {threshold:.4f}\n")
    f.write("\nQuestions to answer in QGIS:\n")
    f.write("- Do known MVT points fall in high-score areas?\n")
    f.write("- Are high-score areas geologically plausible?\n")
    f.write("- Are high scores caused by data edges or NoData boundaries?\n")
    f.write("- Which feature importances make geological sense?\n")
    f.write("- What should be changed in the next model run?\n")

print("Wrote:", report_path)
