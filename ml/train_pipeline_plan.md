# FHI 2.0 Training Pipeline Plan (Design Only)

## 1) Target
- Input: transaction CSV (open dataset)
- Output:
  - feature table (per user, per reference date)
  - trained LightGBM model file
  - basic evaluation report (MAE/RMSE) + feature importance

## 2) Proposed Folder Layout
ml/
- data/
  - raw/        (downloaded CSV)
  - processed/  (normalized tx schema CSV)
  - features/   (feature table CSV)
- src/
  - normalize.py
  - feature_engineering.py
  - label.py
  - train.py
  - eval.py
- artifacts/
  - models/
  - reports/

## 3) Module Interfaces (Python)
### A) normalize.py
- `normalize_raw_dataset(input_csv, output_csv, source_name) -> None`
  - maps raw columns -> FINNUT schema:
    datetime, amount, merchant, category, payment_method, source

### B) feature_engineering.py
- `make_feature_table(tx_csv, out_feature_csv, window_days=[7,30], ref_mode="daily") -> None`
  - outputs one row per (user_id, ref_date)

### C) label.py
- `make_weak_labels(feature_csv, out_csv, label_type="rule_based"|"proxy") -> None`
  - adds `label_fhi` column

### D) train.py
- `train_lgbm(feature_csv, model_out, task="regression") -> dict`
  - returns metrics dict and saves model

### E) eval.py
- `evaluate(model_path, feature_csv) -> dict`
  - MAE/RMSE + feature importance dump

## 4) Train/Val Split Policy
- user-based split recommended (avoid leakage)
- default: 80/20 by user_id

## 5) Deliverables (Week4 output)
- No training code yet (design only)
- Clear spec to implement in Week5~6
