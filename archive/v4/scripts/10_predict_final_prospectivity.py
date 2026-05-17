"""Predict final NT prospectivity map from the trained v4 pipeline.

Workflow:
1) load final scaler+RF model,
2) assemble feature matrix from aligned predictor rasters,
3) score usable pixels in chunks,
4) write float32 prospectivity raster.
"""

import importlib.util
from pathlib import Path

import joblib
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


def read_predictor(cfg, name, path):
    """Read one predictor band and normalize NoData to NaN."""
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
        nodata = src.nodata
    if nodata is not None and name not in cfg.ZERO_IS_VALID_PREDICTORS:
        arr[arr == nodata] = np.nan
    arr[~np.isfinite(arr)] = np.nan
    return arr


cfg = load_config()
cfg.ensure_directories()

if not cfg.FINAL_RANDOM_FOREST_MODEL.exists():
    raise FileNotFoundError(f"Missing final model. Run script 09 first: {cfg.FINAL_RANDOM_FOREST_MODEL}")
if not cfg.NT_MASK_500M.exists():
    raise FileNotFoundError(f"Missing NT mask. Run script 01 first: {cfg.NT_MASK_500M}")

feature_names = cfg.FEATURE_COLUMNS
model = joblib.load(cfg.FINAL_RANDOM_FOREST_MODEL)

# Defensive check: ensure config feature order matches model training order.
trained_features = None
if hasattr(model, "feature_names_in_"):
    trained_features = list(model.feature_names_in_)
elif hasattr(model, "named_steps") and "rf" in model.named_steps:
    rf_model = model.named_steps["rf"]
    if hasattr(rf_model, "feature_names_in_"):
        trained_features = list(rf_model.feature_names_in_)

if trained_features is not None and trained_features != feature_names:
    raise ValueError(
        "Model feature order does not match current config. "
        f"Model: {trained_features}; config: {feature_names}"
    )

with rasterio.open(cfg.NT_MASK_500M) as src:
    mask = src.read(1)
    profile = src.profile.copy()

valid_mask = mask == 1
valid_rows, valid_cols = np.where(valid_mask)
feature_columns = []

# Build model matrix in config-defined column order.
for name in feature_names:
    path = cfg.PREDICTOR_RASTERS[name]
    if not path.exists():
        raise FileNotFoundError(f"Missing predictor raster: {path}")
    print("Reading:", name)
    arr = read_predictor(cfg, name, path)
    if arr.shape != mask.shape:
        raise ValueError(f"Predictor shape does not match NT mask: {name}")
    feature_columns.append(arr[valid_mask])

X = np.column_stack(feature_columns)
usable = ~np.isnan(X).any(axis=1)
usable_indices = np.where(usable)[0]

if len(usable_indices) == 0:
    raise ValueError("No usable pixels remain after removing predictor NoData.")

scores = np.full(X.shape[0], cfg.NODATA_FLOAT, dtype="float32")
# Chunking keeps memory stable on large rasters.
chunk_size = cfg.PREDICTION_CHUNK_SIZE

for start in range(0, len(usable_indices), chunk_size):
    end = start + chunk_size
    idx = usable_indices[start:end]
    chunk = pd.DataFrame(X[idx], columns=feature_names)
    scores[idx] = model.predict_proba(chunk)[:, 1].astype("float32")
    print("Predicted pixels:", min(end, len(usable_indices)), "of", len(usable_indices))

score_map = np.full(mask.shape, cfg.NODATA_FLOAT, dtype="float32")
score_map[valid_rows, valid_cols] = scores

profile.update(dtype="float32", nodata=cfg.NODATA_FLOAT, count=1, compress="lzw")
with rasterio.open(cfg.FINAL_PROSPECTIVITY_MAP, "w", **profile) as dst:
    dst.write(score_map, 1)

print("Wrote:", cfg.FINAL_PROSPECTIVITY_MAP)
print("Map values are relative prospectivity scores, not calibrated deposit probabilities.")
