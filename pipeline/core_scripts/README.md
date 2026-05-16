# Core Scripts (Permanent Base)

This directory is the permanent home for the stable base pipeline scripts:

- `00_config.py`
- `01_make_roi_and_template.py`
- `02_process_continuous_rasters.py`
- `03_process_vector_predictors.py`
- `04_check_raster_stack.py`

These are kept outside archived runs so you do not need to move them every iteration.

## Intended Usage

Use these as the base when creating a new run (for example `v4`), then copy them into that run's `scripts/` directory.

Example:

```bash
mkdir -p runs/v4/{scripts,configs,data,outputs}
cp pipeline/core_scripts/0*_*.py runs/v4/scripts/
```

Then adjust run-specific settings (especially in `runs/v4/scripts/00_config.py` and your run config YAML).

## Why Copy Instead Of Edit-In-Place?

`00_config.py` is run-specific by design (paths, run config file, outputs).  
Copying keeps each run reproducible while this directory stays as your clean baseline.

## Rule

- Do not edit archived scripts in `archive/v*/scripts` for future workflow evolution.
- Evolve the baseline here, then copy into new run directories.

## YAML Knobs Moved Out Of Code

The core config now reads these values from your run YAML:

- `sampling.background_per_positive`
- `sampling.use_spatially_stratified_background`
- `sampling.background_block_size_pixels`
- `prediction.chunk_size_pixels`

If omitted, safe defaults are applied.
