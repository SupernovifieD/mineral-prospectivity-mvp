import importlib.util
from pathlib import Path

import joblib
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

if not cfg.RANDOM_FOREST_MODEL.exists():
    raise FileNotFoundError(f"Missing trained model. Run script 07 first: {cfg.RANDOM_FOREST_MODEL}")
if not cfg.NT_MASK_500M.exists():
    raise FileNotFoundError(f"Missing NT mask. Run script 01 first: {cfg.NT_MASK_500M}")

feature_names = list(cfg.PREDICTOR_RASTERS.keys())
missing_predictors = {
    name: path
    for name, path in cfg.PREDICTOR_RASTERS.items()
    if not path.exists()
}
if missing_predictors:
    detail = "\n".join(f"- {name}: {path}" for name, path in missing_predictors.items())
    raise FileNotFoundError(f"Missing predictor raster(s):\n{detail}")


def read_predictor(name, path):
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
        nodata = src.nodata

    if nodata is not None and name not in cfg.ZERO_IS_VALID_PREDICTORS:
        arr[arr == nodata] = np.nan
    arr[~np.isfinite(arr)] = np.nan
    return arr


model = joblib.load(cfg.RANDOM_FOREST_MODEL)
if hasattr(model, "feature_names_in_"):
    trained_features = list(model.feature_names_in_)
    if trained_features != feature_names:
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

for name in feature_names:
    print("Reading:", name)
    arr = read_predictor(name, cfg.PREDICTOR_RASTERS[name])
    if arr.shape != mask.shape:
        raise ValueError(f"Predictor shape does not match NT mask: {name}")
    feature_columns.append(arr[valid_mask])

X = np.column_stack(feature_columns)
usable = ~np.isnan(X).any(axis=1)
usable_indices = np.where(usable)[0]

if len(usable_indices) == 0:
    raise ValueError("No usable pixels remain after removing predictor NoData.")

scores = np.full(X.shape[0], cfg.NODATA_FLOAT, dtype="float32")
chunk_size = 200_000

for start in range(0, len(usable_indices), chunk_size):
    end = start + chunk_size
    idx = usable_indices[start:end]
    chunk = pd.DataFrame(X[idx], columns=feature_names)
    scores[idx] = model.predict_proba(chunk)[:, 1].astype("float32")
    print("Predicted pixels:", min(end, len(usable_indices)), "of", len(usable_indices))

score_map = np.full(mask.shape, cfg.NODATA_FLOAT, dtype="float32")
score_map[valid_rows, valid_cols] = scores

profile.update(dtype="float32", nodata=cfg.NODATA_FLOAT, count=1, compress="lzw")

with rasterio.open(cfg.PROSPECTIVITY_MAP, "w", **profile) as dst:
    dst.write(score_map, 1)

print("Wrote:", cfg.PROSPECTIVITY_MAP)
