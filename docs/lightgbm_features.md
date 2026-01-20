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
