import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score


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


def top_k_metrics(scores, labels, pct):
    if len(scores) == 0:
        return {
            f"top{pct}_selected_pixels": 0,
            f"top{pct}_captured_positives": 0,
            f"top{pct}_recall": np.nan,
            f"top{pct}_precision": np.nan,
            f"top{pct}_enrichment": np.nan,
        }

    n = max(1, int(math.ceil(len(scores) * pct / 100.0)))
    order = np.argsort(scores)[::-1]
    selected = np.zeros(len(scores), dtype=bool)
    selected[order[:n]] = True

    positives = labels == 1
    total_pos = int(positives.sum())
    captured = int((selected & positives).sum())
    selected_count = int(selected.sum())

    recall = captured / total_pos if total_pos else np.nan
    precision = captured / selected_count if selected_count else np.nan
    enrichment = recall / (pct / 100.0) if total_pos else np.nan

    return {
        f"top{pct}_selected_pixels": selected_count,
        f"top{pct}_captured_positives": captured,
        f"top{pct}_recall": recall,
        f"top{pct}_precision": precision,
        f"top{pct}_enrichment": enrichment,
    }


def score_region(model, split_mask, region_value, valid_mask, usable_flat, feature_values, labels, feature_names):
    region = (split_mask[valid_mask] == region_value) & usable_flat
    y = labels[valid_mask][region].astype("uint8")
    if len(y) == 0:
        return np.array([], dtype="float32"), y

    X = pd.DataFrame(
        {name: values[region] for name, values in feature_values.items()},
        columns=feature_names,
    )
    prob = model.predict_proba(X)[:, 1]
    return prob, y


cfg = load_config()
feature_names = list(cfg.PREDICTOR_RASTERS.keys())

for path in [cfg.SPLIT_SUMMARY, cfg.SPLIT_TRAINING_SAMPLES, cfg.NT_MASK_500M, cfg.MVT_LABELS_500M]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required input: {path}")

split_summary = pd.read_csv(cfg.SPLIT_SUMMARY)
training_samples = pd.read_csv(cfg.SPLIT_TRAINING_SAMPLES)

with rasterio.open(cfg.NT_MASK_500M) as src:
    valid_mask = src.read(1) == 1

with rasterio.open(cfg.MVT_LABELS_500M) as src:
    labels = src.read(1)

feature_values = {}
usable_flat = np.ones(int(valid_mask.sum()), dtype=bool)
for name, path in cfg.PREDICTOR_RASTERS.items():
    if not path.exists():
        raise FileNotFoundError(f"Missing predictor raster: {path}")
    arr = read_predictor(cfg, name, path)
    values = arr[valid_mask]
    feature_values[name] = values
    usable_flat &= ~np.isnan(values)

records = []

for split in split_summary.itertuples():
    split_train = training_samples[training_samples["split_id"] == split.split_id]
    X_train = split_train[feature_names]
    y_train = split_train["label"].astype("uint8")

    if y_train.nunique() < 2:
        raise ValueError(f"Split {split.split_id} training data has only one class.")

    model = RandomForestClassifier(
        n_estimators=500,
        min_samples_leaf=2,
        class_weight="balanced",
        random_state=cfg.RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    with rasterio.open(split.split_mask) as src:
        split_mask = src.read(1)

    for region_name, region_value in [("validation", 2), ("holdout", 3)]:
        scores, y = score_region(
            model,
            split_mask,
            region_value,
            valid_mask,
            usable_flat,
            feature_values,
            labels,
            feature_names,
        )

        if len(y) == 0 or len(np.unique(y)) < 2:
            roc_auc = np.nan
            average_precision = np.nan
        else:
            roc_auc = roc_auc_score(y, scores)
            average_precision = average_precision_score(y, scores)

        row = {
            "split_id": int(split.split_id),
            "region": region_name,
            "pixels": int(len(y)),
            "positives": int(y.sum()),
            "roc_auc": roc_auc,
            "average_precision": average_precision,
        }
        for pct in cfg.TOP_K_PCTS:
            row.update(top_k_metrics(scores, y, pct))
        records.append(row)

metrics = pd.DataFrame(records)
metrics.to_csv(cfg.METRICS_BY_SPLIT, index=False)
print("Wrote:", cfg.METRICS_BY_SPLIT)

metric_cols = [col for col in metrics.columns if col not in {"split_id", "region"}]
aggregate_rows = []

for region, group in metrics.groupby("region"):
    for col in metric_cols:
        values = pd.to_numeric(group[col], errors="coerce")
        aggregate_rows.append(
            {
                "region": region,
                "metric": col,
                "split_count": int(values.notna().sum()),
                "mean": float(values.mean()),
                "median": float(values.median()),
                "std": float(values.std()),
                "worst_min": float(values.min()),
                "best_max": float(values.max()),
            }
        )

aggregate = pd.DataFrame(aggregate_rows)
aggregate.to_csv(cfg.AGGREGATE_METRICS, index=False)
print("Wrote:", cfg.AGGREGATE_METRICS)
