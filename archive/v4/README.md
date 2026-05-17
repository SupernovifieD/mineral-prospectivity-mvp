# V4 Archive Snapshot

Archived on: 2026-05-17 15:59:27 +0330

This folder is the frozen v4 run snapshot for NT MVT 500 m.

## Included

- `configs/v4_run_config.yml`
- `scripts/00_config.py` through `scripts/12_write_run_manifest.py`
- `PROJECT_WORKFLOW_NT_MVT_500M_V4.md`
- `DECISIONS_TO_MAKE_V4.md`
- `data/processed/` artifacts used and produced by v4
- `outputs/` maps, tables, and `run_manifest_v4.json`

## Key Run Facts

- Accepted original splits: 10 (non-exploratory threshold met)
- Holdout zones covered: 3 (`northern`, `central`, `southern`)
- Spatial buffer: 10 km
- Holdout aggregate average precision (mean): `0.000724`
- Holdout top-area capture (mean recall):
  - top 1%: `0.1185`
  - top 5%: `0.3863`
  - top 10%: `0.4747`

## Claims Language

- Scores are relative prospectivity rankings, not calibrated deposit probabilities.
- Holdout evidence comes from split evaluation, not from the final production model.
