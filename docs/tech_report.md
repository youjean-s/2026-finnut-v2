# FINNUT FHI 1.0 Rule-based Engine — Technical Report (Draft)

## 1. Overview
- Goal: Push notification → transaction parsing → spending analysis → FHI score
- Scope (Week1~2): rule-based pipeline + format parsers + tests

## 2. System Pipeline
1) Parse push notification text into normalized transaction schema  
2) Categorize merchant into spending category (keyword rules)  
3) Compute impulsive spending indicator (rule-based)  
4) Compute spending spike indicator (rule-based)  
5) Combine into FHI score (0~100)

## 3. Data Schema (Normalized Transaction)
- datetime: datetime
- amount: float (positive spend)
- merchant: str
- category: str | None
- source: str (shinhan/kakaopay/kb/samsung/unknown)
- payment_method: str (card/wallet/unknown)
- raw_text: str

## 4. Key Modules
- utils/parser.py: multi-source parsing + normalization
- utils/category_rules.py: merchant → category mapping
- utils/impulsive_detector.py: impulsive score + flags
- utils/spending_spike.py: spike score + flags
- utils/fhi_calculator.py: final FHI calculation
- demo_pages/: regression/extreme test scripts

## 5. Error Handling & Robustness
- empty input handling
- invalid/negative amount handling
- datetime missing fallback policy
- schema normalization defaults

## 6. Validation (Tests)
- week1 cases: source/payment_method/category expectations
- category regression tests
- extreme input tests (bad amounts, empty list)

## 7. Limitations
- Parser coverage is heuristic; message formats may vary by app/device
- Category mapping depends on keyword list
- Spike/impulsive thresholds need tuning with real user data

## 8. Future Work (FHI 2.0)
- Feature engineering from transaction history
- Label design (regression 0~100 vs risk classes)
- LightGBM training + explainability (feature importance/SHAP)
