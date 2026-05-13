from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA = PROJECT_ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
OUTPUTS = PROJECT_ROOT / "outputs"

ROI_DIR = PROCESSED / "roi"
VECTORS_3577_DIR = PROCESSED / "vectors_3577"
RASTERS_500M_DIR = PROCESSED / "rasters_500m"
LABELS_DIR = PROCESSED / "labels"
SPLITS_DIR = PROCESSED / "splits"
MODELS_DIR = PROCESSED / "models"
MAPS_DIR = OUTPUTS / "maps"
TABLES_DIR = OUTPUTS / "tables"

PROJECT_CRS = "EPSG:3577"
SOURCE_CRS = "EPSG:4326"
PIXEL_SIZE = 500
NODATA_FLOAT = -9999.0
RANDOM_STATE = 42

# V2 decisions from DECISIONS_TO_MAKE.md.
BACKGROUND_PER_POSITIVE = 50
USE_SPATIALLY_STRATIFIED_BACKGROUND = True
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

TOP_K_PCTS = [1, 5, 10]

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
    **{
        name: RASTERS_500M_DIR / f"{name}_500m.tif"
        for name in CONTINUOUS_RASTERS
    },
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
FINAL_PROSPECTIVITY_MAP = MAPS_DIR / "mvt_prospectivity_rf_v2_500m.tif"


def ensure_directories():
    for path in [
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
    return {
        name: path
        for name, path in required_input_paths().items()
        if not path.exists()
    }
