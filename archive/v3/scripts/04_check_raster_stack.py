"""Validate predictor stack integrity before modeling.

Checks performed:
1) leakage guard on predictor names/paths,
2) existence of all configured feature rasters,
3) exact alignment against the NT template (CRS, transform, width, height).
"""

import importlib.util
from pathlib import Path

import rasterio


def load_config():
    """Import ``00_config.py`` dynamically and return it as a module object."""
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load config from {config_path}")
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


def check_predictor_leakage(cfg):
    """Detect obvious leakage keywords in configured predictors.

    This is a defensive string-based check. It cannot prove zero leakage, but
    it catches common configuration mistakes early.
    """
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


cfg = load_config()
check_predictor_leakage(cfg)
feature_names = cfg.FEATURE_COLUMNS

# Template acts as the single alignment reference for all predictors.
if not cfg.NT_MASK_500M.exists():
    raise FileNotFoundError(f"Missing template mask. Run script 01 first: {cfg.NT_MASK_500M}")

with rasterio.open(cfg.NT_MASK_500M) as ref:
    ref_crs = ref.crs
    ref_transform = ref.transform
    ref_width = ref.width
    ref_height = ref.height

print("Reference:", cfg.NT_MASK_500M)
print("  CRS:", ref_crs)
print("  width/height:", ref_width, ref_height)
print("  transform:", ref_transform)
print()

errors = []

# Validate only active features listed in YAML (not every file on disk).
for name in feature_names:
    path = cfg.PREDICTOR_RASTERS[name]
    print(name)
    print("  Path:", path)

    if not path.exists():
        print("  ERROR: missing")
        errors.append(f"{name}: missing {path}")
        print()
        continue

    with rasterio.open(path) as src:
        print("  CRS:", src.crs)
        print("  width/height:", src.width, src.height)
        print("  pixel size:", src.transform.a, src.transform.e)
        print("  nodata:", src.nodata)

        # All four properties must match exactly for pixel-perfect stacking.
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
        errors.append(f"{name}: does not match template")

    print()

if errors:
    detail = "\n".join(f"- {error}" for error in errors)
    raise SystemExit(f"At least one raster is missing or misaligned:\n{detail}")

print("All active feature rasters match the template.")
