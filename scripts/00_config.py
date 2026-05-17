"""Shared v5 configuration module.

This module is imported by every v5 script. It centralizes:
1) project paths and artifact filenames,
2) values loaded from the YAML run config,
3) fixed v4 baseline controls reused in v5,
4) feature-ablation experiment definitions and validation.
"""

from pathlib import Path
import re

try:
    import yaml
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "Missing dependency 'PyYAML'. Install it in your environment, for example: "
        "pip install pyyaml"
    ) from exc


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA = PROJECT_ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
OUTPUTS = PROJECT_ROOT / "outputs"
CONFIGS_DIR = PROJECT_ROOT / "configs"
RUN_CONFIG_PATH = CONFIGS_DIR / "v5_run_config.yml"

ROI_DIR = PROCESSED / "roi"
VECTORS_3577_DIR = PROCESSED / "vectors_3577"
RASTERS_500M_DIR = PROCESSED / "rasters_500m"
LABELS_DIR = PROCESSED / "labels"
SPLITS_DIR = PROCESSED / "splits"
MODELS_DIR = PROCESSED / "models"
MAPS_DIR = OUTPUTS / "maps"
TABLES_DIR = OUTPUTS / "tables"

SOURCE_CRS = "EPSG:4326"
NODATA_FLOAT = -9999.0

MANDATORY_CLAIMS_LANGUAGE = [
    "Scores are relative prospectivity rankings, not calibrated deposit probabilities.",
    "Holdout evidence comes from split evaluation, not from the final production model.",
    "V5 compares feature subsets under fixed V4 conditions; it does not prove geological causality.",
    "Ablation results are screening evidence only and should be interpreted with geological judgment.",
]


def load_run_config(path):
    """Load and validate the YAML run configuration as a dictionary."""
    if not path.exists():
        raise FileNotFoundError(f"Missing run config: {path}")
    with open(path, "r", encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)
    if not isinstance(cfg, dict):
        raise ValueError("Run config must be a YAML mapping.")
    return cfg


RUN_CFG = load_run_config(RUN_CONFIG_PATH)

RUN_META = RUN_CFG.get("run", {})
DATA_ROLES = RUN_CFG.get("data_roles", {})
SCALING_CFG = RUN_CFG.get("scaling", {})
SAMPLING_CFG = RUN_CFG.get("sampling", {})
PREDICTION_CFG = RUN_CFG.get("prediction", {})
SPLIT_CFG = RUN_CFG.get("split", {})
MODEL_CFG = RUN_CFG.get("model", {})
ABLATION_CFG = RUN_CFG.get("ablation", {})

RUN_NAME = str(RUN_META.get("name", "nt_mvt_v5_feature_ablation_500m"))
PROJECT_CRS = str(RUN_META.get("crs", "EPSG:3577"))
PIXEL_SIZE = int(RUN_META.get("pixel_size_m", 500))
RANDOM_STATE = int(RUN_META.get("random_state", 42))
TOP_K_PCTS = [int(x) for x in RUN_META.get("top_k_pcts", [1, 5, 10])]

LABEL_COLUMN = str(DATA_ROLES.get("label_column", "label"))
FEATURE_COLUMNS = [str(x) for x in DATA_ROLES.get("feature_columns", [])]
IDENTIFIER_COLUMNS = [str(x) for x in DATA_ROLES.get("identifier_columns", [])]
FORBIDDEN_FEATURE_PATTERNS = [str(x) for x in DATA_ROLES.get("forbidden_feature_patterns", [])]

SCALING_ENABLED = bool(SCALING_CFG.get("enabled", True))
SCALING_METHOD = str(SCALING_CFG.get("method", "standard"))
SCALING_WITH_MEAN = bool(SCALING_CFG.get("with_mean", True))
SCALING_WITH_STD = bool(SCALING_CFG.get("with_std", True))

MODEL_TYPE = str(MODEL_CFG.get("type", "random_forest"))
MODEL_N_ESTIMATORS = int(MODEL_CFG.get("n_estimators", 500))
MODEL_MIN_SAMPLES_LEAF = int(MODEL_CFG.get("min_samples_leaf", 2))
MODEL_CLASS_WEIGHT = MODEL_CFG.get("class_weight", "balanced")
MODEL_N_JOBS = int(MODEL_CFG.get("n_jobs", -1))

BACKGROUND_PER_POSITIVE = int(SAMPLING_CFG.get("background_per_positive", 50))
USE_SPATIALLY_STRATIFIED_BACKGROUND = bool(
    SAMPLING_CFG.get("use_spatially_stratified_background", True)
)
BACKGROUND_BLOCK_SIZE_PIXELS = int(SAMPLING_CFG.get("background_block_size_pixels", 100))
PREDICTION_CHUNK_SIZE = int(PREDICTION_CFG.get("chunk_size_pixels", 200_000))

SPLIT_STRATEGY = str(SPLIT_CFG.get("strategy", "zone_diverse_deterministic"))
SPLIT_N_GEOGRAPHIC_ZONES = int(SPLIT_CFG.get("n_geographic_zones", 3))
SPLIT_REQUIRE_MIN_ZONE_COUNT = int(SPLIT_CFG.get("require_min_zone_count", 2))
SPLIT_PREFER_CROSS_ZONE_VALIDATION = bool(
    SPLIT_CFG.get("prefer_cross_zone_validation", True)
)
SPLIT_ALLOW_SWAPPED_PAIRS = bool(SPLIT_CFG.get("allow_swapped_pairs", False))
TARGET_ACCEPTED_SPLITS = int(SPLIT_CFG.get("target_accepted_splits", 10))
MIN_ACCEPTED_SPLITS_FOR_NON_EXPLORATORY = int(
    SPLIT_CFG.get("min_accepted_splits_for_non_exploratory", 5)
)

USE_SPATIAL_BUFFER = bool(SPLIT_CFG.get("use_spatial_buffer", True))
BUFFER_DISTANCE_M = int(SPLIT_CFG.get("buffer_distance_m", 10_000))
STRICT_AREA_TOLERANCE = float(SPLIT_CFG.get("strict_area_tolerance", 0.03))

STRICT_HOLDOUT_AREA = float(SPLIT_CFG.get("strict_holdout_area", 0.10))
STRICT_VALIDATION_AREA = float(SPLIT_CFG.get("strict_validation_area", 0.10))
STRICT_MIN_HOLDOUT_POSITIVES = int(SPLIT_CFG.get("strict_min_holdout_positives", 3))
STRICT_MIN_VALIDATION_POSITIVES = int(
    SPLIT_CFG.get("strict_min_validation_positives", 3)
)
STRICT_MIN_TRAIN_POSITIVES = int(SPLIT_CFG.get("strict_min_train_positives", 30))

FALLBACK_AREA_MIN = float(SPLIT_CFG.get("fallback_area_min", 0.08))
FALLBACK_AREA_MAX = float(SPLIT_CFG.get("fallback_area_max", 0.20))
FALLBACK_MIN_POSITIVES = int(SPLIT_CFG.get("fallback_min_positives", 3))

ABLATION_ENABLED = bool(ABLATION_CFG.get("enabled", True))
ABLATION_BASELINE_EXPERIMENT = str(ABLATION_CFG.get("baseline_experiment", "full_baseline"))
ABLATION_AGGREGATE_REFERENCE_REGION = str(
    ABLATION_CFG.get("aggregate_reference_region", "holdout")
)
ABLATION_RANKING_METRIC = str(ABLATION_CFG.get("ranking_metric", "average_precision"))
ABLATION_RANKING_SECONDARY_METRICS = [
    str(x) for x in ABLATION_CFG.get("ranking_secondary_metrics", [])
]

AUSTRALIA_BOUNDARY = RAW / "gadm41_AUS_shp" / "gadm41_AUS_1.shp"

GEOLOGY = (
    INTERIM
    / "[Geological Data] Geology shapefiles for the United States and Australia"
    / "Geology_Australia"
    / "Geology_Australia.shp"
)

FAULTS = (
    INTERIM
    / "[Geological Data] Shapefiles of faults for the United States, Canada, and Australia"
    / "GeologyFaults_Australia"
    / "GeologyFaults_Australia.shp"
)

OCCURRENCES = (
    INTERIM
    / "[Geological Data] Basin-hosted (CD:SEDEX and MVT) Zn-Pb deposits and prospects for the United States, Canada, and Australia"
    / "GeologyMineralOccurrences_USCanada_Australia.csv"
)

LAWLEY_MVT_MODEL = (
    INTERIM
    / "[Prospectivity Models] Prospectivity models - clastic-dominated (CD) and Mississippi Valley-type (MVT) GeoTIFF grids for the United States, Canada, and Australia"
    / "ProspectivityModel_MVT_Australia"
    / "Aus_Lawleyetal_MVTModel.tif"
)

CONTINUOUS_RASTERS = {
    "moho_depth": INTERIM
    / "[Geophysical Data] Depth to Moho GeoTIFF grids for the United States, Canada, and Australia"
    / "GeophysicsMoho_Australia"
    / "GeophysicsMoho_Australia.tif",
    "lab_depth": INTERIM
    / "[Geophysical Data] Depth to lithosphere-asthenosphere boundary GeoTIFF grids for the United States, Canada, and Australia"
    / "GeophysicsLAB_Australia"
    / "GeophysicsLAB_Australia.tif",
    "gravity": INTERIM
    / "[Geophysical Data] Gravity and related derivative GeoTIFF grids and data for Australia"
    / "GeophysicsGravity_Australia"
    / "GeophysicsGravity_Australia.tif",
    "gravity_hgm": INTERIM
    / "[Geophysical Data] Gravity and related derivative GeoTIFF grids and data for Australia"
    / "GeophysicsGravity_HGM_Australia"
    / "GeophysicsGravity_HGM_Australia.tif",
    "mag_rtp": INTERIM
    / "[Geophysical Data] Magnetic and related derivative GeoTIFF grids and data for Australia"
    / "GeophysicsMagRTP_Australia"
    / "GeophysicsMagRTP_Australia.tif",
    "mag_hgm": INTERIM
    / "[Geophysical Data] Magnetic and related derivative GeoTIFF grids and data for Australia"
    / "GeophysicsMagRTP_HGM_Australia"
    / "GeophysicsMagRTP_HGM_Australia.tif",
    "shape_index": INTERIM
    / "[Geophysical Data] Shape index GeoTIFF grids from satellite gravity for the United States, Canada, and Australia"
    / "GeophysicsSatelliteGravity_ShapeIndex_Australia"
    / "GeophysicsSatelliteGravity_ShapeIndex_Australia.tif",
}

LITHOLOGY_ONEHOT_CLASSES = [
    "carbonate",
    "chemical",
    "evaporite",
    "siliciclastic",
    "unconsolidated",
    "igneous",
    "metamorphic",
    "unknown",
]
LITHOLOGY_ONEHOT_FEATURES = [f"lithology_{name}" for name in LITHOLOGY_ONEHOT_CLASSES]

PREDICTOR_RASTERS = {
    "carbonate_host": RASTERS_500M_DIR / "carbonate_host_500m.tif",
    **{name: RASTERS_500M_DIR / f"{name}_500m.tif" for name in LITHOLOGY_ONEHOT_FEATURES},
    "dist_faults": RASTERS_500M_DIR / "dist_faults_500m.tif",
    **{name: RASTERS_500M_DIR / f"{name}_500m.tif" for name in CONTINUOUS_RASTERS},
}

# 0 is a valid predictor value for binary one-hot layers inside the NT mask.
ZERO_IS_VALID_PREDICTORS = {"carbonate_host", *set(LITHOLOGY_ONEHOT_FEATURES)}

NT_BOUNDARY_3577 = ROI_DIR / "nt_boundary_3577_dissolved.gpkg"
NT_MASK_500M = ROI_DIR / "nt_mask_500m.tif"
MVT_POINTS_3577 = LABELS_DIR / "mvt_points_nt_3577.gpkg"
MVT_LABELS_500M = LABELS_DIR / "mvt_labels_500m.tif"

SPLIT_SUMMARY = SPLITS_DIR / "split_summary.csv"
CANDIDATE_BLOCKS_SUMMARY = SPLITS_DIR / "candidate_blocks.csv"
SPLIT_MASK_PREFIX = "split"
SPLIT_TRAINING_SAMPLES = MODELS_DIR / "split_training_samples.csv"

# Legacy/non-ablation split metrics paths retained for continuity.
METRICS_BY_SPLIT = MODELS_DIR / "metrics_by_split.csv"
AGGREGATE_METRICS = MODELS_DIR / "aggregate_metrics.csv"
METRICS_BY_HOLDOUT_CANDIDATE = MODELS_DIR / "metrics_by_holdout_candidate.csv"
VALIDATION_HOLDOUT_GAP_DIAGNOSTIC = MODELS_DIR / "validation_holdout_gap_diagnostic.csv"

FEATURE_ABLATION_METRICS_BY_SPLIT = MODELS_DIR / "feature_ablation_metrics_by_split.csv"
FEATURE_ABLATION_AGGREGATE_METRICS = MODELS_DIR / "feature_ablation_aggregate_metrics.csv"
FEATURE_ABLATION_BY_HOLDOUT_CANDIDATE = MODELS_DIR / "feature_ablation_by_holdout_candidate.csv"
FEATURE_ABLATION_DELTA_VS_BASELINE = MODELS_DIR / "feature_ablation_delta_vs_baseline.csv"
FEATURE_ABLATION_VALIDATION_HOLDOUT_GAP = MODELS_DIR / "feature_ablation_validation_holdout_gap.csv"
FEATURE_ABLATION_RANKED_SUMMARY = TABLES_DIR / "feature_ablation_ranked_summary.csv"

FINAL_TRAINING_TABLE = MODELS_DIR / "final_training_table.csv"
FINAL_RANDOM_FOREST_MODEL = MODELS_DIR / "final_random_forest_mvt.joblib"
FINAL_FEATURE_IMPORTANCE = MODELS_DIR / "final_feature_importance.csv"
FINAL_PROSPECTIVITY_MAP = MAPS_DIR / "mvt_prospectivity_rf_v5_500m.tif"
FINAL_SCORE_SUMMARY = TABLES_DIR / "final_score_summary_v5.csv"
MODEL_REVIEW_REPORT = TABLES_DIR / "v5_model_review.txt"
RUN_CONFIG_SNAPSHOT = TABLES_DIR / "v5_run_config_snapshot.yml"
RUN_MANIFEST_JSON = OUTPUTS / "run_manifest_v5.json"


def _matches_forbidden_pattern(feature_name):
    """Return matching forbidden pattern or None."""
    for pattern in FORBIDDEN_FEATURE_PATTERNS:
        if re.search(pattern, feature_name, flags=re.IGNORECASE):
            return pattern
    return None


def resolve_ablation_experiments():
    """Resolve configured ablation experiments to explicit feature lists."""
    experiments = ABLATION_CFG.get("experiments", [])
    if not isinstance(experiments, list) or not experiments:
        raise ValueError("ablation.experiments must be a non-empty list.")

    resolved = []
    seen_ids = set()

    for exp in experiments:
        if not isinstance(exp, dict):
            raise ValueError("Each ablation experiment must be a mapping.")

        exp_id = str(exp.get("id", "")).strip()
        if not exp_id:
            raise ValueError("Each ablation experiment must have a non-empty id.")
        if exp_id in seen_ids:
            raise ValueError(f"Duplicate ablation experiment id: {exp_id}")
        seen_ids.add(exp_id)

        label = str(exp.get("label", exp_id)).strip()
        mode = str(exp.get("mode", "")).strip().lower()

        if mode == "include":
            features = exp.get("features", [])
            if not isinstance(features, list) or not features:
                raise ValueError(
                    f"Experiment '{exp_id}' with mode=include must define non-empty features list."
                )
            resolved_features = [str(f) for f in features]
        elif mode == "drop":
            drop_features = exp.get("drop_features", [])
            if not isinstance(drop_features, list) or not drop_features:
                raise ValueError(
                    f"Experiment '{exp_id}' with mode=drop must define non-empty drop_features list."
                )
            drop_set = {str(f) for f in drop_features}
            resolved_features = [f for f in FEATURE_COLUMNS if f not in drop_set]
        else:
            raise ValueError(f"Experiment '{exp_id}' has unsupported mode '{mode}'.")

        if len(resolved_features) != len(set(resolved_features)):
            raise ValueError(f"Experiment '{exp_id}' resolves to duplicate feature names.")
        if not resolved_features:
            raise ValueError(f"Experiment '{exp_id}' resolves to an empty feature list.")

        missing = [f for f in resolved_features if f not in FEATURE_COLUMNS]
        if missing:
            raise ValueError(
                f"Experiment '{exp_id}' references features outside data_roles.feature_columns: "
                + ", ".join(missing)
            )

        for feature_name in resolved_features:
            matched = _matches_forbidden_pattern(feature_name)
            if matched is not None:
                raise ValueError(
                    f"Experiment '{exp_id}' feature '{feature_name}' matches forbidden pattern '{matched}'."
                )

        dropped = [f for f in FEATURE_COLUMNS if f not in resolved_features]
        resolved.append(
            {
                "id": exp_id,
                "label": label,
                "mode": mode,
                "features": resolved_features,
                "included_features": resolved_features,
                "dropped_features": dropped,
                "feature_count": len(resolved_features),
            }
        )

    ids = {exp["id"] for exp in resolved}
    if ABLATION_BASELINE_EXPERIMENT not in ids:
        raise ValueError(
            "ablation.baseline_experiment not found in experiments: "
            f"{ABLATION_BASELINE_EXPERIMENT}"
        )

    baseline = next(exp for exp in resolved if exp["id"] == ABLATION_BASELINE_EXPERIMENT)
    if baseline["features"] != FEATURE_COLUMNS:
        raise ValueError(
            "Baseline ablation experiment must exactly match data_roles.feature_columns "
            "for v5 controlled comparison."
        )

    return resolved


ABLATION_EXPERIMENTS = resolve_ablation_experiments()


def validate_run_config():
    """Fail fast when YAML settings violate v5 workflow rules."""
    if RUN_NAME != "nt_mvt_v5_feature_ablation_500m":
        raise ValueError("V5 requires run.name='nt_mvt_v5_feature_ablation_500m'.")

    if not FEATURE_COLUMNS:
        raise ValueError("Run config must define at least one feature column.")

    missing_features = [name for name in FEATURE_COLUMNS if name not in PREDICTOR_RASTERS]
    if missing_features:
        raise ValueError(
            "Run config feature_columns are not in PREDICTOR_RASTERS: "
            + ", ".join(missing_features)
        )

    missing_onehot = [name for name in LITHOLOGY_ONEHOT_FEATURES if name not in FEATURE_COLUMNS]
    if missing_onehot:
        raise ValueError(
            "V5 requires one-hot lithology features in feature_columns: "
            + ", ".join(missing_onehot)
        )

    if LABEL_COLUMN in FEATURE_COLUMNS:
        raise ValueError(f"Label column '{LABEL_COLUMN}' cannot be in feature_columns.")

    if len(FEATURE_COLUMNS) != len(set(FEATURE_COLUMNS)):
        raise ValueError("feature_columns contains duplicate names.")

    for col in FEATURE_COLUMNS:
        matched = _matches_forbidden_pattern(col)
        if matched is not None:
            raise ValueError(
                f"Feature '{col}' matches forbidden coordinate pattern '{matched}'."
            )

    if not SCALING_ENABLED:
        raise ValueError("V5 requires scaling.enabled = true.")
    if SCALING_METHOD != "standard":
        raise ValueError("V5 currently supports only scaling.method='standard'.")

    if MODEL_TYPE != "random_forest":
        raise ValueError("V5 currently supports only model.type='random_forest'.")
    if MODEL_N_ESTIMATORS <= 0:
        raise ValueError("model.n_estimators must be greater than zero.")
    if MODEL_MIN_SAMPLES_LEAF <= 0:
        raise ValueError("model.min_samples_leaf must be greater than zero.")

    if BACKGROUND_PER_POSITIVE != 50:
        raise ValueError("V5 requires sampling.background_per_positive = 50.")
    if not USE_SPATIALLY_STRATIFIED_BACKGROUND:
        raise ValueError("V5 requires use_spatially_stratified_background = true.")
    if BACKGROUND_BLOCK_SIZE_PIXELS <= 0:
        raise ValueError("sampling.background_block_size_pixels must be greater than zero.")
    if PREDICTION_CHUNK_SIZE <= 0:
        raise ValueError("prediction.chunk_size_pixels must be greater than zero.")

    if SPLIT_STRATEGY != "zone_diverse_deterministic":
        raise ValueError("V5 requires split.strategy='zone_diverse_deterministic'.")
    if SPLIT_N_GEOGRAPHIC_ZONES < 2:
        raise ValueError("split.n_geographic_zones must be at least 2.")
    if not (2 <= SPLIT_REQUIRE_MIN_ZONE_COUNT <= SPLIT_N_GEOGRAPHIC_ZONES):
        raise ValueError(
            "split.require_min_zone_count must be between 2 and split.n_geographic_zones."
        )
    if SPLIT_ALLOW_SWAPPED_PAIRS:
        raise ValueError("V5 requires split.allow_swapped_pairs = false.")
    if TARGET_ACCEPTED_SPLITS <= 0:
        raise ValueError("split.target_accepted_splits must be greater than zero.")
    if MIN_ACCEPTED_SPLITS_FOR_NON_EXPLORATORY <= 0:
        raise ValueError(
            "split.min_accepted_splits_for_non_exploratory must be greater than zero."
        )

    if not USE_SPATIAL_BUFFER:
        raise ValueError("V5 requires split.use_spatial_buffer = true.")
    if BUFFER_DISTANCE_M != 10000:
        raise ValueError("V5 requires split.buffer_distance_m = 10000.")
    if STRICT_AREA_TOLERANCE <= 0:
        raise ValueError("split.strict_area_tolerance must be greater than zero.")

    if not (0 < STRICT_HOLDOUT_AREA < 1 and 0 < STRICT_VALIDATION_AREA < 1):
        raise ValueError("strict area shares must be between 0 and 1.")
    if STRICT_MIN_HOLDOUT_POSITIVES <= 0 or STRICT_MIN_VALIDATION_POSITIVES <= 0:
        raise ValueError("strict holdout/validation positive minima must be > 0.")
    if STRICT_MIN_TRAIN_POSITIVES <= 0:
        raise ValueError("split.strict_min_train_positives must be > 0.")
    if not (0 < FALLBACK_AREA_MIN <= FALLBACK_AREA_MAX < 1):
        raise ValueError("fallback areas must satisfy 0 < min <= max < 1.")
    if FALLBACK_MIN_POSITIVES <= 0:
        raise ValueError("split.fallback_min_positives must be > 0.")

    if not TOP_K_PCTS:
        raise ValueError("run.top_k_pcts must contain at least one percentile.")
    if any(pct <= 0 or pct >= 100 for pct in TOP_K_PCTS):
        raise ValueError("All run.top_k_pcts values must be in the range 1..99.")

    if not ABLATION_ENABLED:
        raise ValueError("V5 requires ablation.enabled = true.")
    if ABLATION_AGGREGATE_REFERENCE_REGION not in {"holdout", "validation"}:
        raise ValueError("ablation.aggregate_reference_region must be 'holdout' or 'validation'.")


validate_run_config()


def ensure_directories():
    """Create expected output directories if they are missing."""
    for path in [
        CONFIGS_DIR,
        ROI_DIR,
        VECTORS_3577_DIR,
        RASTERS_500M_DIR,
        LABELS_DIR,
        SPLITS_DIR,
        MODELS_DIR,
        MAPS_DIR,
        TABLES_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def to_relative_project_path(path):
    """Return a project-relative path string when possible."""
    path_obj = Path(path)
    try:
        return str(path_obj.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        try:
            return str(path_obj.relative_to(PROJECT_ROOT))
        except ValueError:
            return str(path_obj)


def resolve_project_path(path_value):
    """Resolve an absolute or project-relative filesystem path."""
    path_obj = Path(path_value)
    if path_obj.is_absolute():
        return path_obj
    return PROJECT_ROOT / path_obj


def required_input_paths():
    """Return all external/raw inputs expected by the workflow."""
    paths = {
        "australia_boundary": AUSTRALIA_BOUNDARY,
        "geology": GEOLOGY,
        "faults": FAULTS,
        "occurrences": OCCURRENCES,
        "lawley_mvt_model_for_comparison_only": LAWLEY_MVT_MODEL,
    }
    paths.update({f"continuous_{name}": path for name, path in CONTINUOUS_RASTERS.items()})
    return paths


def missing_required_inputs():
    """Return missing entries from ``required_input_paths()``."""
    return {name: path for name, path in required_input_paths().items() if not path.exists()}
