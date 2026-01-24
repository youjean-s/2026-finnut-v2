# FHI 2.0 Label Design (Draft)

## 1) Primary Choice
- Use **Regression (0~100)** as the main target for v1.
- Reason: aligns with FHI 1.0 score and preserves granularity.

## 2) Bootstrap Label (Weak Label)
### Weak label definition
- y = clamp(FHI_1_0_rule_based, 0, 100)
- FHI 1.0 is computed from rule-based impulsive/spike components.

### Why weak label
- No ground truth “financial health” label exists in open datasets.
- Weak label enables initial LightGBM model training and feature importance analysis.

## 3) Optional Derived Classification Label (for analysis only)
Define risk classes from y:
- High risk: y < 60
- Medium risk: 60 ≤ y < 80
- Low risk: y ≥ 80

This is not the main training objective, but can be used to:
- sanity-check separability
- communicate demo outputs

## 4) Handling missing/approx labels on open datasets
If dataset lacks necessary fields for exact FHI 1.0:
- Use simplified proxy weak label:
  - impulsive_proxy: night_tx_ratio + small_tx_ratio + repeat_24h
  - spike_proxy: spend_trend_ratio
  - y_proxy = 100 - (w1*impulsive_proxy + w2*spike_proxy), then clamp 0..100
- Keep “label_type” field to distinguish (rule_based vs proxy)

## 5) Evaluation plan (since label is weak)
- Primary: holdout MAE/RMSE vs weak label
- Secondary: stability checks:
  - feature importance consistency across folds
  - monotonic sanity checks (e.g., higher spike → lower score)
