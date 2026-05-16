"""Shared v3 configuration module.

This file is imported by every v3 script. It centralizes:
1) project paths and file locations,
2) values loaded from the YAML run config,
3) fixed workflow decisions for splitting/sampling,
4) validation rules that keep the run scientifically consistent.

Nothing in this module performs geoprocessing or modeling directly. Its job is
to provide validated constants and helper functions.
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
RUN_CONFIG_PATH = CONFIGS_DIR / "v3_run_config.yml"

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


def load_run_config(path):
    """Load and validate the YAML run configuration as a Python dictionary.

    Args:
        path: Filesystem path to ``v3_run_config.yml``.

    Returns:
        Parsed configuration mapping.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the YAML content is not a mapping (dictionary-like).
    """
    if not path.exists():
        raise FileNotFoundError(f"Missing run config: {path}")
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError("Run config must be a YAML mapping.")
    return cfg


# Load run-time knobs once at import time so all scripts see the same values.
RUN_CFG = load_run_config(RUN_CONFIG_PATH)

RUN_META = RUN_CFG.get("run", {})
DATA_ROLES = RUN_CFG.get("data_roles", {})
SCALING_CFG = RUN_CFG.get("scaling", {})
SAMPLING_CFG = RUN_CFG.get("sampling", {})
PREDICTION_CFG = RUN_CFG.get("prediction", {})
MODEL_CFG = RUN_CFG.get("model", {})

# Core run metadata.
PROJECT_CRS = str(RUN_META.get("crs", "EPSG:3577"))
PIXEL_SIZE = int(RUN_META.get("pixel_size_m", 500))
RANDOM_STATE = int(RUN_META.get("random_state", 42))
TOP_K_PCTS = [int(x) for x in RUN_META.get("top_k_pcts", [1, 5, 10])]

# Feature/label role definitions from YAML.
LABEL_COLUMN = str(DATA_ROLES.get("label_column", "label"))
FEATURE_COLUMNS = list(DATA_ROLES.get("feature_columns", []))
IDENTIFIER_COLUMNS = list(DATA_ROLES.get("identifier_columns", []))
FORBIDDEN_FEATURE_PATTERNS = list(DATA_ROLES.get("forbidden_feature_patterns", []))

# Scaling configuration (v3 requires scaling enabled).
SCALING_ENABLED = bool(SCALING_CFG.get("enabled", True))
SCALING_METHOD = str(SCALING_CFG.get("method", "standard"))
SCALING_WITH_MEAN = bool(SCALING_CFG.get("with_mean", True))
SCALING_WITH_STD = bool(SCALING_CFG.get("with_std", True))

# Model configuration (v3 currently supports RandomForest only).
MODEL_TYPE = str(MODEL_CFG.get("type", "random_forest"))
MODEL_N_ESTIMATORS = int(MODEL_CFG.get("n_estimators", 500))
MODEL_MIN_SAMPLES_LEAF = int(MODEL_CFG.get("min_samples_leaf", 2))
MODEL_CLASS_WEIGHT = MODEL_CFG.get("class_weight", "balanced")
MODEL_N_JOBS = int(MODEL_CFG.get("n_jobs", -1))

# Sampling and prediction runtime knobs.
BACKGROUND_PER_POSITIVE = int(SAMPLING_CFG.get("background_per_positive", 50))
USE_SPATIALLY_STRATIFIED_BACKGROUND = bool(
    SAMPLING_CFG.get("use_spatially_stratified_background", True)
)
BACKGROUND_BLOCK_SIZE_PIXELS = int(SAMPLING_CFG.get("background_block_size_pixels", 100))
PREDICTION_CHUNK_SIZE = int(PREDICTION_CFG.get("chunk_size_pixels", 200_000))

# V2/V3 split decisions from DECISIONS_TO_MAKE.md.
USE_SPATIAL_BUFFER = False
BUFFER_DISTANCE_M = 0

TARGET_ACCEPTED_SPLITS = 10
MIN_ACCEPTED_SPLITS_FOR_NON_EXPLORATORY = 5

STRICT_HOLDOUT_AREA = 0.10
STRICT_VALIDATION_AREA = 0.10
STRICT_MIN_HOLDOUT_POSITIVES = 5
STRICT_MIN_VALIDATION_POSITIVES = 5
STRICT_MIN_TRAIN_POSITIVES = 40

FALLBACK_AREA_MIN = 0.08
FALLBACK_AREA_MAX = 0.20
FALLBACK_MIN_POSITIVES = 4

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

PREDICTOR_RASTERS = {
    "carbonate_host": RASTERS_500M_DIR / "carbonate_host_500m.tif",
    "lithology_code": RASTERS_500M_DIR / "lithology_code_500m.tif",
    "dist_faults": RASTERS_500M_DIR / "dist_faults_500m.tif",
    **{name: RASTERS_500M_DIR / f"{name}_500m.tif" for name in CONTINUOUS_RASTERS},
}

# 0 is a valid model value for these rasters inside the NT mask.
ZERO_IS_VALID_PREDICTORS = {"carbonate_host", "lithology_code"}

NT_BOUNDARY_3577 = ROI_DIR / "nt_boundary_3577_dissolved.gpkg"
NT_MASK_500M = ROI_DIR / "nt_mask_500m.tif"
MVT_POINTS_3577 = LABELS_DIR / "mvt_points_nt_3577.gpkg"
MVT_LABELS_500M = LABELS_DIR / "mvt_labels_500m.tif"

SPLIT_SUMMARY = SPLITS_DIR / "split_summary.csv"
SPLIT_MASK_PREFIX = "split"
SPLIT_TRAINING_SAMPLES = MODELS_DIR / "split_training_samples.csv"
METRICS_BY_SPLIT = MODELS_DIR / "metrics_by_split.csv"
AGGREGATE_METRICS = MODELS_DIR / "aggregate_metrics.csv"
FINAL_TRAINING_TABLE = MODELS_DIR / "final_training_table.csv"
FINAL_RANDOM_FOREST_MODEL = MODELS_DIR / "final_random_forest_mvt.joblib"
FINAL_FEATURE_IMPORTANCE = MODELS_DIR / "final_feature_importance.csv"
FINAL_PROSPECTIVITY_MAP = MAPS_DIR / "mvt_prospectivity_rf_v3_500m.tif"


def validate_run_config():
    """Fail fast when YAML settings violate v3 workflow rules.

    The checks here protect against common mistakes:
    - empty or duplicated feature lists,
    - accidental inclusion of label/coordinate-like fields as features,
    - unsupported scaling/model settings for this run version.
    """
    if not FEATURE_COLUMNS:
        raise ValueError("Run config must define at least one feature column.")

    missing_features = [name for name in FEATURE_COLUMNS if name not in PREDICTOR_RASTERS]
    if missing_features:
        raise ValueError(
            "Run config feature_columns are not in PREDICTOR_RASTERS: "
            + ", ".join(missing_features)
        )

    if LABEL_COLUMN in FEATURE_COLUMNS:
        raise ValueError(f"Label column '{LABEL_COLUMN}' cannot be in feature_columns.")

    if len(FEATURE_COLUMNS) != len(set(FEATURE_COLUMNS)):
        raise ValueError("feature_columns contains duplicate names.")

    for col in FEATURE_COLUMNS:
        for pattern in FORBIDDEN_FEATURE_PATTERNS:
            if re.search(pattern, col, flags=re.IGNORECASE):
                raise ValueError(
                    f"Feature '{col}' matches forbidden coordinate pattern '{pattern}'."
                )

    if not SCALING_ENABLED:
        raise ValueError("V3 requires scaling.enabled = true.")
    if SCALING_METHOD != "standard":
        raise ValueError("V3 currently supports only scaling.method='standard'.")

    if MODEL_TYPE != "random_forest":
        raise ValueError("V3 currently supports only model.type='random_forest'.")
    if MODEL_N_ESTIMATORS <= 0:
        raise ValueError("model.n_estimators must be greater than zero.")
    if MODEL_MIN_SAMPLES_LEAF <= 0:
        raise ValueError("model.min_samples_leaf must be greater than zero.")
    if BACKGROUND_PER_POSITIVE <= 0:
        raise ValueError("sampling.background_per_positive must be greater than zero.")
    if BACKGROUND_BLOCK_SIZE_PIXELS <= 0:
        raise ValueError("sampling.background_block_size_pixels must be greater than zero.")
    if PREDICTION_CHUNK_SIZE <= 0:
        raise ValueError("prediction.chunk_size_pixels must be greater than zero.")


# Validate immediately when imported so downstream scripts can assume consistency.
validate_run_config()


def ensure_directories():
    """Create all expected output directories if they are missing."""
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


def required_input_paths():
    """Return all external/raw inputs expected by the workflow.

    Returns:
        Mapping from logical input name to filesystem path.
    """
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
    """Return only missing entries from ``required_input_paths()``."""
    return {name: path for name, path in required_input_paths().items() if not path.exists()}
