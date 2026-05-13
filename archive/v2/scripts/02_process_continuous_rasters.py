import importlib.util
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject


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

if not cfg.NT_MASK_500M.exists():
    raise FileNotFoundError(f"Missing template mask. Run script 01 first: {cfg.NT_MASK_500M}")

missing_inputs = {
    name: path
    for name, path in cfg.CONTINUOUS_RASTERS.items()
    if not path.exists()
}
if missing_inputs:
    message = "\n".join(f"- {name}: {path}" for name, path in missing_inputs.items())
    raise FileNotFoundError(f"Missing continuous raster input(s):\n{message}")

with rasterio.open(cfg.NT_MASK_500M) as mask_src:
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

    destination = np.full(
        (template_height, template_width),
        cfg.NODATA_FLOAT,
        dtype="float32",
    )

    with rasterio.open(src_path) as src:
        if src.count < 1:
            raise ValueError(f"Input raster has no bands: {src_path}")

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

    destination[~np.isfinite(destination)] = cfg.NODATA_FLOAT
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
    if valid.size == 0:
        raise ValueError(f"Output raster has no valid pixels inside NT: {out_path}")
    print("  Min/max:", float(np.nanmin(valid)), float(np.nanmax(valid)))


for raster_name, raster_path in cfg.CONTINUOUS_RASTERS.items():
    process_one_raster(raster_name, raster_path)
