import importlib.util
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import rasterio
from sklearn.ensemble import RandomForestClassifier


def load_config():
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load config from {config_path}")
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


def read_predictor(cfg, name, path):
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
        nodata = src.nodata
    if nodata is not None and name not in cfg.ZERO_IS_VALID_PREDICTORS:
        arr[arr == nodata] = np.nan
    arr[~np.isfinite(arr)] = np.nan
    return arr


def spatial_block_ids(rows, cols, block_size_pixels=100):
    block_rows = pd.Series((rows // block_size_pixels).astype(int)).astype(str)
    block_cols = pd.Series((cols // block_size_pixels).astype(int)).astype(str)
    return block_rows + "_" + block_cols


def stratified_background_sample(candidate_idx, rows, cols, n_needed, seed):
    if n_needed >= len(candidate_idx):
        return candidate_idx

    rng = np.random.default_rng(seed)
    block_ids = spatial_block_ids(rows[candidate_idx], cols[candidate_idx])
    groups = pd.Series(candidate_idx).groupby(block_ids)
    group_values = [group.to_numpy() for _, group in groups]

    selected = []
    group_order = np.arange(len(group_values))
    while len(selected) < n_needed and len(group_order) > 0:
        rng.shuffle(group_order)
        made_progress = False
        for group_i in group_order:
            group = group_values[group_i]
            if len(group) == 0:
                continue
            chosen_pos = rng.integers(0, len(group))
            selected.append(group[chosen_pos])
            group_values[group_i] = np.delete(group, chosen_pos)
            made_progress = True
            if len(selected) >= n_needed:
                break
        if not made_progress:
            break

    return np.array(selected, dtype=int)


cfg = load_config()
cfg.ensure_directories()
feature_names = list(cfg.PREDICTOR_RASTERS.keys())

for path in [cfg.NT_MASK_500M, cfg.MVT_LABELS_500M]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required raster: {path}")

with rasterio.open(cfg.NT_MASK_500M) as src:
    mask = src.read(1)
    transform = src.transform

with rasterio.open(cfg.MVT_LABELS_500M) as src:
    labels = src.read(1)

valid_mask = mask == 1
rows, cols = np.where(valid_mask)
flat_labels = labels[valid_mask].astype("uint8")
usable = np.ones(flat_labels.shape[0], dtype=bool)
feature_values = {}

for name, path in cfg.PREDICTOR_RASTERS.items():
    if not path.exists():
        raise FileNotFoundError(f"Missing predictor raster: {path}")
    print("Reading predictor:", name)
    arr = read_predictor(cfg, name, path)
    if arr.shape != mask.shape:
        raise ValueError(f"Predictor shape does not match NT mask: {name}")
    values = arr[valid_mask]
    feature_values[name] = values
    usable &= ~np.isnan(values)

positive_idx = np.where(usable & (flat_labels == 1))[0]
background_idx = np.where(usable & (flat_labels == 0))[0]

if len(positive_idx) == 0:
    raise ValueError("No usable positive pixels found.")
if len(background_idx) == 0:
    raise ValueError("No usable background pixels found.")

n_background = min(len(background_idx), len(positive_idx) * cfg.BACKGROUND_PER_POSITIVE)
sampled_background = stratified_background_sample(
    background_idx,
    rows,
    cols,
    n_background,
    seed=cfg.RANDOM_STATE,
)

selected = np.concatenate([positive_idx, sampled_background])
rng = np.random.default_rng(cfg.RANDOM_STATE)
rng.shuffle(selected)

xs, ys = rasterio.transform.xy(transform, rows[selected], cols[selected])
training = pd.DataFrame({name: vals[selected] for name, vals in feature_values.items()})
training["label"] = flat_labels[selected]
training["x"] = xs
training["y"] = ys
training["row"] = rows[selected]
training["col"] = cols[selected]

training.to_csv(cfg.FINAL_TRAINING_TABLE, index=False)
print("Wrote:", cfg.FINAL_TRAINING_TABLE)

model = RandomForestClassifier(
    n_estimators=500,
    min_samples_leaf=2,
    class_weight="balanced",
    random_state=cfg.RANDOM_STATE,
    n_jobs=-1,
)
model.fit(training[feature_names], training["label"].astype("uint8"))
joblib.dump(model, cfg.FINAL_RANDOM_FOREST_MODEL)
print("Wrote:", cfg.FINAL_RANDOM_FOREST_MODEL)

importance = pd.DataFrame(
    {
        "feature": feature_names,
        "importance": model.feature_importances_,
    }
).sort_values("importance", ascending=False)
importance.to_csv(cfg.FINAL_FEATURE_IMPORTANCE, index=False)
print("Wrote:", cfg.FINAL_FEATURE_IMPORTANCE)

print("IMPORTANT: this final model is for screening-map production.")
print("It is not the source of holdout performance evidence.")
print("Use metrics_by_split.csv and aggregate_metrics.csv for evaluation.")
