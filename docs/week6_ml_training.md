# Week6 — LightGBM Training (FHI 2.0 Baseline + Grid Tuning)

## Goal
Train a LightGBM regressor for proxy FHI label (`label_fhi`) using engineered features.

## Inputs
- `ml/data/features/features.csv` (merged features)
- `ml/data/features/features_labeled.csv` (features + label_fhi)
- `ml/data/features/train.csv`, `ml/data/features/val.csv` (user-based split)

> Note: `ml/data/` is gitignored (generated locally).

## Pipeline (Repro commands)
From repo root:

1) Merge features
```bash
python ml/src/merge_features.py

2) Make weak label
python ml/src/make_labels.py

3) Split train/val by user_id (no leakage)
python ml/src/split_train_val.py

4) Train baseline LightGBM
python ml/src/train_lgbm_baseline.py

5) Gri search tuning
python ml/src/tune_lgbm_grid.py

Outputs

1) Models

Baseline: ml/artifacts/models/lgbm_fhi_v2_baseline.txt

Best (grid): ml/artifacts/models/lgbm_fhi_v2_grid_best.txt

2) Reports

Baseline metrics: ml/artifacts/reports/baseline_report.json

Baseline feature importance: ml/artifacts/reports/feature_importance.csv

Grid best report: ml/artifacts/reports/grid_search_report.json

Full grid results: ml/artifacts/reports/grid_search_results.csv

Grid best feature importance: ml/artifacts/reports/grid_best_feature_importance.csv

Best Params (Grid)
See ml/artifacts/reports/grid_search_report.json


