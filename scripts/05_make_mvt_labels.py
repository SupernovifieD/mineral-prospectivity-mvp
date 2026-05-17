"""Create MVT point layer and binary label raster for NT.

The label raster is the target used by modeling:
- 1 = pixel containing at least one known MVT point,
- 0 = all other pixels (background/unlabeled).
"""

import importlib.util
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol


def load_config():
    """Import ``00_config.py`` dynamically and return it as a module object."""
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load config from {config_path}")
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


cfg = load_config()
cfg.ensure_directories()

if not cfg.OCCURRENCES.exists():
    raise FileNotFoundError(f"Missing occurrence CSV: {cfg.OCCURRENCES}")
if not cfg.NT_BOUNDARY_3577.exists() or not cfg.NT_MASK_500M.exists():
    raise FileNotFoundError("Missing ROI outputs. Run script 01 first.")

# Read occurrence catalog and keep only Australian MVT records.
df = pd.read_csv(cfg.OCCURRENCES, encoding="latin1")
print("Occurrence rows:", len(df))

required_columns = {"Admin", "Dep_Grp", "Longitude", "Latitude"}
missing_columns = required_columns.difference(df.columns)
if missing_columns:
    raise KeyError(f"Occurrence CSV missing required columns: {sorted(missing_columns)}")

df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
df = df.dropna(subset=["Longitude", "Latitude"]).copy()

df = df[df["Admin"] == "Australia"].copy()
df = df[df["Dep_Grp"].str.contains("Mississippi Valley-type", case=False, na=False)].copy()
print("Australian MVT rows:", len(df))

if df.empty:
    raise ValueError("No Australian MVT occurrence rows found.")

points = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["Longitude"], df["Latitude"]),
    crs=cfg.SOURCE_CRS,
)
points = points.to_crs(cfg.PROJECT_CRS)

# Spatially filter points to the NT ROI in project CRS.
nt = gpd.read_file(cfg.NT_BOUNDARY_3577).to_crs(cfg.PROJECT_CRS)
points_nt = gpd.sjoin(points, nt[["geometry"]], predicate="intersects", how="inner")
points_nt = points_nt.drop(columns=["index_right"])
print("MVT rows inside NT:", len(points_nt))

if points_nt.empty:
    raise ValueError("No Australian MVT points fall inside the Northern Territory ROI.")

if cfg.MVT_POINTS_3577.exists():
    cfg.MVT_POINTS_3577.unlink()
points_nt.to_file(cfg.MVT_POINTS_3577, driver="GPKG", layer="mvt_points_nt_3577")
print("Wrote:", cfg.MVT_POINTS_3577)

with rasterio.open(cfg.NT_MASK_500M) as src:
    mask = src.read(1)
    profile = src.profile.copy()
    transform = src.transform

label = np.zeros(mask.shape, dtype="uint8")

xs = points_nt.geometry.x.to_numpy()
ys = points_nt.geometry.y.to_numpy()
rows, cols = rowcol(transform, xs, ys)

# Mark every in-bounds NT pixel containing at least one MVT point as positive.
for row, col in zip(rows, cols):
    if 0 <= row < label.shape[0] and 0 <= col < label.shape[1]:
        if mask[row, col] == 1:
            label[row, col] = 1

positive_pixels = int(label.sum())
if positive_pixels == 0:
    raise ValueError("No positive label pixels were created inside the NT mask.")

profile.update(dtype="uint8", nodata=0, count=1, compress="lzw")

with rasterio.open(cfg.MVT_LABELS_500M, "w", **profile) as dst:
    dst.write(label, 1)

print("Wrote:", cfg.MVT_LABELS_500M)
print("Positive label pixels:", positive_pixels)
# Difference > 0 means multiple points collapsed into shared pixels at 500 m.
print("Point rows sharing pixels:", len(points_nt) - positive_pixels)
