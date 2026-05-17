"""Run v5 feature-ablation evaluation across accepted spatial splits.

This script keeps v4 controls fixed and changes only feature subsets.
Outputs:
1) feature_ablation_metrics_by_split.csv
2) feature_ablation_aggregate_metrics.csv
3) feature_ablation_by_holdout_candidate.csv
4) feature_ablation_delta_vs_baseline.csv
5) feature_ablation_validation_holdout_gap.csv
6) feature_ablation_ranked_summary.csv
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


TOP_PCTS = [1, 5, 10]


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
    """Score one split region using raster feature values."""
    region = (split_mask[valid_mask] == region_value) & usable_flat
    y = flat_labels[region].astype("uint8")
    if len(y) == 0:
        return np.array([], dtype="float32"), y

    X = pd.DataFrame(
        {name: feature_values[name][region] for name in feature_names},
        columns=feature_names,
    )
    prob = model.predict_proba(X)[:, 1]
    return prob, y


def join_features(values):
    """Convert a feature name list to a stable, CSV-friendly string."""
    return "|".join(values)


def interpretation_flag(delta_mean, baseline_mean):
    """Assign a directional delta label for baseline comparison."""
    if pd.isna(delta_mean) or pd.isna(baseline_mean):
        return "unstable_or_nan"

    tolerance = max(abs(baseline_mean) * 0.01, 1e-12)
    if abs(delta_mean) <= tolerance:
        return "approximately_equal"
    if delta_mean > 0:
        return "improved_vs_baseline"
    return "worse_than_baseline"


def metric_mean(agg_df, experiment_id, region, metric):
    """Fetch one aggregate mean value from grouped metrics table."""
    row = agg_df[
        (agg_df["experiment_id"] == experiment_id)
        & (agg_df["region"] == region)
        & (agg_df["metric"] == metric)
    ]
    if row.empty:
        return np.nan
    return float(row.iloc[0]["mean"])


cfg = load_config()
cfg.ensure_directories()

if not cfg.ABLATION_ENABLED:
    raise ValueError("Ablation is disabled in config; v5 script 08 requires ablation.enabled=true.")

required_paths = [cfg.SPLIT_SUMMARY, cfg.SPLIT_TRAINING_SAMPLES, cfg.NT_MASK_500M, cfg.MVT_LABELS_500M]
for path in required_paths:
    if not path.exists():
        raise FileNotFoundError(f"Missing required input: {path}")

split_summary = pd.read_csv(cfg.SPLIT_SUMMARY)
if split_summary.empty:
    raise ValueError("No accepted splits found. Run script 06 first.")
if "split_type" in split_summary.columns:
    split_summary = split_summary[split_summary["split_type"] == "original"].copy()
if split_summary.empty:
    raise ValueError("No original splits found in split_summary.")

training_samples = pd.read_csv(cfg.SPLIT_TRAINING_SAMPLES)
if training_samples.empty:
    raise ValueError("Split training samples are empty. Run script 07 first.")

with rasterio.open(cfg.NT_MASK_500M) as src:
    valid_mask = src.read(1) == 1

with rasterio.open(cfg.MVT_LABELS_500M) as src:
    labels = src.read(1)

flat_labels = labels[valid_mask].astype("uint8")

feature_values = {}
usable_flat = np.ones(int(valid_mask.sum()), dtype=bool)
for name in cfg.FEATURE_COLUMNS:
    path = cfg.PREDICTOR_RASTERS[name]
    if not path.exists():
        raise FileNotFoundError(f"Missing predictor raster: {path}")
    arr = read_predictor(cfg, name, path)
    values = arr[valid_mask]
    feature_values[name] = values
    usable_flat &= ~np.isnan(values)

split_masks = {}
for row in split_summary.itertuples(index=False):
    split_mask_path = cfg.resolve_project_path(row.split_mask)
    with rasterio.open(split_mask_path) as src:
        split_masks[int(row.split_id)] = src.read(1)

records = []

for experiment in cfg.ABLATION_EXPERIMENTS:
    exp_id = experiment["id"]
    exp_label = experiment["label"]
    exp_mode = experiment["mode"]
    exp_features = experiment["features"]
    exp_included = join_features(experiment["included_features"])
    exp_dropped = join_features(experiment["dropped_features"])

    print(f"Running experiment: {exp_id} ({len(exp_features)} features)")

    for split in split_summary.itertuples(index=False):
        split_id = int(split.split_id)
        split_train = training_samples[training_samples["split_id"] == split_id]
        X_train = split_train[exp_features]
        y_train = split_train[cfg.LABEL_COLUMN].astype("uint8")

        if y_train.nunique() < 2:
            raise ValueError(f"Split {split_id} training data has only one class.")

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

        split_mask = split_masks[split_id]

        for region_name, region_value in [("validation", 2), ("holdout", 3)]:
            scores, y = score_region(
                model,
                split_mask,
                region_value,
                valid_mask,
                usable_flat,
                feature_values,
                flat_labels,
                exp_features,
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
                "experiment_id": exp_id,
                "experiment_label": exp_label,
                "feature_mode": exp_mode,
                "feature_count": int(len(exp_features)),
                "included_features": exp_included,
                "dropped_features": exp_dropped,
                "split_id": split_id,
                "split_type": str(getattr(split, "split_type", "original")),
                "holdout_candidate_id": int(split.holdout_candidate_id),
                "validation_candidate_id": int(split.validation_candidate_id),
                "holdout_zone": int(split.holdout_zone),
                "validation_zone": int(split.validation_zone),
                "holdout_zone_name": str(getattr(split, "holdout_zone_name", split.holdout_zone)),
                "validation_zone_name": str(getattr(split, "validation_zone_name", split.validation_zone)),
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

            for pct in TOP_PCTS:
                row.update(top_k_metrics(scores, y, pct))

            records.append(row)

metrics = pd.DataFrame(records)
metrics.to_csv(cfg.FEATURE_ABLATION_METRICS_BY_SPLIT, index=False)
print("Wrote:", cfg.FEATURE_ABLATION_METRICS_BY_SPLIT)

original_metrics = metrics[metrics["split_type"] == "original"].copy()
if original_metrics.empty:
    raise ValueError("No original-split rows in feature_ablation_metrics_by_split.csv")

metadata_cols = {
    "experiment_id",
    "experiment_label",
    "feature_mode",
    "feature_count",
    "included_features",
    "dropped_features",
    "split_id",
    "split_type",
    "holdout_candidate_id",
    "validation_candidate_id",
    "holdout_zone",
    "validation_zone",
    "holdout_zone_name",
    "validation_zone_name",
    "region",
    "region_zone_name",
}
metric_cols = [col for col in original_metrics.columns if col not in metadata_cols]

aggregate_rows = []
for (exp_id, exp_label, region), group in original_metrics.groupby(
    ["experiment_id", "experiment_label", "region"]
):
    for metric in metric_cols:
        values = pd.to_numeric(group[metric], errors="coerce")
        aggregate_rows.append(
            {
                "experiment_id": exp_id,
                "experiment_label": exp_label,
                "region": region,
                "metric": metric,
                "split_count": int(values.notna().sum()),
                "mean": float(values.mean()),
                "median": float(values.median()),
                "std": float(values.std()),
                "worst_min": float(values.min()),
                "best_max": float(values.max()),
            }
        )

aggregate = pd.DataFrame(aggregate_rows)
aggregate.to_csv(cfg.FEATURE_ABLATION_AGGREGATE_METRICS, index=False)
print("Wrote:", cfg.FEATURE_ABLATION_AGGREGATE_METRICS)

holdout_rows = original_metrics[original_metrics["region"] == "holdout"].copy()
per_holdout_rows = []
for (exp_id, cand_id, zone, zone_name), group in holdout_rows.groupby(
    ["experiment_id", "holdout_candidate_id", "holdout_zone", "holdout_zone_name"]
):
    exp_label = str(group.iloc[0]["experiment_label"])
    row = {
        "experiment_id": exp_id,
        "experiment_label": exp_label,
        "holdout_candidate_id": int(cand_id),
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
        "mean_top1_recall": float(group["top1_recall"].mean()),
        "mean_top5_recall": float(group["top5_recall"].mean()),
        "mean_top10_recall": float(group["top10_recall"].mean()),
        "mean_top1_enrichment": float(group["top1_enrichment"].mean()),
        "mean_top5_enrichment": float(group["top5_enrichment"].mean()),
        "mean_top10_enrichment": float(group["top10_enrichment"].mean()),
    }
    per_holdout_rows.append(row)

per_holdout = pd.DataFrame(per_holdout_rows)
if not per_holdout.empty:
    per_holdout = per_holdout.sort_values(["experiment_id", "holdout_candidate_id"])
per_holdout.to_csv(cfg.FEATURE_ABLATION_BY_HOLDOUT_CANDIDATE, index=False)
print("Wrote:", cfg.FEATURE_ABLATION_BY_HOLDOUT_CANDIDATE)

val_rows = original_metrics[original_metrics["region"] == "validation"].copy()
hold_rows = original_metrics[original_metrics["region"] == "holdout"].copy()

gap = val_rows.merge(
    hold_rows,
    on=[
        "experiment_id",
        "experiment_label",
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
    raise ValueError("Could not build feature_ablation_validation_holdout_gap table.")

gap["ap_gap_difference"] = gap["average_precision_validation"] - gap["average_precision_holdout"]
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

gap_out = gap[
    [
        "experiment_id",
        "experiment_label",
        "split_id",
        "average_precision_validation",
        "average_precision_holdout",
        "ap_gap_difference",
        "ap_gap_ratio",
        "ap_skill_vs_baseline_validation",
        "ap_skill_vs_baseline_holdout",
        "skill_gap_difference",
        "skill_gap_ratio",
    ]
].copy()
gap_out.to_csv(cfg.FEATURE_ABLATION_VALIDATION_HOLDOUT_GAP, index=False)
print("Wrote:", cfg.FEATURE_ABLATION_VALIDATION_HOLDOUT_GAP)

baseline_id = cfg.ABLATION_BASELINE_EXPERIMENT
delta_rows = []

for exp in cfg.ABLATION_EXPERIMENTS:
    exp_id = exp["id"]
    if exp_id == baseline_id:
        continue

    for region in sorted(aggregate["region"].dropna().unique().tolist()):
        region_metrics = aggregate[aggregate["region"] == region]
        for metric in sorted(region_metrics["metric"].dropna().unique().tolist()):
            baseline_mean = metric_mean(aggregate, baseline_id, region, metric)
            experiment_mean = metric_mean(aggregate, exp_id, region, metric)
            delta_mean = experiment_mean - baseline_mean if pd.notna(experiment_mean) and pd.notna(baseline_mean) else np.nan
            if pd.notna(baseline_mean) and baseline_mean != 0 and pd.notna(delta_mean):
                pct_delta = (delta_mean / baseline_mean) * 100.0
            else:
                pct_delta = np.nan

            delta_rows.append(
                {
                    "experiment_id": exp_id,
                    "experiment_label": exp["label"],
                    "region": region,
                    "metric": metric,
                    "baseline_mean": baseline_mean,
                    "experiment_mean": experiment_mean,
                    "delta_mean": delta_mean,
                    "pct_delta_mean": pct_delta,
                    "interpretation_flag": interpretation_flag(delta_mean, baseline_mean),
                }
            )

delta = pd.DataFrame(delta_rows)
delta.to_csv(cfg.FEATURE_ABLATION_DELTA_VS_BASELINE, index=False)
print("Wrote:", cfg.FEATURE_ABLATION_DELTA_VS_BASELINE)

rank_region = cfg.ABLATION_AGGREGATE_REFERENCE_REGION
baseline_holdout_ap = metric_mean(aggregate, baseline_id, rank_region, "average_precision")
baseline_holdout_top5 = metric_mean(aggregate, baseline_id, rank_region, "top5_recall")

ranking_rows = []
for exp in cfg.ABLATION_EXPERIMENTS:
    exp_id = exp["id"]

    holdout_ap = metric_mean(aggregate, exp_id, rank_region, "average_precision")
    holdout_ap_skill = metric_mean(aggregate, exp_id, rank_region, "ap_skill_vs_baseline")
    holdout_top1 = metric_mean(aggregate, exp_id, rank_region, "top1_recall")
    holdout_top5 = metric_mean(aggregate, exp_id, rank_region, "top5_recall")
    holdout_top10 = metric_mean(aggregate, exp_id, rank_region, "top10_recall")

    notes = []
    if exp_id == baseline_id:
        notes.append("baseline_reference")
    if pd.isna(holdout_ap):
        notes.append("missing_holdout_ap")
    if pd.isna(holdout_top5):
        notes.append("missing_holdout_top5")

    ranking_rows.append(
        {
            "rank_by_holdout_average_precision": np.nan,
            "experiment_id": exp_id,
            "experiment_label": exp["label"],
            "feature_count": int(exp["feature_count"]),
            "mean_holdout_average_precision": holdout_ap,
            "mean_holdout_ap_skill_vs_baseline": holdout_ap_skill,
            "mean_holdout_top1_recall": holdout_top1,
            "mean_holdout_top5_recall": holdout_top5,
            "mean_holdout_top10_recall": holdout_top10,
            "delta_holdout_ap_vs_full_baseline": holdout_ap - baseline_holdout_ap
            if pd.notna(holdout_ap) and pd.notna(baseline_holdout_ap)
            else np.nan,
            "delta_holdout_top5_recall_vs_full_baseline": holdout_top5 - baseline_holdout_top5
            if pd.notna(holdout_top5) and pd.notna(baseline_holdout_top5)
            else np.nan,
            "notes": ";".join(notes),
        }
    )

ranking = pd.DataFrame(ranking_rows)
ranking = ranking.sort_values("mean_holdout_average_precision", ascending=False, na_position="last")
ranking["rank_by_holdout_average_precision"] = np.arange(1, len(ranking) + 1)
ranking.to_csv(cfg.FEATURE_ABLATION_RANKED_SUMMARY, index=False)
print("Wrote:", cfg.FEATURE_ABLATION_RANKED_SUMMARY)
