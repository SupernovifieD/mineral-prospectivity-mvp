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
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load config from {config_path}")
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


cfg = load_config()
cfg.ensure_directories()

if not cfg.NT_MASK_500M.exists() or not cfg.NT_BOUNDARY_3577.exists():
    raise FileNotFoundError("Missing ROI outputs. Run script 01 first.")

for required_path in [cfg.GEOLOGY, cfg.FAULTS]:
    if not required_path.exists():
        raise FileNotFoundError(f"Missing vector input: {required_path}")

with rasterio.open(cfg.NT_MASK_500M) as mask_src:
    nt_mask = mask_src.read(1)
    profile = mask_src.profile.copy()
    transform = mask_src.transform
    out_shape = (mask_src.height, mask_src.width)

nt_boundary = gpd.read_file(cfg.NT_BOUNDARY_3577).to_crs(cfg.PROJECT_CRS)
nt_bbox_source = tuple(nt_boundary.to_crs(cfg.SOURCE_CRS).total_bounds)


def write_gpkg(gdf, path, layer):
    if path.exists():
        path.unlink()
    gdf.to_file(path, driver="GPKG", layer=layer)
    print("Wrote:", path)


def clean_project_clip(path):
    print("Read:", path)
    gdf = gpd.read_file(path, bbox=nt_bbox_source)
    print("  Rows after source bbox filter:", len(gdf))
    print("  CRS:", gdf.crs)

    if gdf.crs is None:
        print("  CRS missing, assuming:", cfg.SOURCE_CRS)
        gdf = gdf.set_crs(cfg.SOURCE_CRS)

    gdf = gdf[gdf.geometry.notna()].copy()
    gdf["geometry"] = gdf.geometry.apply(make_valid)
    gdf = gdf[~gdf.geometry.is_empty].copy()
    if gdf.empty:
        raise ValueError(f"No valid geometries after bbox filter: {path}")

    gdf = gdf.to_crs(cfg.PROJECT_CRS)
    clipped = gpd.clip(gdf, nt_boundary)
    clipped = clipped[clipped.geometry.notna()].copy()
    clipped = clipped[~clipped.geometry.is_empty].copy()
    print("  Rows after NT clip:", len(clipped))

    if clipped.empty:
        raise ValueError(f"No geometries intersect Northern Territory: {path}")
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
    if not shapes:
        return np.full(out_shape, fill, dtype=dtype)
    return rasterize(
        shapes,
        out_shape=out_shape,
        transform=transform,
        fill=fill,
        dtype=dtype,
        all_touched=True,
    )


geology = clean_project_clip(cfg.GEOLOGY)
geology_out = cfg.VECTORS_3577_DIR / "geology_nt_3577.gpkg"
write_gpkg(geology, geology_out, "geology_nt_3577")

if "CMMI_Class" not in geology.columns:
    raise KeyError("Geology layer must contain a CMMI_Class field.")

carbonate = geology[geology["CMMI_Class"] == "Sedimentary_Chemical_Carbonate"].copy()
print("Carbonate rows:", len(carbonate))
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

faults = clean_project_clip(cfg.FAULTS)
faults_out = cfg.VECTORS_3577_DIR / "faults_nt_3577.gpkg"
write_gpkg(faults, faults_out, "faults_nt_3577")

fault_binary = rasterize_geometries(faults, value=1, dtype="uint8", fill=0)
fault_binary[nt_mask != 1] = 0
write_raster(cfg.RASTERS_500M_DIR / "faults_binary_500m.tif", fault_binary, "uint8", 0)

if fault_binary.max() == 0:
    raise ValueError("No fault pixels were rasterized. Check the fault layer and ROI.")

distance = distance_transform_edt(
    fault_binary == 0,
    sampling=(cfg.PIXEL_SIZE, cfg.PIXEL_SIZE),
).astype("float32")
distance[nt_mask != 1] = cfg.NODATA_FLOAT
write_raster(cfg.RASTERS_500M_DIR / "dist_faults_500m.tif", distance, "float32", cfg.NODATA_FLOAT)
