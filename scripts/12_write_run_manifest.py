"""Write a reproducibility manifest for the v4 run.

Manifest includes:
1) run timestamp and git commit hash,
2) active config path and full config content snapshot,
3) checksums for key inputs/outputs,
4) project-relative paths for portability.
"""

import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import yaml


def load_config():
    """Import ``00_config.py`` dynamically and return it as a module object."""
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load config from {config_path}")
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


def utc_now_iso():
    """Return current UTC time in ISO-8601 format."""
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_commit_hash(project_root):
    """Return current git commit hash or UNKNOWN if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except Exception:
        return "UNKNOWN"


def sha256_file(path):
    """Compute SHA-256 checksum for a file path."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_record(cfg, label, path):
    """Build one manifest row for a path."""
    path_obj = Path(path)
    resolved = cfg.resolve_project_path(path_obj)
    relpath = cfg.to_relative_project_path(resolved)

    if not resolved.exists():
        return {
            "label": label,
            "relative_path": relpath,
            "exists": False,
            "size_bytes": None,
            "modified_utc": None,
            "sha256": None,
        }

    stat = resolved.stat()
    modified = dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc)
    return {
        "label": label,
        "relative_path": relpath,
        "exists": True,
        "size_bytes": int(stat.st_size),
        "modified_utc": modified.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "sha256": sha256_file(resolved),
    }


cfg = load_config()
cfg.ensure_directories()

# Keep a frozen YAML snapshot next to run tables for audit portability.
with open(cfg.RUN_CONFIG_SNAPSHOT, "w", encoding="utf-8") as handle:
    yaml.safe_dump(cfg.RUN_CFG, handle, sort_keys=False)
print("Wrote:", cfg.RUN_CONFIG_SNAPSHOT)

artifact_items = [
    ("run_config", cfg.RUN_CONFIG_PATH),
    ("run_config_snapshot", cfg.RUN_CONFIG_SNAPSHOT),
    ("nt_mask_500m", cfg.NT_MASK_500M),
    ("mvt_labels_500m", cfg.MVT_LABELS_500M),
    ("split_summary", cfg.SPLIT_SUMMARY),
    ("candidate_blocks", cfg.CANDIDATE_BLOCKS_SUMMARY),
    ("split_training_samples", cfg.SPLIT_TRAINING_SAMPLES),
    ("metrics_by_split", cfg.METRICS_BY_SPLIT),
    ("aggregate_metrics", cfg.AGGREGATE_METRICS),
    ("metrics_by_holdout_candidate", cfg.METRICS_BY_HOLDOUT_CANDIDATE),
    ("validation_holdout_gap_diagnostic", cfg.VALIDATION_HOLDOUT_GAP_DIAGNOSTIC),
    ("final_training_table", cfg.FINAL_TRAINING_TABLE),
    ("final_model", cfg.FINAL_RANDOM_FOREST_MODEL),
    ("final_feature_importance", cfg.FINAL_FEATURE_IMPORTANCE),
    ("final_prospectivity_map", cfg.FINAL_PROSPECTIVITY_MAP),
    ("final_score_summary", cfg.FINAL_SCORE_SUMMARY),
    ("model_review_report", cfg.MODEL_REVIEW_REPORT),
]

for feature_name in cfg.FEATURE_COLUMNS:
    artifact_items.append((f"predictor_{feature_name}", cfg.PREDICTOR_RASTERS[feature_name]))
for pct in cfg.TOP_K_PCTS:
    artifact_items.append(
        (
            f"top_{pct}_percent_map",
            cfg.MAPS_DIR / f"mvt_top_{pct}_percent_rf_v4_500m.tif",
        )
    )

artifacts = [artifact_record(cfg, label, path) for label, path in artifact_items]

manifest = {
    "run_name": cfg.RUN_NAME,
    "generated_utc": utc_now_iso(),
    "git_commit": git_commit_hash(cfg.PROJECT_ROOT),
    "project_root": str(cfg.PROJECT_ROOT),
    "active_config_relative_path": cfg.to_relative_project_path(cfg.RUN_CONFIG_PATH),
    "active_config": cfg.RUN_CFG,
    "claims_language": [
        "Scores are relative prospectivity rankings, not calibrated deposit probabilities.",
        "Holdout evidence comes from split evaluation, not from the final production model.",
    ],
    "artifacts": artifacts,
}

with open(cfg.RUN_MANIFEST_JSON, "w", encoding="utf-8") as handle:
    json.dump(manifest, handle, indent=2)

print("Wrote:", cfg.RUN_MANIFEST_JSON)
