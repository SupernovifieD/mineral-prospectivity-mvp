# Python Workflow V2: Northern Territory MVT Prospectivity at 500 m

This document is the v2 workflow for the Northern Territory MVT mineral prospectivity project.

It builds on `archive/v1/PROJECT_WORKFLOW_NT_MVT_500M.md` and keeps the v1 processing logic wherever it still fits. The main change in v2 is not a more complex model. The main change is a defensible spatial evaluation framework.

V2 primary goal:

```text
Scientific benchmark first, screening map second.
```

V2 model stance:

```text
Keep the v1 predictor set and fixed Random Forest baseline.
Improve evaluation, splitting, metrics, and reporting before adding new predictors or models.
```

## 1. V2 Decisions Used In This Workflow

These decisions come from `DECISIONS_TO_MAKE.md`.

| Topic | V2 decision |
| --- | --- |
| Study area | Northern Territory only |
| Grid | 500 m pixels, `EPSG:3577` |
| Positive labels | All Australian MVT points inside NT, evaluated as unique positive pixels |
| Background labels | Background/unlabeled, not proven barren |
| Background sampling | Spatially stratified background sampling |
| Split strategy | Repeated spatial train/validation/holdout splits |
| Split geometry | Square blocks |
| Split constraints | Holdout 10%, validation 10%, at least 5 holdout positives, at least 5 validation positives, at least 40 training positives, no overlap, no buffer |
| Fallback split policy | If strict rules fail, widen area to 8-20%, then allow 4-5 positives, then revisit geometry later |
| Minimum splits | Target at least 10 accepted splits; fewer than 5 means exploratory only |
| Candidate area measurement | Valid pixels inside ROI, not raw square area |
| Metrics | PR-AUC, top 1/5/10% recall, top 1/5/10% precision, enrichment, captured positives, ROC AUC secondary |
| Metric aggregation | Mean, median, standard deviation, worst split, and split count |
| Thresholding | Fixed top 1%, 5%, and 10% area thresholds |
| Predictors | Use v1 predictors first; no new predictors until evaluation works |
| Coordinates | Do not use raw `x`/`y` as model features |
| Model | Fixed Random Forest baseline |
| Calibration | No probability calibration in v2 |
| Feature scaling | Only if the selected model requires it; Random Forest normally does not |
| Final map | Train one final RF after evaluation using the frozen v2 recipe |
| Uncertainty map | No uncertainty map in v2 |
| Variability archive | Archive per-split metrics and aggregate variability CSVs |
| Claims language | "Prospectivity score" or "relative prospectivity ranking", not "probability of deposit" |

## 2. What V2 Builds

V2 creates this chain:

```text
Raw GIS data
  -> Python ROI mask for Northern Territory
  -> Python 500 m template raster
  -> Python predictor rasters
  -> Python label raster from known MVT points
  -> Python raster stack and leakage checks
  -> Python repeated spatial split masks
  -> Python stratified background samples per split
  -> Python fixed Random Forest evaluation across all accepted splits
  -> Python aggregate metrics
  -> Python final Random Forest model
  -> Python final prospectivity GeoTIFF
  -> Python top 1%, 5%, and 10% maps
  -> QGIS review
  -> Archive v2 run
```

The most important v2 rule:

```text
Use validation/holdout split models for evaluation.
Use one final model only for producing the screening map.
Do not treat the final map as holdout evidence.
```

## 3. Folder Layout

Use this active-run layout:

```text
data/
  raw/                  original downloads; do not edit
  interim/              extracted source files; do not edit unless re-extracting sources
  processed/
    roi/                NT boundary and mask
    vectors_3577/       clipped/reprojected vector files
    rasters_500m/       aligned predictor rasters
    labels/             MVT point and label rasters
    splits/             spatial split masks and split summaries
    models/             training samples, models, metrics
outputs/
  maps/                 final maps and top-k rasters
  tables/               reports and review tables
scripts/                active v2 scripts
archive/
  v1/                   archived first run
```

At the end of the run, archive v2:

```text
archive/v2/
  scripts/
  PROJECT_WORKFLOW_NT_MVT_500M_V2.md
  data/processed/
  outputs/
  README excerpt or run summary
```

## 4. Preserve V1 Code Where Possible

Most v1 scripts remain useful. Do not rewrite them just to make the project look different.

Copy these from `archive/v1/scripts/` and keep the logic unless the script-specific notes below say otherwise:

```text
00_config.py                         modify for v2 paths/constants
01_make_roi_and_template.py           preserve
02_process_continuous_rasters.py      preserve
03_process_vector_predictors.py       preserve for v2 first pass
04_check_raster_stack.py              extend with leakage checks
05_make_mvt_labels.py                 preserve, but record unique positive pixels
```

Replace the v1 single train/test model scripts with v2 evaluation scripts:

```text
06_make_spatial_splits.py
07_build_split_training_samples.py
08_evaluate_random_forest_splits.py
09_train_final_random_forest.py
10_predict_final_prospectivity.py
11_summarize_v2_outputs.py
```

## 5. Script Overview

Run from the project root:

```bash
python scripts/01_make_roi_and_template.py
python scripts/02_process_continuous_rasters.py
python scripts/03_process_vector_predictors.py
python scripts/04_check_raster_stack.py
python scripts/05_make_mvt_labels.py
python scripts/06_make_spatial_splits.py
python scripts/07_build_split_training_samples.py
python scripts/08_evaluate_random_forest_splits.py
python scripts/09_train_final_random_forest.py
python scripts/10_predict_final_prospectivity.py
python scripts/11_summarize_v2_outputs.py
```

Do not run Python from inside `scripts/`.

## 6. Script 00: Shared Configuration

Purpose:

- centralize paths;
- keep v2 decisions explicit;
- prevent accidental leakage;
- make the run reproducible.

Create or update:

```text
scripts/00_config.py
```

Code pattern:

```python
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

# V2 decisions.
BACKGROUND_PER_POSITIVE = 50
USE_SPATIALLY_STRATIFIED_BACKGROUND = True
USE_SPATIAL_BUFFER = False
BUFFER_DISTANCE_M = 0

TARGET_ACCEPTED_SPLITS = 10
MIN_ACCEPTED_SPLITS_FOR_NON_EXPLORATORY = 5

# Strict split rules.
STRICT_HOLDOUT_AREA = 0.10
STRICT_VALIDATION_AREA = 0.10
STRICT_MIN_HOLDOUT_POSITIVES = 5
STRICT_MIN_VALIDATION_POSITIVES = 5
STRICT_MIN_TRAIN_POSITIVES = 40

# Fallback rules chosen from the decision table suggestions.
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

# These predictors use 0 as a meaningful inside-NT value.
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
```

## 7. Scripts 01-03: Preserve V1 Raster Processing

These scripts should stay very close to v1:

```text
scripts/01_make_roi_and_template.py
scripts/02_process_continuous_rasters.py
scripts/03_process_vector_predictors.py
```

Why preserve them:

- the ROI is still NT;
- the CRS is still `EPSG:3577`;
- the pixel size is still 500 m;
- the v1 predictors are intentionally kept for v2;
- v2 focuses on evaluation, not new predictors.

Only update imports/path names if `00_config.py` changed.

Important preserved behavior:

```python
# Preserve this idea from v1:
# all continuous rasters are reprojected onto the exact NT mask/template grid.
destination[nt_mask != 1] = cfg.NODATA_FLOAT
```

```python
# Preserve this idea from v1:
# binary/categorical predictors use 0 as a valid value inside NT.
carbonate_raster[nt_mask != 1] = 0
lithology_raster[nt_mask != 1] = 0
```

Do not add new predictors in v2 until the split/evaluation framework works.

## 8. Script 04: Check Raster Stack And Leakage

Purpose:

- confirm every predictor matches the template;
- confirm forbidden leakage predictors are not configured;
- confirm the Lawley MVT map is not used as a training predictor;
- confirm no predictor name looks derived from MVT labels or occurrences.

Create or update:

```text
scripts/04_check_raster_stack.py
```

Add this leakage check to the preserved v1 stack-check script:

```python
def check_predictor_leakage(cfg):
    forbidden_terms = [
        "mvt_label",
        "mvt_labels",
        "mvt_points",
        "occurrence",
        "occurrences",
        "lawley",
        "prospectivitymodel",
        "prospectivity_model",
    ]

    problems = []
    for name, path in cfg.PREDICTOR_RASTERS.items():
        text = f"{name} {path}".lower()
        for term in forbidden_terms:
            if term in text:
                problems.append((name, path, term))

    if problems:
        detail = "\n".join(
            f"- {name}: {path} contains forbidden term '{term}'"
            for name, path, term in problems
        )
        raise ValueError(
            "Potential data leakage in predictor configuration:\n"
            f"{detail}\n"
            "Known MVT locations, MVT labels, and existing MVT prospectivity maps "
            "must not be predictors."
        )

    print("Leakage check: predictor names and paths passed.")
```

Call it before the alignment loop:

```python
check_predictor_leakage(cfg)
```

## 9. Script 05: Make MVT Labels

Use the v1 script with one reporting improvement.

Path:
```text
scripts/05_make_mvt_labels.py
```

Decision used:

```text
All Australian MVT points inside NT are positive labels.
Evaluation should count unique positive pixels, not duplicate points.
```

Add or preserve this reporting:

```python
positive_pixels = int(label.sum())
duplicate_point_count = len(points_nt) - positive_pixels

print("MVT rows inside NT:", len(points_nt))
print("Positive label pixels:", positive_pixels)
print("Point rows sharing already-positive pixels:", duplicate_point_count)
```

Important:

- labels are for training/evaluation only;
- do not create distance-to-MVT or occurrence-density predictors.

## 10. Script 06: Make Spatial Splits

Purpose:

- generate repeated spatial train/validation/holdout splits;
- use square validation and holdout blocks;
- select splits by geography, area, and label balance only;
- never select splits based on model performance.

Create:

```text
scripts/06_make_spatial_splits.py
```

Output:

```text
data/processed/splits/split_001_mask.tif
data/processed/splits/split_002_mask.tif
...
data/processed/splits/split_summary.csv
```

Split mask values:

```text
0 = outside NT or unused
1 = train
2 = validation
3 = holdout
```

Code snippet:

```python
import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


def load_config():
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    return cfg


cfg = load_config()
cfg.ensure_directories()


def block_slices(height, width, side, step):
    # Square blocks are generated in raster row/column space.
    for row0 in range(0, max(1, height - side + 1), step):
        for col0 in range(0, max(1, width - side + 1), step):
            yield row0, col0, row0 + side, col0 + side


def make_block_mask(shape, window):
    row0, col0, row1, col1 = window
    block = np.zeros(shape, dtype=bool)
    block[row0:row1, col0:col1] = True
    return block


def summarize_region(name, region, valid, labels):
    valid_region = region & valid
    positives = int((labels[valid_region] == 1).sum())
    pixels = int(valid_region.sum())
    return {
        f"{name}_pixels": pixels,
        f"{name}_positives": positives,
    }


with rasterio.open(cfg.NT_MASK_500M) as src:
    nt_mask = src.read(1)
    profile = src.profile.copy()

with rasterio.open(cfg.MVT_LABELS_500M) as src:
    labels = src.read(1)

valid = nt_mask == 1
valid_pixels = int(valid.sum())
total_positives = int((labels[valid] == 1).sum())

if total_positives == 0:
    raise ValueError("No positive pixels found in label raster.")

height, width = valid.shape

# Strict target: one square block around 10% of valid pixels.
target_block_pixels = max(1, int(valid_pixels * cfg.STRICT_HOLDOUT_AREA))
side = int(round(math.sqrt(target_block_pixels)))
side = max(8, min(side, height, width))
step = max(1, side // 3)

print("Valid pixels:", valid_pixels)
print("Positive pixels:", total_positives)
print("Candidate square side in pixels:", side)
print("Candidate step in pixels:", step)

windows = list(block_slices(height, width, side, step))
candidate_blocks = []

for idx, window in enumerate(windows):
    block = make_block_mask(valid.shape, window)
    block_valid = block & valid
    area_share = block_valid.sum() / valid_pixels
    positives = int((labels[block_valid] == 1).sum())

    # Candidate area is measured by valid pixels inside the ROI.
    # Raw square area is not used because NT has an irregular boundary.
    if area_share == 0:
        continue

    candidate_blocks.append(
        {
            "candidate_id": idx,
            "window": window,
            "area_share": float(area_share),
            "positives": positives,
        }
    )

accepted = []
split_id = 1

for holdout in candidate_blocks:
    holdout_block = make_block_mask(valid.shape, holdout["window"]) & valid

    strict_holdout_ok = (
        abs(holdout["area_share"] - cfg.STRICT_HOLDOUT_AREA) <= 0.03
        and holdout["positives"] >= cfg.STRICT_MIN_HOLDOUT_POSITIVES
    )
    fallback_holdout_ok = (
        cfg.FALLBACK_AREA_MIN <= holdout["area_share"] <= cfg.FALLBACK_AREA_MAX
        and holdout["positives"] >= cfg.FALLBACK_MIN_POSITIVES
    )
    if not (strict_holdout_ok or fallback_holdout_ok):
        continue

    for validation in candidate_blocks:
        if validation["candidate_id"] == holdout["candidate_id"]:
            continue

        validation_block = make_block_mask(valid.shape, validation["window"]) & valid

        # V2 decision: validation and holdout cannot overlap.
        if np.any(validation_block & holdout_block):
            continue

        strict_validation_ok = (
            abs(validation["area_share"] - cfg.STRICT_VALIDATION_AREA) <= 0.03
            and validation["positives"] >= cfg.STRICT_MIN_VALIDATION_POSITIVES
        )
        fallback_validation_ok = (
            cfg.FALLBACK_AREA_MIN <= validation["area_share"] <= cfg.FALLBACK_AREA_MAX
            and validation["positives"] >= cfg.FALLBACK_MIN_POSITIVES
        )
        if not (strict_validation_ok or fallback_validation_ok):
            continue

        train_region = valid & ~validation_block & ~holdout_block
        train_positives = int((labels[train_region] == 1).sum())
        if train_positives < cfg.STRICT_MIN_TRAIN_POSITIVES:
            continue

        split_mask = np.zeros(valid.shape, dtype="uint8")
        split_mask[train_region] = 1
        split_mask[validation_block] = 2
        split_mask[holdout_block] = 3

        split_name = f"{cfg.SPLIT_MASK_PREFIX}_{split_id:03d}_mask.tif"
        split_path = cfg.SPLITS_DIR / split_name

        out_profile = profile.copy()
        out_profile.update(dtype="uint8", nodata=0, count=1, compress="lzw")
        with rasterio.open(split_path, "w", **out_profile) as dst:
            dst.write(split_mask, 1)

        row = {
            "split_id": split_id,
            "split_mask": str(split_path),
            "holdout_candidate_id": holdout["candidate_id"],
            "validation_candidate_id": validation["candidate_id"],
            "rule_type": "strict_or_fallback",
            "uses_buffer": False,
            "buffer_distance_m": 0,
        }
        row.update(summarize_region("train", split_mask == 1, valid, labels))
        row.update(summarize_region("validation", split_mask == 2, valid, labels))
        row.update(summarize_region("holdout", split_mask == 3, valid, labels))
        accepted.append(row)

        print("Accepted split:", split_id)
        split_id += 1

        if len(accepted) >= cfg.TARGET_ACCEPTED_SPLITS:
            break

    if len(accepted) >= cfg.TARGET_ACCEPTED_SPLITS:
        break

summary = pd.DataFrame(accepted)
summary.to_csv(cfg.SPLIT_SUMMARY, index=False)
print("Wrote:", cfg.SPLIT_SUMMARY)
print("Accepted splits:", len(summary))

if len(summary) < cfg.MIN_ACCEPTED_SPLITS_FOR_NON_EXPLORATORY:
    print(
        "WARNING: fewer than",
        cfg.MIN_ACCEPTED_SPLITS_FOR_NON_EXPLORATORY,
        "splits accepted. Treat v2 evaluation as exploratory.",
    )
```

## 11. Script 07: Build Split Training Samples

Purpose:

- for each accepted split, sample training rows only from the training region;
- keep all positive training pixels;
- sample background pixels with spatial stratification;
- do not use validation or holdout pixels for training.

Create:

```text
scripts/07_build_split_training_samples.py
```

Output:

```text
data/processed/models/split_training_samples.csv
```

Code snippet:

```python
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


def load_config():
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    return cfg


cfg = load_config()
cfg.ensure_directories()


def read_predictor(name, path):
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
        nodata = src.nodata

    if nodata is not None and name not in cfg.ZERO_IS_VALID_PREDICTORS:
        arr[arr == nodata] = np.nan
    arr[~np.isfinite(arr)] = np.nan
    return arr


def spatial_block_ids(rows, cols, block_size_pixels=100):
    # Background stratification: group pixels into coarse raster blocks.
    # At 500 m pixels, 100 pixels is a 50 km block.
    return (rows // block_size_pixels).astype(str) + "_" + (cols // block_size_pixels).astype(str)


def stratified_background_sample(candidate_idx, rows, cols, n_needed, seed):
    rng = np.random.default_rng(seed)
    if n_needed >= len(candidate_idx):
        return candidate_idx

    block_ids = spatial_block_ids(rows[candidate_idx], cols[candidate_idx])
    groups = pd.Series(candidate_idx).groupby(block_ids)
    group_values = [group.to_numpy() for _, group in groups]

    selected = []
    group_order = np.arange(len(group_values))

    # Round-robin across spatial groups so one large area does not dominate.
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


split_summary = pd.read_csv(cfg.SPLIT_SUMMARY)

with rasterio.open(cfg.NT_MASK_500M) as src:
    mask = src.read(1)
    transform = src.transform

with rasterio.open(cfg.MVT_LABELS_500M) as src:
    labels = src.read(1)

valid_mask = mask == 1
rows, cols = np.where(valid_mask)
flat_labels = labels[valid_mask].astype("uint8")

feature_values = {}
usable = np.ones(flat_labels.shape[0], dtype=bool)
for name, path in cfg.PREDICTOR_RASTERS.items():
    print("Reading predictor:", name)
    arr = read_predictor(name, path)
    values = arr[valid_mask]
    feature_values[name] = values
    usable &= ~np.isnan(values)

all_records = []

for split in split_summary.itertuples():
    with rasterio.open(split.split_mask) as src:
        split_mask = src.read(1)

    train_flat = split_mask[valid_mask] == 1
    positive_idx = np.where(train_flat & usable & (flat_labels == 1))[0]
    background_idx = np.where(train_flat & usable & (flat_labels == 0))[0]

    n_background = min(
        len(background_idx),
        len(positive_idx) * cfg.BACKGROUND_PER_POSITIVE,
    )
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
    table["label"] = flat_labels[selected]
    table["x"] = xs
    table["y"] = ys
    table["row"] = rows[selected]
    table["col"] = cols[selected]
    table["sample_role"] = np.where(table["label"] == 1, "positive", "background")

    print(
        "Split",
        split.split_id,
        "training positives:",
        int(table["label"].sum()),
        "background:",
        int((table["label"] == 0).sum()),
    )
    all_records.append(table)

training_samples = pd.concat(all_records, ignore_index=True)
training_samples.to_csv(cfg.SPLIT_TRAINING_SAMPLES, index=False)
print("Wrote:", cfg.SPLIT_TRAINING_SAMPLES)
```

## 12. Script 08: Evaluate Random Forest Across Splits

Purpose:

- train one fixed Random Forest per split;
- use training samples only from the training region;
- evaluate on all usable validation and holdout pixels;
- report top 1%, 5%, and 10% metrics;
- aggregate mean, median, standard deviation, worst split, and split count.

Create:

```text
scripts/08_evaluate_random_forest_splits.py
```

Outputs:

```text
data/processed/models/metrics_by_split.csv
data/processed/models/aggregate_metrics.csv
```

Code snippet:

```python
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
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    return cfg


cfg = load_config()
feature_names = list(cfg.PREDICTOR_RASTERS.keys())


def read_predictor(name, path):
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
        nodata = src.nodata
    if nodata is not None and name not in cfg.ZERO_IS_VALID_PREDICTORS:
        arr[arr == nodata] = np.nan
    arr[~np.isfinite(arr)] = np.nan
    return arr


def top_k_metrics(scores, labels, pct):
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


def score_region(model, split_mask, region_value, valid_mask, usable_flat, feature_values, labels):
    region = (split_mask[valid_mask] == region_value) & usable_flat
    y = labels[valid_mask][region].astype("uint8")
    X = pd.DataFrame(
        {name: values[region] for name, values in feature_values.items()},
        columns=feature_names,
    )
    prob = model.predict_proba(X)[:, 1]
    return prob, y


split_summary = pd.read_csv(cfg.SPLIT_SUMMARY)
training_samples = pd.read_csv(cfg.SPLIT_TRAINING_SAMPLES)

with rasterio.open(cfg.NT_MASK_500M) as src:
    valid_mask = src.read(1) == 1

with rasterio.open(cfg.MVT_LABELS_500M) as src:
    labels = src.read(1)

feature_values = {}
usable_flat = np.ones(int(valid_mask.sum()), dtype=bool)
for name, path in cfg.PREDICTOR_RASTERS.items():
    arr = read_predictor(name, path)
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
        )

        if len(np.unique(y)) < 2:
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

metric_cols = [
    col
    for col in metrics.columns
    if col not in {"split_id", "region"}
]

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
```

## 13. Script 09: Train Final Random Forest

Purpose:

- train one final Random Forest for map production;
- use the fixed v2 recipe;
- use all eligible NT positive pixels;
- use spatially stratified background sampling across the full valid NT area;
- do not call this final map a holdout evaluation.

Create:

```text
scripts/09_train_final_random_forest.py
```

Outputs:

```text
data/processed/models/final_training_table.csv
data/processed/models/final_random_forest_mvt.joblib
data/processed/models/final_feature_importance.csv
```

Code note:

```python
# Reuse the same read_predictor and stratified_background_sample functions
# from scripts/07_build_split_training_samples.py.
```

Core training pattern:

```python
model = RandomForestClassifier(
    n_estimators=500,
    min_samples_leaf=2,
    class_weight="balanced",
    random_state=cfg.RANDOM_STATE,
    n_jobs=-1,
)

model.fit(X_train, y_train)
```

Reporting requirement:

```python
print("IMPORTANT: this final model is for screening-map production.")
print("It is not the source of holdout performance evidence.")
print("Use metrics_by_split.csv and aggregate_metrics.csv for evaluation.")
```

## 14. Script 10: Predict Final Prospectivity

Purpose:

- apply the final RF model to all usable NT pixels;
- create a final prospectivity-score map;
- preserve `-9999` NoData outside NT and where predictors are missing.

Create:

```text
scripts/10_predict_final_prospectivity.py
```

Output:

```text
outputs/maps/mvt_prospectivity_rf_v2_500m.tif
```

Use the v1 prediction structure, but update model/output paths:

```python
model = joblib.load(cfg.FINAL_RANDOM_FOREST_MODEL)
out_path = cfg.FINAL_PROSPECTIVITY_MAP
```

Important wording:

```text
The map values are relative prospectivity scores.
They are not calibrated probabilities of deposit presence.
```

## 15. Script 11: Summarize V2 Outputs

Purpose:

- summarize final map scores;
- make fixed top 1%, 5%, and 10% maps;
- write a v2 review report;
- include aggregate split metrics;
- record limitations.

Create:

```text
scripts/11_summarize_v2_outputs.py
```

Outputs:

```text
outputs/tables/final_score_summary_v2.csv
outputs/maps/mvt_top_1_percent_rf_v2_500m.tif
outputs/maps/mvt_top_5_percent_rf_v2_500m.tif
outputs/maps/mvt_top_10_percent_rf_v2_500m.tif
outputs/tables/v2_model_review.txt
```

Code snippet:

```python
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


def load_config():
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    return cfg


cfg = load_config()
cfg.ensure_directories()

with rasterio.open(cfg.FINAL_PROSPECTIVITY_MAP) as src:
    scores = src.read(1)
    profile = src.profile.copy()
    nodata = src.nodata

valid = np.isfinite(scores)
if nodata is not None:
    valid &= scores != nodata

valid_scores = scores[valid]
if valid_scores.size == 0:
    raise ValueError("Final prospectivity map contains no valid scores.")

summary = {
    "valid_pixels": int(valid_scores.size),
    "min": float(np.min(valid_scores)),
    "max": float(np.max(valid_scores)),
    "mean": float(np.mean(valid_scores)),
    "p50": float(np.percentile(valid_scores, 50)),
    "p90": float(np.percentile(valid_scores, 90)),
    "p95": float(np.percentile(valid_scores, 95)),
    "p99": float(np.percentile(valid_scores, 99)),
}

summary_path = cfg.TABLES_DIR / "final_score_summary_v2.csv"
pd.DataFrame([summary]).to_csv(summary_path, index=False)
print("Wrote:", summary_path)

profile.update(dtype="uint8", nodata=0, count=1, compress="lzw")

for pct in cfg.TOP_K_PCTS:
    threshold = float(np.percentile(valid_scores, 100 - pct))
    top = np.zeros(scores.shape, dtype="uint8")
    top[valid & (scores >= threshold)] = 1

    top_path = cfg.MAPS_DIR / f"mvt_top_{pct}_percent_rf_v2_500m.tif"
    with rasterio.open(top_path, "w", **profile) as dst:
        dst.write(top, 1)

    print(f"Top {pct}% threshold:", threshold)
    print("Wrote:", top_path)

aggregate_metrics = pd.read_csv(cfg.AGGREGATE_METRICS)

report_path = cfg.TABLES_DIR / "v2_model_review.txt"
with open(report_path, "w", encoding="utf-8") as f:
    f.write("Run: NT MVT v2 Random Forest baseline\n")
    f.write("Primary goal: scientific benchmark\n")
    f.write("Secondary output: screening prospectivity map\n")
    f.write("Pixel size: 500 m\n")
    f.write("CRS: EPSG:3577\n")
    f.write("Model: fixed Random Forest\n")
    f.write("Predictors: v1 predictor set\n")
    f.write("Coordinates used as predictors: no\n")
    f.write("Probability calibration: no\n")
    f.write("Spatial buffer: no\n")
    f.write("Background sampling: spatially stratified\n")
    f.write("\nImportant limitation:\n")
    f.write("- Final map scores are relative prospectivity rankings, not deposit probabilities.\n")
    f.write("- No uncertainty map was produced in v2.\n")
    f.write("- Holdout evidence comes from repeated split evaluation, not the final map itself.\n")
    f.write("\nAggregate metrics:\n")
    f.write(aggregate_metrics.to_string(index=False))
    f.write("\n")

print("Wrote:", report_path)
```

## 16. QGIS Review

Load these layers:

```text
data/processed/roi/nt_boundary_3577_dissolved.gpkg
data/processed/roi/nt_mask_500m.tif
data/processed/labels/mvt_points_nt_3577.gpkg
outputs/maps/mvt_prospectivity_rf_v2_500m.tif
outputs/maps/mvt_top_1_percent_rf_v2_500m.tif
outputs/maps/mvt_top_5_percent_rf_v2_500m.tif
outputs/maps/mvt_top_10_percent_rf_v2_500m.tif
data/processed/splits/split_001_mask.tif
data/processed/rasters_500m/carbonate_host_500m.tif
data/processed/rasters_500m/dist_faults_500m.tif
```

Check:

- final map aligns with NT;
- no values appear outside NT;
- split masks make geographic sense;
- validation and holdout blocks do not overlap;
- known MVT points are visible;
- high-score zones are not only raster edges or NoData boundaries;
- top 1/5/10% zones are geologically plausible.

## 17. Reporting Rules

Use this wording:

```text
The model produces a relative MVT prospectivity score.
```

Do not use this wording:

```text
The model predicts the probability of an MVT deposit.
```

Report v2 performance from:

```text
data/processed/models/metrics_by_split.csv
data/processed/models/aggregate_metrics.csv
```

Report the final screening map from:

```text
outputs/maps/mvt_prospectivity_rf_v2_500m.tif
```

Keep these separate:

```text
Repeated split models = evaluation evidence.
Final model = screening map production.
```

## 18. Archive V2

After v2 is complete and reviewed, archive it:

```text
archive/v2/
  scripts/
  PROJECT_WORKFLOW_NT_MVT_500M_V2.md
  data/processed/
  outputs/
```

Also add a dated README excerpt with:

- run date and time;
- accepted split count;
- whether the run is exploratory or non-exploratory;
- aggregate holdout PR-AUC;
- top 1/5/10% holdout capture;
- major limitations;
- statement that scores are relative prospectivity rankings.

## 19. Full V2 Run Order

```bash
python scripts/01_make_roi_and_template.py
python scripts/02_process_continuous_rasters.py
python scripts/03_process_vector_predictors.py
python scripts/04_check_raster_stack.py
python scripts/05_make_mvt_labels.py
python scripts/06_make_spatial_splits.py
python scripts/07_build_split_training_samples.py
python scripts/08_evaluate_random_forest_splits.py
python scripts/09_train_final_random_forest.py
python scripts/10_predict_final_prospectivity.py
python scripts/11_summarize_v2_outputs.py
```

Stop if any script fails. Do not skip `04_check_raster_stack.py` or `06_make_spatial_splits.py`.

## 20. V2 Completion Criteria

V2 is complete only if:

1. ROI/template exists.
2. Predictor rasters align with the template.
3. Leakage check passes.
4. MVT label raster exists.
5. Split masks exist.
6. Split summary records accepted split count.
7. If accepted splits are fewer than 5, the run is labeled exploratory.
8. Training samples are built only from training regions.
9. Per-split metrics exist.
10. Aggregate metrics exist with mean, median, standard deviation, worst split, and split count.
11. Final RF model exists.
12. Final prospectivity map exists.
13. Top 1%, 5%, and 10% maps exist.
14. QGIS review is performed.
15. README/archive summary states limitations clearly.

## 21. What Not To Change Yet

Do not add these in v2 unless the evaluation framework already works:

- new geology indicators;
- distance to lithological contacts;
- fault density;
- contact density;
- geophysical texture layers;
- gradient boosting;
- CNNs;
- probability calibration;
- uncertainty maps.

Those are valid future improvements, but adding them now would make it harder to know whether v2 improved because of better science or because of changed features/models.
