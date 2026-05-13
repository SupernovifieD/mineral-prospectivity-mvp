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
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load config from {config_path}")
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


cfg = load_config()
cfg.ensure_directories()

if not cfg.AUSTRALIA_BOUNDARY.exists():
    raise FileNotFoundError(f"Missing boundary file: {cfg.AUSTRALIA_BOUNDARY}")

boundary = gpd.read_file(cfg.AUSTRALIA_BOUNDARY)
print("Boundary CRS:", boundary.crs)
print("Boundary rows:", len(boundary))

if boundary.crs is None:
    print("Boundary CRS missing, assuming:", cfg.SOURCE_CRS)
    boundary = boundary.set_crs(cfg.SOURCE_CRS)

if "NAME_1" not in boundary.columns:
    raise KeyError("Boundary file must contain a NAME_1 field.")

nt = boundary[boundary["NAME_1"] == "Northern Territory"].copy()
if nt.empty:
    raise ValueError("Could not find Northern Territory in NAME_1 field.")

nt["geometry"] = nt.geometry.apply(make_valid)
nt = nt[nt.geometry.notna() & ~nt.geometry.is_empty].copy()
if nt.empty:
    raise ValueError("Northern Territory geometry is empty after validation.")

nt_3577 = nt.to_crs(cfg.PROJECT_CRS)
nt_3577["dissolve_id"] = 1
nt_3577 = nt_3577.dissolve(by="dissolve_id").reset_index(drop=True)

if nt_3577.empty:
    raise ValueError("Northern Territory geometry is empty after dissolving.")

if cfg.NT_BOUNDARY_3577.exists():
    cfg.NT_BOUNDARY_3577.unlink()
nt_3577.to_file(
    cfg.NT_BOUNDARY_3577,
    driver="GPKG",
    layer="nt_boundary_3577_dissolved",
)
print("Wrote:", cfg.NT_BOUNDARY_3577)

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

inside_pixels = int(mask.sum())
if inside_pixels == 0:
    raise ValueError("The NT mask has zero inside pixels.")

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

with rasterio.open(cfg.NT_MASK_500M, "w", **profile) as dst:
    dst.write(mask, 1)

print("Wrote:", cfg.NT_MASK_500M)
print("Inside-NT pixels:", inside_pixels)
