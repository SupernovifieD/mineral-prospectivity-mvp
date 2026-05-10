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

for path in [cfg.NT_MASK_500M, cfg.MVT_LABELS_500M]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required raster. Run previous scripts first: {path}")

missing_predictors = {
    name: path
    for name, path in cfg.PREDICTOR_RASTERS.items()
    if not path.exists()
}
if missing_predictors:
    detail = "\n".join(f"- {name}: {path}" for name, path in missing_predictors.items())
    raise FileNotFoundError(f"Missing predictor raster(s). Run scripts 02 and 03 first:\n{detail}")


def read_predictor(name, path):
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
        nodata = src.nodata

    if nodata is not None and name not in cfg.ZERO_IS_VALID_PREDICTORS:
        arr[arr == nodata] = np.nan
    arr[~np.isfinite(arr)] = np.nan
    return arr


with rasterio.open(cfg.NT_MASK_500M) as src:
    mask = src.read(1)
    transform = src.transform

with rasterio.open(cfg.MVT_LABELS_500M) as src:
    labels = src.read(1)

if labels.shape != mask.shape:
    raise ValueError("Label raster shape does not match NT mask shape.")

valid_mask = mask == 1
rows, cols = np.where(valid_mask)
flat_labels = labels[valid_mask].astype("uint8")
usable = np.ones(flat_labels.shape[0], dtype=bool)
feature_values = {}

for name, path in cfg.PREDICTOR_RASTERS.items():
    print("Reading:", name)
    arr = read_predictor(name, path)
    if arr.shape != mask.shape:
        raise ValueError(f"Predictor shape does not match NT mask: {name}")
    values = arr[valid_mask]
    feature_values[name] = values
    usable &= ~np.isnan(values)

positive_idx = np.where(usable & (flat_labels == 1))[0]
background_idx = np.where(usable & (flat_labels == 0))[0]

print("Inside-NT pixels:", int(valid_mask.sum()))
print("Usable positive pixels:", len(positive_idx))
print("Usable background pixels:", len(background_idx))

if len(positive_idx) == 0:
    raise ValueError("No usable positive labels found. Check labels and predictor NoData.")
if len(background_idx) == 0:
    raise ValueError("No usable background pixels found. Check mask and predictor NoData.")

n_background = min(len(background_idx), len(positive_idx) * cfg.BACKGROUND_PER_POSITIVE)
rng = np.random.default_rng(cfg.RANDOM_STATE)
background_sample = rng.choice(background_idx, size=n_background, replace=False)
selected = np.concatenate([positive_idx, background_sample])
rng.shuffle(selected)

xs, ys = rasterio.transform.xy(transform, rows[selected], cols[selected])

training = pd.DataFrame(
    {
        name: values[selected]
        for name, values in feature_values.items()
    }
)
training["label"] = flat_labels[selected]
training["x"] = xs
training["y"] = ys

training.to_csv(cfg.TRAINING_TABLE, index=False)

print("Wrote:", cfg.TRAINING_TABLE)
print("Training table rows:", len(training))
print("Training positives:", int(training["label"].sum()))
print("Training background:", int((training["label"] == 0).sum()))
