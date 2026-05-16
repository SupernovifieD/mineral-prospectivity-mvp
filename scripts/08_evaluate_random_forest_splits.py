"""Evaluate v4 Random Forest pipeline across accepted spatial splits.

For each split, this script trains on split-specific training samples, then
scores validation and holdout regions on full rasters. It writes:
1) metrics_by_split.csv,
2) aggregate_metrics.csv (original splits only),
3) metrics_by_holdout_candidate.csv,
4) validation_holdout_gap_diagnostic.csv.
"""

import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


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


def top_k_metrics(scores, labels, pct):
    """Compute recall/precision/enrichment for top-k% ranked pixels."""
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


def score_region(model, split_mask, region_value, valid_mask, usable_flat, feature_values, flat_labels, feature_names):
    """Score one split region (validation or holdout) using raster features."""
    region = (split_mask[valid_mask] == region_value) & usable_flat
    y = flat_labels[region].astype("uint8")
    if len(y) == 0:
        return np.array([], dtype="float32"), y

    X = pd.DataFrame(
        {name: values[region] for name, values in feature_values.items()},
        columns=feature_names,
    )
    prob = model.predict_proba(X)[:, 1]
    return prob, y


cfg = load_config()
feature_names = cfg.FEATURE_COLUMNS

for path in [cfg.SPLIT_SUMMARY, cfg.SPLIT_TRAINING_SAMPLES, cfg.NT_MASK_500M, cfg.MVT_LABELS_500M]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required input: {path}")

split_summary = pd.read_csv(cfg.SPLIT_SUMMARY)
if split_summary.empty:
    raise ValueError("No accepted spatial splits found. Run script 06 first.")

training_samples = pd.read_csv(cfg.SPLIT_TRAINING_SAMPLES)
if training_samples.empty:
    raise ValueError("Split training sample table is empty. Run script 07 first.")

with rasterio.open(cfg.NT_MASK_500M) as src:
    valid_mask = src.read(1) == 1

with rasterio.open(cfg.MVT_LABELS_500M) as src:
    labels = src.read(1)

flat_labels = labels[valid_mask].astype("uint8")

feature_values = {}
usable_flat = np.ones(int(valid_mask.sum()), dtype=bool)
for name in feature_names:
    path = cfg.PREDICTOR_RASTERS[name]
    if not path.exists():
        raise FileNotFoundError(f"Missing predictor raster: {path}")
    arr = read_predictor(cfg, name, path)
    values = arr[valid_mask]
    feature_values[name] = values
    usable_flat &= ~np.isnan(values)

records = []

for split in split_summary.itertuples(index=False):
    split_train = training_samples[training_samples["split_id"] == split.split_id]
    X_train = split_train[feature_names]
    y_train = split_train[cfg.LABEL_COLUMN].astype("uint8")

    if y_train.nunique() < 2:
        raise ValueError(f"Split {split.split_id} training data has only one class.")

    model = Pipeline(
        steps=[
            (
                "scaler",
                StandardScaler(
                    with_mean=cfg.SCALING_WITH_MEAN,
                    with_std=cfg.SCALING_WITH_STD,
                ),
            ),
            (
                "rf",
                RandomForestClassifier(
                    n_estimators=cfg.MODEL_N_ESTIMATORS,
                    min_samples_leaf=cfg.MODEL_MIN_SAMPLES_LEAF,
                    class_weight=cfg.MODEL_CLASS_WEIGHT,
                    random_state=cfg.RANDOM_STATE,
                    n_jobs=cfg.MODEL_N_JOBS,
                ),
            ),
        ]
    )
    model.fit(X_train, y_train)

    split_mask_path = cfg.resolve_project_path(split.split_mask)
    with rasterio.open(split_mask_path) as src:
        split_mask = src.read(1)

    for region_name, region_value in [("validation", 2), ("holdout", 3)]:
        scores, y = score_region(
            model,
            split_mask,
            region_value,
            valid_mask,
            usable_flat,
            feature_values,
            flat_labels,
            feature_names,
        )

        if len(y) == 0 or len(np.unique(y)) < 2:
            roc_auc = np.nan
            average_precision = np.nan
        else:
            roc_auc = roc_auc_score(y, scores)
            average_precision = average_precision_score(y, scores)

        positives = int(y.sum())
        pixels = int(len(y))
        baseline_prevalence = (positives / pixels) if pixels > 0 else np.nan
        ap_skill = (
            average_precision / baseline_prevalence
            if pd.notna(average_precision)
            and pd.notna(baseline_prevalence)
            and baseline_prevalence > 0
            else np.nan
        )

        row = {
            "split_id": int(split.split_id),
            "split_type": str(getattr(split, "split_type", "original")),
            "holdout_candidate_id": int(split.holdout_candidate_id),
            "validation_candidate_id": int(split.validation_candidate_id),
            "holdout_zone": int(split.holdout_zone),
            "validation_zone": int(split.validation_zone),
            "holdout_zone_name": str(getattr(split, "holdout_zone_name", split.holdout_zone)),
            "validation_zone_name": str(
                getattr(split, "validation_zone_name", split.validation_zone)
            ),
            "region": region_name,
            "region_zone_name": str(
                getattr(split, "validation_zone_name", split.validation_zone)
                if region_name == "validation"
                else getattr(split, "holdout_zone_name", split.holdout_zone)
            ),
            "pixels": pixels,
            "positives": positives,
            "baseline_prevalence": baseline_prevalence,
            "roc_auc": roc_auc,
            "average_precision": average_precision,
            "ap_skill_vs_baseline": ap_skill,
        }

        for pct in cfg.TOP_K_PCTS:
            row.update(top_k_metrics(scores, y, pct))

        records.append(row)

metrics = pd.DataFrame(records)
metrics.to_csv(cfg.METRICS_BY_SPLIT, index=False)
print("Wrote:", cfg.METRICS_BY_SPLIT)

original_metrics = metrics[metrics["split_type"] == "original"].copy()
if original_metrics.empty:
    raise ValueError("No original splits found in metrics table.")

metadata_cols = {
    "split_id",
    "split_type",
    "region",
    "holdout_candidate_id",
    "validation_candidate_id",
    "holdout_zone",
    "validation_zone",
    "holdout_zone_name",
    "validation_zone_name",
    "region_zone_name",
}
metric_cols = [col for col in original_metrics.columns if col not in metadata_cols]
aggregate_rows = []

for region, group in original_metrics.groupby("region"):
    for col in metric_cols:
        values = pd.to_numeric(group[col], errors="coerce")
        aggregate_rows.append(
            {
                "split_type": "original",
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

holdout_rows = original_metrics[original_metrics["region"] == "holdout"].copy()
per_holdout_records = []
for (candidate_id, zone, zone_name), group in holdout_rows.groupby(
    ["holdout_candidate_id", "holdout_zone", "holdout_zone_name"]
):
    entry = {
        "holdout_candidate_id": int(candidate_id),
        "holdout_zone": int(zone),
        "holdout_zone_name": str(zone_name),
        "split_count": int(len(group)),
        "mean_pixels": float(group["pixels"].mean()),
        "mean_positives": float(group["positives"].mean()),
        "mean_baseline_prevalence": float(group["baseline_prevalence"].mean()),
        "mean_average_precision": float(group["average_precision"].mean()),
        "median_average_precision": float(group["average_precision"].median()),
        "min_average_precision": float(group["average_precision"].min()),
        "max_average_precision": float(group["average_precision"].max()),
        "mean_roc_auc": float(group["roc_auc"].mean()),
        "median_roc_auc": float(group["roc_auc"].median()),
        "mean_ap_skill_vs_baseline": float(group["ap_skill_vs_baseline"].mean()),
    }

    for pct in cfg.TOP_K_PCTS:
        entry[f"mean_top{pct}_recall"] = float(group[f"top{pct}_recall"].mean())
        entry[f"mean_top{pct}_enrichment"] = float(group[f"top{pct}_enrichment"].mean())

    per_holdout_records.append(entry)

per_holdout = pd.DataFrame(per_holdout_records)
if not per_holdout.empty:
    per_holdout = per_holdout.sort_values("holdout_candidate_id")
per_holdout.to_csv(cfg.METRICS_BY_HOLDOUT_CANDIDATE, index=False)
print("Wrote:", cfg.METRICS_BY_HOLDOUT_CANDIDATE)

val_rows = original_metrics[original_metrics["region"] == "validation"].copy()
hold_rows = original_metrics[original_metrics["region"] == "holdout"].copy()

gap = val_rows.merge(
    hold_rows,
    on=[
        "split_id",
        "split_type",
        "holdout_candidate_id",
        "validation_candidate_id",
        "holdout_zone",
        "validation_zone",
        "holdout_zone_name",
        "validation_zone_name",
    ],
    suffixes=("_validation", "_holdout"),
)

if gap.empty:
    raise ValueError("Could not build validation-holdout gap table from split metrics.")

gap["ap_gap_difference"] = (
    gap["average_precision_validation"] - gap["average_precision_holdout"]
)
gap["ap_gap_ratio"] = np.where(
    gap["average_precision_holdout"] > 0,
    gap["average_precision_validation"] / gap["average_precision_holdout"],
    np.nan,
)
gap["skill_gap_difference"] = (
    gap["ap_skill_vs_baseline_validation"] - gap["ap_skill_vs_baseline_holdout"]
)
gap["skill_gap_ratio"] = np.where(
    gap["ap_skill_vs_baseline_holdout"] > 0,
    gap["ap_skill_vs_baseline_validation"] / gap["ap_skill_vs_baseline_holdout"],
    np.nan,
)

gap_columns = [
    "split_id",
    "split_type",
    "holdout_candidate_id",
    "holdout_zone",
    "holdout_zone_name",
    "validation_candidate_id",
    "validation_zone",
    "validation_zone_name",
    "pixels_validation",
    "positives_validation",
    "baseline_prevalence_validation",
    "average_precision_validation",
    "ap_skill_vs_baseline_validation",
    "pixels_holdout",
    "positives_holdout",
    "baseline_prevalence_holdout",
    "average_precision_holdout",
    "ap_skill_vs_baseline_holdout",
    "ap_gap_difference",
    "ap_gap_ratio",
    "skill_gap_difference",
    "skill_gap_ratio",
]

gap_out = gap[gap_columns].copy()
gap_out.to_csv(cfg.VALIDATION_HOLDOUT_GAP_DIAGNOSTIC, index=False)
print("Wrote:", cfg.VALIDATION_HOLDOUT_GAP_DIAGNOSTIC)
