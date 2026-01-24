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


---

# Feature Specification (FHI 2.0 / LightGBM)

## 0) Conventions
- All amounts are positive spend (+).
- Time windows are computed per user.
- If a window has no data, use 0 (or NaN → 0) consistently.

## 1) Base schema (input)
Per transaction:
- datetime: datetime
- amount: float
- merchant: str (or proxy)
- category: str
- payment_method: str (optional)
- source: str (optional)

## 2) Feature Table (per user, per reference date T)
Reference date T = prediction timestamp (e.g., end of day)

### A) Volume / Frequency
| feature | window | type | definition |
|---|---:|---|---|
| tx_count_7d | 7d | int | count(tx in (T-7d, T]) |
| tx_count_30d | 30d | int | count(tx in (T-30d, T]) |
| total_spend_7d | 7d | float | sum(amount) |
| total_spend_30d | 30d | float | sum(amount) |
| avg_spend_per_tx_30d | 30d | float | total_spend_30d / max(tx_count_30d,1) |
| max_single_spend_30d | 30d | float | max(amount) |
| std_spend_30d | 30d | float | std(amount) |

### B) Trend / Change
| feature | window | type | definition |
|---|---:|---|---|
| spend_trend_ratio | 30d vs prev30d | float | (spend_30d - spend_prev30d) / max(spend_prev30d,1) |
| tx_trend_ratio | 30d vs prev30d | float | (tx_30d - tx_prev30d) / max(tx_prev30d,1) |

### C) Category Mix (top-K 또는 고정 카테고리)
고정 카테고리 예: food, cafe, convenience, shopping, transport, housing, beauty, 기타  
| feature | window | type | definition |
|---|---:|---|---|
| cat_spend_ratio_{cat} | 30d | float | sum(amount where category=cat)/max(total_spend_30d,1) |
| cat_tx_ratio_{cat} | 30d | float | count(tx where category=cat)/max(tx_count_30d,1) |
| unique_category_count_30d | 30d | int | number of unique categories |

### D) Time Pattern
| feature | window | type | definition |
|---|---:|---|---|
| night_spend_ratio_30d | 30d | float | sum(amount where hour in [21..23]∪[0..2]) / max(total_spend_30d,1) |
| night_tx_ratio_30d | 30d | float | count(tx at night) / max(tx_count_30d,1) |
| weekend_spend_ratio_30d | 30d | float | sum(amount where weekday in {Sat,Sun}) / max(total_spend_30d,1) |
| weekend_tx_ratio_30d | 30d | float | count(weekend tx) / max(tx_count_30d,1) |

### E) Micro-spend / Repetition
| feature | window | type | definition |
|---|---:|---|---|
| small_tx_ratio_30d | 30d | float | count(amount<=10000)/max(tx_count_30d,1) |
| small_spend_ratio_30d | 30d | float | sum(amount<=10000)/max(total_spend_30d,1) |
| repeat_24h_max_30d | 30d | int | max #tx in any rolling 24h window |
| repeat_24h_avg_30d | 30d | float | avg #tx per rolling 24h window (approx ok) |

### F) Rule-based signals as numeric features (bootstrap)
| feature | window | type | definition |
|---|---:|---|---|
| impulsive_score_7d | 7d | float | average of rule-based impulsive scores over txs |
| impulsive_score_30d | 30d | float | average of rule-based impulsive scores |
| spike_score_7d | 7d | float | rule-based spike score computed on window |
| spike_score_30d | 30d | float | rule-based spike score computed on window |

## 3) Feature Output Shape
- One training row per (user, reference date T)
- Features above + label column

## 4) Notes
- Merchant string은 ML에서 직접 쓰기 어렵기 때문에 기본은 category 기반으로 간다.
- Merchant는 추후 top-N merchant frequency 같은 방식으로만 제한적으로 사용 고려.

