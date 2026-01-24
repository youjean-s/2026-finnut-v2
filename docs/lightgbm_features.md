# LightGBM Feature Definition (Draft)

## 1) Transaction-level raw fields (from parser)
- datetime
- amount
- merchant
- category
- payment_method
- source

## 2) Aggregation features (per user / per week / per month)
- total_spend_week
- total_spend_month
- avg_spend_per_tx
- tx_count_week
- tx_count_month
- category_spend_ratio (food, cafe, convenience, etc.)

## 3) Pattern features (rule-based -> ML input)
- impulsive_score (rule-based)
- spike_score (rule-based)
- night_spend_ratio (21~02)
- small_tx_ratio (<= 10,000)
- repeat_24h_count
- weekday_vs_weekend_ratio

## 4) Label design (TBD)
- Option A: regression 0~100 (FHI)
- Option B: 3-class risk level (low/medium/high)

---

# FHI 2.0 (ML) — Data Requirements & Training Plan (Draft)

## A) Minimum Dataset Requirements
- User-level transaction history (at least 30~90 days)
- Required fields per tx: datetime, amount, merchant, category (or mcc-like), payment_method
- Optional: income events, recurring payments, user demographics (non-sensitive)

## B) Feature Windowing
- Weekly window features (last 7 days)
- Monthly window features (last 30 days)
- Trend features (last 30d vs previous 30d)

## C) Candidate Feature Groups
### 1) Volume / Frequency
- tx_count_7d, tx_count_30d
- total_spend_7d, total_spend_30d
- avg_spend_per_tx_30d
- max_single_spend_30d

### 2) Category Mix
- category_spend_ratio_* (food/cafe/convenience/shopping/transport/etc.)
- category_tx_ratio_*

### 3) Time Pattern
- night_spend_ratio (21~02)
- weekend_spend_ratio
- hour_histogram features (bucketed)

### 4) Behavior Signals (rule-based -> numeric)
- impulsive_score_7d (avg / max)
- spike_score_7d (avg / max)
- repeat_purchase_count_24h
- small_tx_ratio (<= 10,000)

## D) Label Options
### Option 1: Regression (0~100)
- Use current rule-based FHI as weak label (initial bootstrap)
- Later replace with user feedback / expert rubric

### Option 2: Classification (risk level)
- low / medium / high risk based on thresholds
- Pros: easier to explain
- Cons: loses granularity

## E) Evaluation & Explainability
- Metrics: MAE/RMSE (regression) or F1/AUROC (classification)
- Explainability: feature importance + SHAP summary (top drivers)

