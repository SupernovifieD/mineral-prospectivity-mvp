import importlib.util
from pathlib import Path

import rasterio


def load_config():
    config_path = Path(__file__).resolve().parent / "00_config.py"
    spec = importlib.util.spec_from_file_location("config", config_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load config from {config_path}")
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


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


cfg = load_config()
check_predictor_leakage(cfg)

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

for name, path in cfg.PREDICTOR_RASTERS.items():
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

print("All predictor rasters match the template.")
