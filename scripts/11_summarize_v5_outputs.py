"""Summarize v5 ablation outputs into review artifacts.

This script produces:
1) v5_model_review.txt
2) feature_ablation_ranked_summary.csv (if missing)
3) final_score_summary_v5.csv (optional, if final map exists)
4) optional top-k map summaries (if final map exists)
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


def safe_read_csv(path):
    """Read CSV if present, else return empty DataFrame."""
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def metric_mean(agg_df, experiment_id, region, metric):
    """Fetch aggregate mean value from metric table."""
    row = agg_df[
        (agg_df["experiment_id"] == experiment_id)
        & (agg_df["region"] == region)
        & (agg_df["metric"] == metric)
    ]
    if row.empty:
        return np.nan
    return float(row.iloc[0]["mean"])


def ensure_ranked_summary(cfg, aggregate_df):
    """Create ranking table if missing."""
    if cfg.FEATURE_ABLATION_RANKED_SUMMARY.exists():
        return pd.read_csv(cfg.FEATURE_ABLATION_RANKED_SUMMARY)

    rank_region = cfg.ABLATION_AGGREGATE_REFERENCE_REGION
    baseline_id = cfg.ABLATION_BASELINE_EXPERIMENT
    baseline_ap = metric_mean(aggregate_df, baseline_id, rank_region, "average_precision")
    baseline_top5 = metric_mean(aggregate_df, baseline_id, rank_region, "top5_recall")

    rows = []
    for exp in cfg.ABLATION_EXPERIMENTS:
        exp_id = exp["id"]
        holdout_ap = metric_mean(aggregate_df, exp_id, rank_region, "average_precision")
        holdout_ap_skill = metric_mean(aggregate_df, exp_id, rank_region, "ap_skill_vs_baseline")
        holdout_top1 = metric_mean(aggregate_df, exp_id, rank_region, "top1_recall")
        holdout_top5 = metric_mean(aggregate_df, exp_id, rank_region, "top5_recall")
        holdout_top10 = metric_mean(aggregate_df, exp_id, rank_region, "top10_recall")

        notes = []
        if exp_id == baseline_id:
            notes.append("baseline_reference")
        if pd.isna(holdout_ap):
            notes.append("missing_holdout_ap")

        rows.append(
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
                "delta_holdout_ap_vs_full_baseline": holdout_ap - baseline_ap
                if pd.notna(holdout_ap) and pd.notna(baseline_ap)
                else np.nan,
                "delta_holdout_top5_recall_vs_full_baseline": holdout_top5 - baseline_top5
                if pd.notna(holdout_top5) and pd.notna(baseline_top5)
                else np.nan,
                "notes": ";".join(notes),
            }
        )

    ranking = pd.DataFrame(rows)
    ranking = ranking.sort_values("mean_holdout_average_precision", ascending=False, na_position="last")
    ranking["rank_by_holdout_average_precision"] = np.arange(1, len(ranking) + 1)
    ranking.to_csv(cfg.FEATURE_ABLATION_RANKED_SUMMARY, index=False)
    print("Wrote:", cfg.FEATURE_ABLATION_RANKED_SUMMARY)
    return ranking


cfg = load_config()
cfg.ensure_directories()

EXPERIMENT_QUESTIONS = {
    "full_baseline": "Reference experiment using full V4 feature set.",
    "no_lab_depth": "Does LAB depth improve or hurt holdout performance?",
    "no_deep_lithosphere": "Do deep-earth proxies (Moho + LAB) help or add noise?",
    "geology_only": "How far geology + faults can go without geophysics.",
    "geophysics_only": "Whether geophysics has independent predictive signal.",
    "no_magnetics": "Do magnetic predictors improve holdout discrimination?",
    "no_gravity": "Do gravity-related predictors improve holdout discrimination?",
    "no_lithology_onehot": "Does detailed one-hot lithology add value beyond carbonate host?",
    "carbonate_fault_only": "Simple mineral-system baseline using host + fault distance.",
}

required = [
    cfg.FEATURE_ABLATION_METRICS_BY_SPLIT,
    cfg.FEATURE_ABLATION_AGGREGATE_METRICS,
    cfg.FEATURE_ABLATION_BY_HOLDOUT_CANDIDATE,
    cfg.FEATURE_ABLATION_DELTA_VS_BASELINE,
    cfg.FEATURE_ABLATION_VALIDATION_HOLDOUT_GAP,
]
for path in required:
    if not path.exists():
        raise FileNotFoundError(f"Missing required ablation artifact: {path}")

metrics_by_split = safe_read_csv(cfg.FEATURE_ABLATION_METRICS_BY_SPLIT)
aggregate = safe_read_csv(cfg.FEATURE_ABLATION_AGGREGATE_METRICS)
by_holdout = safe_read_csv(cfg.FEATURE_ABLATION_BY_HOLDOUT_CANDIDATE)
delta = safe_read_csv(cfg.FEATURE_ABLATION_DELTA_VS_BASELINE)
gap = safe_read_csv(cfg.FEATURE_ABLATION_VALIDATION_HOLDOUT_GAP)

ranking = ensure_ranked_summary(cfg, aggregate)

if cfg.FINAL_PROSPECTIVITY_MAP.exists():
    with rasterio.open(cfg.FINAL_PROSPECTIVITY_MAP) as src:
        scores = src.read(1)
        nodata = src.nodata

    valid = np.isfinite(scores)
    if nodata is not None:
        valid &= scores != nodata

    valid_scores = scores[valid]
    if valid_scores.size > 0:
        summary = {
            "run_name": cfg.RUN_NAME,
            "valid_pixels": int(valid_scores.size),
            "min": float(np.min(valid_scores)),
            "max": float(np.max(valid_scores)),
            "mean": float(np.mean(valid_scores)),
            "p50": float(np.percentile(valid_scores, 50)),
            "p90": float(np.percentile(valid_scores, 90)),
            "p95": float(np.percentile(valid_scores, 95)),
            "p99": float(np.percentile(valid_scores, 99)),
        }
        pd.DataFrame([summary]).to_csv(cfg.FINAL_SCORE_SUMMARY, index=False)
        print("Wrote:", cfg.FINAL_SCORE_SUMMARY)

baseline_id = cfg.ABLATION_BASELINE_EXPERIMENT
rank_region = cfg.ABLATION_AGGREGATE_REFERENCE_REGION
exp_count = len(cfg.ABLATION_EXPERIMENTS)

mean_gap_ratio = np.nan
median_gap_ratio = np.nan
if not gap.empty and "ap_gap_ratio" in gap.columns:
    mean_gap_ratio = float(pd.to_numeric(gap["ap_gap_ratio"], errors="coerce").mean())
    median_gap_ratio = float(pd.to_numeric(gap["ap_gap_ratio"], errors="coerce").median())

best_row = ranking.iloc[0] if not ranking.empty else None
worst_row = ranking.iloc[-1] if not ranking.empty else None

with open(cfg.MODEL_REVIEW_REPORT, "w", encoding="utf-8") as handle:
    handle.write(f"Run: {cfg.RUN_NAME}\n")
    handle.write("Objective: feature ablation study\n")
    handle.write("Model family: Random Forest only\n")
    handle.write(f"Pixel size: {cfg.PIXEL_SIZE} m\n")
    handle.write(f"CRS: {cfg.PROJECT_CRS}\n")
    handle.write(f"Spatial buffer: enabled ({cfg.BUFFER_DISTANCE_M} m)\n")
    handle.write(
        f"Background sampling: {cfg.BACKGROUND_PER_POSITIVE}:1 "
        f"(spatially stratified={cfg.USE_SPATIALLY_STRATIFIED_BACKGROUND})\n"
    )
    handle.write(f"Ablation experiments: {exp_count}\n")
    handle.write("\n")

    handle.write("Fixed V4 conditions kept in V5:\n")
    handle.write("- Same study area (Northern Territory), 500 m grid, EPSG:3577\n")
    handle.write("- Same MVT label logic and predictor raster inventory\n")
    handle.write("- Same split generator and 10 km buffer\n")
    handle.write("- Same 50:1 spatially stratified background sampling\n")
    handle.write("- Same StandardScaler + RandomForest hyperparameter recipe\n")
    handle.write("\n")

    handle.write("Ablation experiment table:\n")
    for exp in cfg.ABLATION_EXPERIMENTS:
        question = EXPERIMENT_QUESTIONS.get(exp["id"], "Experiment-specific feature-subset test.")
        handle.write(
            f"- {exp['id']}: mode={exp['mode']}, feature_count={exp['feature_count']}, "
            f"drop={','.join(exp['dropped_features']) if exp['dropped_features'] else 'none'}, "
            f"question={question}\n"
        )
    handle.write("\n")

    handle.write(
        f"Main ranking ({rank_region} region, metric={cfg.ABLATION_RANKING_METRIC}):\n"
    )
    if ranking.empty:
        handle.write("- No ranking rows found.\n")
    else:
        for row in ranking.itertuples(index=False):
            handle.write(
                f"- rank {int(row.rank_by_holdout_average_precision)}: {row.experiment_id} "
                f"(AP={row.mean_holdout_average_precision:.6f}, "
                f"AP-skill={row.mean_holdout_ap_skill_vs_baseline:.2f}, "
                f"top5={row.mean_holdout_top5_recall:.3f}, top10={row.mean_holdout_top10_recall:.3f})\n"
            )
    handle.write("\n")

    if best_row is not None and worst_row is not None:
        handle.write("Best and worst experiment snapshot:\n")
        handle.write(
            f"- Best: {best_row.experiment_id} "
            f"(delta AP vs baseline={best_row.delta_holdout_ap_vs_full_baseline:.6f})\n"
        )
        handle.write(
            f"- Worst: {worst_row.experiment_id} "
            f"(delta AP vs baseline={worst_row.delta_holdout_ap_vs_full_baseline:.6f})\n"
        )
        handle.write("\n")

    handle.write("Validation-vs-holdout gap summary:\n")
    handle.write(f"- Mean AP gap ratio (validation/holdout): {mean_gap_ratio:.3f}x\n")
    handle.write(f"- Median AP gap ratio (validation/holdout): {median_gap_ratio:.3f}x\n")
    handle.write("\n")

    handle.write("Delta-vs-baseline interpretation guidance:\n")
    handle.write("- Small improvements may be non-meaningful when split variance is high.\n")
    handle.write("- Do not remove a feature group based on one metric alone.\n")
    handle.write(
        "- Prefer subsets that improve holdout AP and top-k recall without worsening validation-holdout gap.\n"
    )
    handle.write(
        "- Validation-up but holdout-down should be treated as potential geography-specific overfitting.\n"
    )
    handle.write("\n")

    handle.write("Mandatory claim limits:\n")
    for line in cfg.MANDATORY_CLAIMS_LANGUAGE:
        handle.write(f"- {line}\n")
    handle.write("\n")

    handle.write("Key artifacts:\n")
    handle.write(f"- {cfg.to_relative_project_path(cfg.FEATURE_ABLATION_METRICS_BY_SPLIT)}\n")
    handle.write(f"- {cfg.to_relative_project_path(cfg.FEATURE_ABLATION_AGGREGATE_METRICS)}\n")
    handle.write(f"- {cfg.to_relative_project_path(cfg.FEATURE_ABLATION_BY_HOLDOUT_CANDIDATE)}\n")
    handle.write(f"- {cfg.to_relative_project_path(cfg.FEATURE_ABLATION_DELTA_VS_BASELINE)}\n")
    handle.write(f"- {cfg.to_relative_project_path(cfg.FEATURE_ABLATION_VALIDATION_HOLDOUT_GAP)}\n")
    handle.write(f"- {cfg.to_relative_project_path(cfg.FEATURE_ABLATION_RANKED_SUMMARY)}\n")

print("Wrote:", cfg.MODEL_REVIEW_REPORT)
