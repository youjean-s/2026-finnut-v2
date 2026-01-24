# Dataset Candidates (for FHI 2.0 ML)

## Candidate A — Kaggle (kartik2112_fraud_detection)
### Why
- 거래 단위 컬럼이 우리가 원하는 형태에 거의 그대로 있음: timestamp / merchant / category / amount
- synthetic이라 개인정보 이슈 없음

### Raw columns
- trans_date_trans_time (timestamp)
- merchant (merchant name)
- category (category string)
- amt (amount)
- + 기타(성별/지역/사기라벨 등)

### Mapping to FINNUT normalized schema
| FINNUT field | Source column | Notes |
|---|---|---|
| datetime | trans_date_trans_time | 그대로 datetime |
| amount | amt | float, 지출=+로 사용 |
| merchant | merchant | 문자열 |
| category | category | 문자열 |
| payment_method | (없음) | 일단 "card" 고정 or "unknown" |
| source | (상수) | "kaggle_fraud_detection" |
| raw_text | (없음) | 원문이 없으므로 None/"generated" |

---

## Candidate B — Kaggle (bhavikjikadara_retail_transactional_dataset)
### Why
- amount + product_category + payment_method가 있어서 “카테고리 믹스/지출 패턴” feature 만들기 좋음
- merchant는 약하지만 brand/name을 proxy로 쓸 수 있음

### Raw columns
- date, time
- amount / total_amount
- product_category
- payment_method
- product_brand, product_type 등

### Mapping to FINNUT normalized schema
| FINNUT field | Source column | Notes |
|---|---|---|
| datetime | date + time | 파싱해서 datetime 생성 |
| amount | amount (or total_amount) | 정책 하나로 고정 |
| merchant | product_brand (fallback name) | merchant proxy |
| category | product_category | 문자열 |
| payment_method | payment_method | 문자열 |
| source | (상수) | "kaggle_retail_tx" |
| raw_text | (없음) | None/"generated" |

---

## Selection Decision
- 1순위 학습/실험: Candidate A (merchant+category가 확실)
- 보조 실험: Candidate B (payment_method/카테고리 분포 다양성 확보)
