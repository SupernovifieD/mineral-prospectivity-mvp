# Python Workflow: Northern Territory MVT Prospectivity at 500 m

This document rewrites the project workflow as a Python-first process.

The goal is to build a reproducible mineral prospectivity workflow for Mississippi Valley-type, or MVT, zinc-lead deposits in the Northern Territory of Australia. The processing target is a set of aligned 500 m GeoTIFF rasters in `EPSG:3577`, followed by a simple machine learning model and a prospectivity map.

QGIS is still useful for visual checking, but this guide does the real processing in Python.

## 1. What You Are Building

You are building this chain:

```text
Raw GIS data
  -> Python ROI mask for Northern Territory
  -> Python 500 m template raster
  -> Python predictor rasters
  -> Python label raster from known MVT points
  -> Python training table
  -> Python Random Forest model
  -> Python prospectivity GeoTIFF
  -> QGIS review and map inspection
```

The most important rule:

```text
Every predictor raster must have the same CRS, extent, pixel size, transform, width, and height.
```

If rasters do not align exactly, the model will mix values from different places.

## 2. Project Data Found In This Folder

Important local files:

| Purpose | Path | Notes |
| --- | --- | --- |
| Australian boundary file | `data/raw/gadm41_AUS_shp/gadm41_AUS_1.shp` | Contains `Northern Territory` in field `NAME_1`. |
| Geology polygons | `data/interim/[Geological Data] Geology shapefiles for the United States and Australia/Geology_Australia/Geology_Australia.shp` | Useful field: `CMMI_Class`. |
| Fault lines | `data/interim/[Geological Data] Shapefiles of faults for the United States, Canada, and Australia/GeologyFaults_Australia/GeologyFaults_Australia.shp` | Used for distance-to-fault raster. |
| MVT and CD occurrences | `data/interim/[Geological Data] Basin-hosted (CD:SEDEX and MVT) Zn-Pb deposits and prospects for the United States, Canada, and Australia/GeologyMineralOccurrences_USCanada_Australia.csv` | Use `encoding="latin1"` in Python. |
| Gravity rasters | `data/interim/[Geophysical Data] Gravity and related derivative GeoTIFF grids and data for Australia/` | Continuous predictors. |
| Magnetic rasters | `data/interim/[Geophysical Data] Magnetic and related derivative GeoTIFF grids and data for Australia/` | Continuous predictors and source point layers. |
| Moho raster | `data/interim/[Geophysical Data] Depth to Moho GeoTIFF grids for the United States, Canada, and Australia/GeophysicsMoho_Australia/GeophysicsMoho_Australia.tif` | Continuous predictor. |
| LAB raster | `data/interim/[Geophysical Data] Depth to lithosphere-asthenosphere boundary GeoTIFF grids for the United States, Canada, and Australia/GeophysicsLAB_Australia/GeophysicsLAB_Australia.tif` | Continuous predictor. |
| Existing Lawley MVT model | `data/interim/[Prospectivity Models] Prospectivity models - clastic-dominated (CD) and Mississippi Valley-type (MVT) GeoTIFF grids for the United States, Canada, and Australia/ProspectivityModel_MVT_Australia/Aus_Lawleyetal_MVTModel.tif` | Use only for comparison, not training. |

Important facts already checked:

- The boundary file is in `EPSG:4326`.
- The geology and faults are in `EPSG:4326`.
- Many source rasters are in `EPSG:4326`.
- The project raster CRS should be `EPSG:3577`, also called `GDA94 / Australian Albers`.
- `EPSG:3577` uses metres, so a 500 m pixel size is meaningful.
- About 70 MVT occurrence records fall inside the Northern Territory boundary.

## 3. Beginner Concepts

### 3.1 CRS

CRS means coordinate reference system.

`EPSG:4326` stores coordinates as longitude and latitude degrees.

`EPSG:3577` stores coordinates in metres across Australia.

Because the project uses 500 m pixels and distance-to-fault rasters, use `EPSG:3577` for processing.

### 3.2 Raster

A raster is a grid. Each pixel stores one value.

Example:

```text
carbonate_host_500m.tif
  1 = carbonate host rock exists in this pixel
  0 = carbonate host rock does not exist in this pixel

dist_faults_500m.tif
  0 = pixel is on a fault
  5000 = pixel is 5000 m from nearest fault

gravity_500m.tif
  numeric gravity value
```

### 3.3 Template Raster

The template raster defines the exact grid:

- CRS
- pixel size
- extent
- transform
- width
- height

Every predictor raster is forced onto this template.

### 3.4 Predictor

A predictor is an input feature used by the model.

Examples:

- carbonate host rock
- distance to fault
- gravity value
- magnetic value
- Moho depth

### 3.5 Label

A label is the known answer used for training.

For this project:

```text
1 = known MVT occurrence/deposit pixel
0 = background pixel
```

Important: background does not mean proven barren. It only means there is no known MVT point in that pixel.

### 3.6 Data Leakage

Data leakage means accidentally giving the answer to the model.

Do not use these as predictors:

- distance to known MVT occurrences
- the existing Lawley MVT prospectivity model
- any raster made from the occurrence labels

Use known MVT points only as labels.

## 4. Recommended Folder Layout

Use this layout for derived files:

```text
data/
  raw/                  original downloads
  interim/              extracted source files
  processed/
    roi/                Northern Territory boundary and mask
    vectors_3577/       clipped/reprojected vector files
    rasters_500m/       final predictor rasters
    labels/             label rasters and label points
    models/             tables, trained models, metrics
outputs/
  maps/                 prospectivity maps
  tables/               review tables
scripts/                Python scripts
```

Do not edit files in `data/raw/`. Treat them as original source data.

## 5. Python Environment Setup

Your current `.venv` already has:

- `geopandas`
- `numpy`
- `pandas`
- `pyogrio`
- `pyproj`
- `shapely`
- `rasterio`
- `scipy`
- `scikit-learn`
- `joblib`
- `matplotlib`

Activate the environment:

```bash
source .venv/bin/activate
```

## 6. Script Overview

Create these scripts in order:

```text
scripts/00_config.py
scripts/01_make_roi_and_template.py
scripts/02_process_continuous_rasters.py
scripts/03_process_vector_predictors.py
scripts/04_check_raster_stack.py
scripts/05_make_mvt_labels.py
scripts/06_build_training_table.py
scripts/07_train_random_forest.py
scripts/08_predict_prospectivity.py
scripts/09_summarize_outputs.py
```

Run them from the project root:

```bash
python scripts/01_make_roi_and_template.py
```

Do not run Python from inside the `scripts/` folder. Run from the project root so relative paths work.

<!-- Implementation note: the actual scripts in this repository include two practical improvements over the first draft shown below. The vector script uses a Northern Territory bounding-box filter before rasterizing large source layers, and the training/prediction scripts keep `0` as a valid value for binary and categorical rasters inside the NT mask. -->

## 7. Script 00: Shared Configuration

Purpose:

- Put all important paths and constants in one file.
- Avoid typing long file paths repeatedly.
- Make the workflow easier to edit later.

Create:

```text
scripts/00_config.py
```

Code:

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
MODELS_DIR = PROCESSED / "models"
MAPS_DIR = OUTPUTS / "maps"
TABLES_DIR = OUTPUTS / "tables"

PROJECT_CRS = "EPSG:3577"
SOURCE_CRS = "EPSG:4326"
PIXEL_SIZE = 500
NODATA_FLOAT = -9999.0

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


def ensure_directories():
    for path in [
        ROI_DIR,
        VECTORS_3577_DIR,
        RASTERS_500M_DIR,
        LABELS_DIR,
        MODELS_DIR,
        MAPS_DIR,
        TABLES_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)
```

What this script does:

- It does not process data.
- It only stores paths and constants.
- Other scripts will import it.

## 8. Script 01: Make ROI Boundary And 500 m Template

Purpose:

- Read the Australian boundary file.
- Select Northern Territory.
- Reproject it to `EPSG:3577`.
- Save it as a GeoPackage.
- Create the 500 m template mask raster.

Create:

```text
scripts/01_make_roi_and_template.py
```

Code:

```python
import importlib.util
import math
from pathlib import Path

import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import mapping
from shapely.validation import make_valid


def load_config():
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


cfg = load_config()
cfg.ensure_directories()

boundary = gpd.read_file(cfg.AUSTRALIA_BOUNDARY)
print("Boundary CRS:", boundary.crs)
print("Boundary rows:", len(boundary))

nt = boundary[boundary["NAME_1"] == "Northern Territory"].copy()
if nt.empty:
    raise ValueError("Could not find Northern Territory in NAME_1 field.")

# Fix invalid geometries before dissolving and rasterizing.
nt["geometry"] = nt.geometry.apply(make_valid)

# Reproject from longitude/latitude to Australian Albers metres.
nt_3577 = nt.to_crs(cfg.PROJECT_CRS)

# Dissolve into one geometry.
nt_3577["dissolve_id"] = 1
nt_3577 = nt_3577.dissolve(by="dissolve_id").reset_index(drop=True)

boundary_out = cfg.ROI_DIR / "nt_boundary_3577_dissolved.gpkg"
nt_3577.to_file(boundary_out, driver="GPKG", layer="nt_boundary_3577_dissolved")
print("Wrote:", boundary_out)

# Build a clean grid aligned to 500 m coordinates.
minx, miny, maxx, maxy = nt_3577.total_bounds

left = math.floor(minx / cfg.PIXEL_SIZE) * cfg.PIXEL_SIZE
bottom = math.floor(miny / cfg.PIXEL_SIZE) * cfg.PIXEL_SIZE
right = math.ceil(maxx / cfg.PIXEL_SIZE) * cfg.PIXEL_SIZE
top = math.ceil(maxy / cfg.PIXEL_SIZE) * cfg.PIXEL_SIZE

width = int(round((right - left) / cfg.PIXEL_SIZE))
height = int(round((top - bottom) / cfg.PIXEL_SIZE))
transform = from_origin(left, top, cfg.PIXEL_SIZE, cfg.PIXEL_SIZE)

print("Template bounds:", left, bottom, right, top)
print("Template width/height:", width, height)
print("Template pixel size:", cfg.PIXEL_SIZE)

shapes = [(mapping(geom), 1) for geom in nt_3577.geometry]

mask = rasterize(
    shapes,
    out_shape=(height, width),
    transform=transform,
    fill=0,
    dtype="uint8",
)

profile = {
    "driver": "GTiff",
    "height": height,
    "width": width,
    "count": 1,
    "dtype": "uint8",
    "crs": cfg.PROJECT_CRS,
    "transform": transform,
    "nodata": 0,
    "compress": "lzw",
}

mask_out = cfg.ROI_DIR / "nt_mask_500m.tif"
with rasterio.open(mask_out, "w", **profile) as dst:
    dst.write(mask, 1)

print("Wrote:", mask_out)
print("Inside-NT pixels:", int(mask.sum()))
```

Run:

```bash
python scripts/01_make_roi_and_template.py
```

Expected outputs:

```text
data/processed/roi/nt_boundary_3577_dissolved.gpkg
data/processed/roi/nt_mask_500m.tif
```

What happened:

- Python selected Northern Territory from the Australian boundary file.
- Python changed the geometry from degrees to metres.
- Python made a 500 m grid.
- Python burned the NT polygon into that grid.

Open `nt_mask_500m.tif` in QGIS and check:

- CRS is `EPSG:3577`.
- Pixel size is `500, -500`.
- Values are `1` inside NT and NoData or `0` outside.

## 9. Script 02: Process Continuous Raster Predictors

Purpose:

- Read source GeoTIFF rasters.
- Reproject them to `EPSG:3577`.
- Resample them to the exact 500 m template.
- Mask outside Northern Territory.
- Write final aligned predictor rasters.

Examples of continuous rasters:

- Moho depth
- LAB depth
- gravity
- magnetic RTP
- shape index

Continuous means the value is numeric and can vary smoothly.

Create:

```text
scripts/02_process_continuous_rasters.py
```

Code:

```python
import importlib.util
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject


def load_config():
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


cfg = load_config()
cfg.ensure_directories()

mask_path = cfg.ROI_DIR / "nt_mask_500m.tif"

with rasterio.open(mask_path) as mask_src:
    nt_mask = mask_src.read(1)
    template_profile = mask_src.profile.copy()
    template_transform = mask_src.transform
    template_crs = mask_src.crs
    template_height = mask_src.height
    template_width = mask_src.width


def process_one_raster(name, src_path):
    out_path = cfg.RASTERS_500M_DIR / f"{name}_500m.tif"
    print("Processing:", name)
    print("  Input:", src_path)
    print("  Output:", out_path)

    if not src_path.exists():
        print("  WARNING: missing input, skipped")
        return

    destination = np.full(
        (template_height, template_width),
        cfg.NODATA_FLOAT,
        dtype="float32",
    )

    with rasterio.open(src_path) as src:
        source_crs = src.crs
        if source_crs is None:
            source_crs = cfg.SOURCE_CRS
            print("  Source CRS missing, assuming:", source_crs)

        reproject(
            source=rasterio.band(src, 1),
            destination=destination,
            src_transform=src.transform,
            src_crs=source_crs,
            src_nodata=src.nodata,
            dst_transform=template_transform,
            dst_crs=template_crs,
            dst_nodata=cfg.NODATA_FLOAT,
            resampling=Resampling.bilinear,
        )

    # Force outside Northern Territory to NoData.
    destination[nt_mask != 1] = cfg.NODATA_FLOAT

    profile = template_profile.copy()
    profile.update(
        dtype="float32",
        nodata=cfg.NODATA_FLOAT,
        count=1,
        compress="lzw",
    )

    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(destination, 1)

    valid = destination[destination != cfg.NODATA_FLOAT]
    print("  Valid pixels:", valid.size)
    if valid.size:
        print("  Min/max:", float(np.nanmin(valid)), float(np.nanmax(valid)))


for raster_name, raster_path in cfg.CONTINUOUS_RASTERS.items():
    process_one_raster(raster_name, raster_path)
```

Run:

```bash
python scripts/02_process_continuous_rasters.py
```

Expected outputs include:

```text
data/processed/rasters_500m/moho_depth_500m.tif
data/processed/rasters_500m/lab_depth_500m.tif
data/processed/rasters_500m/gravity_500m.tif
data/processed/rasters_500m/gravity_hgm_500m.tif
data/processed/rasters_500m/mag_rtp_500m.tif
data/processed/rasters_500m/mag_hgm_500m.tif
data/processed/rasters_500m/shape_index_500m.tif
```

What happened:

- `rasterio.warp.reproject` did what QGIS/GDAL `Clip raster by mask layer` does.
- The source raster was reprojected from degrees to metres.
- The output was forced onto your template grid.
- Outside Northern Territory was set to NoData.

## 10. Script 03: Process Vector Predictors

Purpose:

- Make a carbonate host raster from geology polygons.
- Make a lithology code raster from geology polygons.
- Make a distance-to-fault raster from fault lines.

Create:

```text
scripts/03_process_vector_predictors.py
```

Code:

```python
import importlib.util
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from scipy.ndimage import distance_transform_edt
from shapely.geometry import mapping
from shapely.validation import make_valid


def load_config():
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


cfg = load_config()
cfg.ensure_directories()

mask_path = cfg.ROI_DIR / "nt_mask_500m.tif"
boundary_path = cfg.ROI_DIR / "nt_boundary_3577_dissolved.gpkg"

with rasterio.open(mask_path) as mask_src:
    nt_mask = mask_src.read(1)
    profile = mask_src.profile.copy()
    transform = mask_src.transform
    out_shape = (mask_src.height, mask_src.width)

nt_boundary = gpd.read_file(boundary_path).to_crs(cfg.PROJECT_CRS)


def clean_project_clip(path):
    gdf = gpd.read_file(path)
    print("Read:", path)
    print("  Rows:", len(gdf))
    print("  CRS:", gdf.crs)

    gdf = gdf[gdf.geometry.notna()].copy()
    gdf["geometry"] = gdf.geometry.apply(make_valid)
    gdf = gdf[~gdf.geometry.is_empty].copy()
    gdf = gdf.to_crs(cfg.PROJECT_CRS)
    clipped = gpd.clip(gdf, nt_boundary)
    clipped = clipped[clipped.geometry.notna()].copy()
    clipped = clipped[~clipped.geometry.is_empty].copy()
    print("  Rows after NT clip:", len(clipped))
    return clipped


def write_raster(path, array, dtype, nodata):
    out_profile = profile.copy()
    out_profile.update(dtype=dtype, nodata=nodata, count=1, compress="lzw")
    with rasterio.open(path, "w", **out_profile) as dst:
        dst.write(array.astype(dtype), 1)
    print("Wrote:", path)


def rasterize_geometries(gdf, value, dtype="uint8", fill=0):
    shapes = [
        (mapping(geom), value)
        for geom in gdf.geometry
        if geom is not None and not geom.is_empty
    ]
    return rasterize(
        shapes,
        out_shape=out_shape,
        transform=transform,
        fill=fill,
        dtype=dtype,
        all_touched=True,
    )


# 1. Geology rasters
geology = clean_project_clip(cfg.GEOLOGY)
geology_out = cfg.VECTORS_3577_DIR / "geology_nt_3577.gpkg"
geology.to_file(geology_out, driver="GPKG", layer="geology_nt_3577")
print("Wrote:", geology_out)

carbonate = geology[geology["CMMI_Class"] == "Sedimentary_Chemical_Carbonate"].copy()
carbonate_raster = rasterize_geometries(carbonate, value=1, dtype="uint8", fill=0)
carbonate_raster[nt_mask != 1] = 0
write_raster(cfg.RASTERS_500M_DIR / "carbonate_host_500m.tif", carbonate_raster, "uint8", 0)


def lithology_id(value):
    value = str(value)
    if value == "Sedimentary_Chemical_Carbonate":
        return 1
    if value == "Sedimentary_Chemical":
        return 2
    if value == "Sedimentary_Chemical_Evaporite":
        return 3
    if value == "Sedimentary_Siliciclastic":
        return 4
    if value == "Other_Unconsolidated":
        return 5
    if value.startswith("Igneous"):
        return 6
    if value.startswith("Metamorphic"):
        return 7
    return 99


geology["class_id"] = geology["CMMI_Class"].apply(lithology_id).astype("int16")

lithology_shapes = [
    (mapping(row.geometry), int(row.class_id))
    for row in geology.itertuples()
    if row.geometry is not None and not row.geometry.is_empty
]

lithology_raster = rasterize(
    lithology_shapes,
    out_shape=out_shape,
    transform=transform,
    fill=0,
    dtype="int16",
    all_touched=True,
)
lithology_raster[nt_mask != 1] = 0
write_raster(cfg.RASTERS_500M_DIR / "lithology_code_500m.tif", lithology_raster, "int16", 0)

lookup = pd.DataFrame(
    [
        (0, "NoData or outside NT"),
        (1, "Sedimentary_Chemical_Carbonate"),
        (2, "Sedimentary_Chemical"),
        (3, "Sedimentary_Chemical_Evaporite"),
        (4, "Sedimentary_Siliciclastic"),
        (5, "Other_Unconsolidated"),
        (6, "Igneous"),
        (7, "Metamorphic"),
        (99, "Other or unknown"),
    ],
    columns=["class_id", "meaning"],
)
lookup_path = cfg.RASTERS_500M_DIR / "lithology_code_lookup.csv"
lookup.to_csv(lookup_path, index=False)
print("Wrote:", lookup_path)


# 2. Fault distance raster
faults = clean_project_clip(cfg.FAULTS)
faults_out = cfg.VECTORS_3577_DIR / "faults_nt_3577.gpkg"
faults.to_file(faults_out, driver="GPKG", layer="faults_nt_3577")
print("Wrote:", faults_out)

fault_binary = rasterize_geometries(faults, value=1, dtype="uint8", fill=0)
fault_binary[nt_mask != 1] = 0
write_raster(cfg.RASTERS_500M_DIR / "faults_binary_500m.tif", fault_binary, "uint8", 0)

if fault_binary.max() == 0:
    raise ValueError("No fault pixels were rasterized. Check the fault layer and ROI.")

# distance_transform_edt calculates distance from nonzero cells to nearest zero cell.
# fault_binary == 0 means non-fault pixels are True and fault pixels are False.
distance = distance_transform_edt(
    fault_binary == 0,
    sampling=(cfg.PIXEL_SIZE, cfg.PIXEL_SIZE),
).astype("float32")

distance[nt_mask != 1] = cfg.NODATA_FLOAT
write_raster(cfg.RASTERS_500M_DIR / "dist_faults_500m.tif", distance, "float32", cfg.NODATA_FLOAT)
```

Run:

```bash
python scripts/03_process_vector_predictors.py
```

Expected outputs:

```text
data/processed/rasters_500m/carbonate_host_500m.tif
data/processed/rasters_500m/lithology_code_500m.tif
data/processed/rasters_500m/lithology_code_lookup.csv
data/processed/rasters_500m/faults_binary_500m.tif
data/processed/rasters_500m/dist_faults_500m.tif
```

What happened:

- Python clipped vector layers to Northern Territory.
- Python rasterized polygons and lines onto the 500 m template.
- `all_touched=True` means a feature is written to every pixel it touches, not only pixels whose centers it crosses.
- Python converted fault lines to a distance raster in metres.

<!-- Implemented script note: `scripts/03_process_vector_predictors.py` now bbox-loads geology and faults before rasterization because the full Australia geology shapefile is large. The final rasters are still masked by `nt_mask_500m.tif`, so pixels outside Northern Territory are removed from the model grid. Existing geology outputs are skipped on rerun unless you set `FORCE=1`. -->

## 11. Script 04: Check Raster Stack

Purpose:

- Confirm every predictor matches the template.
- Print CRS, size, transform, pixel size, and NoData.
- Stop early if a raster is missing or misaligned.

Create:

```text
scripts/04_check_raster_stack.py
```

Code:

```python
import importlib.util
from pathlib import Path

import rasterio


def load_config():
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


cfg = load_config()

mask_path = cfg.ROI_DIR / "nt_mask_500m.tif"

with rasterio.open(mask_path) as ref:
    ref_crs = ref.crs
    ref_transform = ref.transform
    ref_width = ref.width
    ref_height = ref.height

print("Reference:", mask_path)
print("  CRS:", ref_crs)
print("  width/height:", ref_width, ref_height)
print("  transform:", ref_transform)
print()

all_ok = True

for name, path in cfg.PREDICTOR_RASTERS.items():
    print(name)
    print("  Path:", path)

    if not path.exists():
        print("  ERROR: missing")
        all_ok = False
        continue

    with rasterio.open(path) as src:
        print("  CRS:", src.crs)
        print("  width/height:", src.width, src.height)
        print("  pixel size:", src.transform.a, src.transform.e)
        print("  nodata:", src.nodata)

        same = (
            src.crs == ref_crs
            and src.transform == ref_transform
            and src.width == ref_width
            and src.height == ref_height
        )

    if same:
        print("  OK")
    else:
        print("  ERROR: does not match template")
        all_ok = False

    print()

if not all_ok:
    raise SystemExit("At least one raster is missing or misaligned.")

print("All predictor rasters match the template.")
```

Run:

```bash
python scripts/04_check_raster_stack.py
```

Do not continue until it prints:

```text
All predictor rasters match the template.
```

## 12. Script 05: Make MVT Label Raster

Purpose:

- Read the occurrence CSV.
- Keep Australian MVT points.
- Reproject points to `EPSG:3577`.
- Keep only points inside Northern Territory.
- Burn those points into the 500 m template grid.

Create:

```text
scripts/05_make_mvt_labels.py
```

Code:

```python
import importlib.util
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol


def load_config():
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


cfg = load_config()
cfg.ensure_directories()

df = pd.read_csv(cfg.OCCURRENCES, encoding="latin1")
print("Occurrence rows:", len(df))

df = df[df["Admin"] == "Australia"].copy()
df = df[df["Dep_Grp"].str.contains("Mississippi Valley-type", na=False)].copy()
print("Australian MVT rows:", len(df))

points = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["Longitude"], df["Latitude"]),
    crs=cfg.SOURCE_CRS,
)
points = points.to_crs(cfg.PROJECT_CRS)

nt = gpd.read_file(cfg.ROI_DIR / "nt_boundary_3577_dissolved.gpkg").to_crs(cfg.PROJECT_CRS)
points_nt = gpd.sjoin(points, nt[["geometry"]], predicate="within", how="inner")
points_nt = points_nt.drop(columns=["index_right"])
print("MVT rows inside NT:", len(points_nt))

points_out = cfg.LABELS_DIR / "mvt_points_nt_3577.gpkg"
points_nt.to_file(points_out, driver="GPKG", layer="mvt_points_nt_3577")
print("Wrote:", points_out)

mask_path = cfg.ROI_DIR / "nt_mask_500m.tif"
with rasterio.open(mask_path) as src:
    mask = src.read(1)
    profile = src.profile.copy()
    transform = src.transform

label = np.zeros(mask.shape, dtype="uint8")

xs = points_nt.geometry.x.to_numpy()
ys = points_nt.geometry.y.to_numpy()
rows, cols = rowcol(transform, xs, ys)

for row, col in zip(rows, cols):
    if 0 <= row < label.shape[0] and 0 <= col < label.shape[1]:
        if mask[row, col] == 1:
            label[row, col] = 1

profile.update(dtype="uint8", nodata=0, count=1, compress="lzw")

label_out = cfg.LABELS_DIR / "mvt_labels_500m.tif"
with rasterio.open(label_out, "w", **profile) as dst:
    dst.write(label, 1)

print("Wrote:", label_out)
print("Positive label pixels:", int(label.sum()))
```

Run:

```bash
python scripts/05_make_mvt_labels.py
```

Expected outputs:

```text
data/processed/labels/mvt_points_nt_3577.gpkg
data/processed/labels/mvt_labels_500m.tif
```

Important:

- If 70 points become fewer than 70 positive pixels, that is normal.
- Multiple points can fall in the same 500 m pixel.
- These are training labels, not predictor rasters.

## 13. Script 06: Build Training Table

Purpose:

- Read predictor rasters.
- Read the label raster.
- Convert valid pixels into table rows.
- Sample background pixels.
- Write a CSV table for machine learning.

Create:

```text
scripts/06_build_training_table.py
```

Code:

```python
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


def load_config():
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


cfg = load_config()
cfg.ensure_directories()


def read_as_float(path):
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
        nodata = src.nodata
    if nodata is not None:
        arr[arr == nodata] = np.nan
    return arr


with rasterio.open(cfg.ROI_DIR / "nt_mask_500m.tif") as src:
    mask = src.read(1)
    transform = src.transform

with rasterio.open(cfg.LABELS_DIR / "mvt_labels_500m.tif") as src:
    labels = src.read(1)

valid = mask == 1

columns = {}
for name, path in cfg.PREDICTOR_RASTERS.items():
    print("Reading:", name)
    arr = read_as_float(path)
    columns[name] = arr[valid]

rows, cols = np.where(valid)
xs, ys = rasterio.transform.xy(transform, rows, cols)

table = pd.DataFrame(columns)
table["label"] = labels[valid].astype("uint8")
table["x"] = xs
table["y"] = ys

before = len(table)
table = table.dropna()
after = len(table)
print("Rows before dropping missing values:", before)
print("Rows after dropping missing values:", after)

positives = table[table["label"] == 1]
background = table[table["label"] == 0]

print("Positive rows:", len(positives))
print("Background rows:", len(background))

if len(positives) == 0:
    raise ValueError("No positive labels found. Check mvt_labels_500m.tif.")

background_per_positive = 50
n_background = min(len(background), len(positives) * background_per_positive)

background_sample = background.sample(n=n_background, random_state=42)
training = pd.concat([positives, background_sample], ignore_index=True)
training = training.sample(frac=1, random_state=42).reset_index(drop=True)

out_path = cfg.MODELS_DIR / "training_table.csv"
training.to_csv(out_path, index=False)

print("Wrote:", out_path)
print("Training table rows:", len(training))
print("Training positives:", int(training["label"].sum()))
print("Training background:", int((training["label"] == 0).sum()))
```

Run:

```bash
python scripts/06_build_training_table.py
```

Expected output:

```text
data/processed/models/training_table.csv
```

What happened:

- Each valid pixel became one possible ML row.
- The script kept all positive MVT pixels.
- The script sampled background pixels so the model is not overwhelmed by millions of zeros.

<!-- Implemented script note: `scripts/06_build_training_table.py` keeps `0` values from `carbonate_host_500m.tif` and `lithology_code_500m.tif` as valid model values inside the NT mask. It also samples positives/backgrounds from arrays before building the final DataFrame, which is much lighter than creating a DataFrame for every NT pixel. -->

## 14. Script 07: Train Random Forest Model

Purpose:

- Train a beginner-friendly machine learning model.
- Use a spatial block split so validation is less over-optimistic.
- Save model metrics and feature importance.

Random Forest is a good first model because it handles nonlinear relationships and does not require scaling.

Create:

```text
scripts/07_train_random_forest.py
```

Code:

```python
import importlib.util
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, classification_report, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit


def load_config():
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


cfg = load_config()

training_path = cfg.MODELS_DIR / "training_table.csv"
df = pd.read_csv(training_path)

feature_names = list(cfg.PREDICTOR_RASTERS.keys())

X = df[feature_names]
y = df["label"]

# Spatial validation: pixels in the same 100 km block stay together.
# This is stricter than a normal random split.
block_size = 100_000
block_x = (df["x"] // block_size).astype(int)
block_y = (df["y"] // block_size).astype(int)
groups = block_x.astype(str) + "_" + block_y.astype(str)

splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
train_idx, test_idx = next(splitter.split(X, y, groups=groups))

X_train = X.iloc[train_idx]
X_test = X.iloc[test_idx]
y_train = y.iloc[train_idx]
y_test = y.iloc[test_idx]

print("Train positives:", int(y_train.sum()))
print("Test positives:", int(y_test.sum()))

if y_test.nunique() < 2:
    raise ValueError(
        "The test split has only one class. Try changing random_state or block_size."
    )

model = RandomForestClassifier(
    n_estimators=500,
    min_samples_leaf=2,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,
)

model.fit(X_train, y_train)

prob = model.predict_proba(X_test)[:, 1]
pred = model.predict(X_test)

roc_auc = roc_auc_score(y_test, prob)
average_precision = average_precision_score(y_test, prob)
report = classification_report(y_test, pred)

importance = pd.DataFrame(
    {
        "feature": feature_names,
        "importance": model.feature_importances_,
    }
).sort_values("importance", ascending=False)

model_path = cfg.MODELS_DIR / "random_forest_mvt.joblib"
importance_path = cfg.MODELS_DIR / "feature_importance.csv"
metrics_path = cfg.MODELS_DIR / "model_metrics.txt"

joblib.dump(model, model_path)
importance.to_csv(importance_path, index=False)

with open(metrics_path, "w", encoding="utf-8") as f:
    f.write(f"ROC AUC: {roc_auc:.4f}\n")
    f.write(f"Average precision: {average_precision:.4f}\n\n")
    f.write(report)
    f.write("\n\nFeature importance:\n")
    f.write(importance.to_string(index=False))

print("ROC AUC:", roc_auc)
print("Average precision:", average_precision)
print(report)
print("Wrote:", model_path)
print("Wrote:", importance_path)
print("Wrote:", metrics_path)
```

Run:

```bash
python scripts/07_train_random_forest.py
```

Expected outputs:

```text
data/processed/models/random_forest_mvt.joblib
data/processed/models/feature_importance.csv
data/processed/models/model_metrics.txt
```

How to read metrics:

- `ROC AUC` near 0.5 means little predictive skill.
- Higher `ROC AUC` is better, but it can be misleading for rare deposits.
- `Average precision` is useful for rare positive labels.
- Spatial validation is harder than random validation and is usually more honest.

## 15. Script 08: Predict Prospectivity Map

Purpose:

- Apply the trained model to every valid Northern Territory pixel.
- Write a prospectivity GeoTIFF with values from 0 to 1.

Create:

```text
scripts/08_predict_prospectivity.py
```

Code:

```python
import importlib.util
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import rasterio


def load_config():
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


cfg = load_config()
cfg.ensure_directories()


def read_as_float(path):
    with rasterio.open(path) as src:
        arr = src.read(1).astype("float32")
        nodata = src.nodata
    if nodata is not None:
        arr[arr == nodata] = np.nan
    return arr


model = joblib.load(cfg.MODELS_DIR / "random_forest_mvt.joblib")
feature_names = list(cfg.PREDICTOR_RASTERS.keys())

with rasterio.open(cfg.ROI_DIR / "nt_mask_500m.tif") as src:
    mask = src.read(1)
    profile = src.profile.copy()

valid = mask == 1

feature_arrays = []
for name in feature_names:
    print("Reading:", name)
    feature_arrays.append(read_as_float(cfg.PREDICTOR_RASTERS[name]))

stack = np.stack(feature_arrays, axis=0)
valid_rows, valid_cols = np.where(valid)
X = stack[:, valid_rows, valid_cols].T

usable = ~np.isnan(X).any(axis=1)
scores = np.full(X.shape[0], cfg.NODATA_FLOAT, dtype="float32")

chunk_size = 200_000
usable_indices = np.where(usable)[0]

for start in range(0, len(usable_indices), chunk_size):
    end = start + chunk_size
    idx = usable_indices[start:end]
    chunk = pd.DataFrame(X[idx], columns=feature_names)
    scores[idx] = model.predict_proba(chunk)[:, 1].astype("float32")
    print("Predicted pixels:", min(end, len(usable_indices)), "of", len(usable_indices))

score_map = np.full(mask.shape, cfg.NODATA_FLOAT, dtype="float32")
score_map[valid_rows, valid_cols] = scores

profile.update(dtype="float32", nodata=cfg.NODATA_FLOAT, count=1, compress="lzw")

out_path = cfg.MAPS_DIR / "mvt_prospectivity_random_forest_500m.tif"
with rasterio.open(out_path, "w", **profile) as dst:
    dst.write(score_map, 1)

print("Wrote:", out_path)
```

Run:

```bash
python scripts/08_predict_prospectivity.py
```

Expected output:

```text
outputs/maps/mvt_prospectivity_random_forest_500m.tif
```

Meaning of output values:

- `0.0` means low model score.
- `1.0` means high model score.
- `-9999` means NoData.

These are model scores, not guaranteed discovery probabilities.

## 16. Script 09: Summarize Outputs

Purpose:

- Create simple summary tables for review.
- Make a top 5 percent raster.
- Save a short text report.

Create:

```text
scripts/09_summarize_outputs.py
```

Code:

```python
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio


def load_config():
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


cfg = load_config()
cfg.ensure_directories()

score_path = cfg.MAPS_DIR / "mvt_prospectivity_random_forest_500m.tif"

with rasterio.open(score_path) as src:
    scores = src.read(1)
    profile = src.profile.copy()
    nodata = src.nodata

valid = scores != nodata
valid_scores = scores[valid]

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

summary_path = cfg.TABLES_DIR / "prospectivity_score_summary.csv"
pd.DataFrame([summary]).to_csv(summary_path, index=False)
print("Wrote:", summary_path)

threshold = summary["p95"]
top5 = np.zeros(scores.shape, dtype="uint8")
top5[valid & (scores >= threshold)] = 1

profile.update(dtype="uint8", nodata=0, count=1, compress="lzw")
top5_path = cfg.MAPS_DIR / "mvt_top_5_percent_500m.tif"
with rasterio.open(top5_path, "w", **profile) as dst:
    dst.write(top5, 1)

print("Top 5 percent threshold:", threshold)
print("Wrote:", top5_path)

report_path = cfg.TABLES_DIR / "model_review_template.txt"
with open(report_path, "w", encoding="utf-8") as f:
    f.write("Model run name: random_forest_mvt_500m\n")
    f.write("Pixel size: 500 m\n")
    f.write("CRS: EPSG:3577\n")
    f.write("Prospectivity map: outputs/maps/mvt_prospectivity_random_forest_500m.tif\n")
    f.write("Top 5 percent map: outputs/maps/mvt_top_5_percent_500m.tif\n")
    f.write(f"Top 5 percent threshold: {threshold:.4f}\n")
    f.write("\nQuestions to answer in QGIS:\n")
    f.write("- Do known MVT points fall in high-score areas?\n")
    f.write("- Are high-score areas geologically plausible?\n")
    f.write("- Are high scores caused by data edges or NoData boundaries?\n")
    f.write("- Which feature importances make geological sense?\n")
    f.write("- What should be changed in the next model run?\n")

print("Wrote:", report_path)
```

Run:

```bash
python scripts/09_summarize_outputs.py
```

Expected outputs:

```text
outputs/tables/prospectivity_score_summary.csv
outputs/maps/mvt_top_5_percent_500m.tif
outputs/tables/model_review_template.txt
```

## 17. Full Run Order

After all scripts are created, run:

```bash
python scripts/01_make_roi_and_template.py
python scripts/02_process_continuous_rasters.py
python scripts/03_process_vector_predictors.py
python scripts/04_check_raster_stack.py
python scripts/05_make_mvt_labels.py
python scripts/06_build_training_table.py
python scripts/07_train_random_forest.py
python scripts/08_predict_prospectivity.py
python scripts/09_summarize_outputs.py
```

If a script fails, stop and fix that step before moving on.

Do not skip `04_check_raster_stack.py`. It is the quality gate for the entire workflow.

## 18. QGIS Review After Python Processing

Even in a Python workflow, you should review the outputs visually in QGIS.

Load these layers:

```text
data/processed/roi/nt_boundary_3577_dissolved.gpkg
data/processed/roi/nt_mask_500m.tif
data/processed/labels/mvt_points_nt_3577.gpkg
outputs/maps/mvt_prospectivity_random_forest_500m.tif
outputs/maps/mvt_top_5_percent_500m.tif
data/processed/rasters_500m/carbonate_host_500m.tif
data/processed/rasters_500m/dist_faults_500m.tif
```

Check:

- The prospectivity raster aligns with Northern Territory.
- Values do not appear outside the ROI.
- Known MVT points are visible.
- High-score areas are not just raster edges or NoData boundaries.
- High-score areas have some geological logic.

Style the prospectivity map:

- Render type: `Singleband pseudocolor`
- Min: `0`
- Max: `1`
- Suggested classes:
  - `0.00 to 0.20`: very low
  - `0.20 to 0.40`: low
  - `0.40 to 0.60`: moderate
  - `0.60 to 0.80`: high
  - `0.80 to 1.00`: very high

## 19. How To Think About The Result

The model does not know geology the way a geologist does.

It only learns statistical patterns from:

- known MVT pixels
- sampled background pixels
- predictor raster values

A high score means:

```text
This pixel looks similar to the known MVT pixels according to the input predictors.
```

It does not mean:

```text
There is definitely an ore deposit here.
```

You must combine the model result with geological review.

## 20. Common Beginner Mistakes

### Mistake 1: Using EPSG:4326 For 500 m Pixels

EPSG:4326 uses degrees. Use EPSG:3577 for 500 m pixels and distance calculations.

### Mistake 2: Not Checking Alignment

All rasters must match the template exactly. Same CRS and same pixel size are not enough. The transform, width, and height must also match.

### Mistake 3: Treating Background As True Absence

Background pixels are not proven barren. They are simply pixels without known MVT points.

### Mistake 4: Data Leakage

Do not use occurrence locations or the existing MVT prospectivity model as predictors.

### Mistake 5: Trusting Accuracy Alone

Rare deposit problems can have misleading accuracy. Use average precision, ROC AUC, spatial validation, and map review.

### Mistake 6: Too Many Predictors Too Early

Start simple. Add more predictors only after the basic workflow runs cleanly.

## 21. First Milestone

The first complete Python milestone is:

1. `data/processed/roi/nt_mask_500m.tif` exists.
2. Continuous rasters exist in `data/processed/rasters_500m/`.
3. Carbonate, lithology, and distance-to-fault rasters exist.
4. `04_check_raster_stack.py` passes.
5. `mvt_labels_500m.tif` exists.
6. `training_table.csv` exists.
7. `random_forest_mvt.joblib` exists.
8. `outputs/maps/mvt_prospectivity_random_forest_500m.tif` exists.
9. The result opens correctly in QGIS.
10. You write down what worked, what looked suspicious, and what to try next.

The first goal is not a perfect mineral prospectivity model. The first goal is a correct, repeatable workflow that you understand.
