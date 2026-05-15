"""Build per-split training sample tables from train regions only.

For each accepted split:
1) keep train-region pixels only,
2) keep usable pixels (all feature values present),
3) include all train positives,
4) sample stratified background at the configured ratio.

Output is one combined CSV with metadata columns needed for traceability.
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


def read_predictor(cfg, name, path):
    """Read one predictor band and normalize NoData to NaN."""
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
        nodata = src.nodata

    if nodata is not None and name not in cfg.ZERO_IS_VALID_PREDICTORS:
        arr[arr == nodata] = np.nan
    arr[~np.isfinite(arr)] = np.nan
    return arr


def spatial_block_ids(rows, cols, block_size_pixels=100):
    """Assign each sample to a coarse spatial block ID."""
    block_rows = pd.Series((rows // block_size_pixels).astype(int)).astype(str)
    block_cols = pd.Series((cols // block_size_pixels).astype(int)).astype(str)
    return block_rows + "_" + block_cols


def stratified_background_sample(candidate_idx, rows, cols, n_needed, seed):
    """Sample background indices while spreading picks across spatial blocks."""
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
feature_names = cfg.FEATURE_COLUMNS

for path in [cfg.SPLIT_SUMMARY, cfg.NT_MASK_500M, cfg.MVT_LABELS_500M]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required input: {path}")

split_summary = pd.read_csv(cfg.SPLIT_SUMMARY)
if split_summary.empty:
    raise ValueError("No accepted spatial splits found.")

with rasterio.open(cfg.NT_MASK_500M) as src:
    mask = src.read(1)
    transform = src.transform

with rasterio.open(cfg.MVT_LABELS_500M) as src:
    labels = src.read(1)

# Flatten NT-valid pixels to a table-like index space.
valid_mask = mask == 1
rows, cols = np.where(valid_mask)
flat_labels = labels[valid_mask].astype("uint8")

feature_values = {}
usable = np.ones(flat_labels.shape[0], dtype=bool)
for name in feature_names:
    path = cfg.PREDICTOR_RASTERS[name]
    if not path.exists():
        raise FileNotFoundError(f"Missing predictor raster: {path}")
    print("Reading predictor:", name)
    arr = read_predictor(cfg, name, path)
    if arr.shape != mask.shape:
        raise ValueError(f"Predictor shape does not match NT mask: {name}")
    values = arr[valid_mask]
    feature_values[name] = values
    # A row is usable only if every active feature is present.
    usable &= ~np.isnan(values)

all_records = []

for split in split_summary.itertuples():
    with rasterio.open(split.split_mask) as src:
        split_mask = src.read(1)

    train_flat = split_mask[valid_mask] == 1
    # Positives are all included; background is sampled to control class ratio.
    positive_idx = np.where(train_flat & usable & (flat_labels == 1))[0]
    background_idx = np.where(train_flat & usable & (flat_labels == 0))[0]

    if len(positive_idx) == 0:
        raise ValueError(f"Split {split.split_id} has no usable positive training pixels.")
    if len(background_idx) == 0:
        raise ValueError(f"Split {split.split_id} has no usable background training pixels.")

    n_background = min(len(background_idx), len(positive_idx) * cfg.BACKGROUND_PER_POSITIVE)
    sampled_background = stratified_background_sample(
        background_idx,
        rows,
        cols,
        n_background,
        seed=cfg.RANDOM_STATE + int(split.split_id),
    )

    selected = np.concatenate([positive_idx, sampled_background])
    rng = np.random.default_rng(cfg.RANDOM_STATE + int(split.split_id))
    rng.shuffle(selected)

    xs, ys = rasterio.transform.xy(transform, rows[selected], cols[selected])
    table = pd.DataFrame({name: vals[selected] for name, vals in feature_values.items()})
    table["split_id"] = int(split.split_id)
    table[cfg.LABEL_COLUMN] = flat_labels[selected]
    table["x"] = xs
    table["y"] = ys
    table["row"] = rows[selected]
    table["col"] = cols[selected]
    table["sample_role"] = np.where(table[cfg.LABEL_COLUMN] == 1, "positive", "background")

    print(
        "Split",
        split.split_id,
        "training positives:",
        int(table[cfg.LABEL_COLUMN].sum()),
        "background:",
        int((table[cfg.LABEL_COLUMN] == 0).sum()),
    )
    all_records.append(table)

training_samples = pd.concat(all_records, ignore_index=True)
training_samples.to_csv(cfg.SPLIT_TRAINING_SAMPLES, index=False)
print("Wrote:", cfg.SPLIT_TRAINING_SAMPLES)
